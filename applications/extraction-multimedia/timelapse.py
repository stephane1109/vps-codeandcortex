import json
import os
import shutil
import stat
import subprocess
import tarfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2


BASE_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
TIMELAPSE_DIR = BASE_DIR / "timelapse_jobs"
TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)


def _telecharger_ffmpeg_statique(dest_dir: Path) -> str:
    import urllib.request

    dest_dir.mkdir(parents=True, exist_ok=True)
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    archive = dest_dir / "ffmpeg-release-amd64-static.tar.xz"
    urllib.request.urlretrieve(url, str(archive))

    with tarfile.open(archive, "r:xz") as contenu:
        membres = [m for m in contenu.getmembers() if m.name.endswith("/ffmpeg")]
        if not membres:
            raise RuntimeError("Archive ffmpeg invalide : binaire non trouve.")
        contenu.extractall(path=dest_dir)

    for chemin in dest_dir.glob("ffmpeg-*-amd64-static/ffmpeg"):
        chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return str(chemin)

    raise RuntimeError("Binaire ffmpeg introuvable apres extraction.")


def _resoudre_binaire(nom_env: str, nom: str) -> Optional[str]:
    candidat = os.environ.get(nom_env)
    if candidat and Path(candidat).exists():
        return candidat

    which = shutil.which(nom)
    if which:
        return which

    try:
        import imageio_ffmpeg

        chemin = imageio_ffmpeg.get_ffmpeg_exe()
        if chemin and Path(chemin).exists():
            return chemin
    except Exception:
        pass

    cache_dir = BASE_DIR / "ffmpeg-bin"
    for chemin in cache_dir.glob("ffmpeg-*-amd64-static/ffmpeg"):
        if chemin.exists():
            return str(chemin)

    try:
        return _telecharger_ffmpeg_statique(cache_dir)
    except Exception:
        return None


def chemin_ffmpeg() -> str:
    chemin = _resoudre_binaire("FFMPEG_BINARY", "ffmpeg")
    if not chemin:
        raise RuntimeError("ffmpeg introuvable et fallback impossible.")
    return chemin


def _progress_path(job_dir: Path) -> Path:
    return job_dir / "progress.json"


def _sauver_progress(job_dir: Path, contenu: dict) -> None:
    _progress_path(job_dir).write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")


def _ouvrir_capture(chemin_video: str, debut: Optional[int], fin: Optional[int]) -> Tuple[cv2.VideoCapture, float, int, int]:
    cap = cv2.VideoCapture(chemin_video)
    if not cap.isOpened():
        raise RuntimeError("Impossible d'ouvrir la video source.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if debut is None:
        debut = 0
    if fin is None or fin <= 0:
        fin = int(round(nb_frames / fps)) if fps > 0 else 1
    if fin <= debut:
        fin = debut + 1

    frame_start = int(round(debut * fps))
    frame_end = min(nb_frames, int(round(fin * fps))) if fps > 0 else nb_frames
    frame_start = max(0, frame_start)
    frame_end = max(frame_start + 1, frame_end)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
    return cap, float(fps), frame_start, frame_end


def _extraire_images_avec_reprise(
    src_path: str,
    job_dir: Path,
    fps_cible: int,
    debut: Optional[int],
    fin: Optional[int],
    batch_frames: int = 1200,
) -> Tuple[int, int]:
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    cap, fps_source, frame_start, frame_end = _ouvrir_capture(src_path, debut, fin)
    ratio_saut = max(1, int(round(fps_source / float(fps_cible))))

    existantes = sorted(images_dir.glob("frame_*.jpg"))
    next_index = 0
    if existantes:
        try:
            next_index = int(existantes[-1].stem.split("_")[1]) + 1
        except Exception:
            next_index = len(existantes)

    frame_pos = frame_start + next_index * ratio_saut
    if frame_pos < frame_end:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)

    total = next_index
    while frame_pos < frame_end:
        courant = 0
        lot: List = []
        while courant < batch_frames and frame_pos < frame_end:
            ok, image = cap.read()
            if not ok:
                break
            if ((frame_pos - frame_start) % ratio_saut) == 0:
                lot.append(image)
            courant += 1
            frame_pos += 1

        if not lot:
            continue

        for image in lot:
            cv2.imwrite(str(images_dir / f"frame_{total:06d}.jpg"), image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            total += 1

        _sauver_progress(
            job_dir,
            {
                "fps_source": fps_source,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "ratio_saut": ratio_saut,
                "images_sauvegardees": total,
            },
        )
        time.sleep(0.01)

    cap.release()
    return int(round(fps_source)), total


def _construire_video_depuis_images(job_dir: Path, fps_sortie: int, base_nom: str) -> str:
    images_dir = job_dir / "images"
    fichiers = sorted(images_dir.glob("frame_*.jpg"))
    if not fichiers:
        raise RuntimeError("Aucune image prete pour le timelapse.")

    premiere = cv2.imread(str(fichiers[0]))
    if premiere is None:
        raise RuntimeError("Impossible de lire la premiere image.")

    hauteur, largeur = premiere.shape[:2]
    out_brut = job_dir / f"{base_nom}_timelapse_{fps_sortie}fps_brut.mp4"
    writer = cv2.VideoWriter(str(out_brut), cv2.VideoWriter_fourcc(*"mp4v"), fps_sortie, (largeur, hauteur))

    for fichier in fichiers:
        image = cv2.imread(str(fichier))
        if image is None:
            continue
        if image.shape[:2] != (hauteur, largeur):
            image = cv2.resize(image, (largeur, hauteur))
        writer.write(image)
    writer.release()

    out_final = job_dir / f"{base_nom}_timelapse_{fps_sortie}fps.mp4"
    try:
        ffmpeg = chemin_ffmpeg()
    except Exception:
        ffmpeg = None

    if ffmpeg:
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(out_brut),
                    "-vcodec",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-movflags",
                    "+faststart",
                    str(out_final),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return str(out_final)
        except Exception:
            return str(out_brut)

    return str(out_brut)


def executer_timelapse(
    src_path: str,
    job_id: str,
    base_nom: str,
    fps: int,
    debut: Optional[int] = None,
    fin: Optional[int] = None,
    job_root: Optional[str | Path] = None,
    **kwargs,
) -> Tuple[str, int]:
    root = Path(job_root) if job_root is not None else TIMELAPSE_DIR
    job_dir = root / f"job_{job_id}"
    (job_dir / "images").mkdir(parents=True, exist_ok=True)

    _, nb_images = _extraire_images_avec_reprise(src_path, job_dir, fps, debut, fin)
    sortie = _construire_video_depuis_images(job_dir, fps, base_nom)
    return sortie, nb_images
