from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def ensure_directory(path: str | Path) -> Path:
    """Crée un dossier si besoin et renvoie un Path normalisé."""
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def utc_session_id(prefix: str = "session") -> str:
    """Identifiant de session simple et stable."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"


def write_json(path: str | Path, payload: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def is_youtube_url(source: str) -> bool:
    value = str(source or "").strip().lower()
    return "youtube.com/" in value or "youtu.be/" in value


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def resolve_ytdlp_command() -> list[str]:
    """Privilégie le module Python yt_dlp, sinon le binaire yt-dlp."""
    try:
        import yt_dlp  # noqa: F401  # pragma: no cover - dépendance externe

        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        if command_exists("yt-dlp"):
            return ["yt-dlp"]

    raise RuntimeError("yt-dlp est requis pour traiter une URL YouTube.")


def resolve_ffmpeg_command() -> str:
    """Résout un exécutable ffmpeg système ou fourni par imageio-ffmpeg."""
    if command_exists("ffmpeg"):
        return "ffmpeg"

    try:
        import imageio_ffmpeg  # pragma: no cover - dépendance externe

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and Path(candidate).is_file():
            return candidate
    except Exception:
        pass

    raise RuntimeError(
        "ffmpeg est requis pour ce traitement. Installez-le ou laissez le bootstrap Python installer imageio-ffmpeg."
    )


def run_command(args: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """Exécute une commande et remonte une erreur explicite en cas d'échec."""
    try:
      return subprocess.run(
          args,
          cwd=str(cwd) if cwd else None,
          check=True,
          text=True,
          capture_output=True,
      )
    except subprocess.CalledProcessError as exc:
      stderr = (exc.stderr or "").strip()
      stdout = (exc.stdout or "").strip()
      details = stderr or stdout or str(exc)
      command_label = Path(args[0]).name if args else ""
      joined_args = " ".join(args)
      if command_label == "yt-dlp" or "yt_dlp" in joined_args:
          details = enrich_ytdlp_error(details)
      raise RuntimeError(f"Commande en échec: {' '.join(args)}\n{details}") from exc


def enrich_ytdlp_error(details: str) -> str:
    """Ajoute un diagnostic plus utile pour les erreurs YouTube fréquentes."""
    message = str(details or "").strip()
    lowered = message.lower()
    hints: list[str] = []

    if "nsig extraction failed" in lowered or "http error 403" in lowered or "http error 400" in lowered:
        hints.append(
            "Diagnostic multimodal : YouTube refuse le téléchargement. Les causes les plus probables sont "
            "un yt-dlp trop ancien ou des cookies expirés / incomplets."
        )
    if "confirm you are on the latest version using yt-dlp -u" in lowered or "please report this issue" in lowered:
        hints.append(
            "Action recommandée : mettez à jour yt-dlp, puis relancez le téléchargement avec un cookies.txt exporté récemment."
        )

    if not hints:
        return message

    return f"{message}\n\n" + "\n".join(hints)


def resolve_local_source(source: str | Path) -> Path:
    candidate = Path(source).expanduser()
    if not candidate.exists():
        raise FileNotFoundError(f"Source introuvable: {candidate}")
    return candidate.resolve()


def download_youtube_source(
    url: str,
    output_dir: str | Path,
    prefer: str = "audio",
    cookies_path: str | Path | None = None,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> Path:
    """
    Télécharge une source YouTube localement via yt-dlp.
    - prefer='audio' : meilleure piste audio
    - prefer='video' : meilleur mp4 lisible pour analyse visuelle
    """
    destination_dir = ensure_directory(output_dir)
    template = destination_dir / ("youtube_source.%(ext)s")
    if prefer == "video":
        format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        format_selector = "bestaudio/best"

    command = [
        *resolve_ytdlp_command(),
        "--no-playlist",
        "--force-overwrites",
    ]
    if cookies_path:
        resolved_cookies = resolve_local_source(cookies_path)
        command.extend(["--cookies", str(resolved_cookies)])
    if start_sec is not None or end_sec is not None:
        start_label = seconds_to_ffmpeg_timestamp(start_sec or 0.0)
        end_label = seconds_to_ffmpeg_timestamp(end_sec) if end_sec is not None else ""
        section = f"*{start_label}-{end_label}" if end_label else f"*{start_label}-inf"
        command.extend(["--download-sections", section])

    command.extend(
        [
            "-f",
            format_selector,
            "-o",
            str(template),
            url,
        ]
    )

    if prefer == "video":
        command[command.index("-o"):command.index("-o")] = ["--merge-output-format", "mp4"]

    run_command(command)

    candidates = sorted(destination_dir.glob("youtube_source.*"))
    if not candidates:
        raise RuntimeError("yt-dlp a terminé sans produire de fichier local.")
    return candidates[-1]


def resolve_media_source(
    source: str,
    output_dir: str | Path,
    prefer: str = "audio",
    cookies_path: str | Path | None = None,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> Path:
    value = str(source or "").strip()
    if not value:
        raise ValueError("Aucune source fournie.")

    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        if is_youtube_url(value):
            return download_youtube_source(
                value,
                output_dir=output_dir,
                prefer=prefer,
                cookies_path=cookies_path,
                start_sec=start_sec,
                end_sec=end_sec,
            )
        raise ValueError("Seules les URLs YouTube sont prises en charge directement.")

    return resolve_local_source(value)


def seconds_to_ffmpeg_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = max(0.0, float(seconds))
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total - (hours * 3600) - (minutes * 60)
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def extract_audio_wav(
    source_path: str | Path,
    output_dir: str | Path,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    """Extrait une piste WAV standardisée via ffmpeg."""
    ffmpeg_command = resolve_ffmpeg_command()
    destination_dir = ensure_directory(output_dir)
    wav_path = destination_dir / "audio_source.wav"
    args = [
        ffmpeg_command,
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ar",
        str(sample_rate),
    ]
    if mono:
        args.extend(["-ac", "1"])
    args.append(str(wav_path))
    run_command(args)
    return wav_path


def extract_audio_mp3(
    source_path: str | Path,
    output_dir: str | Path,
) -> Path:
    """Extrait une piste MP3 standardisée via ffmpeg."""
    ffmpeg_command = resolve_ffmpeg_command()
    destination_dir = ensure_directory(output_dir)
    mp3_path = destination_dir / "audio_source.mp3"
    args = [
        ffmpeg_command,
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(mp3_path),
    ]
    run_command(args)
    return mp3_path


def ensure_video_mp4(
    source_path: str | Path,
    output_dir: str | Path,
) -> Path:
    """Normalise une source vidéo vers un MP4 lisible pour les traitements suivants."""
    ffmpeg_command = resolve_ffmpeg_command()
    source = Path(source_path).expanduser().resolve()
    destination_dir = ensure_directory(output_dir)
    mp4_path = destination_dir / "source_video.mp4"

    if source.suffix.lower() == ".mp4":
        if source != mp4_path:
            shutil.copy2(source, mp4_path)
        return mp4_path

    args = [
        ffmpeg_command,
        "-y",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(mp4_path),
    ]
    run_command(args)
    return mp4_path


def clip_video_interval(
    source_path: str | Path,
    output_dir: str | Path,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> Path:
    """Découpe un intervalle vidéo en MP4, si un intervalle personnalisé est demandé."""
    if start_sec is None and end_sec is None:
        return Path(source_path).expanduser().resolve()

    ffmpeg_command = resolve_ffmpeg_command()
    source = Path(source_path).expanduser().resolve()
    destination_dir = ensure_directory(output_dir)
    clip_path = destination_dir / "source_video_clip.mp4"

    args = [ffmpeg_command, "-y"]
    if start_sec is not None and start_sec > 0:
        args.extend(["-ss", str(start_sec)])
    args.extend(["-i", str(source)])
    if end_sec is not None:
        if start_sec is not None and end_sec > start_sec:
            args.extend(["-t", str(end_sec - start_sec)])
        elif start_sec is None and end_sec > 0:
            args.extend(["-to", str(end_sec)])
    args.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(clip_path),
        ]
    )
    run_command(args)
    return clip_path


def extract_video_frames(
    source_path: str | Path,
    output_dir: str | Path,
    fps_value: float = 1.0,
    start_sec: float | None = None,
    end_sec: float | None = None,
    quality: str = "low",
) -> Path:
    """Extrait des images régulières d'une vidéo via ffmpeg."""
    ffmpeg_command = resolve_ffmpeg_command()
    if fps_value <= 0:
        raise ValueError("La cadence d'extraction doit être strictement positive.")

    destination_dir = ensure_directory(output_dir)
    if float(fps_value).is_integer():
        fps_prefix = f"{int(fps_value)}fps"
    else:
        fps_prefix = f"{str(fps_value).replace('.', '_')}fps"
    output_pattern = destination_dir / f"{fps_prefix}_%06d.jpg"

    args = [ffmpeg_command, "-y"]
    if start_sec is not None and start_sec > 0:
        args.extend(["-ss", str(start_sec)])
    args.extend(["-i", str(source_path)])

    if end_sec is not None:
        if start_sec is not None and end_sec > start_sec:
            args.extend(["-t", str(end_sec - start_sec)])
        elif start_sec is None and end_sec > 0:
            args.extend(["-to", str(end_sec)])

    scale_filter = "scale=1024:-2" if quality == "low" else "scale=1920:-2"
    quality_level = "5" if quality == "low" else "2"
    args.extend(
        [
            "-vf",
            f"fps={fps_value},{scale_filter}",
            "-q:v",
            quality_level,
            str(output_pattern),
        ]
    )
    run_command(args)
    return destination_dir


def probe_duration_seconds(media_path: str | Path) -> float | None:
    """Durée totale via ffprobe si disponible."""
    if not command_exists("ffprobe"):
        return None

    try:
        result = run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ]
        )
        return float((result.stdout or "").strip())
    except Exception:
        return None
