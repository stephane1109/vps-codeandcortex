"""# Onglet Données brutes

Ce module affiche l'onglet Streamlit consacré au filtrage des variables du
corpus, à la visualisation du texte combiné et aux statistiques descriptives
sur les connecteurs.

## Dépendances
- `analyses.py` : annotations et comptage des connecteurs, génération des
  styles de surlignage.
- `connecteurs.py` : récupération des connecteurs et étiquettes sélectionnés.
- `densite.py` : concaténation des textes et comptage global des mots.
- `fcts_utils.py` : calcul des statistiques par variable et rappel des
  connecteurs actifs.
- Bibliothèques `streamlit`, `pandas` et `altair` pour l'interface et les
  graphiques.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import streamlit as st
from analyses import (
    annotate_connectors_html,
    build_label_style_block,
    count_connectors,
    generate_label_colors,
)
from connecteurs import get_selected_connectors, get_selected_labels
from densite import (
    build_text_from_dataframe,
    compute_total_connectors,
    count_words,
)
from fcts_utils import (
    build_annotation_style_block,
    build_variable_stats,
    render_connectors_reminder,
)


def rendu_donnees_brutes(
    tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]
) -> Optional[Tuple[pd.DataFrame, List[str], str]]:
    variable_names = [column for column in df.columns if column not in ("texte", "entete")]
    st.subheader("Filtrer par variables")
    render_connectors_reminder(filtered_connectors)
    selected_variables = st.multiselect(
        "Variables disponibles", variable_names, default=variable_names
    )

    modality_filters: Dict[str, List[str]] = {}
    filtered_df = df.copy()

    for variable in selected_variables:
        options = sorted(filtered_df[variable].dropna().unique().tolist())
        selected_modalities = st.multiselect(
            f"Modalités pour {variable}", options, default=options
        )
        modality_filters[variable] = selected_modalities
        filtered_df = filtered_df[filtered_df[variable].isin(selected_modalities)]

    combined_text = build_text_from_dataframe(filtered_df)

    st.subheader("Texte combiné")
    if combined_text:
        flattened_text = combined_text.replace("\r\n", "\n")
        st.text_area("", flattened_text, height=200)
    else:
        st.info("Aucun texte ne correspond aux filtres sélectionnés.")
        return None

    if not filtered_connectors:
        st.info("Choisissez des connecteurs dans l'onglet « Connecteurs » pour poursuivre.")
        return None

    selected_labels = get_selected_labels(filtered_connectors.values())

    label_colors = generate_label_colors(filtered_connectors.values())
    label_style_block = build_label_style_block(label_colors)
    annotation_style_block = build_annotation_style_block(label_style_block)
    annotated_html = annotate_connectors_html(combined_text, filtered_connectors)

    st.markdown(annotation_style_block, unsafe_allow_html=True)
    st.subheader("Connecteurs annotés")

    downloadable_html = f"""<!DOCTYPE html>
    <html lang=\"fr\">
    <head>
    <meta charset=\"utf-8\" />
    {annotation_style_block}
    </head>
    <body>
    <div class='annotated-container'>{annotated_html}</div>
    </body>
    </html>"""

    st.markdown(
        f"<div class='annotated-container'>{annotated_html}</div>",
        unsafe_allow_html=True,
    )
    st.download_button(
        label="Télécharger le texte annoté (HTML)",
        data=downloadable_html,
        file_name="texte_annote_connecteurs.html",
        mime="text/html",
    )

    st.subheader("Statistiques des connecteurs")

    stats_df = count_connectors(combined_text, filtered_connectors)

    if stats_df.empty:
        st.info("Aucun connecteur trouvé dans le texte sélectionné.")
    else:
        stats_df = (
            stats_df.sort_values("occurrences", ascending=False)
            .reset_index(drop=True)
        )

        st.dataframe(stats_df, use_container_width=True)

        st.subheader("Fréquences des connecteurs")

        chart = (
            alt.Chart(stats_df)
            .mark_bar()
            .encode(
                x=alt.X("connecteur", sort="-y", title="Connecteur"),
                y=alt.Y("occurrences", title="Occurrences"),
                color=alt.Color("label", title="Label"),
                tooltip=["connecteur", "label", "occurrences"],
            )
        )
        st.altair_chart(chart, use_container_width=True)

    st.subheader("Statistiques par variables")

    selected_labels = sorted(set(filtered_connectors.values()))

    variable_stats_df = build_variable_stats(
        filtered_df, selected_variables, filtered_connectors, selected_labels
    )

    if variable_stats_df.empty:
        st.info("Aucune donnée disponible pour les statistiques par variables.")
    else:
        variable_chart = (
            alt.Chart(variable_stats_df)
            .mark_bar()
            .encode(
                x=alt.X("modalite:N", title="Modalité"),
                xOffset="label",
                y=alt.Y("occurrences:Q", title="Occurrences"),
                color=alt.Color("label:N", title="Connecteur"),
                column=alt.Column("variable:N", title="Variable"),
                tooltip=["variable", "modalite", "label", "occurrences"],
            )
            .properties(spacing=20)
        )

        st.altair_chart(variable_chart, use_container_width=True)

    return filtered_df, selected_variables, combined_text
