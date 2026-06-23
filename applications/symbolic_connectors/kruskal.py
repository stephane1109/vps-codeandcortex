"""Outils pour le test de Kruskal–Wallis."""
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy.stats import kruskal


@dataclass
class ResultatKruskal:
    """Résultat structuré pour un test de Kruskal–Wallis."""

    statistique: float
    p_value: float
    effectif_total: int


def effectuer_test_kruskal(donnees_par_modalite: Dict[str, List[float]]) -> Optional[ResultatKruskal]:
    """Appliquer un test de Kruskal–Wallis sur plusieurs modalités."""

    modalites = sorted(donnees_par_modalite)
    valeurs = []

    for modalite in modalites:
        echantillon = [v for v in donnees_par_modalite[modalite] if v is not None and not np.isnan(v)]
        if echantillon:
            valeurs.append(echantillon)

    if len(valeurs) < 2:
        return None

    resultat = kruskal(*valeurs)

    effectif_total = sum(len(donnees_par_modalite[m]) for m in modalites)

    return ResultatKruskal(
        statistique=float(resultat.statistic),
        p_value=float(resultat.pvalue),
        effectif_total=effectif_total,
    )
