# pip install streamlit opencv-python yt-dlp

import streamlit as st
import cv2
import os
import re
import shutil
import tempfile
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ticket_gate import enforce_streamlit_access
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


DEFAULT_YOUTUBE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
APP_DIR = Path(__file__).resolve().parent
HELP_PATH = APP_DIR / "aide.md"
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
COOKIES_ROOT = APP_DATA_DIR / "youtube-cookies"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
APP_BUILD = "stopmotion-hide-valid-cookies-caption-2026-07-20-01"


def env_int(nom, valeur_defaut):
    try:
        return int(os.environ.get(nom, str(valeur_defaut)).strip())
    except (TypeError, ValueError):
        return valeur_defaut


def load_help_markdown() -> str:
    if not HELP_PATH.exists():
        return "Le fichier `aide.md` est introuvable pour cette application."
    return HELP_PATH.read_text(encoding="utf-8")


def dossier_cookies_session():
    session_id = st.session_state.setdefault("session_id", uuid.uuid4().hex)
    dossier = COOKIES_ROOT / session_id
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def chemin_cookies_session():
    return dossier_cookies_session() / "cookies.txt"


def enregistrer_cookies_upload(fichier_streamlit, dossier_temporaire=None):
    """
    Enregistre un cookies.txt persistant pour la session Streamlit courante.
    """
    chemin_cookies = chemin_cookies_session()
    if fichier_streamlit is None:
        return str(chemin_cookies) if chemin_cookies.exists() and chemin_cookies.stat().st_size > 0 else None

    with open(chemin_cookies, "wb") as fichier_sortie:
        fichier_sortie.write(fichier_streamlit.getvalue())
    return str(chemin_cookies)


def diagnostiquer_cookies(chemin_cookies):
    """
    Vérifie rapidement que le fichier ressemble à un export cookies YouTube exploitable.
    """
    if not chemin_cookies:
        return ""

    try:
        contenu = Path(chemin_cookies).read_text(encoding="utf-8", errors="replace")
    except OSError as erreur:
        return f"Lecture cookies impossible : {erreur}"

    if "youtube.com" not in contenu and ".youtube.com" not in contenu:
        return "Le fichier cookies ne contient aucune entrée YouTube détectée."
    if len(contenu) < 1000:
        return "Le fichier cookies semble très court ; l'export est peut-être incomplet."
    expirations = []
    maintenant = int(time.time())
    for ligne in contenu.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") and not ligne.startswith("#HttpOnly_"):
            continue
        colonnes = ligne.replace("#HttpOnly_", "", 1).split("\t")
        if len(colonnes) < 7:
            continue
        domaine = colonnes[0].lower()
        if "youtube.com" not in domaine and "google.com" not in domaine:
            continue
        try:
            expiration = int(colonnes[4])
        except ValueError:
            continue
        if expiration > 0:
            expirations.append(expiration)
    if expirations:
        restant = max(expirations) - maintenant
        if restant <= 0:
            return "Fichier cookies chargé, mais ses expirations utiles semblent dépassées."
        if restant < 3600:
            return f"Fichier cookies chargé ; attention, expiration utile dans environ {max(1, int(restant / 60))} min."
        return ""
    return ""


def trouver_video_telechargee(dossier_temporaire):
    candidats = []
    for chemin in Path(dossier_temporaire).iterdir():
        if chemin.suffix.lower() in VIDEO_EXTENSIONS and chemin.is_file() and chemin.stat().st_size > 0:
            candidats.append(chemin)
    if not candidats:
        return None
    return str(max(candidats, key=lambda item: item.stat().st_size))


def construire_options_ytdlp(dossier_temporaire, cookies_path=None, user_agent=None, clients_youtube=None):
    output_template = os.path.join(dossier_temporaire, "video_originale.%(ext)s")
    options = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "retries": max(0, env_int("YTDLP_CDN_RETRIES", 0)),
        "fragment_retries": max(0, env_int("YTDLP_CDN_FRAGMENT_RETRIES", 1)),
        "extractor_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 1,
        "sleep_interval_requests": 1,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "socket_timeout": max(5, env_int("YTDLP_CDN_SOCKET_TIMEOUT_SECONDS", 10)),
        "geo_bypass": True,
        "nocheckcertificate": True,
        "restrictfilenames": True,
        "trim_file_name": 120,
        "http_headers": {
            "User-Agent": user_agent or DEFAULT_YOUTUBE_USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.youtube.com/",
        },
    }

    format_env = os.environ.get("YTDLP_FORMAT", "").strip()
    if format_env:
        options["format"] = format_env
    else:
        options["format"] = "18/best[height<=360][ext=mp4]/best[height<=360]/best[ext=mp4]/best"

    youtube_args = {}
    clients_env = [
        client.strip()
        for client in os.environ.get("YTDLP_PLAYER_CLIENTS", "").split(",")
        if client.strip()
    ]
    if clients_youtube is not None:
        youtube_args["player_client"] = clients_youtube
    elif clients_env:
        youtube_args["player_client"] = clients_env

    po_token_args = [
        item.strip()
        for item in os.environ.get("YTDLP_YOUTUBE_PO_TOKEN_ARGS", "").split(",")
        if item.strip()
    ]
    if po_token_args:
        youtube_args["po_token"] = po_token_args

    if youtube_args:
        options["extractor_args"] = {"youtube": youtube_args}

    impersonate = os.environ.get("YTDLP_IMPERSONATE", "").strip()
    if impersonate:
        options["impersonate"] = impersonate

    remote_components = [
        item.strip()
        for item in os.environ.get("YTDLP_REMOTE_COMPONENTS", "").split(",")
        if item.strip()
    ]
    if remote_components:
        options["remote_components"] = set(remote_components)

    if cookies_path:
        options["cookiefile"] = cookies_path
    return options


def erreur_reseau_googlevideo(message):
    message = (message or "").lower()
    incidents = (
        "failed to resolve",
        "address family for hostname not supported",
        "temporary failure in name resolution",
        "network is unreachable",
        "name or service not known",
        "connect timeout",
        "timed out",
    )
    return "googlevideo.com" in message and any(incident in message for incident in incidents)


def url_cdn_googlevideo_alternatif(url_source):
    url_decomposee = urlparse(url_source)
    hostname = url_decomposee.hostname or ""
    correspondance_hote = re.match(
        r"^(?P<prefixe>.*?)(?P<cache>sn-[^.]+)\.googlevideo\.com$",
        hostname,
    )
    if not correspondance_hote:
        return None, None

    caches = []
    for valeur in parse_qs(url_decomposee.query).get("mn", []):
        caches.extend(partie.strip() for partie in valeur.split(",") if partie.strip())
    correspondance_mn = re.search(r"/mn/([^/]+)", unquote(url_decomposee.path))
    if correspondance_mn:
        caches.extend(
            partie.strip()
            for partie in correspondance_mn.group(1).split(",")
            if partie.strip()
        )

    prefixe = correspondance_hote.group("prefixe")
    cache_courant = correspondance_hote.group("cache")
    for cache in caches:
        if cache.startswith("sn-") and cache != cache_courant:
            hote_alternatif = f"{prefixe}{cache}.googlevideo.com"
            return url_decomposee._replace(netloc=hote_alternatif).geturl(), hote_alternatif
    return None, None


def media_video_valide(chemin):
    chemin = Path(chemin)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not chemin.is_file() or chemin.stat().st_size <= 0:
        return False
    resultat = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(chemin),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    return resultat.returncode == 0 and "video" in resultat.stdout.splitlines()


def telecharger_via_cdn_googlevideo_alternatif(
    url,
    dossier_temporaire,
    cookies_path=None,
    user_agent=None,
):
    options = construire_options_ytdlp(
        dossier_temporaire,
        cookies_path=cookies_path,
        user_agent=user_agent,
        clients_youtube=None,
    )
    options_probe = dict(options)
    options_probe.pop("format", None)
    options_probe.update(
        {
            "simulate": True,
            "skip_download": True,
            "ignore_no_formats_error": True,
        }
    )
    with YoutubeDL(options_probe) as ydl:
        info = ydl.extract_info(url.strip(), download=False) or {}

    formats_directs = [
        fmt
        for fmt in (info.get("formats") or [])
        if isinstance(fmt, dict)
        and str(fmt.get("url") or "").startswith(("http://", "https://"))
        and str(fmt.get("vcodec") or "none") != "none"
        and str(fmt.get("acodec") or "none") != "none"
        and "m3u8" not in str(fmt.get("protocol") or "").lower()
    ]
    formats_directs.sort(
        key=lambda fmt: (
            str(fmt.get("format_id") or "") == "18",
            int(fmt.get("height") or 0) <= 720,
            int(fmt.get("height") or 0),
            float(fmt.get("tbr") or 0),
        ),
        reverse=True,
    )
    if not formats_directs:
        raise RuntimeError("aucun format vidéo progressif n'est disponible pour le CDN alternatif")

    format_video = formats_directs[0]
    url_alternative, hote_alternatif = url_cdn_googlevideo_alternatif(
        str(format_video.get("url") or "")
    )
    if not url_alternative or not hote_alternatif:
        raise RuntimeError("l'URL signée ne contient aucun CDN GoogleVideo alternatif")

    extension = re.sub(r"[^A-Za-z0-9]+", "", str(format_video.get("ext") or "mp4")) or "mp4"
    destination = Path(dossier_temporaire) / f"video_originale_cdn_alternatif.{extension}"
    destination.unlink(missing_ok=True)
    headers = options.get("http_headers") or {}
    timeout_total = max(120, env_int("YTDLP_DOWNLOAD_TIMEOUT_SECONDS", 900))
    commande = [
        "curl",
        "--location",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(max(5, env_int("YTDLP_CDN_SOCKET_TIMEOUT_SECONDS", 10))),
        "--max-time",
        str(timeout_total),
        "--speed-time",
        "30",
        "--speed-limit",
        "1024",
        "--output",
        str(destination),
    ]
    if cookies_path:
        commande += ["--cookie", str(cookies_path)]
    for nom_entete in ("User-Agent", "Referer", "Accept-Language"):
        if headers.get(nom_entete):
            commande += ["--header", f"{nom_entete}: {headers[nom_entete]}"]
    commande.append(url_alternative)

    resultat = subprocess.run(
        commande,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_total + 10,
        check=False,
    )
    if resultat.returncode != 0:
        destination.unlink(missing_ok=True)
        detail = (resultat.stderr or resultat.stdout or f"code {resultat.returncode}").strip()
        raise RuntimeError(f"{hote_alternatif} : {detail}")
    if not media_video_valide(destination):
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"{hote_alternatif} a répondu, mais aucun flux vidéo valide n'a été téléchargé"
        )
    return str(destination), hote_alternatif


def telecharger_video_yt_dlp(
    url,
    dossier_temporaire,
    cookies_path=None,
    user_agent=None,
    progress_callback=None,
):
    """
    Télécharge une vidéo YouTube avec yt-dlp.
    """
    if not url or not url.strip():
        raise RuntimeError("Veuillez fournir une URL YouTube.")

    profils_clients = [
        ("auto", None),
        ("source", ["android", "ios", "mweb", "web"]),
        ("web", ["web"]),
        ("mweb", ["mweb"]),
        ("ios", ["ios"]),
        ("android", ["android"]),
    ]
    erreurs = []

    for libelle, clients in profils_clients:
        options = construire_options_ytdlp(
            dossier_temporaire,
            cookies_path=cookies_path,
            user_agent=user_agent,
            clients_youtube=clients,
        )
        try:
            with YoutubeDL(options) as ydl:
                ydl.extract_info(url.strip(), download=True)
            chemin_video = trouver_video_telechargee(dossier_temporaire)
            if chemin_video:
                return chemin_video
            erreurs.append(f"{libelle} : yt-dlp a terminé sans fichier vidéo exploitable.")
        except DownloadError as erreur:
            message = str(erreur) or repr(erreur)
            erreurs.append(f"{libelle} : {message}")
            if erreur_reseau_googlevideo(message):
                if progress_callback:
                    progress_callback(
                        18,
                        "CDN GoogleVideo principal inaccessible. Tentative du CDN alternatif signé.",
                    )
                try:
                    chemin_alternatif, hote_alternatif = telecharger_via_cdn_googlevideo_alternatif(
                        url,
                        dossier_temporaire,
                        cookies_path=cookies_path,
                        user_agent=user_agent,
                    )
                    if progress_callback:
                        progress_callback(
                            22,
                            f"Téléchargement repris via {hote_alternatif}.",
                        )
                    return chemin_alternatif
                except Exception as erreur_alternative:
                    raise RuntimeError(
                        "Le CDN GoogleVideo principal et son CDN alternatif sont "
                        f"inaccessibles depuis le VPS : {erreur_alternative}"
                    ) from erreur_alternative
            if "Sign in to confirm you’re not a bot" in message or "Sign in to confirm you're not a bot" in message:
                if not cookies_path:
                    raise RuntimeError(
                        "YouTube bloque le téléchargement. Ajoute un fichier cookies.txt récent "
                        "exporté depuis le navigateur qui vient d'ouvrir la vidéo, puis relance."
                    ) from erreur
                raise RuntimeError(
                    "YouTube bloque encore malgré le cookies fourni. Réexporte un cookies.txt récent "
                    "depuis le même navigateur et remplace aussi le User-Agent par celui de ce navigateur."
                ) from erreur
        except Exception as erreur:
            message = str(erreur) or repr(erreur)
            erreurs.append(f"{libelle} : {message}")
            if erreur_reseau_googlevideo(message):
                raise RuntimeError(
                    "Le CDN GoogleVideo principal est inaccessible depuis le VPS."
                ) from erreur

    detail = " | ".join(erreurs[-4:]) if erreurs else "aucun détail yt-dlp disponible"
    raise RuntimeError(
        "Aucun format vidéo YouTube exploitable n'a pu être téléchargé par yt-dlp. "
        "Si la vidéo se lit dans le navigateur, réexporte un cookies.txt récent depuis le même navigateur. "
        "Si YouTube exige un PO token, ajoute YTDLP_YOUTUBE_PO_TOKEN_ARGS dans Coolify. "
        f"Dernières erreurs : {detail}"
    )

def appliquer_optical_flow(images):
    """
    Applique la visualisation du flux optique sur les images successives.
    """
    images_avec_flow = []
    for i in range(len(images) - 1):
        img1 = cv2.cvtColor(images[i], cv2.COLOR_BGR2GRAY)
        img2 = cv2.cvtColor(images[i + 1], cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(img1, img2, None,
                                            0.5, 3, 15, 3, 5, 1.2, 0)
        vis = images[i].copy()
        h, w = img1.shape
        step = 16
        for y in range(0, h, step):
            for x in range(0, w, step):
                fx, fy = flow[y, x]
                cv2.arrowedLine(vis, (x, y), (int(x + fx), int(y + fy)),
                                (0, 255, 0), 1, tipLength=0.4)
        images_avec_flow.append(vis)
    images_avec_flow.append(images[-1])  # Dernière image sans flow
    return images_avec_flow


def executer_commande_video(commande, contexte):
    processus = subprocess.run(
        commande,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if processus.returncode != 0:
        sortie = "\n".join(
            ligne.strip()
            for ligne in (processus.stderr or processus.stdout or "").splitlines()[-20:]
            if ligne.strip()
        )
        raise RuntimeError(f"{contexte} a échoué : {sortie or 'aucun détail ffmpeg disponible'}")
    return processus


def detecter_fps_video(chemin_video):
    commande = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate,r_frame_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        chemin_video,
    ]
    try:
        processus = subprocess.run(
            commande,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for ligne in (processus.stdout or "").splitlines():
            valeur = ligne.strip()
            if not valeur or valeur == "0/0":
                continue
            if "/" in valeur:
                numerateur, denominateur = valeur.split("/", 1)
                fps = float(numerateur) / float(denominateur)
            else:
                fps = float(valeur)
            if fps > 0:
                return int(round(fps))
    except Exception:
        pass

    cap = cv2.VideoCapture(chemin_video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return int(round(fps)) if fps and fps > 0 else 0


def extraire_images_echantillonnées(chemin_video, dossier_sortie, fps_cible, avec_flow=False):
    """
    Extrait les images via ffmpeg pour éviter les échecs OpenCV sur certains
    fichiers YouTube récents, puis applique éventuellement l'Optical Flow.
    """
    os.makedirs(dossier_sortie, exist_ok=True)
    fps_original = detecter_fps_video(chemin_video)
    motif_images = os.path.join(dossier_sortie, "image_%05d.jpg")
    commande = [
        "ffmpeg",
        "-y",
        "-i",
        chemin_video,
        "-vf",
        f"fps={fps_cible}",
        "-q:v",
        "2",
        motif_images,
    ]
    executer_commande_video(commande, "Extraction des images avec ffmpeg")

    fichiers_images = sorted(Path(dossier_sortie).glob("image_*.jpg"))
    if not fichiers_images:
        raise RuntimeError(
            "Aucune image n'a été extraite. Le fichier vidéo téléchargé est probablement illisible "
            "ou ne contient pas de flux vidéo exploitable."
        )

    if avec_flow and len(fichiers_images) > 1:
        images = []
        for chemin_image in fichiers_images:
            image = cv2.imread(str(chemin_image))
            if image is None:
                raise RuntimeError(f"Image extraite illisible : {chemin_image.name}")
            images.append(image)
        images_avec_flow = appliquer_optical_flow(images)
        for chemin_image, image in zip(fichiers_images, images_avec_flow):
            cv2.imwrite(str(chemin_image), image)

    return fps_original, len(fichiers_images)

def créer_vidéo_depuis_images(dossier_images, chemin_sortie, fps=12):
    """
    Construit une vidéo MP4 à partir des images extraites via ffmpeg.
    """
    fichiers = sorted([f for f in os.listdir(dossier_images) if f.endswith(".jpg")])
    if not fichiers:
        raise RuntimeError("Impossible de créer la vidéo : aucune image extraite.")

    motif_images = os.path.join(dossier_images, "image_%05d.jpg")
    commande = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        motif_images,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        chemin_sortie,
    ]
    executer_commande_video(commande, "Création de la vidéo stop motion")
    if not os.path.exists(chemin_sortie) or os.path.getsize(chemin_sortie) == 0:
        raise RuntimeError("ffmpeg n'a pas produit de vidéo stop motion exploitable.")
    return chemin_sortie

def reencoder_video_h264(chemin_entrée, chemin_sortie):
    """
    Réencode une vidéo en H.264 pour compatibilité Streamlit.
    """
    commande = [
        "ffmpeg",
        "-y",
        "-i", chemin_entrée,
        "-vcodec", "libx264",
        "-preset", "fast",
        "-crf", "23",
        chemin_sortie
    ]
    executer_commande_video(commande, "Réencodage final H.264")
    if not os.path.exists(chemin_sortie) or os.path.getsize(chemin_sortie) == 0:
        raise RuntimeError("ffmpeg n'a pas produit la vidéo finale H.264.")

# Interface Streamlit
st.set_page_config(page_title="StopMotion", layout="wide")
enforce_streamlit_access("stopmotion_opticalflow", "StopMotion")
st.title("Générateur de Stop Motion avec Optical Flow (optionnel)")
with st.expander("Aide"):
    st.markdown(load_help_markdown(), unsafe_allow_html=True)

mode = st.radio("Source de la vidéo :", ["YouTube (yt-dlp)", "Fichier local (.mp4)"])

cookies_file = None
user_agent_youtube = DEFAULT_YOUTUBE_USER_AGENT
if mode == "YouTube (yt-dlp)":
    url = st.text_input("Entrez l'URL de la vidéo YouTube")
    cookies_file = st.file_uploader(
        "Fichier cookies YouTube (optionnel mais utile si YouTube bloque)",
        type=["txt", "cookies"],
    )
    cookies_session_path = chemin_cookies_session()
    if cookies_session_path.exists() and cookies_session_path.stat().st_size > 0:
        diagnostic_cookies_session = diagnostiquer_cookies(str(cookies_session_path))
        if diagnostic_cookies_session:
            st.caption(diagnostic_cookies_session)
    else:
        st.caption("Aucun cookies.txt mémorisé pour cette session.")
    user_agent_youtube = st.text_input(
        "User-Agent navigateur (utile si YouTube bloque)",
        value=DEFAULT_YOUTUBE_USER_AGENT,
        help=(
            "Si tu utilises un cookies.txt, l'idéal est de coller ici le User-Agent du "
            "même navigateur ayant servi à exporter ce cookies."
        ),
    )
else:
    fichier = st.file_uploader("Téléverser une vidéo .mp4", type=["mp4"])

fps_cible = st.selectbox("FPS cible (effet Stop Motion)", [4, 6, 8, 10, 12, 14, 16], index=2)
avec_optical_flow = st.checkbox("Ajouter le flux optique (mouvement entre images)")

if st.button("Créer la vidéo Stop Motion"):
    progression = st.progress(0, text="Initialisation du traitement...")
    journal = st.empty()
    journal_lignes = []

    def actualiser_progression(pourcentage, message):
        journal_lignes.append(message)
        progression.progress(pourcentage, text=message)
        journal.info("\n".join(f"- {ligne}" for ligne in journal_lignes[-8:]))

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            actualiser_progression(5, "Préparation de l'espace temporaire.")
            # Charger la vidéo
            if mode == "YouTube (yt-dlp)":
                if not url:
                    st.error("Veuillez fournir une URL YouTube.")
                    st.stop()
                cookies_path = enregistrer_cookies_upload(cookies_file, tmpdir)
                diagnostic_cookies = diagnostiquer_cookies(cookies_path)
                if diagnostic_cookies:
                    st.warning(diagnostic_cookies)
                actualiser_progression(15, "Téléchargement de la vidéo YouTube en cours avec yt-dlp.")
                chemin_video = telecharger_video_yt_dlp(
                    url,
                    tmpdir,
                    cookies_path=cookies_path,
                    user_agent=user_agent_youtube.strip() or None,
                    progress_callback=actualiser_progression,
                )
                taille_video = os.path.getsize(chemin_video) / (1024 * 1024)
                actualiser_progression(25, f"Téléchargement terminé : {Path(chemin_video).name} ({taille_video:.1f} Mo).")
            else:
                if not fichier:
                    st.error("Veuillez téléverser une vidéo.")
                    st.stop()
                chemin_video = os.path.join(tmpdir, "video_originale.mp4")
                with open(chemin_video, "wb") as f:
                    f.write(fichier.read())
                taille_video = os.path.getsize(chemin_video) / (1024 * 1024)
                actualiser_progression(25, f"Vidéo téléversée : {taille_video:.1f} Mo.")

            # Extraction images
            dossier_images = os.path.join(tmpdir, "images")
            os.makedirs(dossier_images, exist_ok=True)

            actualiser_progression(40, "Extraction des images en cours avec ffmpeg.")
            fps_origine, nb = extraire_images_echantillonnées(
                chemin_video, dossier_images, fps_cible, avec_flow=avec_optical_flow)
            actualiser_progression(60, f"{nb} images extraites (FPS origine : {fps_origine or 'inconnu'}).")

            # Création de la vidéo temporaire
            chemin_brut = os.path.join(tmpdir, "video_brute.mp4")
            actualiser_progression(75, "Création de la vidéo stop motion intermédiaire.")
            créer_vidéo_depuis_images(dossier_images, chemin_brut, fps=fps_cible)

            # Réencodage final
            chemin_final = os.path.join(tmpdir, "video_finale.mp4")
            actualiser_progression(90, "Réencodage final H.264 en cours.")
            reencoder_video_h264(chemin_brut, chemin_final)

            with open(chemin_final, "rb") as f:
                video_bytes = f.read()
                actualiser_progression(100, "Vidéo générée avec succès.")
                st.success("Vidéo générée avec succès.")
                st.video(video_bytes)
                st.download_button("Télécharger la vidéo", data=video_bytes, file_name="stopmotion.mp4", mime="video/mp4")

        except subprocess.CalledProcessError:
            st.error("Erreur lors de l'utilisation de yt-dlp ou ffmpeg. Vérifiez leur installation.")
        except Exception as e:
            st.error(f"Erreur : {str(e)}")
