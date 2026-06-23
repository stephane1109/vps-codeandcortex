from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import ensure_directory, utc_session_id, write_json, write_jsonl

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - dépendance externe
    raise RuntimeError("numpy est requis pour multimodale/synchronisation.py") from exc

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
except ImportError:  # pragma: no cover - dépendance externe
    KMeans = None
    StandardScaler = None


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


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def overlap_duration(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def weighted_mean(rows: list[dict[str, Any]], key: str, weights: list[float]) -> float | None:
    values = []
    valid_weights = []
    for row, weight in zip(rows, weights):
        value = safe_float(row.get(key))
        if value is None or weight <= 0:
            continue
        values.append(value)
        valid_weights.append(weight)
    if not values or not valid_weights:
        return None
    return float(np.average(np.array(values, dtype=float), weights=np.array(valid_weights, dtype=float)))


def weighted_mode(rows: list[dict[str, Any]], key: str, weights: list[float]) -> str:
    scores: dict[str, float] = defaultdict(float)
    for row, weight in zip(rows, weights):
        value = str(row.get(key, "") or "").strip()
        if not value or weight <= 0:
            continue
        scores[value] += weight
    if not scores:
        return ""
    return max(scores.items(), key=lambda item: item[1])[0]


def synchroniser_segments(
    segments_csv: str | Path,
    windows_csv: str | Path,
    output_dir: str | Path,
    clusters: int = 3,
) -> dict[str, Any]:
    """
    Synchronise les segments textuels horodatés avec :
    - les indicateurs audio déjà présents dans les segments
    - les fenêtres vidéo de mouvements
    """
    destination = ensure_directory(output_dir)
    session_id = utc_session_id("sync")

    segment_rows = read_csv_rows(segments_csv)
    window_rows = read_csv_rows(windows_csv)

    synchronized_rows: list[dict[str, Any]] = []
    for segment in segment_rows:
        start_sec = safe_float(segment.get("start_sec")) or 0.0
        end_sec = safe_float(segment.get("end_sec")) or start_sec
        overlaps = []
        overlap_weights = []

        for window in window_rows:
            window_start = safe_float(window.get("start_sec")) or 0.0
            window_end = safe_float(window.get("end_sec")) or window_start
            duration = overlap_duration(start_sec, end_sec, window_start, window_end)
            if duration > 0:
                overlaps.append(window)
                overlap_weights.append(duration)

        synchronized = dict(segment)
        synchronized["window_matches"] = len(overlaps)
        synchronized["motion_mean_sync"] = None
        synchronized["motion_peak_sync"] = None
        synchronized["motion_active_ratio_sync"] = None
        synchronized["direction_sync"] = ""
        synchronized["face_area_ratio_sync"] = None
        synchronized["keyframe_path_sync"] = ""

        if overlaps:
            synchronized["motion_mean_sync"] = round(weighted_mean(overlaps, "motion_mean", overlap_weights) or 0.0, 6)
            synchronized["motion_peak_sync"] = round(weighted_mean(overlaps, "motion_peak_p95", overlap_weights) or 0.0, 6)
            synchronized["motion_active_ratio_sync"] = round(weighted_mean(overlaps, "motion_active_ratio", overlap_weights) or 0.0, 6)
            synchronized["face_area_ratio_sync"] = round(weighted_mean(overlaps, "face_area_ratio", overlap_weights) or 0.0, 6)
            synchronized["direction_sync"] = weighted_mode(overlaps, "dominant_direction", overlap_weights)
            synchronized["keyframe_path_sync"] = weighted_mode(overlaps, "keyframe_path", overlap_weights)

        synchronized_rows.append(synchronized)

    cluster_summary = {
        "enabled": False,
        "backend": "aucun",
        "clusters": [],
    }

    if synchronized_rows and KMeans is not None and StandardScaler is not None and len(synchronized_rows) >= max(2, clusters):
        feature_columns = [
            "duration_sec",
            "pause_before_sec",
            "pause_after_sec",
            "words_per_sec",
            "rms_mean",
            "peak_dbfs",
            "motion_mean_sync",
            "motion_peak_sync",
            "motion_active_ratio_sync",
            "face_area_ratio_sync",
        ]

        numeric_matrix = []
        valid_indices = []
        for index, row in enumerate(synchronized_rows):
            vector = []
            valid = True
            for column in feature_columns:
                value = safe_float(row.get(column))
                if value is None:
                    value = 0.0
                vector.append(value)
            if valid:
                numeric_matrix.append(vector)
                valid_indices.append(index)

        if len(numeric_matrix) >= max(2, clusters):
            matrix = np.array(numeric_matrix, dtype=float)
            scaler = StandardScaler()
            scaled = scaler.fit_transform(matrix)
            model = KMeans(n_clusters=clusters, n_init=10, random_state=42)
            labels = model.fit_predict(scaled)
            distances = model.transform(scaled)

            for row_index, cluster_label, distance_vector in zip(valid_indices, labels, distances):
                synchronized_rows[row_index]["cluster_id"] = int(cluster_label)
                synchronized_rows[row_index]["cluster_distance"] = round(float(np.min(distance_vector)), 6)

            cluster_descriptions = []
            for cluster_label in sorted(set(labels)):
                indices = [idx for idx, label in zip(valid_indices, labels) if label == cluster_label]
                subset = [synchronized_rows[idx] for idx in indices]
                cluster_descriptions.append(
                    {
                        "cluster_id": int(cluster_label),
                        "segment_count": len(subset),
                        "mean_words_per_sec": round(float(np.mean([safe_float(row.get("words_per_sec")) or 0.0 for row in subset])), 6),
                        "mean_motion": round(float(np.mean([safe_float(row.get("motion_mean_sync")) or 0.0 for row in subset])), 6),
                        "dominant_direction": weighted_mode(subset, "direction_sync", [1.0] * len(subset)),
                    }
                )

            cluster_summary = {
                "enabled": True,
                "backend": "sklearn-kmeans",
                "clusters": cluster_descriptions,
            }
        else:
            for row in synchronized_rows:
                row["cluster_id"] = ""
                row["cluster_distance"] = ""
    else:
        for row in synchronized_rows:
            row["cluster_id"] = ""
            row["cluster_distance"] = ""

    summary = {
        "session_id": session_id,
        "segments_csv": str(segments_csv),
        "windows_csv": str(windows_csv),
        "segment_count": len(segment_rows),
        "window_count": len(window_rows),
        "cluster_summary": cluster_summary,
        "propositions_shs": {
            "discordance_verbal_non_verbal": "Comparer contenu textuel, direction du mouvement et variations prosodiques.",
            "pre_rupture": "Observer les segments qui précèdent un pic de mouvement ou une pause longue.",
            "double_contrainte": "Rechercher les moments où le texte indique une chose tandis que la prosodie et le non-verbal indiquent l'inverse.",
        },
    }

    write_csv(destination / "segments_multimodaux.csv", synchronized_rows)
    write_jsonl(destination / "segments_multimodaux.jsonl", synchronized_rows)
    write_json(destination / "synchronisation_summary.json", summary)

    return {
        "session_id": session_id,
        "segments_multimodaux_csv": str(destination / "segments_multimodaux.csv"),
        "segments_multimodaux_jsonl": str(destination / "segments_multimodaux.jsonl"),
        "summary_json": str(destination / "synchronisation_summary.json"),
        "segment_count": len(synchronized_rows),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronise segments textuels/audio avec indicateurs visuels multimodaux."
    )
    parser.add_argument("--segments-csv", required=True, help="CSV produit par multimodale/audio.py")
    parser.add_argument("--windows-csv", required=True, help="CSV produit par multimodale/mouvements.py")
    parser.add_argument("--output-dir", default="multimodale/exports/synchronisation", help="Dossier d'export.")
    parser.add_argument("--clusters", type=int, default=3, help="Nombre de clusters KMeans si sklearn est disponible.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    result = synchroniser_segments(
        segments_csv=args.segments_csv,
        windows_csv=args.windows_csv,
        output_dir=args.output_dir,
        clusters=args.clusters,
    )
    print("Synchronisation terminée.")
    print(f"Segments synchronisés : {result['segment_count']}")
    print(f"CSV : {result['segments_multimodaux_csv']}")


if __name__ == "__main__":
    main()
