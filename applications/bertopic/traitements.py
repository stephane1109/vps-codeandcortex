"""Mise en correspondance des thèmes BERTopic et des unités IRaMuTeQ."""
from __future__ import annotations

import numpy as np
import pandas as pd


def nom_theme(identifiant: int) -> str:
    """Fournir des modalités compatibles avec les variables étoilées."""
    return "hors_theme" if identifiant == -1 else f"theme_{identifiant:02d}"


def enrichir_documents(
    tableau: pd.DataFrame,
    indices: np.ndarray,
    affectations: list[int],
    confiances: list[float] | np.ndarray,
    matrice_probabilites: np.ndarray | None = None,
    themes_probabilites: list[int] | None = None,
) -> pd.DataFrame:
    """Réinjecter les affectations sans supprimer les documents non analysés."""
    indices = np.asarray(indices, dtype=int)
    affectations = [int(numero) for numero in affectations]
    confiances = np.asarray(confiances, dtype=float)
    if len(indices) != len(affectations) or len(indices) != len(confiances):
        raise ValueError("Nombre d'indices, d'affectations et de confiances incohérent.")
    if len(set(indices.tolist())) != len(indices):
        raise ValueError("Indices documentaires dupliqués.")
    if np.any(indices < 0) or np.any(indices >= len(tableau)):
        raise ValueError("Indice documentaire hors limites.")

    resultat = tableau.copy()
    resultat["theme_dominant"] = "non_analyse"
    resultat["identifiant_theme"] = pd.Series([pd.NA] * len(resultat), index=resultat.index, dtype="Int64")
    resultat["statut_analyse"] = "non_analyse"
    resultat["probabilite_theme"] = np.nan

    colonnes = resultat.index.to_numpy()[indices]
    resultat.loc[colonnes, "theme_dominant"] = [nom_theme(t) for t in affectations]
    resultat.loc[colonnes, "identifiant_theme"] = pd.array(affectations, dtype="Int64")
    resultat.loc[colonnes, "statut_analyse"] = [
        "hors_theme" if numero == -1 else "attribue" for numero in affectations
    ]
    valeurs = [np.nan if identifiant == -1 else float(probabilite)
               for identifiant, probabilite in zip(affectations, confiances)]
    resultat.loc[colonnes, "probabilite_theme"] = valeurs

    if matrice_probabilites is not None:
        matrice = np.asarray(matrice_probabilites, dtype=float)
        identifiants = list(themes_probabilites or [])
        if matrice.ndim != 2 or matrice.shape != (len(indices), len(identifiants)):
            raise ValueError("La matrice de probabilités ne correspond pas aux thèmes.")
        for position, numero in enumerate(identifiants):
            colonne = "probabilite_" + nom_theme(int(numero))
            resultat[colonne] = np.nan
            resultat.loc[colonnes, colonne] = matrice[:, position]
    return resultat


def construire_croisement(
    resultat: pd.DataFrame, variable: str, inclure_hors_theme: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculer les effectifs et pourcentages selon une variable étoilée."""
    if variable not in resultat.columns:
        raise ValueError("Variable absente : " + variable)
    masque = resultat["statut_analyse"].isin(["attribue", "hors_theme"])
    if not inclure_hors_theme:
        masque &= resultat["statut_analyse"].eq("attribue")
    sous_ensemble = resultat.loc[masque, [variable, "theme_dominant"]].copy()
    if sous_ensemble.empty:
        return pd.DataFrame(), pd.DataFrame()
    sous_ensemble[variable] = sous_ensemble[variable].fillna("(absent)").astype(str)
    effectifs = pd.crosstab(sous_ensemble[variable], sous_ensemble["theme_dominant"])
    pourcentages = effectifs.div(effectifs.sum(axis=1), axis=0).mul(100).fillna(0)
    return effectifs, pourcentages.round(2)
