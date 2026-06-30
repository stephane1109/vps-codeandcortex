"""Outils pour le test ANOVA et les comparaisons post-hoc."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import f_oneway, ttest_ind
from statsmodels.stats.multitest import multipletests

from densite import compute_density, compute_total_connectors, count_words


@dataclass
class ResultatAnova:
    """Résultat structuré pour un test ANOVA à un facteur."""

    statistique: float
    p_value: float
    ddl_inter: int
    ddl_intra: int
    effectif_total: int
    nb_groupes: int


def build_text_from_row(row: pd.Series) -> str:
    """Construire un texte à partir d'une ligne unique du DataFrame."""

    header = str(row.get("entete", "")).strip()
    body = str(row.get("texte", "")).strip()

    if header and body:
        return f"{header}\n{body}"

    return body or header


def compute_density_per_response(
    dataframe: pd.DataFrame,
    connectors: Dict[str, str],
    base: int = 1000,
) -> pd.DataFrame:
    """Calculer la densité par réponse individuelle."""

    if dataframe.empty:
        return pd.DataFrame(columns=["densite", "mots", "connecteurs"])

    rows = []

    for _, row in dataframe.iterrows():
        text_value = build_text_from_row(row)
        total_words = count_words(text_value)
        total_connectors = compute_total_connectors(text_value, connectors)
        density = compute_density(text_value, connectors, base=base)
        rows.append(
            {
                **row.to_dict(),
                "densite": density,
                "mots": total_words,
                "connecteurs": total_connectors,
            }
        )

    return pd.DataFrame(rows)


def effectuer_test_anova(donnees_par_modalite: Dict[str, List[float]]) -> Optional[ResultatAnova]:
    """Appliquer un test ANOVA à un facteur sur plusieurs modalités."""

    modalites = sorted(donnees_par_modalite)
    valeurs = []

    for modalite in modalites:
        echantillon = [
            v for v in donnees_par_modalite[modalite] if v is not None and not np.isnan(v)
        ]
        if echantillon:
            valeurs.append(echantillon)

    if len(valeurs) < 2:
        return None

    resultat = f_oneway(*valeurs)
    effectif_total = sum(len(donnees_par_modalite[m]) for m in modalites)
    nb_groupes = len(valeurs)
    ddl_inter = nb_groupes - 1
    ddl_intra = effectif_total - nb_groupes

    return ResultatAnova(
        statistique=float(resultat.statistic),
        p_value=float(resultat.pvalue),
        ddl_inter=int(ddl_inter),
        ddl_intra=int(ddl_intra),
        effectif_total=int(effectif_total),
        nb_groupes=int(nb_groupes),
    )


def tests_post_hoc_ttest(
    donnees_par_modalite: Dict[str, List[float]],
    methode_correction: Optional[str] = None,
    equal_var: bool = False,
) -> pd.DataFrame:
    """Comparer les modalités deux à deux avec un test t."""

    modalites = sorted(donnees_par_modalite)
    resultats: List[Dict[str, float | str | int]] = []

    for modalite_a, modalite_b in itertools.combinations(modalites, 2):
        valeurs_a = [
            v
            for v in donnees_par_modalite[modalite_a]
            if v is not None and not np.isnan(v)
        ]
        valeurs_b = [
            v
            for v in donnees_par_modalite[modalite_b]
            if v is not None and not np.isnan(v)
        ]

        if len(valeurs_a) < 2 or len(valeurs_b) < 2:
            continue

        resultat = ttest_ind(valeurs_a, valeurs_b, equal_var=equal_var)
        resultats.append(
            {
                "modalite_a": modalite_a,
                "modalite_b": modalite_b,
                "statistique": float(resultat.statistic),
                "p_brute": float(resultat.pvalue),
                "n_a": int(len(valeurs_a)),
                "n_b": int(len(valeurs_b)),
            }
        )

    if not resultats:
        return pd.DataFrame()

    resultats_df = pd.DataFrame(resultats)

    if methode_correction:
        try:
            _, p_ajustees, _, _ = multipletests(
                resultats_df["p_brute"], method=methode_correction
            )
            resultats_df["p_ajustee"] = p_ajustees
        except Exception:
            resultats_df["p_ajustee"] = np.nan
    else:
        resultats_df["p_ajustee"] = resultats_df["p_brute"]

    ordre = "p_ajustee" if "p_ajustee" in resultats_df.columns else "p_brute"

    return resultats_df.sort_values(by=ordre).reset_index(drop=True)
