from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any
import sys
import re

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import (
    VIDEO_EXTENSIONS,
    clip_video_interval,
    ensure_directory,
    ensure_video_mp4,
    extract_audio_mp3,
    extract_audio_wav,
    extract_video_frames,
    is_youtube_url,
    probe_duration_seconds,
    resolve_media_source,
    utc_session_id,
    write_json,
    write_jsonl,
)
from multimodale.timeline import build_timeline_payload
from multimodale.visualisations import altair_available, configure_chart, save_chart


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("", encoding="utf-8")
        return

    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def project_rows(rows: list[dict[str, Any]], preferred_columns: list[str]) -> list[dict[str, Any]]:
    if not rows:
        return []

    available_columns: set[str] = set()
    for row in rows:
        available_columns.update(row.keys())
    selected_columns = [column for column in preferred_columns if column in available_columns]
    return [{column: row.get(column, "") for column in selected_columns} for row in rows]


def write_csv_variants(path: str | Path, rows: list[dict[str, Any]], essential_columns: list[str]) -> tuple[str, str, str]:
    destination = Path(path)
    legacy_path = destination
    complete_path = destination.with_name(f"{destination.stem}_complet{destination.suffix}")
    essential_path = destination.with_name(f"{destination.stem}_essentiel{destination.suffix}")
    essential_rows = project_rows(rows, essential_columns)
    write_csv(legacy_path, rows)
    write_csv(complete_path, rows)
    write_csv(essential_path, essential_rows)
    return (str(legacy_path), str(complete_path), str(essential_path))


ALIGNEMENT_SEGMENTS_ESSENTIAL_COLUMNS = [
    "segment_id",
    "start_sec",
    "end_sec",
    "timestamp_sync",
    "text",
    "frame_count_sync",
    "first_frame_id_sync",
    "last_frame_id_sync",
    "nearest_frame_id_sync",
    "nearest_frame_time_sec_sync",
    "nearest_frame_path_sync",
    "motion_mean_sync",
    "direction_label_sync",
    "roi_directional_entropy_sync",
    "roi_directional_entropy_norm_sync",
    "roi_motion_energy_sync",
    "anomalie_audio_sync",
]


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def normalize_path_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser().resolve()).replace("\\", "/").lower()
    except Exception:
        return text.replace("\\", "/").lower()


def natural_sort_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.lower())
    key: list[Any] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return key


def list_frame_paths(frames_dir: str | Path) -> list[Path]:
    directory = Path(frames_dir).expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=natural_sort_key,
    )


def build_frames_index(
    frames_dir: str | Path,
    fps_value: float,
    start_sec: float | None = None,
) -> list[dict[str, Any]]:
    base_start = float(start_sec or 0.0)
    frame_paths = list_frame_paths(frames_dir)
    rows: list[dict[str, Any]] = []
    for index, frame_path in enumerate(frame_paths):
        time_sec = base_start + (index / fps_value)
        rows.append(
            {
                "frame_id": index + 1,
                "time_sec": round(time_sec, 6),
                "frame_path": str(frame_path.resolve()),
            }
        )
    return rows


def build_frames_index_from_motion_rows(motion_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    indexed_rows: list[dict[str, Any]] = []
    for position, row in enumerate(motion_rows, start=1):
        time_sec = safe_float(row.get("time_sec"))
        if time_sec is None:
            continue
        frame_id = safe_float(row.get("frame_index"))
        frame_path = str(row.get("image_path") or row.get("frame_preview_path") or "").strip()
        if not frame_path:
            continue
        indexed_rows.append(
            {
                "frame_id": int(frame_id) if frame_id is not None else position,
                "time_sec": round(time_sec, 6),
                "frame_path": frame_path,
            }
        )

    indexed_rows.sort(key=lambda item: (float(item.get("time_sec", 0.0)), int(item.get("frame_id", 0))))
    return indexed_rows


def align_segments_with_frames(
    segments_rows: list[dict[str, str]],
    frame_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aligned_rows: list[dict[str, Any]] = []

    for segment in segments_rows:
        start_sec = safe_float(segment.get("start_sec")) or 0.0
        end_sec = safe_float(segment.get("end_sec")) or start_sec
        midpoint = (start_sec + end_sec) / 2.0

        matched_frames = [
            frame for frame in frame_rows
            if start_sec <= float(frame.get("time_sec", 0.0)) <= end_sec
        ]
        nearest_frame = min(
            frame_rows,
            key=lambda frame: abs(float(frame.get("time_sec", 0.0)) - midpoint),
        ) if frame_rows else None
        aligned_rows.append(
            {
                **segment,
                "timestamp_sync": round(midpoint, 6),
                "frame_count_sync": len(matched_frames),
                "first_frame_id_sync": matched_frames[0]["frame_id"] if matched_frames else "",
                "first_frame_path_sync": matched_frames[0]["frame_path"] if matched_frames else "",
                "last_frame_id_sync": matched_frames[-1]["frame_id"] if matched_frames else "",
                "last_frame_path_sync": matched_frames[-1]["frame_path"] if matched_frames else "",
                "nearest_frame_id_sync": nearest_frame["frame_id"] if nearest_frame else "",
                "nearest_frame_path_sync": nearest_frame["frame_path"] if nearest_frame else "",
                "nearest_frame_time_sec_sync": round(float(nearest_frame["time_sec"]), 6) if nearest_frame else "",
            }
        )

    return aligned_rows


def enrich_alignment_with_motion_metrics(
    aligned_rows: list[dict[str, Any]],
    motion_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not aligned_rows or not motion_rows:
        return aligned_rows

    metrics_to_copy = [
        "motion_mean",
        "motion_peak_p95",
        "motion_active_ratio",
        "direction_label",
        "roi_flow_mean",
        "roi_active_ratio",
        "roi_motion_energy",
        "roi_directional_entropy",
        "roi_directional_entropy_norm",
        "anatomy_mode",
        "anatomy_backend",
        "mouth_opening",
        "left_eye_opening",
        "right_eye_opening",
        "left_right_asymmetry",
        "mouth_motion_energy",
        "eyes_motion_energy",
        "brows_motion_energy",
        "body_center_displacement",
        "head_motion_energy",
        "torso_motion_energy",
        "left_arm_motion_energy",
        "right_arm_motion_energy",
    ]

    motion_by_path: dict[str, dict[str, str]] = {}
    motion_by_frame_id: dict[int, dict[str, str]] = {}
    for row in motion_rows:
        image_path = normalize_path_key(row.get("image_path"))
        if image_path and image_path not in motion_by_path:
            motion_by_path[image_path] = row
        frame_preview_path = normalize_path_key(row.get("frame_preview_path"))
        if frame_preview_path and frame_preview_path not in motion_by_path:
            motion_by_path[frame_preview_path] = row
        try:
            frame_index = int(float(row.get("frame_index", "") or 0))
        except Exception:
            frame_index = 0
        if frame_index > 0 and frame_index not in motion_by_frame_id:
            motion_by_frame_id[frame_index] = row

    enriched_rows: list[dict[str, Any]] = []
    for row in aligned_rows:
        matched_motion = None
        nearest_path = normalize_path_key(row.get("nearest_frame_path_sync"))
        if nearest_path:
            matched_motion = motion_by_path.get(nearest_path)

        if matched_motion is None:
            nearest_frame_id = safe_float(row.get("nearest_frame_id_sync"))
            if nearest_frame_id is not None:
                matched_motion = motion_by_frame_id.get(int(nearest_frame_id))

        enriched = dict(row)
        for metric in metrics_to_copy:
            enriched[f"{metric}_sync"] = matched_motion.get(metric, "") if matched_motion else ""
        enriched_rows.append(enriched)

    return enriched_rows


def enrich_alignment_with_audio_anomalies(
    aligned_rows: list[dict[str, Any]],
    anomaly_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not aligned_rows or not anomaly_rows:
        return aligned_rows

    parsed_anomalies = []
    for row in anomaly_rows:
        start_sec = safe_float(row.get("start_sec"))
        end_sec = safe_float(row.get("end_sec"))
        if start_sec is None or end_sec is None:
            continue
        parsed_anomalies.append(
            {
                "window_id": row.get("window_id", ""),
                "start_sec": start_sec,
                "end_sec": end_sec,
                "time_sec": safe_float(row.get("time_sec")),
                "mean_amp": row.get("mean_amp", ""),
                "z_score": row.get("z_score", ""),
                "anomaly_flag": str(row.get("anomaly_flag", "")).strip().lower() == "oui",
            }
        )

    if not parsed_anomalies:
        return aligned_rows

    enriched_rows: list[dict[str, Any]] = []
    for row in aligned_rows:
        enriched = dict(row)
        timestamp_sync = safe_float(row.get("timestamp_sync"))
        if timestamp_sync is None:
            timestamp_sync = safe_float(row.get("nearest_frame_time_sec_sync"))
        if timestamp_sync is None:
            start_sec = safe_float(row.get("start_sec")) or 0.0
            end_sec = safe_float(row.get("end_sec")) or start_sec
            timestamp_sync = (start_sec + end_sec) / 2.0

        timestamp_anomalies = [
            anomaly for anomaly in parsed_anomalies
            if anomaly["anomaly_flag"] and anomaly["start_sec"] <= timestamp_sync <= anomaly["end_sec"]
        ]

        enriched.update(
            {
                "anomalie_audio_sync": "oui" if timestamp_anomalies else "non",
            }
        )
        enriched_rows.append(enriched)

    return enriched_rows


def build_alignment_altair_chart(aligned_rows: list[dict[str, Any]], output_path: str | Path) -> str:
    if not aligned_rows or not altair_available():
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    rows = []
    for row in aligned_rows:
        rows.append(
            {
                "segment_id": int(row.get("segment_id", 0) or 0),
                "start_sec": float(row.get("start_sec", 0.0) or 0.0),
                "end_sec": float(row.get("end_sec", 0.0) or 0.0),
                "frame_count_sync": int(row.get("frame_count_sync", 0) or 0),
                "nearest_frame_time_sec_sync": float(row.get("nearest_frame_time_sec_sync", 0.0) or 0.0),
                "text": str(row.get("text", "") or ""),
            }
        )

    base = alt.Chart(alt.Data(values=rows)).encode(
        x=alt.X("start_sec:Q", title="Temps du segment (s)")
    )

    counts = base.mark_bar(color="#5b7c99", opacity=0.8).encode(
        y=alt.Y("frame_count_sync:Q", title="Nombre d'images dans le segment"),
        tooltip=[
            alt.Tooltip("segment_id:Q", title="Segment"),
            alt.Tooltip("start_sec:Q", title="Début (s)", format=".2f"),
            alt.Tooltip("end_sec:Q", title="Fin (s)", format=".2f"),
            alt.Tooltip("frame_count_sync:Q", title="Images"),
            alt.Tooltip("text:N", title="Texte"),
        ],
    ).properties(height=220)

    nearest = base.mark_circle(color="#b33a3a", size=90).encode(
        y=alt.Y("nearest_frame_time_sec_sync:Q", title="Temps de l'image la plus proche (s)"),
        tooltip=[
            alt.Tooltip("segment_id:Q", title="Segment"),
            alt.Tooltip("nearest_frame_time_sec_sync:Q", title="Image la plus proche (s)", format=".2f"),
            alt.Tooltip("text:N", title="Texte"),
        ],
    ).properties(height=220)

    chart = configure_chart(
        alt.vconcat(counts, nearest).resolve_scale(x="shared"),
        "Alignement images ↔ segments",
    )
    return save_chart(chart, output_path)


def extraire_et_aligner(
    source: str,
    output_dir: str | Path,
    fps_value: float = 1.0,
    start_sec: float | None = None,
    end_sec: float | None = None,
    quality: str = "low",
    segments_csv: str | None = None,
    cookies_path: str | None = None,
    extract_mp4: bool = True,
    extract_mp3: bool = True,
    extract_wav: bool = False,
    extract_frames: bool = True,
    overlay_images: bool = True,
    overlay_segments: bool = True,
    overlay_audio: bool = False,
    motion_frames_csv: str | None = None,
    audio_anomalies_csv: str | None = None,
    audio_pauses_csv: str | None = None,
) -> dict[str, Any]:
    """
    Extrait des images à cadence fixe puis aligne ces images avec les segments textuels
    lorsqu'un CSV de transcription est fourni.
    """
    destination = ensure_directory(output_dir)
    session_id = utc_session_id("alignement")
    local_source = Path(source).expanduser()
    source_is_images_dir = local_source.exists() and local_source.is_dir()

    raw_source_path: Path
    source_path: Path | None = None
    audio_mp3_path: Path | None = None
    audio_wav_path: Path | None = None
    frames_dir: Path | None = None

    if source_is_images_dir:
        raw_source_path = local_source.resolve()
        frame_rows = build_frames_index(raw_source_path, fps_value=fps_value, start_sec=start_sec or 0.0)
        if not frame_rows:
            raise ValueError("Le dossier d'images sélectionné ne contient aucune image exploitable pour l'alignement.")
        write_csv(destination / "frames_index.csv", frame_rows)
        write_jsonl(destination / "frames_index.jsonl", frame_rows)
    else:
        raw_source_path = resolve_media_source(
            source,
            output_dir=destination / "downloads",
            prefer="video",
            cookies_path=cookies_path,
            start_sec=start_sec if is_youtube_url(source) else None,
            end_sec=end_sec if is_youtube_url(source) else None,
        )

        if raw_source_path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError("La source d'alignement doit être une séquence d'images, une vidéo locale ou une URL YouTube.")

        if not any([extract_mp4, extract_mp3, extract_wav, extract_frames, bool(segments_csv)]):
            extract_mp4 = True
            extract_mp3 = True
            extract_frames = True

        working_dir = destination / ("downloads" if extract_mp4 else "tmp")
        source_path = ensure_video_mp4(
            source_path=raw_source_path,
            output_dir=working_dir,
        )
        if not is_youtube_url(source) and (start_sec is not None or end_sec is not None):
            source_path = clip_video_interval(
                source_path=source_path,
                output_dir=working_dir,
                start_sec=start_sec,
                end_sec=end_sec,
            )
        audio_mp3_path = (
            extract_audio_mp3(
                source_path=source_path,
                output_dir=destination / "audio",
            )
            if extract_mp3
            else None
        )
        audio_wav_path = (
            extract_audio_wav(
                source_path=source_path,
                output_dir=destination / "audio",
            )
            if extract_wav
            else None
        )

        frame_rows = []
        if extract_frames or segments_csv:
            frames_dir = extract_video_frames(
                source_path=source_path,
                output_dir=destination / "frames",
                fps_value=fps_value,
                start_sec=None,
                end_sec=None,
                quality=quality,
            )
            frame_rows = build_frames_index(frames_dir, fps_value=fps_value, start_sec=0.0)
            write_csv(destination / "frames_index.csv", frame_rows)
            write_jsonl(destination / "frames_index.jsonl", frame_rows)

    aligned_rows: list[dict[str, Any]] = []
    alignment_frame_rows: list[dict[str, Any]] = []
    motion_rows: list[dict[str, str]] = []
    anomaly_rows: list[dict[str, str]] = []
    pause_rows: list[dict[str, str]] = []
    segments_images_alignement_csv = ""
    segments_images_alignement_csv_complet = ""
    segments_images_alignement_csv_essentiel = ""
    segments_texte_sync_csv = ""
    segments_texte_sync_csv_complet = ""
    segments_texte_sync_csv_essentiel = ""

    if not audio_pauses_csv and segments_csv:
        segments_parent = Path(segments_csv).expanduser().resolve().parent
        for candidate_name in ("audio_pauses_complet.csv", "audio_pauses.csv"):
            candidate = segments_parent / candidate_name
            if candidate.exists():
                audio_pauses_csv = str(candidate)
                break

    if segments_csv and (frame_rows or motion_frames_csv):
        if motion_frames_csv:
            motion_rows = read_csv_rows(motion_frames_csv)
            alignment_frame_rows = build_frames_index_from_motion_rows(motion_rows)
        if not alignment_frame_rows:
            alignment_frame_rows = frame_rows

        segment_rows = read_csv_rows(segments_csv)
        aligned_rows = align_segments_with_frames(segment_rows, alignment_frame_rows)
        if motion_rows:
            aligned_rows = enrich_alignment_with_motion_metrics(aligned_rows, motion_rows)
        if audio_anomalies_csv:
            anomaly_rows = read_csv_rows(audio_anomalies_csv)
            aligned_rows = enrich_alignment_with_audio_anomalies(aligned_rows, anomaly_rows)
        if audio_pauses_csv:
            pause_rows = read_csv_rows(audio_pauses_csv)
        (
            segments_images_alignement_csv,
            segments_images_alignement_csv_complet,
            segments_images_alignement_csv_essentiel,
        ) = write_csv_variants(
            destination / "segments_images_alignement.csv",
            aligned_rows,
            ALIGNEMENT_SEGMENTS_ESSENTIAL_COLUMNS,
        )
        write_jsonl(destination / "segments_images_alignement.jsonl", aligned_rows)
        (
            segments_texte_sync_csv,
            segments_texte_sync_csv_complet,
            segments_texte_sync_csv_essentiel,
        ) = write_csv_variants(
            destination / "segments_texte_sync.csv",
            aligned_rows,
            ALIGNEMENT_SEGMENTS_ESSENTIAL_COLUMNS,
        )
        write_jsonl(destination / "segments_texte_sync.jsonl", aligned_rows)
    chart_path = build_alignment_altair_chart(aligned_rows, destination / "alignement_segments_altair.html")
    timeline_payload = build_timeline_payload(aligned_rows, motion_rows, anomaly_rows, pause_rows)
    timeline_json_path = destination / "timeline_multimodale.json"
    write_json(timeline_json_path, timeline_payload)

    summary = {
        "session_id": session_id,
        "source": source,
        "source_resolved": str(raw_source_path),
        "source_video_mp4": str(source_path) if source_path and extract_mp4 else "",
        "source_frames_dir": str(raw_source_path) if source_is_images_dir else str(frames_dir) if frames_dir else "",
        "source_audio_mp3": str(audio_mp3_path) if audio_mp3_path else "",
        "source_audio_wav": str(audio_wav_path) if audio_wav_path else "",
        "cookies_path": cookies_path,
        "fps_value": fps_value,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "quality": quality,
        "video_duration_sec": probe_duration_seconds(source_path) if source_path else None,
        "frame_count": len(frame_rows),
        "segments_count": len(aligned_rows) if aligned_rows else 0,
        "segments_csv": segments_csv or "",
        "requested_outputs": {
            "mp4": extract_mp4,
            "mp3": extract_mp3,
            "wav": extract_wav,
            "frames": extract_frames,
        },
        "requested_overlays": {
            "images": overlay_images,
            "segments": overlay_segments,
            "audio": overlay_audio,
        },
        "alignement_reference": "mouvements_frames.csv" if alignment_frame_rows and motion_rows else "frames_index.csv",
        "motion_frames_csv": motion_frames_csv or "",
        "audio_anomalies_csv": audio_anomalies_csv or "",
        "audio_pauses_csv": audio_pauses_csv or "",
        "chart_html": chart_path,
        "timeline_json": str(timeline_json_path),
        "propositions_alignement": {
            "frame_count_sync": "Nombre d'images qui tombent à l'intérieur du segment transcrit.",
            "first_frame_id_sync": "Numéro de la première image synchronisée dans le segment.",
            "nearest_frame_path_sync": "Image la plus proche du centre temporel du segment.",
            "nearest_frame_id_sync": "Numéro de l'image la plus proche du centre temporel du segment.",
            "nearest_frame_time_sec_sync": "Horodatage de l'image la plus proche du segment.",
            "motion_mean_sync": "Optical flow moyen de l'image synchronisée la plus proche.",
            "motion_peak_p95_sync": "Magnitude p95 de l'image synchronisée la plus proche.",
            "roi_directional_entropy_sync": "Entropie directionnelle de l'image synchronisée la plus proche.",
            "roi_directional_entropy_norm_sync": "Entropie directionnelle normalisée (0-1) de l'image synchronisée la plus proche.",
            "roi_motion_energy_sync": "Énergie de mouvement ROI de l'image synchronisée la plus proche.",
            "timestamp_sync": "Horodatage de référence commun utilisé pour synchroniser texte, image et audio. Si mouvements_frames.csv est fourni, ce sont ses timestamps qui servent de référence visuelle.",
            "anomalie_audio_sync": "Indique si ce timestamp synchronisé tombe dans une anomalie audio.",
        },
    }

    write_json(destination / "alignement_summary.json", summary)

    return {
        "session_id": session_id,
        "frames_index_csv": str(destination / "frames_index.csv") if frame_rows else "",
        "frames_index_jsonl": str(destination / "frames_index.jsonl") if frame_rows else "",
        "source_video_mp4": str(source_path) if source_path and extract_mp4 else "",
        "source_frames_dir": str(raw_source_path) if source_is_images_dir else str(frames_dir) if frames_dir else "",
        "source_audio_mp3": str(audio_mp3_path) if audio_mp3_path else "",
        "source_audio_wav": str(audio_wav_path) if audio_wav_path else "",
        "segments_images_alignement_csv": segments_images_alignement_csv if aligned_rows else "",
        "segments_images_alignement_csv_complet": segments_images_alignement_csv_complet if aligned_rows else "",
        "segments_images_alignement_csv_essentiel": segments_images_alignement_csv_essentiel if aligned_rows else "",
        "segments_images_alignement_jsonl": str(destination / "segments_images_alignement.jsonl") if aligned_rows else "",
        "segments_texte_sync_csv": segments_texte_sync_csv if aligned_rows else "",
        "segments_texte_sync_csv_complet": segments_texte_sync_csv_complet if aligned_rows else "",
        "segments_texte_sync_csv_essentiel": segments_texte_sync_csv_essentiel if aligned_rows else "",
        "segments_texte_sync_jsonl": str(destination / "segments_texte_sync.jsonl") if aligned_rows else "",
        "chart_html": str(chart_path),
        "timeline_json": str(timeline_json_path),
        "summary_json": str(destination / "alignement_summary.json"),
        "frame_count": len(frame_rows),
        "segment_count": len(aligned_rows),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extraction d'images vidéo ou usage d'une séquence d'images, puis alignement avec des segments textuels horodatés."
    )
    parser.add_argument("--source", required=True, help="Séquence d'images, vidéo locale ou URL YouTube.")
    parser.add_argument("--output-dir", default="multimodale/exports/alignement", help="Dossier d'export.")
    parser.add_argument("--fps", type=float, default=1.0, help="Cadence d'extraction : 1 ou 25 images par seconde.")
    parser.add_argument("--start-sec", type=float, default=None, help="Début de l'intervalle à extraire.")
    parser.add_argument("--end-sec", type=float, default=None, help="Fin de l'intervalle à extraire.")
    parser.add_argument("--quality", choices=["low", "high"], default="low", help="Qualité d'extraction des images.")
    parser.add_argument("--segments-csv", default="", help="CSV de transcription produit par multimodale/audio.py.")
    parser.add_argument("--cookies", default="", help="Chemin vers un fichier cookies.txt ou .cookies.")
    parser.add_argument("--extract-mp4", action="store_true", help="Prépare une vidéo MP4 locale.")
    parser.add_argument("--extract-mp3", action="store_true", help="Extrait une piste MP3.")
    parser.add_argument("--extract-wav", action="store_true", help="Extrait une piste WAV.")
    parser.add_argument("--extract-frames", action="store_true", help="Extrait les images et leur index temporel.")
    parser.add_argument("--overlay-images", action="store_true", help="Active la superposition des images.")
    parser.add_argument("--overlay-segments", action="store_true", help="Active la superposition des segments.")
    parser.add_argument("--overlay-audio", action="store_true", help="Active la superposition des indicateurs audio.")
    parser.add_argument("--motion-frames-csv", default="", help="CSV produit par multimodale/mouvements.py pour projeter les scores de mouvement dans l'alignement.")
    parser.add_argument("--audio-anomalies-csv", default="", help="CSV produit par multimodale/audio.py pour projeter les anomalies audio dans l'alignement.")
    parser.add_argument("--audio-pauses-csv", default="", help="CSV produit par multimodale/audio.py pour projeter les silences réels dans l'alignement.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    result = extraire_et_aligner(
        source=args.source,
        output_dir=args.output_dir,
        fps_value=args.fps,
        start_sec=args.start_sec,
        end_sec=args.end_sec,
        quality=args.quality,
        segments_csv=args.segments_csv or None,
        cookies_path=args.cookies or None,
        extract_mp4=args.extract_mp4,
        extract_mp3=args.extract_mp3,
        extract_wav=args.extract_wav,
        extract_frames=args.extract_frames,
        overlay_images=args.overlay_images,
        overlay_segments=args.overlay_segments,
        overlay_audio=args.overlay_audio,
        motion_frames_csv=args.motion_frames_csv or None,
        audio_anomalies_csv=args.audio_anomalies_csv or None,
        audio_pauses_csv=args.audio_pauses_csv or None,
    )
    print("Alignement terminé.")
    print(f"Images extraites : {result['frame_count']}")
    print(f"Index images : {result['frames_index_csv']}")
    print(f"Alignement segments/images : {result['segments_images_alignement_csv']}")
    print(f"Segments de texte synchronisés : {result['segments_texte_sync_csv']}")


if __name__ == "__main__":
    main()
