"""# Onglet ANOVA

Analyse statistique des densités de connecteurs par réponse (ANOVA + t-tests).
"""
from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from anova import (
    compute_density_per_response,
    effectuer_test_anova,
    tests_post_hoc_ttest,
)
from fcts_utils import render_connectors_reminder


def rendu_anova(tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    """Rendre l'onglet ANOVA pour comparer les densités par modalité."""

    render_connectors_reminder(filtered_connectors)
    st.write(
        "Cette section propose une ANOVA à un facteur sur la densité de connecteurs "
        "calculée par réponse individuelle, suivie de tests t post-hoc."
    )
    st.caption(
        "Hypothèses : indépendance des observations, normalité approximative et "
        "homogénéité des variances (ou Welch si variances inégales)."
    )

    if not filtered_connectors:
        st.info("Sélectionnez au moins un connecteur pour lancer l'ANOVA.")
        return

    variables = [column for column in df.columns if column not in ("texte", "entete")]
    if not variables:
        st.info("Aucune variable n'a été trouvée dans le fichier importé.")
        return

    anova_variable = st.selectbox(
        "Variable à comparer",
        variables,
        help="Choisissez la variable (ex. modèle/LLM) à comparer via ANOVA.",
    )

    if not anova_variable or anova_variable not in df.columns:
        st.info("Sélectionnez une variable valide pour lancer l'ANOVA.")
        return

    base = 1000
    densities_by_response = compute_density_per_response(
        df,
        filtered_connectors,
        base=base,
    )
    densities_by_response = densities_by_response[densities_by_response["mots"] > 0]

    if densities_by_response.empty:
        st.info("Aucune réponse exploitable pour calculer l'ANOVA.")
        return

    donnees_par_modalite = {
        modalite: subset["densite"].dropna().tolist()
        for modalite, subset in densities_by_response.groupby(anova_variable)
    }

    resultat_anova = effectuer_test_anova(donnees_par_modalite)

    if resultat_anova is None:
        st.info("Test ANOVA impossible : il faut au moins deux modalités avec des données.")
        return

    st.success(
        "ANOVA à un facteur : "
        f"F({resultat_anova.ddl_inter}, {resultat_anova.ddl_intra}) = "
        f"{resultat_anova.statistique:.4f}, p = {resultat_anova.p_value:.4g} "
        f"(n = {resultat_anova.effectif_total}, groupes = {resultat_anova.nb_groupes})."
    )

    st.markdown("### Tests t post-hoc (comparaisons par paires)")
    correction_labels = {
        "Aucune": None,
        "Bonferroni": "bonferroni",
        "Holm": "holm",
    }
    correction_choice = st.selectbox(
        "Correction des p-values",
        list(correction_labels.keys()),
        index=1,
        help="Appliquez une correction pour limiter l'inflation des erreurs de type I.",
    )
    equal_var = st.checkbox(
        "Supposer des variances égales",
        value=False,
        help="Décochez pour appliquer la version de Welch (recommandée si les variances diffèrent).",
    )

    resultat_ttest = tests_post_hoc_ttest(
        donnees_par_modalite,
        methode_correction=correction_labels[correction_choice],
        equal_var=equal_var,
    )

    if resultat_ttest.empty:
        st.info("Aucune comparaison t-test disponible avec les données actuelles.")
        return

    resultat_ttest_display = resultat_ttest.copy()
    resultat_ttest_display["p_brute"] = resultat_ttest_display["p_brute"].map(
        lambda value: f"{value:.4g}"
    )
    resultat_ttest_display["p_ajustee"] = resultat_ttest_display["p_ajustee"].map(
        lambda value: f"{value:.4g}"
    )

    st.dataframe(
        resultat_ttest_display.rename(
            columns={
                "modalite_a": "Modalité A",
                "modalite_b": "Modalité B",
                "statistique": "t",
                "p_brute": "p brute",
                "p_ajustee": "p ajustée",
                "n_a": "n A",
                "n_b": "n B",
            }
        ),
        use_container_width=True,
    )
