import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import re
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Optional

import cv2
import streamlit as st
from yt_dlp import YoutubeDL

st.set_page_config(page_title="Stop Motion Optical Flow", layout="wide")

APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
SESSIONS_DIR = APP_DATA_DIR / "sessions"
SESSION_ID = st.session_state.setdefault("session_id", uuid.uuid4().hex)
SESSION_DIR = SESSIONS_DIR / SESSION_ID
JOBS_DIR = SESSION_DIR / "jobs"
try:
    PREVIEW_MAX_BYTES = max(1, int(os.environ.get("APP_MAX_PREVIEW_MB", "200"))) * 1024 * 1024
except Exception:
    PREVIEW_MAX_BYTES = 200 * 1024 * 1024


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def touch_session() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    os.utime(SESSION_DIR, None)


def initialiser_repertoires_session() -> None:
    for directory in (SESSIONS_DIR, SESSION_DIR, JOBS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        os.utime(directory, None)


def nettoyer_sessions_expirees() -> None:
    ttl_hours = max(0, _env_int("APP_SESSION_TTL_HOURS", 24))
    if ttl_hours == 0:
        return

    limit = time.time() - (ttl_hours * 3600)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir() or session_dir.name == SESSION_ID:
            continue
        try:
            if session_dir.stat().st_mtime < limit:
                shutil.rmtree(session_dir, ignore_errors=True)
        except Exception:
            continue


def format_file_size(path: Path) -> str:
    size = path.stat().st_size
    units = ["B", "KB", "MB", "GB"]
    index = 0
    value = float(size)
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return f"{value:.1f} {units[index]}"


def clean_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "video"


def create_job_directory(base_name: str) -> Path:
    job_dir = JOBS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:8]}_{clean_name(base_name)[:40]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def pick_downloaded_video(job_dir: Path) -> Path:
    candidates = [
        path
        for path in sorted(job_dir.glob("source*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
    ]
    if not candidates:
        raise RuntimeError("Aucun fichier video n'a ete telecharge par yt-dlp.")
    return candidates[0]


def telecharger_video_youtube(url: str, job_dir: Path) -> tuple[Path, str, str]:
    options: dict[str, Any] = {
        "outtmpl": str(job_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "restrictfilenames": True,
        "merge_output_format": "mp4",
        "format": "bestvideo*+bestaudio/best",
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    title = str(info.get("title") or "youtube_video")
    video_id = str(info.get("id") or "youtube")
    return pick_downloaded_video(job_dir), video_id, title


def sauvegarder_upload(uploaded_file: Any, job_dir: Path) -> tuple[Path, str, str]:
    source_name = uploaded_file.name or "video_locale.mp4"
    suffix = Path(source_name).suffix.lower() or ".mp4"
    destination = job_dir / f"source{suffix}"
    destination.write_bytes(bytes(uploaded_file.getbuffer()))
    return destination, "local", Path(source_name).stem


def collect_video_metadata(video_path: Path) -> dict[str, Optional[float]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Impossible d'ouvrir la video source.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0
    height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0
    capture.release()

    duration = frame_count / fps if fps > 0 else None
    return {
        "fps": fps if fps > 0 else None,
        "frame_count": frame_count if frame_count > 0 else None,
        "width": width if width > 0 else None,
        "height": height if height > 0 else None,
        "duration": duration if duration and duration > 0 else None,
    }


def appliquer_optical_flow(images: list[Any], flow_step: int) -> list[Any]:
    if len(images) < 2:
        return images

    images_with_flow: list[Any] = []
    for index in range(len(images) - 1):
        first_gray = cv2.cvtColor(images[index], cv2.COLOR_BGR2GRAY)
        second_gray = cv2.cvtColor(images[index + 1], cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(
            first_gray,
            second_gray,
            None,
            0.5,
            3,
            15,
            3,
            5,
            1.2,
            0,
        )

        canvas = images[index].copy()
        height, width = first_gray.shape
        for y in range(0, height, flow_step):
            for x in range(0, width, flow_step):
                fx, fy = flow[y, x]
                end_x = max(0, min(width - 1, int(round(x + fx))))
                end_y = max(0, min(height - 1, int(round(y + fy))))
                if (end_x == x and end_y == y) or ((fx * fx + fy * fy) ** 0.5) < 1.0:
                    continue
                cv2.arrowedLine(canvas, (x, y), (end_x, end_y), (0, 255, 0), 1, tipLength=0.35)

        images_with_flow.append(canvas)

    images_with_flow.append(images[-1])
    return images_with_flow


def extraire_images_echantillonnees(
    video_path: Path,
    images_dir: Path,
    target_fps: int,
    with_optical_flow: bool,
    flow_step: int,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Impossible d'ouvrir la video pour extraire les images.")

    original_fps = capture.get(cv2.CAP_PROP_FPS) or float(target_fps)
    if original_fps <= 0:
        original_fps = float(target_fps)

    frame_skip = max(1, int(round(original_fps / float(target_fps))))
    sampled_images: list[Any] = []
    frame_index = 0

    while capture.isOpened():
        success, frame = capture.read()
        if not success:
            break
        if frame_index % frame_skip == 0:
            sampled_images.append(frame)
        frame_index += 1

    capture.release()

    if not sampled_images:
        raise RuntimeError("Aucune image n'a pu etre extraite depuis la video.")

    if with_optical_flow:
        sampled_images = appliquer_optical_flow(sampled_images, flow_step)

    image_paths: list[Path] = []
    for index, image in enumerate(sampled_images):
        output_path = images_dir / f"image_{index:05d}.jpg"
        cv2.imwrite(str(output_path), image)
        image_paths.append(output_path)

    return {
        "fps_original": original_fps,
        "frame_skip": frame_skip,
        "image_paths": image_paths,
        "image_count": len(image_paths),
    }


def creer_video_depuis_images(images_dir: Path, output_path: Path, fps: int) -> Path:
    image_paths = sorted(images_dir.glob("*.jpg"))
    if not image_paths:
        raise RuntimeError("Aucune image JPG n'est disponible pour reconstruire la video.")

    first_image = cv2.imread(str(image_paths[0]))
    if first_image is None:
        raise RuntimeError("Impossible de lire la premiere image extraite.")

    height, width, _ = first_image.shape
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError("Impossible de creer la video temporaire.")

    try:
        for image_path in image_paths:
            image = cv2.imread(str(image_path))
            if image is None:
                continue
            if image.shape[0] != height or image.shape[1] != width:
                image = cv2.resize(image, (width, height))
            writer.write(image)
    finally:
        writer.release()

    if not output_path.exists():
        raise RuntimeError("La video temporaire n'a pas ete ecrite.")
    return output_path


def reencoder_video_h264(source_path: Path, destination_path: Path) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-an",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-movflags",
        "+faststart",
        str(destination_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Echec du reencodage ffmpeg: {result.stderr[-1200:]}")
    return destination_path


def zipper_images(image_paths: list[Path], zip_path: Path) -> Path:
    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_path in image_paths:
            archive.write(str(image_path), arcname=image_path.name)
    return zip_path


def render_result(result: dict[str, Any]) -> None:
    video_path = Path(result["video_path"])
    zip_path = Path(result["zip_path"])
    image_paths = [Path(path) for path in result["image_paths"]]

    if not video_path.exists():
        st.warning("Le dernier resultat de session n'est plus disponible sur le disque temporaire.")
        return

    st.markdown("### Resultat")

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("FPS source", result["fps_original"])
    metric_col_2.metric("FPS stop motion", result["target_fps"])
    metric_col_3.metric("Images extraites", result["image_count"])
    metric_col_4.metric("Taille video", format_file_size(video_path))

    info_parts = [
        f"Source: {result['source_label']}",
        f"Optical flow: {'oui' if result['with_optical_flow'] else 'non'}",
    ]
    if result.get("duration_seconds") is not None:
        info_parts.append(f"Duree source: {result['duration_seconds']:.1f} s")
    if result.get("resolution") is not None:
        info_parts.append(f"Resolution source: {result['resolution']}")
    st.caption(" | ".join(info_parts))

    if video_path.stat().st_size <= PREVIEW_MAX_BYTES:
        st.video(video_path.read_bytes())
    else:
        st.info("La video finale est trop volumineuse pour un apercu integre. Utilise le bouton de telechargement.")

    st.download_button(
        "Telecharger la video MP4",
        data=video_path.read_bytes(),
        file_name=video_path.name,
        mime="video/mp4",
        type="primary",
    )

    if zip_path.exists():
        st.download_button(
            "Telecharger les images JPG",
            data=zip_path.read_bytes(),
            file_name=zip_path.name,
            mime="application/zip",
        )

    preview_paths = [str(path) for path in image_paths[:6] if path.exists()]
    if preview_paths:
        captions = [Path(path).name for path in preview_paths]
        st.image(preview_paths, caption=captions, use_container_width=True)


initialiser_repertoires_session()
nettoyer_sessions_expirees()
touch_session()

if "last_result" not in st.session_state:
    st.session_state.last_result = None

st.title("Generateur Stop Motion avec Optical Flow")
st.caption("Version preparee pour un deploiement VPS / Coolify avec stockage temporaire par session.")

if not ffmpeg_available():
    st.error("ffmpeg n'est pas disponible sur ce serveur. L'application ne peut pas produire la video finale.")
    st.stop()

with st.sidebar:
    st.markdown("### Fonctionnement")
    st.write("- Video YouTube ou fichier local")
    st.write("- Echantillonnage en stop motion")
    st.write("- Optical flow optionnel entre les images")
    st.write("- Export MP4 H.264 + archive ZIP des images")
    st.write("")
    st.write("Les fichiers temporaires sont isoles par session et nettoyes automatiquement.")

source_mode = st.radio("Source de la video", ["YouTube", "Fichier local"], horizontal=True)

youtube_url = ""
uploaded_file = None

if source_mode == "YouTube":
    youtube_url = st.text_input("URL YouTube", placeholder="https://www.youtube.com/watch?v=...")
else:
    uploaded_file = st.file_uploader(
        "Importer une video",
        type=["mp4", "mov", "m4v", "mkv", "webm", "avi"],
        help="Formats acceptes: mp4, mov, m4v, mkv, webm, avi.",
    )

settings_col_1, settings_col_2, settings_col_3 = st.columns(3)
with settings_col_1:
    target_fps = st.select_slider("FPS cible", options=[2, 4, 6, 8, 10, 12, 15, 18, 24], value=8)
with settings_col_2:
    with_optical_flow = st.checkbox("Activer l'optical flow", value=True)
with settings_col_3:
    flow_step = st.select_slider("Pas du maillage", options=[8, 12, 16, 20, 24, 32], value=16)

if not with_optical_flow:
    flow_step = 16

st.info("Le rendu final est reencode en H.264 pour rester compatible avec les navigateurs et Streamlit.")

if st.button("Generer la video stop motion", type="primary", use_container_width=True):
    if source_mode == "YouTube" and not youtube_url.strip():
        st.error("Merci de renseigner une URL YouTube.")
    elif source_mode == "Fichier local" and uploaded_file is None:
        st.error("Merci d'importer un fichier video.")
    else:
        status_box = st.empty()
        try:
            base_name = "youtube" if source_mode == "YouTube" else Path(uploaded_file.name).stem
            job_dir = create_job_directory(base_name)
            images_dir = job_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            if source_mode == "YouTube":
                status_box.info("Telechargement de la video YouTube...")
                source_path, source_id, source_title = telecharger_video_youtube(youtube_url.strip(), job_dir)
            else:
                status_box.info("Copie du fichier local sur le stockage temporaire...")
                source_path, source_id, source_title = sauvegarder_upload(uploaded_file, job_dir)

            status_box.info("Lecture des metadonnees video...")
            metadata = collect_video_metadata(source_path)

            status_box.info("Extraction des images echantillonnees...")
            extraction = extraire_images_echantillonnees(
                source_path,
                images_dir,
                target_fps=target_fps,
                with_optical_flow=with_optical_flow,
                flow_step=flow_step,
            )

            status_box.info("Reconstruction de la video temporaire...")
            raw_video_path = creer_video_depuis_images(
                images_dir,
                job_dir / f"{clean_name(source_title)}_stopmotion_raw.mp4",
                fps=target_fps,
            )

            status_box.info("Reencodage final en H.264...")
            final_video_path = reencoder_video_h264(
                raw_video_path,
                job_dir / f"{clean_name(source_title)}_stopmotion.mp4",
            )

            status_box.info("Archivage des images JPG...")
            images_zip_path = zipper_images(
                extraction["image_paths"],
                job_dir / f"{clean_name(source_title)}_images.zip",
            )

            fps_original = extraction["fps_original"]
            fps_display = int(round(fps_original)) if fps_original else target_fps
            resolution = None
            if metadata.get("width") and metadata.get("height"):
                resolution = f"{int(metadata['width'])}x{int(metadata['height'])}"

            st.session_state.last_result = {
                "source_id": source_id,
                "source_label": source_title,
                "video_path": str(final_video_path),
                "zip_path": str(images_zip_path),
                "image_paths": [str(path) for path in extraction["image_paths"]],
                "target_fps": target_fps,
                "fps_original": fps_display,
                "image_count": extraction["image_count"],
                "with_optical_flow": with_optical_flow,
                "duration_seconds": metadata.get("duration"),
                "resolution": resolution,
            }

            status_box.success("Traitement termine. Le resultat est pret a etre telecharge.")
        except Exception as exc:
            status_box.empty()
            st.session_state.last_result = None
            st.error(str(exc))

if st.session_state.last_result:
    render_result(st.session_state.last_result)
