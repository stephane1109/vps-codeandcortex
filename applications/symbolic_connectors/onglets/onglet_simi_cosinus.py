"""# Onglet Similarité cosinus

Ce module alimente l'onglet Streamlit qui calcule la similarité cosinus entre
groupes de textes, avec filtrage par variables et option de suppression des
stopwords.

## Dépendances
- `simicosinus.py` : agrégation des textes, construction de la matrice TF-IDF
  et calcul de la similarité cosinus.
- `fcts_utils.py` : affichage centré des graphiques dans l'interface.
- Bibliothèques `streamlit`, `pandas` et `altair` pour la sélection des
  modalités et la visualisation des matrices.
"""
from __future__ import annotations

from typing import List

import altair as alt
import pandas as pd
import streamlit as st

from fcts_utils import display_centered_chart
from simicosinus import (
    aggregate_texts_by_variables,
    concatenate_texts_with_headers,
    compute_cosine_similarity_matrix,
    get_french_stopwords,
)


def rendu_simi_cosinus(tab, df: pd.DataFrame) -> None:
    st.subheader("Simi cosinus")

    cosine_variables = [
        column for column in df.columns if column not in ("texte", "entete")
    ]

    if not cosine_variables:
        st.info("Aucune variable n'a été trouvée dans le fichier importé.")
        return

    selected_cosine_variables = st.multiselect(
        "Variables à filtrer pour la similarité cosinus",
        cosine_variables,
        default=cosine_variables,
        help=(
            "Sélectionnez les variables à prendre en compte puis choisissez les modalités "
            "à conserver pour chacune d'elles."
        ),
    )

    if not selected_cosine_variables:
        st.info("Sélectionnez au moins une variable pour calculer la similarité cosinus.")
        return

    cosine_filtered_df = df.copy()
    for variable in selected_cosine_variables:
        modality_options = sorted(
            cosine_filtered_df[variable].dropna().unique().tolist()
        )
        selected_modalities = st.multiselect(
            f"Modalités à inclure pour {variable}",
            modality_options,
            default=modality_options,
            help="Choisissez les modalités dont les textes seront pris en compte.",
        )

        if selected_modalities:
            cosine_filtered_df = cosine_filtered_df[
                cosine_filtered_df[variable].isin(selected_modalities)
            ]
        else:
            cosine_filtered_df = cosine_filtered_df.iloc[0:0]

    if cosine_filtered_df.empty:
        st.info(
            "Aucun texte ne correspond aux filtres appliqués. Ajustez vos sélections pour "
            "poursuivre."
        )
        return

    cosine_df = cosine_filtered_df

    apply_stopwords = st.checkbox(
        "Appliquer les stopwords français (NLTK) avant le calcul",
        value=False,
        help=(
            "Supprime les mots vides français fournis par NLTK avant de construire"
            " la matrice TF-IDF."
        ),
    )

    aggregated_texts = aggregate_texts_by_variables(
        cosine_df, selected_cosine_variables
    )

    aggregated_export_text = concatenate_texts_with_headers(
        cosine_filtered_df, selected_cosine_variables
    )

    if aggregated_export_text:
        st.download_button(
            label="Télécharger les textes concaténés par sélection",
            data=aggregated_export_text,
            file_name="textes_concatenation_simicosi.txt",
            mime="text/plain",
            help=(
                "Export des textes regroupés selon les variables et modalités choisies "
                "pour vérifier la composition de la matrice TF-IDF."
            ),
        )

    if len(aggregated_texts) < 2:
        st.info(
            "Au moins deux groupes de modalités doivent contenir du texte pour calculer la similarité cosinus."
        )
        return

    group_labels = sorted(aggregated_texts.keys())
    ordered_texts = {label: aggregated_texts[label] for label in group_labels}
    texts_summary = pd.DataFrame(
        {
            "Groupe": group_labels,
            "Mots": [len(aggregated_texts[label].split()) for label in group_labels],
        }
    )

    st.markdown("### Textes regroupés")
    st.dataframe(texts_summary, use_container_width=True)

    stop_words = get_french_stopwords() if apply_stopwords else None

    similarity_df = compute_cosine_similarity_matrix(
        ordered_texts, stop_words=stop_words
    )

    if similarity_df.empty:
        st.info("Impossible de calculer la matrice de similarité cosinus avec les données fournies.")
        return

    st.markdown("### Matrice de similarité cosinus")
    st.dataframe(similarity_df.style.format("{:.4f}"), use_container_width=True)

    similarity_long = (
        similarity_df.reset_index()
        .rename(columns={"index": "Groupe"})
        .melt(id_vars="Groupe", var_name="Comparé à", value_name="Similarité")
    )

    modalities_order = similarity_df.index.tolist()

    heatmap = (
        alt.Chart(similarity_long)
        .mark_rect()
        .encode(
            x=alt.X("Groupe:N", sort=modalities_order),
            y=alt.Y("Comparé à:N", sort=modalities_order),
            color=alt.Color(
                "Similarité:Q",
                scale=alt.Scale(
                    domain=[0, 0.5, 1],
                    range=["#f7fbff", "#4292c6", "#08306b"],
                ),
                title="Cosinus",
            ),
            tooltip=["Groupe", "Comparé à", alt.Tooltip("Similarité:Q", format=".4f")],
        )
        .properties(
            title="Carte de chaleur des similarités",
            width=alt.Step(80),
            height=alt.Step(80),
        )
    )

    display_centered_chart(heatmap)
