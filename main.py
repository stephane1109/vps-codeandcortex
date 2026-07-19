import io
import json
import math
import shutil
import subprocess
import tempfile
import wave
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image


APP_NAME = "DetectIA vidéo"
APP_VERSION = "0.1.0 - 14/07/2026"
APP_BUILD = "detectia-forensic-comparison-audio-flow-2026-07-19-02"
HELP_PATH = Path(__file__).resolve().parent / "aide.md"


@dataclass
class AnalysisConfig:
    sample_every_n_frames: int
    max_pairs: int
    resize_width: int
    algorithm: str
    candidate_count: int
    keep_flow_gallery: bool
    flow_gallery_limit: int


def resize_frame(frame_bgr: np.ndarray, target_width: int) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    if width <= target_width:
        return frame_bgr
    ratio = target_width / float(width)
    target_height = max(1, int(height * ratio))
    return cv2.resize(frame_bgr, (target_width, target_height), interpolation=cv2.INTER_AREA)


def bgr_to_rgb(frame_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def image_to_png_bytes(image_rgb: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image_rgb).save(buffer, format="PNG")
    return buffer.getvalue()


def normalize_map(values: np.ndarray) -> np.ndarray:
    clean = np.nan_to_num(values.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if float(clean.max()) <= float(clean.min()):
        return np.zeros_like(clean, dtype=np.uint8)
    normalized = cv2.normalize(clean, None, 0, 255, cv2.NORM_MINMAX)
    return normalized.astype(np.uint8)


def heatmap_rgb(values: np.ndarray) -> np.ndarray:
    heat_bgr = cv2.applyColorMap(normalize_map(values), cv2.COLORMAP_INFERNO)
    return cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)


def flow_to_rgb(flow: np.ndarray) -> np.ndarray:
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
    hsv = np.zeros((*magnitude.shape, 3), dtype=np.uint8)
    hsv[..., 0] = np.uint8(np.mod(angle / 2.0, 180))
    hsv[..., 1] = 255
    hsv[..., 2] = normalize_map(magnitude)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def draw_flow_arrows(frame_rgb: np.ndarray, flow: np.ndarray, step: int = 22) -> np.ndarray:
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    height, width = flow.shape[:2]
    for y in range(step // 2, height, step):
        for x in range(step // 2, width, step):
            dx, dy = flow[y, x]
            end_x = int(np.clip(x + dx * 2.0, 0, width - 1))
            end_y = int(np.clip(y + dy * 2.0, 0, height - 1))
            cv2.arrowedLine(frame_bgr, (x, y), (end_x, end_y), (0, 255, 90), 1, tipLength=0.35)
    return bgr_to_rgb(frame_bgr)


def entropy_from_values(values: np.ndarray, bins: int, value_range: tuple[float, float] | None = None) -> float:
    flat = values[np.isfinite(values)].ravel()
    if flat.size == 0:
        return 0.0
    hist, _ = np.histogram(flat, bins=bins, range=value_range)
    total = hist.sum()
    if total <= 0:
        return 0.0
    probabilities = hist.astype(np.float64) / float(total)
    probabilities = probabilities[probabilities > 0]
    return float(-(probabilities * np.log2(probabilities)).sum())


def compute_optical_flow(prev_gray: np.ndarray, curr_gray: np.ndarray, algorithm: str) -> np.ndarray:
    if algorithm == "DIS rapide" and hasattr(cv2, "DISOpticalFlow_create"):
        try:
            dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
            return dis.calc(prev_gray, curr_gray, None)
        except Exception:
            pass

    return cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        pyr_scale=0.5,
        levels=3,
        winsize=21,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )


def warp_previous_frame(prev_gray: np.ndarray, flow: np.ndarray) -> np.ndarray:
    height, width = prev_gray.shape
    grid_x, grid_y = np.meshgrid(np.arange(width), np.arange(height))
    map_x = (grid_x - flow[..., 0]).astype(np.float32)
    map_y = (grid_y - flow[..., 1]).astype(np.float32)
    return cv2.remap(prev_gray, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def component_score(value: float, reference: float) -> float:
    if reference <= 0:
        return 0.0
    return float(np.clip(value / reference, 0.0, 1.0))


def compute_global_score(metrics_df: pd.DataFrame) -> dict[str, float | str]:
    if metrics_df.empty:
        return {
            "score": 0.0,
            "niveau": "indisponible",
            "interpretation": "Analyse insuffisante : trop peu de frames exploitables.",
        }

    residual_median = float(metrics_df["residual_mean"].median())
    residual_p95 = float(metrics_df["residual_p95"].median())
    flicker_median = float(metrics_df["flicker_mean"].median())
    flow_cv_median = float(metrics_df["flow_cv"].median())
    jerk_median = float(metrics_df["motion_jerk"].median())

    residual_score = component_score(residual_median, 0.075)
    residual_peak_score = component_score(residual_p95, 0.22)
    flicker_score = component_score(flicker_median, 0.10)
    flow_cv_score = component_score(flow_cv_median, 3.0)
    jerk_score = component_score(jerk_median, 0.75)

    score = 100.0 * (
        0.32 * residual_score
        + 0.20 * residual_peak_score
        + 0.18 * flicker_score
        + 0.15 * flow_cv_score
        + 0.15 * jerk_score
    )

    if score < 35:
        niveau = "faible"
        interpretation = "Peu d'incohérences temporelles fortes ont été détectées sur cet échantillon."
    elif score < 65:
        niveau = "à examiner"
        interpretation = "Des incohérences temporelles existent. Elles doivent être interprétées avec le contexte, la compression et le montage."
    else:
        niveau = "élevé"
        interpretation = "L'analyse repère de fortes incohérences de mouvement ou de reconstruction entre frames."

    return {
        "score": round(score, 1),
        "niveau": niveau,
        "interpretation": interpretation,
        "residual_median": round(residual_median, 4),
        "residual_p95": round(residual_p95, 4),
        "flicker_median": round(flicker_median, 4),
        "flow_cv_median": round(flow_cv_median, 4),
        "jerk_median": round(jerk_median, 4),
    }


def update_top_candidates(candidates: list[dict[str, Any]], candidate: dict[str, Any], limit: int) -> None:
    candidates.append(candidate)
    candidates.sort(key=lambda item: float(item["pair_score"]), reverse=True)
    del candidates[limit:]


def log_analysis(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    lines = st.session_state.setdefault("analysis_log", [])
    lines.append(f"[{timestamp}] {message}")
    st.session_state.analysis_log = lines[-180:]


def render_analysis_log(expanded: bool = False) -> None:
    lines = st.session_state.get("analysis_log", [])
    if not lines:
        return
    with st.expander("Journal d'analyse", expanded=expanded):
        st.code("\n".join(lines))


def run_command(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def ffprobe_summary(video_path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False, "message": "ffprobe indisponible"}

    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
        "-show_entries",
        "format=format_name,duration,size",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_command(command, timeout=30)
    if result.returncode != 0:
        return {"available": True, "error": result.stderr.strip() or result.stdout.strip()}
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": True, "error": "Sortie ffprobe illisible", "raw": result.stdout[:1000]}


def log_video_probe(video_path: Path, label: str) -> None:
    probe = ffprobe_summary(video_path)
    if not probe.get("available", True):
        log_analysis(f"Diagnostic vidéo {label} : ffprobe indisponible.")
        return
    if probe.get("error"):
        log_analysis(f"Diagnostic vidéo {label} : ffprobe erreur : {probe['error']}")
        return

    stream = (probe.get("streams") or [{}])[0]
    fmt = probe.get("format") or {}
    log_analysis(
        "Diagnostic vidéo "
        f"{label} : codec={stream.get('codec_name', '?')} | "
        f"taille={stream.get('width', '?')}x{stream.get('height', '?')} | "
        f"fps={stream.get('avg_frame_rate', '?')} | "
        f"frames={stream.get('nb_frames', '?')} | "
        f"durée_stream={stream.get('duration', '?')}s | "
        f"durée_format={fmt.get('duration', '?')}s | "
        f"format={fmt.get('format_name', '?')}"
    )


def transcode_for_opencv(source_path: Path, output_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg est indisponible dans le conteneur : impossible de convertir la vidéo.")

    # Conversion de secours : H.264 + yuv420p + FPS constant pour maximiser la compatibilité OpenCV.
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        "fps=25,scale=960:-2:force_original_aspect_ratio=decrease",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    log_analysis("Conversion ffmpeg de secours : normalisation MP4 H.264 pour OpenCV.")
    result = run_command(command, timeout=300)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "erreur ffmpeg inconnue"
        raise RuntimeError(f"Conversion ffmpeg impossible : {details}")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError("Conversion ffmpeg terminée sans fichier vidéo exploitable.")
    log_analysis(f"Conversion ffmpeg réussie : {output_path.stat().st_size} octets.")


def extract_audio_metrics(video_path: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"available": False, "message": "ffmpeg indisponible pour l'analyse sonore"}

    with tempfile.TemporaryDirectory(prefix="detectia_audio_") as audio_dir:
        wav_path = Path(audio_dir) / "audio_mono_16k.wav"
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(wav_path),
        ]
        result = run_command(command, timeout=180)
        if result.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size <= 44:
            details = result.stderr.strip() or result.stdout.strip() or "aucune piste audio exploitable"
            return {"available": False, "message": details}

        with wave.open(str(wav_path), "rb") as wav_file:
            sample_rate = int(wav_file.getframerate())
            channels = int(wav_file.getnchannels())
            frame_count = int(wav_file.getnframes())
            raw_audio = wav_file.readframes(frame_count)

    samples = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return {"available": False, "message": "piste audio vide"}

    frame_size = 1024
    hop = 512
    rms_values: list[float] = []
    zcr_values: list[float] = []
    centroid_values: list[float] = []
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)

    for start in range(0, max(1, samples.size - frame_size + 1), hop):
        frame = samples[start : start + frame_size]
        if frame.size < frame_size:
            frame = np.pad(frame, (0, frame_size - frame.size))
        rms = float(np.sqrt(np.mean(np.square(frame))))
        rms_values.append(rms)
        zcr_values.append(float(np.mean(np.abs(np.diff(np.signbit(frame))))))
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(frame_size)))
        spectrum_sum = float(np.sum(spectrum))
        centroid = 0.0 if spectrum_sum <= 1e-12 else float(np.sum(frequencies * spectrum) / spectrum_sum)
        centroid_values.append(centroid)

    rms_array = np.array(rms_values, dtype=np.float64)
    db_array = 20.0 * np.log10(np.maximum(rms_array, 1e-8))
    voiced = rms_array > 0.015

    return {
        "available": True,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_seconds": round(float(samples.size / sample_rate), 3),
        "rms_mean": round(float(np.mean(rms_array)), 5),
        "rms_std": round(float(np.std(rms_array)), 5),
        "energy_cv": round(float(np.std(rms_array) / (np.mean(rms_array) + 1e-8)), 4),
        "silence_ratio": round(float(1.0 - np.mean(voiced)), 4),
        "dynamic_range_db": round(float(np.percentile(db_array, 95) - np.percentile(db_array, 5)), 3),
        "zcr_mean": round(float(np.mean(zcr_values)), 5),
        "spectral_centroid_mean": round(float(np.mean(centroid_values)), 2),
    }


def attach_audio_metrics(result: dict[str, Any], video_path: Path, label: str) -> dict[str, Any]:
    log_analysis(f"Analyse sonore ({label}) : extraction ffmpeg et indicateurs audio.")
    try:
        result["audio"] = extract_audio_metrics(video_path)
    except Exception as exc:
        result["audio"] = {"available": False, "message": str(exc) or repr(exc)}
    if result["audio"].get("available"):
        log_analysis(
            f"Audio ({label}) : durée={result['audio']['duration_seconds']}s | "
            f"silence={result['audio']['silence_ratio']} | énergie_cv={result['audio']['energy_cv']}"
        )
    else:
        log_analysis(f"Audio ({label}) indisponible : {result['audio'].get('message', 'erreur inconnue')}")
    return result


def analyze_video_cv2(video_path: Path, config: AnalysisConfig, source_label: str) -> dict[str, Any]:
    log_video_probe(video_path, source_label)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir la vidéo avec OpenCV ({source_label}).")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    fps = fps if fps > 0 else 25.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    original_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    original_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_seconds = float(total_frames / fps) if total_frames > 0 else 0.0

    metrics: list[dict[str, float | int]] = []
    candidates: list[dict[str, Any]] = []
    flow_gallery: list[dict[str, Any]] = []
    previous_gray: np.ndarray | None = None
    previous_mean_mag: float | None = None
    flow_heat: np.ndarray | None = None
    residual_heat: np.ndarray | None = None

    frame_index = -1
    read_frames = 0
    sampled_pairs = 0
    progress = st.progress(0, text="Analyse en cours...")
    status_box = st.empty()
    log_analysis(
        f"Lecture OpenCV ({source_label}) : fps={fps:.2f} | frames annoncées={total_frames} | "
        f"durée estimée={duration_seconds:.2f}s | taille={original_width}x{original_height}"
    )

    while True:
        success, frame_bgr = capture.read()
        if not success:
            break
        frame_index += 1
        read_frames += 1

        if frame_index % config.sample_every_n_frames != 0:
            continue

        frame_bgr = resize_frame(frame_bgr, config.resize_width)
        frame_rgb = bgr_to_rgb(frame_bgr)
        current_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        if previous_gray is None:
            previous_gray = current_gray
            continue

        flow = compute_optical_flow(previous_gray, current_gray, config.algorithm)
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=False)
        warped_previous = warp_previous_frame(previous_gray, flow)
        residual_map = np.abs(current_gray.astype(np.float32) - warped_previous.astype(np.float32)) / 255.0
        flicker_map = np.abs(current_gray.astype(np.float32) - previous_gray.astype(np.float32)) / 255.0

        mean_mag = float(np.mean(magnitude))
        std_mag = float(np.std(magnitude))
        p95_mag = float(np.percentile(magnitude, 95))
        residual_mean = float(np.mean(residual_map))
        residual_p95 = float(np.percentile(residual_map, 95))
        flicker_mean = float(np.mean(flicker_map))
        flow_cv = float(std_mag / (mean_mag + 1e-6))
        motion_jerk = 0.0 if previous_mean_mag is None else float(abs(mean_mag - previous_mean_mag) / (previous_mean_mag + 1e-6))
        previous_mean_mag = mean_mag

        pair_score = 100.0 * (
            0.34 * component_score(residual_mean, 0.075)
            + 0.22 * component_score(residual_p95, 0.22)
            + 0.18 * component_score(flicker_mean, 0.10)
            + 0.14 * component_score(flow_cv, 3.0)
            + 0.12 * component_score(motion_jerk, 0.75)
        )

        metrics.append(
            {
                "frame_index": frame_index,
                "time_seconds": round(frame_index / fps, 3),
                "mean_magnitude": mean_mag,
                "std_magnitude": std_mag,
                "p95_magnitude": p95_mag,
                "flow_cv": flow_cv,
                "angle_entropy": entropy_from_values(angle, bins=36, value_range=(0.0, 2.0 * math.pi)),
                "magnitude_entropy": entropy_from_values(magnitude, bins=40),
                "residual_mean": residual_mean,
                "residual_p95": residual_p95,
                "flicker_mean": flicker_mean,
                "motion_jerk": motion_jerk,
                "pair_score": pair_score,
            }
        )

        if flow_heat is None:
            flow_heat = np.zeros_like(magnitude, dtype=np.float32)
            residual_heat = np.zeros_like(residual_map, dtype=np.float32)
        flow_heat += magnitude.astype(np.float32)
        residual_heat += residual_map.astype(np.float32)

        flow_rgb = flow_to_rgb(flow)
        flow_arrows_rgb = draw_flow_arrows(frame_rgb, flow)
        residual_rgb = heatmap_rgb(residual_map)
        if config.keep_flow_gallery and len(flow_gallery) < config.flow_gallery_limit:
            flow_gallery.append(
                {
                    "sequence_index": sampled_pairs + 1,
                    "frame_index": frame_index,
                    "time_seconds": round(frame_index / fps, 3),
                    "pair_score": round(pair_score, 1),
                    "flow_rgb": flow_rgb,
                    "flow_arrows_rgb": flow_arrows_rgb,
                    "residual_rgb": residual_rgb,
                }
            )

        update_top_candidates(
            candidates,
            {
                "frame_index": frame_index,
                "time_seconds": round(frame_index / fps, 3),
                "pair_score": round(pair_score, 1),
                "frame_rgb": frame_rgb,
                "flow_rgb": flow_rgb,
                "flow_arrows_rgb": flow_arrows_rgb,
                "residual_rgb": residual_rgb,
            },
            config.candidate_count,
        )

        sampled_pairs += 1
        if config.max_pairs and sampled_pairs >= config.max_pairs:
            break

        if total_frames > 0:
            progress_value = min(1.0, frame_index / max(total_frames, 1))
        else:
            progress_value = min(1.0, sampled_pairs / max(config.max_pairs, 1))
        progress.progress(progress_value, text=f"Analyse en cours... {sampled_pairs} paire(s) de frames")
        status_box.caption(f"Dernière frame analysée : {frame_index} | temps vidéo : {frame_index / fps:.2f}s")

        previous_gray = current_gray

    capture.release()
    progress.progress(1.0, text="Analyse terminée")
    status_box.caption(f"Analyse terminée : {sampled_pairs} paire(s) de frames exploitée(s).")

    metrics_df = pd.DataFrame(metrics)
    if metrics_df.empty or sampled_pairs <= 0:
        raise RuntimeError(
            "Aucune paire de frames exploitable n'a été analysée. "
            f"Frames annoncées : {total_frames}. Frames lues réellement : {read_frames}. FPS : {fps:.2f}. "
            "Réduisez 'Analyser une frame sur', augmentez le nombre maximum de paires, "
            "ou essayez une vidéo encodée en MP4/H.264."
        )

    score = compute_global_score(metrics_df)

    heatmaps: dict[str, np.ndarray] = {}
    if flow_heat is not None and residual_heat is not None and sampled_pairs > 0:
        heatmaps["flow"] = heatmap_rgb(flow_heat / float(sampled_pairs))
        heatmaps["residual"] = heatmap_rgb(residual_heat / float(sampled_pairs))

    return {
        "metadata": {
            "fps": round(fps, 3),
            "total_frames": total_frames,
            "read_frames": read_frames,
            "duration_seconds": round(duration_seconds, 3),
            "original_width": original_width,
            "original_height": original_height,
            "sample_every_n_frames": config.sample_every_n_frames,
            "sampled_pairs": sampled_pairs,
            "algorithm": config.algorithm,
            "resize_width": config.resize_width,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "score": score,
        "metrics": metrics_df,
        "heatmaps": heatmaps,
        "candidates": candidates,
        "flow_gallery": flow_gallery,
    }


def should_retry_with_ffmpeg(error: Exception) -> bool:
    message = str(error)
    retry_markers = [
        "Aucune paire de frames exploitable",
        "Impossible d'ouvrir la vidéo avec OpenCV",
        "pas assez de frames",
    ]
    return any(marker in message for marker in retry_markers)


def analyze_video(video_path: Path, config: AnalysisConfig) -> dict[str, Any]:
    try:
        result = analyze_video_cv2(video_path, config, "fichier original")
        return attach_audio_metrics(result, video_path, "fichier original")
    except Exception as original_error:
        if not should_retry_with_ffmpeg(original_error):
            raise

        log_analysis(f"Analyse OpenCV originale insuffisante : {original_error}")
        with tempfile.TemporaryDirectory(prefix="detectia_transcode_") as transcode_dir:
            normalized_path = Path(transcode_dir) / "video_normalisee_opencv.mp4"
            transcode_for_opencv(video_path, normalized_path)
            try:
                result = analyze_video_cv2(normalized_path, config, "vidéo normalisée ffmpeg")
                return attach_audio_metrics(result, video_path, "fichier original")
            except Exception as fallback_error:
                raise RuntimeError(
                    "La vidéo reste inexploitable après conversion ffmpeg. "
                    f"Erreur initiale : {original_error}. Erreur après conversion : {fallback_error}"
                ) from fallback_error


def build_report_zip(result: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    metrics_df: pd.DataFrame = result["metrics"]
    metadata = result["metadata"]
    score = result["score"]

    report = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "metadata": metadata,
        "score": score,
        "audio": result.get("audio", {"available": False}),
        "note": "Indice heuristique d'incohérence temporelle. Ne constitue pas une preuve automatique de génération par IA.",
    }

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("rapport_detectia.json", json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr("mesures_temporelles.csv", metrics_df.to_csv(index=False))

        for name, image_rgb in result["heatmaps"].items():
            archive.writestr(f"heatmaps/{name}.png", image_to_png_bytes(image_rgb))

        for item in result.get("flow_gallery", []):
            prefix = f"optical_flow_sequence/{item['sequence_index']:04d}_t{item['time_seconds']:.2f}s"
            archive.writestr(f"{prefix}_flow.png", image_to_png_bytes(item["flow_rgb"]))
            archive.writestr(f"{prefix}_flow_fleches.png", image_to_png_bytes(item["flow_arrows_rgb"]))
            archive.writestr(f"{prefix}_residu.png", image_to_png_bytes(item["residual_rgb"]))

        for index, candidate in enumerate(result["candidates"], start=1):
            prefix = f"frames_suspectes/{index:02d}_t{candidate['time_seconds']:.2f}s"
            archive.writestr(f"{prefix}_frame.png", image_to_png_bytes(candidate["frame_rgb"]))
            archive.writestr(f"{prefix}_flow.png", image_to_png_bytes(candidate["flow_rgb"]))
            archive.writestr(f"{prefix}_flow_fleches.png", image_to_png_bytes(candidate["flow_arrows_rgb"]))
            archive.writestr(f"{prefix}_residu.png", image_to_png_bytes(candidate["residual_rgb"]))

    buffer.seek(0)
    return buffer.getvalue()


def summarize_result(result: dict[str, Any], label: str) -> dict[str, Any]:
    metrics_df: pd.DataFrame = result["metrics"]
    score = result["score"]
    audio = result.get("audio", {})
    return {
        "Source": label,
        "Score global": score.get("score"),
        "Niveau": score.get("niveau"),
        "Résidu médian": score.get("residual_median"),
        "Flicker médian": score.get("flicker_median"),
        "Instabilité flow": score.get("flow_cv_median"),
        "Jerk médian": score.get("jerk_median"),
        "Mouvement moyen": round(float(metrics_df["mean_magnitude"].median()), 4),
        "Paires analysées": result["metadata"].get("sampled_pairs"),
        "Durée vidéo": result["metadata"].get("duration_seconds"),
        "Audio disponible": "oui" if audio.get("available") else "non",
        "Silence audio": audio.get("silence_ratio"),
        "Variation énergie audio": audio.get("energy_cv"),
        "Centroïde spectral moyen": audio.get("spectral_centroid_mean"),
    }


def build_comparison_dataframe(suspect: dict[str, Any], reference: dict[str, Any]) -> pd.DataFrame:
    rows = [
        summarize_result(suspect, "Vidéo suspecte"),
        summarize_result(reference, "Vidéo de référence"),
    ]
    return pd.DataFrame(rows)


def normalized_metric_frame(result: dict[str, Any], label: str, metric_name: str) -> pd.DataFrame:
    metrics_df: pd.DataFrame = result["metrics"]
    if metrics_df.empty or metric_name not in metrics_df:
        return pd.DataFrame(columns=["progression", label])
    values = metrics_df[metric_name].astype(float).reset_index(drop=True)
    progression = np.linspace(0.0, 100.0, num=len(values))
    return pd.DataFrame({"progression": progression, label: values})


def render_normalized_comparison(
    suspect: dict[str, Any],
    reference: dict[str, Any],
    metric_name: str,
    title: str,
) -> None:
    suspect_df = normalized_metric_frame(suspect, "Vidéo suspecte", metric_name)
    reference_df = normalized_metric_frame(reference, "Vidéo de référence", metric_name)
    if suspect_df.empty or reference_df.empty:
        st.info(f"{title} : comparaison indisponible.")
        return

    merged = pd.merge_asof(
        suspect_df.sort_values("progression"),
        reference_df.sort_values("progression"),
        on="progression",
        direction="nearest",
    ).set_index("progression")
    st.markdown(f"#### {title}")
    st.line_chart(merged, use_container_width=True)


def render_audio_table(result: dict[str, Any], label: str) -> None:
    audio = result.get("audio", {})
    if not audio.get("available"):
        st.warning(f"{label} : audio indisponible - {audio.get('message', 'aucune piste exploitable')}")
        return
    rows = [
        {"Indicateur": "Durée audio", "Valeur": audio.get("duration_seconds"), "Lecture": "Durée sonore réellement extraite."},
        {"Indicateur": "Énergie moyenne", "Valeur": audio.get("rms_mean"), "Lecture": "Niveau moyen du signal audio."},
        {"Indicateur": "Variation énergie", "Valeur": audio.get("energy_cv"), "Lecture": "Instabilité relative du volume."},
        {"Indicateur": "Ratio de silence", "Valeur": audio.get("silence_ratio"), "Lecture": "Part approximative de frames audio silencieuses."},
        {"Indicateur": "Dynamique dB", "Valeur": audio.get("dynamic_range_db"), "Lecture": "Écart entre passages faibles et forts."},
        {"Indicateur": "ZCR moyen", "Valeur": audio.get("zcr_mean"), "Lecture": "Indice simple de rugosité/bruit dans le signal."},
        {"Indicateur": "Centroïde spectral", "Valeur": audio.get("spectral_centroid_mean"), "Lecture": "Centre de gravité fréquentiel moyen."},
    ]
    st.markdown(f"#### {label}")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_flow_gallery(result: dict[str, Any], title: str, key_prefix: str, page_size: int = 4) -> None:
    gallery = result.get("flow_gallery", [])
    if not gallery:
        st.warning(f"{title} : aucune image optical flow conservée.")
        return

    total_pages = max(1, math.ceil(len(gallery) / page_size))
    page = st.number_input(
        f"{title} - page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"{key_prefix}_flow_page",
    )
    start = (int(page) - 1) * page_size
    end = min(start + page_size, len(gallery))
    st.caption(f"{title} : images {start + 1} à {end} sur {len(gallery)} optical flows conservés.")

    for item in gallery[start:end]:
        st.markdown(
            f"##### #{item['sequence_index']} - t={item['time_seconds']:.2f}s - score local={item['pair_score']} / 100"
        )
        cols = st.columns(3)
        cols[0].image(item["flow_arrows_rgb"], caption="Vecteurs sur frame", use_container_width=True)
        cols[1].image(item["flow_rgb"], caption="Optical flow", use_container_width=True)
        cols[2].image(item["residual_rgb"], caption="Résidu temporel", use_container_width=True)


def build_comparison_zip(suspect: dict[str, Any], reference: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    comparison_df = build_comparison_dataframe(suspect, reference)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("comparaison_indicateurs.csv", comparison_df.to_csv(index=False))
        archive.writestr("video_suspecte/rapport_detectia.zip", build_report_zip(suspect))
        archive.writestr("video_reference/rapport_detectia.zip", build_report_zip(reference))
    buffer.seek(0)
    return buffer.getvalue()


def load_help() -> str:
    try:
        return HELP_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Aide indisponible."


st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
        .main-title {
            padding: 1rem 1.2rem;
            border-radius: 1.2rem;
            background: linear-gradient(135deg, #111827 0%, #1f2937 52%, #7c2d12 100%);
            color: white;
            margin-bottom: 1rem;
        }
        .main-title h1 { margin: 0; font-size: 2.2rem; }
        .main-title p { margin: .35rem 0 0; color: #fed7aa; }
        .warning-box {
            border-left: 5px solid #f97316;
            background: #fff7ed;
            padding: 0.9rem 1rem;
            border-radius: 0.7rem;
            color: #7c2d12;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="main-title">
        <h1>{APP_NAME}</h1>
        <p>Analyse forensique exploratoire des incohérences temporelles et du mouvement - {APP_VERSION}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Paramètres")
    uploaded_file = st.file_uploader(
        "Importer la vidéo suspecte",
        type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
        help=(
            "Charge la vidéo à examiner. Formats acceptés : MP4, MOV, MKV, AVI, WEBM, M4V. "
            "Pour un premier test, privilégie un extrait court : l'analyse optical flow peut être coûteuse."
        ),
    )
    reference_file = st.file_uploader(
        "Vidéo réelle de référence (facultatif)",
        type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
        help=(
            "Ajoute une vidéo réelle de la même personne, si possible dans un contexte proche. "
            "Elle servira de base comparative pour l'optical flow et l'audio."
        ),
    )

    st.divider()
    sample_every_n_frames = st.slider(
        "Analyser une frame sur",
        1,
        25,
        5,
        help=(
            "Définit l'échantillonnage temporel. 1 analyse presque toutes les frames et donne une analyse fine, "
            "mais lente. Une valeur plus élevée accélère le calcul, au risque de manquer des ruptures courtes."
        ),
    )
    max_pairs = st.slider(
        "Nombre maximum de paires analysées",
        20,
        600,
        160,
        step=20,
        help=(
            "Nombre maximal de paires de frames consécutives utilisées pour mesurer le mouvement. "
            "Augmenter cette valeur stabilise les indicateurs, mais augmente le temps de calcul."
        ),
    )
    resize_width = st.slider(
        "Largeur de travail",
        320,
        1280,
        640,
        step=80,
        help=(
            "Largeur, en pixels, à laquelle les frames sont redimensionnées avant analyse. "
            "Une largeur faible est plus rapide ; une largeur élevée conserve davantage de détails visuels."
        ),
    )
    algorithm = st.selectbox(
        "Méthode optical flow",
        ["Farneback robuste", "DIS rapide"],
        index=0,
        help=(
            "Farneback robuste est plus stable pour l'analyse exploratoire, mais plus lent. "
            "DIS rapide accélère le calcul et convient aux pré-tests ou aux vidéos longues."
        ),
    )
    candidate_count = st.slider(
        "Frames suspectes à conserver",
        3,
        12,
        6,
        help=(
            "Nombre de moments considérés comme les plus suspects à afficher et exporter. "
            "Ces frames sont sélectionnées selon les signaux de résidu, flicker et rupture de mouvement."
        ),
    )
    keep_flow_gallery = st.checkbox(
        "Afficher/exporter les optical flows analysés",
        value=True,
        help=(
            "Conserve les images optical flow des paires analysées afin de les afficher et de les exporter. "
            "Un plafond est appliqué pour protéger la mémoire du VPS."
        ),
    )
    flow_gallery_limit = st.slider(
        "Nombre maximum d'optical flows conservés",
        20,
        300,
        120,
        step=20,
        help="Nombre maximal d'images optical flow conservées pour l'affichage et l'export ZIP.",
        disabled=not keep_flow_gallery,
    )

    st.divider()
    with st.expander("Aide", expanded=False):
        st.markdown(load_help())

st.markdown(
    """
    <div class="warning-box">
        <strong>Important :</strong> DetectIA ne donne pas une preuve automatique.
        L'application produit un indice d'incohérence temporelle pour aider une enquête fake news :
        compression, montage, ralenti, stabilisation ou mauvaise qualité peuvent aussi produire des signaux suspects.
    </div>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("analysis_result", None)
st.session_state.setdefault("reference_result", None)
st.session_state.setdefault("analysis_error", "")
st.session_state.setdefault("reference_error", "")
st.session_state.setdefault("analysis_log", [])

if uploaded_file is None:
    st.info("Importe une vidéo suspecte dans la colonne de gauche pour lancer l'analyse.")
    st.stop()

video_bytes = uploaded_file.getvalue()
reference_bytes = reference_file.getvalue() if reference_file is not None else None

if reference_bytes is None:
    st.markdown("### Vidéo suspecte")
    st.video(video_bytes)
else:
    preview_cols = st.columns(2)
    with preview_cols[0]:
        st.markdown("### Vidéo suspecte")
        st.video(video_bytes)
    with preview_cols[1]:
        st.markdown("### Vidéo réelle de référence")
        st.video(reference_bytes)

config = AnalysisConfig(
    sample_every_n_frames=int(sample_every_n_frames),
    max_pairs=int(max_pairs),
    resize_width=int(resize_width),
    algorithm=algorithm,
    candidate_count=int(candidate_count),
    keep_flow_gallery=bool(keep_flow_gallery),
    flow_gallery_limit=int(flow_gallery_limit),
)

if st.button("Lancer l'analyse DetectIA", type="primary", use_container_width=True):
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    st.session_state.analysis_result = None
    st.session_state.reference_result = None
    st.session_state.analysis_error = ""
    st.session_state.reference_error = ""
    st.session_state.analysis_log = []
    log_analysis(f"Build application : {APP_BUILD}")
    log_analysis(
        f"Vidéo suspecte reçue : {uploaded_file.name} | taille={len(video_bytes) / (1024 * 1024):.1f} Mo | "
        f"sample_every={config.sample_every_n_frames} | max_pairs={config.max_pairs} | "
        f"resize_width={config.resize_width} | algorithm={config.algorithm} | "
        f"flow_gallery={config.keep_flow_gallery} | flow_gallery_limit={config.flow_gallery_limit}"
    )
    with tempfile.TemporaryDirectory(prefix="detectia_") as tmpdir:
        temp_path = Path(tmpdir) / f"video_source{suffix}"
        temp_path.write_bytes(video_bytes)
        log_analysis(f"Vidéo suspecte temporaire écrite : {temp_path.name} ({temp_path.stat().st_size} octets)")
        try:
            with st.spinner("Analyse DetectIA de la vidéo suspecte en cours..."):
                st.session_state.analysis_result = analyze_video(temp_path, config)
            metadata_done = st.session_state.analysis_result["metadata"]
            log_analysis(
                f"Analyse suspecte terminée : {metadata_done['sampled_pairs']} paire(s), "
                f"durée={metadata_done['duration_seconds']}s, fps={metadata_done['fps']}"
            )
        except Exception as exc:
            st.session_state.analysis_result = None
            st.session_state.analysis_error = str(exc) or repr(exc)
            log_analysis(f"Erreur pendant l'analyse suspecte : {st.session_state.analysis_error}")
            st.error(f"Erreur pendant l'analyse suspecte : {st.session_state.analysis_error}")
            render_analysis_log(expanded=True)

        if reference_bytes is not None and st.session_state.analysis_result is not None:
            reference_suffix = Path(reference_file.name).suffix or ".mp4"
            reference_path = Path(tmpdir) / f"video_reference{reference_suffix}"
            reference_path.write_bytes(reference_bytes)
            log_analysis(
                f"Vidéo de référence reçue : {reference_file.name} | "
                f"taille={len(reference_bytes) / (1024 * 1024):.1f} Mo"
            )
            try:
                with st.spinner("Analyse DetectIA de la vidéo de référence en cours..."):
                    st.session_state.reference_result = analyze_video(reference_path, config)
                reference_metadata = st.session_state.reference_result["metadata"]
                log_analysis(
                    f"Analyse référence terminée : {reference_metadata['sampled_pairs']} paire(s), "
                    f"durée={reference_metadata['duration_seconds']}s, fps={reference_metadata['fps']}"
                )
            except Exception as exc:
                st.session_state.reference_result = None
                st.session_state.reference_error = str(exc) or repr(exc)
                log_analysis(f"Erreur pendant l'analyse référence : {st.session_state.reference_error}")
                st.warning(f"Analyse de référence indisponible : {st.session_state.reference_error}")

result = st.session_state.analysis_result
if result is None:
    if st.session_state.get("analysis_error"):
        st.warning("Aucun résultat n'a été produit pour cette analyse.")
        render_analysis_log(expanded=True)
    st.stop()

render_analysis_log(expanded=False)

reference_result = st.session_state.reference_result
metadata = result["metadata"]
score = result["score"]
metrics_df: pd.DataFrame = result["metrics"]

tab_summary, tab_comparison, tab_temporal, tab_flow, tab_gallery, tab_audio, tab_candidates, tab_export = st.tabs(
    [
        "Synthèse",
        "Comparaison",
        "Temporalité",
        "Optical flow",
        "Galerie optical flow",
        "Audio",
        "Frames suspectes",
        "Rapport",
    ]
)

with tab_summary:
    col_score, col_meta = st.columns([1, 2])
    with col_score:
        st.metric("Indice de suspicion", f"{score['score']} / 100", score["niveau"])
        st.write(score["interpretation"])
    with col_meta:
        meta_cols = st.columns(5)
        meta_cols[0].metric("FPS", metadata["fps"])
        meta_cols[1].metric("Durée", f"{metadata['duration_seconds']:.1f}s")
        meta_cols[2].metric("Frames annoncées", metadata["total_frames"])
        meta_cols[3].metric("Frames lues", metadata.get("read_frames", metadata["total_frames"]))
        meta_cols[4].metric("Paires analysées", metadata["sampled_pairs"])

    st.markdown("#### Lecture rapide")
    st.write(
        "Un score élevé signifie que les mouvements ou les résidus entre frames sont atypiques. "
        "Il faut ensuite vérifier les frames suspectes, la qualité d'encodage, le montage et la source."
    )

    st.dataframe(
        pd.DataFrame(
            [
                {"Indicateur": "Résidu médian", "Valeur": score.get("residual_median")},
                {"Indicateur": "Résidu p95", "Valeur": score.get("residual_p95")},
                {"Indicateur": "Flicker médian", "Valeur": score.get("flicker_median")},
                {"Indicateur": "Instabilité du flow", "Valeur": score.get("flow_cv_median")},
                {"Indicateur": "Jerk médian", "Valeur": score.get("jerk_median")},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

with tab_comparison:
    if reference_result is None:
        st.info(
            "Ajoute une vidéo réelle de référence dans la colonne de gauche pour comparer la vidéo suspecte "
            "avec un comportement visuel et sonore de la même personne."
        )
        if st.session_state.get("reference_error"):
            st.warning(f"Dernière erreur référence : {st.session_state.reference_error}")
    else:
        st.markdown("### Comparaison suspect / référence")
        comparison_df = build_comparison_dataframe(result, reference_result)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

        render_normalized_comparison(result, reference_result, "pair_score", "Score local normalisé")
        render_normalized_comparison(result, reference_result, "residual_mean", "Résidu temporel moyen")
        render_normalized_comparison(result, reference_result, "mean_magnitude", "Intensité du mouvement")
        render_normalized_comparison(result, reference_result, "flicker_mean", "Flicker moyen")

        st.caption(
            "Les courbes sont ramenées sur une progression 0-100 % pour comparer deux vidéos de durée différente. "
            "L'objectif n'est pas une preuve automatique, mais une lecture comparative des ruptures de mouvement."
        )

with tab_temporal:
    if metrics_df.empty:
        st.warning("Pas assez de frames pour afficher les courbes.")
    else:
        chart_df = metrics_df.set_index("time_seconds")
        st.markdown("#### Score de suspicion par instant")
        st.line_chart(chart_df["pair_score"], use_container_width=True)
        st.markdown("#### Résidu de reconstruction")
        st.line_chart(chart_df[["residual_mean", "residual_p95"]], use_container_width=True)
        st.markdown("#### Mouvement apparent")
        st.line_chart(chart_df[["mean_magnitude", "p95_magnitude"]], use_container_width=True)
        st.markdown("#### Flicker et jerk")
        st.line_chart(chart_df[["flicker_mean", "motion_jerk"]], use_container_width=True)

with tab_flow:
    heatmaps = result["heatmaps"]
    if not heatmaps:
        st.warning("Aucune heatmap disponible.")
    else:
        col_flow, col_residual = st.columns(2)
        with col_flow:
            st.markdown("#### Intensité moyenne du mouvement")
            st.image(heatmaps["flow"], use_container_width=True)
        with col_residual:
            st.markdown("#### Résidus après compensation du mouvement")
            st.image(heatmaps["residual"], use_container_width=True)
        st.caption(
            "La heatmap de résidu montre les zones qui restent incohérentes même après estimation du mouvement."
        )

with tab_gallery:
    if reference_result is None:
        render_flow_gallery(result, "Vidéo suspecte", "suspect")
    else:
        st.markdown("### Optical flow comparatif")
        gallery_cols = st.columns(2)
        with gallery_cols[0]:
            render_flow_gallery(result, "Vidéo suspecte", "suspect")
        with gallery_cols[1]:
            render_flow_gallery(reference_result, "Vidéo de référence", "reference")

with tab_audio:
    if reference_result is None:
        render_audio_table(result, "Vidéo suspecte")
    else:
        audio_cols = st.columns(2)
        with audio_cols[0]:
            render_audio_table(result, "Vidéo suspecte")
        with audio_cols[1]:
            render_audio_table(reference_result, "Vidéo de référence")
        st.caption(
            "Les indicateurs audio restent exploratoires : ils servent à repérer des écarts de dynamique, "
            "de silence, de rugosité ou de centre fréquentiel entre deux sources."
        )

with tab_candidates:
    candidates = result["candidates"]
    if not candidates:
        st.warning("Aucune frame suspecte disponible.")
    for candidate in candidates:
        st.markdown(
            f"### t = {candidate['time_seconds']:.2f}s | score local = {candidate['pair_score']} / 100"
        )
        view_cols = st.columns(4)
        view_cols[0].image(candidate["frame_rgb"], caption="Frame", use_container_width=True)
        view_cols[1].image(candidate["flow_arrows_rgb"], caption="Vecteurs de mouvement", use_container_width=True)
        view_cols[2].image(candidate["flow_rgb"], caption="Direction / magnitude", use_container_width=True)
        view_cols[3].image(candidate["residual_rgb"], caption="Résidu temporel", use_container_width=True)

with tab_export:
    st.markdown("### Exporter l'analyse")
    if reference_result is not None:
        st.download_button(
            "Télécharger la comparaison complète ZIP",
            data=build_comparison_zip(result, reference_result),
            file_name=f"detectia_comparaison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
        )
    st.download_button(
        "Télécharger le rapport vidéo suspecte ZIP",
        data=build_report_zip(result),
        file_name=f"detectia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        use_container_width=True,
    )
    if reference_result is not None:
        st.download_button(
            "Télécharger le rapport vidéo de référence ZIP",
            data=build_report_zip(reference_result),
            file_name=f"detectia_reference_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
        )
    st.download_button(
        "Télécharger les mesures suspectes CSV",
        data=metrics_df.to_csv(index=False).encode("utf-8"),
        file_name="detectia_mesures_temporelles.csv",
        mime="text/csv",
        use_container_width=True,
    )
    if reference_result is not None:
        reference_metrics: pd.DataFrame = reference_result["metrics"]
        st.download_button(
            "Télécharger les mesures référence CSV",
            data=reference_metrics.to_csv(index=False).encode("utf-8"),
            file_name="detectia_mesures_reference.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.json({"metadata": metadata, "score": score})
