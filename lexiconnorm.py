"""Composants Streamlit pour l'onglet "OpenLexicon"."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import altair as alt
import pandas as pd
import streamlit as st

from densite import (
    compute_density_per_modality_by_label,
    compute_total_connectors,
    count_words,
    filter_dataframe_by_modalities,
)


def load_norms_from_lexicon(
    lexicon_path: Path, connectors: Dict[str, str]
) -> pd.DataFrame:
    """Charger les normes disponibles à partir du dictionnaire OpenLexicon."""

    if not lexicon_path.exists():
        return pd.DataFrame(columns=["label", "densite", "occurrences"])

    try:
        raw_df = pd.read_json(lexicon_path)
        lexicon_entries = raw_df.get("entries", pd.Series(dtype=object)).dropna().tolist()
        lexicon_df = pd.DataFrame(lexicon_entries)
    except (ValueError, TypeError):
        return pd.DataFrame(columns=["label", "densite", "occurrences"])

    if lexicon_df.empty or "ortho" not in lexicon_df.columns:
        return pd.DataFrame(columns=["label", "densite", "occurrences"])

    connector_tokens = {connector.lower() for connector in connectors}
    lexicon_df["ortho_lower"] = lexicon_df["ortho"].str.lower()
    lexicon_df = lexicon_df[lexicon_df["ortho_lower"].isin(connector_tokens)]

    norm_columns = [
        column
        for column in lexicon_df.columns
        if column not in {"ortho", "Lexique3__cgram", "ortho_lower"}
    ]

    rows: List[Dict[str, float | str]] = []

    for column in norm_columns:
        numeric_values = pd.to_numeric(lexicon_df[column], errors="coerce").dropna()

        if numeric_values.empty:
            continue

        rows.append(
            {
                "label": column,
                "densite": float(numeric_values.mean()),
                "occurrences": float(numeric_values.sum()),
            }
        )

    return pd.DataFrame(rows).sort_values("label").reset_index(drop=True)


def _select_variable_modalities(
    dataframe: pd.DataFrame, variable_choice: str
) -> Iterable[str]:
    """Retourner les modalités disponibles pour la variable choisie."""

    if variable_choice == "(Aucune)" or variable_choice not in dataframe.columns:
        return []

    return sorted(dataframe[variable_choice].dropna().unique().tolist())


def render_lexicon_norm_tab(
    dataframe: pd.DataFrame, filtered_connectors: Dict[str, str]
) -> None:
    """Afficher l'onglet « OpenLexicon » avec les normes sélectionnées."""

    st.subheader("OpenLexicon")

    if dataframe.empty:
        st.info("Aucune donnée disponible après filtrage.")
        return

    allowed_labels = {"CONDITION", "ALORS", "ALTERNATIVE", "AND"}
    normalized_connectors = {
        connector: label
        for connector, label in filtered_connectors.items()
        if label in allowed_labels
    }

    if not normalized_connectors:
        st.info(
            "Sélectionnez au moins un connecteur de type condition, alors, alternative ou addition pour afficher la densité."
        )
        return

    variables = [column for column in dataframe.columns if column not in ("texte", "entete")]
    default_index = 0 if not variables else 1
    variable_choice = st.selectbox(
        "Variable à filtrer",
        ["(Aucune)"] + variables,
        index=default_index,
        help="Choisissez la variable utilisée pour séparer les modalités.",
    )

    modality_options = _select_variable_modalities(dataframe, variable_choice)
    selected_modalities = st.multiselect(
        "Modalités incluses",
        modality_options,
        default=modality_options,
        help="Affiner le calcul des densités par modalité.",
    )

    base = 1000
    st.markdown(
        "Les densités affichées sont systématiquement normalisées sur 1 000 mots afin de "
        "pouvoir comparer les corpus entre eux, quelle que soit leur longueur."
    )

    density_filtered_df = filter_dataframe_by_modalities(
        dataframe,
        None if variable_choice == "(Aucune)" else variable_choice,
        selected_modalities or None,
    )

    per_modality_label_df = compute_density_per_modality_by_label(
        density_filtered_df,
        None if variable_choice == "(Aucune)" else variable_choice,
        normalized_connectors,
        base=int(base),
    )

    st.markdown("### Normes disponibles")
    st.caption(
        "Les normes affichées proviennent d'OpenLexicon : http://www.lexique.org/django/openlexicon/."
    )

    norm_density_df = load_norms_from_lexicon(
        Path(__file__).parent / "dictionnaires" / "lexicon.json", normalized_connectors
    )

    if norm_density_df.empty:
        st.info("Aucune norme disponible pour les connecteurs sélectionnés.")
    else:
        # Les fréquences Lexique sont exprimées pour un million de mots ;
        # on les ramène à une base de 1 000 mots pour aligner le graphique.
        norm_density_df["densite"] = norm_density_df["densite"] / 1000.0

        unchecked_labels = {"WorldLex_FR__BlogFreq"}
        selected_labels = []
        for _, row in norm_density_df.iterrows():
            checkbox_label = row["label"]
            if st.checkbox(
                checkbox_label,
                value=checkbox_label not in unchecked_labels,
                key=f"lexicon-norm-{row['label']}",
            ):
                selected_labels.append(row)

        norm_density_df = pd.DataFrame(selected_labels)

    st.markdown("### Densité par connecteur et modalités")

    if per_modality_label_df.empty:
        st.info("Aucune donnée de densité disponible pour les paramètres sélectionnés.")
        return

    per_modality_label_df["label"] = per_modality_label_df["label"].str.lower()

    bar_chart = (
        alt.Chart(per_modality_label_df)
        .mark_bar()
        .encode(
            x=alt.X("modalite:N", title="Modalité"),
            xOffset="label",
            y=alt.Y("densite:Q", title=f"Densité pour {int(base)} mots"),
            color=alt.Color("label:N", title="Connecteur"),
            tooltip=[
                alt.Tooltip("modalite:N", title="Modalité"),
                alt.Tooltip("label:N", title="Connecteur"),
                alt.Tooltip("densite:Q", title="Densité", format=".4f"),
                alt.Tooltip("mots:Q", title="Mots"),
                alt.Tooltip("connecteurs:Q", title="Connecteurs"),
            ],
        )
    )

    layers: List[alt.Chart] = [bar_chart]

    if not norm_density_df.empty:
        rule_layer = (
            alt.Chart(norm_density_df)
            .mark_rule(color="#dc2626", strokeDash=[6, 3])
            .encode(
                y=alt.Y("densite:Q", title=None),
                tooltip=[
                    alt.Tooltip("label:N", title="Connecteur"),
                    alt.Tooltip("densite:Q", title="Densité", format=".4f"),
                    alt.Tooltip("occurrences:Q", title="Occurrences"),
                ],
            )
        )

        text_layer = (
            alt.Chart(norm_density_df)
            .mark_text(align="left", baseline="bottom", dx=6, dy=-2, color="#dc2626", fontWeight="bold")
            .encode(y="densite:Q", text="label")
        )

        layers.extend([rule_layer, text_layer])

    density_chart = alt.layer(*layers)
    st.altair_chart(density_chart, use_container_width=True)

    try:
        buffer = BytesIO()
        density_chart.save(buffer, format="png")
        buffer.seek(0)

        st.download_button(
            label="Télécharger le graphique",
            data=buffer,
            file_name="graph_lexicon.png",
            mime="image/png",
        )
    except Exception:  # noqa: BLE001 - fallback handled via Streamlit message
        st.info("Le graphique ne peut pas être exporté pour le moment.")
