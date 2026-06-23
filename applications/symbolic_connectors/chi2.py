"""### Outils de calcul pour le test du chi2

Ce module regroupe les fonctions nécessaires à la construction de tableaux de
contingence basés sur les variables/modalités du corpus et les connecteurs
logiques, ainsi que les calculs associés au test du chi2 (valeur du test,
attendus, résidus standardisés, taille d'effet). Les fonctions privilégient la
robustesse : contrôles d'entrée, gestion des cas vides et interfaces
conviviales pour l'onglet Streamlit dédié."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from analyses import count_connectors_by_label
from densite import build_text_from_dataframe, compute_total_connectors, count_words


@dataclass
class ResultatChiDeux:
    """Structure contenant les résultats principaux du test du chi2."""

    chi2: float
    ddl: int
    p_value: float
    tableau_attendu: pd.DataFrame
    residus_standardises: pd.DataFrame
    cramers_v: float
    contributions: pd.DataFrame
    contributions_modalites: pd.DataFrame


def _filtrer_connecteurs_par_categories(
    connectors: Dict[str, str], categories: Iterable[str]
) -> Dict[str, str]:
    """Restreindre les connecteurs aux catégories sélectionnées."""

    categories_set = {categorie for categorie in categories if categorie}
    return {
        connector: label
        for connector, label in connectors.items()
        if label in categories_set
    }


def construire_table_contingence_categories(
    dataframe: pd.DataFrame,
    variable: str,
    modalities: Sequence[str],
    connectors: Dict[str, str],
    categories: Sequence[str],
) -> pd.DataFrame:
    """Construire la table (modalités x catégories de connecteurs)."""

    if dataframe.empty:
        raise ValueError("Le corpus filtré est vide : aucun calcul possible.")

    if variable not in dataframe.columns:
        raise ValueError("La variable choisie n'existe pas dans le corpus filtré.")

    if not categories:
        raise ValueError("Aucune catégorie de connecteurs sélectionnée.")

    filtres_categories = _filtrer_connecteurs_par_categories(connectors, categories)

    if not filtres_categories:
        raise ValueError("Les catégories sélectionnées ne correspondent à aucun connecteur actif.")

    lignes: List[Dict[str, int | str]] = []
    dataframe_variable = dataframe.dropna(subset=[variable])
    selected_modalities = list(modalities)

    if not selected_modalities:
        selected_modalities = sorted(dataframe_variable[variable].unique().tolist())

    for modalite in selected_modalities:
        sous_ensemble = dataframe_variable[dataframe_variable[variable] == modalite]
        texte_modalite = build_text_from_dataframe(sous_ensemble)
        compte_labels = count_connectors_by_label(texte_modalite, filtres_categories)

        ligne: Dict[str, int | str] = {"Modalité": modalite}
        for categorie in categories:
            ligne[categorie] = int(compte_labels.get(categorie, 0))

        lignes.append(ligne)

    tableau = pd.DataFrame(lignes)
    tableau = tableau.set_index("Modalité") if "Modalité" in tableau.columns else tableau
    return tableau


def construire_table_contingence_connecteurs(
    dataframe: pd.DataFrame,
    variable: str,
    modalities: Sequence[str],
    connectors: Dict[str, str],
    connectors_selection: Sequence[str],
) -> pd.DataFrame:
    """Construire la table (modalités x [connecteurs, non-connecteurs])."""

    if dataframe.empty:
        raise ValueError("Le corpus filtré est vide : aucun calcul possible.")

    if variable not in dataframe.columns:
        raise ValueError("La variable choisie n'existe pas dans le corpus filtré.")

    connectors_selectionnes = {
        connector: label
        for connector, label in connectors.items()
        if not connectors_selection or connector in connectors_selection
    }

    dataframe_variable = dataframe.dropna(subset=[variable])
    selected_modalities = list(modalities)

    if not selected_modalities:
        selected_modalities = sorted(dataframe_variable[variable].unique().tolist())

    lignes: List[Dict[str, int | str]] = []

    for modalite in selected_modalities:
        sous_ensemble = dataframe_variable[dataframe_variable[variable] == modalite]
        texte_modalite = build_text_from_dataframe(sous_ensemble)
        total_mots = count_words(texte_modalite)
        total_connecteurs = compute_total_connectors(texte_modalite, connectors_selectionnes)
        total_connecteurs = max(total_connecteurs, 0)

        if total_mots < total_connecteurs:
            total_connecteurs = total_mots

        total_non_connecteurs = max(total_mots - total_connecteurs, 0)

        lignes.append(
            {
                "Modalité": modalite,
                "Connecteurs": int(total_connecteurs),
                "Non-connecteurs": int(total_non_connecteurs),
            }
        )

    tableau = pd.DataFrame(lignes)
    tableau = tableau.set_index("Modalité") if "Modalité" in tableau.columns else tableau
    return tableau


def calculer_statistiques_chi2(tableau: pd.DataFrame) -> ResultatChiDeux:
    """Calculer le test du chi2 et les statistiques associées."""

    if tableau.empty:
        raise ValueError("Le tableau de contingence est vide : aucun calcul possible.")

    if tableau.shape[0] < 2 or tableau.shape[1] < 2:
        raise ValueError("Le tableau doit contenir au moins deux lignes et deux colonnes.")

    if not np.all(np.isfinite(tableau.to_numpy())):
        raise ValueError("Le tableau contient des valeurs non numériques ou infinies.")

    tableau_numpy = tableau.to_numpy(dtype=float)

    if np.any(tableau_numpy < 0):
        raise ValueError("Le tableau contient des effectifs négatifs.")

    total = tableau_numpy.sum()
    if total == 0:
        raise ValueError("Le tableau de contingence ne contient aucun effectif.")

    chi2, p_value, ddl, attendus = chi2_contingency(tableau_numpy)

    tableau_attendu = pd.DataFrame(attendus, index=tableau.index, columns=tableau.columns)
    residus = (tableau_numpy - attendus) / np.sqrt(attendus)
    residus_df = pd.DataFrame(residus, index=tableau.index, columns=tableau.columns)

    contributions_numpy = ((tableau_numpy - attendus) ** 2) / attendus
    contributions_df = pd.DataFrame(
        contributions_numpy, index=tableau.index, columns=tableau.columns
    )
    contributions_modalites_df = pd.DataFrame(
        {
            "Contribution": contributions_df.sum(axis=1),
        }
    )
    contributions_modalites_df["Part (%)"] = (
        contributions_modalites_df["Contribution"] / chi2 * 100
        if chi2 > 0
        else 0
    )

    min_dim = min(tableau_numpy.shape[0] - 1, tableau_numpy.shape[1] - 1)
    cramers_v = float(np.sqrt(chi2 / (total * min_dim))) if min_dim > 0 else 0.0

    return ResultatChiDeux(
        chi2=float(chi2),
        ddl=int(ddl),
        p_value=float(p_value),
        tableau_attendu=tableau_attendu,
        residus_standardises=residus_df,
        cramers_v=cramers_v,
        contributions=contributions_df,
        contributions_modalites=contributions_modalites_df,
    )


def fusionner_tables_export(
    tableau_observe: pd.DataFrame,
    tableau_attendu: pd.DataFrame,
    residus: pd.DataFrame,
    contributions: pd.DataFrame,
    contributions_modalites: pd.DataFrame,
    resume: Tuple[float, int, float, float],
) -> pd.DataFrame:
    """Assembler les données à exporter dans un seul DataFrame long."""

    chi2, ddl, p_value, cramers_v = resume
    sections = []

    for nom, table in [
        ("Observé", tableau_observe),
        ("Attendu", tableau_attendu),
        ("Sur et sous-représentations (écarts à l’attendu)", residus),
        ("Contributions (cellules)", contributions),
        ("Contributions par modalité", contributions_modalites),
    ]:
        table_reset = table.reset_index().rename(columns={table.index.name or "index": "Modalité"})
        table_long = table_reset.melt(id_vars=["Modalité"], var_name="Colonne", value_name="Valeur")
        table_long.insert(0, "Section", nom)
        sections.append(table_long)

    resume_df = pd.DataFrame(
        [
            {"Section": "Résumé", "Modalité": "", "Colonne": "chi2", "Valeur": chi2},
            {"Section": "Résumé", "Modalité": "", "Colonne": "ddl", "Valeur": ddl},
            {"Section": "Résumé", "Modalité": "", "Colonne": "p_value", "Valeur": p_value},
            {"Section": "Résumé", "Modalité": "", "Colonne": "V de Cramér", "Valeur": cramers_v},
        ]
    )

    return pd.concat([*sections, resume_df], ignore_index=True)
