"""Analyse factorielle des correspondances sur les connecteurs filtrés.

Ce module illustre la logique décrite dans l'application Streamlit :
1. filtrer les segments en fonction des variables issues des marqueurs IRaMuTeQ,
2. reconstruire un tableau de contingence connecteur × document,
3. appliquer une AFC pour obtenir des coordonnées factorielles.

L'implémentation reste volontairement légère pour être importable dans un
notebook ou un script sans dépendre de l'interface Streamlit.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from analyses import count_connectors


def _apply_modality_filters(
    dataframe: pd.DataFrame, modality_filters: Optional[Mapping[str, Iterable[str]]]
) -> pd.DataFrame:
    """Filtrer le DataFrame selon des couples variable/modalités.

    ``modality_filters`` doit suivre la structure ``{"variable": ["mod1", "mod2"]}``.
    Les variables absentes du DataFrame sont ignorées silencieusement.
    """

    if not modality_filters:
        return dataframe

    filtered = dataframe.copy()

    for variable, modalities in modality_filters.items():
        if variable in filtered.columns and modalities:
            filtered = filtered[filtered[variable].isin(modalities)]

    return filtered


def _filter_segments_with_connectors(
    dataframe: pd.DataFrame, connectors: Dict[str, str]
) -> pd.DataFrame:
    """Restreindre le DataFrame aux segments contenant au moins un connecteur.

    L'AFC doit être effectuée sur le sous-corpus défini par les connecteurs
    sélectionnés. Cette fonction applique un filtre simple qui ne conserve que
    les lignes dont le champ ``texte`` comporte au moins un connecteur.
    """

    connector_names = [name.strip() for name in connectors if name.strip()]
    if not connector_names:
        return pd.DataFrame(columns=dataframe.columns)

    pattern = re.compile(
        rf"\b({'|'.join(re.escape(name) for name in sorted(connector_names, key=len, reverse=True))})\b",
        re.IGNORECASE,
    )

    mask = dataframe["texte"].fillna("").apply(lambda text: bool(pattern.search(text)))
    return dataframe.loc[mask]


def build_connector_matrix(
    dataframe: pd.DataFrame,
    connectors: Dict[str, str],
    modality_filters: Optional[Mapping[str, Iterable[str]]] = None,
) -> pd.DataFrame:
    """Construire une matrice documents × connecteurs après filtrage.

    Chaque ligne correspond à un segment filtré, identifié par son index d'origine.
    Les colonnes représentent les connecteurs sélectionnés, les valeurs le nombre
    d'occurrences dans le segment.
    """

    filtered_df = _apply_modality_filters(dataframe, modality_filters)
    filtered_df = _filter_segments_with_connectors(filtered_df, connectors)
    if filtered_df.empty:
        return pd.DataFrame()

    connector_names = sorted({name for name in connectors if name})
    if not connector_names:
        return pd.DataFrame()

    rows = []
    index_labels = []

    for row_index, text in filtered_df["texte"].fillna("").items():
        counts = count_connectors(text, connectors).set_index("connecteur")[
            "occurrences"
        ]
        rows.append([int(counts.get(name, 0)) for name in connector_names])
        index_labels.append(row_index)

    matrix = pd.DataFrame(rows, columns=connector_names, index=index_labels)

    # Retirer les colonnes et lignes entièrement nulles pour éviter des divisions par
    # zéro lors du calcul de l'AFC.
    matrix = matrix.loc[:, matrix.sum() > 0]
    matrix = matrix.loc[matrix.sum(axis=1) > 0]

    return matrix


def run_afc(
    dataframe: pd.DataFrame,
    connectors: Dict[str, str],
    modality_filters: Optional[Mapping[str, Iterable[str]]] = None,
    n_components: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Appliquer une AFC en traitant les connecteurs comme variables supplémentaires.

    L'analyse factorielle est réalisée sur les catégories (labels) associées aux
    connecteurs. Les connecteurs individuels sont ensuite projetés comme
    variables supplémentaires pour ne pas influencer le calcul des axes.

    Parameters
    ----------
    dataframe:
        Table contenant au minimum une colonne ``texte`` et les variables
        issues des marqueurs IRaMuTeQ.
    connectors:
        Dictionnaire ``connecteur -> label`` tel que fourni par l'application.
    modality_filters:
        Filtres sur les variables/modalités avant de recalculer la matrice.
    n_components:
        Nombre d'axes factoriels à conserver.
    """

    connector_matrix = build_connector_matrix(dataframe, connectors, modality_filters)
    if connector_matrix.empty:
        return pd.DataFrame(), pd.DataFrame()

    connector_to_label = {name: label for name, label in connectors.items() if label}

    # Construire une matrice agrégée par label pour définir les axes factoriels.
    label_columns = sorted(set(connector_to_label.values()))
    label_matrix = pd.DataFrame(0, index=connector_matrix.index, columns=label_columns)

    for connector, label in connector_to_label.items():
        if connector in connector_matrix.columns:
            label_matrix[label] += connector_matrix[connector]

    label_matrix = label_matrix.loc[:, label_matrix.sum() > 0]

    if label_matrix.empty:
        return pd.DataFrame(), pd.DataFrame()

    total = label_matrix.to_numpy().sum()
    if total == 0:
        return pd.DataFrame(), pd.DataFrame()

    relative = label_matrix / total
    row_masses = relative.sum(axis=1).to_numpy()
    col_masses = relative.sum(axis=0).to_numpy()

    expected = np.outer(row_masses, col_masses)
    with np.errstate(divide="ignore", invalid="ignore"):
        standardized = (relative.to_numpy() - expected) / np.sqrt(expected)
        standardized = np.nan_to_num(standardized, nan=0.0, posinf=0.0, neginf=0.0)

    try:
        U, singular_values, Vt = np.linalg.svd(standardized, full_matrices=False)
    except np.linalg.LinAlgError:
        return pd.DataFrame(), pd.DataFrame()

    max_components = min(n_components, len(singular_values))
    row_coords = (U[:, :max_components] * singular_values[:max_components]) / np.sqrt(
        row_masses[:, None]
    )
    supplementary_coords = []
    supplementary_index = []

    for connector in connector_matrix.columns:
        counts = connector_matrix[connector].to_numpy(dtype=float)
        column_total = counts.sum()

        if column_total == 0:
            continue

        connector_mass = column_total / total
        connector_profile = counts / total

        standardized_column = (connector_profile - row_masses * connector_mass) / np.sqrt(
            row_masses * connector_mass
        )
        projected = (standardized_column @ U[:, :max_components]) / np.sqrt(connector_mass)

        supplementary_coords.append(projected)
        supplementary_index.append(connector)

    row_df = pd.DataFrame(row_coords, index=label_matrix.index)
    connector_df = pd.DataFrame(supplementary_coords, index=supplementary_index)

    return row_df, connector_df


__all__ = [
    "build_connector_matrix",
    "run_afc",
]
