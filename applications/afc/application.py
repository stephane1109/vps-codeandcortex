"""Interface Streamlit en français pour l'AFC FactoMineR sur fichiers CSV."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from interface_statistiques_descriptives import construire_onglet_statistique_descriptive
from statistiques_descriptives import CHAMPS_ENGAGEMENT

from traitement_csv import (
    concatener_fichiers_csv, decrire_variables,
    exclure_modalites_contingence, lire_csv, preparer_acm,
    preparer_contingence, preparer_tableau_inerties,
)


DOSSIER_APPLICATION = Path(__file__).resolve().parent
NOMBRE_LIGNES_APERCU = 20
DELAI_CALCUL = max(10, int(os.environ.get("AFC_TIMEOUT_SECONDS", "180")))

st.set_page_config(
    page_title="AFC — FactoMineR",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False, max_entries=3)
def importer_donnees(contenu: bytes, separateur: str, encodage: str) -> pd.DataFrame:
    """Met en cache l'import pour éviter de relire le CSV à chaque interaction."""
    return lire_csv(contenu, separateur=separateur, encodage=encodage)


def choisir_defaut(variables: list[str], nom_souhaite: str, position: int = 0) -> int:
    """Choisit la variable privilégiée si elle figure dans le jeu de données."""
    return variables.index(nom_souhaite) if nom_souhaite in variables else min(position, len(variables) - 1)


def diagnostiquer_echec_r(
    sortie_erreur: str, sortie_standard: str
) -> str:
    """Prioriser le message d'erreur R plutôt que les avertissements graphiques."""
    messages = "\n".join(
        morceau for morceau in (sortie_erreur, sortie_standard) if morceau
    ).splitlines()
    indices = [
        indice for indice, ligne in enumerate(messages)
        if ligne.lstrip().startswith(("Error in ", "Error:", "Erreur", "ERROR"))
    ]
    if indices:
        debut = indices[-1]
        # Conserver les lignes explicatives qui suivent l'erreur R.
        extrait = messages[debut:debut + 8]
        arret = next(
            (i for i, ligne in enumerate(extrait)
             if ligne.lstrip().startswith("Execution halted")),
            None,
        )
        return "\n".join(extrait[:arret + 1] if arret is not None else extrait)[:3500]
    return "\n".join(messages[-18:])[-3500:] or (
        "Le processus R s'est arrêté sans message exploitable."
    )


def executer_moteur_r(
    tableau: pd.DataFrame,
    variable_lignes: str,
    variable_colonnes: str,
    nom_source: str,
    effectif_initial: int,
    effectif_final: int,
    parametres: dict,
) -> dict:
    """Exécute R dans un répertoire temporaire isolé et renvoie les exports."""
    executable = shutil.which("Rscript")
    if executable is None:
        raise RuntimeError(
            "Rscript est introuvable. Déployer le projet avec son Dockerfile "
            "pour installer R et FactoMineR automatiquement."
        )

    with tempfile.TemporaryDirectory(prefix="afc_factominer_") as temporaire:
        dossier = Path(temporaire)
        fichier_tableau = dossier / "contingence.tsv"
        dossier_sortie = dossier / "resultats"
        dossier_sortie.mkdir()
        tableau.to_csv(fichier_tableau, sep="\t", encoding="utf-8", index=True, index_label="modalite")

        commande = [
            executable,
            str(DOSSIER_APPLICATION / "moteur_afc.R"),
            str(fichier_tableau),
            str(dossier_sortie),
            variable_lignes,
            variable_colonnes,
            nom_source,
            str(effectif_initial),
            str(effectif_final),
        ]
        try:
            processus = subprocess.run(
                commande,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=DELAI_CALCUL,
                check=False,
            )
        except subprocess.TimeoutExpired as erreur:
            raise RuntimeError(
                f"Le calcul R a dépassé la limite de {DELAI_CALCUL} secondes. "
                "Réduire le nombre de modalités ou augmenter AFC_TIMEOUT_SECONDS."
            ) from erreur
        if processus.returncode != 0:
            details = (processus.stderr or processus.stdout).strip()
            raise RuntimeError(f"Erreur dans FactoMineR : {details[:2500]}")

        (dossier_sortie / "17_parametres_analyse.json").write_text(
            json.dumps(parametres, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        fichiers = {
            chemin.name: chemin.read_bytes()
            for chemin in sorted(dossier_sortie.iterdir())
            if chemin.is_file()
        }
        attendus = {
            "00_rapport_afc.txt", "06_valeurs_propres_inerties.csv",
            "13_plan_factoriel.png", "16_resultats_statistiques.csv",
            "significativite_modalites_factominer.csv",
        }
        manquants = sorted(attendus - fichiers.keys())
        if manquants:
            raise RuntimeError(f"Export FactoMineR incomplet : {', '.join(manquants)}")

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as fichier_zip:
            for nom, contenu in fichiers.items():
                fichier_zip.writestr(nom, contenu)
        return {
            "archive": archive.getvalue(),
            "fichiers": fichiers,
            "sortie_standard": processus.stdout,
        }


def afficher_resultats(
    resultats: dict, methode: str = "AFC", mode_acm: str = "Indicator"
) -> None:
    """Présente les graphiques, mesures et exports calculés par R."""
    fichiers = resultats["fichiers"]
    st.subheader(f"Résultats de l'{methode}")
    suffixe_methode = (
        "_burt" if methode == "ACM" and mode_acm == "Burt" else ""
    )
    st.download_button(
        "Télécharger tous les résultats (ZIP)",
        data=resultats["archive"],
        file_name=f"resultats_{methode.lower()}{suffixe_methode}_factominer.zip",
        mime="application/zip",
        type="primary",
    )
    statistiques = pd.read_csv(
        io.BytesIO(fichiers["16_resultats_statistiques.csv"]),
        sep=";", dtype=str, decimal=",", encoding="utf-8",
    )
    valeurs = dict(zip(statistiques["indicateur"], statistiques["valeur"]))
    indicateurs = st.columns(4)
    indicateurs[0].metric("Observations", valeurs.get("Observations analysées", "—"))
    indicateurs[1].metric("Axes factoriels", valeurs.get("Axes factoriels", "—"))
    indicateurs[2].metric(
        "Modalités significatives",
        valeurs.get("Modalités significatives (p <= 0,05)", "—"),
    )
    indicateurs[3].metric(
        "Inertie totale",
        valeurs.get("Inertie totale (FactoMineR)", "—"),
    )
    if methode == "AFC":
        st.caption(
            "Résultats issus de FactoMineR::CA() et FactoMineR::descfreq(). "
            "Le rapport méthodologique utilise le résumé natif de FactoMineR "
            "ou, pour une AFC à un seul axe, les matrices natives de CA()."
        )
    else:
        libelle_mode = (
            "tableau de Burt" if mode_acm == "Burt"
            else "tableau disjonctif complet (TDC)"
        )
        st.caption(
            f"Résultats de FactoMineR::MCA() selon le {libelle_mode} ; "
            "le filtre à p ≤ 0,05 utilise directement les p-values "
            "de FactoMineR::dimdesc(). Les valeurs-tests et les "
            "coordonnées proviennent de FactoMineR::MCA()."
        )

    onglet_plan, onglet_inertie, onglet_matrices, onglet_rapport = st.tabs(
        ["Plan factoriel", "Inerties", "Tableaux", "Rapport méthodologique"]
    )
    with onglet_plan:
        filtrer_modalites = st.checkbox(
            "Afficher uniquement les modalités significatives (p ≤ 0,05)",
            value=False,
            key=f"filtrer_modalites_{methode.lower()}",
            help=(
                "Décochez pour voir toutes les modalités actives ; "
                "cochez pour afficher uniquement les modalités significatives. "
                "Les calculs, inerties et exports restent inchangés."
            ),
        )
        nom_graphique = (
            "13_plan_factoriel_significatif.png"
            if filtrer_modalites
            else "13_plan_factoriel.png"
        )
        st.image(fichiers[nom_graphique], use_container_width=True)
        if methode == "ACM":
            if "21_coordonnees_qualitatives_supplementaires.csv" in fichiers:
                st.caption(
                    "Les modalités des variables supplémentaires apparaissent "
                    "en triangles violets et restent visibles lorsque le "
                    "filtre à p ≤ 0,05 des modalités actives est appliqué."
                )
            if "26_plan_quantitatives_supplementaires.png" in fichiers:
                st.subheader("Projection des variables supplémentaires")
                st.image(
                    fichiers["26_plan_quantitatives_supplementaires.png"],
                    use_container_width=True,
                )
                st.caption(
                    "Projection calculée par FactoMineR : les variables "
                    "numériques sont représentées sur un graphique séparé."
                )
        st.caption(
            "Plan complet : toutes les modalités actives."
            if not filtrer_modalites
            else (
                "Plan filtré : modalités associées significativement à une "
                "autre modalité selon FactoMineR::descfreq (AFC)."
                if methode == "AFC"
                else (
                    "Plan filtré : modalités caractérisant l'axe 1 ou 2 "
                    "avec p ≤ 0,05 selon FactoMineR::dimdesc(), "
                    "sans correction multiple."
                )
            )
        )
        st.caption(
            "Cette case ne modifie pas le calcul factoriel. "
            "Les deux graphiques sont disponibles dans le ZIP. "
            "Lorsque l'analyse ne comporte qu'un axe, le filtre n'est pas appliqué."
        )
        if methode == "ACM":
            # Les effectifs et p-values affichés proviennent du même export
            # que le filtre R, sans retraitement statistique en Python.
            nom_significativite = "significativite_modalites_factominer.csv"
            significativites = pd.read_csv(
                io.BytesIO(fichiers[nom_significativite]),
                sep=";", decimal=",", encoding="utf-8",
                low_memory=False,
            )
            p_values = pd.to_numeric(
                significativites["p_value_min"], errors="coerce"
            )
            nombre_valides = int(p_values.notna().sum())
            nombre_significatives = int(p_values.le(0.05).sum())
            p_minimale = p_values.min()
            valeur_p = (
                f"{p_minimale:.3g}".replace(".", ",")
                if pd.notna(p_minimale) else "indisponible"
            )
            diagnostic_p = (
                f"Vérification ACM : {nombre_significatives} modalité(s) "
                f"significative(s) sur {len(significativites)} ; "
                f"{nombre_valides} p-value(s) exploitables ; "
                f"p minimale = {valeur_p}."
            )
            if nombre_significatives == 0:
                st.warning(
                    diagnostic_p
                    + " Aucune modalité n'atteint p ≤ 0,05 sur les axes "
                    "représentés. Le plan complet reste accessible."
                )
            else:
                st.caption(diagnostic_p)
            with st.expander(
                "Contrôler les p-values de toutes les modalités",
                expanded=False,
            ):
                colonnes_p = [
                    "variable", "modalite", "identifiant_dimdesc", "v_test_axe_1",
                    "p_value_axe_1", "v_test_axe_2", "p_value_axe_2",
                    "p_value_min", "significative_005",
                ]
                tableau_p = significativites[
                    [nom for nom in colonnes_p if nom in significativites]
                ].copy()
                if "p_value_min" in tableau_p:
                    tableau_p = tableau_p.sort_values(
                        "p_value_min", na_position="last"
                    )
                st.dataframe(
                    tableau_p, hide_index=True, use_container_width=True,
                )
                st.download_button(
                    "Télécharger les p-values des modalités (CSV)",
                    data=fichiers[nom_significativite],
                    file_name=nom_significativite,
                    mime="text/csv",
                    key="telecharger_pvalues_acm",
                )
    with onglet_inertie:
        st.image(fichiers["15_inerties.png"], use_container_width=True)
        st.subheader("Inertie des axes factoriels (%)")
        tableau_inerties = preparer_tableau_inerties(
            fichiers["06_valeurs_propres_inerties.csv"]
        )
        st.dataframe(
            tableau_inerties,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Valeur propre": st.column_config.NumberColumn(
                    "Valeur propre", format="%.4f"
                ),
                "Inertie (%)": st.column_config.NumberColumn(
                    "Inertie (%)", format="%.2f"
                ),
                "Inertie cumulée (%)": st.column_config.NumberColumn(
                    "Inertie cumulée (%)", format="%.2f"
                ),
            },
        )
        if methode == "AFC":
            st.caption(
                "Les valeurs propres, les pourcentages et les inerties cumulées "
                "proviennent de FactoMineR::CA()."
            )
        else:
            st.caption(
                "Pour le TDC, les inerties sont rapportées à la somme des "
                "valeurs propres du tableau disjonctif. Pour Burt, les valeurs "
                "propres sont leurs carrés ; les pourcentages changent."
            )
            nom_comparaison = "18_comparaison_inerties_tdc_burt.csv"
            if nom_comparaison in fichiers:
                st.subheader("Comparaison des inerties : TDC et Burt")
                comparaison = pd.read_csv(
                    io.BytesIO(fichiers[nom_comparaison]),
                    sep=";", decimal=",", encoding="utf-8",
                )
                st.dataframe(
                    comparaison, hide_index=True, use_container_width=True
                )
                st.download_button(
                    "Télécharger la comparaison TDC–Burt (CSV)",
                    data=fichiers[nom_comparaison],
                    file_name=nom_comparaison,
                    mime="text/csv",
                )
        st.download_button(
            "Télécharger le tableau des inerties (CSV)",
            data=fichiers["06_valeurs_propres_inerties.csv"],
            file_name="06_valeurs_propres_inerties.csv",
            mime="text/csv",
        )
    with onglet_matrices:
        choix = [nom for nom in fichiers if nom.lower().endswith(".csv")]
        tableau_selectionne = st.selectbox("Tableau statistique", choix)
        valeurs_tableau = pd.read_csv(
            io.BytesIO(fichiers[tableau_selectionne]),
            sep=";", encoding="utf-8", low_memory=False,
        )
        st.dataframe(valeurs_tableau, use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger ce tableau (CSV)",
            fichiers[tableau_selectionne],
            file_name=tableau_selectionne,
            mime="text/csv",
        )
    with onglet_rapport:
        nom_rapport = (
            "00_rapport_afc.txt" if methode == "AFC"
            else "00_rapport_acm.txt"
        )
        st.text(fichiers[nom_rapport].decode("utf-8"))



def executer_moteur_acm(
    donnees: pd.DataFrame,
    nom_source: str,
    effectif_initial: int,
    effectif_final: int,
    parametres: dict,
    methode_calcul: str = "Indicator",
    variables_supplementaires_qualitatives: list[str] | None = None,
    variables_supplementaires_quantitatives: list[str] | None = None,
) -> dict:
    """Exécuter l'ACM native sur TDC ou sur le tableau de Burt."""
    if methode_calcul not in {"Indicator", "Burt"}:
        raise ValueError("Méthode ACM invalide : Indicator ou Burt attendu.")
    executable = shutil.which("Rscript")
    if executable is None:
        raise RuntimeError(
            "Rscript est introuvable. Déployer l'application avec le Dockerfile "
            "pour installer R et FactoMineR."
        )
    supplementaires_qualitatives = (
        variables_supplementaires_qualitatives or []
    )
    supplementaires_quantitatives = (
        variables_supplementaires_quantitatives or []
    )
    toutes_supplementaires = [
        *supplementaires_qualitatives, *supplementaires_quantitatives
    ]
    if (
        len(set(toutes_supplementaires)) != len(toutes_supplementaires)
        or any(nom not in donnees for nom in toutes_supplementaires)
    ):
        raise ValueError(
            "Variables supplémentaires absentes ou sélectionnées deux fois."
        )
    colonnes_entree = list(donnees.columns)
    indices_quali_sup = [
        colonnes_entree.index(nom) + 1
        for nom in supplementaires_qualitatives
    ]
    indices_quanti_sup = [
        colonnes_entree.index(nom) + 1
        for nom in supplementaires_quantitatives
    ]
    if len(colonnes_entree) - len(toutes_supplementaires) < 3:
        raise ValueError("L'ACM nécessite au moins trois variables actives.")

    with tempfile.TemporaryDirectory(prefix="acm_factominer_") as temporaire:
        dossier = Path(temporaire)
        chemin_donnees = dossier / "categories.tsv"
        dossier_sortie = dossier / "resultats"
        dossier_sortie.mkdir()
        donnees.to_csv(
            chemin_donnees, sep="\t", index=False, encoding="utf-8"
        )
        commande = [
            executable,
            str(DOSSIER_APPLICATION / "moteur_acm.R"),
            str(chemin_donnees),
            str(dossier_sortie),
            nom_source,
            str(effectif_initial),
            str(effectif_final),
            methode_calcul,
            ",".join(map(str, indices_quali_sup)),
            ",".join(map(str, indices_quanti_sup)),
        ]
        try:
            processus = subprocess.run(
                commande, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=DELAI_CALCUL, check=False,
            )
        except subprocess.TimeoutExpired as erreur:
            raise RuntimeError(
                f"Le calcul ACM a dépassé {DELAI_CALCUL} secondes. "
                "Réduire le nombre de variables ou ajuster AFC_TIMEOUT_SECONDS."
            ) from erreur
        if processus.returncode != 0:
            details = diagnostiquer_echec_r(
                processus.stderr, processus.stdout
            )
            raise RuntimeError(
                "Échec du calcul ou des exports ACM (R) : " + details
            )
        (dossier_sortie / "17_parametres_analyse.json").write_text(
            json.dumps(parametres, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fichiers = {
            chemin.name: chemin.read_bytes()
            for chemin in sorted(dossier_sortie.iterdir())
            if chemin.is_file()
        }
        attendus = {
            "00_rapport_acm.txt", "01_donnees_acm_filtrees.csv",
            "06_valeurs_propres_inerties.csv",
            "07_coordonnees_modalites.csv",
            "08_contributions_modalites.csv",
            "09_cos2_modalites.csv",
            "13_plan_factoriel.png",
            "13_plan_factoriel_significatif.png",
            "14_plan_factoriel.pdf",
            "14_plan_factoriel_significatif.pdf",
            "15_inerties.png", "16_resultats_statistiques.csv",
            "significativite_modalites_factominer.csv",
            "18_comparaison_inerties_tdc_burt.csv",
            "19_couleurs_variables.csv",
            "20_diagnostic_filtre_pvalue.csv",
        }
        if supplementaires_qualitatives:
            attendus.update({
                "21_coordonnees_qualitatives_supplementaires.csv",
                "22_cos2_qualitatives_supplementaires.csv",
                "23_vtest_qualitatives_supplementaires.csv",
                "24_eta2_qualitatives_supplementaires.csv",
            })
        if supplementaires_quantitatives:
            attendus.update({
                "25_coordonnees_quantitatives_supplementaires.csv",
                "26_plan_quantitatives_supplementaires.png",
                "27_plan_quantitatives_supplementaires.pdf",
            })
        manquants = sorted(attendus.difference(fichiers))
        if manquants:
            raise RuntimeError(
                "Exports ACM FactoMineR incomplets : " + ", ".join(manquants)
            )
        archive = io.BytesIO()
        with zipfile.ZipFile(
            archive, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as fichier_zip:
            for nom, donnees_fichier in fichiers.items():
                fichier_zip.writestr(nom, donnees_fichier)
        return {
            "archive": archive.getvalue(),
            "fichiers": fichiers,
            "sortie_standard": processus.stdout,
        }


def construire_interface_acm(
    donnees: pd.DataFrame,
    contenu: bytes,
    nom_source: str,
    noms_variables: list[str],
    candidates: list[str],
) -> None:
    """Construire une ACM multi-variables et actualiser ses sorties."""
    st.subheader("2. Sélectionner les variables actives de l'ACM")
    defaut_acm = [
        nom for nom in [
            "vues_classe", "classe_taux_engagement", "type_media",
            "likes_classe", "commentaires_classe",
        ]
        if nom in candidates
    ]
    for nom in candidates:
        if len(defaut_acm) >= 3:
            break
        if nom not in defaut_acm:
            defaut_acm.append(nom)
    variables_actives = st.multiselect(
        "Variables catégorielles actives (trois au minimum)",
        options=noms_variables,
        default=defaut_acm[:3],
        help=(
            "FactoMineR::MCA() analyse simultanément les modalités de toutes "
            "les variables sélectionnées, sans transformation en tableau 2 × 2."
        ),
        key="acm_variables_actives",
    )
    if len(variables_actives) < 3:
        st.info("Sélectionnez au moins trois variables pour l'ACM.")
        return

    st.subheader("Variable supplémentaire")
    st.caption(
        "Choisissez une ou plusieurs variables à afficher sur les axes de "
        "l'ACM, sans participer à leur construction. Laissez ce champ vide "
        "si vous n'en souhaitez pas."
    )
    options_supplementaires = [
        nom for nom in noms_variables if nom not in variables_actives
    ]
    variables_supplementaires = st.multiselect(
        "Variable supplémentaire",
        options=options_supplementaires,
        default=[],
        key="acm_variables_supplementaires",
        placeholder="Choisir une variable dans le CSV",
        help=(
            "Vous pouvez sélectionner plusieurs colonnes. "
            "FactoMineR les projette sans modifier les axes de l'ACM."
        ),
    )

    # La distinction exigée par FactoMineR est faite automatiquement.
    # Les mesures numériques explicites restent numériques, y compris
    # lorsqu'elles ont peu de valeurs différentes. Une variable codée
    # par quelques nombres (0/1, classes...) reste une catégorie.
    descriptions_variables = decrire_variables(donnees)
    candidats_numeriques = set(
        descriptions_variables.loc[
            descriptions_variables["Diagnostic"].eq("À recoder (numérique)"),
            "Variable",
        ]
    )
    aliases_mesures = {
        alias.casefold()
        for noms_alias in CHAMPS_ENGAGEMENT.values()
        for alias in noms_alias
    }
    variables_supplementaires_quantitatives = [
        nom for nom in variables_supplementaires
        if nom.casefold() in aliases_mesures
        or nom in candidats_numeriques
    ]
    variables_supplementaires_qualitatives = [
        nom for nom in variables_supplementaires
        if nom not in variables_supplementaires_quantitatives
    ]

    choix_methode = st.radio(
        "Formulation de l'ACM",
        options=[
            "Tableau disjonctif complet (TDC)",
            "Tableau de Burt",
        ],
        horizontal=True,
        key="acm_methode_calcul",
        help=(
            "Les deux calculs sont réalisés avec FactoMineR::MCA(), "
            "respectivement method='Indicator' et method='Burt'. "
            "Le tableau de Burt produit des valeurs propres au carré "
            "et une répartition différente de l'inertie."
        ),
    )
    methode_calcul = (
        "Indicator"
        if choix_methode == "Tableau disjonctif complet (TDC)"
        else "Burt"
    )
    st.caption(
        "Les coordonnées, contributions et cos² sont ceux de la méthode "
        "sélectionnée. Un tableau comparatif distingue les deux "
        "normalisations de l'inertie."
    )

    st.subheader("3. Paramètres de préparation et de calcul")
    col_param, col_filtre = st.columns(2)
    with col_param:
        uniquement_retenues = st.checkbox(
            "Conserver uniquement les publications retenues",
            value="retenue" in donnees.columns,
            disabled="retenue" not in donnees.columns,
        )
        dedoublonner = st.checkbox(
            "Dédoublonner par publication_id (conserver la première occurrence)",
            value=False,
            disabled="publication_id" not in donnees.columns,
        )
        exclure_indeterminees = st.checkbox(
            "Exclure les modalités indéterminées", value=True
        )
        inclure_manquantes = st.checkbox(
            "Conserver les valeurs manquantes comme une modalité distincte",
            value=False,
        )
    with col_filtre:
        maximum_modalites = st.number_input(
            "Nombre maximal de modalités par variable",
            min_value=2, max_value=100, value=40, step=1,
        )
        options_filtre = ["(Aucun)"] + noms_variables
        variable_filtre_choisie = st.selectbox(
            "Filtrer sur une variable (facultatif)", options_filtre
        )
        variable_filtre = (
            None if variable_filtre_choisie == "(Aucun)"
            else variable_filtre_choisie
        )
        modalites_filtre = None
        if variable_filtre:
            modalites = sorted(donnees[variable_filtre].unique().tolist())
            if len(modalites) > 300:
                st.error("Cette variable possède plus de 300 modalités.")
                return
            modalites_filtre = st.multiselect(
                "Modalités à conserver", modalites, default=modalites
            )

    options_preparation = dict(
        donnees=donnees,
        variables=variables_actives,
        variables_supplementaires_qualitatives=(
            variables_supplementaires_qualitatives
        ),
        variables_supplementaires_quantitatives=(
            variables_supplementaires_quantitatives
        ),
        uniquement_retenues=uniquement_retenues,
        dedoublonner=dedoublonner,
        exclure_indeterminees=exclure_indeterminees,
        inclure_manquantes=inclure_manquantes,
        maximum_modalites=int(maximum_modalites),
        variable_filtre=variable_filtre,
        modalites_filtre=modalites_filtre,
    )
    try:
        preparation_initiale = preparer_acm(**options_preparation)
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    st.subheader("4. Vérifier et modifier les modalités de l'ACM")
    st.caption(
        "Les modalités exclues retirent les observations correspondantes "
        "avant l'ACM. Les autres variables et le CSV original restent intacts. "
        "La modification d'une exclusion relance automatiquement FactoMineR."
    )
    portee = {
        "empreinte_sha256": hashlib.sha256(contenu).hexdigest(),
        "variables_actives": variables_actives,
        "variables_supplementaires_qualitatives": (
            variables_supplementaires_qualitatives
        ),
        "variables_supplementaires_quantitatives": (
            variables_supplementaires_quantitatives
        ),
        "filtres": {
            "retenues": uniquement_retenues,
            "dedoublonner": dedoublonner,
            "exclure_indeterminees": exclure_indeterminees,
            "inclure_manquantes": inclure_manquantes,
            "maximum_modalites": int(maximum_modalites),
            "variable_filtre": variable_filtre,
            "modalites_filtre": sorted(modalites_filtre)
            if modalites_filtre is not None else None,
        },
    }
    identifiant_portee = hashlib.sha256(
        json.dumps(portee, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("acm_portee") != identifiant_portee:
        st.session_state["acm_portee"] = identifiant_portee
        for indice in range(len(noms_variables)):
            st.session_state.pop(f"acm_exclure_{indice}", None)
        st.session_state["acm_exclusions_precedentes"] = (
            identifiant_portee, ()
        )

    exclusions = {}
    colonnes = st.columns(2)
    for indice, nom in enumerate(variables_actives):
        with colonnes[indice % 2]:
            valeurs_possibles = sorted(
                preparation_initiale.donnees[nom].unique().tolist()
            )
            exclusions[nom] = st.multiselect(
                f"Supprimer des modalités — {nom}",
                options=valeurs_possibles,
                key=f"acm_exclure_{indice}",
            )
    if st.button(
        "Rétablir toutes les modalités de l'ACM",
        disabled=not any(exclusions.values()),
    ):
        for indice in range(len(variables_actives)):
            st.session_state[f"acm_exclure_{indice}"] = []
        st.rerun()

    selection_exclusions = (
        identifiant_portee,
        methode_calcul,
        tuple(
            (nom, tuple(sorted(valeurs)))
            for nom, valeurs in exclusions.items()
        ),
    )
    recalcul_automatique = (
        selection_exclusions
        != st.session_state.get("acm_exclusions_precedentes")
    )
    st.session_state["acm_exclusions_precedentes"] = selection_exclusions
    try:
        preparation = preparer_acm(
            **options_preparation, modalites_a_exclure=exclusions
        )
    except ValueError as erreur:
        st.warning(str(erreur))
        st.dataframe(
            preparation_initiale.donnees.head(NOMBRE_LIGNES_APERCU),
            use_container_width=True,
        )
        return

    metriques = st.columns(3)
    metriques[0].metric("Observations analysables", preparation.effectif_final)
    metriques[1].metric("Variables actives", len(variables_actives))
    metriques[2].metric(
        "Modalités actives",
        sum(preparation.donnees[nom].nunique() for nom in variables_actives),
    )
    if variables_supplementaires:
        st.caption(
            "Variables supplémentaires : "
            + " ; ".join(variables_supplementaires)
            + ". Elles ne contribuent pas à la construction des axes."
        )
    tableau_effectifs = pd.concat(
        [
            pd.DataFrame({
                "Variable": nom,
                "Modalité": valeurs.index.tolist(),
                "Effectif": valeurs.values.tolist(),
            })
            for nom in variables_actives
            for valeurs in [preparation.donnees[nom].value_counts()]
        ],
        ignore_index=True,
    )
    st.dataframe(
        tableau_effectifs, use_container_width=True, hide_index=True
    )
    with st.expander("Afficher les observations conservées", expanded=False):
        st.dataframe(
            preparation.donnees.head(NOMBRE_LIGNES_APERCU),
            use_container_width=True, hide_index=True,
        )
    st.caption(
        f"Import : {preparation.effectif_initial} ; "
        f"après filtres : {preparation.effectif_apres_filtre} ; "
        f"après dédoublonnage : {preparation.effectif_apres_dedoublonnage} ; "
        f"avant exclusion des modalités : "
        f"{preparation.effectif_avant_exclusion_modalites} ; "
        f"observations conservées : {preparation.effectif_final}."
    )

    parametres = dict(
        portee,
        methode="ACM",
        methode_calcul=methode_calcul,
        modalites_exclues=preparation.modalites_exclues,
        effectif_initial=preparation.effectif_initial,
        effectif_avant_exclusion_modalites=(
            preparation.effectif_avant_exclusion_modalites
        ),
        effectif_analyse=preparation.effectif_final,
    )
    signature = hashlib.sha256(
        json.dumps(parametres, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    lancement_manuel = st.button(
        "Lancer l'ACM avec FactoMineR", type="primary"
    )
    if lancement_manuel or recalcul_automatique:
        try:
            with st.spinner(
                "Recalcul automatique de l'ACM avec FactoMineR..."
                if recalcul_automatique and not lancement_manuel
                else "Calcul de l'ACM avec FactoMineR..."
            ):
                resultats = executer_moteur_acm(
                    donnees=preparation.donnees,
                    nom_source=nom_source,
                    effectif_initial=preparation.effectif_initial,
                    effectif_final=preparation.effectif_final,
                    parametres=parametres,
                    methode_calcul=methode_calcul,
                    variables_supplementaires_qualitatives=(
                        variables_supplementaires_qualitatives
                    ),
                    variables_supplementaires_quantitatives=(
                        variables_supplementaires_quantitatives
                    ),
                )
        except (RuntimeError, OSError) as erreur:
            st.session_state.pop("dernier_resultat_acm", None)
            st.session_state.pop("signature_resultat_acm", None)
            st.error(str(erreur))
        else:
            st.session_state["dernier_resultat_acm"] = resultats
            st.session_state["signature_resultat_acm"] = signature
            st.success("ACM actualisée par FactoMineR. Résultats disponibles.")

    if "dernier_resultat_acm" in st.session_state:
        if st.session_state.get("signature_resultat_acm") == signature:
            afficher_resultats(
                st.session_state["dernier_resultat_acm"],
                methode="ACM", mode_acm=methode_calcul,
            )
        else:
            st.info(
                "Les paramètres de l'ACM ont changé. Relancer l'analyse "
                "pour actualiser les résultats."
            )

def construire_interface_afc(
    donnees: pd.DataFrame,
    contenu: bytes,
    nom_source: str,
    noms_variables: list[str],
    candidates: list[str],
) -> None:
    """Conserver l'interface AFC et tous ses filtres originaux."""
    st.subheader("2. Sélectionner les variables de l'AFC")
    defaut_lignes = candidates[0] if candidates else noms_variables[0]
    defaut_colonnes = candidates[1] if len(candidates) > 1 else noms_variables[min(1, len(noms_variables)-1)]
    col_lignes, col_colonnes = st.columns(2)
    with col_lignes:
        variable_lignes = st.selectbox(
            "Variable en lignes", noms_variables,
            index=choisir_defaut(noms_variables, "vues_classe", noms_variables.index(defaut_lignes)),
            help="Variable qualitative ou numérique préalablement recodée en classes.",
        )
    with col_colonnes:
        variable_colonnes = st.selectbox(
            "Variable en colonnes", noms_variables,
            index=choisir_defaut(noms_variables, "classe_taux_engagement", noms_variables.index(defaut_colonnes)),
            help="Choisir une autre variable qualitative que celle des lignes.",
        )

    st.subheader("3. Paramètres de préparation et de calcul")
    col_param, col_filtre = st.columns(2)
    with col_param:
        uniquement_retenues = st.checkbox(
            "Conserver uniquement les publications retenues",
            value="retenue" in donnees.columns,
            disabled="retenue" not in donnees.columns,
        )
        dedoublonner = st.checkbox(
            "Dédoublonner par publication_id (conserver la première occurrence)",
            value=False,
            disabled="publication_id" not in donnees.columns,
        )
        exclure_indeterminees = st.checkbox("Exclure les modalités indéterminées", value=True)
        inclure_manquantes = st.checkbox(
            "Conserver les valeurs manquantes comme une modalité distincte", value=False
        )
    with col_filtre:
        maximum_modalites = st.number_input(
            "Nombre maximal de modalités par variable", min_value=2, max_value=100,
            value=40, step=1,
        )
        options_filtre = ["(Aucun)"] + noms_variables
        variable_filtre_choisie = st.selectbox("Filtrer sur une variable (facultatif)", options_filtre)
        variable_filtre = None if variable_filtre_choisie == "(Aucun)" else variable_filtre_choisie
        modalites_filtre = None
        if variable_filtre:
            modalites = sorted(donnees[variable_filtre].unique().tolist())
            if len(modalites) > 300:
                st.error("Cette variable comporte plus de 300 valeurs. Choisir un filtre catégoriel.")
                return
            modalites_filtre = st.multiselect(
                "Modalités à conserver", options=modalites, default=modalites,
            )

    try:
        preparation_initiale = preparer_contingence(
            donnees=donnees,
            variable_lignes=variable_lignes,
            variable_colonnes=variable_colonnes,
            uniquement_retenues=uniquement_retenues,
            dedoublonner=dedoublonner,
            exclure_indeterminees=exclure_indeterminees,
            inclure_manquantes=inclure_manquantes,
            maximum_modalites=int(maximum_modalites),
            variable_filtre=variable_filtre,
            modalites_filtre=modalites_filtre,
        )
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    st.subheader("4. Vérifier et modifier le tableau de contingence")
    # Les exclusions concernent ce tableau, et non le fichier CSV importé.
    # Changer de corpus, de variables ou de filtres réinitialise la sélection.
    empreinte_csv = hashlib.sha256(contenu).hexdigest()
    portee_modalites = {
        "empreinte_csv": empreinte_csv,
        "variable_lignes": variable_lignes,
        "variable_colonnes": variable_colonnes,
        "uniquement_retenues": uniquement_retenues,
        "dedoublonner": dedoublonner,
        "exclure_indeterminees": exclure_indeterminees,
        "inclure_manquantes": inclure_manquantes,
        "maximum_modalites": int(maximum_modalites),
        "variable_filtre": variable_filtre,
        "modalites_filtre": sorted(modalites_filtre) if modalites_filtre is not None else None,
    }
    identifiant_portee = hashlib.sha256(
        json.dumps(portee_modalites, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("afc_portee_modalites") != identifiant_portee:
        st.session_state["afc_portee_modalites"] = identifiant_portee
        st.session_state["afc_lignes_exclues"] = []
        st.session_state["afc_colonnes_exclues"] = []
        st.session_state["afc_selection_exclusions_precedente"] = (
            identifiant_portee, (), ()
        )
    # Streamlit peut nettoyer les clés des widgets AFC lorsque le mode ACM
    # est sélectionné : conserver un retour à l'AFC sans erreur de session.
    st.session_state.setdefault("afc_lignes_exclues", [])
    st.session_state.setdefault("afc_colonnes_exclues", [])

    st.caption(
        "Supprimez une ou plusieurs modalités en lignes ou en colonnes, "
        "par exemple 'modalité_nontrouvé'. L'AFC FactoMineR, ses inerties, "
        "son plan et ses exports seront recalculés automatiquement après "
        "chaque modification. Le CSV importé reste intact."
    )
    if st.button(
        "Rétablir toutes les lignes et colonnes",
        disabled=not (
            st.session_state["afc_lignes_exclues"]
            or st.session_state["afc_colonnes_exclues"]
        ),
    ):
        st.session_state["afc_lignes_exclues"] = []
        st.session_state["afc_colonnes_exclues"] = []
        st.rerun()

    col_exclure_lignes, col_exclure_colonnes = st.columns(2)
    with col_exclure_lignes:
        lignes_exclues = st.multiselect(
            "Supprimer des lignes (modalités)",
            options=preparation_initiale.tableau.index.tolist(),
            key="afc_lignes_exclues",
            help="Les observations de ces modalités ne participeront plus à l'AFC.",
        )
    with col_exclure_colonnes:
        colonnes_exclues = st.multiselect(
            "Supprimer des colonnes (modalités)",
            options=preparation_initiale.tableau.columns.tolist(),
            key="afc_colonnes_exclues",
            help="Les observations de ces modalités ne participeront plus à l'AFC.",
        )

    selection_exclusions = (
        identifiant_portee, tuple(sorted(lignes_exclues)),
        tuple(sorted(colonnes_exclues)),
    )
    recalcul_automatique = (
        selection_exclusions
        != st.session_state.get("afc_selection_exclusions_precedente")
    )
    st.session_state["afc_selection_exclusions_precedente"] = selection_exclusions
    try:
        preparation = exclure_modalites_contingence(
            preparation_initiale, lignes_exclues, colonnes_exclues
        )
    except ValueError as erreur:
        st.warning(str(erreur))
        st.dataframe(preparation_initiale.tableau, use_container_width=True)
        return

    controles = st.columns(3)
    controles[0].metric("Observations analysables", preparation.effectif_final)
    controles[1].metric("Modalités en lignes", len(preparation.tableau.index))
    controles[2].metric("Modalités en colonnes", len(preparation.tableau.columns))
    if preparation.effectif_final < 30:
        st.warning("Effectif inférieur à 30 : interprétation exploratoire.")
    if min(preparation.tableau.shape) == 2:
        st.info("Le tableau ne comporte qu'un axe factoriel : aucun plan en deux dimensions n'est possible.")
    st.dataframe(preparation.tableau, use_container_width=True)
    if preparation.modalites_vides_lignes or preparation.modalites_vides_colonnes:
        st.info(
            "Les modalités devenues vides après exclusion ont également été "
            "retirées du tableau : "
            + ", ".join(
                list(preparation.modalites_vides_lignes)
                + list(preparation.modalites_vides_colonnes)
            )
            + "."
        )
    st.caption(
        f"Import : {preparation.effectif_initial} lignes ; "
        f"après filtres : {preparation.effectif_apres_filtre} ; "
        f"après dédoublonnage : {preparation.effectif_apres_dedoublonnage} ; "
        f"avant suppression des modalités : {preparation.effectif_avant_exclusion_modalites} ; "
        f"observations conservées pour l'AFC : {preparation.effectif_final}."
    )
    parametres = {
        "source": nom_source,
        "empreinte_sha256": empreinte_csv,
        "variable_lignes": variable_lignes,
        "variable_colonnes": variable_colonnes,
        "uniquement_retenues": uniquement_retenues,
        "dedoublonner": dedoublonner,
        "exclure_indeterminees": exclure_indeterminees,
        "inclure_manquantes": inclure_manquantes,
        "maximum_modalites": int(maximum_modalites),
        "variable_filtre": variable_filtre,
        "modalites_filtre": modalites_filtre,
        "effectif_initial": preparation.effectif_initial,
        "effectif_avant_exclusion_modalites": preparation.effectif_avant_exclusion_modalites,
        "modalites_exclues_lignes": list(preparation.modalites_exclues_lignes),
        "modalites_exclues_colonnes": list(preparation.modalites_exclues_colonnes),
        "modalites_vides_lignes": list(preparation.modalites_vides_lignes),
        "modalites_vides_colonnes": list(preparation.modalites_vides_colonnes),
        "effectif_analyse": preparation.effectif_final,
    }
    signature = hashlib.sha256(
        json.dumps(parametres, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    lancement_manuel = st.button("Lancer l'AFC avec FactoMineR", type="primary")
    if lancement_manuel or recalcul_automatique:
        try:
            with st.spinner(
                "Recalcul automatique de l'AFC avec FactoMineR..."
                if recalcul_automatique and not lancement_manuel
                else "Calcul de l'AFC dans R et préparation des graphiques..."
            ):
                resultats = executer_moteur_r(
                    tableau=preparation.tableau,
                    variable_lignes=variable_lignes,
                    variable_colonnes=variable_colonnes,
                    nom_source=nom_source,
                    effectif_initial=preparation.effectif_initial,
                    effectif_final=preparation.effectif_final,
                    parametres=parametres,
                )
        except (RuntimeError, OSError) as erreur:
            st.session_state.pop("dernier_resultat", None)
            st.session_state.pop("signature_resultat", None)
            st.error(str(erreur))
        else:
            st.session_state["dernier_resultat"] = resultats
            st.session_state["signature_resultat"] = signature
            st.success(
                "AFC recalculée automatiquement après la suppression de modalités."
                if recalcul_automatique and not lancement_manuel
                else "AFC calculée par FactoMineR. Les exports sont disponibles ci-dessous."
            )

    if "dernier_resultat" in st.session_state:
        if st.session_state.get("signature_resultat") == signature:
            afficher_resultats(st.session_state["dernier_resultat"], methode="AFC")
        else:
            st.info("Les paramètres ont changé depuis le dernier calcul. Relancer l'AFC pour actualiser les résultats.")


def construire_interface() -> None:
    """Importer un ou plusieurs CSV et proposer les analyses conservées."""
    st.title("Analyses des correspondances — FactoMineR")
    st.subheader("1. Importer un ou plusieurs fichiers CSV")
    colonne_choix, colonne_fichier = st.columns([1, 2])
    with colonne_choix:
        separateur = st.selectbox(
            "Séparateur", ["Automatique", "Point-virgule (;)", "Virgule (, )", "Tabulation", "Barre verticale (|)"],
        )
        encodage = st.selectbox("Encodage", ["Automatique", "UTF-8", "Windows-1252", "Latin-1"])
    with colonne_fichier:
        fichiers = st.file_uploader(
            "Fichiers CSV (un ou plusieurs)",
            type=["csv", "txt"],
            accept_multiple_files=True,
            help=(
                "Tous les fichiers doivent contenir les mêmes noms de colonnes. "
                "L'ordre des colonnes peut varier ; les lignes sont réunies "
                "sans dédoublonnage automatique."
            ),
        )

    if not fichiers:
        st.info("Importer un ou plusieurs fichiers CSV pour commencer l'analyse.")
        return

    # Conserver un suivi de chaque fichier et identifier sans ambiguïté le
    # corpus réuni pour la réinitialisation des paramètres AFC et ACM.
    tableaux_sources = []
    contenu_total = 0
    empreinte_import = hashlib.sha256()
    bilan_sources = []
    for fichier in fichiers:
        contenu_fichier = fichier.getvalue()
        try:
            tableau_source = importer_donnees(
                contenu_fichier, separateur, encodage
            )
        except (ValueError, UnicodeError) as erreur:
            st.error(f"Erreur dans '{fichier.name}' : {erreur}")
            return
        tableaux_sources.append((fichier.name, tableau_source))
        contenu_total += len(contenu_fichier)
        bilan_sources.append({
            "Fichier": fichier.name,
            "Observations": len(tableau_source),
            "Variables": len(tableau_source.columns),
            "Taille (Mo)": round(len(contenu_fichier) / (1024**2), 3),
        })
        nom_octets = fichier.name.encode("utf-8")
        empreinte_import.update(len(nom_octets).to_bytes(8, "big"))
        empreinte_import.update(nom_octets)
        empreinte_import.update(len(contenu_fichier).to_bytes(8, "big"))
        empreinte_import.update(contenu_fichier)

    try:
        donnees = concatener_fichiers_csv(tableaux_sources)
    except ValueError as erreur:
        st.error(str(erreur))
        return

    # Les deux interfaces factorielles se servent de 'contenu' uniquement
    # pour calculer la signature du corpus. L'empreinte évite de reproduire
    # intégralement le CSV concaténé à chaque interaction Streamlit.
    contenu = (
        fichiers[0].getvalue() if len(fichiers) == 1
        else empreinte_import.digest()
    )
    nom_source = (
        fichiers[0].name if len(fichiers) == 1
        else f"Fusion de {len(fichiers)} CSV : "
        + " ; ".join(fichier.name for fichier in fichiers)
    )

    mesures = st.columns(4 if len(fichiers) > 1 else 3)
    mesures[0].metric(
        "Observations importées", f"{len(donnees):,}".replace(",", " ")
    )
    mesures[1].metric("Variables disponibles", len(donnees.columns))
    mesures[2].metric("Taille totale", f"{contenu_total / (1024**2):.2f} Mo")
    if len(fichiers) > 1:
        mesures[3].metric("Fichiers réunis", len(fichiers))
        st.caption(
            "Les observations ont été concaténées dans l'ordre des fichiers. "
            "Les colonnes ont été alignées par leur nom. Les doublons "
            "éventuels sont conservés ; les options de dédoublonnage "
            "restent disponibles dans les analyses."
        )
        with st.expander("Détail des fichiers importés", expanded=False):
            st.dataframe(
                pd.DataFrame(bilan_sources),
                use_container_width=True, hide_index=True,
            )
        st.download_button(
            "Télécharger le corpus fusionné (CSV)",
            data=donnees.to_csv(
                index=False, sep=";", encoding="utf-8",
                lineterminator="\n",
            ).encode("utf-8-sig"),
            file_name="corpus_csv_fusionne.csv",
            mime="text/csv",
            key="telecharger_corpus_fusionne",
        )
    with st.expander("Aperçu des données et inventaire des variables", expanded=False):
        st.dataframe(donnees.head(NOMBRE_LIGNES_APERCU), use_container_width=True)
        st.caption("Le diagnostic des variables sert uniquement à aider la sélection ; il ne recode pas les valeurs.")
        st.dataframe(decrire_variables(donnees), use_container_width=True, hide_index=True)

    noms_variables = list(donnees.columns)
    variables_adaptees = decrire_variables(donnees)
    candidates = variables_adaptees.loc[
        variables_adaptees["Diagnostic"].eq("Catégorielle possible"), "Variable"
    ].tolist()

    onglet_descriptif, onglet_factoriel = st.tabs(
        ["Statistique descriptive", "AFC / ACM"]
    )
    with onglet_descriptif:
        construire_onglet_statistique_descriptive(donnees)

    with onglet_factoriel:
        methode = st.radio(
            "Méthode d'analyse",
            options=["AFC", "ACM"],
            horizontal=True,
            help=(
                "AFC : croisement de deux variables qualitatives. "
                "ACM : analyse simultanée de trois variables qualitatives ou davantage."
            ),
        )
        if methode == "AFC":
            st.caption(
                "AFC avec FactoMineR::CA() : deux variables catégorielles croisées."
            )
        else:
            st.caption(
                "ACM avec FactoMineR::MCA() : choisir le tableau disjonctif "
                "complet (TDC) ou le tableau de Burt pour plusieurs variables "
                "catégorielles analysées simultanément."
            )
        if methode == "ACM":
            construire_interface_acm(
                donnees, contenu, nom_source, noms_variables, candidates
            )
        else:
            construire_interface_afc(
                donnees, contenu, nom_source, noms_variables, candidates
            )



if __name__ == "__main__":
    construire_interface()
