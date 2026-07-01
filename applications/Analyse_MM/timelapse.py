# timelapse.py
# Timelapse SANS optical flow. Reprise d’extraction, H.264 + faststart si possible.

import os, json, tarfile, stat, time, subprocess
from pathlib import Path
from typing import Optional, Tuple, List
import urllib.request
import cv2

from app_runtime import ensure_app_data_dir

BASE_DIR = ensure_app_data_dir()
TIMELAPSE_DIR = BASE_DIR / "timelapse_jobs"
TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)

def _resoudre_binaire(env_name: str, nom: str) -> Optional[str]:
    import shutil
    cand = os.environ.get(env_name)
    if cand and Path(cand).exists():
        return cand
    p = shutil.which(nom)
    if p: return p
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    cache = BASE_DIR / "ffmpeg-bin"
    for p in cache.glob("ffmpeg-*-amd64-static/ffmpeg"):
        if p.exists():
            return str(p)
    try:
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        cache.mkdir(parents=True, exist_ok=True)
        arch = cache / "ffmpeg-release-amd64-static.tar.xz"
        urllib.request.urlretrieve(url, str(arch))
        with tarfile.open(arch, "r:xz") as tf:
            tf.extractall(path=cache)
        for p in cache.glob("ffmpeg-*-amd64-static/ffmpeg"):
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return str(p)
    except Exception:
        return None

def chemin_ffmpeg() -> str:
    p = _resoudre_binaire("FFMPEG_BINARY", "ffmpeg")
    if not p:
        raise RuntimeError("ffmpeg introuvable et fallback impossible.")
    return p

def _ouvrir_capture(chemin_video: str, debut: Optional[int], fin: Optional[int]):
    cap = cv2.VideoCapture(chemin_video)
    if not cap.isOpened():
        raise RuntimeError("Impossible d’ouvrir la vidéo source.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    nb = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if debut is None: debut = 0
    if fin is None or fin <= 0: fin = int(round(nb / fps)) if fps > 0 else 1
    if fin <= debut: fin = debut + 1
    frame_start = int(round(debut * fps))
    frame_end = min(nb, int(round(fin * fps))) if fps > 0 else nb
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
    return cap, float(fps), frame_start, frame_end

def _extraire_images(job_dir: Path, src_path: str, fps_cible: int, debut: Optional[int], fin: Optional[int]) -> int:
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    cap, fps, f0, f1 = _ouvrir_capture(src_path, debut, fin)
    ratio = max(1, int(round(fps / float(fps_cible))))
    existantes = sorted(images_dir.glob("frame_*.jpg"))
    next_idx = 0
    if existantes:
        try:
            next_idx = int(existantes[-1].stem.split("_")[1]) + 1
        except Exception:
            next_idx = len(existantes)
    frame_pos = f0 + next_idx * ratio
    if frame_pos < f1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
    total = next_idx
    while frame_pos < f1:
        ok, img = cap.read()
        if not ok:
            break
        if ((frame_pos - f0) % ratio) == 0:
            cv2.imwrite(str(images_dir / f"frame_{total:06d}.jpg"), img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            total += 1
        frame_pos += 1
    cap.release()
    return total

def _assembler(job_dir: Path, fps_sortie: int, base_nom: str) -> str:
    images_dir = job_dir / "images"
    fichiers = sorted(images_dir.glob("frame_*.jpg"))
    if not fichiers:
        raise RuntimeError("Aucune image extraite.")
    img0 = cv2.imread(str(fichiers[0]))
    h, w = img0.shape[:2]
    brut = job_dir / f"{base_nom}_timelapse_{fps_sortie}fps_brut.mp4"
    vw = cv2.VideoWriter(str(brut), cv2.VideoWriter_fourcc(*"mp4v"), fps_sortie, (w, h))
    for fp in fichiers:
        im = cv2.imread(str(fp))
        if im is None: continue
        if im.shape[:2] != (h, w):
            im = cv2.resize(im, (w, h))
        vw.write(im)
    vw.release()
    final = job_dir / f"{base_nom}_timelapse_{fps_sortie}fps.mp4"
    ffmpeg = chemin_ffmpeg()
    try:
        subprocess.run([ffmpeg,"-y","-i",str(brut),"-vcodec","libx264","-preset","fast","-crf","23",
                        "-movflags","+faststart",str(final)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return str(final)
    except Exception:
        return str(brut)

def executer_timelapse(src_path: str, job_id: str, base_nom: str, fps: int,
                       debut: Optional[int] = None, fin: Optional[int] = None, **kwargs):
    job_dir = TIMELAPSE_DIR / f"job_{job_id}"
    (job_dir / "images").mkdir(parents=True, exist_ok=True)
    nb = _extraire_images(job_dir, src_path, fps, debut, fin)
    out = _assembler(job_dir, fps, base_nom)
    return out, nb
