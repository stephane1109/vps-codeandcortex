import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import glob
import hashlib
import importlib.util
import re
import shutil
import subprocess
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import streamlit as st
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
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
APP_NAME = "Extraction multimedia"
APP_TICKET_DEFAULT_ID = "extraction-multimedia"
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
FORMATS_YOUTUBE_FALLBACK: List[Optional[str]] = [
    # None = laisser yt-dlp choisir lui-même son meilleur format compatible.
    None,
    # Formats YouTube progressifs très fréquents. Le format 18 est souvent le
    # dernier format MP4 audio+vidéo encore disponible sur les vidéos contraintes.
    "18",
    "22",
    "best[height<=1080][acodec!=none][vcodec!=none]/best[height<=720][acodec!=none][vcodec!=none]/best[height<=480][acodec!=none][vcodec!=none]/best[height<=360][acodec!=none][vcodec!=none]",
    "best[height<=720][ext=mp4]/best[height<=480][ext=mp4]/best[height<=360][ext=mp4]/best[ext=mp4]/best",
    "bestvideo*+bestaudio/best",
    "bv*+ba/b",
    "bestvideo+bestaudio/best",
    "best[ext=mp4]/best",
    "best[protocol^=http]/best",
    "best[acodec!=none][vcodec!=none]/best[acodec!=none]/best",
    "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b",
    "worstvideo*+worstaudio/worst",
    "worst[acodec!=none][vcodec!=none]/worst",
    "bestaudio/best",
]
YOUTUBE_CLIENT_FALLBACKS: List[tuple[str, Optional[List[str]]]] = [
    # `auto` laisse yt-dlp choisir ses clients. C'est le profil le plus robuste
    # face aux changements YouTube, PO Token et SABR.
    ("auto", None),
    ("android_vr", ["android_vr"]),
    ("web", ["web"]),
    ("mweb", ["mweb"]),
    ("android", ["android"]),
    ("legacy_forced", ["android", "ios", "mweb", "web"]),
]
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


FFMPEG_TIMEOUT_SECONDS = max(60, _env_int("APP_FFMPEG_TIMEOUT_SECONDS", 3600))


def load_help_markdown() -> str:
    try:
        return HELP_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Le fichier `aide.md` est introuvable pour cette application."


def render_help_tab() -> None:
    with st.expander("Aide - cookies YouTube et formats", expanded=False):
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
        if LATEST_ZIP_PATH.is_file() and LATEST_ZIP_PATH.stat().st_size > 0:
            return LATEST_ZIP_PATH
    except Exception:
        return None
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

    try:
        subprocess.run(
            commande,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{description} a dépassé le délai maximal ffmpeg ({FFMPEG_TIMEOUT_SECONDS}s). "
            "Réduis l'intervalle ou les options d'images."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        if len(details) > 1200:
            details = details[-1200:]
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
    return chemin_zip


def nettoyer_resultats_session() -> None:
    """Nettoie les anciens médias sans supprimer le cookies.txt de la session."""
    REPERTOIRE_SORTIE.mkdir(parents=True, exist_ok=True)
    for element in REPERTOIRE_SORTIE.iterdir():
        if element.name.lower() == "cookies.txt":
            continue
        try:
            if element.is_dir():
                shutil.rmtree(element, ignore_errors=True)
            elif element.is_file():
                element.unlink()
        except Exception:
            continue


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
            if not fichier.is_file():
                continue
            if fichier.suffix.lower() == ".zip":
                continue
            if fichier.name.lower() == "cookies.txt":
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


def afficher_bouton_telechargement_resultats(key_prefix: str, titre: bool = False) -> None:
    if titre:
        st.subheader("Télécharger les résultats")

    zip_path, message = obtenir_zip_telechargeable()
    if zip_path is not None:
        taille_zip = zip_path.stat().st_size / (1024 * 1024)
        st.download_button(
            "Télécharger les résultats (.zip)",
            data=zip_path.read_bytes(),
            file_name=zip_path.name,
            mime="application/zip",
            key=f"{key_prefix}_download_zip_{zip_path.name}_{int(zip_path.stat().st_mtime)}",
            use_container_width=True,
        )
        st.caption(f"{message} · {taille_zip:.1f} Mo")
        with st.expander("Où sont les résultats ?", expanded=False):
            st.write(f"Dossier de session : `{SESSION_DIR}`")
            st.write(f"Dossier des fichiers : `{REPERTOIRE_SORTIE}`")
            st.write(f"Archive ZIP : `{zip_path}`")
            if LATEST_ZIP_PATH.is_file():
                st.write(f"Copie stable : `{LATEST_ZIP_PATH}`")
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
        taille_zip = zip_path.stat().st_size / (1024 * 1024)
        st.success(message_zip)
        st.download_button(
            "Télécharger les résultats (.zip)",
            data=zip_path.read_bytes(),
            file_name=zip_path.name,
            mime="application/zip",
            key=f"download_zip_{zip_path.name}_{int(zip_path.stat().st_mtime)}",
            use_container_width=True,
        )
        st.caption(f"Archive : {zip_path.name} · {taille_zip:.1f} Mo")
        with st.expander("Emplacement des résultats sur le serveur", expanded=False):
            st.write(f"Dossier de session : `{SESSION_DIR}`")
            st.write(f"Dossier des fichiers : `{REPERTOIRE_SORTIE}`")
            st.write(f"Archive ZIP : `{zip_path}`")
            if LATEST_ZIP_PATH.is_file():
                st.write(f"Copie stable : `{LATEST_ZIP_PATH}`")
    elif fichiers:
        st.warning(message_zip)

    if fichiers:
        with st.expander(f"Voir les fichiers inclus ({len(fichiers)})", expanded=False):
            for fichier in fichiers[:200]:
                try:
                    rel = fichier.relative_to(REPERTOIRE_SORTIE)
                except ValueError:
                    rel = fichier.name
                taille = (taille_fichier(fichier) or 0) / (1024 * 1024)
                st.write(f"- `{rel}` · {taille:.2f} Mo")
    else:
        st.info("Aucun fichier exploitable n'est actuellement mémorisé pour cette session.")
        with st.expander("Diagnostic du dossier de sortie", expanded=True):
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

    class SilentLogger:
        def debug(self, msg):  # noqa: ANN001
            pass

        def warning(self, msg):  # noqa: ANN001
            pass

        def error(self, msg):  # noqa: ANN001
            pass

    return SilentLogger()


def _opts_communs(verbose: bool, cookies_path: Optional[Path], user_agent: str) -> Dict[str, Any]:
    user_agent_final = (user_agent or "").strip() or USER_AGENT_YOUTUBE_DEFAUT
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
        "merge_output_format": "mp4",
    }
    clients_env = [
        client.strip()
        for client in os.environ.get("YTDLP_PLAYER_CLIENTS", "").split(",")
        if client.strip()
    ]
    if clients_env:
        opts["extractor_args"] = {"youtube": {"player_client": clients_env}}
    logger = _logger_silencieux(verbose)
    if logger is not None:
        opts["logger"] = logger
    if cookies_path:
        opts["cookiefile"] = str(cookies_path)
    return opts


def _opts_avec_clients_youtube(opts_base: Dict[str, Any], clients: Optional[List[str]]) -> Dict[str, Any]:
    opts = dict(opts_base)
    extractor_args = dict(opts.get("extractor_args") or {})
    if clients:
        extractor_args["youtube"] = {"player_client": clients}
        opts["extractor_args"] = extractor_args
    else:
        extractor_args.pop("youtube", None)
        if extractor_args:
            opts["extractor_args"] = extractor_args
        else:
            opts.pop("extractor_args", None)
    return opts


def _format_score(format_info: Dict[str, Any], prefer_audio: bool = False) -> float:
    height = float(format_info.get("height") or 0)
    width = float(format_info.get("width") or 0)
    tbr = float(format_info.get("tbr") or 0)
    abr = float(format_info.get("abr") or 0)
    filesize = float(format_info.get("filesize") or format_info.get("filesize_approx") or 0)
    if prefer_audio:
        return (abr * 1000) + tbr + (filesize / 1000000000)
    return (height * 1000000) + (width * 1000) + tbr + (filesize / 1000000000)


def _format_id(format_info: Dict[str, Any]) -> Optional[str]:
    value = format_info.get("format_id")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _format_est_exploitable(format_info: Dict[str, Any]) -> bool:
    format_id = _format_id(format_info)
    if not format_id:
        return False
    ext = str(format_info.get("ext") or "").lower()
    protocol = str(format_info.get("protocol") or "").lower()
    vcodec = str(format_info.get("vcodec") or "none").lower()
    acodec = str(format_info.get("acodec") or "none").lower()
    if ext in {"mhtml", "html", "json"}:
        return False
    if "storyboard" in format_id.lower() or "mhtml" in protocol:
        return False
    return vcodec != "none" or acodec != "none"


def _formats_disponibles_youtube(url: str, opts_base: Dict[str, Any]) -> List[str]:
    probe_opts = dict(opts_base)
    probe_opts.pop("format", None)
    probe_opts.pop("download_sections", None)
    probe_opts.pop("force_keyframes_at_cuts", None)
    probe_opts.pop("merge_output_format", None)
    probe_opts.pop("check_formats", None)
    probe_opts["ignore_no_formats_error"] = True
    probe_opts["simulate"] = True
    probe_opts["skip_download"] = True
    with YoutubeDL(probe_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return []

    formats = info.get("formats") or []
    video_only: List[Dict[str, Any]] = []
    audio_only: List[Dict[str, Any]] = []
    combined: List[Dict[str, Any]] = []

    for format_info in formats:
        if not _format_est_exploitable(format_info):
            continue
        format_id = _format_id(format_info)
        if not format_id:
            continue
        vcodec = str(format_info.get("vcodec") or "none")
        acodec = str(format_info.get("acodec") or "none")
        if vcodec != "none" and acodec != "none":
            combined.append(format_info)
        elif vcodec != "none":
            video_only.append(format_info)
        elif acodec != "none":
            audio_only.append(format_info)

    video_only.sort(key=_format_score, reverse=True)
    audio_only.sort(key=lambda item: _format_score(item, prefer_audio=True), reverse=True)
    combined.sort(key=_format_score, reverse=True)

    candidates: List[str] = []
    for video_format in video_only:
        video_id = _format_id(video_format)
        for audio_format in audio_only:
            audio_id = _format_id(audio_format)
            if video_id and audio_id:
                candidates.append(f"{video_id}+{audio_id}")
    for format_info in combined:
        format_id = _format_id(format_info)
        if format_id:
            candidates.append(format_id)
    for format_info in audio_only:
        format_id = _format_id(format_info)
        if format_id:
            candidates.append(format_id)
    for format_info in video_only:
        format_id = _format_id(format_info)
        if format_id:
            candidates.append(format_id)

    deduped: List[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _strategies_youtube(url: str, opts_base: Dict[str, Any]) -> List[tuple[str, Optional[str], Dict[str, Any]]]:
    strategies: List[tuple[str, Optional[str], Dict[str, Any]]] = []
    deja_vus = set()

    for label_client, clients in YOUTUBE_CLIENT_FALLBACKS:
        opts_client = _opts_avec_clients_youtube(opts_base, clients)
        formats_reels: List[Optional[str]] = []
        try:
            formats_reels.extend(_formats_disponibles_youtube(url, opts_client))
        except Exception:
            pass
        formats_reels.extend(FORMATS_YOUTUBE_FALLBACK)

        for fmt in formats_reels:
            cle = (label_client, "__default__" if fmt is None else str(fmt))
            if cle in deja_vus:
                continue
            deja_vus.add(cle)
            opts = dict(opts_client)
            if fmt is None:
                opts.pop("format", None)
            else:
                opts["format"] = fmt
            # Le remux MP4 est fait ensuite par ffmpeg. On ne bloque donc pas
            # yt-dlp sur un conteneur précis pendant les tentatives de secours.
            opts.pop("merge_output_format", None)
            strategies.append((label_client, fmt, opts))
    return strategies


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

    ydl_opts = _opts_communs(verbose, cookies_path, user_agent)
    if utiliser_intervalle:
        ydl_opts["download_sections"] = [{"section": f"*{debut}-{fin}"}]
        ydl_opts["force_keyframes_at_cuts"] = True

    def _telecharger(opts: Dict[str, Any]):
        with YoutubeDL(opts) as ydl:
            info_local = ydl.extract_info(url, download=True)
            _ = ydl.prepare_filename(info_local)
        return info_local

    try:
        info = _telecharger(ydl_opts)
    except Exception as e:
        message = str(e) or repr(e)
        if "Sign in to confirm you’re not a bot" in message or "Sign in to confirm you're not a bot" in message:
            if not cookies_path:
                return None, None, None, (
                    "YouTube bloque la requête comme anti-bot. "
                    "Ajoute un cookies.txt recent exporte depuis le meme navigateur "
                    "et idealement la meme IP publique, puis relance."
                )
            return None, None, None, (
                "YouTube refuse encore la requête malgré le cookies.txt. "
                "Cause probable : cookies trop anciens, export incomplet, compte non reconnecte "
                "recemment, ou User-Agent non coherent avec le navigateur d'origine. "
                "Recharge YouTube dans ton navigateur, re-exporte le cookies.txt, puis colle "
                "le User-Agent exact du navigateur dans le champ dedie."
            )
        if "403" in message or "Forbidden" in message:
            if not cookies_path:
                return None, None, None, "HTTP 403 detecte. La video est restreinte. Fournis un cookies.txt puis relance."
            return None, None, None, "HTTP 403 persistant malgre les cookies. Verifie le cookies.txt."
        if "Requested format is not available" in message or "format not available" in message.lower():
            erreurs_fallback: List[str] = []
            info = None
            tentatives: List[str] = []
            for label_client, fmt, ydl_opts_fallback in _strategies_youtube(url, ydl_opts):
                tentatives.append(f"{label_client}:{fmt or 'auto'}")
                try:
                    info = _telecharger(ydl_opts_fallback)
                    break
                except Exception as e2:
                    erreurs_fallback.append(f"{tentatives[-1]} -> {str(e2) or repr(e2)}")
            if info is None:
                return None, None, None, (
                    "Aucun format YouTube exploitable n'a pu être téléchargé par yt-dlp. "
                    f"{len(tentatives)} stratégies ont été tentées sur plusieurs profils YouTube. "
                    "Si la vidéo se lit dans le navigateur, réexporte un cookies.txt récent "
                    "puis relance. Dernière stratégie : "
                    + (tentatives[-1] if tentatives else "aucune")
                    + ". Dernière erreur : "
                    + (erreurs_fallback[-1] if erreurs_fallback else message)
                )
        else:
            return None, None, None, message
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    candidats: List[Path] = []
    for ext in ["mp4", "mkv", "webm", "m4a", "mp3"]:
        candidats.extend(REPERTOIRE_SORTIE.glob(f"*.{ext}"))
    if not candidats:
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
        with open(chemin_video, "rb") as fichier:
            st.video(fichier.read(), format="video/mp4", start_time=0)
    except Exception as e:
        st.warning(f"Aperçu impossible : {e}")


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

with st.expander("Diagnostic systeme"):
    try:
        chemin_ffmpeg = tl.chemin_ffmpeg()
        version = subprocess.run([chemin_ffmpeg, "-version"], capture_output=True, text=True, check=False)
        st.write(f"ffmpeg : {chemin_ffmpeg}")
        if version.stdout:
            st.code(version.stdout.splitlines()[0])
    except Exception as e:
        st.write(f"ffmpeg : introuvable ({e})")
    st.write(f"Session : {SESSION_ID[:8]}")
    st.write(f"Workspace temporaire : {SESSION_DIR}")
    try:
        st.write(ck.info_cookies(REPERTOIRE_SORTIE))
    except Exception:
        pass

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

with st.container(border=True):
    afficher_bouton_telechargement_resultats(f"top_results_{st.session_state['resultats_revision']}", titre=True)

st.subheader("Source")
url = st.text_input("URL YouTube")
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

mode_verbose = st.checkbox("Mode diagnostic yt-dlp", value=False)
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
if afficher_apercu and not opt_timelapse:
    if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
        afficher_video_bytes(Path(st.session_state["video_base"]))
    elif fichier_local is not None:
        tmp = sauvegarder_upload_local(fichier_local)
        if tmp is not None:
            afficher_video_bytes(tmp)

if st.button("Lancer le traitement"):
    with st.spinner("Traitement en cours..."):
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
        st.session_state["dernier_zip_path"] = None
        st.session_state["dernier_zip_stable_path"] = None
        st.session_state["derniers_fichiers"] = []
        st.session_state["dernier_message_resultats"] = ""
        st.session_state["derniere_erreur_resultats"] = ""
        nettoyer_derniere_archive_stable()
        nettoyer_resultats_session()
        if not ffmpeg_disponible():
            st.error("ffmpeg introuvable et fallback impossible. Verifie l'image Docker et les dependances systeme.")
            enregistrer_erreur_resultats("ffmpeg est introuvable : aucune extraction ne peut être lancée.")
        else:
            if url:
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
                    video_base = None
                else:
                    st.session_state["video_base"] = video_base
                    st.session_state["base_court"] = base_court
                    st.success(f"Vidéo prête : {Path(video_base).name}")
                    if afficher_apercu and not opt_timelapse:
                        afficher_video_bytes(Path(video_base))
            elif fichier_local is not None or st.session_state.get("local_temp_path"):
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
                    st.success(f"Vidéo prête : {Path(cible).name}")
                    if afficher_apercu and not opt_timelapse:
                        afficher_video_bytes(Path(cible))
                except Exception as e:
                    st.error(f"Echec du traitement local : {e}")
            else:
                st.warning("Veuillez fournir une URL YouTube ou un fichier local.")

            if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
                base_court = st.session_state["base_court"]
                video_path = st.session_state["video_base"]

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
                        try:
                            erreur_extraction = extraire_ressources(video_path, debut_eff, fin_eff, base_court, options, utiliser_intervalle)
                        except Exception as exc:
                            erreur_extraction = str(exc) or repr(exc)
                        if erreur_extraction:
                            message_erreur = f"Erreur pendant l'extraction : {erreur_extraction}"
                            st.error(message_erreur)
                            enregistrer_erreur_resultats(message_erreur)
                        else:
                            st.success("Ressources generees.")
                            keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
                    else:
                        st.info("Aucune ressource supplémentaire sélectionnée : seul le fichier vidéo de base sera mis dans l'archive.")

                    fichiers = fichiers_exportables_session()
                    video_base_path = Path(video_path)
                    if video_base_path.is_file() and video_base_path not in fichiers:
                        fichiers.append(video_base_path)
                    fichiers = fichiers_valides(fichiers)
                    if not fichiers:
                        message_erreur = (
                            "Aucun fichier exploitable n'a été généré. "
                            "Le diagnostic du dossier de sortie est affiché ci-dessous."
                        )
                        st.error(message_erreur)
                        enregistrer_erreur_resultats(message_erreur)
                        st.code(diagnostic_contenu_sortie())
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

afficher_resultats_generes()
