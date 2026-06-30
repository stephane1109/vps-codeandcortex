"""# Onglet Densité

Ce module gère l'onglet Streamlit dédié au calcul de la densité des
connecteurs (nombre d'occurrences rapporté à 1 000 mots) et à leur
visualisation par modalité.

## Dépendances
- `densite.py` : construction du texte filtré et calculs de densité,
  comptages et filtrages par modalité.
- `fcts_utils.py` : rappel des connecteurs sélectionnés à l'écran.
- `graphiques/densitegraph.py` : génération des graphiques Altair pour les
  densités globales et par connecteur.
- Bibliothèques `streamlit`, `pandas` et `altair` pour l'interface et les
  visualisations.
"""
from __future__ import annotations

from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from densite import (
    build_text_from_dataframe,
    compute_density,
    compute_density_per_modality,
    compute_density_per_modality_by_label,
    compute_total_connectors,
    count_words,
)
from fcts_utils import render_connectors_reminder
from simicosinus import concatenate_texts_with_headers
from graphiques.densitegraph import build_connector_density_chart, build_density_chart


def rendu_densite(tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    render_connectors_reminder(filtered_connectors)
    st.write(
        "Densité des textes analysés : La densité correspond au nombre de connecteurs "
        "ramené à une base de 1 000 mots. "
    )
    if not filtered_connectors:
        st.info("Sélectionnez au moins un connecteur pour calculer la densité.")
        return

    st.subheader("Sélection des variables/modalités")
    density_variables = [
        column for column in df.columns if column not in ("texte", "entete")
    ]

    if not density_variables:
        st.info("Aucune variable n'a été trouvée dans le fichier importé.")
        return

    selected_density_variables = st.multiselect(
        "Variables à filtrer pour la densité",
        density_variables,
        default=density_variables,
        help=(
            "Sélectionnez les variables et modalités à inclure avant de calculer la "
            "densité."
        ),
    )

    if not selected_density_variables:
        st.info("Sélectionnez au moins une variable pour calculer la densité.")
        return

    density_modality_filters: Dict[str, List[str]] = {}
    density_filtered_df = df.copy()

    for variable in selected_density_variables:
        modality_options = sorted(
            density_filtered_df[variable].dropna().unique().tolist()
        )
        selected_modalities = st.multiselect(
            f"Modalités à inclure pour {variable}",
            modality_options,
            default=modality_options,
            help=(
                "Sélectionnez les modalités dont les textes seront pris en compte pour"
                " cette variable."
            ),
        )
        density_modality_filters[variable] = selected_modalities

        if selected_modalities:
            density_filtered_df = density_filtered_df[
                density_filtered_df[variable].isin(selected_modalities)
            ]
        else:
            density_filtered_df = density_filtered_df.iloc[0:0]

    if density_filtered_df.empty:
        st.info(
            "Aucun texte ne correspond aux filtres appliqués. Ajustez vos sélections pour"
            " continuer."
        )
        return

    density_text = concatenate_texts_with_headers(
        density_filtered_df, selected_density_variables
    )
    if density_text:
        st.download_button(
            label="Télécharger les textes concaténés",
            data=density_text,
            file_name="textes_concatenation_densite.txt",
            mime="text/plain",
            help=(
                "Export des textes regroupés selon les variables et modalités choisies "
                "pour vérifier la composition de la densité."
            ),
        )
    else:
        st.info(
            "Impossible de générer le texte concaténé pour les données filtrées. Vérifiez"
            " vos sélections."
        )

    density_text = build_text_from_dataframe(density_filtered_df)
    if not density_text:
        st.info(
            "Aucun texte disponible avec les modalités sélectionnées pour calculer la densité."
        )
        return

    base = 1000

    total_words = count_words(density_text)
    total_connectors = compute_total_connectors(density_text, filtered_connectors)
    density = compute_density(density_text, filtered_connectors, base=base)

    col1, col2, col3 = st.columns(3)
    col1.metric("Nombre total de mots", f"{total_words:,}".replace(",", " "))
    col2.metric("Occurrences de connecteurs", f"{total_connectors:,}".replace(",", " "))
    col3.metric(f"Densité pour {base:,} mots", f"{density:.2f}".replace(",", " "))

    if total_connectors == 0:
        st.info("Aucun connecteur détecté : la densité est nulle pour ce texte.")

    st.caption(
        "Un score élevé signale un texte plus riche en connecteurs logiques."
    )

    for variable in selected_density_variables:
        st.markdown(f"### Analyse par variable : {variable}")

        per_modality_df = compute_density_per_modality(
            density_filtered_df,
            variable,
            filtered_connectors,
            base=base,
        )
        per_modality_label_df = compute_density_per_modality_by_label(
            density_filtered_df,
            variable,
            filtered_connectors,
            base=base,
        )

        if per_modality_df.empty:
            selected_modalities = density_modality_filters.get(variable, [])
            if selected_modalities:
                st.info(
                    "Aucun texte ne correspond aux modalités choisies : impossible de calculer la densité."
                )
            else:
                st.info(
                    "Aucune modalité n'a été trouvée pour cette variable dans les données sélectionnées."
                )
            continue

        st.subheader(f"Modalité(s) sélectionnée(s) de la variable : {variable}")
        modality_display_df = per_modality_df.copy()
        modality_display_df["densite"] = modality_display_df["densite"].apply(
            lambda value: f"{value:.2f}"
        )
        modality_display_df["mots"] = modality_display_df["mots"].apply(
            lambda value: f"{int(value)}"
        )
        modality_display_df["connecteurs"] = modality_display_df["connecteurs"].apply(
            lambda value: f"{int(value)}"
        )

        modality_display_df = modality_display_df.rename(
            columns={
                "modalite": "Modalité",
                "densite": "Densité",
                "mots": "Mots comptés",
                "connecteurs": "Connecteurs",
            }
        )

        st.dataframe(
            modality_display_df,
            use_container_width=True,
            column_config={
                "Densité": st.column_config.TextColumn("Densité"),
                "Mots comptés": st.column_config.TextColumn("Mots comptés"),
                "Connecteurs": st.column_config.TextColumn("Connecteurs"),
            },
        )

        st.markdown("#### Graphique de densité")
        st.altair_chart(
            build_density_chart(per_modality_df),
            use_container_width=True,
        )

        if not per_modality_label_df.empty:
            st.markdown("#### Densité par connecteur et modalité")
            modality_label_display_df = per_modality_label_df.copy()
            modality_label_display_df["densite"] = modality_label_display_df[
                "densite"
            ].apply(lambda value: f"{value:.2f}")
            modality_label_display_df["mots"] = modality_label_display_df[
                "mots"
            ].apply(lambda value: f"{int(value)}")
            modality_label_display_df["connecteurs"] = modality_label_display_df[
                "connecteurs"
            ].apply(lambda value: f"{int(value)}")

            modality_label_display_df = modality_label_display_df.rename(
                columns={
                    "modalite": "Modalité",
                    "label": "Connecteur",
                    "densite": "Densité",
                    "mots": "Mots comptés",
                    "connecteurs": "Connecteurs",
                }
            )

            st.dataframe(
                modality_label_display_df,
                use_container_width=True,
                column_config={
                    "Densité": st.column_config.TextColumn("Densité"),
                    "Mots comptés": st.column_config.TextColumn("Mots comptés"),
                    "Connecteurs": st.column_config.TextColumn("Connecteurs"),
                },
            )

            st.altair_chart(
                build_connector_density_chart(per_modality_label_df),
                use_container_width=True,
            )
