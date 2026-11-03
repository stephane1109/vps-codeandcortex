"""Interface Streamlit de description des métriques d'engagement du corpus."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from statistiques_descriptives import (
    CHAMPS_CLASSES,
    CHAMPS_DATES,
    CHAMPS_GROUPES,
    comparer_groupes,
    preparer_echantillon_descriptif,
    preparer_mesures_engagement,
    produire_evolution,
    produire_histogramme,
    repartir_modalites,
    resumer_engagement,
)


def exporter_csv(tableau: pd.DataFrame) -> bytes:
    """Exporter les tableaux au format français, sans index artificiel."""
    return tableau.to_csv(
        index=False, sep=";", decimal=",", na_rep="", lineterminator="\n"
    ).encode("utf-8-sig")


def formatter_nombre(valeur: float | int | None, decimales: int = 0) -> str:
    """Présenter un indicateur sans en masquer la nature approximative."""
    if valeur is None or pd.isna(valeur):
        return "—"
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


def construire_onglet_statistique_descriptive(donnees: pd.DataFrame) -> None:
    """Construire les graphiques et exports descriptifs avant toute AFC/ACM."""
    st.subheader("Statistique descriptive")
    st.caption(
        "Une observation correspond à une ligne du fichier importé. "
        "Ces statistiques sont descriptives et ne constituent pas des tests "
        "d'hypothèse. Les filtres appliqués ici n'altèrent ni le CSV source "
        "ni les paramètres des analyses factorielles."
    )

    colonne_filtres, colonne_categories = st.columns(2)
    with colonne_filtres:
        uniquement_retenues = st.checkbox(
            "Conserver uniquement les publications retenues",
            value="retenue" in donnees.columns,
            disabled="retenue" not in donnees.columns,
            key="desc_retenues",
        )
        dedoublonner = st.checkbox(
            "Dédoublonner par publication_id",
            value=False,
            disabled="publication_id" not in donnees.columns,
            key="desc_dedoublonnage",
        )
    with colonne_categories:
        variables_filtrables = [
            nom for nom in (*CHAMPS_GROUPES, *CHAMPS_CLASSES)
            if nom in donnees and 1 < donnees[nom].nunique() <= 100
        ]
        variable_filtre = st.selectbox(
            "Filtrer sur une catégorie (facultatif)",
            options=["(Aucun)"] + variables_filtrables,
            key="desc_variable_filtre",
        )
        modalites_filtre = None
        if variable_filtre != "(Aucun)":
            modalites_possibles = sorted(
                donnees[variable_filtre].fillna("").astype(str).unique().tolist()
            )
            modalites_filtre = st.multiselect(
                "Modalités à conserver",
                options=modalites_possibles,
                default=modalites_possibles,
                key=f"desc_modalites_{variable_filtre}",
            )
    try:
        echantillon = preparer_echantillon_descriptif(
            donnees,
            uniquement_retenues=uniquement_retenues,
            dedoublonner=dedoublonner,
            variable_filtre=None if variable_filtre == "(Aucun)" else variable_filtre,
            modalites_filtre=modalites_filtre,
        )
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    mesures, origines = preparer_mesures_engagement(echantillon)
    st.caption(
        f"Échantillon importé : {formatter_nombre(len(donnees))} lignes ; "
        f"échantillon descriptif après filtres : "
        f"{formatter_nombre(len(echantillon))} publications."
    )
    if mesures.empty:
        st.warning(
            "Aucune mesure d'engagement reconnue dans ce fichier. "
            "Colonnes attendues notamment : vues, likes, commentaires, "
            "partages, favoris, taux_engagement, follower_count."
        )
        return

    bilan = resumer_engagement(mesures, len(echantillon))
    onglet_synthese, onglet_distributions, onglet_comparaisons, onglet_exports = st.tabs(
        ["Vue d'ensemble", "Distributions", "Comparaisons et évolution", "Données et exports"]
    )
    with onglet_synthese:
        def lire_statistique(nom: str, champ: str) -> float | None:
            lignes = bilan.loc[bilan["Indicateur"].eq(nom)]
            if lignes.empty:
                return None
            return float(lignes.iloc[0][champ])

        indicateurs = st.columns(4)
        indicateurs[0].metric("Publications", formatter_nombre(len(echantillon)))
        indicateurs[1].metric(
            "Vues totales",
            formatter_nombre(lire_statistique("Vues", "Somme")),
        )
        indicateurs[2].metric(
            "Likes totaux",
            formatter_nombre(lire_statistique("Likes", "Somme")),
        )
        taux_median = lire_statistique("Taux d'engagement (%)", "Médiane")
        indicateurs[3].metric(
            "Taux d'engagement médian",
            f"{formatter_nombre(taux_median, 2)} %"
            if "Taux d'engagement (%)" in mesures else "—",
        )
        st.subheader("Statistiques des principales métriques")
        st.dataframe(
            bilan.round(3), hide_index=True, use_container_width=True,
        )
        interactions = [
            nom for nom in ("Likes", "Commentaires", "Partages", "Favoris")
            if nom in mesures
        ]
        if interactions:
            st.subheader("Volume cumulé des interactions")
            totaux = bilan.set_index("Indicateur").loc[interactions, "Somme"]
            st.bar_chart(
                totaux.rename_axis("Interaction").reset_index(name="Total"),
                x="Interaction", y="Total",
            )
        st.subheader("Proportion de données absentes par indicateur")
        st.bar_chart(
            bilan[["Indicateur", "Absents (%)"]],
            x="Indicateur", y="Absents (%)",
        )
        st.caption(
            "Les effectifs valides varient selon les variables. Les moyennes "
            "peuvent être fortement influencées par quelques publications "
            "à engagement très élevé ; lire également médiane, quartiles "
            "et percentiles. L'engagement par vue peut dépasser 100 %."
        )

    with onglet_distributions:
        st.subheader("Distributions des variables numériques")
        choix_defaut = [
            nom for nom in (
                "Vues", "Likes", "Commentaires", "Partages", "Favoris",
                "Taux d'engagement (%)",
            ) if nom in mesures
        ]
        variables_affichees = st.multiselect(
            "Choisir les mesures à représenter",
            options=list(mesures.columns),
            default=choix_defaut or list(mesures.columns),
            key="desc_variables_distributions",
        )
        col_echelle, col_classes = st.columns(2)
        with col_echelle:
            logarithmique = st.checkbox(
                "Échelle logarithmique log(1 + x)",
                value=True,
                key="desc_echelle_log",
                help=(
                    "La transformation s'applique uniquement aux classes "
                    "de l'histogramme, pas aux statistiques ni aux exports."
                ),
            )
        with col_classes:
            nombre_classes = st.slider(
                "Nombre de classes d'histogramme",
                min_value=5, max_value=60, value=25, step=5,
                key="desc_nombre_classes",
            )
        for indice in range(0, len(variables_affichees), 2):
            colonnes = st.columns(2)
            for position, nom in enumerate(variables_affichees[indice:indice + 2]):
                with colonnes[position]:
                    st.markdown(f"**{nom}**")
                    histogramme = produire_histogramme(
                        mesures[nom], nombre_classes, logarithmique
                    )
                    if histogramme.empty:
                        st.info("Aucune observation numérique valide.")
                    else:
                        st.bar_chart(
                            histogramme, x="Classe", y="Publications",
                        )
                        st.caption(
                            f"N valide : {mesures[nom].notna().sum()} ; "
                            + ("bornes retransformées dans l'unité d'origine."
                               if logarithmique else "échelle d'origine.")
                        )
        variables_qualitatives = [
            nom for nom in CHAMPS_CLASSES if nom in echantillon
        ]
        if variables_qualitatives:
            st.subheader("Répartition des classes d'engagement")
            classe = st.selectbox(
                "Variable catégorielle",
                options=variables_qualitatives,
                key="desc_classe_repartition",
            )
            repartition = repartir_modalites(echantillon, classe)
            st.bar_chart(
                repartition, x="Modalité", y="Effectif",
            )
            st.dataframe(
                repartition, use_container_width=True, hide_index=True,
            )
        st.caption(
            "L'affichage logarithmique facilite la lecture des distributions "
            "asymétriques, mais les valeurs nulles restent conservées grâce "
            "à la transformation log(1 + x)."
        )

    with onglet_comparaisons:
        st.subheader("Comparaison descriptive entre catégories")
        groupes = [
            nom for nom in CHAMPS_GROUPES
            if nom in echantillon and 1 < echantillon[nom].nunique() <= 200
        ]
        indicateurs_valides = [
            nom for nom in mesures if mesures[nom].notna().any()
        ]
        if groupes and indicateurs_valides:
            col_groupe, col_mesure, col_seuil = st.columns([2, 2, 1])
            with col_groupe:
                variable_groupe = st.selectbox(
                    "Variable de regroupement",
                    groupes, key="desc_groupe_comparaison",
                )
            with col_mesure:
                indicateur = st.selectbox(
                    "Mesure étudiée",
                    indicateurs_valides,
                    index=(
                        indicateurs_valides.index("Taux d'engagement (%)")
                        if "Taux d'engagement (%)" in indicateurs_valides else 0
                    ),
                    key="desc_mesure_comparaison",
                )
            with col_seuil:
                seuil = st.number_input(
                    "N minimal par groupe", min_value=1,
                    max_value=max(1, len(echantillon)),
                    value=1, key="desc_seuil_groupes",
                )
            tableau_groupes = comparer_groupes(
                echantillon, mesures, variable_groupe, indicateur,
                minimum_observations=int(seuil),
            )
            if tableau_groupes.empty:
                st.info("Aucun groupe avec des mesures valides à ce seuil.")
            else:
                st.bar_chart(tableau_groupes, x="Groupe", y="Médiane")
                st.dataframe(
                    tableau_groupes.round(3), hide_index=True,
                    use_container_width=True,
                )
        else:
            st.info(
                "Aucune variable de groupe exploitable pour une comparaison."
            )

        if "Vues" in mesures:
            mesures_interactions = [
                nom for nom in ("Likes", "Commentaires", "Partages", "Favoris")
                if nom in mesures
            ]
            if mesures_interactions:
                st.subheader("Relation entre les vues et les interactions")
                indicateur_y = st.selectbox(
                    "Interaction en ordonnée",
                    mesures_interactions,
                    key="desc_interaction_nuage",
                )
                nuage = mesures[["Vues", indicateur_y]].dropna()
                nuage = nuage.loc[
                    nuage["Vues"].ge(0) & nuage[indicateur_y].ge(0)
                ]
                if len(nuage) > 5000:
                    nuage = nuage.sample(n=5000, random_state=42)
                    st.caption(
                        "Nuage limité à 5 000 publications tirées "
                        "aléatoirement avec une graine fixe. "
                        "Les statistiques portent sur tout l'échantillon."
                    )
                if not nuage.empty:
                    nuage = np.log1p(nuage)
                    nuage.columns = ["log(1 + vues)", f"log(1 + {indicateur_y.lower()})"]
                    st.scatter_chart(
                        nuage,
                        x="log(1 + vues)",
                        y=f"log(1 + {indicateur_y.lower()})",
                    )
                    st.caption(
                        "Nuage descriptif en log(1 + x) sur les deux axes ; "
                        "aucune association causale ou significativité n'est déduite."
                    )

        champs_dates = [nom for nom in CHAMPS_DATES if nom in echantillon]
        if champs_dates and indicateurs_valides:
            st.subheader("Évolution temporelle")
            colonne_date, colonne_variable = st.columns(2)
            with colonne_date:
                choix_date = st.selectbox(
                    "Champ temporel", champs_dates,
                    key="desc_champ_temporel",
                )
            with colonne_variable:
                choix_mesure_temps = st.selectbox(
                    "Mesure temporelle",
                    indicateurs_valides,
                    key="desc_mesure_temporelle",
                )
            evolution = produire_evolution(
                echantillon, mesures, choix_date, choix_mesure_temps
            )
            if evolution.empty:
                st.info("Aucune date valide ne peut être interprétée.")
            else:
                st.caption(
                    "Agrégation par jour civil UTC. "
                    + (
                        "Attention : date_collecte décrit la collecte, "
                        "et non la publication."
                        if choix_date == "date_collecte" else
                        "La date correspond au champ sélectionné dans le CSV."
                    )
                )
                col_volume, col_mediane = st.columns(2)
                with col_volume:
                    st.markdown("**Nombre de publications par jour**")
                    st.line_chart(evolution, x="Jour", y="Publications")
                with col_mediane:
                    st.markdown(f"**Médiane quotidienne : {choix_mesure_temps}**")
                    st.line_chart(evolution, x="Jour", y="Médiane")

    with onglet_exports:
        st.subheader("Données et résultats exportables")
        st.download_button(
            "Télécharger les statistiques descriptives (CSV)",
            data=exporter_csv(bilan),
            file_name="statistiques_descriptives_engagement.csv",
            mime="text/csv",
            key="desc_export_bilan",
        )
        st.download_button(
            "Télécharger les mesures numériques normalisées (CSV)",
            data=exporter_csv(mesures.reset_index(drop=True)),
            file_name="mesures_engagement_normalisees.csv",
            mime="text/csv",
            key="desc_export_mesures",
        )
        st.download_button(
            "Télécharger l'échantillon filtré (CSV)",
            data=exporter_csv(echantillon.reset_index(drop=True)),
            file_name="echantillon_descriptif_filtre.csv",
            mime="text/csv",
            key="desc_export_echantillon",
        )
        provenance = pd.DataFrame(
            [{"Indicateur": nom, "Colonne source ou formule": origine}
             for nom, origine in origines.items()]
        )
        st.markdown("**Provenance des indicateurs**")
        st.dataframe(provenance, use_container_width=True, hide_index=True)
        st.caption(
            "Le taux d'engagement est repris du CSV lorsqu'il existe. "
            "À défaut, ou pour compléter ses valeurs manquantes, il est "
            "calculé uniquement si les cinq mesures vues, likes, commentaires, "
            "partages et favoris sont disponibles et que les vues sont "
            "strictement positives. Aucune valeur absente n'est remplacée "
            "silencieusement par zéro."
        )
