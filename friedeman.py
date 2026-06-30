"""Calculs pour le test de Friedman appliqué aux indicateurs de hachage.

Ce module construit les tableaux appariés (prompts × modèles) et réalise le
Friedman ainsi que les tests post-hoc de Wilcoxon avec correction éventuelle
des p-values.
"""

from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon
from statsmodels.stats.multitest import multipletests

from densite import build_text_from_dataframe
from hash import compute_segment_word_lengths, resumer_longueurs_segments


def calculer_indicateurs_reponses_appairees(
    dataframe: pd.DataFrame,
    variable_modele: Optional[str],
    variable_bloc: Optional[str],
    connectors: Dict[str, str],
    segmentation_mode: str,
    tokenization_mode: str,
    seuil_segment_court: int = 10,
    modalites_modele: Optional[Iterable[str]] = None,
    modalites_bloc: Optional[Iterable[str]] = None,
) -> Tuple[pd.DataFrame, int]:
    """Calculer les indicateurs pour chaque réponse en gardant modèle et bloc.

    Les réponses vides ou sans segments détectés sont exclues et comptabilisées
    pour informer l'utilisateur.
    """

    if (
        dataframe.empty
        or not variable_modele
        or not variable_bloc
        or variable_modele not in dataframe.columns
        or variable_bloc not in dataframe.columns
    ):
        return pd.DataFrame(), 0

    if modalites_modele is not None:
        dataframe = dataframe[dataframe[variable_modele].isin(modalites_modele)]

    if modalites_bloc is not None:
        dataframe = dataframe[dataframe[variable_bloc].isin(modalites_bloc)]

    if dataframe.empty:
        return pd.DataFrame(), 0

    lignes: List[Dict[str, float | str]] = []
    reponses_ignorees = 0

    for _, row in dataframe.iterrows():
        modele = row.get(variable_modele)
        bloc = row.get(variable_bloc)
        texte = build_text_from_dataframe(pd.DataFrame([row]))

        if pd.isna(modele) or pd.isna(bloc) or not texte:
            reponses_ignorees += 1
            continue

        longueurs = compute_segment_word_lengths(
            texte, connectors, segmentation_mode, tokenization_mode
        )

        resume = resumer_longueurs_segments(longueurs, seuil_segment_court)

        if resume is None:
            reponses_ignorees += 1
            continue

        lignes.append({variable_modele: modele, variable_bloc: bloc, **resume})

    return pd.DataFrame(lignes), reponses_ignorees


def construire_tableau_apparie(
    indicateurs_reponses: pd.DataFrame,
    variable_modele: str,
    variable_bloc: str,
    indicateur: str,
    methode_agregation: str = "moyenne",
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Construire un tableau apparié blocs × modèles pour un indicateur donné."""

    if indicateurs_reponses.empty or indicateur not in indicateurs_reponses.columns:
        return pd.DataFrame(), [], []

    fonction_agregation = np.mean if methode_agregation == "moyenne" else np.median

    tableau = (
        indicateurs_reponses.groupby([variable_bloc, variable_modele])[indicateur]
        .agg(fonction_agregation)
        .unstack(variable_modele)
        .sort_index()
    )

    prompts_initiaux = tableau.index.tolist()
    tableau_complet = tableau.dropna(axis=0, how="any")
    prompts_exclus = sorted(set(prompts_initiaux) - set(tableau_complet.index))

    return tableau_complet, prompts_initiaux, prompts_exclus


def calculer_statistique_friedman(tableau_apparie: pd.DataFrame) -> Optional[Dict[str, float]]:
    """Calculer la statistique de Friedman et Kendall W sur un tableau complet."""

    if tableau_apparie.empty or tableau_apparie.shape[0] < 2 or tableau_apparie.shape[1] < 2:
        return None

    valeurs = [tableau_apparie[colonne].to_numpy() for colonne in tableau_apparie.columns]
    statistique, p_value = friedmanchisquare(*valeurs)

    n_prompts = tableau_apparie.shape[0]
    k_modeles = tableau_apparie.shape[1]
    kendall_w = statistique / (n_prompts * (k_modeles - 1)) if n_prompts > 0 and k_modeles > 1 else np.nan

    return {
        "statistique": float(statistique),
        "p_value": float(p_value),
        "n_prompts": int(n_prompts),
        "k_modeles": int(k_modeles),
        "kendall_w": float(kendall_w),
    }


def tests_post_hoc_wilcoxon(
    tableau_apparie: pd.DataFrame, methode_correction: Optional[str] = None
) -> pd.DataFrame:
    """Comparer les modèles deux à deux avec Wilcoxon signé-rang."""

    if tableau_apparie.empty or tableau_apparie.shape[1] < 2:
        return pd.DataFrame()

    resultats: List[Dict[str, float | str]] = []

    for modele_a, modele_b in itertools.combinations(tableau_apparie.columns, 2):
        valeurs_a = tableau_apparie[modele_a].to_numpy()
        valeurs_b = tableau_apparie[modele_b].to_numpy()

        if len(valeurs_a) == 0 or len(valeurs_b) == 0:
            continue

        try:
            statistique, p_value = wilcoxon(valeurs_a, valeurs_b)
        except ValueError:
            # Wilcoxon peut échouer si toutes les différences sont nulles
            continue

        resultats.append(
            {
                "modele_a": modele_a,
                "modele_b": modele_b,
                "statistique": float(statistique),
                "p_brute": float(p_value),
                "n": int(len(valeurs_a)),
            }
        )

    if not resultats:
        return pd.DataFrame()

    resultats_df = pd.DataFrame(resultats)

    if methode_correction:
        try:
            _, p_ajustees, _, _ = multipletests(resultats_df["p_brute"], method=methode_correction)
            resultats_df["p_ajustee"] = p_ajustees
        except Exception:
            resultats_df["p_ajustee"] = np.nan
    else:
        resultats_df["p_ajustee"] = resultats_df["p_brute"]

    ordre = "p_ajustee" if "p_ajustee" in resultats_df.columns else "p_brute"

    return resultats_df.sort_values(by=ordre).reset_index(drop=True)
