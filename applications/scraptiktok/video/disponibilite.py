"""Vérifier la présence des outils vidéo sans charger leurs bibliothèques."""
from importlib.util import find_spec
import os
import shutil


def video_disponible():
    if os.getenv("INSTALL_VIDEO") == "0":
        return False
    try:
        return bool(shutil.which("ffmpeg")) and all(
            find_spec(module) is not None for module in ("numpy", "cv2", "PIL", "yt_dlp"))
    except (ImportError, ValueError):
        return False
