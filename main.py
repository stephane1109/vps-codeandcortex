import io
import json
import math
import tempfile
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
HELP_PATH = Path(__file__).resolve().parent / "aide.md"


@dataclass
class AnalysisConfig:
    sample_every_n_frames: int
    max_pairs: int
    resize_width: int
    algorithm: str
    candidate_count: int


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


def analyze_video(video_path: Path, config: AnalysisConfig) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Impossible d'ouvrir la vidéo avec OpenCV.")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    fps = fps if fps > 0 else 25.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    original_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    original_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_seconds = float(total_frames / fps) if total_frames > 0 else 0.0

    metrics: list[dict[str, float | int]] = []
    candidates: list[dict[str, Any]] = []
    previous_gray: np.ndarray | None = None
    previous_mean_mag: float | None = None
    flow_heat: np.ndarray | None = None
    residual_heat: np.ndarray | None = None

    frame_index = -1
    sampled_pairs = 0
    progress = st.progress(0, text="Analyse en cours...")
    status_box = st.empty()

    while True:
        success, frame_bgr = capture.read()
        if not success:
            break
        frame_index += 1

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

        update_top_candidates(
            candidates,
            {
                "frame_index": frame_index,
                "time_seconds": round(frame_index / fps, 3),
                "pair_score": round(pair_score, 1),
                "frame_rgb": frame_rgb,
                "flow_rgb": flow_to_rgb(flow),
                "flow_arrows_rgb": draw_flow_arrows(frame_rgb, flow),
                "residual_rgb": heatmap_rgb(residual_map),
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

    metrics_df = pd.DataFrame(metrics)
    score = compute_global_score(metrics_df)

    heatmaps: dict[str, np.ndarray] = {}
    if flow_heat is not None and residual_heat is not None and sampled_pairs > 0:
        heatmaps["flow"] = heatmap_rgb(flow_heat / float(sampled_pairs))
        heatmaps["residual"] = heatmap_rgb(residual_heat / float(sampled_pairs))

    return {
        "metadata": {
            "fps": round(fps, 3),
            "total_frames": total_frames,
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
    }


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
        "note": "Indice heuristique d'incohérence temporelle. Ne constitue pas une preuve automatique de génération par IA.",
    }

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("rapport_detectia.json", json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr("mesures_temporelles.csv", metrics_df.to_csv(index=False))

        for name, image_rgb in result["heatmaps"].items():
            archive.writestr(f"heatmaps/{name}.png", image_to_png_bytes(image_rgb))

        for index, candidate in enumerate(result["candidates"], start=1):
            prefix = f"frames_suspectes/{index:02d}_t{candidate['time_seconds']:.2f}s"
            archive.writestr(f"{prefix}_frame.png", image_to_png_bytes(candidate["frame_rgb"]))
            archive.writestr(f"{prefix}_flow.png", image_to_png_bytes(candidate["flow_rgb"]))
            archive.writestr(f"{prefix}_flow_fleches.png", image_to_png_bytes(candidate["flow_arrows_rgb"]))
            archive.writestr(f"{prefix}_residu.png", image_to_png_bytes(candidate["residual_rgb"]))

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
        "Importer une vidéo",
        type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
        help="Pour une première analyse, privilégie une vidéo courte ou un extrait.",
    )

    st.divider()
    sample_every_n_frames = st.slider("Analyser une frame sur", 1, 25, 5)
    max_pairs = st.slider("Nombre maximum de paires analysées", 20, 600, 160, step=20)
    resize_width = st.slider("Largeur de travail", 320, 1280, 640, step=80)
    algorithm = st.selectbox("Méthode optical flow", ["Farneback robuste", "DIS rapide"], index=0)
    candidate_count = st.slider("Frames suspectes à conserver", 3, 12, 6)

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

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if uploaded_file is None:
    st.info("Importe une vidéo dans la colonne de gauche pour lancer l'analyse.")
    st.stop()

video_bytes = uploaded_file.getvalue()
st.video(video_bytes)

config = AnalysisConfig(
    sample_every_n_frames=int(sample_every_n_frames),
    max_pairs=int(max_pairs),
    resize_width=int(resize_width),
    algorithm=algorithm,
    candidate_count=int(candidate_count),
)

if st.button("Lancer l'analyse DetectIA", type="primary", use_container_width=True):
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as temp_video:
        temp_video.write(video_bytes)
        temp_video.flush()
        try:
            st.session_state.analysis_result = analyze_video(Path(temp_video.name), config)
        except Exception as exc:
            st.session_state.analysis_result = None
            st.error(f"Erreur pendant l'analyse : {exc}")

result = st.session_state.analysis_result
if result is None:
    st.stop()

metadata = result["metadata"]
score = result["score"]
metrics_df: pd.DataFrame = result["metrics"]

tab_summary, tab_temporal, tab_flow, tab_candidates, tab_export = st.tabs(
    ["Synthèse", "Temporalité", "Optical flow", "Frames suspectes", "Rapport"]
)

with tab_summary:
    col_score, col_meta = st.columns([1, 2])
    with col_score:
        st.metric("Indice de suspicion", f"{score['score']} / 100", score["niveau"])
        st.write(score["interpretation"])
    with col_meta:
        meta_cols = st.columns(4)
        meta_cols[0].metric("FPS", metadata["fps"])
        meta_cols[1].metric("Durée", f"{metadata['duration_seconds']:.1f}s")
        meta_cols[2].metric("Frames", metadata["total_frames"])
        meta_cols[3].metric("Paires analysées", metadata["sampled_pairs"])

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
    st.download_button(
        "Télécharger le rapport complet ZIP",
        data=build_report_zip(result),
        file_name=f"detectia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        use_container_width=True,
    )
    st.download_button(
        "Télécharger les mesures CSV",
        data=metrics_df.to_csv(index=False).encode("utf-8"),
        file_name="detectia_mesures_temporelles.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.json({"metadata": metadata, "score": score})
