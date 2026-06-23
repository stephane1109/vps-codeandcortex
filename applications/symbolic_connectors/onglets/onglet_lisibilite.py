"""# Onglet Lisibilité

Ce module orchestre l'onglet Streamlit consacré au calcul des indicateurs de
lisibilité Flesch-Kincaid sur un corpus filtré selon les variables
saisies.

## Dépendances
- `densite.py` : construction du texte combiné à partir du DataFrame filtré.
- `test_lesch_Kincaid.py` : calcul des scores Flesch-Kincaid, bande de
  difficulté et messages d'interprétation.
- `fcts_utils.py` : affichage des connecteurs actifs pour guider
  l'utilisateur.
- Bibliothèques `streamlit` et `pandas` pour la sélection des modalités et la
  restitution des résultats.
"""
from __future__ import annotations

from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from densite import build_text_from_dataframe
from fcts_utils import render_connectors_reminder
from test_lesch_Kincaid import (
    READABILITY_SCALE,
    compute_flesch_kincaid_metrics,
    get_readability_band,
    interpret_reading_ease,
)


def rendu_lisibilite(tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    st.subheader("Test de lisibilité (Flesch-Kincaid)")
    st.markdown(
        "Le calcul est réalisé à partir du texte composé uniquement des connecteurs sélectionnés.\n"
        "Les scores indiquent simplement la facilité de lecture estimée du corpus filtré."
    )
    render_connectors_reminder(filtered_connectors)

    st.markdown("### Sélection des variables/modalités")

    readability_variables = [
        column for column in df.columns if column not in ("texte", "entete")
    ]
    readability_selected_variables = st.multiselect(
        "Variables disponibles pour la lisibilité",
        readability_variables,
        default=readability_variables,
        help="Choisissez les variables à filtrer pour le test de lisibilité.",
        key="readability_variables",
    )

    readability_filtered_df = df.copy()
    readability_modalities_selection: Dict[str, List[str]] = {}

    for variable in readability_selected_variables:
        modality_options = sorted(
            readability_filtered_df[variable].dropna().unique().tolist()
        )
        selected_modalities = st.multiselect(
            f"Modalités à inclure pour {variable}",
            modality_options,
            default=modality_options,
            help="Filtrer les textes utilisés pour le test de lisibilité.",
        )
        readability_modalities_selection[variable] = selected_modalities
        if selected_modalities:
            readability_filtered_df = readability_filtered_df[
                readability_filtered_df[variable].isin(selected_modalities)
            ]
        else:
            readability_filtered_df = readability_filtered_df.iloc[0:0]

    if readability_filtered_df.empty:
        st.info("Aucun texte ne correspond aux filtres sélectionnés.")
        return

    readability_text = build_text_from_dataframe(readability_filtered_df)
    if not readability_text:
        st.info("Aucun texte valide à analyser pour la lisibilité.")
        return

    readability_metrics = compute_flesch_kincaid_metrics(readability_text)

    st.markdown("### Résultats de lisibilité")

    if readability_metrics is None:
        st.info("Impossible de calculer les scores de lisibilité pour le texte fourni.")
        return

    ease_score = readability_metrics.get("reading_ease", 0.0)
    st.metric(
        "Flesch Reading Ease",
        f"{ease_score:.2f}",
        help="Indice mesurant la facilité de lecture (plus il est élevé, plus le texte est facile).",
    )

    readability_band = get_readability_band(ease_score)
    readability_description = interpret_reading_ease(ease_score)

    st.markdown(
        f"**Interprétation** : {readability_description} (échelle : {readability_band.get('range', '')})"
    )

    st.markdown("#### Échelle visuelle du score de lisibilité")
    readability_scale_df = pd.DataFrame(READABILITY_SCALE)
    readability_scale_df["band"] = "Échelle Flesch Reading Ease"

    bands_chart = (
        alt.Chart(readability_scale_df)
        .mark_bar(height=45)
        .encode(
            x=alt.X(
                "min:Q",
                title="Indice de lisibilité (Flesch Reading Ease)",
                scale=alt.Scale(domain=[0, 100]),
            ),
            x2="max:Q",
            y=alt.Y("band:N", title=None, axis=None),
            color=alt.Color(
                "range:N",
                title="Plages de lisibilité",
                sort="descending",
                scale=alt.Scale(scheme="blues"),
            ),
            tooltip=[
                alt.Tooltip("range:N", title="Plage"),
                alt.Tooltip("niveau:N", title="Niveau"),
                alt.Tooltip("description:N", title="Description"),
            ],
        )
    )

    score_df = pd.DataFrame(
        {"score": [ease_score], "band": ["Échelle Flesch Reading Ease"]}
    )
    score_marker = (
        alt.Chart(score_df)
        .mark_rule(color="black", strokeWidth=3, strokeDash=[6, 4])
        .encode(
            x=alt.X("score:Q", title="Indice de lisibilité (Flesch Reading Ease)"),
            y=alt.Y("band:N"),
            tooltip=[alt.Tooltip("score:Q", title="Score", format=".2f")],
        )
    )

    score_label = (
        alt.Chart(score_df)
        .mark_text(align="left", dx=5, dy=-10, fontWeight="bold")
        .encode(x="score:Q", y="band:N", text=alt.Text("score:Q", format=".2f"))
    )

    st.altair_chart((bands_chart + score_marker + score_label), use_container_width=True)

    st.caption(
        "Les scores de lisibilité sont calculés sur la base du texte filtré, en utilisant les variables/modalités sélectionnées."
    )

    st.markdown("#### Tableau de référence (source : Wikipédia)")
    readability_reference_df = readability_scale_df.rename(
        columns={
            "range": "Score",
            "description": "Notes",
        }
    )[["Score", "Notes"]]
    st.table(readability_reference_df)

    readability_per_modality: List[Dict[str, float | str]] = []

    for variable, selected_modalities in readability_modalities_selection.items():
        for modality in selected_modalities:
            modality_df = readability_filtered_df[
                readability_filtered_df[variable] == modality
            ]
            modality_text = build_text_from_dataframe(modality_df)
            if not modality_text:
                continue

            modality_metrics = compute_flesch_kincaid_metrics(modality_text)
            readability_per_modality.append(
                {
                    "variable": variable,
                    "modalite": modality,
                    "reading_ease": modality_metrics.get("reading_ease", 0.0),
                }
            )

    if readability_per_modality:
        st.markdown("### Score de lisibilité par modalité")
        modality_scores_df = pd.DataFrame(readability_per_modality)
        modality_scores_df = modality_scores_df.sort_values(
            by=["variable", "reading_ease"], ascending=[True, False]
        )

        display_df = modality_scores_df.rename(
            columns={
                "variable": "Variable",
                "modalite": "Modalité",
                "reading_ease": "Indice de lisibilité",
            }
        )
        display_df["Indice de lisibilité"] = display_df["Indice de lisibilité"].apply(
            lambda score: f"{score:.2f}"
        )
        st.dataframe(display_df, use_container_width=True)

    else:
        st.info(
            "Aucun score modalité n'a pu être calculé avec la sélection actuelle."
        )
