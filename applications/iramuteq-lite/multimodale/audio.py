from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    clip_video_interval,
    ensure_directory,
    extract_audio_wav,
    is_youtube_url,
    probe_duration_seconds,
    resolve_media_source,
    utc_session_id,
    write_json,
    write_jsonl,
)
from multimodale.visualisations import altair_available, save_chart

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - dépendance externe
    raise RuntimeError("numpy est requis pour multimodale/audio.py") from exc

try:
    import librosa
except ImportError:  # pragma: no cover - dépendance externe
    librosa = None


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ'-]+\b", text or "", flags=re.UNICODE))


def normalise_word_timestamps(raw_words: Any) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    if not raw_words:
        return words
    for item in raw_words:
        try:
            if isinstance(item, dict):
                start = float(item.get("start", 0.0) or 0.0)
                end = float(item.get("end", start) or start)
                text = str(item.get("word", "") or item.get("text", "") or "").strip()
                probability = item.get("probability")
            else:
                start = float(getattr(item, "start", 0.0) or 0.0)
                end = float(getattr(item, "end", start) or start)
                text = str(getattr(item, "word", "") or getattr(item, "text", "") or "").strip()
                probability = getattr(item, "probability", None)
            if end < start:
                end = start
            if not text:
                continue
            words.append(
                {
                    "start_sec": round(start, 6),
                    "end_sec": round(end, 6),
                    "duration_sec": round(max(0.0, end - start), 6),
                    "word": text,
                    "probability": round(float(probability), 6) if probability not in ("", None) else "",
                }
            )
        except Exception:
            continue
    return words


def normalise_whisper_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(raw_segments, start=1):
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)
        text = str(item.get("text", "") or "").strip()
        word_rows = normalise_word_timestamps(item.get("words"))
        if end < start:
            end = start
        segments.append(
            {
                "segment_id": index,
                "start_sec": round(start, 6),
                "end_sec": round(end, 6),
                "duration_sec": round(max(0.0, end - start), 6),
                "text": text,
                "word_count": count_words(text),
                "word_timestamps_count": len(word_rows),
                "word_timestamps_json": json.dumps(word_rows, ensure_ascii=False),
                "avg_logprob": item.get("avg_logprob"),
                "no_speech_prob": item.get("no_speech_prob"),
            }
        )
    return segments


def transcribe_with_faster_whisper(
    audio_path: str | Path,
    model_name: str,
    language: str,
    device: str,
    compute_type: str,
    word_timestamps: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from faster_whisper import WhisperModel  # pragma: no cover - dépendance externe

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    iterator, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=word_timestamps,
        vad_filter=True,
    )

    segments = []
    for segment in iterator:
        segments.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text,
                "words": [
                    {
                        "start": float(getattr(word, "start", 0.0) or 0.0),
                        "end": float(getattr(word, "end", getattr(word, "start", 0.0)) or 0.0),
                        "word": str(getattr(word, "word", "") or "").strip(),
                        "probability": getattr(word, "probability", None),
                    }
                    for word in (getattr(segment, "words", None) or [])
                ],
                "avg_logprob": getattr(segment, "avg_logprob", None),
                "no_speech_prob": getattr(segment, "no_speech_prob", None),
            }
        )

    metadata = {
        "backend": "faster-whisper",
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
    }
    return segments, metadata


def transcribe_with_openai_whisper(
    audio_path: str | Path,
    model_name: str,
    language: str,
    word_timestamps: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import whisper  # pragma: no cover - dépendance externe

    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=word_timestamps,
        verbose=False,
    )

    metadata = {
        "backend": "openai-whisper",
        "language": result.get("language", language),
    }
    return result.get("segments", []), metadata


def transcribe_audio(
    audio_path: str | Path,
    model_name: str = "small",
    language: str = "fr",
    device: str = "auto",
    compute_type: str = "auto",
    word_timestamps: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Lance Whisper avec une stratégie de repli :
    1. faster-whisper
    2. openai-whisper
    """
    last_error: Exception | None = None
    try:
        return transcribe_with_faster_whisper(
            audio_path=audio_path,
            model_name=model_name,
            language=language,
            device=device,
            compute_type=compute_type,
            word_timestamps=word_timestamps,
        )
    except Exception as exc:  # pragma: no cover - dépendances externes
        last_error = exc

    try:
        return transcribe_with_openai_whisper(
            audio_path=audio_path,
            model_name=model_name,
            language=language,
            word_timestamps=word_timestamps,
        )
    except Exception as exc:  # pragma: no cover - dépendances externes
        last_error = exc

    raise RuntimeError(
        "Impossible de lancer Whisper. Installez `faster-whisper` ou `openai-whisper`."
    ) from last_error


def audio_feature_stats(
    signal: np.ndarray,
    sr: int,
    amplitude_filter_k: float | None = None,
) -> dict[str, float | None]:
    """Indicateurs audio simples et utiles pour un usage SHS."""
    if signal.size == 0:
        return {
            "rms_mean": None,
            "rms_std": None,
            "peak_dbfs": None,
            "zcr_mean": None,
            "spectral_centroid_mean": None,
            "onset_strength_mean": None,
            "silence_ratio": None,
            "amplitude_filter_k": None,
            "amplitude_filter_window_sec": None,
            "amplitude_outlier_ratio": None,
        }

    filtered_signal = signal
    filter_meta = {
        "amplitude_filter_k": None,
        "amplitude_filter_window_sec": None,
        "amplitude_outlier_ratio": None,
    }
    if amplitude_filter_k is not None and np.isfinite(amplitude_filter_k) and amplitude_filter_k >= 0:
        filtered_signal, filter_meta = filter_atypical_amplitudes(signal, sr, amplitude_filter_k)

    if librosa is None:
        peak = float(np.max(np.abs(filtered_signal))) if filtered_signal.size else 0.0
        peak_dbfs = 20.0 * math.log10(max(peak, 1e-12))
        return {
            "rms_mean": None,
            "rms_std": None,
            "peak_dbfs": round(peak_dbfs, 6),
            "zcr_mean": None,
            "spectral_centroid_mean": None,
            "onset_strength_mean": None,
            "silence_ratio": None,
            **filter_meta,
        }

    rms = librosa.feature.rms(y=filtered_signal)[0]
    zcr = librosa.feature.zero_crossing_rate(signal)[0]
    centroid = librosa.feature.spectral_centroid(y=signal, sr=sr)[0]
    onset = librosa.onset.onset_strength(y=signal, sr=sr)
    intervals = librosa.effects.split(signal, top_db=35)
    voiced = sum(int(end - start) for start, end in intervals)
    silence_ratio = 1.0 - (voiced / max(1, signal.size))
    peak = float(np.max(np.abs(filtered_signal))) if filtered_signal.size else 0.0
    peak_dbfs = 20.0 * math.log10(max(peak, 1e-12))

    return {
        "rms_mean": round(float(np.mean(rms)), 6),
        "rms_std": round(float(np.std(rms)), 6),
        "peak_dbfs": round(peak_dbfs, 6),
        "zcr_mean": round(float(np.mean(zcr)), 6),
        "spectral_centroid_mean": round(float(np.mean(centroid)), 6),
        "onset_strength_mean": round(float(np.mean(onset)) if onset.size else 0.0, 6),
        "silence_ratio": round(float(silence_ratio), 6),
        **filter_meta,
    }


def filter_atypical_amplitudes(
    signal: np.ndarray,
    sr: int,
    k: float,
    window_sec: float = 1.0,
) -> tuple[np.ndarray, dict[str, float | None]]:
    if signal.size == 0 or sr <= 0 or not np.isfinite(k) or k < 0:
        return signal, {
            "amplitude_filter_k": None,
            "amplitude_filter_window_sec": None,
            "amplitude_outlier_ratio": None,
        }

    filtered = np.array(signal, copy=True)
    window_size = max(1, int(round(float(sr) * max(window_sec, 0.1))))
    removed_count = 0

    for start_idx in range(0, filtered.size, window_size):
        end_idx = min(filtered.size, start_idx + window_size)
        window_signal = filtered[start_idx:end_idx]
        if window_signal.size == 0:
            continue
        mu = float(np.mean(window_signal))
        sigma = float(np.std(window_signal))
        lower = mu - (k * sigma)
        upper = mu + (k * sigma)
        keep_mask = (window_signal >= lower) & (window_signal <= upper)
        if not np.any(keep_mask):
            keep_mask = np.ones_like(window_signal, dtype=bool)
        removed_count += int(keep_mask.size - np.count_nonzero(keep_mask))
        filtered[start_idx:end_idx] = np.where(keep_mask, window_signal, 0.0)

    return filtered, {
        "amplitude_filter_k": round(float(k), 6),
        "amplitude_filter_window_sec": round(float(window_sec), 6),
        "amplitude_outlier_ratio": round(float(removed_count) / max(1, filtered.size), 6),
    }


def enrich_segments_with_audio_indicators(
    segments: list[dict[str, Any]],
    waveform: np.ndarray | None,
    sample_rate: int | None,
    amplitude_filter_k: float | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    previous_end = 0.0

    for index, segment in enumerate(segments):
        start = float(segment["start_sec"])
        end = float(segment["end_sec"])
        pause_before = max(0.0, start - previous_end)
        next_start = float(segments[index + 1]["start_sec"]) if index + 1 < len(segments) else end
        pause_after = max(0.0, next_start - end)

        current = dict(segment)
        current["pause_before_sec"] = round(pause_before, 6)
        current["pause_after_sec"] = round(pause_after, 6)
        current["words_per_sec"] = round(
            current["word_count"] / current["duration_sec"], 6
        ) if current["duration_sec"] > 0 else None

        if waveform is not None and sample_rate:
            start_idx = max(0, int(start * sample_rate))
            end_idx = max(start_idx, int(end * sample_rate))
            segment_signal = waveform[start_idx:end_idx]
            current.update(audio_feature_stats(segment_signal, sample_rate, amplitude_filter_k))
        else:
            current.update(audio_feature_stats(np.array([], dtype=float), 1, amplitude_filter_k))

        enriched.append(current)
        previous_end = end

    return enriched


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with destination.open("w", encoding="utf-8", newline="") as stream:
            stream.write("")
        return

    fieldnames = list(rows[0].keys())
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def remove_file_if_exists(path: str | Path) -> None:
    target = Path(path)
    try:
        target.unlink()
    except FileNotFoundError:
        return


def project_rows(rows: list[dict[str, Any]], preferred_columns: list[str]) -> list[dict[str, Any]]:
    if not rows:
        return []

    available_columns: set[str] = set()
    for row in rows:
        available_columns.update(row.keys())
    selected_columns = [column for column in preferred_columns if column in available_columns]
    return [{column: row.get(column, "") for column in selected_columns} for row in rows]


def write_csv_variants(
    path: str | Path,
    rows: list[dict[str, Any]],
    essential_columns: list[str],
    *,
    write_legacy: bool = True,
) -> tuple[str, str, str]:
    destination = Path(path)
    legacy_path = destination
    complete_path = destination.with_name(f"{destination.stem}_complet{destination.suffix}")
    essential_path = destination.with_name(f"{destination.stem}_essentiel{destination.suffix}")
    essential_rows = project_rows(rows, essential_columns)
    if write_legacy:
        write_csv(legacy_path, rows)
    write_csv(complete_path, rows)
    write_csv(essential_path, essential_rows)
    return (str(legacy_path) if write_legacy else "", str(complete_path), str(essential_path))


AUDIO_SEGMENT_ESSENTIAL_COLUMNS = [
    "segment_id",
    "start_sec",
    "end_sec",
    "duration_sec",
    "text",
    "word_count",
    "pause_before_sec",
    "pause_after_sec",
    "words_per_sec",
    "rms_mean",
    "peak_dbfs",
]

AUDIO_ANOMALY_ESSENTIAL_COLUMNS = [
    "window_id",
    "time_sec",
    "start_sec",
    "end_sec",
    "anomaly_flag",
    "mean_amp",
    "z_score",
]

AUDIO_ANOMALY_CONCORDANCIER_ESSENTIAL_COLUMNS = [
    "window_id",
    "timestamp_sec",
    "anomaly_start_sec",
    "anomaly_end_sec",
    "segment_id",
    "segment_start_sec",
    "segment_end_sec",
    "text",
]

AUDIO_PAUSE_ESSENTIAL_COLUMNS = [
    "pause_id",
    "start_sec",
    "end_sec",
    "center_sec",
    "duration_sec",
]


def write_timestamped_segments_text(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for row in rows:
        start_sec = float(row.get("start_sec", 0.0) or 0.0)
        end_sec = float(row.get("end_sec", start_sec) or start_sec)
        text = str(row.get("text", "") or "").strip()
        segment_id = row.get("segment_id", "")
        lines.append(
            f"[Segment {segment_id}] [{start_sec:.3f}s -> {end_sec:.3f}s] {text}".rstrip()
        )

    destination.write_text("\n".join(lines), encoding="utf-8")


def write_word_timestamped_segments_text(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for row in rows:
        segment_id = row.get("segment_id", "")
        text = str(row.get("text", "") or "").strip()
        lines.append(f"[Segment {segment_id}] {text}".rstrip())
        try:
            words = json.loads(str(row.get("word_timestamps_json", "") or "[]"))
        except Exception:
            words = []
        for word in words if isinstance(words, list) else []:
            try:
                start_sec = float(word.get("start_sec", 0.0) or 0.0)
                end_sec = float(word.get("end_sec", start_sec) or start_sec)
                word_text = str(word.get("word", "") or "").strip()
            except Exception:
                continue
            if not word_text:
                continue
            lines.append(f"  [{start_sec:.3f}s -> {end_sec:.3f}s] {word_text}")
        lines.append("")

    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_audio_segment_rows(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in segments:
        rows.append(
            {
                "segment_id": int(row.get("segment_id", 0) or 0),
                "start_sec": float(row.get("start_sec", 0.0) or 0.0),
                "pause_before_sec": float(row.get("pause_before_sec", 0.0) or 0.0),
                "words_per_sec": float(row.get("words_per_sec", 0.0) or 0.0),
                "rms_mean": float(row.get("rms_mean", 0.0) or 0.0),
                "peak_dbfs": float(row.get("peak_dbfs", 0.0) or 0.0),
                "text": str(row.get("text", "") or ""),
            }
        )
    return rows


def detect_silence_rows(
    waveform: np.ndarray | None,
    sample_rate: int | None,
    top_db: float = 35.0,
    min_pause_sec: float = 0.15,
) -> list[dict[str, float]]:
    if (
        waveform is None
        or sample_rate is None
        or sample_rate <= 0
        or waveform.size == 0
        or librosa is None
    ):
        return []

    nonsilent_intervals = librosa.effects.split(waveform, top_db=top_db)
    total_samples = int(waveform.size)
    previous_end = 0
    silence_rows: list[dict[str, float]] = []

    def append_silence(start_sample: int, end_sample: int) -> None:
        duration_sec = max(0.0, (end_sample - start_sample) / sample_rate)
        if duration_sec < min_pause_sec:
            return
        start_sec = start_sample / sample_rate
        end_sec = end_sample / sample_rate
        silence_rows.append(
            {
                "pause_id": len(silence_rows) + 1,
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "center_sec": round((start_sec + end_sec) / 2.0, 6),
                "duration_sec": round(duration_sec, 6),
            }
        )

    for start_sample, end_sample in nonsilent_intervals:
        if start_sample > previous_end:
            append_silence(previous_end, int(start_sample))
        previous_end = max(previous_end, int(end_sample))

    if previous_end < total_samples:
        append_silence(previous_end, total_samples)

    return silence_rows


def build_audio_pauses_chart(
    waveform: np.ndarray | None,
    sample_rate: int | None,
    output_path: str | Path,
) -> str:
    if not altair_available():
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    rows = detect_silence_rows(waveform, sample_rate)
    if not rows:
        return ""

    chart = (
        alt.Chart(alt.Data(values=rows))
        .mark_bar(color="#c45a5a", opacity=0.82)
        .encode(
            x=alt.X("start_sec:Q", title="Début du silence (s)"),
            y=alt.Y("duration_sec:Q", title="Durée du silence (s)"),
            tooltip=[
                alt.Tooltip("pause_id:Q", title="Silence"),
                alt.Tooltip("start_sec:Q", title="Début (s)", format=".3f"),
                alt.Tooltip("end_sec:Q", title="Fin (s)", format=".3f"),
                alt.Tooltip("duration_sec:Q", title="Durée (s)", format=".3f"),
            ],
        )
        .properties(width=780, height=250, title="Silences détectés dans le signal")
        .configure(background="#ffffff")
        .configure_view(stroke="#d9d9d9")
        .configure_axis(
            labelColor="#1f1f1f",
            titleColor="#1f1f1f",
            gridColor="#e8ddd4",
            domainColor="#8a6e5a",
            tickColor="#8a6e5a",
        )
        .configure_title(fontSize=18, color="#1f1f1f", anchor="start")
    )
    return save_chart(chart, output_path)


def build_audio_speech_rate_chart(segments: list[dict[str, Any]], output_path: str | Path) -> str:
    if not segments or not altair_available():
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    rows = build_audio_segment_rows(segments)
    chart = (
        alt.Chart(alt.Data(values=rows))
        .mark_line(color="#2d6f9f", point={"size": 40, "filled": True})
        .encode(
            x=alt.X("start_sec:Q", title="Temps (s)"),
            y=alt.Y("words_per_sec:Q", title="Mots par seconde"),
            tooltip=[
                alt.Tooltip("segment_id:Q", title="Segment"),
                alt.Tooltip("words_per_sec:Q", title="Débit", format=".3f"),
                alt.Tooltip("rms_mean:Q", title="RMS", format=".4f"),
                alt.Tooltip("peak_dbfs:Q", title="Pic dBFS", format=".2f"),
                alt.Tooltip("text:N", title="Texte"),
            ],
        )
        .properties(width=780, height=250, title="Débit de parole")
        .configure(background="#ffffff")
        .configure_view(stroke="#d9d9d9")
        .configure_axis(
            labelColor="#1f1f1f",
            titleColor="#1f1f1f",
            gridColor="#e8ddd4",
            domainColor="#8a6e5a",
            tickColor="#8a6e5a",
        )
        .configure_title(fontSize=18, color="#1f1f1f", anchor="start")
    )
    return save_chart(chart, output_path)


def build_waveform_rows(
    waveform: np.ndarray | None,
    sample_rate: int | None,
) -> list[dict[str, float]]:
    if waveform is None or sample_rate is None or sample_rate <= 0 or waveform.size == 0:
        return []

    chunk_size = int(sample_rate)
    if chunk_size <= 0:
        return []

    nb_bins = waveform.size // chunk_size
    rows: list[dict[str, float]] = []
    for bin_index in range(nb_bins):
        start_idx = bin_index * chunk_size
        end_idx = min(waveform.size, start_idx + chunk_size)
        chunk = waveform[start_idx:end_idx]
        if chunk.size == 0:
            continue
        amp_min = float(np.min(chunk))
        amp_max = float(np.max(chunk))
        avg_amp = (amp_min + amp_max) / 2.0
        rows.append(
            {
                "time_sec": round(((start_idx + end_idx) / 2.0) / sample_rate, 6),
                "amp_min": round(amp_min, 6),
                "amp_max": round(amp_max, 6),
                "mean_amp": round(avg_amp, 6),
            }
        )
    return rows


def build_waveform_chart(
    waveform: np.ndarray | None,
    sample_rate: int | None,
    output_path: str | Path,
) -> str:
    if not altair_available():
        return ""

    rows = build_waveform_rows(waveform, sample_rate)
    if not rows:
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    base = alt.Chart(alt.Data(values=rows)).encode(
        x=alt.X("time_sec:Q", title="Temps (s)"),
    )

    envelope = base.mark_area(
        color="#8a8e18",
        opacity=0.55,
    ).encode(
        y=alt.Y("amp_max:Q", title="Amplitude"),
        y2="amp_min:Q",
        tooltip=[
            alt.Tooltip("time_sec:Q", title="Temps (s)", format=".2f"),
            alt.Tooltip("amp_min:Q", title="Min", format=".4f"),
            alt.Tooltip("amp_max:Q", title="Max", format=".4f"),
            alt.Tooltip("mean_amp:Q", title="Moyenne", format=".4f"),
        ],
    )

    mean_line = base.mark_line(color="#2042ff", point={"size": 30, "filled": True}).encode(
        y=alt.Y("mean_amp:Q", title="Amplitude"),
    )

    min_points = base.mark_point(color="#b5ba32", filled=True, size=20, opacity=0.95).encode(
        y="amp_min:Q"
    )
    max_points = base.mark_point(color="#b5ba32", filled=True, size=20, opacity=0.95).encode(
        y="amp_max:Q"
    )

    chart = (
        alt.layer(envelope, min_points, max_points, mean_line)
        .properties(width=800, height=360, title="Waveform audio par bins d'1 seconde")
        .configure(background="#ffffff")
        .configure_view(stroke="#d9d9d9")
        .configure_axis(
            labelColor="#1f1f1f",
            titleColor="#1f1f1f",
            gridColor="#e8ddd4",
            domainColor="#8a6e5a",
            tickColor="#8a6e5a",
        )
        .configure_title(fontSize=18, color="#1f1f1f", anchor="start")
    )
    return save_chart(chart, output_path)


def build_amplitude_observation_rows(
    waveform: np.ndarray | None,
    sample_rate: int | None,
    amplitude_filter_k: float | None,
    window_sec: float = 1.0,
) -> tuple[list[dict[str, Any]], float, float]:
    if waveform is None or sample_rate is None or sample_rate <= 0 or waveform.size == 0:
        return [], 0.0, 0.0

    k = 2.0 if amplitude_filter_k is None or not np.isfinite(amplitude_filter_k) else float(amplitude_filter_k)
    bin_rows = build_waveform_rows(waveform, sample_rate)
    if not bin_rows:
        return [], 0.0, 0.0

    avg_vals = np.array([float(row["mean_amp"]) for row in bin_rows], dtype=float)
    mu = float(np.mean(avg_vals))
    sigma = float(np.std(avg_vals))
    lower = mu - (k * sigma)
    upper = mu + (k * sigma)

    window_size = max(1, int(round(sample_rate * max(window_sec, 0.1))))
    rows: list[dict[str, Any]] = []
    for window_id, row in enumerate(bin_rows, start=1):
        start_idx = (window_id - 1) * window_size
        end_idx = min(waveform.size, start_idx + window_size)
        window_signal = waveform[start_idx:end_idx]
        amp_min = float(row["amp_min"])
        amp_max = float(row["amp_max"])
        avg_amp = float(row["mean_amp"])
        rms = float(np.sqrt(np.mean(np.square(window_signal)))) if window_signal.size else 0.0
        peak = float(np.max(np.abs(window_signal))) if window_signal.size else 0.0
        peak_dbfs = 20.0 * math.log10(max(peak, 1e-12))
        is_anomaly = avg_amp < lower or avg_amp > upper
        z_score = (avg_amp - mu) / sigma if sigma > 0 else 0.0
        rows.append(
            {
                "window_id": window_id,
                "time_sec": row["time_sec"],
                "start_sec": round(start_idx / sample_rate, 6),
                "end_sec": round(end_idx / sample_rate, 6),
                "amp_min": round(amp_min, 6),
                "amp_max": round(amp_max, 6),
                "mean_amp": round(avg_amp, 6),
                "mu_amplitude": round(mu, 6),
                "sigma_amplitude": round(sigma, 6),
                "lower_bound": round(lower, 6),
                "upper_bound": round(upper, 6),
                "z_score": round(z_score, 6),
                "outlier_ratio": round(abs(z_score), 6),
                "rms_mean": round(rms, 6),
                "peak_dbfs": round(peak_dbfs, 6),
                "anomaly_flag": "oui" if is_anomaly else "non",
            }
        )

    if not rows:
        return rows, lower, upper
    for row in rows:
        row["anomaly_flag"] = "oui" if row["anomaly_flag"] == "oui" else "non"
    return rows, round(lower, 6), round(upper, 6)


def build_anomalies_chart(
    anomaly_rows: list[dict[str, Any]],
    lower_bound: float,
    upper_bound: float,
    output_path: str | Path,
) -> str:
    if not anomaly_rows or not altair_available():
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    base = alt.Chart(alt.Data(values=anomaly_rows)).encode(
        x=alt.X("time_sec:Q", title="Temps (s)")
    )

    envelope = base.mark_area(
        color="#8a8e18",
        opacity=0.55,
    ).encode(
        y=alt.Y("amp_max:Q", title="Amplitude"),
        y2="amp_min:Q",
        tooltip=[
            alt.Tooltip("window_id:Q", title="Bin"),
            alt.Tooltip("time_sec:Q", title="Centre (s)", format=".2f"),
            alt.Tooltip("start_sec:Q", title="Début (s)", format=".2f"),
            alt.Tooltip("end_sec:Q", title="Fin (s)", format=".2f"),
            alt.Tooltip("mean_amp:Q", title="Moyenne", format=".4f"),
            alt.Tooltip("lower_bound:Q", title="Borne inf.", format=".4f"),
            alt.Tooltip("upper_bound:Q", title="Borne sup.", format=".4f"),
            alt.Tooltip("z_score:Q", title="Z-score", format=".4f"),
        ],
    )

    mean_line = base.mark_line(color="#2042ff", point={"size": 28, "filled": True}).encode(
        y=alt.Y("mean_amp:Q", title="Amplitude")
    )

    threshold_rows = [{"bound": float(lower_bound)}, {"bound": float(upper_bound)}]
    bounds = alt.Chart(alt.Data(values=threshold_rows)).mark_rule(
        color="#d8d8d8",
        strokeDash=[6, 4],
        opacity=0.9,
    ).encode(
        y="bound:Q"
    )

    min_points = base.mark_point(color="#b5ba32", filled=True, size=22, opacity=0.95).encode(
        y="amp_min:Q"
    )
    max_points = base.mark_point(color="#b5ba32", filled=True, size=22, opacity=0.95).encode(
        y="amp_max:Q"
    )

    anomalies = base.transform_filter(
        alt.datum.anomaly_flag == "oui"
    ).mark_point(color="#ff2d2d", shape="diamond", size=70, filled=True).encode(
        y="mean_amp:Q"
    )

    chart = (
        alt.layer(envelope, min_points, max_points, bounds, mean_line, anomalies)
        .properties(width=800, height=420, title="Anomalies d'amplitude par bins d'1 seconde")
        .configure(background="#ffffff")
        .configure_view(stroke="#d9d9d9")
        .configure_axis(
            labelColor="#1f1f1f",
            titleColor="#1f1f1f",
            gridColor="#e8ddd4",
            domainColor="#8a6e5a",
            tickColor="#8a6e5a",
        )
        .configure_title(fontSize=18, color="#1f1f1f", anchor="start")
    )
    return save_chart(chart, output_path)


def build_anomaly_concordancier(
    anomaly_rows: list[dict[str, Any]],
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for anomaly in anomaly_rows:
        if str(anomaly.get("anomaly_flag", "")) != "oui":
            continue
        time_sec = float(anomaly.get("time_sec", 0.0) or 0.0)
        start_sec = max(0.0, time_sec - 1.0)
        end_sec = time_sec + 1.0
        overlapping = [
            segment for segment in segments
            if float(segment.get("end_sec", 0.0) or 0.0) >= start_sec
            and float(segment.get("start_sec", 0.0) or 0.0) <= end_sec
        ]
        if not overlapping:
            rows.append(
                {
                    "window_id": anomaly.get("window_id"),
                    "timestamp_sec": anomaly.get("time_sec"),
                    "anomaly_start_sec": anomaly.get("start_sec"),
                    "anomaly_end_sec": anomaly.get("end_sec"),
                    "valeur_moyenne": anomaly.get("mean_amp"),
                    "segment_id": "",
                    "segment_start_sec": "",
                    "segment_end_sec": "",
                    "text": "",
                }
            )
            continue
        for segment in overlapping:
            rows.append(
                {
                    "window_id": anomaly.get("window_id"),
                    "timestamp_sec": anomaly.get("time_sec"),
                    "anomaly_start_sec": anomaly.get("start_sec"),
                    "anomaly_end_sec": anomaly.get("end_sec"),
                    "valeur_moyenne": anomaly.get("mean_amp"),
                    "segment_id": segment.get("segment_id"),
                    "segment_start_sec": segment.get("start_sec"),
                    "segment_end_sec": segment.get("end_sec"),
                    "text": segment.get("text", ""),
                }
            )
    return rows


def build_anomaly_segment_rows(
    anomaly_concordancier_rows: list[dict[str, Any]],
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not anomaly_concordancier_rows or not segments:
        return []

    matched_ids: set[int] = set()
    for row in anomaly_concordancier_rows:
        try:
            segment_id = int(float(row.get("segment_id", "") or 0))
        except Exception:
            segment_id = 0
        if segment_id > 0:
            matched_ids.add(segment_id)

    if not matched_ids:
        return []

    return [
        segment
        for segment in segments
        if int(segment.get("segment_id", 0) or 0) in matched_ids
    ]


def build_audio_summary(
    segments: list[dict[str, Any]],
    media_duration_sec: float | None,
    waveform: np.ndarray | None,
    sample_rate: int | None,
    metadata: dict[str, Any],
    amplitude_filter_k: float | None,
    lower_bound: float,
    upper_bound: float,
    anomaly_count: int,
) -> dict[str, Any]:
    pauses = [float(row["pause_before_sec"]) for row in segments if float(row["pause_before_sec"]) > 0]
    speaking_time = sum(float(row["duration_sec"]) for row in segments)
    total_words = sum(int(row["word_count"]) for row in segments)
    mean_words_per_second = total_words / speaking_time if speaking_time > 0 else None
    global_audio = audio_feature_stats(
        waveform if waveform is not None else np.array([], dtype=float),
        sample_rate or 1,
        amplitude_filter_k,
    )

    return {
        "backend_whisper": metadata.get("backend"),
        "langue": metadata.get("language"),
        "probabilite_langue": metadata.get("language_probability"),
        "sample_rate_hz": int(sample_rate) if sample_rate else None,
        "waveform_observation_count": int(waveform.size) if waveform is not None else 0,
        "waveform_duration_sec": round(float((waveform.size / sample_rate) if waveform is not None and sample_rate else 0.0), 6),
        "waveform_binning_sec": 1.0,
        "waveform_binning_method": "Le signal est regroupé par intervalles stricts d'une seconde. Pour chaque bin, on calcule min, max et une moyenne résumée définie comme (min + max) / 2.",
        "segments_count": len(segments),
        "total_words": total_words,
        "total_duration_sec": round(float(media_duration_sec), 6) if media_duration_sec else None,
        "speaking_time_sec": round(speaking_time, 6),
        "speech_ratio": round(speaking_time / media_duration_sec, 6) if media_duration_sec else None,
        "pause_count": len(pauses),
        "long_pause_count_1s": sum(1 for pause in pauses if pause >= 1.0),
        "max_pause_sec": round(max(pauses), 6) if pauses else 0.0,
        "mean_pause_sec": round(sum(pauses) / len(pauses), 6) if pauses else 0.0,
        "mean_words_per_sec": round(mean_words_per_second, 6) if mean_words_per_second else None,
        "amplitude_filter_k": round(float(amplitude_filter_k), 6) if amplitude_filter_k is not None else None,
        "lower_bound": round(float(lower_bound), 6),
        "upper_bound": round(float(upper_bound), 6),
        "anomaly_count": int(anomaly_count),
        "global_audio_indicators": global_audio,
        "filtrage_amplitude": {
            "description": "Détection des bins atypiques sur le signal résumé par seconde, avec l'intervalle global [μ - k·σ ; μ + k·σ].",
            "k": round(float(amplitude_filter_k), 6) if amplitude_filter_k is not None else None,
        },
        "indicateurs_proposes": {
            "pause_count": "Nombre total de pauses entre segments.",
            "long_pause_count_1s": "Pauses supérieures ou égales à une seconde.",
            "speech_ratio": "Part du temps total occupée par la parole transcrite.",
            "mean_words_per_sec": "Vitesse moyenne de lecture orale ou de débit transcrit.",
            "peak_dbfs": "Pic sonore maximal du signal.",
            "rms_mean": "Énergie moyenne du signal.",
            "onset_strength_mean": "Intensité moyenne des attaques sonores.",
        },
    }


def transcribe_source(
    source: str,
    output_dir: str | Path,
    language: str = "fr",
    model_name: str = "small",
    device: str = "auto",
    compute_type: str = "auto",
    word_timestamps: bool = False,
    cookies_path: str | None = None,
    start_sec: float | None = None,
    end_sec: float | None = None,
    amplitude_filter_k: float | None = 2.0,
) -> dict[str, Any]:
    """
    Pipeline complet :
    - URL YouTube ou fichier local
    - extraction WAV standardisée
    - transcription Whisper
    - enrichissement des segments avec indicateurs audio
    """
    destination = ensure_directory(output_dir)
    session_id = utc_session_id("audio")
    raw_source_path = resolve_media_source(
        source,
        output_dir=destination / "downloads",
        prefer="audio",
        cookies_path=cookies_path,
        start_sec=start_sec if is_youtube_url(source) else None,
        end_sec=end_sec if is_youtube_url(source) else None,
    )
    suffix = raw_source_path.suffix.lower()

    prepared_source_path = raw_source_path
    if not is_youtube_url(source) and suffix in VIDEO_EXTENSIONS and (start_sec is not None or end_sec is not None):
        prepared_source_path = clip_video_interval(
            source_path=raw_source_path,
            output_dir=destination / "downloads",
            start_sec=start_sec,
            end_sec=end_sec,
        )
        suffix = prepared_source_path.suffix.lower()

    if suffix in AUDIO_EXTENSIONS:
        wav_path = extract_audio_wav(prepared_source_path, output_dir=destination / "prepared_audio")
    elif suffix in VIDEO_EXTENSIONS:
        wav_path = extract_audio_wav(prepared_source_path, output_dir=destination / "prepared_audio")
    else:
        raise ValueError(f"Extension non prise en charge pour l'audio: {suffix}")

    raw_segments, metadata = transcribe_audio(
        audio_path=wav_path,
        model_name=model_name,
        language=language,
        device=device,
        compute_type=compute_type,
        word_timestamps=word_timestamps,
    )
    segments = normalise_whisper_segments(raw_segments)

    waveform = None
    sample_rate = None
    if librosa is not None:
        waveform, sample_rate = librosa.load(str(wav_path), sr=16000, mono=True)

    enriched_segments = enrich_segments_with_audio_indicators(segments, waveform, sample_rate, amplitude_filter_k)
    silence_rows = detect_silence_rows(waveform, sample_rate)
    media_duration_sec = probe_duration_seconds(wav_path)
    anomaly_rows, lower_bound, upper_bound = build_amplitude_observation_rows(waveform, sample_rate, amplitude_filter_k)
    anomaly_count = sum(1 for row in anomaly_rows if row.get("anomaly_flag") == "oui")
    anomaly_concordancier_rows = build_anomaly_concordancier(anomaly_rows, enriched_segments)
    anomaly_segment_rows = build_anomaly_segment_rows(anomaly_concordancier_rows, enriched_segments)
    summary = build_audio_summary(
        enriched_segments,
        media_duration_sec,
        waveform,
        sample_rate,
        metadata,
        amplitude_filter_k,
        lower_bound,
        upper_bound,
        anomaly_count,
    )
    pauses_chart_path = build_audio_pauses_chart(waveform, sample_rate, destination / "audio_pauses_altair.png")
    speech_rate_chart_path = build_audio_speech_rate_chart(enriched_segments, destination / "audio_speech_rate_altair.png")
    anomalies_chart_path = build_anomalies_chart(anomaly_rows, lower_bound, upper_bound, destination / "audio_anomalies_altair.png")
    remove_file_if_exists(destination / "audio_waveform_altair.png")
    remove_file_if_exists(destination / "transcription_segments.csv")
    remove_file_if_exists(destination / "segments_texte_global.csv")
    remove_file_if_exists(destination / "segments_texte_anomalies.csv")
    remove_file_if_exists(destination / "audio_anomalies.csv")
    remove_file_if_exists(destination / "audio_anomalies_concordancier.csv")
    remove_file_if_exists(destination / "audio_pauses.csv")

    segments_csv_path, segments_csv_complete_path, segments_csv_essential_path = write_csv_variants(
        destination / "transcription_segments.csv",
        enriched_segments,
        AUDIO_SEGMENT_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    write_jsonl(destination / "transcription_segments.jsonl", enriched_segments)
    write_timestamped_segments_text(destination / "transcription_segments_timestamped.txt", enriched_segments)
    write_timestamped_segments_text(destination / "segments_texte_global_timestamped.txt", enriched_segments)
    write_word_timestamped_segments_text(destination / "transcription_mots_timestamped.txt", enriched_segments)
    write_word_timestamped_segments_text(destination / "segments_texte_global_mots_timestamped.txt", enriched_segments)
    segments_global_csv_path, segments_global_complete_path, segments_global_essential_path = write_csv_variants(
        destination / "segments_texte_global.csv",
        enriched_segments,
        AUDIO_SEGMENT_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    (
        segments_anomalies_csv_path,
        segments_anomalies_complete_path,
        segments_anomalies_essential_path,
    ) = write_csv_variants(
        destination / "segments_texte_anomalies.csv",
        anomaly_segment_rows,
        AUDIO_SEGMENT_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    anomalies_csv_path, anomalies_complete_path, anomalies_essential_path = write_csv_variants(
        destination / "audio_anomalies.csv",
        anomaly_rows,
        AUDIO_ANOMALY_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    (
        anomalies_concordancier_csv_path,
        anomalies_concordancier_complete_path,
        anomalies_concordancier_essential_path,
    ) = write_csv_variants(
        destination / "audio_anomalies_concordancier.csv",
        anomaly_concordancier_rows,
        AUDIO_ANOMALY_CONCORDANCIER_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    pauses_csv_path, pauses_complete_path, pauses_essential_path = write_csv_variants(
        destination / "audio_pauses.csv",
        silence_rows,
        AUDIO_PAUSE_ESSENTIAL_COLUMNS,
        write_legacy=False,
    )
    write_json(
        destination / "audio_summary.json",
        {
            "session_id": session_id,
            "source": source,
            "cookies_path": cookies_path,
            "source_resolved": str(raw_source_path),
            "source_prepared": str(prepared_source_path),
            "start_sec": start_sec,
            "end_sec": end_sec,
            "amplitude_filter_k": amplitude_filter_k,
            "wav_path": str(wav_path),
            "audio_pauses_png": pauses_chart_path,
            "audio_pauses_csv": pauses_complete_path,
            "audio_speech_rate_png": speech_rate_chart_path,
            "audio_anomalies_png": anomalies_chart_path,
            "summary": summary,
        },
    )

    return {
        "session_id": session_id,
        "source_path": str(raw_source_path),
        "wav_path": str(wav_path),
        "segments_csv": segments_csv_complete_path,
        "segments_csv_complet": segments_csv_complete_path,
        "segments_csv_essentiel": segments_csv_essential_path,
        "segments_global_csv": segments_global_complete_path,
        "segments_global_csv_complet": segments_global_complete_path,
        "segments_global_csv_essentiel": segments_global_essential_path,
        "segments_anomalies_csv": segments_anomalies_complete_path,
        "segments_anomalies_csv_complet": segments_anomalies_complete_path,
        "segments_anomalies_csv_essentiel": segments_anomalies_essential_path,
        "segments_jsonl": str(destination / "transcription_segments.jsonl"),
        "segments_txt": str(destination / "transcription_segments_timestamped.txt"),
        "segments_global_txt": str(destination / "segments_texte_global_timestamped.txt"),
        "segments_words_txt": str(destination / "transcription_mots_timestamped.txt"),
        "segments_global_words_txt": str(destination / "segments_texte_global_mots_timestamped.txt"),
        "summary_json": str(destination / "audio_summary.json"),
        "pauses_csv": pauses_complete_path,
        "pauses_csv_complet": pauses_complete_path,
        "pauses_csv_essentiel": pauses_essential_path,
        "pauses_png": pauses_chart_path,
        "speech_rate_png": speech_rate_chart_path,
        "anomalies_png": anomalies_chart_path,
        "anomalies_csv": anomalies_complete_path,
        "anomalies_csv_complet": anomalies_complete_path,
        "anomalies_csv_essentiel": anomalies_essential_path,
        "anomalies_concordancier_csv": anomalies_concordancier_complete_path,
        "anomalies_concordancier_csv_complet": anomalies_concordancier_complete_path,
        "anomalies_concordancier_csv_essentiel": anomalies_concordancier_essential_path,
        "segment_count": len(enriched_segments),
        "summary": summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extraction du texte horodaté et des indicateurs audio pour une source locale ou YouTube."
    )
    parser.add_argument("--source", required=True, help="Fichier audio/vidéo local ou URL YouTube.")
    parser.add_argument("--output-dir", required=False, default="multimodale/exports/audio", help="Dossier d'export.")
    parser.add_argument("--language", default="fr", help="Langue cible pour Whisper.")
    parser.add_argument("--model", default="small", help="Modèle Whisper à utiliser.")
    parser.add_argument("--device", default="auto", help="Device Whisper (auto, cpu, cuda).")
    parser.add_argument("--compute-type", default="auto", help="Type de calcul faster-whisper.")
    parser.add_argument("--word-timestamps", action="store_true", help="Active les timestamps mot à mot si disponibles.")
    parser.add_argument(
        "--cookies",
        default="",
        help="Chemin vers un fichier cookies.txt ou .cookies pour les téléchargements YouTube.",
    )
    parser.add_argument("--start-sec", type=float, default=None, help="Début de l'intervalle à traiter.")
    parser.add_argument("--end-sec", type=float, default=None, help="Fin de l'intervalle à traiter.")
    parser.add_argument(
        "--amplitude-filter-k",
        type=float,
        default=2.0,
        help="Facteur k du filtrage des amplitudes atypiques sur des fenêtres d'une seconde.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    result = transcribe_source(
        source=args.source,
        output_dir=args.output_dir,
        language=args.language,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        word_timestamps=args.word_timestamps,
        cookies_path=args.cookies or None,
        start_sec=args.start_sec,
        end_sec=args.end_sec,
        amplitude_filter_k=args.amplitude_filter_k,
    )
    print("Transcription terminée.")
    print(f"Segments : {result['segment_count']}")
    print(f"CSV : {result['segments_csv']}")
    print(f"Résumé : {result['summary_json']}")


if __name__ == "__main__":
    main()
