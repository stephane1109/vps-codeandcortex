"""Graphiques pour l'onglet Densité."""

from __future__ import annotations

from typing import Iterable

import altair as alt
import pandas as pd
from pandas.api.types import is_float_dtype, is_numeric_dtype


def build_density_chart(per_modality_df: pd.DataFrame) -> alt.Chart:
    """Créer le graphique de densité par modalité."""

    return (
        alt.Chart(per_modality_df)
        .mark_bar()
        .encode(
            x=alt.X("modalite:N", title="Modalité"),
            y=alt.Y("densite:Q", title="Densité"),
            color=alt.Color("modalite:N", title="Modalité"),
            tooltip=[
                alt.Tooltip("modalite:N", title="Modalité"),
                alt.Tooltip("densite:Q", title="Densité", format=".4f"),
                alt.Tooltip("mots:Q", title="Mots"),
                alt.Tooltip("connecteurs:Q", title="Connecteurs"),
            ],
        )
        .properties(title="Graphique de densité")
    )


def build_connector_density_chart(per_modality_label_df: pd.DataFrame) -> alt.Chart:
    """Créer le graphique de densité par connecteur et modalité."""

    return (
        alt.Chart(per_modality_label_df)
        .mark_bar()
        .encode(
            x=alt.X("modalite:N", title="Modalité"),
            xOffset="label",
            y=alt.Y("densite:Q", title="Densité"),
            color=alt.Color("label:N", title="Connecteur"),
            tooltip=[
                alt.Tooltip("modalite:N", title="Modalité"),
                alt.Tooltip("label:N", title="Connecteur"),
                alt.Tooltip("densite:Q", title="Densité", format=".4f"),
                alt.Tooltip("connecteurs:Q", title="Connecteurs"),
                alt.Tooltip("mots:Q", title="Mots"),
            ],
        )
        .properties(title="Densité par connecteur et modalité")
    )


def _format_tooltip_fields(df: pd.DataFrame, fields: Iterable[str]) -> list[alt.Tooltip]:
    """Formater les info-bulles pour limiter les décimales des valeurs flottantes."""

    tooltips: list[alt.Tooltip] = []

    for field in fields:
        if field not in df.columns:
            tooltips.append(alt.Tooltip(field))
            continue

        series = df[field]

        if is_float_dtype(series):
            tooltips.append(alt.Tooltip(f"{field}:Q", format=".4f"))
        elif is_numeric_dtype(series):
            tooltips.append(alt.Tooltip(f"{field}:Q"))
        else:
            tooltips.append(alt.Tooltip(f"{field}:N"))

    return tooltips


def build_density_scatter_chart(
    scatter_df: pd.DataFrame,
    selected_x_label: str,
    selected_y_label: str,
    tooltip_fields: Iterable[str] | None = None,
) -> alt.Chart:
    """Créer la classification visuelle des densités sur deux axes."""

    return (
        alt.Chart(scatter_df)
        .mark_circle(opacity=0.7)
        .encode(
            x=alt.X(
                "densite_x:Q",
                title=f"Densité {selected_x_label}",
            ),
            y=alt.Y(
                "densite_y:Q",
                title=f"Densité {selected_y_label}",
            ),
            size=alt.Size(
                "densite_totale:Q",
                title="Densité totale (taille du cercle)",
                scale=alt.Scale(range=[50, 1200]),
            ),
            color=alt.Color(
                "densite_totale:Q",
                title="Densité totale",
                scale=alt.Scale(scheme="oranges"),
            ),
            tooltip=_format_tooltip_fields(
                scatter_df,
                tooltip_fields if tooltip_fields is not None else list(scatter_df.columns),
            ),
        )
        .properties(height=500)
    )
