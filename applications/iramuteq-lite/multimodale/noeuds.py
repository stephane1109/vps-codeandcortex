from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
import unicodedata
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import ensure_directory, write_json


FRENCH_STOPWORDS = {
    "a", "ai", "alors", "au", "aucun", "aussi", "autre", "avec", "avoir", "bon", "car", "ce", "cela", "ces",
    "ceux", "chaque", "ci", "comme", "comment", "dans", "des", "du", "dedans", "dehors", "depuis", "deux",
    "devrait", "doit", "donc", "dos", "droite", "de", "elle", "elles", "en", "encore", "essai", "est", "et",
    "eu", "fait", "faites", "fois", "font", "force", "haut", "hors", "ici", "il", "ils", "je", "juste", "la",
    "le", "les", "leur", "là", "ma", "maintenant", "mais", "mes", "mine", "moins", "mon", "mot", "même", "ni",
    "nommés", "notre", "nous", "nouveaux", "ou", "où", "par", "parce", "parole", "pas", "peu", "peut", "plupart",
    "pour", "pourquoi", "quand", "que", "quel", "quelle", "quelles", "quels", "qui", "sa", "sans", "ses", "seulement",
    "si", "sien", "son", "sont", "sous", "soyez", "sujet", "sur", "ta", "tandis", "tellement", "tels", "tes",
    "ton", "tous", "tout", "trop", "très", "tu", "un", "une", "va", "vos", "votre", "vous", "vu", "ça", "étaient",
    "état", "étions", "été", "être", "c", "d", "j", "l", "n", "qu", "s", "t", "y",
}


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("", encoding="utf-8")
        return str(destination)

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
    return str(destination)


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


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def median_step(points: list[dict[str, Any]]) -> float:
    if len(points) < 2:
        return 1.0
    diffs = []
    for left, right in zip(points, points[1:]):
        left_time = safe_float(left.get("time_sec"))
        right_time = safe_float(right.get("time_sec"))
        if left_time is None or right_time is None:
            continue
        diff = right_time - left_time
        if diff > 0:
            diffs.append(diff)
    if not diffs:
        return 1.0
    return max(0.04, statistics.median(diffs))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    index = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return float(ordered[low])
    low_value = ordered[low]
    high_value = ordered[high]
    weight = index - low
    return float(low_value + ((high_value - low_value) * weight))


def normalize_token(token: str) -> str:
    stripped = unicodedata.normalize("NFD", token.lower())
    stripped = "".join(char for char in stripped if unicodedata.category(char) != "Mn")
    return stripped


def tokenize_text(text: str) -> list[str]:
    normalized = normalize_token(text)
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in raw_tokens if len(token) >= 3 and token not in FRENCH_STOPWORDS]


def build_motion_points(motion_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, row in enumerate(motion_rows, start=1):
        time_sec = safe_float(row.get("time_sec"))
        entropy = safe_float(row.get("roi_directional_entropy"))
        if time_sec is None or entropy is None:
            continue
        points.append(
            {
                "point_index": index,
                "time_sec": round(time_sec, 6),
                "frame_index": safe_int(row.get("frame_index")) or index,
                "entropy": float(entropy),
                "motion_mean": safe_float(row.get("motion_mean")) or 0.0,
                "motion_energy": safe_float(row.get("roi_motion_energy")) or 0.0,
                "direction_label": safe_text(row.get("direction_label")),
                "image_path": safe_text(row.get("image_path")),
                "frame_preview_path": safe_text(row.get("frame_preview_path")),
                "entropy_preview_path": safe_text(row.get("directional_entropy_preview_path")),
            }
        )
    points.sort(key=lambda point: (point["time_sec"], point["frame_index"]))
    return points


def build_entropy_threshold(points: list[dict[str, Any]], entropy_k: float) -> tuple[float, float, float]:
    entropies = [float(point["entropy"]) for point in points]
    if not entropies:
        return 0.0, 0.0, 0.0
    mean_entropy = statistics.fmean(entropies)
    std_entropy = statistics.pstdev(entropies) if len(entropies) > 1 else 0.0
    threshold = mean_entropy + (float(entropy_k) * std_entropy)
    return float(mean_entropy), float(std_entropy), float(threshold)


def select_local_peak_indices(points: list[dict[str, Any]]) -> list[int]:
    peak_indices: list[int] = []
    if not points:
        return peak_indices
    for index, point in enumerate(points):
        current = float(point["entropy"])
        previous = float(points[index - 1]["entropy"]) if index > 0 else float("-inf")
        following = float(points[index + 1]["entropy"]) if index < len(points) - 1 else float("-inf")
        if current >= previous and current >= following:
            peak_indices.append(index)
    if peak_indices:
        return peak_indices
    ranked_indices = sorted(range(len(points)), key=lambda idx: float(points[idx]["entropy"]), reverse=True)
    return sorted(ranked_indices[: min(3, len(ranked_indices))])


def build_visual_events(points: list[dict[str, Any]], event_mode: str, entropy_k: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not points:
        return [], {
            "selection_mode": event_mode,
            "mean_entropy": 0.0,
            "std_entropy": 0.0,
            "threshold": None,
            "entropy_k": float(entropy_k),
        }

    mean_entropy, std_entropy, threshold = build_entropy_threshold(points, entropy_k)
    if event_mode == "local-peaks":
        selected_indices = select_local_peak_indices(points)
    else:
        selected_indices = [index for index, point in enumerate(points) if float(point["entropy"]) >= threshold]
    if not selected_indices:
        ranked_indices = sorted(range(len(points)), key=lambda idx: float(points[idx]["entropy"]), reverse=True)
        selected_indices = sorted(ranked_indices[: min(3, len(ranked_indices))])

    if not selected_indices:
        return [], {
            "selection_mode": event_mode,
            "mean_entropy": round(mean_entropy, 6),
            "std_entropy": round(std_entropy, 6),
            "threshold": round(threshold, 6) if event_mode != "local-peaks" else None,
            "entropy_k": float(entropy_k),
        }

    step_sec = median_step(points)
    merge_gap_sec = max(step_sec * 1.15, 0.12)
    groups: list[list[int]] = [[selected_indices[0]]]
    for index in selected_indices[1:]:
        previous_index = groups[-1][-1]
        if points[index]["time_sec"] - points[previous_index]["time_sec"] <= merge_gap_sec:
            groups[-1].append(index)
        else:
            groups.append([index])

    if not groups:
        return [], {
            "selection_mode": event_mode,
            "mean_entropy": round(mean_entropy, 6),
            "std_entropy": round(std_entropy, 6),
            "threshold": round(threshold, 6) if event_mode != "local-peaks" else None,
            "entropy_k": float(entropy_k),
        }

    events: list[dict[str, Any]] = []
    for event_index, group in enumerate(groups, start=1):
        group_points = [points[idx] for idx in group]
        peak_point = max(group_points, key=lambda point: float(point["entropy"]))
        start_sec = max(0.0, float(group_points[0]["time_sec"]) - (step_sec / 2.0))
        end_sec = float(group_points[-1]["time_sec"]) + (step_sec / 2.0)
        events.append(
            {
                "id": f"event_{event_index}",
                "type": "event",
                "label": f"Événement {event_index}",
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "time_sec": round(float(peak_point["time_sec"]), 6),
                "entropy_peak": round(float(peak_point["entropy"]), 6),
                "entropy_mean": round(statistics.fmean(float(point["entropy"]) for point in group_points), 6),
                "motion_mean": round(statistics.fmean(float(point["motion_mean"]) for point in group_points), 6),
                "motion_energy": round(statistics.fmean(float(point["motion_energy"]) for point in group_points), 6),
                "direction_label": safe_text(peak_point.get("direction_label")),
                "frame_index": peak_point.get("frame_index"),
                "image_path": safe_text(peak_point.get("image_path")),
                "frame_preview_path": safe_text(peak_point.get("frame_preview_path")),
                "entropy_preview_path": safe_text(peak_point.get("entropy_preview_path")),
                "member_frame_count": len(group_points),
                "selection_threshold": round(threshold, 6) if event_mode != "local-peaks" else None,
            }
        )
    return events, {
        "selection_mode": event_mode,
        "mean_entropy": round(mean_entropy, 6),
        "std_entropy": round(std_entropy, 6),
        "threshold": round(threshold, 6) if event_mode != "local-peaks" else None,
        "entropy_k": float(entropy_k),
    }


def build_text_nodes(aligned_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for index, row in enumerate(aligned_rows, start=1):
        segment_id = safe_text(row.get("segment_id")) or str(index)
        start_sec = safe_float(row.get("start_sec")) or 0.0
        end_sec = safe_float(row.get("end_sec")) or start_sec
        midpoint = (start_sec + end_sec) / 2.0
        text = safe_text(row.get("text"))
        tokens = tokenize_text(text)
        nodes.append(
            {
                "id": f"text_{segment_id}",
                "type": "text",
                "segment_id": segment_id,
                "label": f"Segment {segment_id}",
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "time_sec": round(midpoint, 6),
                "text": text,
                "text_excerpt": text[:160],
                "word_count": len(text.split()),
                "tokens": tokens,
                "nearest_frame_id_sync": safe_text(row.get("nearest_frame_id_sync")),
                "nearest_frame_time_sec_sync": safe_float(row.get("nearest_frame_time_sec_sync")),
                "nearest_frame_path_sync": safe_text(row.get("nearest_frame_path_sync")),
            }
        )
    return nodes


def build_temporal_edges(events: list[dict[str, Any]], text_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for event in events:
        overlaps = [
            text_node
            for text_node in text_nodes
            if float(text_node["start_sec"]) <= float(event["end_sec"]) and float(text_node["end_sec"]) >= float(event["start_sec"])
        ]
        if not overlaps and text_nodes:
            nearest = min(
                text_nodes,
                key=lambda text_node: abs(float(text_node["time_sec"]) - float(event["time_sec"])),
            )
            if abs(float(nearest["time_sec"]) - float(event["time_sec"])) <= 1.0:
                overlaps = [nearest]
        for text_node in overlaps:
            overlap_start = max(float(event["start_sec"]), float(text_node["start_sec"]))
            overlap_end = min(float(event["end_sec"]), float(text_node["end_sec"]))
            overlap_duration = max(0.0, overlap_end - overlap_start)
            edges.append(
                {
                    "id": f"{event['id']}__{text_node['id']}__temporal",
                    "source": event["id"],
                    "target": text_node["id"],
                    "type": "temporal",
                    "label": "coïncidence temporelle",
                    "weight": round(max(0.1, overlap_duration if overlap_duration > 0 else 0.1), 6),
                    "time_gap_sec": round(abs(float(text_node["time_sec"]) - float(event["time_sec"])), 6),
                }
            )
    return edges


def build_visual_edges(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    ordered = sorted(events, key=lambda event: (float(event["time_sec"]), str(event["id"])))
    for left, right in zip(ordered, ordered[1:]):
        gap_sec = max(0.0, float(right["time_sec"]) - float(left["time_sec"]))
        entropy_delta = abs(float(right["entropy_peak"]) - float(left["entropy_peak"]))
        similarity = max(0.0, 1.0 - min(gap_sec, 8.0) / 8.0) * 0.6 + max(0.0, 1.0 - min(entropy_delta, 2.0) / 2.0) * 0.4
        if similarity <= 0.15:
            continue
        edges.append(
            {
                "id": f"{left['id']}__{right['id']}__visual",
                "source": left["id"],
                "target": right["id"],
                "type": "visual",
                "label": "proximité visuelle",
                "weight": round(similarity, 6),
                "time_gap_sec": round(gap_sec, 6),
                "entropy_delta": round(entropy_delta, 6),
            }
        )
    return edges


def build_lexical_edges(text_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for left_index, left in enumerate(text_nodes):
        left_tokens = set(left.get("tokens") or [])
        if not left_tokens:
            continue
        for right in text_nodes[left_index + 1:]:
            right_tokens = set(right.get("tokens") or [])
            if not right_tokens:
                continue
            shared = sorted(left_tokens & right_tokens)
            if len(shared) < 2:
                continue
            union_count = max(1, len(left_tokens | right_tokens))
            jaccard = len(shared) / union_count
            candidates.append(
                {
                    "id": f"{left['id']}__{right['id']}__lexical",
                    "source": left["id"],
                    "target": right["id"],
                    "type": "lexical",
                    "label": "proximité lexicale",
                    "weight": round(jaccard, 6),
                    "shared_terms": ", ".join(shared[:8]),
                    "shared_terms_count": len(shared),
                }
            )

    candidates.sort(key=lambda edge: (-int(edge.get("shared_terms_count", 0)), -float(edge.get("weight", 0.0))))
    return candidates[:40]


def build_summary(
    events: list[dict[str, Any]],
    text_nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    threshold_stats: dict[str, Any],
) -> dict[str, Any]:
    counts_by_type: dict[str, int] = {}
    for edge in edges:
        edge_type = safe_text(edge.get("type")) or "inconnu"
        counts_by_type[edge_type] = counts_by_type.get(edge_type, 0) + 1
    return {
        "event_count": len(events),
        "text_node_count": len(text_nodes),
        "edge_count": len(edges),
        "edge_types": counts_by_type,
        "max_entropy_peak": max((float(event["entropy_peak"]) for event in events), default=0.0),
        "mean_entropy_peak": round(statistics.fmean(float(event["entropy_peak"]) for event in events), 6) if events else 0.0,
        "mean_entropy_global": threshold_stats.get("mean_entropy", 0.0),
        "std_entropy_global": threshold_stats.get("std_entropy", 0.0),
        "entropy_threshold": threshold_stats.get("threshold"),
        "entropy_k": threshold_stats.get("entropy_k", 1.0),
        "selection_mode": threshold_stats.get("selection_mode", "threshold"),
    }


def build_graph(
    aligned_rows: list[dict[str, str]],
    motion_rows: list[dict[str, str]],
    event_mode: str,
    entropy_k: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    motion_points = build_motion_points(motion_rows)
    events, threshold_stats = build_visual_events(motion_points, event_mode, entropy_k)
    all_text_nodes = build_text_nodes(aligned_rows)
    temporal_edges = build_temporal_edges(events, all_text_nodes)
    linked_text_ids = {str(edge["target"]) for edge in temporal_edges if safe_text(edge.get("target"))}
    text_nodes = [node for node in all_text_nodes if str(node.get("id")) in linked_text_ids]
    visual_edges = build_visual_edges(events)
    lexical_edges = build_lexical_edges(text_nodes)
    all_edges = temporal_edges + visual_edges + lexical_edges
    all_nodes = events + text_nodes
    summary = build_summary(events, text_nodes, all_edges, threshold_stats)
    return all_nodes, all_edges, summary


def export_noeuds(
    aligned_csv: str | Path,
    motion_frames_csv: str | Path,
    output_dir: str | Path,
    event_mode: str = "threshold",
    entropy_k: float = 1.0,
) -> dict[str, Any]:
    destination = ensure_directory(output_dir)
    aligned_rows = read_csv_rows(aligned_csv)
    motion_rows = read_csv_rows(motion_frames_csv)
    nodes, edges, summary = build_graph(aligned_rows, motion_rows, event_mode, entropy_k)

    graph_payload = {
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
    }

    graph_json = destination / "noeuds_graphe.json"
    summary_json = destination / "noeuds_summary.json"
    nodes_csv = destination / "noeuds_noeuds.csv"
    edges_csv = destination / "noeuds_liens.csv"

    write_json(graph_json, graph_payload)
    write_json(summary_json, summary)
    write_csv(nodes_csv, nodes)
    write_csv(edges_csv, edges)

    return {
        "graph_json": str(graph_json),
        "summary_json": str(summary_json),
        "nodes_csv": str(nodes_csv),
        "edges_csv": str(edges_csv),
        "summary": summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit un graphe multimodal reliant événements visuels à forte entropie et segments de texte synchronisés."
    )
    parser.add_argument("--aligned-csv", required=True, help="CSV d'alignement complet.")
    parser.add_argument("--motion-frames-csv", required=True, help="CSV mouvements_frames complet.")
    parser.add_argument(
        "--event-mode",
        choices=("threshold", "local-peaks"),
        default="threshold",
        help="Mode de sélection : seuil moyenne + k × écart-type, ou pics locaux.",
    )
    parser.add_argument("--entropy-k", type=float, default=1.0, help="Seuil des événements : moyenne + k × écart-type.")
    parser.add_argument("--output-dir", default="multimodale/exports/noeuds", help="Dossier d'export.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = export_noeuds(args.aligned_csv, args.motion_frames_csv, args.output_dir, args.event_mode, args.entropy_k)
    print(f"Graphe noeuds : {result['graph_json']}")
    print(f"Résumé noeuds : {result['summary_json']}")
    print(f"Noeuds CSV : {result['nodes_csv']}")
    print(f"Liens CSV : {result['edges_csv']}")


if __name__ == "__main__":
    main()
