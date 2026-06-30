"""Densité des textes analysés : La densité, c'est simplement le nombre de connecteurs
ramené à une base (pour 1 000 mots). C'est ce qui permet de dire par exemple :
"Ce texte est 3 fois plus 'logique' que l'autre".
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

import pandas as pd


def _build_connector_pattern(connectors: Dict[str, str]) -> re.Pattern[str]:
    """Construire un motif regex sécurisé pour tous les connecteurs fournis."""

    cleaned = [key for key in connectors if key]
    sorted_keys = sorted(cleaned, key=len, reverse=True)
    escaped = [re.escape(key) for key in sorted_keys]
    pattern = "|".join(escaped)

    return re.compile(rf"\b({pattern})\b", re.IGNORECASE)


def count_words(text: str) -> int:
    """Compter le nombre de mots dans un texte donné."""

    if not text:
        return 0

    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def compute_total_connectors(text: str, connectors: Dict[str, str]) -> int:
    """Compter toutes les occurrences des connecteurs dans le texte."""

    if not text:
        return 0

    cleaned_connectors = {key: value for key, value in connectors.items() if key}

    if not cleaned_connectors:
        return 0

    pattern = _build_connector_pattern(cleaned_connectors)
    return len(list(pattern.finditer(text)))


def compute_density(text: str, connectors: Dict[str, str], base: int = 1000) -> float:
    """Calculer la densité de connecteurs ramenée à ``base`` mots."""

    word_count = count_words(text)

    if word_count == 0:
        return 0.0

    total_connectors = compute_total_connectors(text, connectors)

    if total_connectors == 0:
        return 0.0

    return (total_connectors / word_count) * float(base)


def compute_density_by_label(text: str, connectors: Dict[str, str], base: int = 1000) -> Dict[str, float]:
    """Calculer la densité ramenée à ``base`` mots pour chaque label présent."""

    word_count = count_words(text)

    if word_count == 0:
        return {}

    per_label: Dict[str, float] = {}

    for label in sorted(set(connectors.values())):
        label_connectors = {
            connector: connector_label
            for connector, connector_label in connectors.items()
            if connector_label == label
        }
        total = compute_total_connectors(text, label_connectors)

        if total:
            per_label[label] = (total / word_count) * float(base)
        else:
            per_label[label] = 0.0

    return per_label


def filter_dataframe_by_modalities(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    modalities: Optional[Iterable[str]],
) -> pd.DataFrame:
    """Restreindre un DataFrame aux modalités sélectionnées pour une variable donnée.

    - Si ``variable`` est vide ou absente du DataFrame, aucune restriction n'est appliquée.
    - Si ``modalities`` est fourni mais vide, seules les lignes non nulles pour la variable
      sont conservées.
    - Si ``modalities`` contient des valeurs, seules ces modalités sont conservées.
    """

    if dataframe.empty:
        return dataframe

    if not variable or variable not in dataframe.columns:
        return dataframe

    selected_modalities = list(modalities or [])

    if not selected_modalities:
        return dataframe[dataframe[variable].notna()]

    return dataframe[dataframe[variable].isin(selected_modalities)]


def build_text_from_dataframe(dataframe: pd.DataFrame) -> str:
    """Concaténer les en-têtes et textes d'un DataFrame en un seul bloc de texte."""

    if dataframe.empty:
        return ""

    combined_parts = []

    for _, row in dataframe.iterrows():
        header = str(row.get("entete", "")).strip()
        body = str(row.get("texte", "")).strip()

        if header and body:
            combined_parts.append(f"{header}\n{body}")
        elif body:
            combined_parts.append(body)
        elif header:
            combined_parts.append(header)

    return "\n\n".join(part for part in combined_parts if part).strip()


def compute_density_per_modality(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    base: int = 1000,
) -> pd.DataFrame:
    """Calculer la densité par modalité pour une variable donnée."""

    if not variable or variable not in dataframe.columns or dataframe.empty:
        return pd.DataFrame(columns=["modalite", "densite", "mots", "connecteurs"])

    rows = []

    for modality, subset in dataframe.groupby(variable):
        text_value = build_text_from_dataframe(subset)
        total_words = count_words(text_value)
        total_connectors = compute_total_connectors(text_value, connectors)
        density = compute_density(text_value, connectors, base=base)

        rows.append(
            {
                "modalite": modality,
                "densite": density,
                "mots": total_words,
                "connecteurs": total_connectors,
            }
        )

    return pd.DataFrame(rows).sort_values("modalite").reset_index(drop=True)


def compute_density_per_modality_by_label(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    base: int = 1000,
) -> pd.DataFrame:
    """Calculer la densité par modalité et par label pour une variable donnée."""

    if not variable or variable not in dataframe.columns or dataframe.empty:
        return pd.DataFrame(columns=["modalite", "label", "densite", "mots", "connecteurs"])

    labels = sorted(set(connectors.values()))
    rows = []

    for modality, subset in dataframe.groupby(variable):
        text_value = build_text_from_dataframe(subset)
        total_words = count_words(text_value)
        label_densities = compute_density_by_label(text_value, connectors, base=base)

        for label in labels:
            label_connectors = {
                connector: connector_label
                for connector, connector_label in connectors.items()
                if connector_label == label
            }
            total_connectors = compute_total_connectors(text_value, label_connectors)

            rows.append(
                {
                    "modalite": modality,
                    "label": label,
                    "densite": label_densities.get(label, 0.0),
                    "mots": total_words,
                    "connecteurs": total_connectors,
                }
            )

    return pd.DataFrame(rows).sort_values(["modalite", "label"]).reset_index(drop=True)
