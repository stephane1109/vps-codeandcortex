"""Page Streamlit pour l'analyse du vecteur émotionnel."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler


DEFAULT_EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


def _texte_par_seconde() -> dict[int, str]:
    """Retourne un dictionnaire {seconde: texte} à partir de st.session_state."""

    df_align_sec = st.session_state.get("df_align_sec")
    mapping: dict[int, str] = {}

    if isinstance(df_align_sec, pd.DataFrame) and not df_align_sec.empty:
        for _, row in df_align_sec.iterrows():
            t_sec = row.get("t_sec")
            if pd.isna(t_sec):
                continue
            try:
                seconde = int(t_sec)
            except Exception:
                continue
            texte = row.get("texte_sec", "")
            if isinstance(texte, str):
                mapping[seconde] = texte.strip()

    return mapping


def _collecter_audio_features() -> pd.DataFrame:
    """Agrège les mesures audio par seconde depuis st.session_state['plots_audio']."""

    audio_entries = st.session_state.get("plots_audio", []) or []
    rows_debit: list[pd.DataFrame] = []
    rows_parole: list[pd.DataFrame] = []

    for entree in audio_entries:
        if not isinstance(entree, (list, tuple)) or len(entree) != 5:
            continue
        _, _, _, df_debit_sec, df_parole_pause_sec = entree

        if isinstance(df_debit_sec, pd.DataFrame) and not df_debit_sec.empty:
            tmp = df_debit_sec.rename(columns={"t_seconde": "Seconde"})
            if {"Seconde", "debit_seconde"}.issubset(tmp.columns):
                rows_debit.append(tmp[["Seconde", "debit_seconde"]].copy())

        if isinstance(df_parole_pause_sec, pd.DataFrame) and not df_parole_pause_sec.empty:
            tmp = df_parole_pause_sec.rename(columns={"t_seconde": "Seconde"})
            colonnes = [c for c in ["parole_s", "pause_s"] if c in tmp.columns]
            if "Seconde" in tmp.columns and colonnes:
                rows_parole.append(tmp[["Seconde", *colonnes]].copy())

    if not rows_debit and not rows_parole:
        return pd.DataFrame(columns=["Seconde", "debit_moyen", "parole_s", "pause_s"])

    df_audio: pd.DataFrame | None = None

    if rows_debit:
        df_debit = pd.concat(rows_debit, ignore_index=True)
        df_debit_grouped = (
            df_debit.groupby("Seconde", as_index=False)["debit_seconde"].mean().rename(
                columns={"debit_seconde": "debit_moyen"}
            )
        )
        df_audio = df_debit_grouped

    if rows_parole:
        df_parole = pd.concat(rows_parole, ignore_index=True)
        agg_cols = {col: "mean" for col in ["parole_s", "pause_s"] if col in df_parole.columns}
        if agg_cols:
            df_parole_grouped = df_parole.groupby("Seconde", as_index=False).agg(agg_cols)
            if df_audio is None:
                df_audio = df_parole_grouped
            else:
                df_audio = pd.merge(df_audio, df_parole_grouped, on="Seconde", how="outer")

    if df_audio is None:
        df_audio = pd.DataFrame(columns=["Seconde", "debit_moyen", "parole_s", "pause_s"])

    return df_audio.sort_values("Seconde").reset_index(drop=True)


def _expand_scores(df_emotions: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Déplie la colonne scores_emotions en colonnes numériques individuelles."""

    df = df_emotions.copy()
    if "scores_emotions" not in df.columns:
        df["scores_emotions"] = [{}] * len(df)

    emotions: set[str] = set()
    for item in df["scores_emotions"]:
        if isinstance(item, dict):
            emotions.update(str(k) for k in item.keys())

    colonnes = sorted(emotions) if emotions else list(DEFAULT_EMOTIONS)

    for emotion in colonnes:
        df[emotion] = df["scores_emotions"].apply(
            lambda d: float(d.get(emotion, np.nan)) if isinstance(d, dict) else np.nan
        )

    return df, colonnes


def _preparer_df_frames(
    df_emotions: pd.DataFrame,
    df_images: pd.DataFrame | None,
    texte_map: dict[int, str],
) -> tuple[pd.DataFrame, list[str]]:
    """Prépare le tableau par image avec les scores émotionnels moyens."""

    if not isinstance(df_emotions, pd.DataFrame) or df_emotions.empty:
        return pd.DataFrame(), []

    df = df_emotions.copy()

    if ("t_image" not in df.columns) or df["t_image"].isna().all():
        if isinstance(df_images, pd.DataFrame) and not df_images.empty:
            mapping = dict(zip(df_images["fichier_image"], df_images["t_image"]))
            df["t_image"] = df["fichier_image"].map(mapping)

    df = df.dropna(subset=["fichier_image"])
    df, emotions = _expand_scores(df)

    if "t_image" not in df.columns:
        df["t_image"] = np.nan

    df = df.dropna(subset=["t_image"]).copy()
    if df.empty:
        return pd.DataFrame(), emotions

    agg_scores = {emotion: "mean" for emotion in emotions}
    base_group = df.groupby(["fichier_image", "t_image"], dropna=False)
    df_scores = base_group.agg(agg_scores).reset_index()
    df_counts = base_group.size().reset_index(name="nb_faces")
    df_frames = pd.merge(df_scores, df_counts, on=["fichier_image", "t_image"], how="left")

    df_frames["Seconde"] = df_frames["t_image"].round().astype("Int64")
    df_frames = df_frames.dropna(subset=["Seconde"]).copy()
    if df_frames.empty:
        return pd.DataFrame(), emotions

    df_frames["Seconde"] = df_frames["Seconde"].astype(int)
    df_frames = df_frames.sort_values(["Seconde", "fichier_image"]).reset_index(drop=True)
    df_frames["Frame_Index"] = np.arange(len(df_frames), dtype=int)
    df_frames["Texte"] = df_frames["Seconde"].map(texte_map)
    df_frames["nb_faces"] = df_frames["nb_faces"].fillna(0).astype(int)

    return df_frames, emotions


def _aggreger_par_seconde(
    df_frames: pd.DataFrame,
    emotions: list[str],
    texte_map: dict[int, str],
) -> pd.DataFrame:
    """Calcule les moyennes émotionnelles par seconde."""

    if df_frames is None or df_frames.empty:
        return pd.DataFrame()

    agg_dict: dict[str, str] = {emotion: "mean" for emotion in emotions}
    agg_dict.update({"nb_faces": "sum", "fichier_image": "nunique"})

    df_seconds = df_frames.groupby("Seconde", dropna=False).agg(agg_dict).reset_index()
    df_seconds = df_seconds.rename(columns={"fichier_image": "nb_images"})
    df_seconds["nb_faces"] = df_seconds["nb_faces"].fillna(0).astype(int)
    df_seconds["nb_images"] = df_seconds["nb_images"].fillna(0).astype(int)

    images_map = df_frames.groupby("Seconde")["fichier_image"].apply(list).to_dict()
    df_seconds["Images"] = df_seconds["Seconde"].map(images_map)
    df_seconds["Texte"] = df_seconds["Seconde"].map(texte_map)

    dominantes: list[str | None] = []
    scores_dom: list[float] = []

    for _, row in df_seconds.iterrows():
        valeurs = np.array([row.get(emotion, np.nan) for emotion in emotions], dtype=float)
        if np.all(np.isnan(valeurs)):
            dominantes.append(None)
            scores_dom.append(np.nan)
            continue
        idx = int(np.nanargmax(valeurs))
        dominantes.append(emotions[idx])
        scores_dom.append(float(valeurs[idx]))

    df_seconds["Emotion_Dominante"] = dominantes
    df_seconds["Score_Emotion_Dominant"] = scores_dom

    return df_seconds.sort_values("Seconde").reset_index(drop=True)


def _calculer_stats_emotions(df_seconds: pd.DataFrame, emotions: list[str]) -> pd.DataFrame:
    """Calcule moyenne et variance des émotions sur la plage sélectionnée."""

    lignes = []
    for emotion in emotions:
        if emotion not in df_seconds.columns:
            continue
        valeurs = pd.to_numeric(df_seconds[emotion], errors="coerce").dropna()
        if valeurs.empty:
            lignes.append({"Emotion": emotion, "Moyenne": np.nan, "Variance": np.nan})
        else:
            lignes.append(
                {
                    "Emotion": emotion,
                    "Moyenne": float(valeurs.mean()),
                    "Variance": float(valeurs.var()),
                }
            )

    return pd.DataFrame(lignes)


def _determiner_clusters(X_pca: np.ndarray) -> tuple[int | None, pd.DataFrame]:
    """Recherche le nombre de clusters optimal via le score de silhouette."""

    n_samples = X_pca.shape[0]
    if n_samples < 3:
        return None, pd.DataFrame(columns=["k", "silhouette"])

    records: list[dict[str, float]] = []
    max_k = min(10, n_samples)

    for k in range(2, max_k + 1):
        try:
            kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = kmeans.fit_predict(X_pca)
            score = silhouette_score(X_pca, labels)
        except Exception:
            continue
        records.append({"k": k, "silhouette": float(score)})

    if not records:
        return None, pd.DataFrame(columns=["k", "silhouette"])

    df_scores = pd.DataFrame(records)
    meilleur_k = int(df_scores.loc[df_scores["silhouette"].idxmax(), "k"])
    return meilleur_k, df_scores


def ui_vecteur_emotionnel() -> None:
    """Interface principale pour la page « Vecteur émotionnel »."""

    st.markdown("### 7. Vecteur émotionnel")
    st.caption(
        "Cette vue réutilise les images (1 fps), les textes alignés et les mesures audio importés dans l'onglet "
        "« 1. Données » afin de construire un profil émotionnel temporel."
    )

    df_emotions = st.session_state.get("df_emotions")
    if not isinstance(df_emotions, pd.DataFrame):
        try:
            df_emotions = pd.DataFrame(df_emotions)
        except Exception:
            df_emotions = None

    if df_emotions is None or df_emotions.empty:
        st.info(
            "Aucun résultat d'émotions n'est disponible. Rendez-vous dans l'onglet « 6. Émotions » pour lancer la "
            "détection avant d'utiliser cette page."
        )
        return

    df_images = st.session_state.get("df_images")
    if not isinstance(df_images, pd.DataFrame):
        try:
            df_images = pd.DataFrame(df_images)
        except Exception:
            df_images = None
    texte_map = _texte_par_seconde()

    df_frames, emotions = _preparer_df_frames(df_emotions, df_images, texte_map)
    if df_frames.empty or not emotions:
        st.warning("Impossible de calculer le vecteur émotionnel : aucune image horodatée exploitable.")
        return

    min_sec = int(df_frames["Seconde"].min())
    max_sec = int(df_frames["Seconde"].max())

    if min_sec == max_sec:
        start_sec, end_sec = min_sec, max_sec
    else:
        start_sec, end_sec = st.slider(
            "Fenêtre temporelle (secondes)",
            min_value=min_sec,
            max_value=max_sec,
            value=(min_sec, max_sec),
            step=1,
        )

    masque = (df_frames["Seconde"] >= start_sec) & (df_frames["Seconde"] <= end_sec)
    df_frames_sel = df_frames.loc[masque].reset_index(drop=True)

    if df_frames_sel.empty:
        st.info("Aucune image dans l'intervalle sélectionné.")
        return

    df_frames_sel["nb_faces"] = df_frames_sel["nb_faces"].fillna(0).astype(int)

    st.markdown("#### Scores émotionnels par image (1 fps)")
    colonnes_frames = [
        "Frame_Index",
        "fichier_image",
        "Seconde",
        "nb_faces",
        "Texte",
        *emotions,
    ]
    df_affichage_frames = df_frames_sel[colonnes_frames].rename(
        columns={
            "Frame_Index": "Index_frame",
            "fichier_image": "Image",
            "nb_faces": "Visages_detectés",
            "Texte": "Texte_aligné",
        }
    )
    st.dataframe(df_affichage_frames, use_container_width=True)

    df_frames_long = df_frames_sel.melt(
        id_vars=["Frame_Index", "Seconde"],
        value_vars=emotions,
        var_name="Emotion",
        value_name="Score",
    ).dropna(subset=["Score"])

    if not df_frames_long.empty:
        streamgraph_frames = alt.Chart(df_frames_long).mark_area().encode(
            x=alt.X("Frame_Index:Q", title="Index image (1 fps)"),
            y=alt.Y("Score:Q", title="Score émotionnel", stack="center"),
            color=alt.Color("Emotion:N", title="Émotion"),
            tooltip=[
                alt.Tooltip("Frame_Index:Q", title="Index"),
                alt.Tooltip("Seconde:Q", title="Seconde"),
                alt.Tooltip("Emotion:N", title="Émotion"),
                alt.Tooltip("Score:Q", title="Score", format=".3f"),
            ],
        ).properties(height=320)
        st.altair_chart(streamgraph_frames, use_container_width=True)
    else:
        st.caption("Aucun score émotionnel exploitable pour l'affichage par image.")

    df_seconds = _aggreger_par_seconde(df_frames_sel, emotions, texte_map)
    audio_features = _collecter_audio_features()
    if not audio_features.empty:
        df_seconds = df_seconds.merge(audio_features, on="Seconde", how="left")

    if df_seconds.empty:
        st.warning("Les moyennes par seconde n'ont pas pu être calculées sur cette plage.")
        return

    st.markdown("#### Moyenne des émotions par seconde")
    colonnes_seconds = [
        "Seconde",
        "Texte",
        "nb_images",
        "nb_faces",
        "Emotion_Dominante",
        "Score_Emotion_Dominant",
        *emotions,
    ]
    for col in ["debit_moyen", "parole_s", "pause_s"]:
        if col in df_seconds.columns:
            colonnes_seconds.append(col)

    df_affichage_seconds = df_seconds[colonnes_seconds].rename(
        columns={
            "Texte": "Texte_aligné",
            "nb_images": "Images",
            "nb_faces": "Visages",
            "Emotion_Dominante": "Émotion_dominante",
            "Score_Emotion_Dominant": "Score_dominant",
            "debit_moyen": "Débit_moyen",
            "parole_s": "Parole_s",
            "pause_s": "Pause_s",
        }
    )
    st.dataframe(df_affichage_seconds, use_container_width=True)

    df_seconds_long = df_seconds.melt(
        id_vars=["Seconde"],
        value_vars=emotions,
        var_name="Emotion",
        value_name="Score",
    ).dropna(subset=["Score"])

    if not df_seconds_long.empty:
        streamgraph_seconds = alt.Chart(df_seconds_long).mark_area().encode(
            x=alt.X("Seconde:Q", title="Seconde"),
            y=alt.Y("Score:Q", title="Score moyen", stack="center"),
            color=alt.Color("Emotion:N", title="Émotion"),
            tooltip=[
                alt.Tooltip("Seconde:Q", title="Seconde"),
                alt.Tooltip("Emotion:N", title="Émotion"),
                alt.Tooltip("Score:Q", title="Score", format=".3f"),
            ],
        ).properties(height=320)
        st.altair_chart(streamgraph_seconds, use_container_width=True)

    df_stats = _calculer_stats_emotions(df_seconds, emotions)
    if not df_stats.empty:
        st.markdown("#### Statistiques globales (moyenne / variance)")
        st.dataframe(df_stats, use_container_width=True)
        chart_stats = alt.Chart(df_stats).mark_bar().encode(
            x=alt.X("Emotion:N", title="Émotion"),
            y=alt.Y("Moyenne:Q", title="Moyenne"),
            color=alt.Color("Emotion:N", legend=None),
            tooltip=[alt.Tooltip("Emotion:N", title="Émotion"), alt.Tooltip("Moyenne:Q", format=".3f")],
        )
        chart_var = alt.Chart(df_stats).mark_point(size=100, color="red").encode(
            x="Emotion:N",
            y=alt.Y("Variance:Q", title="Variance"),
            tooltip=[alt.Tooltip("Emotion:N", title="Émotion"), alt.Tooltip("Variance:Q", format=".3f")],
        )
        st.altair_chart(
            alt.layer(chart_stats, chart_var).resolve_scale(y="independent").properties(height=320),
            use_container_width=True,
        )

    st.markdown("#### Concordancier multimodal")
    colonnes_audio = [col for col in ["debit_moyen", "parole_s", "pause_s"] if col in df_seconds.columns]
    df_concordance = df_seconds[
        [
            "Seconde",
            "Images",
            "Texte",
            "Emotion_Dominante",
            "Score_Emotion_Dominant",
            "nb_images",
            "nb_faces",
            *colonnes_audio,
        ]
    ].copy()
    df_concordance["Images"] = df_concordance["Images"].apply(
        lambda lst: ", ".join(lst) if isinstance(lst, list) else ""
    )
    df_concordance = df_concordance.rename(
        columns={
            "Texte": "Texte_aligné",
            "Emotion_Dominante": "Émotion_dominante",
            "Score_Emotion_Dominant": "Score_dominant",
            "nb_images": "Nb_images",
            "nb_faces": "Nb_visages",
            "debit_moyen": "Débit_moyen",
            "parole_s": "Parole_s",
            "pause_s": "Pause_s",
        }
    )
    st.dataframe(df_concordance, use_container_width=True)

    csv_concordance = df_concordance.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Télécharger le concordancier (CSV)",
        data=csv_concordance,
        file_name="concordancier_vecteur_emotionnel.csv",
        mime="text/csv",
    )

    st.markdown("#### Analyse PCA & clustering K-means")
    df_modele = df_seconds[emotions].apply(pd.to_numeric, errors="coerce")
    if df_modele.dropna(how="all").empty:
        st.info("Les scores émotionnels ne contiennent pas assez de valeurs numériques pour l'analyse PCA/K-means.")
        return

    df_modele = df_modele.fillna(df_modele.mean(numeric_only=True))
    df_modele = df_modele.fillna(0.0)

    if len(df_modele) < 2:
        st.info("Au moins deux secondes sont nécessaires pour la PCA et le clustering.")
        return

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_modele.to_numpy(dtype=float))
    n_components = min(len(emotions), len(df_modele))
    pca = PCA(n_components=n_components, random_state=42)
    X_pca = pca.fit_transform(X_scaled)

    df_variance = pd.DataFrame(
        {
            "Composante": [f"PC{i+1}" for i in range(len(pca.explained_variance_ratio_))],
            "Variance_expliquee": pca.explained_variance_ratio_ * 100,
        }
    )
    st.dataframe(df_variance, use_container_width=True)
    st.altair_chart(
        alt.Chart(df_variance)
        .mark_bar()
        .encode(
            x=alt.X("Composante", sort=None),
            y=alt.Y("Variance_expliquee", title="Variance expliquée (%)"),
            tooltip=["Composante", alt.Tooltip("Variance_expliquee", format=".2f")],
        )
        .properties(height=320),
        use_container_width=True,
    )

    k_opt, df_silhouette = _determiner_clusters(X_pca)
    if not df_silhouette.empty:
        st.altair_chart(
            alt.Chart(df_silhouette)
            .mark_line(point=True)
            .encode(
                x=alt.X("k:Q", title="Nombre de clusters"),
                y=alt.Y("silhouette:Q", title="Score de silhouette"),
                tooltip=["k", alt.Tooltip("silhouette:Q", format=".3f")],
            )
            .properties(height=260),
            use_container_width=True,
        )

    if k_opt is None:
        st.info("Impossible de déterminer un nombre optimal de clusters (échantillons insuffisants).")
        return

    kmeans = KMeans(n_clusters=k_opt, n_init="auto", random_state=42)
    labels = kmeans.fit_predict(X_pca)
    df_seconds["Cluster"] = labels
    st.caption(f"Nombre optimal de clusters (silhouette) : {k_opt}")
    st.session_state["df_vecteur_emotionnel"] = df_seconds.copy()

    if X_pca.shape[1] >= 2:
        df_seconds["PC1"] = X_pca[:, 0]
        df_seconds["PC2"] = X_pca[:, 1]
        scatter = alt.Chart(df_seconds).mark_circle(size=80).encode(
            x=alt.X("PC1:Q", title="PC1"),
            y=alt.Y("PC2:Q", title="PC2"),
            color=alt.Color("Cluster:N", title="Cluster"),
            tooltip=[
                alt.Tooltip("Seconde:Q", title="Seconde"),
                alt.Tooltip("Cluster:N", title="Cluster"),
                alt.Tooltip("Emotion_Dominante:N", title="Émotion dominante"),
                alt.Tooltip("Score_Emotion_Dominant:Q", title="Score dominant", format=".3f"),
            ]
            + [alt.Tooltip(f"{em}:Q", title=em, format=".3f") for em in emotions],
        ).properties(height=360)
        st.altair_chart(scatter, use_container_width=True)
    else:
        st.caption("La réduction dimensionnelle ne comporte qu'une composante : la projection 2D est omise.")

    similarites = cosine_similarity(kmeans.cluster_centers_)
    df_similarites = pd.DataFrame(
        similarites,
        columns=[f"Cluster {i}" for i in range(k_opt)],
        index=[f"Cluster {i}" for i in range(k_opt)],
    )

    fig, ax = plt.subplots(figsize=(6, 4))
    sns.heatmap(df_similarites, annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
    ax.set_title("Similarité cosinus entre les centroïdes")
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)

    st.markdown(
        "Une similarité proche de 1 indique des clusters capturant des combinaisons émotionnelles proches ; "
        "une valeur proche de 0 témoigne de profils contrastés."
    )

    timeline = alt.Chart(df_seconds).mark_rect().encode(
        x=alt.X("Seconde:O", title="Seconde"),
        y=alt.Y("Cluster:O", title="Cluster"),
        color=alt.Color("Cluster:N", title="Cluster"),
        tooltip=[
            alt.Tooltip("Seconde:Q", title="Seconde"),
            alt.Tooltip("Cluster:N", title="Cluster"),
            alt.Tooltip("Emotion_Dominante:N", title="Émotion dominante"),
            alt.Tooltip("Score_Emotion_Dominant:Q", title="Score", format=".3f"),
        ],
    ).properties(height=200)
    st.altair_chart(timeline, use_container_width=True)

    for cluster in sorted(df_seconds["Cluster"].unique()):
        df_cluster = df_seconds[df_seconds["Cluster"] == cluster]
        if df_cluster.empty:
            continue
        st.markdown(f"##### Moyenne des émotions – Cluster {cluster}")
        df_cluster_mean = df_cluster[emotions].mean().reset_index()
        df_cluster_mean.columns = ["Émotion", "Moyenne"]
        st.dataframe(df_cluster_mean, use_container_width=True)

