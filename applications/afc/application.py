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

from traitement_csv import decrire_variables, lire_csv, preparer_contingence, preparer_tableau_inerties


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


def executer_moteur_r(
    tableau: pd.DataFrame,
    repetitions: int,
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
            str(repetitions),
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
                "Réduire le nombre de modalités ou les simulations Monte-Carlo."
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


def afficher_resultats(resultats: dict) -> None:
    """Présente les graphiques, mesures et exports calculés par R."""
    fichiers = resultats["fichiers"]
    st.subheader("Résultats de l'AFC")
    st.download_button(
        "Télécharger tous les résultats (ZIP)",
        data=resultats["archive"],
        file_name="resultats_afc_factominer.zip",
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
    indicateurs[1].metric("Chi-deux", valeurs.get("Chi-deux de Pearson", "—"))
    indicateurs[2].metric("Valeur p", valeurs.get("Valeur p", "—"))
    indicateurs[3].metric("V de Cramér", valeurs.get("V de Cramér", "—"))
    st.caption(valeurs.get("Méthode du test", ""))

    onglet_plan, onglet_inertie, onglet_matrices, onglet_rapport = st.tabs(
        ["Plan factoriel", "Inerties", "Tableaux", "Rapport méthodologique"]
    )
    with onglet_plan:
        st.image(fichiers["13_plan_factoriel.png"], use_container_width=True)
        st.caption(
            "Sur un plan à deux axes, seules les modalités associées "
            "significativement à au moins une modalité de l'autre variable "
            "(p ≤ 0,05) sont affichées. Les associations sont déterminées "
            "exclusivement par FactoMineR::descfreq (test hypergéométrique), "
            "et non par un test de position sur les axes."
        )
        st.caption(
            "Les coordonnées, contributions et cos² de toutes les modalités "
            "restent disponibles dans les tableaux CSV. Le fichier "
            "significativite_modalites_factominer.csv récapitule les "
            "associations significatives identifiées par FactoMineR. "
            "Sur un plan à un seul axe, le filtrage n'est pas appliqué."
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
        st.caption(
            "Les pourcentages et les inerties cumulées proviennent "
            "directement des valeurs propres calculées par FactoMineR::CA()."
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
        st.text(fichiers["00_rapport_afc.txt"].decode("utf-8"))


def construire_interface() -> None:
    """Présente les paramètres de l'analyse et déclenche le calcul sur demande."""
    st.title("Analyse factorielle des correspondances")
    st.caption("AFC calculée par FactoMineR (R) — import CSV, sélection des variables et export des résultats")
    st.markdown(
        "Chaque ligne du CSV représente une observation. L'application construit un tableau "
        "de contingence en croisant **deux variables catégorielles** que vous choisissez."
    )

    st.subheader("1. Importer le fichier CSV")
    colonne_choix, colonne_fichier = st.columns([1, 2])
    with colonne_choix:
        separateur = st.selectbox(
            "Séparateur", ["Automatique", "Point-virgule (;)", "Virgule (, )", "Tabulation", "Barre verticale (|)"],
        )
        encodage = st.selectbox("Encodage", ["Automatique", "UTF-8", "Windows-1252", "Latin-1"])
    with colonne_fichier:
        fichier = st.file_uploader("Fichier CSV", type=["csv", "txt"], accept_multiple_files=False)
        st.caption("Les identifiants sont lus comme du texte ; les résultats ne sont pas enregistrés en base.")

    if fichier is None:
        st.info("Importer un fichier CSV pour commencer l'analyse.")
        return

    contenu = fichier.getvalue()
    nom_source = fichier.name
    try:
        donnees = importer_donnees(contenu, separateur, encodage)
    except (ValueError, UnicodeError) as erreur:
        st.error(str(erreur))
        return

    mesures = st.columns(3)
    mesures[0].metric("Observations importées", f"{len(donnees):,}".replace(",", " "))
    mesures[1].metric("Variables disponibles", len(donnees.columns))
    mesures[2].metric("Taille du fichier", f"{len(contenu) / (1024**2):.2f} Mo")
    with st.expander("Aperçu des données et inventaire des variables", expanded=False):
        st.dataframe(donnees.head(NOMBRE_LIGNES_APERCU), use_container_width=True)
        st.caption("Le diagnostic des variables sert uniquement à aider la sélection ; il ne recode pas les valeurs.")
        st.dataframe(decrire_variables(donnees), use_container_width=True, hide_index=True)

    st.subheader("2. Sélectionner les variables de l'AFC")
    noms_variables = list(donnees.columns)
    variables_adaptees = decrire_variables(donnees)
    candidates = variables_adaptees.loc[
        variables_adaptees["Diagnostic"].eq("Catégorielle possible"), "Variable"
    ].tolist()
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
        repetitions = st.number_input(
            "Répétitions Monte-Carlo si effectifs théoriques faibles",
            min_value=999, max_value=19999, value=1999, step=1000,
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
        preparation = preparer_contingence(
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

    st.subheader("4. Vérifier le tableau avant l'AFC")
    controles = st.columns(4)
    controles[0].metric("Observations analysables", preparation.effectif_final)
    controles[1].metric("Modalités en lignes", len(preparation.tableau.index))
    controles[2].metric("Modalités en colonnes", len(preparation.tableau.columns))
    controles[3].metric("Cellules attendues < 5", preparation.cellules_attendues_faibles)
    if preparation.effectif_final < 30:
        st.warning("Effectif inférieur à 30 : résultats exploratoires, non concluants statistiquement.")
    if preparation.cellules_attendues_faibles:
        st.info("Des effectifs attendus sont inférieurs à 5 ; le test Chi-deux utilisera une estimation Monte-Carlo.")
    if min(preparation.tableau.shape) == 2:
        st.info("Le tableau ne comporte qu'un axe factoriel : aucun plan en deux dimensions n'est possible.")
    st.dataframe(preparation.tableau, use_container_width=True)
    st.caption(
        f"Import : {preparation.effectif_initial} lignes ; "
        f"après filtres : {preparation.effectif_apres_filtre} ; "
        f"après dédoublonnage : {preparation.effectif_apres_dedoublonnage} ; "
        f"après exclusion des valeurs inutilisables : {preparation.effectif_final}."
    )
    if preparation.inertie_nulle:
        st.warning("Le tableau présente une indépendance parfaite : aucune inertie à représenter.")
        return

    parametres = {
        "source": nom_source,
        "empreinte_sha256": hashlib.sha256(contenu).hexdigest(),
        "variable_lignes": variable_lignes,
        "variable_colonnes": variable_colonnes,
        "uniquement_retenues": uniquement_retenues,
        "dedoublonner": dedoublonner,
        "exclure_indeterminees": exclure_indeterminees,
        "inclure_manquantes": inclure_manquantes,
        "maximum_modalites": int(maximum_modalites),
        "repetitions_monte_carlo": int(repetitions),
        "variable_filtre": variable_filtre,
        "modalites_filtre": modalites_filtre,
        "effectif_initial": preparation.effectif_initial,
        "effectif_analyse": preparation.effectif_final,
    }
    signature = hashlib.sha256(
        json.dumps(parametres, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if st.button("Lancer l'AFC avec FactoMineR", type="primary"):
        try:
            with st.spinner("Calcul de l'AFC dans R et préparation des graphiques..."):
                resultats = executer_moteur_r(
                    tableau=preparation.tableau,
                    repetitions=int(repetitions),
                    variable_lignes=variable_lignes,
                    variable_colonnes=variable_colonnes,
                    nom_source=nom_source,
                    effectif_initial=preparation.effectif_initial,
                    effectif_final=preparation.effectif_final,
                    parametres=parametres,
                )
        except (RuntimeError, OSError) as erreur:
            st.error(str(erreur))
        else:
            st.session_state["dernier_resultat"] = resultats
            st.session_state["signature_resultat"] = signature
            st.success("AFC calculée par FactoMineR. Les exports sont disponibles ci-dessous.")

    if "dernier_resultat" in st.session_state:
        if st.session_state.get("signature_resultat") == signature:
            afficher_resultats(st.session_state["dernier_resultat"])
        else:
            st.info("Les paramètres ont changé depuis le dernier calcul. Relancer l'AFC pour actualiser les résultats.")

    st.caption(
        "Précaution méthodologique : l'AFC est descriptive et ne permet pas d'inférer "
        "une causalité. Les annotations de violence doivent provenir de données explicites."
    )


if __name__ == "__main__":
    construire_interface()
