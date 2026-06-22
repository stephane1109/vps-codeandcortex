"""Helpers for manual annotation UI in Streamlit."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import streamlit as st
from st_annotator import text_annotator


def _slice_text(text: str, start: Optional[int], end: Optional[int]) -> Optional[str]:
    if start is None or end is None:
        return None
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end < 0 or start > len(text) or end > len(text) or start >= end:
        return None
    return text[start:end]


def _iter_annotation_items(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        yield value


def _resolve_label(
    mapping_label: Optional[str],
    item_label: Optional[str],
    snippet: Optional[str],
) -> Optional[str]:
    if item_label and snippet and item_label != snippet:
        return item_label
    if mapping_label:
        return mapping_label
    return item_label


def _extract_rows_from_mapping(
    text: str, label: str, items: Any
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in _iter_annotation_items(items):
        item_label = item.get("label") or item.get("tag") or item.get("category")
        start = item.get("start") or item.get("start_offset") or item.get("startOffset")
        end = item.get("end") or item.get("end_offset") or item.get("endOffset")
        snippet = _slice_text(text, start, end)
        if snippet is None:
            snippet = item.get("text") or item.get("token") or item.get("value")
        raw_label = _resolve_label(label, item_label, snippet)
        if snippet is None or raw_label is None:
            continue
        rows.append({"Texte": str(snippet), "Label": str(raw_label)})
    return rows


def _build_annotation_rows(text: str, annotations: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if isinstance(annotations, dict):
        payload = annotations.get("annotations") or annotations.get("labels") or annotations
        if isinstance(payload, dict):
            for label, items in payload.items():
                rows.extend(_extract_rows_from_mapping(text, str(label), items))
        elif isinstance(payload, list):
            for entry in payload:
                rows.extend(_build_annotation_rows(text, entry))
        return rows
    if isinstance(annotations, list):
        for entry in annotations:
            if isinstance(entry, dict) and len(entry) == 1:
                label, items = next(iter(entry.items()))
                rows.extend(_extract_rows_from_mapping(text, str(label), items))
                continue
            if isinstance(entry, dict):
                label = (
                    entry.get("label")
                    or entry.get("tag")
                    or entry.get("category")
                    or entry.get("label_name")
                    or entry.get("name")
                )
                start = entry.get("start") or entry.get("start_offset") or entry.get("startOffset")
                end = entry.get("end") or entry.get("end_offset") or entry.get("endOffset")
                snippet = _slice_text(text, start, end)
                if snippet is None:
                    snippet = entry.get("text") or entry.get("token") or entry.get("value")
                label = _resolve_label(None, label, snippet)
                if snippet is None or label is None:
                    continue
                rows.append({"Texte": str(snippet), "Label": str(label)})
    return rows


def _build_markdown_table(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return ""
    lines = ["| Texte | Label |", "| --- | --- |"]
    for row in rows:
        text_value = row.get("Texte", "").replace("|", "\\|")
        label_value = row.get("Label", "").replace("|", "\\|")
        lines.append(f"| {text_value} | {label_value} |")
    return "\n".join(lines)


def render_manual_annotations() -> None:
    st.title("Annotation d'un texte")

    label_colors = {
        "label_input": "#ff9500",
    }

    uploaded_file = st.file_uploader("Upload a .txt file to annotate", type=["txt"])

    if uploaded_file is not None:
        text = uploaded_file.getvalue().decode("utf-8")

        st.subheader("Annotation du texte")
        st.info("Double-cliquez sur un mot pour l'annoter. Vous pouvez surligner un passage entier. clic droit de la souris pour visualiser l'information")

        with st.container(height=500, border=True):
            results = text_annotator(
                text=text,
                labels={},
                in_snake_case=False,
                colors=label_colors,
                key="annotator_main",
            )

        st.divider()
        st.subheader("Enregistrement des annotations")

        annotations_data: List[Any] = []
        if results:
            if isinstance(results, str):
                try:
                    annotations_data = json.loads(results)
                except json.JSONDecodeError:
                    st.error("Format de données invalide reçu du composant.")
            else:
                annotations_data = results

        if annotations_data:
            annotation_rows = _build_annotation_rows(text, annotations_data)
            st.success(f"{len(annotation_rows)} annotation(s) détectée(s).")

            if annotation_rows:
                annotation_df = pd.DataFrame(annotation_rows)
                with st.expander("Voir le détail des labels"):
                    st.dataframe(annotation_df, use_container_width=True)

                json_mapping = {row["Texte"]: row["Label"] for row in annotation_rows}
                json_string = json.dumps(json_mapping, indent=4, ensure_ascii=False)
                st.download_button(
                    label="Enregistrer le fichier JSON",
                    data=json_string,
                    file_name="annotations.json",
                    mime="application/json",
                    use_container_width=True,
                )

                markdown_content = _build_markdown_table(annotation_rows)
                st.download_button(
                    label="Exporter les labels (Markdown)",
                    data=markdown_content,
                    file_name="annotations.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            else:
                st.warning(
                    "Les annotations reçues ne contiennent pas de labels exploitables."
                )
                with st.expander("Détail brut des annotations"):
                    st.json(annotations_data)
                raw_json = json.dumps(annotations_data, indent=4, ensure_ascii=False)
                st.download_button(
                    label="Enregistrer le fichier JSON (brut)",
                    data=raw_json,
                    file_name="annotations_brutes.json",
                    mime="application/json",
                    use_container_width=True,
                )
        else:
            st.warning(
                "Aucune annotation n'a été faite pour le moment. Double-cliquez sur un mot dans la zone ci-dessus."
            )

    else:
        st.info("Veuillez charger un fichier .txt pour commencer.")
