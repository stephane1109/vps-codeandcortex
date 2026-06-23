from __future__ import annotations

from typing import Any


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(float(value))
    except Exception:
        return None


def normalize_time_bounds(start_sec: float | None, end_sec: float | None) -> tuple[float | None, float | None]:
    if start_sec is None and end_sec is None:
        return (None, None)
    if start_sec is None:
        start_sec = end_sec
    if end_sec is None:
        end_sec = start_sec
    if start_sec is None or end_sec is None:
        return (None, None)
    if end_sec < start_sec:
        start_sec, end_sec = end_sec, start_sec
    return (start_sec, end_sec)


def build_timeline_payload(
    aligned_rows: list[dict[str, Any]],
    motion_rows: list[dict[str, Any]] | None = None,
    anomaly_rows: list[dict[str, Any]] | None = None,
    pause_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    motion_rows = motion_rows or []
    anomaly_rows = anomaly_rows or []
    pause_rows = pause_rows or []

    image_items: list[dict[str, Any]] = []
    for row in motion_rows:
        time_sec = safe_float(row.get("time_sec"))
        if time_sec is None:
            continue
        image_items.append(
            {
                "time_sec": round(time_sec, 6),
                "frame_index": safe_int(row.get("frame_index")),
                "image_path": str(row.get("image_path", "") or ""),
                "frame_preview_path": str(row.get("frame_preview_path", "") or ""),
                "magnitude_preview_path": str(row.get("magnitude_preview_path", "") or ""),
                "directional_entropy_preview_path": str(row.get("directional_entropy_preview_path", "") or ""),
                "hsv_preview_path": str(row.get("hsv_preview_path", "") or ""),
                "vectors_preview_path": str(row.get("vectors_preview_path", "") or ""),
                "overlay_preview_path": str(row.get("overlay_preview_path", "") or ""),
                "annotated_preview_path": str(row.get("annotated_preview_path", "") or ""),
                "motion_mean": safe_float(row.get("motion_mean")),
                "roi_directional_entropy": safe_float(row.get("roi_directional_entropy")),
                "direction_label": str(row.get("direction_label", "") or ""),
            }
        )

    text_items: list[dict[str, Any]] = []
    for row in aligned_rows:
        start_sec = safe_float(row.get("start_sec"))
        end_sec = safe_float(row.get("end_sec"))
        start_sec, end_sec = normalize_time_bounds(start_sec, end_sec)
        if start_sec is None or end_sec is None:
            continue
        text_items.append(
            {
                "segment_id": str(row.get("segment_id", "") or ""),
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "speech_duration_sec": round(max(0.0, end_sec - start_sec), 6),
                "timestamp_sync": safe_float(row.get("timestamp_sync")),
                "text": str(row.get("text", "") or ""),
                "frame_count_sync": safe_int(row.get("frame_count_sync")),
                "anomalie_audio_sync": str(row.get("anomalie_audio_sync", "") or ""),
                "pause_before_sec": round(max(0.0, safe_float(row.get("pause_before_sec")) or 0.0), 6),
                "pause_after_sec": round(max(0.0, safe_float(row.get("pause_after_sec")) or 0.0), 6),
                "context_start_sec": round(max(0.0, start_sec - (safe_float(row.get("pause_before_sec")) or 0.0)), 6),
                "context_end_sec": round(end_sec + (safe_float(row.get("pause_after_sec")) or 0.0), 6),
                "context_duration_sec": round(
                    max(0.0, (end_sec + (safe_float(row.get("pause_after_sec")) or 0.0)) - max(0.0, start_sec - (safe_float(row.get("pause_before_sec")) or 0.0))),
                    6,
                ),
            }
        )
    pause_items: list[dict[str, Any]] = []
    if pause_rows:
        for row in pause_rows:
            start_sec = safe_float(row.get("start_sec"))
            end_sec = safe_float(row.get("end_sec"))
            start_sec, end_sec = normalize_time_bounds(start_sec, end_sec)
            if start_sec is None or end_sec is None or end_sec <= start_sec:
                continue
            pause_items.append(
                {
                    "kind": "silence",
                    "pause_id": safe_int(row.get("pause_id")),
                    "start_sec": round(start_sec, 6),
                    "end_sec": round(end_sec, 6),
                    "center_sec": safe_float(row.get("center_sec")),
                    "duration_sec": round(max(0.0, end_sec - start_sec), 6),
                }
            )
    else:
        for row in aligned_rows:
            start_sec = safe_float(row.get("start_sec"))
            end_sec = safe_float(row.get("end_sec"))
            start_sec, end_sec = normalize_time_bounds(start_sec, end_sec)
            if start_sec is None or end_sec is None:
                continue
            pause_before_sec = safe_float(row.get("pause_before_sec"))
            if pause_before_sec is not None and pause_before_sec > 0:
                pause_items.append(
                    {
                        "kind": "before",
                        "segment_id": str(row.get("segment_id", "") or ""),
                        "start_sec": round(max(0.0, start_sec - pause_before_sec), 6),
                        "end_sec": round(start_sec, 6),
                        "duration_sec": round(pause_before_sec, 6),
                    }
                )
            pause_after_sec = safe_float(row.get("pause_after_sec"))
            if pause_after_sec is not None and pause_after_sec > 0:
                pause_items.append(
                    {
                        "kind": "after",
                        "segment_id": str(row.get("segment_id", "") or ""),
                        "start_sec": round(end_sec, 6),
                        "end_sec": round(end_sec + pause_after_sec, 6),
                        "duration_sec": round(pause_after_sec, 6),
                    }
                )

    audio_items: list[dict[str, Any]] = []
    for row in anomaly_rows:
        start_sec = safe_float(row.get("start_sec"))
        end_sec = safe_float(row.get("end_sec"))
        start_sec, end_sec = normalize_time_bounds(start_sec, end_sec)
        if start_sec is None or end_sec is None:
            continue
        if str(row.get("anomaly_flag", "") or "").strip().lower() != "oui":
            continue
        audio_items.append(
            {
                "window_id": str(row.get("window_id", "") or ""),
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "time_sec": safe_float(row.get("time_sec")),
                "mean_amp": safe_float(row.get("mean_amp")),
                "z_score": safe_float(row.get("z_score")),
            }
        )

    motion_track = [
        {
            "time_sec": item["time_sec"],
            "value": item["motion_mean"],
            "label": item.get("direction_label", ""),
            "frame_index": item.get("frame_index"),
        }
        for item in image_items
        if item.get("motion_mean") is not None
    ]
    entropy_track = [
        {
            "time_sec": item["time_sec"],
            "value": item["roi_directional_entropy"],
            "label": item.get("direction_label", ""),
            "frame_index": item.get("frame_index"),
        }
        for item in image_items
        if item.get("roi_directional_entropy") is not None
    ]

    end_candidates = [
        *(item["time_sec"] for item in image_items if item.get("time_sec") is not None),
        *(item["end_sec"] for item in text_items if item.get("end_sec") is not None),
        *(item["end_sec"] for item in pause_items if item.get("end_sec") is not None),
        *(item["end_sec"] for item in audio_items if item.get("end_sec") is not None),
    ]
    duration_sec = max(end_candidates) if end_candidates else 0.0

    image_items.sort(key=lambda item: (item.get("time_sec") or 0.0, item.get("frame_index") or 0))
    text_items.sort(key=lambda item: (item.get("start_sec") or 0.0, item.get("segment_id") or ""))
    pause_items.sort(key=lambda item: (item.get("start_sec") or 0.0, item.get("segment_id") or "", item.get("kind") or ""))
    audio_items.sort(key=lambda item: (item.get("start_sec") or 0.0, item.get("window_id") or ""))
    motion_track.sort(key=lambda item: (item.get("time_sec") or 0.0, item.get("frame_index") or 0))
    entropy_track.sort(key=lambda item: (item.get("time_sec") or 0.0, item.get("frame_index") or 0))

    return {
        "duration_sec": round(float(duration_sec), 6),
        "tracks": {
            "images": image_items,
            "text": text_items,
            "pauses": pause_items,
            "audio_anomalies": audio_items,
            "motion_mean": motion_track,
            "directional_entropy": entropy_track,
        },
    }
