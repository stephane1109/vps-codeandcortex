"""Fonctions utilitaires pour le test de Kolmogorov–Smirnov à deux échantillons.

Toutes les fonctions sont écrites en français avec des commentaires explicites
pour faciliter la maintenance dans l'application Streamlit (onglet « Hash »).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from statsmodels.stats.multitest import multipletests

from densite import build_text_from_dataframe, filter_dataframe_by_modalities
from hash import (
    SegmentationMode,
    TokenizationMode,
    compute_segment_word_lengths,
)


@dataclass
class ResultatKSTest:
    """Structure de résultat pour un test KS à deux échantillons."""

    D: float
    p_value: float
    n_a: int
    n_b: int
    ecart_max: Optional[Dict[str, float]]
    ecdf_a: pd.DataFrame
    ecdf_b: pd.DataFrame
    p_value_permutation: Optional[float] = None


ECDF_COLUMNS = ["longueur", "proportion_cumulee"]


def extraire_longueurs_par_modalite(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    modalities: Optional[Iterable[str]] = None,
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> Dict[str, List[int]]:
    """Retourner la liste des longueurs de segments pour chaque modalité."""

    if dataframe.empty or not variable or variable not in dataframe.columns:
        return {}

    filtered_df = filter_dataframe_by_modalities(dataframe, variable, modalities)

    if filtered_df.empty:
        return {}

    longueurs: Dict[str, List[int]] = {}

    for modalite, sous_df in filtered_df.groupby(variable):
        texte = build_text_from_dataframe(sous_df)
        longueurs_modalite = compute_segment_word_lengths(
            texte, connectors, segmentation_mode, tokenization_mode
        )
        if longueurs_modalite:
            longueurs[modalite] = longueurs_modalite

    return longueurs


def _construire_ecdf(longueurs: List[int]) -> pd.DataFrame:
    """Construire l'ECDF (fonction de répartition empirique) d'une liste."""

    if not longueurs:
        return pd.DataFrame(columns=ECDF_COLUMNS)

    valeurs, comptes = np.unique(longueurs, return_counts=True)
    cumule = np.cumsum(comptes) / float(len(longueurs))

    return pd.DataFrame({"longueur": valeurs, "proportion_cumulee": cumule})


def _calculer_ecart_maximal(
    longueurs_a: List[int], longueurs_b: List[int]
) -> Optional[Dict[str, float]]:
    """Identifier le point où l'écart entre ECDF est maximal."""

    if not longueurs_a or not longueurs_b:
        return None

    ecdf_a = _construire_ecdf(longueurs_a)
    ecdf_b = _construire_ecdf(longueurs_b)

    valeurs = sorted(set(ecdf_a["longueur"].tolist() + ecdf_b["longueur"].tolist()))

    ecdf_a_dict = dict(zip(ecdf_a["longueur"], ecdf_a["proportion_cumulee"]))
    ecdf_b_dict = dict(zip(ecdf_b["longueur"], ecdf_b["proportion_cumulee"]))

    proportion_a = 0.0
    proportion_b = 0.0
    ecart_max = {"longueur": 0.0, "proportion_a": 0.0, "proportion_b": 0.0, "ecart": 0.0}

    for valeur in valeurs:
        proportion_a = ecdf_a_dict.get(valeur, proportion_a)
        proportion_b = ecdf_b_dict.get(valeur, proportion_b)
        ecart = abs(proportion_a - proportion_b)

        if ecart > ecart_max["ecart"]:
            ecart_max = {
                "longueur": float(valeur),
                "proportion_a": float(proportion_a),
                "proportion_b": float(proportion_b),
                "ecart": float(ecart),
            }

    return ecart_max


def calculer_test_ks(
    longueurs_a: List[int], longueurs_b: List[int]
) -> Optional[ResultatKSTest]:
    """Calculer le test KS pour deux listes de longueurs."""

    if not longueurs_a or not longueurs_b:
        return None

    resultat = ks_2samp(longueurs_a, longueurs_b, alternative="two-sided", mode="auto")

    ecart_max = _calculer_ecart_maximal(longueurs_a, longueurs_b)

    return ResultatKSTest(
        D=float(resultat.statistic),
        p_value=float(resultat.pvalue),
        n_a=len(longueurs_a),
        n_b=len(longueurs_b),
        ecart_max=ecart_max,
        ecdf_a=_construire_ecdf(longueurs_a),
        ecdf_b=_construire_ecdf(longueurs_b),
    )


def p_value_par_permutation(
    longueurs_a: List[int],
    longueurs_b: List[int],
    n_permutations: int = 2000,
    progress_callback: Optional[Callable[[float], None]] = None,
    random_state: Optional[int] = None,
) -> Optional[float]:
    """Estimer une p-value empirique par permutations."""

    if not longueurs_a or not longueurs_b or n_permutations <= 0:
        return None

    n_a = len(longueurs_a)
    n_total = n_a + len(longueurs_b)

    if n_total < 2:
        return None

    donnees = np.array(longueurs_a + longueurs_b)
    rng = np.random.default_rng(random_state)

    D_observe = ks_2samp(longueurs_a, longueurs_b, alternative="two-sided", mode="auto").statistic

    compteur = 0
    for idx in range(n_permutations):
        indices = rng.permutation(n_total)
        groupe_a = donnees[indices[:n_a]]
        groupe_b = donnees[indices[n_a:]]
        D_perm = ks_2samp(groupe_a, groupe_b, alternative="two-sided", mode="auto").statistic

        if D_perm >= D_observe:
            compteur += 1

        if progress_callback:
            progress_callback((idx + 1) / n_permutations)

    return compteur / n_permutations


def comparer_modalites_par_paires(
    longueurs_par_modalite: Dict[str, List[int]],
    methode_correction: Optional[str] = None,
) -> pd.DataFrame:
    """Comparer toutes les modalités deux à deux avec KS et corrections multiples."""

    modalites = sorted(longueurs_par_modalite)
    if len(modalites) < 2:
        return pd.DataFrame(
            columns=["modalite_a", "modalite_b", "D", "p_brute", "p_ajustee", "n_a", "n_b"]
        )

    lignes = []
    p_values = []

    for modalite_a, modalite_b in combinations(modalites, 2):
        longueurs_a = longueurs_par_modalite.get(modalite_a, [])
        longueurs_b = longueurs_par_modalite.get(modalite_b, [])

        if not longueurs_a or not longueurs_b:
            continue

        res = ks_2samp(longueurs_a, longueurs_b, alternative="two-sided", mode="auto")
        lignes.append(
            {
                "modalite_a": modalite_a,
                "modalite_b": modalite_b,
                "D": float(res.statistic),
                "p_brute": float(res.pvalue),
                "n_a": len(longueurs_a),
                "n_b": len(longueurs_b),
            }
        )
        p_values.append(float(res.pvalue))

    if not lignes:
        return pd.DataFrame(
            columns=["modalite_a", "modalite_b", "D", "p_brute", "p_ajustee", "n_a", "n_b"]
        )

    resultats_df = pd.DataFrame(lignes)

    if methode_correction:
        rejected, p_corrigees, _, _ = multipletests(p_values, method=methode_correction)
        resultats_df["p_ajustee"] = p_corrigees
        resultats_df["rejette"] = rejected
    else:
        resultats_df["p_ajustee"] = resultats_df["p_brute"]
        resultats_df["rejette"] = False

    if methode_correction:
        resultats_df = resultats_df.sort_values("p_ajustee")
    else:
        resultats_df = resultats_df.sort_values("p_brute")

    return resultats_df.reset_index(drop=True)
