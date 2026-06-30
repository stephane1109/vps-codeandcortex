"""# Onglet Test du chi2

Interface Streamlit pour construire un tableau de contingence à partir des
variables/modalités du corpus et des connecteurs sélectionnés, puis exécuter un
test du chi2 avec options complémentaires (résidus, export CSV)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from chi2 import (
    ResultatChiDeux,
    calculer_statistiques_chi2,
    construire_table_contingence_categories,
    construire_table_contingence_connecteurs,
    fusionner_tables_export,
)
from connecteurs import get_selected_labels
from fcts_utils import render_connectors_reminder


def _afficher_residus_heatmap(residus: pd.DataFrame) -> None:
    """Afficher une heatmap simple des résidus standardisés."""

    if residus.empty:
        st.info("Aucun résidu à afficher.")
        return

    colonnes = [str(col) for col in residus.columns]
    modalites = [str(modalite) for modalite in residus.index]

    residus_long = (
        residus.fillna(0)
        .reset_index()
        .rename(columns={residus.index.name or "index": "Modalité"})
        .melt(id_vars="Modalité", var_name="Colonne", value_name="Résidu")
    )

    vmax = float(residus_long["Résidu"].abs().max()) if not residus_long.empty else 1.0

    cell_size = 28
    heatmap = (
        alt.Chart(residus_long)
        .mark_rect()
        .encode(
            x=alt.X(
                "Colonne:N",
                sort=colonnes,
                title="Colonnes",
                axis=alt.Axis(labelAngle=-45),
                scale=alt.Scale(paddingInner=0, paddingOuter=0),
            ),
            y=alt.Y(
                "Modalité:N",
                sort=modalites,
                title="Modalités",
                scale=alt.Scale(paddingInner=0, paddingOuter=0),
            ),
            color=alt.Color(
                "Résidu:Q",
                scale=alt.Scale(scheme="redblue", domain=[-vmax, vmax], domainMid=0),
                legend=alt.Legend(title="Résidu"),
            ),
            tooltip=[
                alt.Tooltip("Modalité:N"),
                alt.Tooltip("Colonne:N"),
                alt.Tooltip("Résidu:Q", format=".2f"),
            ],
        )
        .properties(
            title="Sur et sous-représentations (écarts à l’attendu)",
            width=alt.Step(cell_size),
            height=alt.Step(cell_size),
        )
    )

    st.altair_chart(heatmap, use_container_width=False)


def _afficher_resultats(affichage: ResultatChiDeux) -> None:
    """Afficher les résultats du test du chi2 dans l'interface."""

    st.markdown("---")
    st.subheader("Résultats du test")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Chi2", f"{affichage.chi2:.3f}")
    col2.metric("Degrés de liberté", affichage.ddl)
    col3.metric("p-value", f"{affichage.p_value:.4f}")
    col4.metric("V de Cramér", f"{affichage.cramers_v:.3f}")

    st.caption("Le V de Cramér mesure l'intensité de l'association entre les lignes et les colonnes du tableau.")

    st.subheader("Tableau attendu")
    st.dataframe(affichage.tableau_attendu, use_container_width=True)

    st.subheader("Sur et sous-représentations (écarts à l’attendu)")
    st.caption(
        "Interprétation : signe positif si la cellule est plus fréquente qu'attendu, signe négatif si elle est moins fréquente. "
        "Plus la valeur absolue est grande, plus la contribution à la dépendance globale est forte (des valeurs |résidu| ≳ 2 sont souvent considérées comme remarquables). "
        "Le tableau permet d'identifier quelles associations modalité × colonne expliquent le chi² global."
    )
    st.dataframe(affichage.residus_standardises, use_container_width=True)
    _afficher_residus_heatmap(affichage.residus_standardises)

    st.subheader("Contributions au chi2")
    st.caption(
        "Chaque cellule contribue à la statistique via (observé - attendu)^2 / attendu. Les lignes suivantes synthétisent ces apports."
    )
    st.dataframe(affichage.contributions, use_container_width=True)

    st.subheader("Contribution par modalité")
    st.caption(
        "Ce que contient le tableau :\n"
        "La colonne Contribution est la somme, pour chaque modalité (ligne du tableau de contingence), des contributions individuelles des cellules (observé − attendu)^2 / attendu.\n"
        "La colonne Part (%) exprime la part de cette contribution dans la statistique de chi² totale : Contribution de la modalité / χ² × 100"
    )
    st.dataframe(affichage.contributions_modalites, use_container_width=True)


def _afficher_conclusion(resultats: ResultatChiDeux) -> None:
    """Proposer une phrase de conclusion en fonction de la p-value."""

    if resultats.p_value < 0.001:
        interpretation = "Association très significative entre lignes et colonnes."
    elif resultats.p_value < 0.01:
        interpretation = "Association significative entre lignes et colonnes."
    elif resultats.p_value < 0.05:
        interpretation = "Association modérément significative entre lignes et colonnes."
    else:
        interpretation = "Aucune association statistiquement significative détectée."

    st.info(
        f"Statistique chi2 = {resultats.chi2:.3f} avec {resultats.ddl} ddl, p-value = {resultats.p_value:.4f}. {interpretation}"
    )


def _signaler_attendus_faibles(attendus: pd.DataFrame) -> None:
    """Afficher un avertissement en cas d'attendus faibles."""

    if attendus.empty:
        return

    if (attendus < 5).any().any():
        st.warning(
            "Certaines cases du tableau attendu sont inférieures à 5. Les résultats du chi2 peuvent être fragiles."
        )


def rendu_chi2(tab, dataframe: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    """Afficher l'onglet de test du chi2."""

    st.subheader("Test du chi2")
    render_connectors_reminder(filtered_connectors)

    if dataframe.empty:
        st.info("Aucun texte filtré disponible. Sélectionnez des données dans l'onglet « Données brutes ».")
        return

    variables_disponibles: List[str] = [
        colonne for colonne in dataframe.columns if colonne not in ("texte", "entete")
    ]

    if not variables_disponibles:
        st.info("Aucune variable IRaMuTeQ n'est disponible pour construire un tableau de contingence.")
        return

    variable = st.selectbox("Variable pour les lignes", variables_disponibles)

    if not variable:
        st.info("Choisissez une variable pour lancer le test du chi2.")
        return

    modalities_options = sorted(dataframe[variable].dropna().unique().tolist())
    selected_modalities = st.multiselect(
        "Modalités à inclure", modalities_options, default=modalities_options
    )

    mode = st.radio(
        "Type de colonnes",
        options=["Catégories de connecteurs", "Connecteurs vs non-connecteurs"],
        help="Choisissez entre l'analyse par catégories ou un regroupement global connecteurs/non-connecteurs.",
    )

    table_observee: pd.DataFrame
    categories_selectionnees: List[str] = []
    connecteurs_selectionnes: List[str] = []

    if mode == "Catégories de connecteurs":
        categories_disponibles = get_selected_labels(filtered_connectors.values())
        if not categories_disponibles:
            st.info("Aucune catégorie disponible : sélectionnez des connecteurs dans l'onglet dédié.")
            return

        categories_selectionnees = st.multiselect(
            "Catégories à inclure",
            categories_disponibles,
            default=categories_disponibles,
            help="Les colonnes du tableau correspondent aux catégories choisies.",
        )
    else:
        connecteurs_options = [
            f"{connector} ({label})" for connector, label in filtered_connectors.items()
        ]
        option_map = {f"{connector} ({label})": connector for connector, label in filtered_connectors.items()}

        connecteurs_selectionnes_affiche = st.multiselect(
            "Connecteurs inclus",
            connecteurs_options,
            default=[],
            help="Sélectionnez les connecteurs comptabilisés dans la colonne « Connecteurs ».",
        )
        connecteurs_selectionnes = [option_map[label] for label in connecteurs_selectionnes_affiche]

    lancer_calcul = st.button("Calculer le test du chi2")

    if not lancer_calcul:
        st.info("Configurez les options puis lancez le calcul.")
        return

    try:
        if mode == "Catégories de connecteurs":
            table_observee = construire_table_contingence_categories(
                dataframe,
                variable,
                selected_modalities,
                filtered_connectors,
                categories_selectionnees,
            )
        else:
            if not connecteurs_selectionnes:
                st.error("Sélectionnez au moins un connecteur à inclure.")
                return
            table_observee = construire_table_contingence_connecteurs(
                dataframe,
                variable,
                selected_modalities,
                filtered_connectors,
                connecteurs_selectionnes,
            )
    except ValueError as err:
        st.error(str(err))
        return

    if table_observee.empty:
        st.info("Le tableau de contingence est vide après application des filtres.")
        return

    st.subheader("Tableau observé")
    st.dataframe(table_observee, use_container_width=True)

    try:
        resultats = calculer_statistiques_chi2(table_observee)
    except ValueError as err:
        st.error(str(err))
        return

    _afficher_resultats(resultats)
    _afficher_conclusion(resultats)
    _signaler_attendus_faibles(resultats.tableau_attendu)

    st.markdown("---")
    st.caption(
        "Interprétation : des résidus standardisés positifs indiquent une sur-représentation relative, "
        "des résidus négatifs une sous-représentation. Le V de Cramér mesure la force de l'association "
        "(0 = aucune association, 1 = association parfaite)."
    )

    export_df = fusionner_tables_export(
        table_observee,
        resultats.tableau_attendu,
        resultats.residus_standardises,
        resultats.contributions,
        resultats.contributions_modalites,
        (resultats.chi2, resultats.ddl, resultats.p_value, resultats.cramers_v),
    )

    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom_fichier = f"chi2_{variable}_{horodatage}.csv"

    st.download_button(
        label="Exporter les résultats (CSV)",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=nom_fichier,
        mime="text/csv",
    )
