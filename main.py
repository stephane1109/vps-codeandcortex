import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import glob
import hashlib
import importlib.util
import re
import select
import shutil
import subprocess
import sys
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import cv2
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from yt_dlp import YoutubeDL

from ticket_gate import enforce_streamlit_access, keep_ticket_alive

st.set_page_config(
    page_title="Extraction multimedia",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .main .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
      }
      section[data-testid="stSidebar"] {
        flex-shrink: 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


APP_DIR = Path(__file__).resolve().parent
HELP_PATH = APP_DIR / "aide.md"
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/data/app"))
APP_NAME = "Extraction multimedia"
APP_TICKET_DEFAULT_ID = "extraction-multimedia"
APP_BUILD = "extraction-multimedia-enforced-ytdlp-timeouts-2026-07-18-16"
SESSIONS_DIR = APP_DATA_DIR / "sessions"
SESSION_ID = st.session_state.setdefault("session_id", uuid.uuid4().hex)
SESSION_DIR = SESSIONS_DIR / SESSION_ID
REPERTOIRE_SORTIE = SESSION_DIR / "fichiers"
REPERTOIRE_TEMP = SESSION_DIR / "tmp"
LATEST_RESULTS_DIR = APP_DATA_DIR / "latest_results" / APP_TICKET_DEFAULT_ID
LATEST_ZIP_PATH = LATEST_RESULTS_DIR / "derniers_resultats.zip"

SEUIL_APERCU_OCTETS = 160 * 1024 * 1024
LONGUEUR_TITRE_MAX = 24
LONGUEUR_PREFIX_ID = 8
USER_AGENT_YOUTUBE_DEFAUT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
    "Gecko/20100101 Firefox/115.0"
)
UPLOAD_VIDEO_EXTENSIONS = [
    "mp4",
    "mov",
    "mkv",
    "webm",
    "avi",
    "m4v",
    "flv",
    "wmv",
    "mpeg",
    "mpg",
    "3gp",
    "ts",
    "m2ts",
]
MEDIA_EXTENSIONS_DETECTION = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".flv",
    ".wmv",
    ".mpeg",
    ".mpg",
    ".3gp",
    ".ts",
    ".m2ts",
    ".m4a",
    ".mp3",
    ".wav",
    ".aac",
    ".ogg",
    ".opus",
    ".mka",
    ".jpg",
    ".jpeg",
    ".png",
}


def journal_debug(message: str) -> None:
    horodatage = time.strftime("%H:%M:%S")
    lignes = st.session_state.setdefault("debug_extraction_lignes", [])
    lignes.append(f"[{horodatage}] {message}")
    st.session_state["debug_extraction_lignes"] = lignes[-250:]


def reinitialiser_debug() -> None:
    st.session_state["debug_extraction_lignes"] = []


def afficher_debug_extraction(expanded: bool = False) -> None:
    lignes = st.session_state.get("debug_extraction_lignes", [])
    if not lignes:
        return
    with st.expander("Debug extraction", expanded=expanded):
        st.code("\n".join(lignes))


def _import_module_local(nom_module: str):
    try:
        return __import__(nom_module)
    except Exception:
        chemin_module = APP_DIR / f"{nom_module}.py"
        spec = importlib.util.spec_from_file_location(nom_module, str(chemin_module))
        module = importlib.util.module_from_spec(spec)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Impossible de charger {nom_module} depuis {chemin_module}")
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module


tl = _import_module_local("timelapse")
ck = _import_module_local("cookies")


def _env_int(nom: str, valeur_defaut: int) -> int:
    try:
        return int(os.environ.get(nom, str(valeur_defaut)))
    except Exception:
        return valeur_defaut


def _env_bool(nom: str, valeur_defaut: bool) -> bool:
    valeur = os.environ.get(nom)
    if valeur is None:
        return valeur_defaut
    return valeur.strip().lower() not in {"0", "false", "non", "no", "off"}


def _masquer_url_sensible(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:***@", url)


FFMPEG_TIMEOUT_SECONDS = max(60, _env_int("APP_FFMPEG_TIMEOUT_SECONDS", 3600))


def load_help_markdown() -> str:
    try:
        return HELP_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Le fichier `aide.md` est introuvable pour cette application."


def render_help_tab() -> None:
    with st.expander("Aide", expanded=False):
        st.markdown(
            """
            <p>
              <a href="https://www.codeandcortex.fr/extraction-multimedia-youtube/"
                 target="_blank" rel="noopener noreferrer">
                Lire l'article du blog : Extraction multimédia YouTube
              </a>
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(load_help_markdown())


def initialiser_repertoires_session() -> None:
    for repertoire in (SESSIONS_DIR, SESSION_DIR, REPERTOIRE_SORTIE, REPERTOIRE_TEMP, LATEST_RESULTS_DIR):
        repertoire.mkdir(parents=True, exist_ok=True)
        os.utime(repertoire, None)


def nettoyer_sessions_expirees() -> None:
    ttl_heures = max(0, _env_int("APP_SESSION_TTL_HOURS", 24))
    if ttl_heures == 0:
        return

    seuil = time.time() - (ttl_heures * 3600)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir() or session_dir.name == SESSION_ID:
            continue
        try:
            if session_dir.stat().st_mtime < seuil:
                shutil.rmtree(session_dir, ignore_errors=True)
        except Exception:
            continue


def nettoyer_derniere_archive_stable() -> None:
    try:
        if LATEST_ZIP_PATH.exists():
            LATEST_ZIP_PATH.unlink()
    except Exception:
        pass


def memoriser_archive_stable(zip_path: Path) -> Optional[Path]:
    try:
        LATEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, LATEST_ZIP_PATH)
        return LATEST_ZIP_PATH if LATEST_ZIP_PATH.is_file() and LATEST_ZIP_PATH.stat().st_size > 0 else None
    except Exception:
        return None


initialiser_repertoires_session()
nettoyer_sessions_expirees()
enforce_streamlit_access(APP_TICKET_DEFAULT_ID, APP_NAME)


def ffmpeg_disponible() -> bool:
    try:
        _ = tl.chemin_ffmpeg()
        return True
    except Exception:
        return False


def nettoyer_titre(titre: str) -> str:
    if not titre:
        titre = "video"
    titre = titre.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    remplacement = {
        "«": "",
        "»": "",
        "“": "",
        "”": "",
        "’": "",
        "‘": "",
        "„": "",
        '"': "",
        "'": "",
        ":": "-",
        "/": "-",
        "\\": "-",
        "|": "-",
        "?": "",
        "*": "",
        "<": "",
        ">": "",
        "\u00A0": " ",
    }
    for ancien, nouveau in remplacement.items():
        titre = titre.replace(ancien, nouveau)
    titre = unicodedata.normalize("NFKD", titre)
    titre = "".join(c for c in titre if not unicodedata.combining(c))
    titre = re.sub(r"[^\w\s-]", "", titre, flags=re.UNICODE)
    titre = re.sub(r"\s+", "_", titre.strip())
    return (titre or "video")[:LONGUEUR_TITRE_MAX]


def generer_nom_base(video_id: str, titre: str) -> str:
    vid = (video_id or "vid")[:LONGUEUR_PREFIX_ID]
    return f"{vid}_{nettoyer_titre(titre)}"


def renommer_sans_collision(src_path: Path, dest_path_base: Path, ext: str = ".mp4") -> Path:
    candidat = Path(f"{dest_path_base}{ext}")
    index = 1
    while candidat.exists():
        candidat = Path(f"{dest_path_base}_{index}{ext}")
        index += 1
    shutil.move(str(src_path), str(candidat))
    return candidat


def taille_fichier(chemin: Path) -> Optional[int]:
    try:
        return chemin.stat().st_size
    except Exception:
        return None


def fichier_media_exploitable(chemin: Path) -> bool:
    try:
        if not chemin.is_file() or chemin.stat().st_size <= 0:
            return False
        if chemin.name.lower() == "cookies.txt":
            return False
        if chemin.suffix.lower() in {".zip", ".part", ".ytdl", ".tmp"}:
            return False
        return chemin.suffix.lower() in MEDIA_EXTENSIONS_DETECTION
    except Exception:
        return False


def fichiers_media_sortie(depuis_timestamp: Optional[float] = None) -> List[Path]:
    fichiers: List[Path] = []
    try:
        for fichier in REPERTOIRE_SORTIE.rglob("*"):
            if not fichier_media_exploitable(fichier):
                continue
            if depuis_timestamp is not None and fichier.stat().st_mtime < depuis_timestamp:
                continue
            fichiers.append(fichier)
    except Exception:
        return []
    fichiers.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return fichiers_valides(fichiers)


def chemins_depuis_info_ytdlp(info: Any) -> List[Path]:
    chemins: List[Path] = []

    def collecter(obj: Any) -> None:
        if isinstance(obj, dict):
            for cle in ("filepath", "filename", "_filename", "__filename", "_prepared_filename"):
                valeur = obj.get(cle)
                if isinstance(valeur, str) and valeur.strip():
                    chemins.append(Path(valeur))
            for cle in ("requested_downloads", "entries", "requested_formats"):
                valeur = obj.get(cle)
                if isinstance(valeur, (list, tuple, dict)):
                    collecter(valeur)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                collecter(item)

    collecter(info)
    return fichiers_valides([chemin for chemin in chemins if fichier_media_exploitable(chemin)])


def qualite_compressee(qualite: str) -> bool:
    return "1280p" in (qualite or "") and "CRF 28" in (qualite or "")


def duree_video_seconds(video_path: Path) -> Optional[int]:
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        return int(round(frames / fps)) if fps > 0 else None
    except Exception:
        return None


def executer_ffmpeg(args: List[str], description: str) -> None:
    commande = list(args)
    if "-nostdin" not in commande:
        commande.insert(1, "-nostdin")
    if "-hide_banner" not in commande:
        commande.insert(2, "-hide_banner")
    if "-loglevel" not in commande:
        commande.insert(3, "-loglevel")
        commande.insert(4, "error")

    journal_debug(f"ffmpeg démarrage : {description}")
    try:
        subprocess.run(
            commande,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
        journal_debug(f"ffmpeg OK : {description}")
    except subprocess.TimeoutExpired as exc:
        journal_debug(f"ffmpeg timeout : {description}")
        raise RuntimeError(
            f"{description} a dépassé le délai maximal ffmpeg ({FFMPEG_TIMEOUT_SECONDS}s). "
            "Réduis l'intervalle ou les options d'images."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        if len(details) > 1200:
            details = details[-1200:]
        journal_debug(f"ffmpeg erreur : {description} | {details or exc}")
        raise RuntimeError(f"{description} a échoué avec ffmpeg : {details or exc}") from exc
    finally:
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)


def zipper_sur_disque(fichiers: List[Path], chemin_zip: Path) -> Path:
    fichiers_uniques: List[Path] = []
    deja_vus = set()
    for fichier in fichiers:
        fichier = Path(fichier)
        if not fichier.is_file() or fichier.stat().st_size <= 0:
            continue
        cle = str(fichier.resolve()) if fichier.exists() else str(fichier)
        if cle in deja_vus:
            continue
        fichiers_uniques.append(fichier)
        deja_vus.add(cle)

    chemin_zip.parent.mkdir(parents=True, exist_ok=True)
    if chemin_zip.exists():
        chemin_zip.unlink()

    journal_debug(f"Création ZIP : {chemin_zip.name} avec {len(fichiers_uniques)} fichier(s)")
    # Les médias sont déjà compressés. ZIP_STORED évite une recompaction lente
    # qui peut donner l'impression que l'application tourne sans fin.
    with zipfile.ZipFile(str(chemin_zip), "w", compression=zipfile.ZIP_STORED) as archive:
        for index, fichier in enumerate(fichiers_uniques, start=1):
            try:
                arcname = str(fichier.relative_to(REPERTOIRE_SORTIE))
            except ValueError:
                arcname = fichier.name
            archive.write(str(fichier), arcname=arcname)
            if index % 100 == 0:
                keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    journal_debug(f"ZIP écrit : {chemin_zip} ({chemin_zip.stat().st_size if chemin_zip.exists() else 0} octets)")
    return chemin_zip


def nettoyer_resultats_session() -> None:
    """Nettoie les anciens médias sans supprimer le cookies.txt de la session."""
    REPERTOIRE_SORTIE.mkdir(parents=True, exist_ok=True)
    nb_supprimes = 0
    for element in REPERTOIRE_SORTIE.iterdir():
        if element.name.lower() == "cookies.txt":
            continue
        try:
            if element.is_dir():
                shutil.rmtree(element, ignore_errors=True)
                nb_supprimes += 1
            elif element.is_file():
                element.unlink()
                nb_supprimes += 1
        except Exception:
            continue
    journal_debug(f"Nettoyage dossier résultats : {nb_supprimes} élément(s) supprimé(s), cookies conservé")


def lister_sorties(prefix: str) -> List[Path]:
    motifs = [
        str(REPERTOIRE_SORTIE / f"{prefix}*.mp4"),
        str(REPERTOIRE_SORTIE / f"{prefix}*.mp3"),
        str(REPERTOIRE_SORTIE / f"{prefix}*.wav"),
        str(REPERTOIRE_SORTIE / f"img1_{prefix}" / "i_*.jpg"),
        str(REPERTOIRE_SORTIE / f"img25_{prefix}" / "i_*.jpg"),
        str(REPERTOIRE_SORTIE / f"img1_full_{prefix}" / "i_*.jpg"),
        str(REPERTOIRE_SORTIE / f"img25_full_{prefix}" / "i_*.jpg"),
    ]
    fichiers: List[Path] = []
    for motif in motifs:
        fichiers.extend(Path(p) for p in glob.glob(motif))
    fichiers.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return fichiers


def fichiers_valides(fichiers: List[Path]) -> List[Path]:
    """Ne conserver que les fichiers réellement écrits et non vides."""
    valides: List[Path] = []
    deja_vus = set()
    for fichier in fichiers:
        fichier = Path(fichier)
        try:
            cle = str(fichier.resolve())
            if cle in deja_vus:
                continue
            if fichier.is_file() and fichier.stat().st_size > 0:
                valides.append(fichier)
                deja_vus.add(cle)
        except Exception:
            continue
    return valides


def fichiers_exportables_session() -> List[Path]:
    """Liste les fichiers produits par l'application, sans réinclure les archives."""
    candidats: List[Path] = []
    try:
        for fichier in REPERTOIRE_SORTIE.rglob("*"):
            if not fichier_media_exploitable(fichier):
                continue
            candidats.append(fichier)
    except Exception:
        return []
    candidats.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return fichiers_valides(candidats)


def dernier_zip_disponible() -> Optional[Path]:
    zip_path_brut = st.session_state.get("dernier_zip_path")
    if zip_path_brut:
        zip_path = Path(zip_path_brut)
        if zip_path.is_file() and zip_path.stat().st_size > 0:
            return zip_path

    try:
        zips = sorted(
            REPERTOIRE_SORTIE.glob("resultats*.zip"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
    except Exception:
        zips = []
    for zip_path in zips:
        if zip_path.is_file() and zip_path.stat().st_size > 0:
            return zip_path
    if LATEST_ZIP_PATH.is_file() and LATEST_ZIP_PATH.stat().st_size > 0:
        return LATEST_ZIP_PATH
    return None


def preparer_archive_session() -> tuple[Optional[Path], List[Path], str]:
    fichiers = fichiers_valides([Path(path) for path in st.session_state.get("derniers_fichiers", [])])
    if not fichiers:
        fichiers = fichiers_exportables_session()
    if not fichiers:
        return None, [], "Aucun fichier résultat exportable n'a été trouvé dans cette session."

    zip_path = REPERTOIRE_SORTIE / f"resultats_session_{SESSION_ID[:8]}.zip"
    zipper_sur_disque(fichiers, zip_path)
    if not zip_path.is_file() or zip_path.stat().st_size <= 0:
        return None, fichiers, f"Archive générée mais vide : {zip_path.name}"

    message = f"Archive prête : {zip_path.name} ({zip_path.stat().st_size / (1024 * 1024):.1f} Mo)."
    enregistrer_resultats_generes(zip_path, fichiers, message)
    return zip_path, fichiers, message


def obtenir_zip_telechargeable() -> tuple[Optional[Path], str]:
    zip_path = dernier_zip_disponible()
    if zip_path is not None:
        return zip_path, st.session_state.get("dernier_message_resultats") or f"Archive disponible : {zip_path.name}"

    fichiers = fichiers_valides([Path(path) for path in st.session_state.get("derniers_fichiers", [])])
    if not fichiers:
        fichiers = fichiers_exportables_session()
    if not fichiers:
        return None, "Aucun résultat téléchargeable pour le moment."

    zip_path, _fichiers, message = preparer_archive_session()
    if zip_path is not None:
        return zip_path, message
    return None, message


def afficher_telechargement_zip(zip_path: Path, key_prefix: str, message: str) -> None:
    taille_zip = zip_path.stat().st_size / (1024 * 1024)
    with zip_path.open("rb") as flux_zip:
        st.download_button(
            "Télécharger les résultats (.zip)",
            data=flux_zip,
            file_name=zip_path.name,
            mime="application/zip",
            key=f"{key_prefix}_download_zip_{zip_path.name}_{int(zip_path.stat().st_mtime)}",
            use_container_width=True,
        )
    st.caption(f"{message} · {taille_zip:.1f} Mo")


def afficher_bouton_telechargement_resultats(key_prefix: str, titre: bool = False) -> None:
    if titre:
        st.subheader("Télécharger les résultats")

    zip_path, message = obtenir_zip_telechargeable()
    if zip_path is not None:
        afficher_telechargement_zip(zip_path, key_prefix, message)
        return

    st.caption(message)


def diagnostic_contenu_sortie(max_items: int = 80) -> str:
    lignes: List[str] = []
    try:
        elements = sorted(REPERTOIRE_SORTIE.rglob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    except Exception as exc:
        return f"Impossible de lire le dossier de sortie : {exc}"

    for element in elements[:max_items]:
        try:
            type_element = "dir" if element.is_dir() else "file"
            taille = element.stat().st_size if element.is_file() else 0
            rel = element.relative_to(REPERTOIRE_SORTIE)
            lignes.append(f"{type_element}\t{taille} octets\t{rel}")
        except Exception:
            continue
    return "\n".join(lignes) if lignes else "Le dossier de sortie est vide."


def enregistrer_resultats_generes(zip_path: Path, fichiers: List[Path], message: str) -> None:
    zip_stable = memoriser_archive_stable(zip_path)
    st.session_state["dernier_zip_path"] = str(zip_path)
    if zip_stable is not None:
        st.session_state["dernier_zip_stable_path"] = str(zip_stable)
    st.session_state["derniers_fichiers"] = [str(path) for path in fichiers_valides(fichiers)]
    st.session_state["dernier_message_resultats"] = message
    st.session_state["derniere_erreur_resultats"] = ""
    st.session_state["resultats_revision"] = int(st.session_state.get("resultats_revision", 0)) + 1


def enregistrer_erreur_resultats(message: str) -> None:
    st.session_state["derniere_erreur_resultats"] = message


def afficher_resultats_generes() -> None:
    zip_path_brut = st.session_state.get("dernier_zip_path")
    fichiers = fichiers_valides([Path(path) for path in st.session_state.get("derniers_fichiers", [])])
    if not fichiers:
        fichiers = fichiers_exportables_session()
    if (
        not zip_path_brut
        and not fichiers
        and not st.session_state.get("derniere_erreur_resultats")
        and not (LATEST_ZIP_PATH.is_file() and LATEST_ZIP_PATH.stat().st_size > 0)
    ):
        return

    st.subheader("Derniers fichiers générés")
    if st.session_state.get("derniere_erreur_resultats"):
        st.warning(st.session_state["derniere_erreur_resultats"])

    zip_path, message_zip = obtenir_zip_telechargeable()
    if zip_path and zip_path.is_file() and zip_path.stat().st_size > 0:
        st.success(message_zip)
        afficher_telechargement_zip(zip_path, "download_zip", f"Archive : {zip_path.name}")
    elif fichiers:
        st.warning(message_zip)

    if not fichiers:
        st.info("Aucun fichier exploitable n'est actuellement mémorisé pour cette session.")
        with st.expander("Diagnostic du dossier de sortie", expanded=True):
            st.write(f"Dossier de session : `{SESSION_DIR}`")
            st.write(f"Dossier des fichiers : `{REPERTOIRE_SORTIE}`")
            st.write(f"Dernière archive stable : `{LATEST_ZIP_PATH}`")
            st.code(diagnostic_contenu_sortie())


def hash_job(source_id: str, fps: int, intervalle: Optional[tuple[int, int]]) -> str:
    hachage = hashlib.sha1()
    hachage.update(source_id.encode("utf-8"))
    hachage.update(str(fps).encode("utf-8"))
    if intervalle:
        hachage.update(f"{intervalle[0]}-{intervalle[1]}".encode("utf-8"))
    return hachage.hexdigest()[:16]


def _logger_silencieux(actif: bool):
    if actif:
        return None

    class DebugLogger:
        def debug(self, msg):  # noqa: ANN001
            pass

        def warning(self, msg):  # noqa: ANN001
            journal_debug(f"yt-dlp warning : {msg}")

        def error(self, msg):  # noqa: ANN001
            journal_debug(f"yt-dlp error : {msg}")

    return DebugLogger()


def _appliquer_clients_youtube(opts_base: Dict[str, Any], clients: Optional[List[str]]) -> Dict[str, Any]:
    opts = dict(opts_base)
    extractor_args = dict(opts.get("extractor_args") or {})
    youtube_args = dict(extractor_args.get("youtube") or {})
    if clients:
        youtube_args["player_client"] = clients
    else:
        youtube_args.pop("player_client", None)
    if youtube_args:
        extractor_args["youtube"] = youtube_args
    else:
        extractor_args.pop("youtube", None)
    if extractor_args:
        opts["extractor_args"] = extractor_args
    else:
        opts.pop("extractor_args", None)
    return opts


def diagnostiquer_formats_youtube(url: str, opts_base: Dict[str, Any]) -> str:
    probe_opts = _appliquer_clients_youtube(opts_base, None)
    for cle in ("format", "download_sections", "force_keyframes_at_cuts", "merge_output_format"):
        probe_opts.pop(cle, None)
    probe_opts["simulate"] = True
    probe_opts["skip_download"] = True
    probe_opts["ignore_no_formats_error"] = True
    try:
        with YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return f"Diagnostic formats impossible : {str(exc) or repr(exc)}"

    formats = (info or {}).get("formats") or []
    medias = []
    for fmt in formats:
        vcodec = str(fmt.get("vcodec") or "none")
        acodec = str(fmt.get("acodec") or "none")
        if vcodec != "none" or acodec != "none":
            medias.append(fmt)
    exemples = []
    for fmt in medias[:8]:
        exemples.append(
            f"{fmt.get('format_id')}:{fmt.get('ext')} v={fmt.get('vcodec')} a={fmt.get('acodec')} h={fmt.get('height')}"
        )
    suffixe = " | exemples : " + " ; ".join(exemples) if exemples else ""
    return f"Formats détectés : {len(formats)} total, {len(medias)} média téléchargeable(s){suffixe}"


def _int_format(fmt: Dict[str, Any], cle: str, defaut: int = 0) -> int:
    try:
        valeur = fmt.get(cle)
        if valeur is None:
            return defaut
        return int(float(valeur))
    except Exception:
        return defaut


def _float_format(fmt: Dict[str, Any], cle: str, defaut: float = 0.0) -> float:
    try:
        valeur = fmt.get(cle)
        if valeur is None:
            return defaut
        return float(valeur)
    except Exception:
        return defaut


def _id_format(fmt: Dict[str, Any]) -> str:
    return str(fmt.get("format_id") or "").strip()


def _est_media_youtube(fmt: Dict[str, Any]) -> bool:
    """Exclut les storyboards/images et garde tout format audio/vidéo réel."""
    ext = str(fmt.get("ext") or "").lower()
    vcodec = str(fmt.get("vcodec") or "none").lower()
    acodec = str(fmt.get("acodec") or "none").lower()
    format_id = _id_format(fmt)
    if not format_id or ext in {"mhtml", "html", "json"}:
        return False
    if vcodec == "none" and acodec == "none":
        return False
    return True


def _score_video_youtube(fmt: Dict[str, Any], qualite: str) -> float:
    hauteur = _int_format(fmt, "height")
    largeur = _int_format(fmt, "width")
    fps = _float_format(fmt, "fps")
    tbr = _float_format(fmt, "tbr")
    ext = str(fmt.get("ext") or "").lower()
    vcodec = str(fmt.get("vcodec") or "").lower()
    protocole = str(fmt.get("protocol") or "").lower()
    compresse = qualite_compressee(qualite)

    if compresse:
        score_hauteur = min(hauteur or 360, 720) * 6 - max(0, hauteur - 720) * 30
    else:
        score_hauteur = (hauteur or 360) * 8

    score = score_hauteur + min(largeur, 3840) * 0.2 + min(fps, 60) * 4 + min(tbr, 8000) * 0.1
    if ext == "mp4":
        score += 3500
    elif ext in {"webm", "mkv"}:
        score += 1200
    if vcodec.startswith(("avc", "h264")):
        score += 1800
    elif vcodec.startswith(("vp9", "vp09", "av01")):
        score += 900
    if "m3u8" in protocole:
        score -= 15000
    elif protocole.startswith("https") or protocole == "http":
        score += 30000
    else:
        score += 1000
    return score


def _score_audio_youtube(fmt: Dict[str, Any]) -> float:
    ext = str(fmt.get("ext") or "").lower()
    acodec = str(fmt.get("acodec") or "").lower()
    abr = _float_format(fmt, "abr")
    tbr = _float_format(fmt, "tbr")
    score = min(abr or tbr, 512) * 10
    if ext in {"m4a", "mp4"}:
        score += 2500
    elif ext in {"webm", "opus"}:
        score += 1800
    if acodec.startswith("mp4a"):
        score += 1000
    elif "opus" in acodec:
        score += 800
    return score


def analyser_formats_youtube(info: Dict[str, Any], qualite: str) -> tuple[Optional[str], str, str]:
    """Analyse la liste réelle des formats YouTube et retourne un sélecteur yt-dlp.

    Cette fonction évite la logique fragile "un format fixe pour toutes les
    vidéos". Elle lit tous les formats renvoyés par yt-dlp pour l'URL courante,
    exclut les storyboards, puis choisit soit un format progressif audio+vidéo,
    soit une paire vidéo+audio à fusionner par ffmpeg.
    """
    formats = [fmt for fmt in (info.get("formats") or []) if isinstance(fmt, dict) and _est_media_youtube(fmt)]
    progressifs = [
        fmt
        for fmt in formats
        if str(fmt.get("vcodec") or "none").lower() != "none"
        and str(fmt.get("acodec") or "none").lower() != "none"
    ]
    videos = [
        fmt
        for fmt in formats
        if str(fmt.get("vcodec") or "none").lower() != "none"
        and str(fmt.get("acodec") or "none").lower() == "none"
    ]
    audios = [
        fmt
        for fmt in formats
        if str(fmt.get("vcodec") or "none").lower() == "none"
        and str(fmt.get("acodec") or "none").lower() != "none"
    ]

    resume = (
        f"{len(formats)} format(s) média analysé(s) : "
        f"{len(progressifs)} progressif(s), {len(videos)} vidéo seule, {len(audios)} audio seul."
    )
    format_env = os.environ.get("YTDLP_FORMAT", "").strip()
    if format_env:
        return format_env, "variable YTDLP_FORMAT", resume

    if not qualite_compressee(qualite) and videos and audios:
        videos.sort(key=lambda fmt: _score_video_youtube(fmt, qualite), reverse=True)
        audios.sort(key=_score_audio_youtube, reverse=True)
        video = videos[0]
        audio = audios[0]
        selecteur = f"{_id_format(video)}+{_id_format(audio)}"
        label = (
            f"fusion {_id_format(video)}+{_id_format(audio)} "
            f"video={video.get('ext')} {video.get('height') or '?'}p "
            f"proto={video.get('protocol') or '?'} "
            f"audio={audio.get('ext')} {audio.get('abr') or audio.get('tbr') or '?'}k"
        )
        return selecteur, label, resume

    if progressifs:
        progressifs.sort(key=lambda fmt: _score_video_youtube(fmt, qualite), reverse=True)
        choix = progressifs[0]
        selecteur = _id_format(choix)
        label = (
            f"progressif {selecteur} "
            f"{choix.get('ext')} {choix.get('height') or '?'}p "
            f"proto={choix.get('protocol') or '?'} "
            f"v={choix.get('vcodec')} a={choix.get('acodec')}"
        )
        return selecteur, label, resume

    if videos and audios:
        videos.sort(key=lambda fmt: _score_video_youtube(fmt, qualite), reverse=True)
        audios.sort(key=_score_audio_youtube, reverse=True)
        video = videos[0]
        audio = audios[0]
        selecteur = f"{_id_format(video)}+{_id_format(audio)}"
        label = (
            f"fusion {_id_format(video)}+{_id_format(audio)} "
            f"video={video.get('ext')} {video.get('height') or '?'}p "
            f"proto={video.get('protocol') or '?'} "
            f"audio={audio.get('ext')} {audio.get('abr') or audio.get('tbr') or '?'}k"
        )
        return selecteur, label, resume

    if videos:
        videos.sort(key=lambda fmt: _score_video_youtube(fmt, qualite), reverse=True)
        choix = videos[0]
        return _id_format(choix), f"vidéo seule {_id_format(choix)} {choix.get('ext')}", resume

    if audios:
        audios.sort(key=_score_audio_youtube, reverse=True)
        choix = audios[0]
        return _id_format(choix), f"audio seul {_id_format(choix)} {choix.get('ext')}", resume

    return None, "aucun format audio/vidéo exploitable", resume


def _opts_communs(verbose: bool, cookies_path: Optional[Path], user_agent: str) -> Dict[str, Any]:
    user_agent_final = (user_agent or "").strip() or USER_AGENT_YOUTUBE_DEFAUT
    youtube_args: Dict[str, List[str]] = {}
    po_token_args = [
        item.strip()
        for item in os.environ.get("YTDLP_YOUTUBE_PO_TOKEN_ARGS", "").split(",")
        if item.strip()
    ]
    if po_token_args:
        youtube_args["po_token"] = po_token_args
        # Ne pas forcer youtube:formats=missing_pot ici : cela peut masquer
        # les formats MP4 classiques et provoquer "Requested format is not
        # available" alors que YouTube expose bien un format exploitable.
    opts: Dict[str, Any] = {
        "paths": {"home": str(REPERTOIRE_SORTIE)},
        "outtmpl": {"default": "%(id)s.%(ext)s"},
        "noplaylist": True,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 1,
        "sleep_interval_requests": 1,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": user_agent_final,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.youtube.com/",
        },
        "geo_bypass": True,
        "nocheckcertificate": True,
        "restrictfilenames": True,
        "trim_file_name": 80,
        # yt-dlp peut recopier la date YouTube d'origine sur le fichier final.
        # On désactive ce comportement pour que la détection post-téléchargement
        # retrouve bien le média créé pendant la session courante.
        "updatetime": False,
    }
    # Le format est choisi dans telecharger_preparer_video(), tentative par
    # tentative, pour pouvoir ignorer proprement une variable YTDLP_FORMAT
    # invalide et retomber sur un MP4 progressif fiable.
    # YTDLP_IMPERSONATE reste volontairement optionnel : force a "chrome" par
    # defaut, il peut provoquer un AssertionError dans l'API Python de yt-dlp.
    impersonate_client = os.environ.get("YTDLP_IMPERSONATE", "").strip()
    if impersonate_client:
        opts["impersonate"] = impersonate_client
    clients_env = [
        client.strip()
        for client in os.environ.get("YTDLP_PLAYER_CLIENTS", "").split(",")
        if client.strip()
    ]
    if clients_env:
        youtube_args["player_client"] = clients_env
    remote_components_env = [
        item.strip()
        for item in os.environ.get("YTDLP_REMOTE_COMPONENTS", "").split(",")
        if item.strip()
    ]
    if remote_components_env:
        opts["remote_components"] = set(remote_components_env)
    if youtube_args:
        opts["extractor_args"] = {"youtube": youtube_args}
    logger = _logger_silencieux(verbose)
    if logger is not None:
        opts["logger"] = logger
    if cookies_path:
        opts["cookiefile"] = str(cookies_path)
    return opts


def telecharger_preparer_video(
    url: str,
    cookies_path: Optional[Path],
    user_agent: str,
    verbose: bool,
    qualite: str,
    utiliser_intervalle: bool,
    debut: int,
    fin: int,
):
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    st.write("Téléchargement / préparation de la vidéo en cours...")
    journal_debug("Début préparation YouTube")
    journal_debug(f"URL renseignée : {'oui' if url else 'non'} | cookies : {'oui' if cookies_path else 'non'} | intervalle : {utiliser_intervalle}")
    journal_debug(f"yt-dlp version : {getattr(yt_dlp.version, '__version__', 'inconnue')}")
    debut_telechargement = time.time() - 2

    ydl_opts = _opts_communs(verbose, cookies_path, user_agent)
    journal_debug(f"Arguments YouTube yt-dlp : {ydl_opts.get('extractor_args', {}).get('youtube', {})}")
    journal_debug(f"Impersonation yt-dlp : {ydl_opts.get('impersonate') or 'désactivée'}")
    if utiliser_intervalle:
        ydl_opts["download_sections"] = [{"section": f"*{debut}-{fin}"}]
        ydl_opts["force_keyframes_at_cuts"] = True

    def _extractor_args_cli(opts: Dict[str, Any]) -> List[str]:
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        fragments: List[str] = []
        for cle in ("player_client", "po_token"):
            valeur = youtube_args.get(cle)
            if isinstance(valeur, (list, tuple, set)):
                valeurs = [str(item).strip() for item in valeur if str(item).strip()]
            elif valeur:
                valeurs = [str(valeur).strip()]
            else:
                valeurs = []
            if valeurs:
                fragments.append(f"{cle}={','.join(valeurs)}")
        if not fragments:
            return []
        return ["--extractor-args", "youtube:" + ";".join(fragments)]

    def _selecteurs_telechargement(selecteur_analyse: Optional[str], qualite_video: str) -> List[str]:
        """Construit une liste de sélecteurs yt-dlp robustes.

        yt-dlp recommande les sélecteurs génériques `bestvideo*+bestaudio/best`
        plutôt qu'une liste fermée de formats numériques YouTube. L'application
        garde le sélecteur détecté par analyse, mais elle le place derrière les
        sélecteurs génériques afin de laisser ffmpeg fusionner/remuxer proprement
        tous les conteneurs exposés par YouTube.
        """
        candidats: List[str] = []
        if selecteur_analyse:
            # Si l'analyse trouve un format progressif audio+vidéo comme 18,
            # on le tente en premier : un seul téléchargement est plus fiable
            # sur un VPS qu'une fusion vidéo+audio en deux connexions CDN.
            if "/" not in selecteur_analyse and "+" not in selecteur_analyse and not os.environ.get("YTDLP_FORMAT", "").strip():
                candidats.append(f"{selecteur_analyse}/best[ext=mp4]/best")
            candidats.append(selecteur_analyse)

        if qualite_compressee(qualite_video):
            candidats.extend(
                [
                    "18/best[height<=720][ext=mp4]/best[height<=720]/best",
                    "best[height<=480][ext=mp4]/best[height<=480]/best",
                    "bv*[height<=720]+ba/b[height<=720]/best[height<=720]/best",
                    "bv*[height<=480]+ba/b[height<=480]/best[height<=480]/best",
                ]
            )
        else:
            candidats.extend(
                [
                    "best[ext=mp4]/best",
                    "bv*+ba/b",
                    "bestvideo*+bestaudio/best",
                ]
            )

        selecteurs: List[str] = []
        deja_vus = set()
        for candidat in candidats:
            candidat = (candidat or "").strip()
            if candidat and candidat not in deja_vus:
                selecteurs.append(candidat)
                deja_vus.add(candidat)
        return selecteurs

    def _telecharger_cli(opts: Dict[str, Any], selecteur_format: str, info_probe: Dict[str, Any]) -> Dict[str, Any]:
        headers = opts.get("http_headers") or {}
        timeout_seconds = max(900, _env_int("YTDLP_DOWNLOAD_TIMEOUT_SECONDS", 900))
        socket_timeout_seconds = max(30, _env_int("YTDLP_SOCKET_TIMEOUT_SECONDS", 30))
        retries = max(10, _env_int("YTDLP_RETRIES", 10))
        fragment_retries = max(10, _env_int("YTDLP_FRAGMENT_RETRIES", 10))
        proxy_url = (
            os.environ.get("YTDLP_PROXY_URL", "").strip()
            or os.environ.get("HTTPS_PROXY", "").strip()
            or os.environ.get("HTTP_PROXY", "").strip()
        )
        geo_proxy_url = os.environ.get("YTDLP_GEO_VERIFICATION_PROXY_URL", "").strip()
        source_address = os.environ.get("YTDLP_SOURCE_ADDRESS", "").strip()
        selecteur_effectif = selecteur_format
        commande = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--no-simulate",
            "--force-overwrites",
            "--progress",
            "--progress-delta",
            "5",
            "--no-mtime",
            "--newline",
            "--retries",
            str(retries),
            "--fragment-retries",
            str(fragment_retries),
            "--socket-timeout",
            str(socket_timeout_seconds),
            "--restrict-filenames",
            "--trim-filenames",
            "80",
            "-P",
            str(REPERTOIRE_SORTIE),
            "-o",
            "yt_%(id)s.%(ext)s",
            "-f",
            selecteur_effectif,
        ]
        if _env_bool("YTDLP_FORCE_IPV4", False):
            commande.append("--force-ipv4")
        if _env_bool("YTDLP_FORCE_IPV6", False):
            commande.append("--force-ipv6")
        if proxy_url:
            commande += ["--proxy", proxy_url]
        if geo_proxy_url:
            commande += ["--geo-verification-proxy", geo_proxy_url]
        if source_address:
            commande += ["--source-address", source_address]
        if "+" in selecteur_effectif:
            # MKV accepte mieux les couples vidéo/audio hétérogènes. Le MP4
            # final est ensuite produit par notre étape ffmpeg contrôlée.
            commande += ["--merge-output-format", "mkv"]
        if utiliser_intervalle:
            commande += ["--download-sections", f"*{debut}-{fin}", "--force-keyframes-at-cuts"]
        if opts.get("cookiefile"):
            commande += ["--cookies", str(opts["cookiefile"])]
        if headers.get("User-Agent"):
            commande += ["--user-agent", str(headers["User-Agent"])]
        if headers.get("Referer"):
            commande += ["--referer", str(headers["Referer"])]
        if headers.get("Accept-Language"):
            commande += ["--add-header", f"Accept-Language:{headers['Accept-Language']}"]
        commande += _extractor_args_cli(opts)
        commande.append(url)

        journal_debug(
            "yt-dlp CLI démarrage : "
            f"format={selecteur_effectif} timeout={timeout_seconds}s "
            f"socket={socket_timeout_seconds}s retries={retries}/{fragment_retries} "
            f"ipv4={'oui' if _env_bool('YTDLP_FORCE_IPV4', False) else 'non'} "
            f"ipv6={'oui' if _env_bool('YTDLP_FORCE_IPV6', False) else 'non'} "
            f"proxy={'oui ' + _masquer_url_sensible(proxy_url) if proxy_url else 'non'}"
        )
        statut_ytdlp = st.empty()
        lignes_sortie: List[str] = []
        debut_process = time.time()
        dernier_keepalive = 0.0
        dernier_scan_partiel = 0.0
        processus = subprocess.Popen(
            commande,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def _journaliser_ligne_cli(ligne: str) -> None:
            ligne = ligne.strip()
            if not ligne:
                return
            lignes_sortie.append(ligne)
            ligne_min = ligne.lower()
            utile = (
                "[download]" in ligne_min
                or "destination" in ligne_min
                or "merging" in ligne_min
                or "deleting original" in ligne_min
                or "has already been downloaded" in ligne_min
                or "error" in ligne_min
                or "warning" in ligne_min
                or "ffmpeg" in ligne_min
            )
            if utile:
                journal_debug(f"yt-dlp CLI : {ligne[:500]}")
                statut_ytdlp.caption(ligne[:500])

        try:
            while True:
                if processus.stdout is not None:
                    prets, _, _ = select.select([processus.stdout], [], [], 0.5)
                    if prets:
                        ligne = processus.stdout.readline()
                        if ligne:
                            _journaliser_ligne_cli(ligne)

                code_retour = processus.poll()
                if code_retour is not None:
                    if processus.stdout is not None:
                        reste = processus.stdout.read()
                        if reste:
                            for ligne_reste in reste.splitlines():
                                _journaliser_ligne_cli(ligne_reste)
                    break

                maintenant = time.time()
                if maintenant - dernier_keepalive >= 15:
                    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
                    dernier_keepalive = maintenant

                if maintenant - dernier_scan_partiel >= 20:
                    partiels = sorted(
                        list(REPERTOIRE_SORTIE.rglob("*.part")) + list(REPERTOIRE_SORTIE.rglob("*.ytdl")),
                        key=lambda p: p.stat().st_mtime if p.exists() else 0,
                        reverse=True,
                    )
                    if partiels:
                        for partiel in partiels[:3]:
                            try:
                                journal_debug(f"yt-dlp partiel : {partiel.name} ({partiel.stat().st_size} octets)")
                            except Exception:
                                pass
                    dernier_scan_partiel = maintenant

                if maintenant - debut_process > timeout_seconds:
                    processus.kill()
                    try:
                        processus.communicate(timeout=5)
                    except Exception:
                        pass
                    raise RuntimeError(f"yt-dlp CLI timeout après {timeout_seconds}s")
        finally:
            try:
                statut_ytdlp.empty()
            except Exception:
                pass

        if processus.returncode != 0:
            detail = lignes_sortie[-1] if lignes_sortie else f"code retour {processus.returncode}"
            raise RuntimeError(detail)

        fichiers_cli = fichiers_media_sortie(depuis_timestamp=debut_telechargement)
        if not fichiers_cli:
            fichiers_cli = fichiers_media_sortie()
        journal_debug(f"yt-dlp CLI terminé : {len(fichiers_cli)} fichier(s) média visible(s)")
        for fichier in fichiers_cli[:8]:
            journal_debug(f" - CLI : {fichier.name} ({fichier.stat().st_size} octets)")
        if not fichiers_cli:
            journal_debug("Diagnostic dossier après yt-dlp CLI :")
            for ligne in diagnostic_contenu_sortie(25).splitlines():
                journal_debug(ligne[:500])
            raise RuntimeError("yt-dlp CLI terminé sans fichier média détecté dans le dossier de sortie.")

        info_local = dict(info_probe)
        info_local["_format_selector"] = selecteur_effectif
        return info_local

    def _telecharger_api_ytdlp(opts: Dict[str, Any], selecteur_format: Optional[str]) -> Optional[Dict[str, Any]]:
        """Fallback proche de StopMotion : laisser YoutubeDL gérer le téléchargement.

        La CLI donne un suivi fin, mais elle est volontairement bornée. Si le VPS
        met longtemps à joindre le CDN YouTube, ce fallback reprend la logique
        plus tolérante utilisée par StopMotion.
        """
        opts_api = dict(opts)
        opts_api["format"] = selecteur_format or "18/22/bestvideo*+bestaudio/best[acodec!=none][vcodec!=none]/best"
        opts_api["merge_output_format"] = "mp4"
        opts_api["socket_timeout"] = max(30, _env_int("YTDLP_SOCKET_TIMEOUT_SECONDS", 30))
        opts_api["retries"] = max(10, _env_int("YTDLP_RETRIES", 10))
        opts_api["fragment_retries"] = max(10, _env_int("YTDLP_FRAGMENT_RETRIES", 10))
        opts_api["extractor_retries"] = max(1, _env_int("YTDLP_EXTRACTOR_RETRIES", 3))
        opts_api["quiet"] = not verbose
        opts_api["no_warnings"] = False
        journal_debug(
            "yt-dlp API fallback démarrage : "
            f"format={opts_api['format']} socket={opts_api['socket_timeout']}s "
            f"retries={opts_api['retries']}/{opts_api['fragment_retries']}"
        )
        with YoutubeDL(opts_api) as ydl:
            return ydl.extract_info(url, download=True) or {}

    def _erreur_reseau_cdn(message: str) -> bool:
        message_min = (message or "").lower()
        marqueurs = [
            "googlevideo.com",
            "failed to resolve",
            "address family for hostname not supported",
            "connect timeout",
            "timed out",
            "temporary failure in name resolution",
            "network is unreachable",
            "name or service not known",
        ]
        return any(marqueur in message_min for marqueur in marqueurs)

    def _analyser_info(opts: Dict[str, Any]) -> Dict[str, Any]:
        opts_probe = dict(opts)
        for cle in ("format", "download_sections", "force_keyframes_at_cuts", "merge_output_format"):
            opts_probe.pop(cle, None)
        opts_probe["simulate"] = True
        opts_probe["skip_download"] = True
        opts_probe["ignore_no_formats_error"] = True
        with YoutubeDL(opts_probe) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def _sans_cookiefile(opts: Dict[str, Any]) -> Dict[str, Any]:
        opts_sans_cookies = dict(opts)
        opts_sans_cookies.pop("cookiefile", None)
        return opts_sans_cookies

    profils_clients: List[tuple[str, Optional[List[str]]]] = [("auto", None), ("android", ["android"])]
    clients_forces = (
        ydl_opts.get("extractor_args", {})
        .get("youtube", {})
        .get("player_client")
    )
    if isinstance(clients_forces, list) and clients_forces:
        profils_clients.append(("coolify", [str(client) for client in clients_forces]))
    profils_clients.extend(
        [
            ("source", ["android", "ios", "mweb", "web"]),
            ("web", ["web"]),
            ("mweb", ["mweb"]),
            ("ios", ["ios"]),
        ]
    )

    erreurs_fallback: List[str] = []
    info = None
    if cookies_path:
        bases_ytdlp: List[tuple[str, Dict[str, Any]]] = [
            ("avec-cookies", ydl_opts),
            ("sans-cookies", _sans_cookiefile(ydl_opts)),
        ]
        journal_debug("Cookies fournis : essai avec cookies d'abord, puis secours public sans cookies.")
    else:
        bases_ytdlp = [("sans-cookies", ydl_opts)]

    for label_acces, opts_base_acces in bases_ytdlp:
        journal_debug(f"Mode accès YouTube : {label_acces}")
        for label_client, clients in profils_clients:
            opts_client = _appliquer_clients_youtube(opts_base_acces, clients)
            clients_journal = opts_client.get("extractor_args", {}).get("youtube", {}).get("player_client") or "auto"
            journal_debug(f"yt-dlp profil client : {label_acces}/{label_client} ({clients_journal})")
            try:
                info_probe = _analyser_info(opts_client)
                selecteur_format, label_format, resume_formats = analyser_formats_youtube(info_probe, qualite)
                journal_debug(f"Analyse formats {label_acces}/{label_client} : {resume_formats}")
            except Exception as exc:
                message = str(exc) or repr(exc)
                journal_debug(f"Analyse formats impossible : client={label_acces}/{label_client} | {message[:500]}")
                erreurs_fallback.append(f"{label_acces}/{label_client}/analyse -> {message}")
                continue

            if not selecteur_format:
                journal_debug(f"Aucun sélecteur retenu : client={label_acces}/{label_client} | {label_format}")
                erreurs_fallback.append(f"{label_acces}/{label_client}/analyse -> {label_format}")
                continue

            opts_essai = dict(opts_client)
            opts_essai["format"] = selecteur_format
            if "+" in selecteur_format:
                opts_essai.setdefault("merge_output_format", "mp4")
            try:
                selecteurs_a_tenter = _selecteurs_telechargement(selecteur_format, qualite)
                erreurs_selecteurs: List[str] = []
                for index_selecteur, selecteur_tentative in enumerate(selecteurs_a_tenter, start=1):
                    try:
                        journal_debug(
                            "yt-dlp téléchargement : "
                            f"client={label_acces}/{label_client} | "
                            f"stratégie={index_selecteur}/{len(selecteurs_a_tenter)} | "
                            f"analyse={label_format} | selector={selecteur_tentative}"
                        )
                        info = _telecharger_cli(opts_essai, selecteur_tentative, info_probe)
                        journal_debug(
                            "yt-dlp téléchargement OK (CLI) : "
                            f"client={label_acces}/{label_client} | selector={selecteur_tentative}"
                        )
                        break
                    except Exception as exc_selecteur:
                        message_selecteur = str(exc_selecteur) or repr(exc_selecteur)
                        erreurs_selecteurs.append(f"{selecteur_tentative} -> {message_selecteur}")
                        journal_debug(
                            "yt-dlp sélecteur échoué : "
                            f"client={label_acces}/{label_client} | "
                            f"selector={selecteur_tentative} | {message_selecteur[:500]}"
                        )
                        if _erreur_reseau_cdn(message_selecteur):
                            journal_debug(
                                "Erreur réseau CDN détectée : passage au client YouTube suivant "
                                "sans retenter tous les formats sur le même host googlevideo."
                            )
                            break
                if info is None:
                    detail_selecteurs = " | ".join(erreurs_selecteurs[-3:]) or "aucun sélecteur essayé"
                    raise RuntimeError(detail_selecteurs)
            except Exception as exc:
                message = str(exc) or repr(exc)
                journal_debug(f"yt-dlp erreur : client={label_acces}/{label_client} | format={label_format} | {message[:500]}")
                erreurs_fallback.append(f"{label_acces}/{label_client}/{label_format} -> {message}")
                if "Sign in to confirm you’re not a bot" in message or "Sign in to confirm you're not a bot" in message:
                    if cookies_path and label_acces == "sans-cookies":
                        journal_debug("YouTube demande une authentification : essai avec cookies.")
                        break
                    return None, None, None, (
                        "YouTube bloque la requête comme anti-bot. Ajoute un cookies.txt "
                        "récent exporté depuis le même navigateur, puis relance."
                    )
                if "403" in message or "Forbidden" in message:
                    if cookies_path and label_acces == "sans-cookies":
                        journal_debug("HTTP 403 sans cookies : essai avec cookies.")
                        break
                    return None, None, None, "HTTP 403 détecté. La vidéo est restreinte. Fournis un cookies.txt puis relance."
            if info is not None:
                break
        if info is not None:
            break

    if info is None:
        for label_acces, opts_base_acces in bases_ytdlp:
            try:
                journal_debug(f"Tentative fallback API Python yt-dlp : {label_acces}")
                info_probe = _analyser_info(opts_base_acces)
                selecteur_format, label_format, resume_formats = analyser_formats_youtube(info_probe, qualite)
                journal_debug(f"Fallback API analyse : {resume_formats} | {label_format}")
                info = _telecharger_api_ytdlp(opts_base_acces, selecteur_format)
                if info is not None:
                    journal_debug("Fallback API Python yt-dlp OK")
                    break
            except Exception as exc:
                message = str(exc) or repr(exc)
                journal_debug(f"Fallback API Python yt-dlp échoué : {message[:500]}")
                erreurs_fallback.append(f"{label_acces}/api -> {message}")

    if info is None:
        diagnostic_opts = _sans_cookiefile(ydl_opts) if cookies_path else ydl_opts
        diagnostic_formats = diagnostiquer_formats_youtube(url, diagnostic_opts)
        if cookies_path:
            diagnostic_formats = "Diagnostic final sans cookies : " + diagnostic_formats
        journal_debug(diagnostic_formats)
        detail_erreur = " | ".join(erreurs_fallback[-4:]) if erreurs_fallback else "aucune erreur yt-dlp détaillée"
        return None, None, None, (
            "Echec du téléchargement YouTube : aucun format média exploitable n'a été obtenu. "
            f"{diagnostic_formats}. Dernières erreurs : {detail_erreur}"
        )
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    candidats = chemins_depuis_info_ytdlp(info)
    candidats.extend(fichiers_media_sortie(depuis_timestamp=debut_telechargement))
    if not candidats:
        candidats.extend(fichiers_media_sortie())
    candidats = fichiers_valides(candidats)
    journal_debug(f"Fichiers détectés après yt-dlp : {len(candidats)}")
    for candidat in candidats[:20]:
        journal_debug(f" - {candidat.name} ({candidat.stat().st_size} octets)")
    if not candidats:
        journal_debug("Aucun fichier média détecté après yt-dlp")
        return None, None, None, "Téléchargement terminé mais aucun fichier détecté."
    candidats.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    fichier_final = candidats[0]

    video_id = (info.get("id") if info else "vid") or "vid"
    titre_brut = (info.get("title") if info else fichier_final.stem) or "video"
    base_court = generer_nom_base(video_id, titre_brut)

    ext_src = fichier_final.suffix
    src_base = REPERTOIRE_SORTIE / f"{base_court}_src"
    chemin_source_propre = renommer_sans_collision(fichier_final, src_base, ext=ext_src)
    cible = REPERTOIRE_SORTIE / f"{base_court}_video.mp4"

    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as e:
        return None, None, None, f"ffmpeg introuvable : {e}"

    def _run_ffmpeg(args: List[str], description: str) -> None:
        executer_ffmpeg(args, description)

    try:
        if utiliser_intervalle:
            _run_ffmpeg([ffmpeg, "-y", "-ss", str(debut), "-to", str(fin), "-i", str(chemin_source_propre), "-c", "copy", "-movflags", "+faststart", str(cible)], "Découpe/remux YouTube")
        else:
            _run_ffmpeg([ffmpeg, "-y", "-i", str(chemin_source_propre), "-c", "copy", "-movflags", "+faststart", str(cible)], "Remux YouTube")
    except Exception:
        try:
            if qualite_compressee(qualite):
                filtre_video = ["-vf", "scale=1280:-2"]
                codec_video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]
                codec_audio = ["-c:a", "aac", "-b:a", "96k"]
            else:
                filtre_video = []
                codec_video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
                codec_audio = ["-c:a", "aac", "-b:a", "192k"]
            args = [ffmpeg, "-y"]
            if utiliser_intervalle:
                args += ["-ss", str(debut), "-to", str(fin)]
            args += ["-i", str(chemin_source_propre), *filtre_video, *codec_video, *codec_audio, "-movflags", "+faststart", str(cible)]
            _run_ffmpeg(args, "Transcodage YouTube")
        except Exception as e:
            return None, None, None, f"Echec du remux/transcodage : {e}"

    try:
        if chemin_source_propre.exists():
            chemin_source_propre.unlink()
    except Exception:
        pass

    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    return str(cible), base_court, info, None


def traiter_local(src_local: Path, base_court: str, qualite: str, utiliser_intervalle: bool, debut: int, fin: int) -> str:
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as e:
        raise RuntimeError(f"ffmpeg introuvable : {e}") from e

    cible = REPERTOIRE_SORTIE / f"{base_court}_video.mp4"

    def _run_ffmpeg(args: List[str], description: str) -> None:
        executer_ffmpeg(args, description)

    if qualite_compressee(qualite):
        args = [ffmpeg, "-y"]
        if utiliser_intervalle:
            args += ["-ss", str(debut), "-to", str(fin)]
        args += [
            "-i",
            str(src_local),
            "-vf",
            "scale=1280:-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(cible),
        ]
        _run_ffmpeg(args, "Transcodage du fichier local")
    else:
        try:
            args = [ffmpeg, "-y"]
            if utiliser_intervalle:
                args += ["-ss", str(debut), "-to", str(fin)]
            args += ["-i", str(src_local), "-c", "copy", "-movflags", "+faststart", str(cible)]
            _run_ffmpeg(args, "Remux du fichier local")
        except Exception:
            args = [ffmpeg, "-y"]
            if utiliser_intervalle:
                args += ["-ss", str(debut), "-to", str(fin)]
            args += [
                "-i",
                str(src_local),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(cible),
            ]
            _run_ffmpeg(args, "Transcodage du fichier local")
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    return str(cible)


def extraire_ressources(video_path: str, debut: int, fin: int, base_court: str, options: Dict[str, bool], utiliser_intervalle: bool):
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as e:
        return f"ffmpeg introuvable : {e}"

    def _run_ffmpeg(args: List[str], description: str) -> None:
        executer_ffmpeg(args, description)

    def cmd_segment(sortie: Path) -> List[str]:
        args = [ffmpeg, "-y"]
        if utiliser_intervalle:
            args += ["-ss", str(debut), "-to", str(fin)]
        args += [
            "-i",
            video_path,
            "-vf",
            "scale=1280:-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(sortie),
        ]
        return args

    def cmd_audio(sortie: Path, codec_args: List[str]) -> List[str]:
        args = [ffmpeg, "-y"]
        if utiliser_intervalle:
            args += ["-ss", str(debut), "-to", str(fin)]
        args += ["-i", video_path, *codec_args, str(sortie)]
        return args

    def cmd_images(output_pattern: str, fps: int) -> List[str]:
        args = [ffmpeg, "-y"]
        if utiliser_intervalle:
            args += ["-ss", str(debut), "-to", str(fin)]
        args += ["-i", video_path, "-vf", f"fps={fps},scale=1920:1080", "-q:v", "1", output_pattern]
        return args

    if options.get("mp4"):
        nom = f"{base_court}_seg.mp4" if utiliser_intervalle else f"{base_court}_full.mp4"
        _run_ffmpeg(cmd_segment(REPERTOIRE_SORTIE / nom), "Export MP4")
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    if options.get("mp3"):
        nom = f"{base_court}_seg.mp3" if utiliser_intervalle else f"{base_court}_full.mp3"
        _run_ffmpeg(cmd_audio(REPERTOIRE_SORTIE / nom, ["-vn", "-acodec", "libmp3lame", "-q:a", "5"]), "Export MP3")
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    if options.get("wav"):
        nom = f"{base_court}_seg.wav" if utiliser_intervalle else f"{base_court}_full.wav"
        _run_ffmpeg(cmd_audio(REPERTOIRE_SORTIE / nom, ["-vn", "-acodec", "adpcm_ima_wav"]), "Export WAV")
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    if options.get("img1") or options.get("img25"):
        for fps in (1, 25):
            if (fps == 1 and options.get("img1")) or (fps == 25 and options.get("img25")):
                dossier = f"img{fps}_{base_court}" if utiliser_intervalle else f"img{fps}_full_{base_court}"
                rep = REPERTOIRE_SORTIE / dossier
                rep.mkdir(parents=True, exist_ok=True)
                tmp_pattern = str(rep / "tmp_%06d.jpg")
                _run_ffmpeg(cmd_images(tmp_pattern, fps), f"Export images {fps} FPS")
                images_gen = sorted(rep.glob("tmp_*.jpg"))
                start_offset = debut if utiliser_intervalle else 0
                for index, src in enumerate(images_gen):
                    instant = start_offset + (index / float(fps))
                    sec = int(instant)
                    if fps == 1:
                        nom_cible = f"i_{sec}s_1fps.jpg"
                    else:
                        image_dans_seconde = int(round((instant - sec) * fps))
                        if image_dans_seconde >= fps:
                            image_dans_seconde = fps - 1
                        nom_cible = f"i_{sec}s_{fps}fps_{image_dans_seconde:02d}.jpg"
                    dst = rep / nom_cible
                    suffixe = 1
                    base_dst = dst.with_suffix("")
                    ext = dst.suffix
                    while dst.exists():
                        dst = Path(f"{base_dst}_{suffixe}{ext}")
                        suffixe += 1
                    os.replace(str(src), str(dst))
                keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    return None


def chemin_apercu_video(chemin_video: Path) -> Path:
    try:
        stat = chemin_video.stat()
        signature_base = f"{chemin_video.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        signature_base = str(chemin_video)
    signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()[:16]
    return REPERTOIRE_TEMP / f"preview_{signature}.mp4"


def creer_apercu_video(chemin_video: Path) -> Path:
    """Crée un MP4 web-compatible pour éviter les codecs non lisibles navigateur."""
    apercu = chemin_apercu_video(chemin_video)
    if apercu.is_file() and apercu.stat().st_size > 0:
        journal_debug(f"Aperçu vidéo réutilisé : {apercu.name} ({apercu.stat().st_size} octets)")
        return apercu

    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as exc:
        raise RuntimeError(f"ffmpeg introuvable pour l'aperçu : {exc}") from exc

    journal_debug(f"Création aperçu vidéo web-compatible : {chemin_video.name} -> {apercu.name}")
    executer_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-i",
            str(chemin_video),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale=min(1280\\,iw):-2,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(apercu),
        ],
        "Création aperçu vidéo",
    )
    if not apercu.is_file() or apercu.stat().st_size <= 0:
        raise RuntimeError("le fichier d'aperçu MP4 n'a pas été créé")
    return apercu


def afficher_video_bytes(chemin_video: Path) -> None:
    if not chemin_video.exists() or not chemin_video.is_file():
        st.info("Aperçu indisponible : fichier absent.")
        return
    taille = taille_fichier(chemin_video) or 0
    if taille <= 0:
        st.info("Aperçu indisponible : fichier vide.")
        return
    if taille > SEUIL_APERCU_OCTETS:
        st.info("Fichier volumineux : aperçu désactivé.")
        return
    try:
        apercu = creer_apercu_video(chemin_video)
        journal_debug(f"Affichage aperçu vidéo : {apercu.name} ({apercu.stat().st_size} octets)")
        with open(apercu, "rb") as fichier:
            st.video(fichier.read(), format="video/mp4", start_time=0)
    except Exception as e:
        journal_debug(f"Aperçu web-compatible impossible : {e}")
        try:
            with open(chemin_video, "rb") as fichier:
                st.video(fichier.read(), format="video/mp4", start_time=0)
        except Exception as e2:
            journal_debug(f"Aperçu vidéo impossible : {e2}")
            st.warning(f"Aperçu impossible : {e2}")


def extraire_id_youtube(url_video: str) -> Optional[str]:
    url_video = (url_video or "").strip()
    if not url_video:
        return None
    if not re.match(r"^https?://", url_video, flags=re.IGNORECASE):
        url_video = "https://" + url_video
    try:
        parsed = urlparse(url_video)
    except Exception:
        return None
    host = parsed.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            for prefix in ("/embed/", "/shorts/", "/live/"):
                if parsed.path.startswith(prefix):
                    video_id = parsed.path[len(prefix):].strip("/").split("/")[0]
                    break
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return video_id
    return None


def afficher_apercu_youtube_depuis_url(url_video: str) -> None:
    video_id = extraire_id_youtube(url_video)
    if not video_id:
        st.info("URL renseignée : l'aperçu intégré s'affichera si l'URL YouTube est reconnue.")
        return
    embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}"
    components.html(
        f"""
        <div style="width:100%; border-radius:16px; overflow:hidden; background:#111;">
          <iframe
            src="{embed_url}"
            title="Aperçu YouTube"
            style="width:100%; height:420px; border:0;"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerpolicy="strict-origin-when-cross-origin"
            allowfullscreen>
          </iframe>
        </div>
        """,
        height=430,
    )


def sauvegarder_upload_local(fichier_local) -> Optional[Path]:
    if fichier_local is None:
        return None

    signature_brute = f"{fichier_local.name}-{fichier_local.size}"
    signature = hashlib.sha1(signature_brute.encode("utf-8")).hexdigest()[:16]
    extension = Path(fichier_local.name).suffix.lower() or ".mp4"
    tmp = REPERTOIRE_TEMP / f"local_upload_{signature}{extension}"

    if signature != st.session_state.get("upload_signature") or not tmp.exists():
        with open(tmp, "wb") as sortie:
            sortie.write(fichier_local.getbuffer())
        st.session_state["upload_signature"] = signature
        st.session_state["local_temp_path"] = str(tmp)
        st.session_state["local_name_base"] = generer_nom_base("local", Path(fichier_local.name).stem)

    return tmp


st.title("Extraction multimedia (video, audio, images)")
st.markdown("**[www.codeandcortex.fr](http://www.codeandcortex.fr)**")
st.caption("modifié le 12-09-2026")
st.markdown(
    "Par défaut, l'extraction porte sur toute la vidéo. "
    "Vous pouvez activer un intervalle personnalisé si besoin. "
    "Si la vidéo est restreinte (403), exportez vos cookies avec l'extension Firefox "
    "[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)."
)
st.caption(
    "Si YouTube affiche un blocage anti-bot, il faut en pratique un cookies.txt récent, "
    "exporté depuis le navigateur qui vient d'ouvrir la vidéo, avec un User-Agent cohérent."
)
render_help_tab()

st.session_state.setdefault("debut_secs", 0)
st.session_state.setdefault("fin_secs", 10)
st.session_state.setdefault("video_base", None)
st.session_state.setdefault("base_court", None)
st.session_state.setdefault("upload_signature", None)
st.session_state.setdefault("local_temp_path", None)
st.session_state.setdefault("local_name_base", None)
st.session_state.setdefault("dernier_zip_path", None)
st.session_state.setdefault("dernier_zip_stable_path", None)
st.session_state.setdefault("derniers_fichiers", [])
st.session_state.setdefault("dernier_message_resultats", "")
st.session_state.setdefault("derniere_erreur_resultats", "")
st.session_state.setdefault("resultats_revision", 0)

st.subheader("Source")
url = st.text_input("URL YouTube")
if url.strip():
    with st.container(border=True):
        st.subheader("Aperçu YouTube")
        afficher_apercu_youtube_depuis_url(url)
cookies_path_eff = ck.afficher_section_cookies(REPERTOIRE_SORTIE)
user_agent_youtube = st.text_input(
    "User-Agent navigateur (optionnel)",
    value=os.environ.get("YTDLP_BROWSER_USER_AGENT", USER_AGENT_YOUTUBE_DEFAUT),
    help=(
        "Chrome et Firefox fonctionnent. Si YouTube bloque la vidéo et que tu fournis un cookies.txt, "
        "colle idéalement le User-Agent du même navigateur que celui utilisé pour exporter les cookies. "
        "Sinon, laisse la valeur par défaut."
    ),
)
st.caption(
    "Le User-Agent indique à YouTube quel navigateur est utilisé. "
    "Chrome et Firefox sont compatibles ; il sert surtout à rester cohérent avec le cookies.txt en cas de blocage anti-bot."
)
fichier_local = st.file_uploader(
    "Ou importer un fichier vidéo",
    type=UPLOAD_VIDEO_EXTENSIONS,
    help="ffmpeg accepte de nombreux conteneurs : mp4, mov, mkv, webm, avi, m4v, flv, wmv, mpg, ts, etc.",
)

mode_diagnostic = st.checkbox(
    "Mode diagnostic",
    value=False,
    help="Affiche les logs détaillés et active les messages yt-dlp complets.",
)
mode_verbose = mode_diagnostic
debug_affiche = mode_diagnostic
qualite = st.radio("Qualité de la vidéo de base", ["Compressée (1280p, CRF 28)", "HD (max qualité dispo)"], index=0)

st.subheader("Ressources à produire")
st.markdown("<style>div[data-testid='stHorizontalBlock'] label { white-space: nowrap; }</style>", unsafe_allow_html=True)

opt_timelapse = st.checkbox("Timelapse", key="opt_timelapse")
if opt_timelapse:
    st.warning("Timelapse sélectionné : seul le timelapse sera exporté. Les autres options sont désactivées.")
    fps_timelapse = st.selectbox("FPS timelapse", [4, 6, 8, 10, 12, 14, 16], index=2, key="fps_timelapse")
else:
    fps_timelapse = 12

col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
with col1:
    opt_mp4 = st.checkbox("MP4", key="opt_mp4", disabled=opt_timelapse)
with col2:
    opt_mp3 = st.checkbox("MP3", key="opt_mp3", disabled=opt_timelapse)
with col3:
    opt_wav = st.checkbox("WAV", key="opt_wav", disabled=opt_timelapse)
with col4:
    opt_img1 = st.checkbox("Img 1 FPS", key="opt_img1", disabled=opt_timelapse)
with col5:
    opt_img25 = st.checkbox("Img 25 FPS", key="opt_img25", disabled=opt_timelapse)

st.subheader("Étendue")
etendue = st.radio("Choisir l'étendue", ["Toute la vidéo", "Intervalle personnalisé"], index=0)
if etendue == "Intervalle personnalisé":
    st.info(
        f"Intervalle personnalisé activé : de {st.session_state['debut_secs']}s "
        f"à {st.session_state['fin_secs']}s. Le téléchargement traitera uniquement cet intervalle."
    )
    cc1, cc2 = st.columns(2)
    st.session_state["debut_secs"] = cc1.number_input("Début (s)", min_value=0, value=st.session_state["debut_secs"])
    st.session_state["fin_secs"] = cc2.number_input("Fin (s)", min_value=1, value=st.session_state["fin_secs"])
    utiliser_intervalle = True
    if st.session_state["fin_secs"] <= st.session_state["debut_secs"]:
        st.warning("La fin doit être strictement supérieure au début.")
else:
    utiliser_intervalle = False

afficher_apercu = st.checkbox("Afficher l'aperçu vidéo", value=True, disabled=opt_timelapse)
preview_slot = st.empty()
with preview_slot.container(border=True):
    st.subheader("Aperçu vidéo")
if afficher_apercu and not opt_timelapse:
    if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
        with preview_slot.container(border=True):
            st.subheader("Aperçu vidéo")
            afficher_video_bytes(Path(st.session_state["video_base"]))
    elif fichier_local is not None:
        tmp = sauvegarder_upload_local(fichier_local)
        if tmp is not None:
            with preview_slot.container(border=True):
                st.subheader("Aperçu vidéo")
                afficher_video_bytes(tmp)
    else:
        with preview_slot.container(border=True):
            st.subheader("Aperçu vidéo")
            st.info("L'aperçu s'affichera ici après préparation de la vidéo.")
elif opt_timelapse:
    with preview_slot.container(border=True):
        st.subheader("Aperçu vidéo")
        st.info("Aperçu désactivé pendant le mode timelapse.")
else:
    with preview_slot.container(border=True):
        st.subheader("Aperçu vidéo")
        st.info("Aperçu vidéo désactivé.")

if st.button("Lancer le traitement"):
    with st.spinner("Traitement en cours..."):
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
        reinitialiser_debug()
        journal_debug("Clic sur Lancer le traitement")
        journal_debug("Build application : " + APP_BUILD)
        st.session_state["dernier_zip_path"] = None
        st.session_state["dernier_zip_stable_path"] = None
        st.session_state["derniers_fichiers"] = []
        st.session_state["dernier_message_resultats"] = ""
        st.session_state["derniere_erreur_resultats"] = ""
        st.session_state["video_base"] = None
        st.session_state["base_court"] = None
        nettoyer_derniere_archive_stable()
        nettoyer_resultats_session()
        if not ffmpeg_disponible():
            st.error("ffmpeg introuvable et fallback impossible. Verifie l'image Docker et les dependances systeme.")
            enregistrer_erreur_resultats("ffmpeg est introuvable : aucune extraction ne peut être lancée.")
            journal_debug("Arrêt : ffmpeg indisponible")
        else:
            if url:
                journal_debug("Source choisie : URL YouTube")
                video_base, base_court, info, erreur = telecharger_preparer_video(
                    url,
                    cookies_path_eff,
                    user_agent_youtube,
                    mode_verbose,
                    qualite,
                    utiliser_intervalle,
                    st.session_state["debut_secs"],
                    st.session_state["fin_secs"],
                )
                if erreur:
                    st.error(f"Erreur : {erreur}")
                    enregistrer_erreur_resultats(erreur)
                    journal_debug(f"Préparation YouTube échouée : {erreur}")
                    video_base = None
                else:
                    st.session_state["video_base"] = video_base
                    st.session_state["base_court"] = base_court
                    journal_debug(f"Vidéo préparée : {video_base}")
                    st.success(f"Vidéo prête : {Path(video_base).name}")
                    if afficher_apercu and not opt_timelapse:
                        with preview_slot.container(border=True):
                            st.subheader("Aperçu vidéo")
                            afficher_video_bytes(Path(video_base))
            elif fichier_local is not None or st.session_state.get("local_temp_path"):
                journal_debug("Source choisie : fichier local")
                base_court = st.session_state.get("local_name_base") or generer_nom_base("local", "video")
                try:
                    local_path = sauvegarder_upload_local(fichier_local) if fichier_local is not None else None
                    source_locale = local_path or (
                        Path(st.session_state["local_temp_path"]) if st.session_state.get("local_temp_path") else None
                    )
                    if source_locale is None:
                        raise RuntimeError("Fichier local introuvable dans la session.")
                    cible = traiter_local(
                        source_locale,
                        base_court,
                        qualite,
                        utiliser_intervalle,
                        st.session_state["debut_secs"],
                        st.session_state["fin_secs"],
                    )
                    st.session_state["video_base"] = cible
                    st.session_state["base_court"] = base_court
                    journal_debug(f"Vidéo locale préparée : {cible}")
                    st.success(f"Vidéo prête : {Path(cible).name}")
                    if afficher_apercu and not opt_timelapse:
                        with preview_slot.container(border=True):
                            st.subheader("Aperçu vidéo")
                            afficher_video_bytes(Path(cible))
                except Exception as e:
                    st.error(f"Echec du traitement local : {e}")
                    enregistrer_erreur_resultats(f"Echec du traitement local : {e}")
                    journal_debug(f"Préparation locale échouée : {e}")
            else:
                st.warning("Veuillez fournir une URL YouTube ou un fichier local.")
                enregistrer_erreur_resultats("Aucune source fournie : URL YouTube ou fichier local requis.")
                journal_debug("Arrêt : aucune source fournie")

            if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
                base_court = st.session_state["base_court"]
                video_path = st.session_state["video_base"]
                journal_debug(f"Début extraction depuis : {video_path}")

                if opt_timelapse:
                    try:
                        intervalle = (st.session_state["debut_secs"], st.session_state["fin_secs"]) if utiliser_intervalle else None
                        job_id = hash_job(f"file:{video_path}", fps_timelapse, intervalle)
                        out_path, nb_images = tl.executer_timelapse(
                            video_path,
                            job_id,
                            base_court,
                            fps_timelapse,
                            debut=st.session_state["debut_secs"] if utiliser_intervalle else None,
                            fin=st.session_state["fin_secs"] if utiliser_intervalle else None,
                            job_root=SESSION_DIR / "timelapse_jobs",
                        )
                        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
                        st.success(f"Timelapse genere ({nb_images} images).")
                        zip_path = REPERTOIRE_SORTIE / f"resultats_{base_court}_timelapse.zip"
                        fichiers_timelapse = fichiers_valides([Path(out_path)])
                        if not fichiers_timelapse:
                            message_erreur = "Timelapse terminé, mais aucun fichier vidéo exploitable n'a été retrouvé."
                            st.error(message_erreur)
                            enregistrer_erreur_resultats(message_erreur)
                            st.code(diagnostic_contenu_sortie())
                        else:
                            zipper_sur_disque(fichiers_timelapse, zip_path)
                            taille_zip = taille_fichier(zip_path) or 0
                            if taille_zip <= 0:
                                message_erreur = f"Archive timelapse générée mais vide : {zip_path.name}"
                                st.error(message_erreur)
                                enregistrer_erreur_resultats(message_erreur)
                            else:
                                message_ok = f"Archive prête : {zip_path.name} ({taille_zip / (1024 * 1024):.1f} Mo)."
                                st.success(message_ok)
                                enregistrer_resultats_generes(zip_path, fichiers_timelapse, message_ok)
                    except Exception as e:
                        message_erreur = f"Echec du timelapse : {e}"
                        st.error(message_erreur)
                        enregistrer_erreur_resultats(message_erreur)
                else:
                    if utiliser_intervalle:
                        debut_eff = st.session_state["debut_secs"]
                        fin_eff = st.session_state["fin_secs"]
                    else:
                        duree = duree_video_seconds(Path(video_path)) or 0
                        debut_eff, fin_eff = 0, duree

                    options = {
                        "mp4": opt_mp4,
                        "mp3": opt_mp3,
                        "wav": opt_wav,
                        "img1": opt_img1,
                        "img25": opt_img25,
                    }

                    if any(options.values()):
                        st.info("Extraction des ressources sélectionnées en cours...")
                        journal_debug(f"Options extraction : {options}")
                        try:
                            erreur_extraction = extraire_ressources(video_path, debut_eff, fin_eff, base_court, options, utiliser_intervalle)
                        except Exception as exc:
                            erreur_extraction = str(exc) or repr(exc)
                        if erreur_extraction:
                            message_erreur = f"Erreur pendant l'extraction : {erreur_extraction}"
                            st.error(message_erreur)
                            enregistrer_erreur_resultats(message_erreur)
                            journal_debug(message_erreur)
                        else:
                            st.success("Ressources generees.")
                            journal_debug("Extraction des ressources terminée sans erreur")
                            keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
                    else:
                        st.info("Aucune ressource supplémentaire sélectionnée : seul le fichier vidéo de base sera mis dans l'archive.")
                        journal_debug("Aucune option d'extraction cochée : archivage vidéo de base seulement")

                    fichiers = fichiers_exportables_session()
                    video_base_path = Path(video_path)
                    if video_base_path.is_file() and video_base_path not in fichiers:
                        fichiers.append(video_base_path)
                    fichiers = fichiers_valides(fichiers)
                    journal_debug(f"Fichiers exportables avant ZIP : {len(fichiers)}")
                    for fichier in fichiers[:30]:
                        journal_debug(f" - exportable : {fichier.relative_to(REPERTOIRE_SORTIE) if fichier.is_relative_to(REPERTOIRE_SORTIE) else fichier.name} ({fichier.stat().st_size} octets)")
                    if not fichiers:
                        message_erreur = (
                            "Aucun fichier exploitable n'a été généré. "
                            "Le diagnostic du dossier de sortie est affiché ci-dessous."
                        )
                        st.error(message_erreur)
                        enregistrer_erreur_resultats(message_erreur)
                        st.code(diagnostic_contenu_sortie())
                        afficher_debug_extraction(expanded=True)
                        st.stop()
                    st.info(f"Préparation de l'archive ZIP : {len(fichiers)} fichier(s).")
                    zip_path = REPERTOIRE_SORTIE / f"resultats_{base_court}.zip"
                    zipper_sur_disque(fichiers, zip_path)
                    taille_zip = taille_fichier(zip_path) or 0
                    if taille_zip <= 0:
                        message_erreur = f"Archive générée mais vide : {zip_path.name}"
                        st.error(message_erreur)
                        enregistrer_erreur_resultats(message_erreur)
                        st.code(diagnostic_contenu_sortie())
                    else:
                        message_ok = f"Archive prête : {zip_path.name} ({taille_zip / (1024 * 1024):.1f} Mo)."
                        st.success(message_ok)
                        enregistrer_resultats_generes(zip_path, fichiers, message_ok)
            else:
                message_erreur = "Aucune vidéo source prête : l'extraction n'a pas démarré."
                st.error(message_erreur)
                enregistrer_erreur_resultats(message_erreur)
                journal_debug(message_erreur)
                st.code(diagnostic_contenu_sortie())

afficher_debug_extraction(expanded=debug_affiche or bool(st.session_state.get("derniere_erreur_resultats")))
afficher_resultats_generes()
