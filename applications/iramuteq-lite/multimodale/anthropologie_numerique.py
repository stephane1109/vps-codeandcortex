from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any

from multimodale.common import write_json
from multimodale.visualisations import altair_available, configure_chart, save_chart

try:
    import altair as alt
except ImportError:  # pragma: no cover - dependance externe
    alt = None

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - dependance externe
    raise RuntimeError("numpy est requis pour multimodale/anthropologie_numerique.py") from exc


MAX_DIRECTIONAL_ENTROPY = float(math.log2(12.0))


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


def read_csv_rows(path: str | Path | None) -> list[dict[str, str]]:
    if not path:
        return []
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return []
    with candidate.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return [dict(row) for row in reader]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def minmax_normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0
    return clamp01((float(value) - minimum) / (maximum - minimum))


def overlap_duration(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def label_strength(score: float) -> str:
    if score < 0.33:
        return "faible"
    if score < 0.66:
        return "moyenne"
    return "forte"


def classify_multimodal_state(row: dict[str, Any]) -> str:
    speech_present = bool(row.get("presence_parole"))
    anomaly_flag = bool(row.get("anomalie_audio"))
    movement_norm = float(row.get("mouvement_norm", 0.0) or 0.0)
    entropy_norm = float(row.get("entropie_directionnelle_norm", 0.0) or 0.0)
    discordance = float(row.get("discordance_multimodale", 0.0) or 0.0)
    coupling = float(row.get("couplage_mouvement_parole", 0.0) or 0.0)
    pause_sec = float(row.get("pause_max_sec", 0.0) or 0.0)

    if not speech_present and anomaly_flag:
        return "pause avec anomalie audio"
    if not speech_present and pause_sec >= 1.0 and movement_norm < 0.35:
        return "pause stable"
    if not speech_present and movement_norm >= 0.35:
        return "pause sous tension"
    if speech_present and anomaly_flag and discordance >= 0.55:
        return "discordance audio-motrice"
    if speech_present and discordance >= 0.6:
        return "discordance multimodale"
    if speech_present and coupling >= 0.66 and entropy_norm < 0.45:
        return "parole cadrée"
    if speech_present and movement_norm >= 0.55 and entropy_norm >= 0.55:
        return "parole dispersée"
    if speech_present and movement_norm < 0.33:
        return "parole contenue"
    if speech_present:
        return "parole en variation"
    return "etat indetermine"


def state_color_scale() -> alt.Scale | None:
    if alt is None:
        return None
    return alt.Scale(
        domain=[
            "pause stable",
            "pause sous tension",
            "pause avec anomalie audio",
            "parole contenue",
            "parole cadrée",
            "parole en variation",
            "parole dispersée",
            "discordance multimodale",
            "discordance audio-motrice",
            "etat indetermine",
        ],
        range=[
            "#5b6f8f",
            "#d98f4e",
            "#b82126",
            "#7d8f5b",
            "#3b7f6e",
            "#5f5aa2",
            "#8f5bb3",
            "#c95b7d",
            "#a33b52",
            "#9f9f9f",
        ],
    )


def build_anthropology_timeline_chart(rows: list[dict[str, Any]], output_path: str | Path) -> str:
    if not rows or not altair_available():
        return ""

    values = []
    for row in rows:
        values.append(
            {
                **row,
                "lane": "Etat multimodal",
                "tooltip_rupture": to_float(row.get("rupture_score", 0.0)),
                "tooltip_couplage": to_float(row.get("couplage_mouvement_parole", 0.0)),
                "tooltip_discordance": to_float(row.get("discordance_multimodale", 0.0)),
            }
        )

    chart = (
        alt.Chart(alt.Data(values=values))
        .mark_bar(size=34)
        .encode(
            x=alt.X("start_sec:Q", title="Temps (s)"),
            x2="end_sec:Q",
            y=alt.Y(
                "lane:N",
                title=None,
                axis=alt.Axis(labels=False, ticks=False, domain=False),
            ),
            color=alt.Color("etat_multimodal:N", title="Etat", scale=state_color_scale()),
            tooltip=[
                alt.Tooltip("window_id:Q", title="Fenetre"),
                alt.Tooltip("start_sec:Q", title="Debut", format=".2f"),
                alt.Tooltip("end_sec:Q", title="Fin", format=".2f"),
                alt.Tooltip("etat_multimodal:N", title="Etat"),
                alt.Tooltip("densite_textuelle:Q", title="Densite textuelle", format=".2f"),
                alt.Tooltip("anomalie_audio:N", title="Anomalie audio"),
                alt.Tooltip("lecture_couplage:N", title="Couplage"),
                alt.Tooltip("lecture_rupture:N", title="Rupture"),
                alt.Tooltip("tooltip_rupture:Q", title="Score rupture", format=".3f"),
                alt.Tooltip("tooltip_couplage:Q", title="Couplage score", format=".3f"),
                alt.Tooltip("tooltip_discordance:Q", title="Discordance", format=".3f"),
            ],
        )
    )
    chart = configure_chart(chart.properties(height=92), "Anthropologie numerique · Etats multimodaux")
    return save_chart(chart, output_path)


def build_rupture_chart(rows: list[dict[str, Any]], threshold: float, output_path: str | Path) -> str:
    if not rows or not altair_available():
        return ""

    values = []
    for row in rows:
        values.append(
            {
                **row,
                "mid_sec": (to_float(row.get("start_sec")) + to_float(row.get("end_sec"))) / 2.0,
                "rupture_score": to_float(row.get("rupture_score", 0.0)),
                "threshold": threshold,
                "flag_label": "rupture" if str(row.get("rupture_flag", "")).lower() == "oui" else "continuite",
            }
        )

    base = alt.Chart(alt.Data(values=values)).encode(
        x=alt.X("mid_sec:Q", title="Temps (s)"),
        y=alt.Y("rupture_score:Q", title="Score de rupture"),
        tooltip=[
            alt.Tooltip("window_id:Q", title="Fenetre"),
            alt.Tooltip("mid_sec:Q", title="Centre", format=".2f"),
            alt.Tooltip("rupture_score:Q", title="Rupture", format=".3f"),
            alt.Tooltip("flag_label:N", title="Lecture"),
            alt.Tooltip("etat_multimodal:N", title="Etat"),
        ],
    )

    line = base.mark_line(color="#4f6d8a", point=False)
    points = base.mark_point(size=85, filled=True).encode(
        color=alt.Color(
            "flag_label:N",
            scale=alt.Scale(domain=["continuite", "rupture"], range=["#8aa4bf", "#b82126"]),
            title="Lecture",
        )
    )
    threshold_rule = (
        alt.Chart(alt.Data(values=[{"threshold": threshold}]))
        .mark_rule(color="#b2663b", strokeDash=[6, 4])
        .encode(y="threshold:Q")
    )
    chart = configure_chart(
        alt.layer(line, points, threshold_rule).properties(height=220),
        "Anthropologie numerique · Ruptures de regime",
    )
    return save_chart(chart, output_path)


def build_phase1_rows(
    window_rows: list[dict[str, Any]],
    segment_rows: list[dict[str, str]],
    anomaly_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not window_rows:
        return []

    parsed_segments = []
    for row in segment_rows:
        start_sec = to_float(row.get("start_sec"))
        end_sec = to_float(row.get("end_sec"), start_sec)
        duration_sec = max(0.0, end_sec - start_sec)
        parsed_segments.append(
            {
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": duration_sec,
                "word_count": to_float(row.get("word_count")),
                "words_per_sec": to_float(row.get("words_per_sec")),
                "pause_before_sec": to_float(row.get("pause_before_sec")),
                "text": str(row.get("text", "") or "").strip(),
            }
        )

    parsed_anomalies = []
    for row in anomaly_rows:
        if str(row.get("anomaly_flag", "")).strip().lower() != "oui":
            continue
        parsed_anomalies.append(
            {
                "start_sec": to_float(row.get("start_sec")),
                "end_sec": to_float(row.get("end_sec")),
            }
        )

    raw_rows: list[dict[str, Any]] = []
    motion_energy_values: list[float] = []
    text_density_values: list[float] = []

    for window in window_rows:
        start_sec = to_float(window.get("start_sec"))
        end_sec = to_float(window.get("end_sec"))
        duration_sec = max(0.25, end_sec - start_sec)
        motion_energy = to_float(window.get("roi_motion_energy")) or to_float(window.get("motion_mean"))
        active_ratio = clamp01(to_float(window.get("roi_active_ratio"), to_float(window.get("motion_active_ratio"))))
        entropy_value = max(0.0, to_float(window.get("roi_directional_entropy")))
        entropy_norm = clamp01(entropy_value / MAX_DIRECTIONAL_ENTROPY) if MAX_DIRECTIONAL_ENTROPY > 0 else 0.0

        overlapping_segments = []
        words_in_window = 0.0
        chars_in_window = 0.0
        pause_values: list[float] = []
        speech_seconds = 0.0
        texts: list[str] = []
        for segment in parsed_segments:
            overlap_sec = overlap_duration(start_sec, end_sec, segment["start_sec"], segment["end_sec"])
            if overlap_sec <= 0:
                continue
            overlapping_segments.append(segment)
            duration = max(segment["duration_sec"], 1e-6)
            ratio = clamp01(overlap_sec / duration)
            words_in_window += segment["word_count"] * ratio
            chars_in_window += len(segment["text"]) * ratio
            speech_seconds += overlap_sec
            if segment["text"]:
                texts.append(segment["text"])
            if segment["pause_before_sec"] > 0 and start_sec <= segment["start_sec"] <= end_sec:
                pause_values.append(segment["pause_before_sec"])

        overlapping_anomalies = [
            anomaly
            for anomaly in parsed_anomalies
            if overlap_duration(start_sec, end_sec, anomaly["start_sec"], anomaly["end_sec"]) > 0
        ]

        text_density = words_in_window / duration_sec
        speech_ratio = clamp01(speech_seconds / duration_sec)
        pause_max_sec = max(pause_values) if pause_values else 0.0
        pause_norm = clamp01(pause_max_sec / 3.0)

        raw_rows.append(
            {
                "window_id": int(to_float(window.get("window_id"))),
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "frame_samples": int(to_float(window.get("frame_samples"))),
                "keyframe_path": str(window.get("keyframe_path", "") or ""),
                "movement_energy": round(motion_energy, 6),
                "movement_active_ratio": round(active_ratio, 6),
                "direction_label": str(window.get("dominant_direction", "") or "").strip(),
                "directional_entropy": round(entropy_value, 6),
                "entropie_directionnelle_norm": round(entropy_norm, 6),
                "presence_parole": bool(overlapping_segments),
                "speech_ratio": round(speech_ratio, 6),
                "densite_textuelle": round(text_density, 6),
                "densite_caracteres": round(chars_in_window / duration_sec, 6),
                "pause_max_sec": round(pause_max_sec, 6),
                "pause_norm": round(pause_norm, 6),
                "anomalie_audio": bool(overlapping_anomalies),
                "anomalie_audio_count": len(overlapping_anomalies),
                "texte_fenetre": " ".join(texts).strip(),
            }
        )
        motion_energy_values.append(motion_energy)
        text_density_values.append(text_density)

    motion_min = min(motion_energy_values) if motion_energy_values else 0.0
    motion_max = max(motion_energy_values) if motion_energy_values else 1.0
    text_min = min(text_density_values) if text_density_values else 0.0
    text_max = max(text_density_values) if text_density_values else 1.0

    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        movement_norm = minmax_normalize(row["movement_energy"], motion_min, motion_max)
        speech_norm = minmax_normalize(row["densite_textuelle"], text_min, text_max) if text_density_values else 0.0
        has_text_reference = bool(text_density_values and text_max > text_min)
        if row["presence_parole"] and has_text_reference:
            coupling = clamp01(1.0 - abs(movement_norm - speech_norm))
            discordance = clamp01(abs(movement_norm - speech_norm) + (0.22 if row["anomalie_audio"] else 0.0))
        elif row["presence_parole"]:
            coupling = clamp01(0.45 + (0.25 * (1.0 - row["entropie_directionnelle_norm"])))
            discordance = clamp01(abs(movement_norm - row["speech_ratio"]))
        else:
            coupling = 0.0
            discordance = clamp01((0.35 * movement_norm) + (0.4 if row["anomalie_audio"] else 0.0))

        enriched = {
            **row,
            "mouvement_norm": round(movement_norm, 6),
            "parole_norm": round(speech_norm if row["presence_parole"] else 0.0, 6),
            "couplage_mouvement_parole": round(coupling, 6),
            "discordance_multimodale": round(discordance, 6),
        }
        enriched["etat_multimodal"] = classify_multimodal_state(enriched)
        enriched["lecture_couplage"] = label_strength(coupling) if row["presence_parole"] else "non calcule"
        enriched["lecture_discordance"] = label_strength(discordance)
        rows.append(enriched)

    return rows


def build_phase1_transitions(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    if not rows:
        return [], 0.0

    vectors = []
    for row in rows:
        vectors.append(
            np.array(
                [
                    to_float(row.get("mouvement_norm")),
                    to_float(row.get("entropie_directionnelle_norm")),
                    to_float(row.get("movement_active_ratio")),
                    to_float(row.get("parole_norm")),
                    to_float(row.get("pause_norm")),
                    1.0 if row.get("anomalie_audio") else 0.0,
                ],
                dtype=np.float32,
            )
        )

    rupture_scores = [0.0]
    for index in range(1, len(vectors)):
        delta = vectors[index] - vectors[index - 1]
        score = float(np.linalg.norm(delta) / math.sqrt(float(delta.size)))
        rupture_scores.append(clamp01(score))

    if len(rupture_scores) > 1:
        threshold = max(0.42, float(np.mean(rupture_scores[1:]) + np.std(rupture_scores[1:])))
        threshold = clamp01(threshold)
    else:
        threshold = 0.0

    transitions: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        rupture_score = round(rupture_scores[index], 6)
        rupture_flag = "oui" if index > 0 and rupture_score >= threshold else "non"
        row["rupture_score"] = rupture_score
        row["rupture_flag"] = rupture_flag
        row["lecture_rupture"] = "rupture" if rupture_flag == "oui" else "continuite"
        if index == 0:
            transitions.append(
                {
                    "window_id_from": "",
                    "window_id_to": row["window_id"],
                    "etat_from": "",
                    "etat_to": row["etat_multimodal"],
                    "rupture_score": rupture_score,
                    "rupture_flag": rupture_flag,
                    "transition_type": "depart",
                }
            )
            continue
        previous = rows[index - 1]
        transitions.append(
            {
                "window_id_from": previous["window_id"],
                "window_id_to": row["window_id"],
                "etat_from": previous["etat_multimodal"],
                "etat_to": row["etat_multimodal"],
                "rupture_score": rupture_score,
                "rupture_flag": rupture_flag,
                "transition_type": "changement" if previous["etat_multimodal"] != row["etat_multimodal"] else "stabilite",
            }
        )

    return transitions, threshold


def compute_phase1_anthropology(
    *,
    window_rows: list[dict[str, Any]],
    destination_dir: str | Path,
    audio_dir: str | Path | None = None,
) -> dict[str, Any]:
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)

    segment_rows: list[dict[str, str]] = []
    anomaly_rows: list[dict[str, str]] = []
    if audio_dir:
        audio_base = Path(audio_dir)
        segment_rows = read_csv_rows(audio_base / "segments_texte_global_complet.csv")
        if not segment_rows:
            segment_rows = read_csv_rows(audio_base / "segments_texte_global.csv")
        anomaly_rows = read_csv_rows(audio_base / "audio_anomalies_complet.csv")
        if not anomaly_rows:
            anomaly_rows = read_csv_rows(audio_base / "audio_anomalies.csv")

    state_rows = build_phase1_rows(window_rows, segment_rows, anomaly_rows)
    transitions, threshold = build_phase1_transitions(state_rows)

    timeline_path = build_anthropology_timeline_chart(state_rows, destination / "anthropologie_timeline_altair.png")
    ruptures_path = build_rupture_chart(state_rows, threshold, destination / "anthropologie_ruptures_altair.png")

    state_counter = Counter(str(row.get("etat_multimodal", "") or "") for row in state_rows)
    coupling_values = [to_float(row.get("couplage_mouvement_parole")) for row in state_rows if row.get("presence_parole")]
    discordance_values = [to_float(row.get("discordance_multimodale")) for row in state_rows]
    rupture_values = [to_float(row.get("rupture_score")) for row in state_rows]

    summary = {
        "window_count": len(state_rows),
        "audio_segments_available": bool(segment_rows),
        "audio_anomalies_available": bool(anomaly_rows),
        "etat_dominant": state_counter.most_common(1)[0][0] if state_counter else "",
        "rupture_threshold": round(float(threshold), 6),
        "rupture_count": sum(1 for row in state_rows if str(row.get("rupture_flag", "")).lower() == "oui"),
        "couplage_mouvement_parole_moyen": round(float(np.mean(coupling_values)), 6) if coupling_values else None,
        "discordance_multimodale_moyenne": round(float(np.mean(discordance_values)), 6) if discordance_values else None,
        "rupture_score_moyen": round(float(np.mean(rupture_values)), 6) if rupture_values else 0.0,
        "state_counts": dict(state_counter),
        "lecture": {
            "etat_multimodal": "Configuration synthetique de la fenetre : pause, parole, dispersion ou discordance.",
            "couplage_mouvement_parole": "Proximite entre dynamique du mouvement et densite de parole sur une meme fenetre.",
            "discordance_multimodale": "Ecart entre canaux. Monte quand mouvement, parole et anomalie audio divergent.",
            "rupture_score": "Variation entre deux fenetres consecutives. Plus le score est eleve, plus le regime change.",
        },
    }

    write_csv(destination / "anthropologie_windows.csv", state_rows)
    write_csv(destination / "anthropologie_transitions.csv", transitions)
    write_json(destination / "anthropologie_summary.json", summary)

    return {
        "windows_csv": str(destination / "anthropologie_windows.csv"),
        "transitions_csv": str(destination / "anthropologie_transitions.csv"),
        "summary_json": str(destination / "anthropologie_summary.json"),
        "timeline_png": timeline_path,
        "ruptures_png": ruptures_path,
        "window_count": len(state_rows),
        "audio_segments_available": bool(segment_rows),
        "audio_anomalies_available": bool(anomaly_rows),
    }
