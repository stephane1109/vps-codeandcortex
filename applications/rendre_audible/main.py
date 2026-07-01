from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import soundfile as sf
import streamlit as st

from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_NAME = "Analyse de l'amplitude sonore dans un discours"


def convertir_en_min_sec(seconds: float) -> str:
    """Convertir un temps en secondes en format mm:ss."""
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    return f"{minutes:02d}:{sec:02d}"


def resolve_app_data_dir() -> Path:
    """Dossier de travail côté serveur pour les fichiers temporaires audio."""
    root = Path(os.getenv("APP_DATA_DIR", "/data/app")).expanduser()
    temp_root = root / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def transcrire_audio_whisper(uploaded_file) -> list[dict]:
    """
    Transcrire le fichier audio uploadé avec Whisper.

    Le fichier audio est sauvegardé temporairement côté serveur pour la transcription.
    """
    try:
        import whisper
    except ImportError:
        st.error("Le module 'whisper' n'est pas installé dans l'image Docker.")
        return []

    model_name = os.getenv("WHISPER_MODEL_NAME", "small").strip() or "small"
    language = os.getenv("WHISPER_LANGUAGE", "fr").strip() or "fr"
    download_root = os.getenv("WHISPER_CACHE_DIR", "").strip() or None
    temp_root = resolve_app_data_dir()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=temp_root) as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_audio_path = temp_file.name

    try:
        model = whisper.load_model(model_name, download_root=download_root)
        result = model.transcribe(temp_audio_path, language=language)
        return result.get("segments", [])
    finally:
        try:
            os.remove(temp_audio_path)
        except OSError:
            pass


def downsample_by_second(data: np.ndarray, times: np.ndarray, samplerate: int):
    """
    Regrouper le signal par intervalles fixes de 1 seconde.

    Pour chaque seconde :
    - temps moyen du bin
    - valeur minimale
    - valeur maximale
    - valeur moyenne définie ici comme la moyenne de min et max
    """
    n = len(data)
    bin_size = samplerate
    nb_bins = n // bin_size

    times_bins = []
    min_vals = []
    max_vals = []
    avg_vals = []

    for i in range(nb_bins):
        start = i * bin_size
        end = start + bin_size
        slice_data = data[start:end]
        times_bins.append(np.mean(times[start:end]))
        min_vals.append(np.min(slice_data))
        max_vals.append(np.max(slice_data))
        avg_vals.append((np.min(slice_data) + np.max(slice_data)) / 2.0)

    return np.array(times_bins), np.array(min_vals), np.array(max_vals), np.array(avg_vals)


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="centered")

    # #### VARIABLES D'ENVIRONNEMENT VPS A AJUSTER DANS COOLIFY SI BESOIN
    # - REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
    # - APP_TICKET_ID=rendre_audible
    # - APP_TICKET_MAX_ACTIVE=1
    # - APP_TICKET_COST=2
    # - CAPACITE_SERVEUR=6
    # - APP_TICKET_TTL_SECONDS=3600
    # - APP_TICKET_MAX_WAITING=20
    # - APP_TICKET_WAIT_REFRESH_MS=10000
    # - APP_TICKET_HEARTBEAT_MS=300000
    # - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
    # - APP_TICKET_HIDDEN_RELEASE_SECONDS=300
    # - APP_DATA_DIR=/data/app
    # - WHISPER_MODEL_NAME=small
    # - WHISPER_LANGUAGE=fr
    # - PORT=8501
    enforce_streamlit_access("rendre_audible", APP_NAME)

    st.title(APP_NAME)
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")

    st.markdown(
        """
### Introduction
Ce script analyse un fichier audio `.wav` en regroupant le signal en intervalles fixes de 1 seconde.
Chaque intervalle contient un ensemble d'observations. Pour chaque intervalle, on calcule :

- le **point central de l'intervalle** pour positionner la seconde sur l'axe temporel,
- la **valeur minimale** du signal,
- la **valeur maximale** du signal,
- la **valeur moyenne** de l'intervalle, définie ici comme la moyenne de min et max.

Ces statistiques permettent d'obtenir une représentation condensée du signal sur une base temporelle régulière.
L'analyse statistique se fait ensuite sur le signal résumé, avec calcul de la moyenne globale et de l'écart-type.
L'intervalle de détection `[μ ± k×σ]` sert à repérer les observations atypiques.
Si la transcription est activée, le script associe à chaque observation atypique le segment de texte correspondant sur la fenêtre `[t−1, t+1]`.
"""
    )

    uploaded_file = st.file_uploader("Importer un fichier audio (.wav)", type=["wav"])
    afficher_transcription = st.checkbox(
        "Afficher la transcription avec Whisper (pour le concordancier)",
        value=False,
    )
    k_value = st.slider(
        "Définissez le paramètre k (pour l'intervalle [μ ± k×σ])",
        min_value=1.0,
        max_value=5.0,
        value=2.0,
        step=0.1,
    )

    if not st.button("Lancer l'analyse"):
        st.info("Veuillez importer un fichier audio (.wav).")
        return

    keep_ticket_alive("rendre_audible", APP_NAME)

    if uploaded_file is None:
        st.info("Veuillez importer un fichier audio (WAV).")
        return

    try:
        data, samplerate = sf.read(uploaded_file)
        st.write(f"Taux d'échantillonnage : {samplerate} Hz")
    except Exception as exc:
        st.error(f"Erreur lors de la lecture du fichier audio : {exc}")
        return

    if data.ndim > 1:
        data = data.mean(axis=1)

    n_samples = len(data)
    duration = n_samples / samplerate
    st.info(f"Durée du fichier audio : **{duration:.2f} secondes** ({n_samples} observations).")

    temps_complet = np.linspace(0, duration, n_samples)
    times_bins, min_vals, max_vals, avg_vals = downsample_by_second(data, temps_complet, samplerate)

    if len(times_bins) == 0:
        st.error("Le fichier audio est trop court pour produire au moins un intervalle complet d'une seconde.")
        return

    st.info(f"Le signal est divisé en {len(times_bins)} intervalles (intervalle = 1 seconde).")

    mu = np.mean(avg_vals)
    sigma = np.std(avg_vals)
    st.write(f"Moyenne (μ) : {mu:.4f}")
    st.write(f"Écart-type (σ) : {sigma:.4f}")

    lower_bound = mu - k_value * sigma
    upper_bound = mu + k_value * sigma
    st.markdown(f"Intervalle de détection [μ−k×σ, μ+k×σ] : **[{lower_bound:.4f}, {upper_bound:.4f}]**")

    indices_outliers = np.where((avg_vals < lower_bound) | (avg_vals > upper_bound))[0]
    times_out = times_bins[indices_outliers]
    avg_out = avg_vals[indices_outliers]

    st.info(f"Nombre d'observations atypiques détectées pour k={k_value} : {len(indices_outliers)}")

    fig_bins = go.Figure()
    fig_bins.add_trace(
        go.Scatter(
            x=np.concatenate([times_bins, times_bins[::-1]]),
            y=np.concatenate([min_vals, max_vals[::-1]]),
            fill="toself",
            fillcolor="rgba(255,255,0,0.2)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="Enveloppe (min/max)",
        )
    )
    fig_bins.add_trace(
        go.Scatter(
            x=times_bins,
            y=avg_vals,
            mode="lines+markers",
            name="Signal (moyenne par intervalle)",
            marker=dict(color="blue"),
            line=dict(color="blue"),
        )
    )
    if len(indices_outliers) > 0:
        fig_bins.add_trace(
            go.Scatter(
                x=times_out,
                y=avg_out,
                mode="markers",
                marker=dict(color="red", size=8, symbol="diamond"),
                name="Observations atypiques",
            )
        )
    fig_bins.update_layout(
        title="Signal regroupé par intervalle d'1 seconde",
        xaxis_title="Temps (s)",
        yaxis_title="Amplitude",
        width=800,
        height=500,
        hovermode="x unified",
    )
    st.plotly_chart(fig_bins, use_container_width=True)

    if afficher_transcription:
        keep_ticket_alive("rendre_audible", APP_NAME)
        with st.spinner("Transcription en cours (cela peut prendre quelques minutes)..."):
            transcription_segments = transcrire_audio_whisper(uploaded_file)
        if len(transcription_segments) == 0:
            st.warning("Aucun segment de transcription n'a été généré.")
    else:
        transcription_segments = []

    st.subheader("Concordancier des observations atypiques")
    if len(indices_outliers) > 0:
        concordance = []
        for t, avg in zip(times_out, avg_out):
            segment_text = ""
            if transcription_segments:
                segment_text = " ".join(
                    seg["text"].strip()
                    for seg in transcription_segments
                    if seg["end"] >= t - 1 and seg["start"] <= t + 1
                )
            concordance.append(
                {
                    "Timestamp (s)": f"{t:.3f}",
                    "Time (mm:ss)": convertir_en_min_sec(float(t)),
                    "Valeur moyenne": f"{avg:.4f}",
                    "Segment texte": segment_text,
                }
            )
        df_concordance = pd.DataFrame(concordance)
        st.dataframe(df_concordance, use_container_width=True)
        st.download_button(
            label="Télécharger le concordancier en CSV",
            data=df_concordance.to_csv(index=False).encode("utf-8"),
            file_name="concordancier.csv",
            mime="text/csv",
        )
    else:
        st.info("Aucune observation atypique n'a été détectée.")

    st.markdown(
        """
**Interprétation générale :**

- **Graphique :**
  le signal audio est regroupé par intervalle d'1 seconde. Chaque intervalle affiche une enveloppe
  composée de la valeur minimale et maximale, ainsi qu'une valeur moyenne en bleu.
  Les intervalles dont la valeur moyenne sort de l'intervalle `[μ ± k×σ]` sont marqués en rouge.

- **Concordancier :**
  le tableau récapitule, pour chaque observation atypique, son timestamp
  en secondes et au format `mm:ss`, sa valeur moyenne et, si la transcription est activée,
  le segment de texte correspondant à la fenêtre `[t-1, t+1]`.
"""
    )


if __name__ == "__main__":
    main()
