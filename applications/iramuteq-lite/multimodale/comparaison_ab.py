from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import ensure_directory, utc_session_id, write_json


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_text(path: str | Path, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def compute_audio_pause_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    durations: list[float] = []
    for row in rows:
        duration_sec = safe_float(row.get("duration_sec"))
        if duration_sec is not None and math.isfinite(duration_sec) and duration_sec > 0:
            durations.append(duration_sec)

    if not durations:
        return {
            "count": 0,
            "mean": "",
            "std": "",
            "min": "",
            "max": "",
            "total": "",
        }

    stats = compute_numeric_stats(durations)
    stats["total"] = round(sum(durations), 6)
    return stats


def compute_duration_sec(rows: list[dict[str, str]]) -> float:
    candidates: list[float] = []
    for row in rows:
        for key in ("end_sec", "timestamp_sync", "nearest_frame_time_sec_sync"):
            value = safe_float(row.get(key))
            if value is not None:
                candidates.append(value)
    return max(candidates) if candidates else 0.0


def get_midpoint_sec(row: dict[str, str]) -> float | None:
    timestamp_sync = safe_float(row.get("timestamp_sync"))
    if timestamp_sync is not None:
        return timestamp_sync
    start_sec = safe_float(row.get("start_sec"))
    end_sec = safe_float(row.get("end_sec"))
    if start_sec is None and end_sec is None:
        return None
    if start_sec is None:
        return end_sec
    if end_sec is None:
        return start_sec
    return (start_sec + end_sec) / 2.0


def find_active_row(rows: list[dict[str, str]], time_sec: float) -> dict[str, str] | None:
    if not rows:
        return None

    for row in rows:
        start_sec = safe_float(row.get("start_sec"))
        end_sec = safe_float(row.get("end_sec"))
        pause_before_sec = max(0.0, safe_float(row.get("pause_before_sec")) or 0.0)
        pause_after_sec = max(0.0, safe_float(row.get("pause_after_sec")) or 0.0)
        if start_sec is None and end_sec is None:
            continue
        if start_sec is None:
            start_sec = end_sec
        if end_sec is None:
            end_sec = start_sec
        if start_sec is None or end_sec is None:
            continue
        context_start_sec = max(0.0, start_sec - pause_before_sec)
        context_end_sec = end_sec + pause_after_sec
        if context_start_sec <= time_sec <= context_end_sec:
            return row
    return min(
        rows,
        key=lambda row: abs((get_midpoint_sec(row) or 0.0) - time_sec),
    )


def format_timeline_row(
    side_prefix: str,
    row: dict[str, str] | None,
    absolute_time_sec: float,
) -> dict[str, Any]:
    if not row:
        return {
            f"time_{side_prefix}_sec": round(absolute_time_sec, 6),
            f"segment_{side_prefix}_id": "",
            f"text_{side_prefix}": "",
            f"motion_mean_{side_prefix}": "",
            f"entropy_{side_prefix}": "",
            f"motion_energy_{side_prefix}": "",
            f"words_per_sec_{side_prefix}": "",
            f"anomalie_audio_{side_prefix}": "",
            f"direction_{side_prefix}": "",
            f"nearest_frame_{side_prefix}_id": "",
        }

    return {
        f"time_{side_prefix}_sec": round(absolute_time_sec, 6),
        f"segment_{side_prefix}_id": safe_text(row.get("segment_id")),
        f"text_{side_prefix}": safe_text(row.get("text")),
        f"motion_mean_{side_prefix}": safe_text(row.get("motion_mean_sync")),
        f"entropy_{side_prefix}": safe_text(row.get("roi_directional_entropy_sync")),
        f"motion_energy_{side_prefix}": safe_text(row.get("roi_motion_energy_sync")),
        f"words_per_sec_{side_prefix}": safe_text(row.get("words_per_sec")),
        f"anomalie_audio_{side_prefix}": safe_text(row.get("anomalie_audio_sync")),
        f"direction_{side_prefix}": safe_text(row.get("direction_label_sync")),
        f"nearest_frame_{side_prefix}_id": safe_text(row.get("nearest_frame_id_sync")),
    }


def build_timeline_rows(
    rows_a: list[dict[str, str]],
    rows_b: list[dict[str, str]],
    *,
    steps: int = 100,
) -> list[dict[str, Any]]:
    duration_a = compute_duration_sec(rows_a)
    duration_b = compute_duration_sec(rows_b)
    timeline_rows: list[dict[str, Any]] = []
    previous_signature: tuple[Any, ...] | None = None

    for step in range(steps + 1):
        normalized_percent = round((step / steps) * 100.0, 2)
        time_a = duration_a * (step / steps) if duration_a > 0 else 0.0
        time_b = duration_b * (step / steps) if duration_b > 0 else 0.0
        active_row_a = find_active_row(rows_a, time_a)
        active_row_b = find_active_row(rows_b, time_b)
        row_payload = {
            **format_timeline_row("a", active_row_a, time_a),
            **format_timeline_row("b", active_row_b, time_b),
        }
        signature = (
            row_payload.get("segment_a_id", ""),
            row_payload.get("nearest_frame_a_id", ""),
            row_payload.get("anomalie_audio_a", ""),
            row_payload.get("segment_b_id", ""),
            row_payload.get("nearest_frame_b_id", ""),
            row_payload.get("anomalie_audio_b", ""),
        )
        if timeline_rows and signature == previous_signature:
            timeline_rows[-1]["normalized_percent_end"] = normalized_percent
            timeline_rows[-1]["time_a_end_sec"] = round(time_a, 6)
            timeline_rows[-1]["time_b_end_sec"] = round(time_b, 6)
            continue

        timeline_rows.append(
            {
                "normalized_percent": normalized_percent,
                "normalized_percent_end": normalized_percent,
                "time_a_end_sec": round(time_a, 6),
                "time_b_end_sec": round(time_b, 6),
                **row_payload,
            }
        )
        previous_signature = signature

    return timeline_rows


def build_timestamped_segments_text(rows: list[dict[str, str]], label: str) -> str:
    lines: list[str] = [label]
    for row in rows:
        segment_id = safe_text(row.get("segment_id")) or "?"
        start_sec = safe_float(row.get("start_sec"))
        end_sec = safe_float(row.get("end_sec"))
        text = safe_text(row.get("text"))
        if start_sec is None and end_sec is None:
            continue
        if start_sec is None:
            start_sec = end_sec
        if end_sec is None:
            end_sec = start_sec
        lines.append(
            f"[Segment {segment_id}] [{float(start_sec):.3f}s -> {float(end_sec):.3f}s] {text}".rstrip()
        )
    return "\n".join(lines).rstrip() + "\n"


def build_comparison_timeline_text(
    timeline_rows: list[dict[str, Any]],
    *,
    label_a: str,
    label_b: str,
) -> str:
    lines: list[str] = []
    for row in timeline_rows:
        start_percent = safe_float(row.get("normalized_percent"))
        end_percent = safe_float(row.get("normalized_percent_end"))
        time_a_start = safe_float(row.get("time_a_sec"))
        time_a_end = safe_float(row.get("time_a_end_sec"))
        time_b_start = safe_float(row.get("time_b_sec"))
        time_b_end = safe_float(row.get("time_b_end_sec"))
        segment_a = safe_text(row.get("segment_a_id")) or "?"
        segment_b = safe_text(row.get("segment_b_id")) or "?"
        text_a = safe_text(row.get("text_a"))
        text_b = safe_text(row.get("text_b"))
        lines.append(
            f"[Repère {float(start_percent or 0.0):.2f}% -> {float(end_percent or start_percent or 0.0):.2f}%]"
        )
        lines.append(
            f"{label_a} [Segment {segment_a}] [{float(time_a_start or 0.0):.3f}s -> {float(time_a_end or time_a_start or 0.0):.3f}s] {text_a}".rstrip()
        )
        lines.append(
            f"{label_b} [Segment {segment_b}] [{float(time_b_start or 0.0):.3f}s -> {float(time_b_end or time_b_start or 0.0):.3f}s] {text_b}".rstrip()
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def collect_numeric_values(rows: list[dict[str, str]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = safe_float(row.get(key))
        if value is not None and math.isfinite(value):
            values.append(value)
    return values


def compute_numeric_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": "",
            "std": "",
            "min": "",
            "max": "",
        }

    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return {
        "count": len(values),
        "mean": round(mean_value, 6),
        "std": round(math.sqrt(variance), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def compute_yes_rate(rows: list[dict[str, str]], key: str) -> dict[str, Any]:
    total = len(rows)
    if total <= 0:
        return {"count": 0, "rate": ""}
    positive = sum(1 for row in rows if safe_text(row.get(key)).lower() == "oui")
    return {
        "count": positive,
        "rate": round(positive / total, 6),
    }


INDICATOR_DEFINITIONS = [
    ("words_per_sec", "Débit de parole", "mots/s"),
    ("rms_mean", "Énergie audio RMS", "score"),
    ("peak_dbfs", "Pic sonore", "dBFS"),
    ("motion_mean_sync", "Mouvement moyen", "score"),
    ("roi_directional_entropy_sync", "Entropie directionnelle", "score"),
    ("roi_motion_energy_sync", "Énergie de mouvement", "score"),
    ("frame_count_sync", "Images par segment", "nb"),
]


def build_indicator_rows(
    rows_a: list[dict[str, str]],
    rows_b: list[dict[str, str]],
    *,
    label_a: str,
    label_b: str,
    pause_rows_a: list[dict[str, str]] | None = None,
    pause_rows_b: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    pause_rows_a = pause_rows_a or []
    pause_rows_b = pause_rows_b or []
    indicator_rows: list[dict[str, Any]] = [
        {
            "indicator": "Durée analysée",
            "unite": "s",
            f"{label_a}_mean": round(compute_duration_sec(rows_a), 6),
            f"{label_a}_std": "",
            f"{label_a}_min": "",
            f"{label_a}_max": "",
            f"{label_b}_mean": round(compute_duration_sec(rows_b), 6),
            f"{label_b}_std": "",
            f"{label_b}_min": "",
            f"{label_b}_max": "",
            "delta_b_minus_a": round(compute_duration_sec(rows_b) - compute_duration_sec(rows_a), 6),
        },
        {
            "indicator": "Nombre de segments",
            "unite": "nb",
            f"{label_a}_mean": len(rows_a),
            f"{label_a}_std": "",
            f"{label_a}_min": "",
            f"{label_a}_max": "",
            f"{label_b}_mean": len(rows_b),
            f"{label_b}_std": "",
            f"{label_b}_min": "",
            f"{label_b}_max": "",
            "delta_b_minus_a": len(rows_b) - len(rows_a),
        },
    ]

    anomaly_stats_a = compute_yes_rate(rows_a, "anomalie_audio_sync")
    anomaly_stats_b = compute_yes_rate(rows_b, "anomalie_audio_sync")
    indicator_rows.append(
        {
            "indicator": "Présence d'anomalie audio",
            "unite": "ratio",
            f"{label_a}_mean": anomaly_stats_a["rate"],
            f"{label_a}_std": "",
            f"{label_a}_min": "",
            f"{label_a}_max": "",
            f"{label_b}_mean": anomaly_stats_b["rate"],
            f"{label_b}_std": "",
            f"{label_b}_min": "",
            f"{label_b}_max": "",
            "delta_b_minus_a": (
                round(float(anomaly_stats_b["rate"]) - float(anomaly_stats_a["rate"]), 6)
                if anomaly_stats_a["rate"] != "" and anomaly_stats_b["rate"] != ""
                else ""
            ),
        }
    )

    silence_stats_a = compute_audio_pause_stats(pause_rows_a)
    silence_stats_b = compute_audio_pause_stats(pause_rows_b)
    silence_delta = ""
    if silence_stats_a["mean"] != "" and silence_stats_b["mean"] != "":
        silence_delta = round(float(silence_stats_b["mean"]) - float(silence_stats_a["mean"]), 6)
    indicator_rows.append(
        {
            "indicator": "Durée moyenne des silences",
            "unite": "s",
            f"{label_a}_mean": silence_stats_a["mean"],
            f"{label_a}_std": silence_stats_a["std"],
            f"{label_a}_min": silence_stats_a["min"],
            f"{label_a}_max": silence_stats_a["max"],
            f"{label_b}_mean": silence_stats_b["mean"],
            f"{label_b}_std": silence_stats_b["std"],
            f"{label_b}_min": silence_stats_b["min"],
            f"{label_b}_max": silence_stats_b["max"],
            "delta_b_minus_a": silence_delta,
        }
    )
    total_silence_delta = ""
    if silence_stats_a["total"] != "" and silence_stats_b["total"] != "":
        total_silence_delta = round(float(silence_stats_b["total"]) - float(silence_stats_a["total"]), 6)
    indicator_rows.append(
        {
            "indicator": "Durée totale des silences",
            "unite": "s",
            f"{label_a}_mean": silence_stats_a["total"],
            f"{label_a}_std": "",
            f"{label_a}_min": "",
            f"{label_a}_max": "",
            f"{label_b}_mean": silence_stats_b["total"],
            f"{label_b}_std": "",
            f"{label_b}_min": "",
            f"{label_b}_max": "",
            "delta_b_minus_a": total_silence_delta,
        }
    )
    indicator_rows.append(
        {
            "indicator": "Nombre de silences",
            "unite": "nb",
            f"{label_a}_mean": silence_stats_a["count"],
            f"{label_a}_std": "",
            f"{label_a}_min": "",
            f"{label_a}_max": "",
            f"{label_b}_mean": silence_stats_b["count"],
            f"{label_b}_std": "",
            f"{label_b}_min": "",
            f"{label_b}_max": "",
            "delta_b_minus_a": silence_stats_b["count"] - silence_stats_a["count"],
        }
    )

    for key, label, unit in INDICATOR_DEFINITIONS:
        values_a = collect_numeric_values(rows_a, key)
        values_b = collect_numeric_values(rows_b, key)
        stats_a = compute_numeric_stats(values_a)
        stats_b = compute_numeric_stats(values_b)
        delta = ""
        if stats_a["mean"] != "" and stats_b["mean"] != "":
            delta = round(float(stats_b["mean"]) - float(stats_a["mean"]), 6)
        indicator_rows.append(
            {
                "indicator": label,
                "unite": unit,
                f"{label_a}_mean": stats_a["mean"],
                f"{label_a}_std": stats_a["std"],
                f"{label_a}_min": stats_a["min"],
                f"{label_a}_max": stats_a["max"],
                f"{label_b}_mean": stats_b["mean"],
                f"{label_b}_std": stats_b["std"],
                f"{label_b}_min": stats_b["min"],
                f"{label_b}_max": stats_b["max"],
                "delta_b_minus_a": delta,
            }
        )

    return indicator_rows


def build_summary(
    rows_a: list[dict[str, str]],
    rows_b: list[dict[str, str]],
    indicator_rows: list[dict[str, Any]],
    *,
    label_a: str,
    label_b: str,
    aligned_csv_a: str,
    aligned_csv_b: str,
    output_dir: str,
) -> dict[str, Any]:
    summary_lookup = {row.get("indicator"): row for row in indicator_rows}
    return {
        "session_id": utc_session_id("comparaison_ab"),
        "labels": {
            "a": label_a,
            "b": label_b,
        },
        "sources": {
            "aligned_csv_a": aligned_csv_a,
            "aligned_csv_b": aligned_csv_b,
        },
        "counts": {
            "segments_a": len(rows_a),
            "segments_b": len(rows_b),
        },
        "durations_sec": {
            "a": round(compute_duration_sec(rows_a), 6),
            "b": round(compute_duration_sec(rows_b), 6),
        },
        "key_differences": {
            "motion_mean_delta": summary_lookup.get("Mouvement moyen", {}).get("delta_b_minus_a", ""),
            "directional_entropy_delta": summary_lookup.get("Entropie directionnelle", {}).get("delta_b_minus_a", ""),
            "speech_rate_delta": summary_lookup.get("Débit de parole", {}).get("delta_b_minus_a", ""),
            "audio_anomaly_rate_delta": summary_lookup.get("Présence d'anomalie audio", {}).get("delta_b_minus_a", ""),
        },
        "output_dir": output_dir,
        "comparison_mode": "chaque vidéo est ramenée à 101 repères relatifs communs : 0% = début, 50% = milieu, 100% = fin",
    }


def compare_aligned_series(
    aligned_csv_a: str | Path,
    aligned_csv_b: str | Path,
    output_dir: str | Path,
    *,
    label_a: str = "A",
    label_b: str = "B",
    steps: int = 100,
    audio_pauses_csv_a: str | Path | None = None,
    audio_pauses_csv_b: str | Path | None = None,
) -> dict[str, str]:
    rows_a = read_csv_rows(aligned_csv_a)
    rows_b = read_csv_rows(aligned_csv_b)
    pause_rows_a = read_csv_rows(audio_pauses_csv_a) if audio_pauses_csv_a else []
    pause_rows_b = read_csv_rows(audio_pauses_csv_b) if audio_pauses_csv_b else []
    destination = ensure_directory(output_dir)

    timeline_rows = build_timeline_rows(rows_a, rows_b, steps=steps)
    indicator_rows = build_indicator_rows(
        rows_a,
        rows_b,
        label_a=label_a,
        label_b=label_b,
        pause_rows_a=pause_rows_a,
        pause_rows_b=pause_rows_b,
    )
    summary = build_summary(
        rows_a,
        rows_b,
        indicator_rows,
        label_a=label_a,
        label_b=label_b,
        aligned_csv_a=str(Path(aligned_csv_a).expanduser().resolve()),
        aligned_csv_b=str(Path(aligned_csv_b).expanduser().resolve()),
        output_dir=str(destination),
    )

    timeline_csv_path = destination / "comparaison_ab_timeline.csv"
    indicators_csv_path = destination / "comparaison_ab_indicateurs.csv"
    summary_json_path = destination / "comparaison_ab_summary.json"
    timeline_txt_path = destination / "comparaison_ab_timeline_timestamped.txt"
    segments_txt_a_path = destination / "video_a_segments_timestamped.txt"
    segments_txt_b_path = destination / "video_b_segments_timestamped.txt"

    write_csv(timeline_csv_path, timeline_rows)
    write_csv(indicators_csv_path, indicator_rows)
    write_text(timeline_txt_path, build_comparison_timeline_text(timeline_rows, label_a=label_a, label_b=label_b))
    write_text(segments_txt_a_path, build_timestamped_segments_text(rows_a, label_a))
    write_text(segments_txt_b_path, build_timestamped_segments_text(rows_b, label_b))
    write_json(summary_json_path, summary)

    return {
        "summary_json": str(summary_json_path),
        "timeline_csv": str(timeline_csv_path),
        "indicators_csv": str(indicators_csv_path),
        "timeline_txt": str(timeline_txt_path),
        "segments_txt_a": str(segments_txt_a_path),
        "segments_txt_b": str(segments_txt_b_path),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare deux séries multimodales synchronisées issues de deux vidéos."
    )
    parser.add_argument("--aligned-csv-a", required=True, help="CSV d'alignement complet pour la vidéo A.")
    parser.add_argument("--aligned-csv-b", required=True, help="CSV d'alignement complet pour la vidéo B.")
    parser.add_argument("--label-a", default="Vidéo A", help="Libellé court de la série A.")
    parser.add_argument("--label-b", default="Vidéo B", help="Libellé court de la série B.")
    parser.add_argument("--steps", type=int, default=100, help="Nombre d'étapes de la timeline normalisée.")
    parser.add_argument("--audio-pauses-csv-a", default="", help="CSV des silences audio pour la vidéo A.")
    parser.add_argument("--audio-pauses-csv-b", default="", help="CSV des silences audio pour la vidéo B.")
    parser.add_argument("--output-dir", default="multimodale/exports/comparaison_ab", help="Dossier d'export.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    result = compare_aligned_series(
        aligned_csv_a=args.aligned_csv_a,
        aligned_csv_b=args.aligned_csv_b,
        output_dir=args.output_dir,
        label_a=args.label_a,
        label_b=args.label_b,
        steps=max(10, int(args.steps)),
        audio_pauses_csv_a=args.audio_pauses_csv_a or None,
        audio_pauses_csv_b=args.audio_pauses_csv_b or None,
    )
    print("Comparaison A/B terminée.")
    print(f"Résumé : {result['summary_json']}")
    print(f"Timeline : {result['timeline_csv']}")
    print(f"Indicateurs : {result['indicators_csv']}")
    print(f"Timeline texte : {result['timeline_txt']}")
    print(f"Segments A : {result['segments_txt_a']}")
    print(f"Segments B : {result['segments_txt_b']}")


if __name__ == "__main__":
    main()
