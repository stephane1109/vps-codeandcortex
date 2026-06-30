"""# Onglet Regex motifs

Ce module gère l'onglet Streamlit dédié à l'analyse de motifs regex complexes
dans le corpus, en chargeant un dictionnaire JSON et en affichant les
annotations et statistiques associées.

## Dépendances
- `regexanalyse.py` : chargement des règles regex, segmentation du texte et
  calcul des statistiques de correspondance.
- `analyses.py` : génération des couleurs et styles de labels pour les
  annotations.
- `fcts_utils.py` : construction du bloc de styles pour l'affichage HTML.
- Bibliothèques `streamlit`, `pandas`, `altair` et `pathlib` pour la gestion
  de l'interface, des données et du chemin vers les ressources.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import altair as alt
import pandas as pd
import streamlit as st

from analyses import build_label_style_block, generate_label_colors
from fcts_utils import build_annotation_style_block
from regexanalyse import (
    count_segments_by_pattern,
    highlight_matches_html,
    load_regex_rules,
    split_segments,
    summarize_matches_by_segment,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def _normalize_text_without_blank_lines(text: str) -> str:
    """Nettoyer le texte pour supprimer les lignes vides et unifier les sauts de ligne."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    non_empty_lines = [line for line in normalized.split("\n") if line.strip()]
    return "\n".join(non_empty_lines)


def rendu_regex_motifs(
    tab, combined_text: str, _filtered_connectors: Dict[str, str]
) -> None:
    st.subheader("Regex motifs")

    cleaned_text = _normalize_text_without_blank_lines(combined_text)

    st.markdown(
        """
        Dans cet onglet, les motifs regex repèrent des structures combinées
        (ex : si…alors, si…sinon) dans les segments. La recherche est bornée par la ponctuation
        du texte (. ! ? ; : ou retour ligne) garantissant que les connecteurs sont détectés dans
        une unité lexicale (la phrase).
        """
    )

    regex_rules_path = BASE_DIR / "dictionnaires" / "motifs_progr_regex.json"
    regex_patterns = load_regex_rules(regex_rules_path)

    if not regex_patterns:
        st.info("Aucun motif regex n'a pu être chargé depuis le dictionnaire fourni.")
        return

    regex_label_colors = generate_label_colors([pattern.label for pattern in regex_patterns])
    regex_label_style = build_label_style_block(regex_label_colors)
    regex_annotation_style = build_annotation_style_block(regex_label_style)

    highlighted_corpus = highlight_matches_html(cleaned_text, regex_patterns)

    regex_annotated_doc = f"""<!DOCTYPE html>
    <html lang=\"fr\">
    <head>
    <meta charset=\"utf-8\" />
    {regex_annotation_style}
    </head>
    <body>
    <div class='annotated-container'>{highlighted_corpus}</div>
    </body>
    </html>"""

    st.download_button(
        label="Télécharger le texte annoté (HTML)",
        data=regex_annotated_doc,
        file_name="texte_annote_motifs_regex.html",
        mime="text/html",
        key="download-annotated-regex-html",
    )

    st.markdown(regex_annotation_style, unsafe_allow_html=True)

    segments = split_segments(cleaned_text)

    st.subheader("Corpus annoté (motifs regex)")
    st.markdown(
        f"<div class='annotated-container'>{highlighted_corpus}</div>",
        unsafe_allow_html=True,
    )

    downloadable_regex_html = f"""<!DOCTYPE html>
    <html lang=\"fr\">
    <head>
    <meta charset=\"utf-8\" />
    {regex_annotation_style}
    </head>
    <body>
    <div class='annotated-container'>{highlighted_corpus}</div>
    </body>
    </html>"""

    st.download_button(
        label="Télécharger le corpus annoté (HTML)",
        data=downloadable_regex_html,
        file_name="corpus_regex_annote.html",
        mime="text/html",
        key="download-regex-annotated-html",
    )

    segment_rows = summarize_matches_by_segment(segments, regex_patterns)

    st.markdown("---")
    st.subheader("Segments contenant au moins un motif")

    if not segment_rows:
        st.info("Aucun motif regex détecté dans le corpus fourni.")
        return

    table_rows = []

    for row in segment_rows:
        motif_details = "; ".join(
            f"{motif['label']} ({motif['occurrences']})" for motif in row["motifs"]
        )
        table_rows.append(
            {
                "Segment": row["segment_id"],
                "Texte": row["segment"],
                "Motifs détectés": motif_details,
            }
        )

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

    segment_counts = count_segments_by_pattern(segment_rows)

    if segment_counts:
        st.subheader("Nombre de segments matchés par motif")
        counts_df = pd.DataFrame(
            [
                {"motif": motif, "segments": count}
                for motif, count in segment_counts.items()
            ]
        ).sort_values("segments", ascending=False)

        alt_counts_chart = (
            alt.Chart(counts_df)
            .mark_bar()
            .encode(
                x=alt.X("motif:N", sort="-y", title="Motif"),
                y=alt.Y("segments:Q", title="Segments matchés"),
                tooltip=["motif", "segments"],
            )
            .properties(title="Nombre de segments matchés par motif")
        )

        st.altair_chart(alt_counts_chart, use_container_width=True)
