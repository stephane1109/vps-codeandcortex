"""Interface Streamlit des statistiques descriptives, par variable et analyse."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from statistiques_descriptives import (
    CHAMPS_CLASSES, CHAMPS_DATES, CHAMPS_ENGAGEMENT, CHAMPS_GROUPES,
    comparer_groupes, preparer_echantillon_descriptif,
    preparer_mesures_engagement, produire_evolution, produire_histogramme,
    repartir_modalites, resumer_engagement,
)


def exporter_csv(tableau: pd.DataFrame) -> bytes:
    """Exporter les résultats en CSV français sans index technique."""
    return tableau.to_csv(
        sep=";", decimal=",", index=False, na_rep="", lineterminator="\n"
    ).encode("utf-8-sig")


def formatter_nombre(nombre: float | int | None, decimales: int = 0) -> str:
    """Mettre en forme un nombre, y compris les valeurs manquantes."""
    if nombre is None or pd.isna(nombre):
        return "—"
    return f"{nombre:,.{decimales}f}".replace(",", " ").replace(".", ",")


def repertorier_variables(
    echantillon: pd.DataFrame, mesures: pd.DataFrame
) -> dict[str, tuple[str, str]]:
    """Retenir les métriques et les variables qualitatives exploitables."""
    variables = {
        nom: ("numérique", nom)
        for nom in mesures if mesures[nom].notna().any()
    }
    presse = [nom for nom in echantillon if nom.startswith("presse_")]
    candidates = list(dict.fromkeys(
        [*CHAMPS_CLASSES, *CHAMPS_GROUPES, *presse] + list(echantillon)
    ))
    exclues = {
        "publication_id", "video_id", "url", "video_url", "video_fichier",
        "legende", "description", "hashtags", "hashtags_recherches",
        "hashtags_correspondants", "contenu_genere_ia", "auteur_original",
        "id_video_originale", "retenue", "date_republication",
    }
    noms_numeriques = {
        alias.casefold() for alias_liste in CHAMPS_ENGAGEMENT.values()
        for alias in alias_liste
    }
    for nom in candidates:
        if nom not in echantillon or nom in exclues or nom in CHAMPS_DATES:
            continue
        if nom.casefold() in noms_numeriques:
            continue
        if nom.endswith(("_brut", "_statut")) or nom.startswith(
            ("date_", "video_", "url_", "id_")
        ):
            continue
        valeurs = echantillon[nom].fillna("").astype(str).str.strip()
        if not 1 <= valeurs.nunique() <= 100 or valeurs.str.len().max() > 120:
            continue
        libelle = nom if nom not in variables else f"{nom} (modalités)"
        variables[libelle] = ("catégorielle", nom)
    if not mesures.empty:
        variables["Ensemble des métriques"] = ("ensemble", "ensemble")
    return variables


def analyses_adaptees(
    nature: str, groupes: list[str], mesures: list[str],
    dates: list[str],
) -> list[str]:
    """Sélectionner les analyses pertinentes selon la nature de la variable."""
    if nature == "numérique":
        analyses = ["Résumé statistique", "Histogramme", "Boîte à moustaches"]
        if groupes:
            analyses.append("Comparaison par catégorie")
        if len(mesures) >= 2:
            analyses.append("Nuage de points")
        if dates:
            analyses.append("Évolution temporelle")
        return analyses
    if nature == "catégorielle":
        analyses = ["Répartition en effectifs", "Répartition en pourcentages"]
        if mesures:
            analyses.append("Engagement selon les modalités")
        return analyses
    return ["Volumes cumulés des interactions", "Données manquantes"]


def tableau_statistiques_variable(
    bilan: pd.DataFrame, variable: str
) -> pd.DataFrame:
    """Présenter les indicateurs d'une seule variable en deux colonnes."""
    ligne = bilan.loc[bilan["Indicateur"].eq(variable)]
    if ligne.empty:
        return pd.DataFrame(columns=["Statistique", "Valeur"])
    return (
        ligne.iloc[0].drop(labels=["Indicateur"])
        .rename_axis("Statistique").reset_index(name="Valeur")
    )


def afficher_resultat(
    tableau: pd.DataFrame, graphique: pd.DataFrame,
    type_graphique: str, axe_x: str = "", axe_y: str = "",
    variable_boite: str = "",
) -> None:
    """Afficher systématiquement le tableau avant son graphique."""
    if tableau.empty:
        st.info("Aucune observation exploitable pour cette analyse.")
        return
    st.markdown("**Tableau des résultats**")
    st.dataframe(tableau.round(4), hide_index=True, use_container_width=True)
    st.download_button(
        "Télécharger ce tableau (CSV)", data=exporter_csv(tableau),
        file_name="resultats_descriptifs_selection.csv",
        mime="text/csv", key="desc_export_resultat",
    )
    st.markdown("**Graphique des résultats**")
    if graphique.empty:
        st.info("Aucune valeur disponible pour le graphique.")
        return
    if type_graphique == "boite":
        st.vega_lite_chart(
            graphique,
            {
                "mark": {"type": "boxplot", "extent": 1.5},
                "encoding": {
                    "x": {
                        "field": "Variable", "type": "nominal", "title": "",
                    },
                    "y": {
                        "field": "Valeur", "type": "quantitative",
                        "title": variable_boite,
                    },
                },
            },
            use_container_width=True,
        )
    elif type_graphique == "nuage":
        st.scatter_chart(
            graphique, x=axe_x, y=axe_y, use_container_width=True
        )
    elif type_graphique == "ligne":
        st.line_chart(
            graphique, x=axe_x, y=axe_y, use_container_width=True
        )
    else:
        if axe_y and axe_y in graphique and not graphique[axe_y].notna().any():
            st.info("Aucune valeur numérique disponible pour le graphique.")
            return
        st.bar_chart(
            graphique, x=axe_x, y=axe_y, use_container_width=True
        )


def construire_onglet_statistique_descriptive(donnees: pd.DataFrame) -> None:
    """Afficher deux menus déroulants puis le tableau et le graphique choisis."""
    st.subheader("Statistique descriptive")
    st.caption(
        "Choisissez une variable, puis une analyse descriptive. "
        "Son tableau et son graphique apparaissent immédiatement en dessous. "
        "Ces analyses sont descriptives : elles ne calculent pas de p-value."
    )

    # Les filtres d'origine sont conservés, mais masqués par défaut.
    with st.expander("Filtres de l'échantillon", expanded=False):
        filtre_gauche, filtre_droite = st.columns(2)
        with filtre_gauche:
            uniquement_retenues = st.checkbox(
                "Conserver uniquement les publications retenues",
                value="retenue" in donnees,
                disabled="retenue" not in donnees,
                key="desc_retenues",
            )
            dedoublonner = st.checkbox(
                "Dédoublonner par publication_id",
                value=False,
                disabled="publication_id" not in donnees,
                key="desc_dedoublonnage",
            )
        with filtre_droite:
            variables_filtrables = [
                nom for nom in (*CHAMPS_GROUPES, *CHAMPS_CLASSES)
                if nom in donnees and 1 < donnees[nom].nunique() <= 100
            ]
            variable_filtre = st.selectbox(
                "Filtrer sur une catégorie (facultatif)",
                ["(Aucun)"] + variables_filtrables,
                key="desc_variable_filtre",
            )
            modalites_filtre = None
            if variable_filtre != "(Aucun)":
                disponibles = sorted(
                    donnees[variable_filtre].fillna("")
                    .astype(str).unique().tolist()
                )
                modalites_filtre = st.multiselect(
                    "Modalités à conserver",
                    disponibles, default=disponibles,
                    key=f"desc_modalites_{variable_filtre}",
                )

    try:
        echantillon = preparer_echantillon_descriptif(
            donnees,
            uniquement_retenues=uniquement_retenues,
            dedoublonner=dedoublonner,
            variable_filtre=(
                None if variable_filtre == "(Aucun)" else variable_filtre
            ),
            modalites_filtre=modalites_filtre,
        )
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    mesures, origines = preparer_mesures_engagement(echantillon)
    bilan = resumer_engagement(mesures, len(echantillon))
    variables = repertorier_variables(echantillon, mesures)
    if not variables:
        st.warning("Aucune variable descriptive exploitable dans ce fichier.")
        return

    noms_groupes = [
        nom for nom in CHAMPS_GROUPES if nom in echantillon
        and 1 < echantillon[nom].nunique() <= 200
    ]
    noms_groupes.extend(
        nom for nom in echantillon.columns
        if (nom.startswith("presse_") or nom in CHAMPS_CLASSES)
        and nom not in noms_groupes
        and 1 < echantillon[nom].nunique() <= 100
    )
    noms_mesures = [
        nom for nom in mesures if mesures[nom].notna().any()
    ]
    noms_dates = [nom for nom in CHAMPS_DATES if nom in echantillon]
    st.caption(
        f"Échantillon : {formatter_nombre(len(echantillon))} publications "
        f"sur {formatter_nombre(len(donnees))} lignes importées."
    )

    colonne_variable, colonne_test = st.columns(2)
    with colonne_variable:
        variable = st.selectbox(
            "Variable à analyser",
            options=list(variables),
            key="desc_variable_choisie",
        )
    nature, nom_variable = variables[variable]
    analyses = analyses_adaptees(
        nature, noms_groupes, noms_mesures, noms_dates
    )
    with colonne_test:
        analyse = st.selectbox(
            "Test / analyse descriptive",
            options=analyses,
            key=f"desc_analyse_{variable}",
        )

    st.divider()
    st.subheader(f"Résultats : {variable}")
    st.caption(f"Analyse sélectionnée : {analyse}")

    tableau = pd.DataFrame()
    graphique = pd.DataFrame()
    genre = "barres"
    axe_x = ""
    axe_y = ""
    commentaire = ""
    if nature == "numérique":
        valeurs = mesures[nom_variable]
        if analyse == "Résumé statistique":
            tableau = tableau_statistiques_variable(bilan, nom_variable)
            chiffres = bilan.loc[
                bilan["Indicateur"].eq(nom_variable)
            ].iloc[0]
            graphique = pd.DataFrame({
                "Statistique": ["Moyenne", "Médiane"],
                "Valeur": [chiffres["Moyenne"], chiffres["Médiane"]],
            }).dropna()
            axe_x, axe_y = "Statistique", "Valeur"
            commentaire = (
                "La moyenne peut être influencée par les valeurs extrêmes. "
                "La médiane est moins sensible à ces valeurs."
            )
        elif analyse == "Histogramme":
            options_gauche, options_droite = st.columns(2)
            with options_gauche:
                nombre_classes = st.slider(
                    "Nombre de classes", 5, 60, 25, 5,
                    key="desc_nombre_classes",
                )
            with options_droite:
                logarithmique = st.checkbox(
                    "Échelle logarithmique log(1 + x)",
                    value=True, key="desc_echelle_log",
                )
            tableau = produire_histogramme(
                valeurs, nombre_classes, logarithmique
            )
            graphique = tableau
            axe_x, axe_y = "Classe", "Publications"
            commentaire = (
                "Chaque barre représente le nombre de publications "
                "dans un intervalle de valeurs. Les bornes de classes "
                "sont présentées dans l'unité originale."
            )
        elif analyse == "Boîte à moustaches":
            tableau = tableau_statistiques_variable(bilan, nom_variable)
            graphique = pd.DataFrame({
                "Variable": nom_variable, "Valeur": valeurs.dropna()
            })
            if len(graphique) > 10000:
                graphique = graphique.sample(10000, random_state=42)
                commentaire = (
                    "Boîte calculée sur 10 000 observations tirées "
                    "de manière reproductible ; tableau sur le corpus complet. "
                )
            genre = "boite"
            commentaire += (
                "La boîte représente les quartiles et la médiane ; "
                "les moustaches utilisent 1,5 fois l'écart interquartile."
            )
        elif analyse == "Comparaison par catégorie":
            gauche, droite = st.columns([3, 1])
            with gauche:
                regroupement = st.selectbox(
                    "Variable de regroupement", noms_groupes,
                    key="desc_groupe_comparaison",
                )
            with droite:
                seuil = st.number_input(
                    "N minimal par groupe", min_value=1,
                    max_value=max(1, len(echantillon)), value=1,
                    key="desc_seuil_groupes",
                )
            tableau = comparer_groupes(
                echantillon, mesures, regroupement, nom_variable,
                minimum_observations=int(seuil),
            )
            graphique = tableau
            axe_x, axe_y = "Groupe", "Médiane"
            commentaire = (
                "La médiane est calculée pour chaque catégorie. "
                "Maximum de 20 groupes, sans test de significativité."
            )
        elif analyse == "Nuage de points":
            autres = [nom for nom in noms_mesures if nom != nom_variable]
            seconde = st.selectbox(
                "Deuxième variable numérique", autres,
                key=f"desc_autre_mesure_{nom_variable}",
            )
            logarithmique = st.checkbox(
                "Appliquer log(1 + x) aux deux axes",
                value=True, key="desc_log_nuage",
            )
            tableau = mesures[[nom_variable, seconde]].dropna()
            graphique = tableau
            if len(graphique) > 5000:
                graphique = graphique.sample(5000, random_state=42)
                commentaire = (
                    "Graphique limité à 5 000 observations tirées "
                    "de manière reproductible ; tableau complet. "
                )
            if logarithmique:
                graphique = np.log1p(graphique)
                commentaire += "Les deux axes utilisent log(1 + x)."
            genre = "nuage"
            axe_x, axe_y = nom_variable, seconde
            tableau = tableau.reset_index(drop=True)
        elif analyse == "Évolution temporelle":
            gauche, droite = st.columns(2)
            with gauche:
                champ_date = st.selectbox(
                    "Champ temporel", noms_dates,
                    key="desc_champ_temporel",
                )
            with droite:
                courbe = st.selectbox(
                    "Représenter", ["Médiane", "Publications"],
                    key="desc_type_evolution",
                )
            tableau = produire_evolution(
                echantillon, mesures, champ_date, nom_variable
            )
            graphique = tableau
            genre = "ligne"
            axe_x, axe_y = "Jour", courbe
            commentaire = (
                "Agrégation par jour UTC. "
                + ("Attention : date_collecte ne désigne pas la publication."
                   if champ_date == "date_collecte"
                   else "Les dates proviennent du champ sélectionné.")
            )
    elif nature == "catégorielle":
        if analyse.startswith("Répartition"):
            tableau = repartir_modalites(echantillon, nom_variable)
            graphique = tableau.head(30)
            axe_x = "Modalité"
            axe_y = (
                "Effectif" if analyse == "Répartition en effectifs"
                else "Proportion (%)"
            )
            if len(tableau) > 30:
                commentaire = (
                    "Le graphique présente les 30 modalités les plus fréquentes. "
                    "Le tableau contient toutes les modalités."
                )
        else:
            index_defaut = (
                noms_mesures.index("Taux d'engagement (%)")
                if "Taux d'engagement (%)" in noms_mesures else 0
            )
            gauche, droite = st.columns([3, 1])
            with gauche:
                indicateur = st.selectbox(
                    "Métrique d'engagement",
                    noms_mesures, index=index_defaut,
                    key="desc_mesure_comparaison",
                )
            with droite:
                seuil = st.number_input(
                    "N minimal par groupe", min_value=1,
                    max_value=max(1, len(echantillon)), value=1,
                    key="desc_seuil_categories",
                )
            tableau = comparer_groupes(
                echantillon, mesures, nom_variable, indicateur,
                minimum_observations=int(seuil),
            )
            graphique = tableau
            axe_x, axe_y = "Groupe", "Médiane"
            commentaire = (
                f"Les médianes de {indicateur} sont comparées par modalité. "
                "Il ne s'agit pas d'un test de significativité."
            )
    else:
        if analyse == "Volumes cumulés des interactions":
            interactions = [
                nom for nom in ("Likes", "Commentaires", "Partages", "Favoris")
                if nom in mesures
            ]
            tableau = (
                bilan.set_index("Indicateur")
                .reindex(interactions)[["N valide", "Somme"]]
                .rename_axis("Interaction").reset_index()
            )
            graphique = tableau.rename(columns={"Somme": "Total"})
            axe_x, axe_y = "Interaction", "Total"
            commentaire = (
                "Les totaux de chaque métrique reposent sur les valeurs "
                "disponibles dans le corpus filtré."
            )
        else:
            tableau = bilan[[
                "Indicateur", "N valide", "N absent", "Absents (%)"
            ]].copy()
            graphique = tableau
            axe_x, axe_y = "Indicateur", "Absents (%)"
            commentaire = (
                "Les données manquantes ne sont jamais assimilées à des zéros."
            )

    afficher_resultat(
        tableau, graphique, genre, axe_x, axe_y, nom_variable
    )
    if commentaire:
        st.caption(commentaire)

    with st.expander("Exports complémentaires et provenance", expanded=False):
        if not bilan.empty:
            st.download_button(
                "Toutes les statistiques descriptives (CSV)",
                exporter_csv(bilan),
                file_name="statistiques_descriptives_engagement.csv",
                mime="text/csv", key="desc_export_bilan",
            )
        if not mesures.empty:
            st.download_button(
                "Mesures numériques normalisées (CSV)",
                exporter_csv(mesures.reset_index(drop=True)),
                file_name="mesures_engagement_normalisees.csv",
                mime="text/csv", key="desc_export_mesures",
            )
        st.download_button(
            "Échantillon filtré (CSV)",
            exporter_csv(echantillon.reset_index(drop=True)),
            file_name="echantillon_descriptif_filtre.csv",
            mime="text/csv", key="desc_export_echantillon",
        )
        if origines:
            provenance = pd.DataFrame([
                {"Indicateur": nom, "Colonne source ou formule": origine}
                for nom, origine in origines.items()
            ])
            st.dataframe(
                provenance, hide_index=True, use_container_width=True
            )
        st.caption(
            "Le taux d'engagement existant est conservé. "
            "Il est calculé pour les valeurs manquantes uniquement lorsque "
            "les vues sont positives et les quatre interactions sont connues. "
            "Le corpus importé n'est jamais modifié."
        )
