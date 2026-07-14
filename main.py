# pip install streamlit opencv-python yt-dlp

import streamlit as st
import cv2
import os
import tempfile
import subprocess
import time
import uuid
from pathlib import Path

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
        return f"Fichier cookies chargé ; expiration utile dans environ {int(restant / 3600)} h."
    return "Fichier cookies chargé ; entrées YouTube détectées sans expiration exploitable."


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
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 1,
        "sleep_interval_requests": 1,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "socket_timeout": 30,
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


def telecharger_video_yt_dlp(url, dossier_temporaire, cookies_path=None, user_agent=None):
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
            erreurs.append(f"{libelle} : {str(erreur) or repr(erreur)}")

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

def extraire_images_echantillonnées(chemin_video, dossier_sortie, fps_cible, avec_flow=False):
    """
    Extrait les images à intervalle régulier (effet stop motion), avec option Optical Flow.
    """
    cap = cv2.VideoCapture(chemin_video)
    fps_original = cap.get(cv2.CAP_PROP_FPS)
    ratio_saut = max(1, int(round(fps_original / fps_cible)))

    images_extraites = []
    compteur = 0
    index = 0

    while cap.isOpened():
        succès, image = cap.read()
        if not succès:
            break
        if index % ratio_saut == 0:
            images_extraites.append(image)
            compteur += 1
        index += 1
    cap.release()

    if avec_flow and len(images_extraites) > 1:
        images_extraites = appliquer_optical_flow(images_extraites)

    for i, img in enumerate(images_extraites):
        nom = os.path.join(dossier_sortie, f"image_{i:05d}.jpg")
        cv2.imwrite(nom, img)

    return int(fps_original), len(images_extraites)

def créer_vidéo_depuis_images(dossier_images, chemin_sortie, fps=12):
    """
    Construit une vidéo à partir d’images extraites.
    """
    fichiers = sorted([f for f in os.listdir(dossier_images) if f.endswith(".jpg")])
    if not fichiers:
        return None

    image_exemple = cv2.imread(os.path.join(dossier_images, fichiers[0]))
    h, w, _ = image_exemple.shape
    codec = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(chemin_sortie, codec, fps, (w, h))

    for f in fichiers:
        img = cv2.imread(os.path.join(dossier_images, f))
        img = cv2.resize(img, (w, h))
        video.write(img)

    video.release()
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
    subprocess.run(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
        st.caption(diagnostiquer_cookies(str(cookies_session_path)))
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
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Charger la vidéo
            if mode == "YouTube (yt-dlp)":
                if not url:
                    st.error("Veuillez fournir une URL YouTube.")
                    st.stop()
                cookies_path = enregistrer_cookies_upload(cookies_file, tmpdir)
                diagnostic_cookies = diagnostiquer_cookies(cookies_path)
                if diagnostic_cookies:
                    if diagnostic_cookies.startswith("Fichier cookies chargé") and "attention" not in diagnostic_cookies.lower() and "dépassées" not in diagnostic_cookies.lower():
                        st.success(diagnostic_cookies)
                    else:
                        st.warning(diagnostic_cookies)
                st.info("Téléchargement de la vidéo...")
                chemin_video = telecharger_video_yt_dlp(
                    url,
                    tmpdir,
                    cookies_path=cookies_path,
                    user_agent=user_agent_youtube.strip() or None,
                )
                st.success("Téléchargement terminé.")
            else:
                if not fichier:
                    st.error("Veuillez téléverser une vidéo.")
                    st.stop()
                chemin_video = os.path.join(tmpdir, "video_originale.mp4")
                with open(chemin_video, "wb") as f:
                    f.write(fichier.read())
                st.success("Vidéo téléversée.")

            # Extraction images
            dossier_images = os.path.join(tmpdir, "images")
            os.makedirs(dossier_images, exist_ok=True)

            st.info("Extraction des images en cours...")
            fps_origine, nb = extraire_images_echantillonnées(
                chemin_video, dossier_images, fps_cible, avec_flow=avec_optical_flow)
            st.success(f"{nb} images extraites (FPS origine : {fps_origine})")

            # Création de la vidéo temporaire
            chemin_brut = os.path.join(tmpdir, "video_brute.mp4")
            créer_vidéo_depuis_images(dossier_images, chemin_brut, fps=fps_cible)

            # Réencodage final
            chemin_final = os.path.join(tmpdir, "video_finale.mp4")
            st.info("Réencodage final (H.264)...")
            reencoder_video_h264(chemin_brut, chemin_final)

            with open(chemin_final, "rb") as f:
                video_bytes = f.read()
                st.success("Vidéo générée avec succès.")
                st.video(video_bytes)
                st.download_button("Télécharger la vidéo", data=video_bytes, file_name="stopmotion.mp4", mime="video/mp4")

        except subprocess.CalledProcessError:
            st.error("Erreur lors de l'utilisation de yt-dlp ou ffmpeg. Vérifiez leur installation.")
        except Exception as e:
            st.error(f"Erreur : {str(e)}")
