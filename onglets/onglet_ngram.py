"""# Onglet N-gram

Ce module fournit l'onglet Streamlit pour explorer les n-grams d'un corpus,
en filtrant par variables et en appliquant éventuellement des motifs regex.

## Dépendances
- `ngram.py` : génération des statistiques d'occurrences pour les n-grams.
- `fcts_utils.py` : création des blocs de style pour l'annotation HTML.
- Bibliothèques `streamlit`, `pandas` et `altair` pour l'affichage, la
  sélection des modalités et les graphiques.
"""
from __future__ import annotations

from html import escape
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from fcts_utils import build_annotation_style_block
from ngram import build_ngram_pattern, compute_ngram_statistics


def rendu_ngram(tab, filtered_df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    st.subheader("N-gram")

    st.markdown(
        """
        <style>
        .ngram-context-title {
            font-size: 1.4rem;
            font-weight: 800;
            color: #dc2626;
            margin: 16px 0 8px 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    ngram_variables = [column for column in filtered_df.columns if column not in ("texte", "entete")]
    selected_ngram_variables = st.multiselect(
        "Variables à filtrer pour les N-grams",
        ngram_variables,
        default=ngram_variables,
        help="Choisissez les variables à utiliser pour filtrer les N-grams.",
    )

    ngram_filtered_df = filtered_df.copy()

    for variable in selected_ngram_variables:
        modality_options = sorted(ngram_filtered_df[variable].dropna().unique().tolist())
        selected_modalities = st.multiselect(
            f"Modalités à inclure pour {variable}",
            modality_options,
            default=modality_options,
            help="Modalités retenues pour calculer les N-grams.",
        )

        if selected_modalities:
            ngram_filtered_df = ngram_filtered_df[
                ngram_filtered_df[variable].isin(selected_modalities)
            ]
        else:
            ngram_filtered_df = ngram_filtered_df.iloc[0:0]

    if ngram_filtered_df.empty:
        st.info("Aucun texte ne correspond aux filtres sélectionnés pour les N-grams.")
        return

    ngram_stats = compute_ngram_statistics(
        ngram_filtered_df,
        min_n=3,
        max_n=6,
    )

    results_by_size = {
        size: ngram_stats[ngram_stats["Taille"] == size].reset_index(drop=True)
        for size in range(3, 7)
    }

    def _highlight_context(context_text: str, ngram_value: str) -> str:
        pattern = build_ngram_pattern(ngram_value.split())
        return pattern.sub(
            lambda match: (
                "<span class=\"connector-annotation\">"
                f"<span class=\"connector-text\">{match.group(0)}</span>"
                "</span>"
            ),
            escape(context_text),
        )

    def _normalize_header_value(header_value: str) -> str:
        header_value = header_value.strip()

        if not header_value:
            return ""

        tokens = header_value.split()

        if tokens and tokens[0] == "****":
            trimmed_tokens: list[str] = []

            for token in tokens:
                trimmed_tokens.append(token)

                if token.startswith("*prompt_"):
                    break

            header_value = " ".join(trimmed_tokens)

        return header_value

    def _clean_context_text(context_text: str, header: str) -> str:
        if not context_text:
            return ""

        cleaned = context_text
        normalized_header = _normalize_header_value(header)

        if normalized_header:
            separator_candidates = [" – ", " - ", " — ", " : "]

            for separator in separator_candidates:
                prefix = f"{normalized_header}{separator}"
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix) :]
                    break
            else:
                if cleaned.startswith(normalized_header):
                    cleaned = cleaned[len(normalized_header) :].lstrip(" –—-:")

        return cleaned.strip()

    def _format_context_block(context_entry: dict, ngram_value: str) -> str:
        raw_context = str(context_entry.get("contexte", "")).strip()
        raw_header_value = str(context_entry.get("entete", "") or "")
        header_value = _normalize_header_value(raw_header_value)

        context_text = _clean_context_text(raw_context, header_value)
        if not context_text:
            return ""

        highlighted = _highlight_context(context_text, ngram_value)
        header_parts: list[str] = []

        if header_value:
            header_parts.append(header_value)

        modalities = context_entry.get("modalites", []) or []
        if modalities:
            header_parts.append(
                ", ".join(str(modality) for modality in modalities)
            )

        header_text = " • ".join(header_parts) or "Texte"

        return "\n".join(
            [
                "<div class=\"context-block\">",
                f"<div class=\"context-header\">{header_text}</div>",
                f"<div class=\"context-body\">{highlighted}</div>",
                "</div>",
            ]
        )

    def build_ngram_download_html(results: dict[int, pd.DataFrame]) -> str:
        annotation_style = build_annotation_style_block("")

        sections: list[str] = [
            "<!DOCTYPE html>",
            "<html lang=\"fr\">",
            "<head>",
            "<meta charset=\"utf-8\" />",
            annotation_style,
            "<style>",
            "body { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; padding: 24px; background: #f8fafc; color: #111827; }",
            "h1, h2 { color: #0f172a; }",
            ".ngram-section { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); }",
            ".ngram-entry { margin: 12px 0; padding: 12px 14px; border-radius: 10px; background: #f9fafb; border: 1px solid #e5e7eb; }",
            ".ngram-title { font-size: 17px; font-weight: 700; color: #0ea5e9; margin-bottom: 6px; }",
            ".ngram-frequency { color: #475569; font-size: 14px; margin-bottom: 8px; }",
            ".context-block { background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px; padding: 10px 12px; margin: 10px 0; }",
            ".context-header { font-weight: 700; color: #312e81; margin-bottom: 6px; }",
            ".context-body { line-height: 1.6; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Occurrences des N-grams</h1>",
        ]

        for size in range(3, 7):
            ngram_df = results.get(size)
            if ngram_df is None or ngram_df.empty:
                continue

            sections.append(
                f"<div class=\"ngram-section\"><h2>N-grams de {size} mots</h2>"
            )

            for _, row in ngram_df.iterrows():
                ngram_value = row.get("N-gram", "")
                frequency_value = row.get("Fréquence", 0)

                sections.append(
                    "\n".join(
                        [
                            "<div class=\"ngram-entry\">",
                            f"<div class=\"ngram-title\">{ngram_value}</div>",
                            f"<div class=\"ngram-frequency\">{frequency_value} occurrence(s)</div>",
                        ]
                    )
                )

                detailed_contexts = row.get("Occurrences détaillées") or []

                if not detailed_contexts and "Contexte" in row:
                    context_text = row.get("Contexte", "")
                    if context_text:
                        detailed_contexts = [
                            {
                                "contexte": context_text,
                                "modalites": [],
                                "entete": "",
                                "texte_complet": context_text,
                            }
                        ]

                if not detailed_contexts:
                    sections.append("<p>Aucun contexte disponible.</p></div>")
                    continue

                for context_entry in detailed_contexts:
                    block_html = _format_context_block(context_entry, ngram_value)
                    if block_html:
                        sections.append(block_html)

                sections.append("</div>")

            sections.append("</div>")

        sections.extend(["</body>", "</html>"])
        return "\n".join(sections)

    downloadable_ngram_html = build_ngram_download_html(results_by_size)
    st.download_button(
        label="Tout télécharger",
        data=downloadable_ngram_html,
        file_name="ngrams.html",
        mime="text/html",
        help="Télécharger tous les N-grams au format HTML.",
    )

    for size in range(3, 7):
        st.markdown(f"### N-grams de {size} mots")
        ngram_results = results_by_size[size]

        if ngram_results.empty:
            st.info(
                "Aucun N-gram n'a été trouvé pour cette taille avec les filtres actuels."
            )
            continue

        display_df = ngram_results.copy()
        display_df = display_df.fillna("")

        st.dataframe(display_df.drop(columns=["Occurrences détaillées"], errors="ignore"), use_container_width=True)

        for _, row in display_df.iterrows():
            detailed_contexts = row.get("Occurrences détaillées")
            ngram_value = row.get("N-gram", "")

            if not detailed_contexts:
                continue

            ngram_title = escape(str(ngram_value))
            st.markdown(
                f"<div class=\"ngram-context-title\">Contexte pour : {ngram_title}</div>",
                unsafe_allow_html=True,
            )
            for context_entry in detailed_contexts:
                context_html = _format_context_block(context_entry, ngram_value)
                if context_html:
                    st.markdown(context_html, unsafe_allow_html=True)
