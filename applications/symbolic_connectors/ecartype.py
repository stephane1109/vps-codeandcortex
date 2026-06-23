"""Calcul de l'écart-type des longueurs de segments entre connecteurs."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from densite import build_text_from_dataframe, filter_dataframe_by_modalities
from hash import SegmentationMode, TokenizationMode, compute_segment_word_lengths


def _mean_and_std(lengths: List[int]) -> Tuple[float, float]:
    if not lengths:
        return 0.0, 0.0

    values = np.array(lengths, dtype=float)
    return float(np.mean(values)), float(np.std(values))


def compute_length_standard_deviation(
    text: str,
    connectors: Dict[str, str],
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> Tuple[float, float]:
    """Retourner (moyenne, écart-type) des longueurs des segments."""

    lengths = compute_segment_word_lengths(
        text, connectors, segmentation_mode, tokenization_mode
    )
    return _mean_and_std(lengths)


def standard_deviation_by_modality(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    modalities: Optional[Iterable[str]] = None,
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> pd.DataFrame:
    """Calculer LMS et écart-type des segments par modalité."""

    if dataframe.empty:
        return pd.DataFrame(columns=["modalite", "segments", "lms", "ecart_type"])

    filtered_df = filter_dataframe_by_modalities(dataframe, variable, modalities)

    if not variable or variable not in filtered_df.columns or filtered_df.empty:
        return pd.DataFrame(columns=["modalite", "segments", "lms", "ecart_type"])

    rows: List[Dict[str, float | int | str]] = []

    for modality, subset in filtered_df.groupby(variable):
        text_value = build_text_from_dataframe(subset)
        lengths = compute_segment_word_lengths(
            text_value, connectors, segmentation_mode, tokenization_mode
        )
        lms_value, std_value = _mean_and_std(lengths)

        rows.append(
            {
                "modalite": modality,
                "segments": len(lengths),
                "lms": lms_value,
                "ecart_type": std_value,
            }
        )

    return pd.DataFrame(rows).sort_values("modalite").reset_index(drop=True)
