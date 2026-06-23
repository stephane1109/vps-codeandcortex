from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

import altair as alt
import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from fer import FER
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi


EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/appdata"))
SESSIONS_DIR = APP_DATA_DIR / "sessions"


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def clean_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "vecteur_emotionnel"


def is_valid_video_id(candidate: str | None) -> bool:
    return bool(candidate and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate))


def extraire_video_id(url_video: str) -> str:
    url_video = url_video.strip()
    if not url_video:
        raise ValueError("Renseignez une URL YouTube valide.")

    parsed = urlparse(url_video)
    host = parsed.netloc.lower()

    if host.endswith("youtu.be"):
        candidate = parsed.path.lstrip("/").split("/")[0]
        if is_valid_video_id(candidate):
            return candidate

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if is_valid_video_id(query_video_id):
            return query_video_id

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live", "v", "videos"}:
            candidate = path_parts[1]
            if is_valid_video_id(candidate):
                return candidate

    match = re.search(r"([A-Za-z0-9_-]{11})", url_video)
    if match:
        return match.group(1)

    raise ValueError("Impossible d'extraire un identifiant video YouTube valide.")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def touch_session(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.utime(path, None)


def initialiser_repertoires_session(session_dir: Path) -> Path:
    jobs_dir = session_dir / "jobs"
    for directory in (SESSIONS_DIR, session_dir, jobs_dir):
        ensure_directory(directory)
        os.utime(directory, None)
    return jobs_dir


def nettoyer_sessions_expirees(session_id: str) -> None:
    ttl_hours = max(0, env_int("APP_SESSION_TTL_HOURS", 24))
    if ttl_hours == 0:
        return

    limit = time.time() - (ttl_hours * 3600)
    ensure_directory(SESSIONS_DIR)

    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir() or session_dir.name == session_id:
            continue
        try:
            if session_dir.stat().st_mtime < limit:
                shutil.rmtree(session_dir, ignore_errors=True)
        except Exception:
            continue


def create_job_directory(jobs_dir: Path, base_name: str) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    job_dir = jobs_dir / f"{timestamp}_{uuid.uuid4().hex[:8]}_{clean_name(base_name)[:40]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def pick_downloaded_video(job_dir: Path) -> Path:
    candidates = [
        path
        for path in sorted(job_dir.glob("video*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    if not candidates:
        raise RuntimeError("Aucun fichier video n'a ete telecharge par yt-dlp.")
    return candidates[0]


def telecharger_video(video_url: str, job_dir: Path) -> tuple[Path, str]:
    video_id = extraire_video_id(video_url)
    options = {
        "outtmpl": str(job_dir / "video.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "restrictfilenames": True,
        "merge_output_format": "mp4",
        "format": "bestvideo*+bestaudio/best",
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)

    title = str(info.get("title") or video_id)
    return pick_downloaded_video(job_dir), title


def normalize_emotions(emotions: dict[str, float] | None) -> dict[str, float]:
    values = emotions or {}
    return {emotion: float(values.get(emotion, 0.0) or 0.0) for emotion in EMOTIONS}


@st.cache_resource(show_spinner=False)
def charger_detecteur_fer() -> FER:
    return FER()


def analyser_image(image_path: Path, detector: FER) -> dict[str, float]:
    image = cv2.imread(str(image_path))
    if image is None:
        return normalize_emotions({})

    resultats = detector.detect_emotions(image)
    if not resultats:
        return normalize_emotions({})

    for result in resultats:
        x, y, w, h = result.get("box", (0, 0, 0, 0))
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        emotions = normalize_emotions(result.get("emotions", {}))
        for index, emotion in enumerate(EMOTIONS):
            score = emotions[emotion]
            text = f"{emotion}: {score:.4f}"
            cv2.putText(
                image,
                text,
                (x, y + h + 20 + (index * 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        cv2.imwrite(str(image_path), image)
        return emotions

    return normalize_emotions({})


def emotion_dominante_par_moyenne(emotions_list: list[dict[str, float]]) -> tuple[dict[str, float], str]:
    if not emotions_list:
        return normalize_emotions({}), ""

    moyenne_emotions = {
        emotion: float(np.mean([normalize_emotions(emo).get(emotion, 0.0) for emo in emotions_list]))
        for emotion in EMOTIONS
    }
    emotion_dominante = max(moyenne_emotions, key=moyenne_emotions.get)
    return moyenne_emotions, emotion_dominante


def extraire_images_25fps_ffmpeg(video_path: Path, images_dir: Path, seconde: int) -> list[Path]:
    images_extraites: list[Path] = []
    for frame in range(25):
        image_path = images_dir / f"image_25fps_{seconde}_{frame}.jpg"
        if image_path.exists():
            images_extraites.append(image_path)
            continue

        sample_time = seconde + frame * (1 / 25)
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(sample_time),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(image_path),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(
                f"Erreur FFmpeg a {sample_time:.2f} seconde(s) : {result.stderr.decode('utf-8', errors='ignore')}"
            )
        images_extraites.append(image_path)
    return images_extraites


def transcript_entries(video_id: str, languages: list[str]) -> list[dict[str, object]]:
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)

    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=languages)
    if hasattr(fetched, "to_raw_data"):
        return fetched.to_raw_data()
    return list(fetched)


def obtenir_sous_titres_youtube(video_url: str) -> dict[int, str]:
    video_id = extraire_video_id(video_url)
    for languages in (["fr"], ["en"]):
        try:
            transcript = transcript_entries(video_id, languages=languages)
            sous_titres_par_seconde: dict[int, str] = {}
            for entry in transcript:
                start_time = int(float(entry.get("start", 0)))
                text = str(entry.get("text", "")).strip()
                if text:
                    sous_titres_par_seconde[start_time] = text
            return sous_titres_par_seconde
        except Exception:
            continue
    return {}


def dataframe_to_excel_path(df: pd.DataFrame, path: Path, sheet_name: str) -> Path:
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return path


def save_dataframe_csv(df: pd.DataFrame, path: Path) -> Path:
    df.to_csv(path, index=False)
    return path


def save_altair_outputs(chart: alt.Chart, base_path: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    html_path = base_path.with_suffix(".html")
    chart.save(str(html_path))
    outputs["html"] = html_path

    png_path = base_path.with_suffix(".png")
    try:
        chart.save(str(png_path))
        outputs["png"] = png_path
    except Exception:
        pass
    return outputs


def save_matplotlib_figure(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, format="png", bbox_inches="tight")
    return path


def build_concordancier_df(
    images_data: list[list[Path]],
    emotions_data: list[dict[str, object]],
    sous_titres: dict[int, str],
    start_time: int,
    end_time: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for seconde in range(start_time, end_time + 1):
        offset = seconde - start_time
        images = images_data[offset] if offset < len(images_data) else []
        emotions_row = emotions_data[offset] if offset < len(emotions_data) else {}
        rows.append(
            {
                "Seconde": seconde,
                "Images": ", ".join(path.name for path in images),
                "Moyenne_Emotions": json.dumps(
                    {emotion: float(emotions_row.get(emotion, 0.0) or 0.0) for emotion in EMOTIONS},
                    ensure_ascii=False,
                ),
                "Emotion_Dominante": str(emotions_row.get("Emotion_Dominante", "")),
                "Sous_Titres": sous_titres.get(seconde, "Aucun sous-titre disponible"),
            }
        )

    return pd.DataFrame(rows)


def optimiser_clusters(X_pca: np.ndarray) -> tuple[int | None, pd.DataFrame]:
    if X_pca.shape[0] < 3:
        return None, pd.DataFrame(columns=["Nombre de clusters", "Score de silhouette"])

    max_clusters = min(10, X_pca.shape[0] - 1)
    if max_clusters < 2:
        return None, pd.DataFrame(columns=["Nombre de clusters", "Score de silhouette"])

    scores: list[float] = []
    range_n_clusters = list(range(2, max_clusters + 1))

    for n_clusters in range_n_clusters:
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_pca)
        scores.append(float(silhouette_score(X_pca, labels)))

    df_silhouette = pd.DataFrame(
        {
            "Nombre de clusters": range_n_clusters,
            "Score de silhouette": scores,
        }
    )
    best_n = range_n_clusters[scores.index(max(scores))]
    return best_n, df_silhouette


def create_images_zip(images_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_path in sorted(images_dir.glob("*.jpg")):
            archive.write(image_path, arcname=image_path.name)
    return zip_path


def create_bundle_zip(job_dir: Path, exports_dir: Path, images_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(exports_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=str(file_path.relative_to(job_dir)))
        for file_path in sorted(images_dir.glob("*.jpg")):
            archive.write(file_path, arcname=str(file_path.relative_to(job_dir)))
    return zip_path


def analyser_video(
    video_url: str,
    start_time: int,
    end_time: int,
    jobs_dir: Path,
    job_label: str,
    status_callback: Callable[[str], None] | None = None,
) -> dict[str, object]:
    def status(message: str) -> None:
        if status_callback:
            status_callback(message)

    video_id = extraire_video_id(video_url)
    job_dir = create_job_directory(jobs_dir, job_label or video_id)
    exports_dir = ensure_directory(job_dir / "exports")
    images_dir = ensure_directory(job_dir / "images_25fps")

    status("Telechargement de la video YouTube...")
    video_path, video_title = telecharger_video(video_url, job_dir)

    status("Chargement du detecteur FER...")
    detector = charger_detecteur_fer()

    status("Recuperation des sous-titres YouTube...")
    sous_titres = obtenir_sous_titres_youtube(video_url)

    results_25fps: list[dict[str, object]] = []
    emotion_dominante_moyenne_results: list[dict[str, object]] = []
    images_data: list[list[Path]] = []
    frame_index = 0

    for seconde in range(start_time, end_time + 1):
        status(f"Analyse de la seconde {seconde}...")
        images_25fps = extraire_images_25fps_ffmpeg(video_path, images_dir, seconde)
        images_data.append(images_25fps)

        emotions_25fps_list: list[dict[str, float]] = []
        for frame_in_second, image_path in enumerate(images_25fps):
            emotions = analyser_image(image_path, detector)
            emotions_25fps_list.append(emotions)
            results_25fps.append(
                {
                    "Seconde": seconde,
                    "Frame": f"25fps_{seconde}_{frame_in_second}",
                    "Frame_Index": frame_index,
                    **emotions,
                }
            )
            frame_index += 1

        moyenne_emotions, emotion_dominante = emotion_dominante_par_moyenne(emotions_25fps_list)
        emotion_dominante_moyenne_results.append(
            {
                "Seconde": seconde,
                **moyenne_emotions,
                "Emotion_Dominante": emotion_dominante,
            }
        )

    df_emotions = pd.DataFrame(results_25fps)
    df_emotion_dominante_moyenne = pd.DataFrame(emotion_dominante_moyenne_results)
    df_concordancier = build_concordancier_df(
        images_data,
        emotion_dominante_moyenne_results,
        sous_titres,
        start_time,
        end_time,
    )

    if df_emotions.empty or df_emotion_dominante_moyenne.empty:
        raise RuntimeError("Aucune emotion n'a pu etre calculee sur la plage demandee.")

    df_stats = pd.DataFrame(
        [
            {
                "Emotion": emotion,
                "Moyenne": float(df_emotion_dominante_moyenne[emotion].mean()),
                "Variance": float(df_emotion_dominante_moyenne[emotion].var(ddof=0)),
            }
            for emotion in EMOTIONS
        ]
    )

    concordancier_xlsx = dataframe_to_excel_path(
        df_concordancier,
        exports_dir / "concordancier_emotions.xlsx",
        "Concordancier",
    )
    concordancier_csv = save_dataframe_csv(df_concordancier, exports_dir / "concordancier_emotions.csv")
    frames_csv = save_dataframe_csv(df_emotions, exports_dir / "scores_emotions_frames.csv")
    seconds_csv = save_dataframe_csv(
        df_emotion_dominante_moyenne,
        exports_dir / "scores_emotions_secondes.csv",
    )
    stats_csv = save_dataframe_csv(df_stats, exports_dir / "stats_emotions.csv")

    status("Calcul PCA et KMeans...")
    pca_outputs: dict[str, object] = {
        "df_variance": None,
        "df_silhouette": None,
        "df_points": None,
        "df_similarity": None,
        "df_cluster_means": None,
        "best_n": None,
        "analysis_note": "",
    }

    if len(df_emotion_dominante_moyenne) >= 2:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df_emotion_dominante_moyenne[EMOTIONS].values)
        pca = PCA()
        X_pca = pca.fit_transform(X_scaled)

        df_variance = pd.DataFrame(
            {
                "Composante Principale": [f"PC{i + 1}" for i in range(len(pca.explained_variance_ratio_))],
                "Variance expliquee (%)": pca.explained_variance_ratio_ * 100,
            }
        )
        save_dataframe_csv(df_variance, exports_dir / "variance_pca.csv")

        df_points = df_emotion_dominante_moyenne.copy()
        df_points["PC1"] = X_pca[:, 0]
        df_points["PC2"] = X_pca[:, 1] if X_pca.shape[1] > 1 else np.zeros(len(df_points))

        best_n, df_silhouette = optimiser_clusters(X_pca)
        if not df_silhouette.empty:
            save_dataframe_csv(df_silhouette, exports_dir / "silhouette_scores.csv")

        df_similarity = None
        df_cluster_means = None
        analysis_note = ""

        if best_n is not None:
            kmeans = KMeans(n_clusters=best_n, random_state=42, n_init=10)
            df_points["Cluster"] = kmeans.fit_predict(X_pca)
            df_points["Cluster_Label"] = "Cluster " + df_points["Cluster"].astype(str)
            df_points["Emotion_Dominante"] = df_points[EMOTIONS].idxmax(axis=1)
            save_dataframe_csv(df_points, exports_dir / "pca_kmeans_points.csv")

            similarites = cosine_similarity(kmeans.cluster_centers_)
            df_similarity = pd.DataFrame(
                similarites,
                columns=[f"Cluster {i}" for i in range(best_n)],
                index=[f"Cluster {i}" for i in range(best_n)],
            )
            df_similarity.to_csv(exports_dir / "similarite_cosinus.csv")

            df_cluster_means = (
                df_points.groupby("Cluster")[EMOTIONS]
                .mean()
                .reset_index()
                .rename(columns={"Cluster": "Cluster"})
            )
            save_dataframe_csv(df_cluster_means, exports_dir / "moyennes_emotions_par_cluster.csv")
        else:
            analysis_note = (
                "Le nombre de secondes analysees est trop faible pour calculer un score de silhouette "
                "et proposer un KMeans fiable."
            )
            save_dataframe_csv(df_points, exports_dir / "pca_points.csv")

        pca_outputs = {
            "df_variance": df_variance,
            "df_silhouette": df_silhouette,
            "df_points": df_points,
            "df_similarity": df_similarity,
            "df_cluster_means": df_cluster_means,
            "best_n": best_n,
            "analysis_note": analysis_note,
        }
    else:
        pca_outputs["analysis_note"] = (
            "La PCA et le KMeans necessitent au moins 2 secondes analysees."
        )

    status("Preparation des exports...")
    images_zip = create_images_zip(images_dir, job_dir / "images_25fps.zip")
    bundle_zip = create_bundle_zip(job_dir, exports_dir, images_dir, job_dir / "vecteur_emotionnel_exports.zip")

    return {
        "job_dir": str(job_dir),
        "exports_dir": str(exports_dir),
        "images_dir": str(images_dir),
        "video_id": video_id,
        "video_title": video_title,
        "video_path": str(video_path),
        "start_time": start_time,
        "end_time": end_time,
        "sous_titres_count": len(sous_titres),
        "df_emotions": df_emotions,
        "df_emotion_dominante_moyenne": df_emotion_dominante_moyenne,
        "df_concordancier": df_concordancier,
        "df_stats": df_stats,
        "concordancier_xlsx": str(concordancier_xlsx),
        "concordancier_csv": str(concordancier_csv),
        "frames_csv": str(frames_csv),
        "seconds_csv": str(seconds_csv),
        "stats_csv": str(stats_csv),
        "images_zip": str(images_zip),
        "bundle_zip": str(bundle_zip),
        **pca_outputs,
    }


def render_core_charts(result: dict[str, object]) -> dict[str, object]:
    df_emotions: pd.DataFrame = result["df_emotions"]  # type: ignore[assignment]
    df_seconds: pd.DataFrame = result["df_emotion_dominante_moyenne"]  # type: ignore[assignment]
    df_stats: pd.DataFrame = result["df_stats"]  # type: ignore[assignment]

    df_streamgraph_frames = df_emotions.melt(
        id_vars=["Frame_Index", "Seconde", "Frame"],
        value_vars=EMOTIONS,
        var_name="Emotion",
        value_name="Score",
    )
    streamgraph_frames = (
        alt.Chart(df_streamgraph_frames)
        .mark_area()
        .encode(
            x=alt.X("Frame_Index:Q", title="Frame Index"),
            y=alt.Y("Score:Q", title="Score des emotions", stack="center"),
            color=alt.Color("Emotion:N", title="Emotion"),
            tooltip=["Frame_Index", "Seconde", "Emotion", "Score"],
        )
        .properties(
            title="Streamgraph des emotions par frame (25 fps)",
            width=800,
            height=380,
        )
    )

    df_streamgraph_seconds = df_seconds.melt(
        id_vars=["Seconde", "Emotion_Dominante"],
        value_vars=EMOTIONS,
        var_name="Emotion",
        value_name="Score",
    )
    streamgraph_seconds = (
        alt.Chart(df_streamgraph_seconds)
        .mark_area()
        .encode(
            x=alt.X("Seconde:Q", title="Seconde"),
            y=alt.Y("Score:Q", title="Score des emotions", stack="center"),
            color=alt.Color("Emotion:N", title="Emotion"),
            tooltip=["Seconde", "Emotion", "Score", "Emotion_Dominante"],
        )
        .properties(
            title="Streamgraph des moyennes des emotions par seconde",
            width=800,
            height=380,
        )
    )

    moyenne_bar = (
        alt.Chart(df_stats)
        .mark_bar()
        .encode(
            x=alt.X("Emotion:N", title="Emotion"),
            y=alt.Y("Moyenne:Q", title="Moyenne"),
            color=alt.Color("Emotion:N", legend=None),
        )
    )
    variance_point = (
        alt.Chart(df_stats)
        .mark_circle(size=110, color="red")
        .encode(
            x=alt.X("Emotion:N", title="Emotion"),
            y=alt.Y("Variance:Q", title="Variance"),
            tooltip=["Emotion", "Variance"],
        )
    )
    stats_chart = alt.layer(moyenne_bar, variance_point).resolve_scale(y="independent").properties(
        title="Moyennes et variances des emotions sur la plage analysee",
        width=760,
        height=380,
    )

    return {
        "streamgraph_frames": streamgraph_frames,
        "streamgraph_seconds": streamgraph_seconds,
        "stats_chart": stats_chart,
    }


def render_pca_charts(result: dict[str, object]) -> dict[str, object]:
    outputs: dict[str, object] = {}

    df_variance: pd.DataFrame | None = result.get("df_variance")  # type: ignore[assignment]
    df_silhouette: pd.DataFrame | None = result.get("df_silhouette")  # type: ignore[assignment]
    df_points: pd.DataFrame | None = result.get("df_points")  # type: ignore[assignment]
    df_similarity: pd.DataFrame | None = result.get("df_similarity")  # type: ignore[assignment]
    df_cluster_means: pd.DataFrame | None = result.get("df_cluster_means")  # type: ignore[assignment]
    best_n: int | None = result.get("best_n")  # type: ignore[assignment]

    if df_variance is not None and not df_variance.empty:
        outputs["variance_chart"] = (
            alt.Chart(df_variance)
            .mark_bar()
            .encode(
                x=alt.X("Composante Principale:N", sort=None),
                y=alt.Y("Variance expliquee (%):Q"),
                tooltip=["Composante Principale", "Variance expliquee (%)"],
            )
            .properties(
                title="Variance expliquee par chaque composante principale",
                width=700,
                height=360,
            )
        )

    if df_silhouette is not None and not df_silhouette.empty:
        outputs["silhouette_chart"] = (
            alt.Chart(df_silhouette)
            .mark_line(point=True)
            .encode(
                x=alt.X("Nombre de clusters:Q", title="Nombre de clusters"),
                y=alt.Y("Score de silhouette:Q", title="Score de silhouette"),
                tooltip=["Nombre de clusters", "Score de silhouette"],
            )
            .properties(
                title="Score de silhouette en fonction du nombre de clusters",
                width=700,
                height=360,
            )
        )

    if df_points is not None and not df_points.empty and "Cluster" in df_points.columns and best_n is not None:
        cluster_chart = (
            alt.Chart(df_points)
            .mark_circle(size=80)
            .encode(
                x=alt.X("PC1:Q", title="Premiere composante principale (PC1)"),
                y=alt.Y("PC2:Q", title="Deuxieme composante principale (PC2)"),
                color=alt.Color("Cluster:N", scale=alt.Scale(scheme="category10")),
                tooltip=["Seconde", "Cluster", "Emotion_Dominante", *EMOTIONS],
            )
            .properties(
                title="Representation des clusters avec PCA",
                width=700,
                height=420,
            )
        )

        centroids = (
            df_points.groupby("Cluster")[["PC1", "PC2"]]
            .mean()
            .reset_index()
        )
        centroid_chart = (
            alt.Chart(centroids)
            .mark_point(size=240, shape="cross", filled=True)
            .encode(
                x="PC1:Q",
                y="PC2:Q",
                color=alt.Color("Cluster:N", scale=alt.Scale(scheme="category10")),
            )
        )
        outputs["cluster_chart"] = cluster_chart + centroid_chart

        cluster_time_chart = (
            alt.Chart(df_points)
            .mark_rect()
            .encode(
                x=alt.X("Seconde:O", title="Seconde"),
                y=alt.Y("Cluster:O", title="Cluster"),
                color=alt.Color("Cluster:N", scale=alt.Scale(scheme="category10")),
                tooltip=["Seconde", "Cluster", "Emotion_Dominante"],
            )
            .properties(
                title="Evolution des clusters au fil du temps",
                width=700,
                height=220,
            )
        )
        outputs["cluster_time_chart"] = cluster_time_chart

    if df_similarity is not None and not df_similarity.empty:
        fig, ax = plt.subplots(figsize=(7, 5))
        sns.heatmap(df_similarity, annot=True, cmap="coolwarm", ax=ax, fmt=".2f")
        ax.set_title("Heatmap de la similarite cosinus entre clusters")
        outputs["similarity_fig"] = fig

    if df_cluster_means is not None and not df_cluster_means.empty:
        outputs["df_cluster_means"] = df_cluster_means

    return outputs


def save_visual_exports(result: dict[str, object]) -> None:
    exports_dir = Path(str(result["exports_dir"]))

    charts = render_core_charts(result)
    save_altair_outputs(charts["streamgraph_frames"], exports_dir / "streamgraph_frames")
    save_altair_outputs(charts["streamgraph_seconds"], exports_dir / "streamgraph_secondes")
    save_altair_outputs(charts["stats_chart"], exports_dir / "moyennes_variances")

    pca_charts = render_pca_charts(result)
    if "variance_chart" in pca_charts:
        save_altair_outputs(pca_charts["variance_chart"], exports_dir / "variance_pca")
    if "silhouette_chart" in pca_charts:
        save_altair_outputs(pca_charts["silhouette_chart"], exports_dir / "silhouette")
    if "cluster_chart" in pca_charts:
        save_altair_outputs(pca_charts["cluster_chart"], exports_dir / "clusters")
    if "cluster_time_chart" in pca_charts:
        save_altair_outputs(pca_charts["cluster_time_chart"], exports_dir / "clusters_temps")
    if "similarity_fig" in pca_charts:
        save_matplotlib_figure(pca_charts["similarity_fig"], exports_dir / "similarite_cosinus.png")
        plt.close(pca_charts["similarity_fig"])


def file_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


st.set_page_config(page_title="Vecteur emotionnel", layout="wide")

session_id = st.session_state.setdefault("session_id", uuid.uuid4().hex)
session_dir = SESSIONS_DIR / session_id
jobs_dir = initialiser_repertoires_session(session_dir)
nettoyer_sessions_expirees(session_id)
touch_session(session_dir)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

st.title("Vecteur emotionnel")
st.caption(
    "Analyse emotionnelle d'une video YouTube avec FER, concordancier, streamgraphs, PCA et KMeans."
)

if not ffmpeg_available():
    st.error("ffmpeg n'est pas disponible sur ce serveur. L'application ne peut pas extraire les frames.")
    st.stop()

st.info(
    "Cette version VPS gere automatiquement les repertoires de travail par session. "
    "Les exports sont prepares dans un dossier temporaire puis telechargeables depuis l'interface."
)

video_url = st.text_input(
    "URL de la video YouTube",
    placeholder="https://www.youtube.com/watch?v=...",
)
job_label = st.text_input(
    "Nom du repertoire de travail (optionnel)",
    placeholder="analyse_video_1",
)

time_col_1, time_col_2 = st.columns(2)
with time_col_1:
    start_time = st.number_input(
        "Temps de depart de l'analyse (en secondes)",
        min_value=0,
        value=0,
        step=1,
    )
with time_col_2:
    end_time = st.number_input(
        "Temps de fin de l'analyse (en secondes)",
        min_value=int(start_time),
        value=int(start_time) + 1,
        step=1,
    )

if st.button("Lancer l'analyse", type="primary", use_container_width=True):
    st.session_state.analysis_result = None

    if not video_url.strip():
        st.error("Renseignez une URL YouTube avant de lancer l'analyse.")
    elif int(end_time) < int(start_time):
        st.error("Le temps de fin doit etre superieur ou egal au temps de depart.")
    else:
        status_box = st.empty()
        try:
            result = analyser_video(
                video_url=video_url.strip(),
                start_time=int(start_time),
                end_time=int(end_time),
                jobs_dir=jobs_dir,
                job_label=job_label.strip(),
                status_callback=lambda message: status_box.info(message),
            )
            save_visual_exports(result)
            result["bundle_zip"] = str(
                create_bundle_zip(
                    Path(str(result["job_dir"])),
                    Path(str(result["exports_dir"])),
                    Path(str(result["images_dir"])),
                    Path(str(result["job_dir"])) / "vecteur_emotionnel_exports.zip",
                )
            )
            st.session_state.analysis_result = result
            status_box.success("Analyse terminee. Les resultats sont pret a etre consultes et telecharges.")
        except Exception as exc:
            status_box.empty()
            st.error(f"Erreur lors de l'analyse : {exc}")

result = st.session_state.analysis_result

if result:
    df_emotions: pd.DataFrame = result["df_emotions"]  # type: ignore[assignment]
    df_seconds: pd.DataFrame = result["df_emotion_dominante_moyenne"]  # type: ignore[assignment]
    df_concordancier: pd.DataFrame = result["df_concordancier"]  # type: ignore[assignment]
    df_stats: pd.DataFrame = result["df_stats"]  # type: ignore[assignment]
    charts = render_core_charts(result)
    pca_charts = render_pca_charts(result)

    st.markdown("### Resume")
    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("Secondes analysees", value=str(len(df_seconds)))
    metric_col_2.metric("Frames analysees", value=str(len(df_emotions)))
    metric_col_3.metric("Sous-titres recuperes", value=str(result["sous_titres_count"]))
    metric_col_4.metric("Plage analysee", value=f"{result['start_time']}s - {result['end_time']}s")

    st.markdown(f"**Titre video** : {result['video_title']}")
    st.markdown(f"**ID video** : `{result['video_id']}`")

    st.markdown("### Telechargements")
    download_col_1, download_col_2, download_col_3, download_col_4 = st.columns(4)
    with download_col_1:
        st.download_button(
            "Bundle complet (ZIP)",
            data=file_bytes(result["bundle_zip"]),
            file_name=Path(str(result["bundle_zip"])).name,
            mime="application/zip",
            type="primary",
        )
    with download_col_2:
        st.download_button(
            "Images 25 fps (ZIP)",
            data=file_bytes(result["images_zip"]),
            file_name=Path(str(result["images_zip"])).name,
            mime="application/zip",
        )
    with download_col_3:
        st.download_button(
            "Concordancier XLSX",
            data=file_bytes(result["concordancier_xlsx"]),
            file_name=Path(str(result["concordancier_xlsx"])).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with download_col_4:
        st.download_button(
            "Concordancier CSV",
            data=file_bytes(result["concordancier_csv"]),
            file_name=Path(str(result["concordancier_csv"])).name,
            mime="text/csv",
        )

    st.markdown("### Scores des emotions par frame")
    st.dataframe(df_emotions, use_container_width=True)
    st.altair_chart(charts["streamgraph_frames"], use_container_width=True)

    st.markdown("### Moyennes des emotions par seconde")
    st.dataframe(df_seconds, use_container_width=True)
    st.altair_chart(charts["streamgraph_seconds"], use_container_width=True)

    st.markdown("### Concordancier")
    st.dataframe(df_concordancier, use_container_width=True)

    st.markdown("### Moyennes et variances")
    st.dataframe(df_stats, use_container_width=True)
    st.altair_chart(charts["stats_chart"], use_container_width=True)

    st.markdown("### PCA et KMeans")
    analysis_note = str(result.get("analysis_note", "") or "")
    if analysis_note:
        st.info(analysis_note)

    if result.get("df_variance") is not None:
        st.dataframe(result["df_variance"], use_container_width=True)
        st.altair_chart(pca_charts["variance_chart"], use_container_width=True)

    if result.get("df_silhouette") is not None and not result["df_silhouette"].empty:
        st.markdown(
            "La courbe de silhouette permet de choisir un nombre de clusters avant le KMeans."
        )
        st.dataframe(result["df_silhouette"], use_container_width=True)
        st.altair_chart(pca_charts["silhouette_chart"], use_container_width=True)

    if "cluster_chart" in pca_charts and result.get("best_n") is not None:
        st.success(f"Nombre optimal de clusters propose : {result['best_n']}")
        st.altair_chart(pca_charts["cluster_chart"], use_container_width=True)
        st.altair_chart(pca_charts["cluster_time_chart"], use_container_width=True)

    if result.get("df_similarity") is not None:
        st.markdown("### Similarite cosinus entre clusters")
        st.dataframe(result["df_similarity"], use_container_width=True)
        st.pyplot(pca_charts["similarity_fig"])

    if result.get("df_cluster_means") is not None:
        st.markdown("### Moyenne des emotions par cluster")
        st.dataframe(result["df_cluster_means"], use_container_width=True)
