"""Interface Streamlit en français pour l'AFC FactoMineR sur fichiers CSV."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ticket_gate import enforce_streamlit_access

from traitement_csv import (
    concatener_fichiers_csv, decrire_variables,
    lire_csv, preparer_acm,
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

# Appliquer les styles sans ajouter de bloc vide avant le titre principal.
st.html(
    """
    <style>
    [data-testid="stApp"] h1,
    [data-testid="stApp"] h2,
    [data-testid="stApp"] h3 {
        color: #C62828 !important;
    }
    /* Supprimer entièrement la marge et le retrait supérieurs du contenu. */
    [data-testid="stMainBlockContainer"],
    [data-testid="stMain"] .block-container,
    .stMainBlockContainer {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    </style>
    """
)



def afficher_plan_zoomable(image_png: bytes, cle_graphique: str) -> None:
    """Afficher le PNG de FactoMineR avec zoom, déplacement et réinitialisation."""
    if not image_png.startswith(b"\x89PNG\r\n\x1a\n") or len(image_png) < 24:
        st.image(image_png, use_container_width=True)
        return

    largeur, hauteur = struct.unpack(">II", image_png[16:24])
    if largeur <= 0 or hauteur <= 0:
        st.image(image_png, use_container_width=True)
        return

    # Charger Plotly seulement lorsqu’un résultat factoriel doit être affiché.
    import plotly.graph_objects as go

    source = "data:image/png;base64," + base64.b64encode(image_png).decode("ascii")
    figure = go.Figure()
    # Une trace transparente rend la zone graphique interactive pour le zoom.
    figure.add_trace(
        go.Scatter(
            x=[0, largeur],
            y=[0, hauteur],
            mode="markers",
            marker=dict(size=1, opacity=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_layout_image(
        source=source,
        xref="x",
        yref="y",
        x=0,
        y=hauteur,
        sizex=largeur,
        sizey=hauteur,
        sizing="stretch",
        layer="below",
    )
    figure.update_xaxes(visible=False, range=[0, largeur], constrain="domain")
    figure.update_yaxes(
        visible=False,
        range=[0, hauteur],
        scaleanchor="x",
        scaleratio=1,
    )
    figure.update_layout(
        height=max(450, min(850, round(hauteur * 0.8))),
        margin=dict(l=0, r=0, t=0, b=0),
        dragmode="zoom",
    )
    # Permettre le zoom direct à la molette sans piéger le défilement de la page.
    zoom_molette = st.checkbox(
        "Activer le zoom à la molette (décocher pour faire défiler la page)",
        value=True,
        key=f"{cle_graphique}_zoom_molette",
    )
    # Réinitialiser explicitement la figure sans relancer FactoMineR.
    cle_reset = f"{cle_graphique}_numero_reinitialisation"
    if st.button("Réinitialiser le zoom", key=f"{cle_graphique}_bouton_reset"):
        st.session_state[cle_reset] = st.session_state.get(cle_reset, 0) + 1
    numero_reset = st.session_state.get(cle_reset, 0)
    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "scrollZoom": zoom_molette,
            "displaylogo": False,
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["zoom2d", "pan2d", "resetScale2d"],
        },
        key=f"{cle_graphique}_{numero_reset}",
    )
    st.caption(
        "Zoomer avec la molette ou sélectionner une zone en maintenant le clic "
        "gauche de la souris. Pour faire défiler la page avec la molette, "
        "décocher « Activer le zoom à la molette ». "
        "« Réinitialiser le zoom » rétablit le plan entier. "
        "En plein écran, utiliser l'icône de réduction en haut à droite."
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
            "06_valeurs_propres_inerties.csv",
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
    # Arrondir seulement l'affichage du score, sans modifier les valeurs R.
    inertie_totale_brute = valeurs.get("Inertie totale (FactoMineR)", "—")
    try:
        inertie_totale_affichee = (
            f"{float(inertie_totale_brute.replace(',', '.').replace(' ', '')):.6f}"
            .replace(".", ",")
        )
    except (ValueError, AttributeError):
        inertie_totale_affichee = inertie_totale_brute
    indicateurs[3].metric("Inertie totale", inertie_totale_affichee)
    if methode == "AFC":
        st.caption(
            "Résultats issus de FactoMineR::CA() et FactoMineR::descfreq(). "
            "Les coordonnées et les inerties proviennent directement de FactoMineR::CA()."
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

    onglet_plan, onglet_inertie, onglet_matrices = st.tabs(
        ["Plan factoriel", "Inerties", "Tableaux"]
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
        mode_taille = st.radio(
            "Taille des modalités",
            options=[
                "Taille uniforme",
                "Taille proportionnelle aux effectifs",
            ],
            index=0,
            key=f"{methode.lower()}_mode_taille_modalites",
            help=(
                "La taille des symboles est uniforme par défaut. "
                "En mode proportionnel, la surface reflète les effectifs "
                "marginaux du tableau de contingence pour l'AFC, ou "
                "les effectifs observés des modalités actives pour l'ACM. "
                "Les calculs FactoMineR restent inchangés."
            ),
        )
        nom_graphique = (
            "13_plan_factoriel_significatif" if filtrer_modalites
            else "13_plan_factoriel"
        )
        if mode_taille == "Taille proportionnelle aux effectifs":
            nom_graphique += "_proportionnel"
        nom_graphique += ".png"
        afficher_plan_zoomable(
            fichiers[nom_graphique],
            cle_graphique=f"plan_{methode.lower()}_zoomable",
        )
        if methode == "ACM":
            # Conserver la projection supplémentaire et l'alerte statistique,
            # sans afficher de paragraphe explicatif sous le plan ACM.
            if "26_plan_quantitatives_supplementaires.png" in fichiers:
                st.subheader("Projection des variables supplémentaires")
                afficher_plan_zoomable(
                    fichiers["26_plan_quantitatives_supplementaires.png"],
                    cle_graphique="plan_acm_quantitatives_zoomable",
                )
            nom_significativite = "significativite_modalites_factominer.csv"
            significativites = pd.read_csv(
                io.BytesIO(fichiers[nom_significativite]),
                sep=";", decimal=",", encoding="utf-8",
                low_memory=False,
            )
            p_values = pd.to_numeric(
                significativites["p_value_min"], errors="coerce"
            )
            if int(p_values.le(0.05).sum()) == 0:
                st.warning(
                    "Aucune modalité n'atteint p ≤ 0,05 sur les axes "
                    "représentés. Le plan complet reste accessible."
                )
        else:
            # Conserver les explications du plan factoriel de l'AFC.
            textes_plan = [
                "Plan complet : toutes les modalités actives."
                if not filtrer_modalites
                else (
                    "Plan filtré : modalités associées significativement à une "
                    "autre modalité selon FactoMineR::descfreq (AFC)."
                ),
                "Cette case ne modifie pas le calcul factoriel. "
                "Les deux graphiques sont disponibles dans le ZIP. "
                "Lorsque l'analyse ne comporte qu'un axe, le filtre n'est pas appliqué.",
            ]
            st.caption(" ".join(textes_plan))

    with onglet_inertie:
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
            "01_donnees_acm_filtrees.csv",
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
    st.caption(
        "L'ACM s'effectue exclusivement sur des variables qualitatives "
        "(catégorielles). Les variables numériques doivent être préalablement "
        "recodées en classes pour être utilisées comme variables actives."
    )
    # Proposer directement les seules variables catégorielles admissibles.
    # Aucune variable n'est présélectionnée dans le menu multisélection.
    descriptions_acm = decrire_variables(donnees)
    variables_autorisees = descriptions_acm.loc[
        descriptions_acm["Diagnostic"].eq("Catégorielle possible"), "Variable"
    ].tolist()

    # Vider la sélection si le corpus change et écarter les anciennes
    # variables devenues inadmissibles après un nouvel import.
    empreinte_selection = hashlib.sha256(contenu).hexdigest()
    if st.session_state.get("acm_empreinte_selection") != empreinte_selection:
        st.session_state["acm_empreinte_selection"] = empreinte_selection
        st.session_state["acm_variables_actives"] = []
    elif "acm_variables_actives" in st.session_state:
        st.session_state["acm_variables_actives"] = [
            nom for nom in st.session_state["acm_variables_actives"]
            if nom in variables_autorisees
        ]

    variables_actives = st.multiselect(
        "Variables qualitatives (catégorielles) actives — trois au minimum",
        options=variables_autorisees,
        default=[],
        placeholder="Sélectionner au moins trois variables catégorielles",
        key="acm_variables_actives",
        help=(
            "Seules les variables catégorielles admissibles du CSV figurent "
            "dans cette liste. Aucune variable n'est présélectionnée."
        ),
    )
    if len(variables_actives) < 3:
        st.info("Sélectionnez au moins trois variables pour l'ACM.")
        return

    st.caption(
        "Choisissez une ou plusieurs variables à projeter sur l'ACM "
        "sans modifier les axes."
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
    variables_supplementaires_quantitatives = [
        nom for nom in variables_supplementaires
        if nom in candidats_numeriques
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
    col_param, col_options = st.columns(2)
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
    with col_options:
        exclure_indeterminees = st.checkbox(
            "Exclure les modalités indéterminées", value=True
        )
        inclure_manquantes = st.checkbox(
            "Conserver les valeurs manquantes comme une modalité distincte",
            value=False,
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
    )
    try:
        preparation_initiale = preparer_acm(**options_preparation)
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    # Préparer l'ACM directement avec les variables et les filtres retenus.
    # La sélection et l'exclusion manuelles des modalités sont supprimées.
    preparation = preparation_initiale
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
            },
    }

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
    if lancement_manuel:
        try:
            with st.spinner("Calcul de l'ACM avec FactoMineR..."):
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
    col_param, col_options = st.columns(2)
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
    with col_options:
        exclure_indeterminees = st.checkbox("Exclure les modalités indéterminées", value=True)
        inclure_manquantes = st.checkbox(
            "Conserver les valeurs manquantes comme une modalité distincte", value=False
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
            )
    except ValueError as erreur:
        st.warning(str(erreur))
        return

    # Utiliser directement le tableau préparé sans modification manuelle.
    preparation = preparation_initiale
    empreinte_csv = hashlib.sha256(contenu).hexdigest()
    parametres = {
        "source": nom_source,
        "empreinte_sha256": empreinte_csv,
        "variable_lignes": variable_lignes,
        "variable_colonnes": variable_colonnes,
        "uniquement_retenues": uniquement_retenues,
        "dedoublonner": dedoublonner,
        "exclure_indeterminees": exclure_indeterminees,
        "inclure_manquantes": inclure_manquantes,
        "effectif_initial": preparation.effectif_initial,
        "effectif_avant_exclusion_modalites": preparation.effectif_final,
        "modalites_exclues_lignes": [],
        "modalites_exclues_colonnes": [],
        "modalites_vides_lignes": [],
        "modalites_vides_colonnes": [],
        "effectif_analyse": preparation.effectif_final,
    }
    signature = hashlib.sha256(
        json.dumps(parametres, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    lancement_manuel = st.button("Lancer l'AFC avec FactoMineR", type="primary")
    if lancement_manuel:
        try:
            with st.spinner("Calcul de l'AFC dans R et préparation des graphiques..."):
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
            st.success("AFC calculée par FactoMineR. Les exports sont disponibles ci-dessous.")

    if "dernier_resultat" in st.session_state:
        if st.session_state.get("signature_resultat") == signature:
            afficher_resultats(st.session_state["dernier_resultat"], methode="AFC")
        else:
            st.info("Les paramètres ont changé depuis le dernier calcul. Relancer l'AFC pour actualiser les résultats.")


def construire_interface() -> None:
    """Importer un ou plusieurs CSV et proposer les analyses conservées."""
    # Vérifier l’accès à la session avant toute analyse et afficher sa libération.
    enforce_streamlit_access("afc", "AFC/ACM")
    st.title("Analyses Factorielles des Correspondances — FactoMineR")
    st.caption("version 0.1 - 17-11-2026")
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

    st.subheader("2. Méthode d'analyse")
    methode = st.radio(
        "Méthode d'analyse",
        options=["AFC", "ACM"],
        horizontal=True,
        label_visibility="collapsed",
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
