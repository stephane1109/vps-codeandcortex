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


APP_DIR = Path(__file__).resolve().parent
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
SESSIONS_DIR = APP_DATA_DIR / "sessions"
SESSION_ID = st.session_state.setdefault("session_id", uuid.uuid4().hex)
SESSION_DIR = SESSIONS_DIR / SESSION_ID
REPERTOIRE_SORTIE = SESSION_DIR / "fichiers"
REPERTOIRE_TEMP = SESSION_DIR / "tmp"

SEUIL_APERCU_OCTETS = 160 * 1024 * 1024
LONGUEUR_TITRE_MAX = 24
LONGUEUR_PREFIX_ID = 8
USER_AGENT_YOUTUBE_DEFAUT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


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


def initialiser_repertoires_session() -> None:
    for repertoire in (SESSIONS_DIR, SESSION_DIR, REPERTOIRE_SORTIE, REPERTOIRE_TEMP):
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


initialiser_repertoires_session()
nettoyer_sessions_expirees()


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


def zipper_sur_disque(fichiers: List[Path], chemin_zip: Path) -> Path:
    with zipfile.ZipFile(str(chemin_zip), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for fichier in fichiers:
            if fichier.is_file():
                archive.write(str(fichier), arcname=fichier.name)
    return chemin_zip


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
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "mweb", "web"]}},
        "format": "bestvideo*+bestaudio/best",
    }
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
    st.write("Telechargement / preparation de la video en cours...")

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
                    "YouTube bloque la requete comme anti-bot. "
                    "Ajoute un cookies.txt recent exporte depuis le meme navigateur "
                    "et idealement la meme IP publique, puis relance."
                )
            return None, None, None, (
                "YouTube refuse encore la requete malgre le cookies.txt. "
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
            st.info("Format restreint indisponible, tentative avec d'autres formats.")
            formats_alternatifs = ["bestvideo+bestaudio/best", "best", "bestaudio/best"]
            erreurs_fallback: List[str] = []
            info = None
            for fmt in formats_alternatifs:
                if fmt == ydl_opts.get("format"):
                    continue
                ydl_opts_fallback = dict(ydl_opts)
                ydl_opts_fallback["format"] = fmt
                ydl_opts_fallback.pop("merge_output_format", None)
                try:
                    info = _telecharger(ydl_opts_fallback)
                    break
                except Exception as e2:
                    erreurs_fallback.append(str(e2) or repr(e2))
            if info is None:
                return None, None, None, "Echec du fallback universel : " + (" | ".join(erreurs_fallback) or message)
        else:
            return None, None, None, message

    candidats: List[Path] = []
    for ext in ["mp4", "mkv", "webm", "m4a", "mp3"]:
        candidats.extend(REPERTOIRE_SORTIE.glob(f"*.{ext}"))
    if not candidats:
        return None, None, None, "Telechargement termine mais aucun fichier detecte."
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

    def _run_ffmpeg(args: List[str]) -> None:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    try:
        if utiliser_intervalle:
            _run_ffmpeg([ffmpeg, "-y", "-ss", str(debut), "-to", str(fin), "-i", str(chemin_source_propre), "-c", "copy", "-movflags", "+faststart", str(cible)])
        else:
            _run_ffmpeg([ffmpeg, "-y", "-i", str(chemin_source_propre), "-c", "copy", "-movflags", "+faststart", str(cible)])
    except Exception:
        try:
            if qualite == "Compressee (1280p, CRF 28)":
                filtre_video = ["-vf", "scale=1280:-2"]
                codec_video = ["-c:v", "libx264", "-preset", "slow", "-crf", "28"]
                codec_audio = ["-c:a", "aac", "-b:a", "96k"]
            else:
                filtre_video = []
                codec_video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
                codec_audio = ["-c:a", "aac", "-b:a", "192k"]
            args = [ffmpeg, "-y"]
            if utiliser_intervalle:
                args += ["-ss", str(debut), "-to", str(fin)]
            args += ["-i", str(chemin_source_propre), *filtre_video, *codec_video, *codec_audio, "-movflags", "+faststart", str(cible)]
            _run_ffmpeg(args)
        except Exception as e:
            return None, None, None, f"Echec du remux/transcodage : {e}"

    try:
        if chemin_source_propre.exists():
            chemin_source_propre.unlink()
    except Exception:
        pass

    return str(cible), base_court, info, None


def traiter_local(src_local: Path, base_court: str, qualite: str, utiliser_intervalle: bool, debut: int, fin: int) -> str:
    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as e:
        raise RuntimeError(f"ffmpeg introuvable : {e}") from e

    cible = REPERTOIRE_SORTIE / f"{base_court}_video.mp4"

    def _run_ffmpeg(args: List[str]) -> None:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    if qualite == "Compressee (1280p, CRF 28)":
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
            "slow",
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
        _run_ffmpeg(args)
    else:
        try:
            args = [ffmpeg, "-y"]
            if utiliser_intervalle:
                args += ["-ss", str(debut), "-to", str(fin)]
            args += ["-i", str(src_local), "-c", "copy", "-movflags", "+faststart", str(cible)]
            _run_ffmpeg(args)
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
            _run_ffmpeg(args)
    return str(cible)


def extraire_ressources(video_path: str, debut: int, fin: int, base_court: str, options: Dict[str, bool], utiliser_intervalle: bool):
    try:
        ffmpeg = tl.chemin_ffmpeg()
    except Exception as e:
        return f"ffmpeg introuvable : {e}"

    def _run_ffmpeg(args: List[str]) -> None:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

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
            "slow",
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
        args += ["-i", video_path, *codec_args, "-movflags", "+faststart", str(sortie)]
        return args

    def cmd_images(output_pattern: str, fps: int) -> List[str]:
        args = [ffmpeg, "-y"]
        if utiliser_intervalle:
            args += ["-ss", str(debut), "-to", str(fin)]
        args += ["-i", video_path, "-vf", f"fps={fps},scale=1920:1080", "-q:v", "1", output_pattern]
        return args

    if options.get("mp4"):
        nom = f"{base_court}_seg.mp4" if utiliser_intervalle else f"{base_court}_full.mp4"
        _run_ffmpeg(cmd_segment(REPERTOIRE_SORTIE / nom))

    if options.get("mp3"):
        nom = f"{base_court}_seg.mp3" if utiliser_intervalle else f"{base_court}_full.mp3"
        _run_ffmpeg(cmd_audio(REPERTOIRE_SORTIE / nom, ["-vn", "-acodec", "libmp3lame", "-q:a", "5"]))

    if options.get("wav"):
        nom = f"{base_court}_seg.wav" if utiliser_intervalle else f"{base_court}_full.wav"
        _run_ffmpeg(cmd_audio(REPERTOIRE_SORTIE / nom, ["-vn", "-acodec", "adpcm_ima_wav"]))

    if options.get("img1") or options.get("img25"):
        for fps in (1, 25):
            if (fps == 1 and options.get("img1")) or (fps == 25 and options.get("img25")):
                dossier = f"img{fps}_{base_court}" if utiliser_intervalle else f"img{fps}_full_{base_court}"
                rep = REPERTOIRE_SORTIE / dossier
                rep.mkdir(parents=True, exist_ok=True)
                tmp_pattern = str(rep / "tmp_%06d.jpg")
                _run_ffmpeg(cmd_images(tmp_pattern, fps))
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

    return None


def afficher_video_bytes(chemin_video: Path) -> None:
    if not chemin_video.exists() or not chemin_video.is_file():
        st.info("Apercu indisponible : fichier absent.")
        return
    taille = taille_fichier(chemin_video) or 0
    if taille <= 0:
        st.info("Apercu indisponible : fichier vide.")
        return
    if taille > SEUIL_APERCU_OCTETS:
        st.info("Fichier volumineux : apercu desactive.")
        return
    try:
        with open(chemin_video, "rb") as fichier:
            st.video(fichier.read(), format="video/mp4", start_time=0)
    except Exception as e:
        st.warning(f"Apercu impossible : {e}")


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
st.markdown(
    "Par defaut, l'extraction porte sur toute la video. "
    "Vous pouvez activer un intervalle personnalise si besoin. "
    "Si la video est restreinte (403), exportez vos cookies avec l'extension Firefox "
    "[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)."
)
st.caption(
    "Si YouTube affiche un blocage anti-bot, il faut en pratique un cookies.txt recent, "
    "exporte depuis le navigateur qui vient d'ouvrir la video, avec un User-Agent coherent."
)

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

url = st.text_input("URL YouTube")
cookies_path_eff = ck.afficher_section_cookies(REPERTOIRE_SORTIE)
user_agent_youtube = st.text_input(
    "User-Agent navigateur (utile si YouTube bloque)",
    value=os.environ.get("YTDLP_BROWSER_USER_AGENT", USER_AGENT_YOUTUBE_DEFAUT),
    help=(
        "Colle ici le User-Agent exact du navigateur ayant servi a ouvrir YouTube "
        "et a exporter le cookies.txt. Si tu n'es pas bloque, laisse la valeur par defaut."
    ),
)
fichier_local = st.file_uploader("Ou importer un fichier video (.mp4)", type=["mp4"])

mode_verbose = st.checkbox("Mode diagnostic yt-dlp", value=False)
qualite = st.radio("Qualite de la video de base", ["Compressee (1280p, CRF 28)", "HD (max qualite dispo)"], index=0)

st.subheader("Ressources a produire")
st.markdown("<style>div[data-testid='stHorizontalBlock'] label { white-space: nowrap; }</style>", unsafe_allow_html=True)

opt_timelapse = st.checkbox("Timelapse", key="opt_timelapse")
if opt_timelapse:
    st.warning("Timelapse selectionne : seul le timelapse sera exporte. Les autres options sont desactivees.")
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

st.subheader("Etendue")
etendue = st.radio("Choisir l'etendue", ["Toute la video", "Intervalle personnalise"], index=0)
if etendue == "Intervalle personnalise":
    st.info(
        f"Intervalle personnalise active : de {st.session_state['debut_secs']}s "
        f"a {st.session_state['fin_secs']}s. Le telechargement traitera uniquement cet intervalle."
    )
    cc1, cc2 = st.columns(2)
    st.session_state["debut_secs"] = cc1.number_input("Debut (s)", min_value=0, value=st.session_state["debut_secs"])
    st.session_state["fin_secs"] = cc2.number_input("Fin (s)", min_value=1, value=st.session_state["fin_secs"])
    utiliser_intervalle = True
    if st.session_state["fin_secs"] <= st.session_state["debut_secs"]:
        st.warning("La fin doit etre strictement superieure au debut.")
else:
    utiliser_intervalle = False

afficher_apercu = st.checkbox("Afficher l'apercu video", value=True, disabled=opt_timelapse)
if afficher_apercu and not opt_timelapse:
    if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
        afficher_video_bytes(Path(st.session_state["video_base"]))
    elif fichier_local is not None:
        tmp = sauvegarder_upload_local(fichier_local)
        if tmp is not None:
            afficher_video_bytes(tmp)
    elif url:
        st.info("Apercu indisponible pour une URL tant que le traitement n'a pas ete lance.")

if st.button("Lancer le traitement"):
    with st.spinner("Traitement en cours..."):
        if not ffmpeg_disponible():
            st.error("ffmpeg introuvable et fallback impossible. Verifie l'image Docker et les dependances systeme.")
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
                    st.success(f"Video prete : {Path(video_base).name}")
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
                    st.success(f"Video prete : {Path(cible).name}")
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
                        st.success(f"Timelapse genere ({nb_images} images).")
                        with open(out_path, "rb") as sortie:
                            st.download_button(
                                "Telecharger le timelapse (.mp4)",
                                data=sortie,
                                file_name=Path(out_path).name,
                                mime="video/mp4",
                            )
                        zip_path = REPERTOIRE_SORTIE / f"resultats_{base_court}_timelapse.zip"
                        zipper_sur_disque([Path(out_path)], zip_path)
                        with open(zip_path, "rb") as archive:
                            st.download_button(
                                "Telecharger les resultats (.zip)",
                                data=archive,
                                file_name=zip_path.name,
                                mime="application/zip",
                            )
                    except Exception as e:
                        st.error(f"Echec du timelapse : {e}")
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
                        erreur_extraction = extraire_ressources(video_path, debut_eff, fin_eff, base_court, options, utiliser_intervalle)
                        if erreur_extraction:
                            st.error(f"Erreur pendant l'extraction : {erreur_extraction}")
                        else:
                            st.success("Ressources generees.")

                    fichiers = lister_sorties(base_court)
                    if Path(video_path) not in fichiers:
                        fichiers.append(Path(video_path))
                    zip_path = REPERTOIRE_SORTIE / f"resultats_{base_court}.zip"
                    zipper_sur_disque(fichiers, zip_path)
                    with open(zip_path, "rb") as archive:
                        st.download_button(
                            "Telecharger les resultats (.zip)",
                            data=archive,
                            file_name=zip_path.name,
                            mime="application/zip",
                        )
