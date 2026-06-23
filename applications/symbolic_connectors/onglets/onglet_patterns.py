"""# Onglet Patterns

Ce module pilote l'onglet Streamlit permettant de rechercher et d'annoter des
motifs personnalisés dans le corpus, en affichant les segments correspondants
et leurs métadonnées.

## Dépendances
- `pattern.py` : détection des segments contenant le motif et annotation HTML
  du texte combiné.
- `densite.py` : assemblage du texte complet utilisé pour les annotations.
- `fcts_utils.py` : génération du bloc de styles pour les surlignages.
- Bibliothèques `streamlit`, `pandas` et `altair` pour l'interface, la
  sélection des variables et les graphiques éventuels.
"""
from __future__ import annotations

from typing import List

import altair as alt
import pandas as pd
import streamlit as st

from densite import build_text_from_dataframe
from fcts_utils import build_annotation_style_block
from pattern import annotate_user_pattern_html, find_pattern_segments


def _normalize_text_without_blank_lines(text: str) -> str:
    """Nettoyer le texte pour supprimer les lignes vides et unifier les sauts de ligne."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    non_empty_lines = [line for line in normalized.split("\n") if line.strip()]
    return "\n".join(non_empty_lines)


def format_modalities_for_row(row: pd.Series, variables: List[str]) -> str:
    parts: List[str] = []

    for variable in variables:
        value = row.get(variable, "")

        if pd.isna(value) or value == "":
            continue

        parts.append(f"{variable} = {value}")

    header = str(row.get("entete", "")).strip()

    if parts:
        return " | ".join(parts)

    return header or "Non spécifié"


def rendu_patterns(
    tab,
    filtered_df: pd.DataFrame,
    combined_text: str,
    selected_variables: List[str],
) -> None:
    st.subheader("Patterns (motifs)")
    st.markdown(
        "Saisissez un motif (mot, expression ou signe tel que « ? ») pour identifier les segments qui le contiennent."
    )

    pattern_query = st.text_input(
        "Motif ou signe à rechercher", placeholder="?", key="simple_pattern_query"
    )

    show_only_matching_texts = st.checkbox(
        "Afficher uniquement les textes contenant le motif",
        value=False,
        help="Filtre le corpus et les résultats pour ne conserver que les textes où le motif apparaît.",
    )

    if not pattern_query:
        return

    cleaned_combined_text = _normalize_text_without_blank_lines(combined_text)
    enriched_segments: List[dict] = []
    segment_counter = 1
    matched_rows: List[pd.Series] = []

    for _, row in filtered_df.iterrows():
        row_text = _normalize_text_without_blank_lines(
            build_text_from_dataframe(pd.DataFrame([row]))
        )

        if not row_text:
            continue

        modalities_label = format_modalities_for_row(row, selected_variables)

        row_segments = find_pattern_segments(row_text, pattern_query)
        if row_segments:
            matched_rows.append(row)

        for segment in row_segments:
            enriched_segments.append(
                {
                    "modalites": modalities_label,
                    "segment_id": segment_counter,
                    "segment": segment.get("segment"),
                    "occurrences": segment.get("occurrences", 0),
                }
            )
            segment_counter += 1

    should_restrict_text = show_only_matching_texts
    text_to_annotate = (
        _normalize_text_without_blank_lines(
            build_text_from_dataframe(pd.DataFrame(matched_rows))
        )
        if should_restrict_text
        else cleaned_combined_text
    )

    pattern_annotation_style = build_annotation_style_block("")
    annotated_pattern_html = annotate_user_pattern_html(text_to_annotate, pattern_query)

    st.subheader("Texte annoté par motif")
    st.markdown(pattern_annotation_style, unsafe_allow_html=True)
    st.markdown(
        f"<div class='annotated-container'>{annotated_pattern_html}</div>",
        unsafe_allow_html=True,
    )

    annotated_download = f"""<!DOCTYPE html>
    <html lang=\"fr\">
    <head>
    <meta charset=\"utf-8\" />
    {pattern_annotation_style}
    </head>
    <body>
    <div class='annotated-container'>{annotated_pattern_html}</div>
    </body>
    </html>"""

    st.download_button(
        label="Télécharger le texte annoté par patterns",
        data=annotated_download,
        file_name="texte_annotes_patterns.html",
        mime="text/html",
    )

    if not enriched_segments:
        st.info("Aucun segment ne contient ce motif dans le texte filtré.")
        return

    segments_df = pd.DataFrame(enriched_segments)[
        ["modalites", "segment_id", "segment", "occurrences"]
    ].rename(
        columns={
            "modalites": "Variables/modalités",
            "segment_id": "Segment",
            "segment": "Texte",
            "occurrences": "Occurrences",
        }
    )

    st.markdown("Segments contenant le motif")
    st.dataframe(segments_df, use_container_width=True)

    chart_df = segments_df.rename(
        columns={
            "Variables/modalités": "modalite",
            "Occurrences": "Occurrences",
        }
    )

    occurrences_by_modality = (
        chart_df.groupby("modalite", as_index=False)["Occurrences"].sum()
    )

    if occurrences_by_modality.empty:
        st.info("Aucune répartition par variables/modalités n'est disponible.")
        return

    chart = (
        alt.Chart(occurrences_by_modality)
        .mark_bar()
        .encode(
            x=alt.X("modalite:N", sort="-y", title="Variable / modalité"),
            y=alt.Y("Occurrences:Q", title="Occurrences du motif"),
            color=alt.Color("modalite:N", title="Variable / modalité"),
            tooltip=["modalite", "Occurrences"],
        )
        .properties(title="Occurrences du motif par variables/modalités")
    )

    st.altair_chart(chart, use_container_width=True)
