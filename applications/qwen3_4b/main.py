"""Application Streamlit Qwen3-4B : prompt libre et codage structuré optionnel."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import zipfile
from dataclasses import replace

import pandas as pd
import requests
import streamlit as st

from codage_qwen import (
    CHAMPS_BOOLEENS,
    MODELE,
    PROMPT_LIBRE_DEFAUT,
    PROMPT_VIOLENCE_DEFAUT,
    URL_OLLAMA,
    coder_commentaire,
    verifier_service,
)
from lecture_commentaires import analyser_commentaires_csv, lister_colonnes_csv
from lecture_iramuteq import (
    analyser_corpus,
    exporter_csv,
    exporter_iramuteq,
    tableau_documents,
)

st.set_page_config(page_title="Qwen3-4B — analyse de corpus", layout="wide")


def authentifier() -> None:
    """Empêcher l'accès non autorisé à l'inférence sur le VPS."""
    secret = os.getenv("APP_PASSWORD", "")
    if not secret:
        if os.getenv("APP_ALLOW_PUBLIC", "0") != "1":
            st.error("Définir APP_PASSWORD dans Coolify avant de lancer l'application.")
            st.stop()
        st.warning("Mode public activé explicitement par APP_ALLOW_PUBLIC=1.")
        return
    saisie = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(saisie.encode("utf-8"), secret.encode("utf-8")):
        st.stop()


def est_vrai(valeur: object) -> bool:
    """Lire des booléens provenant de l'interface ou d'un CSV de reprise."""
    if pd.isna(valeur):
        return False
    if isinstance(valeur, str):
        return valeur.strip().lower() in ("true", "vrai", "1", "oui")
    return bool(valeur)


def categorie_document(ligne, mode_analyse: str) -> str:
    """Conserver les anciennes catégories, ou signaler une analyse libre."""
    if ligne.statut_codage != "ok":
        return "indetermine"
    if mode_analyse == "libre":
        return "analyse_libre"
    if est_vrai(ligne.interpretation_indeterminee):
        return "indetermine"
    if est_vrai(ligne.violence_justifiee) and est_vrai(ligne.violence_denoncee):
        return "ambivalent"
    if est_vrai(ligne.violence_justifiee):
        return "justification"
    if est_vrai(ligne.violence_denoncee):
        return "denonciation"
    if est_vrai(ligne.violence_minimisee):
        return "minimisation"
    if est_vrai(ligne.violence_evoquee):
        return "evocation"
    return "hors_violence"


def archive_resultats(
    tableau: pd.DataFrame,
    documents,
    signature: str,
    parametres: dict[str, object],
) -> bytes:
    """Créer une archive ZIP unique incluant toutes les lignes et le prompt."""
    mode_analyse = str(parametres["mode_analyse"])
    categories = {
        int(ligne.numero_document): categorie_document(ligne, mode_analyse)
        for ligne in tableau.itertuples(index=False)
    }
    texte = exporter_iramuteq(documents, categories, "qwen_position")
    colonnes_reponses = [
        "numero_document", "nom_affiche", "texte", "fichier_source",
        "ligne_csv", "colonne_texte_source", "colonne_auteur_source",
        "reponse_qwen", "statut_codage", "erreur_codage", "mode_analyse",
    ]
    reponses = tableau[[col for col in colonnes_reponses if col in tableau]].copy()
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("codage_commentaires.csv", exporter_csv(tableau))
        archive.writestr("reponses_qwen.csv", exporter_csv(reponses))
        archive.writestr("corpus_qwen_iramuteq.txt", texte)
        archive.writestr(
            "parametres.json",
            json.dumps(
                {**parametres, "signature": signature},
                ensure_ascii=False, indent=2,
            ),
        )
    return tampon.getvalue()


def initialiser_tableau(
    tableau: pd.DataFrame,
    signature: str,
    cle_configuration: str = "",
) -> pd.DataFrame:
    """Initialiser les résultats en conservant les textes et les métadonnées."""
    donnees = tableau.copy().reset_index(drop=True)
    donnees["signature_corpus"] = signature
    donnees["cle_configuration"] = cle_configuration
    donnees["statut_codage"] = "non_traite"
    for champ in CHAMPS_BOOLEENS:
        donnees[champ] = pd.Series(
            [pd.NA] * len(donnees), index=donnees.index, dtype="boolean"
        )
    for champ in (
        "acteur_cible", "indice_textuel", "justification",
        "erreur_codage", "reponse_qwen", "mode_analyse",
    ):
        donnees[champ] = ""
    for champ in ("texte_tronque", "contexte_tronque"):
        donnees[champ] = pd.Series(
            [pd.NA] * len(donnees), index=donnees.index, dtype="boolean"
        )
    donnees.loc[
        donnees["texte"].fillna("").astype(str).str.strip().eq(""),
        "statut_codage",
    ] = "vide"
    return donnees


def restaurer_checkpoint(
    donnees: pd.DataFrame,
    anciens: pd.DataFrame,
    signature: str,
    cle_configuration: str,
    autoriser_ancien_format: bool = False,
) -> pd.DataFrame:
    """Restaurer sans mélanger les corpus et les prompts différents."""
    colonnes_indispensables = (
        "numero_document", "signature_corpus", "texte", "statut_codage"
    )
    if any(col not in anciens.columns for col in colonnes_indispensables):
        raise ValueError("Colonnes de reprise incomplètes.")
    if (
        len(anciens) != len(donnees)
        or anciens["signature_corpus"].nunique() != 1
        or anciens["signature_corpus"].iloc[0] != signature
        or not anciens["numero_document"].equals(donnees["numero_document"])
        or not anciens["texte"].fillna("").equals(donnees["texte"].fillna(""))
    ):
        raise ValueError("Le CSV de reprise ne correspond pas au corpus actuel.")

    if "cle_configuration" in anciens.columns:
        if (
            anciens["cle_configuration"].nunique() != 1
            or anciens["cle_configuration"].iloc[0] != cle_configuration
        ):
            raise ValueError(
                "Le prompt, le mode ou les paramètres diffèrent de ceux de la reprise."
            )
    elif not autoriser_ancien_format:
        raise ValueError(
            "Cet ancien CSV n'enregistre pas le prompt utilisé. "
            "Reprise autorisée seulement avec la grille structurée historique."
        )

    restauration = donnees.copy()
    champs_restaurables = (
        "statut_codage", *CHAMPS_BOOLEENS,
        "acteur_cible", "indice_textuel", "justification",
        "erreur_codage", "texte_tronque", "contexte_tronque",
        "reponse_qwen", "mode_analyse",
    )
    for champ in champs_restaurables:
        if champ in anciens.columns:
            valeurs = anciens[champ].reset_index(drop=True)
            if champ in (*CHAMPS_BOOLEENS, "texte_tronque", "contexte_tronque"):
                def convertir_booleen(valeur):
                    if pd.isna(valeur) or str(valeur).strip() == "":
                        return pd.NA
                    return est_vrai(valeur)
                restauration[champ] = pd.Series(
                    [convertir_booleen(v) for v in valeurs], dtype="boolean"
                )
            elif champ in (
                "acteur_cible", "indice_textuel", "justification",
                "erreur_codage", "reponse_qwen", "mode_analyse",
            ):
                restauration[champ] = valeurs.fillna("").astype(str)
            else:
                restauration[champ] = valeurs
    return restauration


def lancer_analyse(
    donnees: pd.DataFrame,
    indices: list[int],
    mode_analyse: str,
    prompt: str,
    contexte_general: str,
    contexte_variables: list[str],
    temperature: float,
) -> tuple[int, int, bool]:
    """Analyser automatiquement toutes les lignes sélectionnées, sans lots visibles."""
    nombre_total = len(indices)
    barre = st.progress(0, text="Préparation de l'analyse")
    information = st.empty()
    termines = 0
    erreurs = 0
    erreurs_consecutives = 0
    interruption_service = False

    with requests.Session() as session:
        for position, indice in enumerate(indices, start=1):
            ligne = donnees.loc[indice]
            details = "\n".join(
                f"{colonne}: {ligne[colonne]}"
                for colonne in contexte_variables
                if pd.notna(ligne.get(colonne))
            )
            contexte = (contexte_general + "\n" + details).strip()
            try:
                resultat = coder_commentaire(
                    texte=str(ligne["texte"]),
                    contexte=contexte,
                    temperature=temperature,
                    session=session,
                    consigne=prompt,
                    mode_analyse=mode_analyse,
                )
                for champ, valeur in resultat.items():
                    donnees.at[indice, champ] = valeur
                donnees.at[indice, "statut_codage"] = "ok"
                donnees.at[indice, "erreur_codage"] = ""
                termines += 1
                erreurs_consecutives = 0
            except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError) as erreur:
                type_erreur = (
                    "erreur_service" if isinstance(erreur, requests.RequestException)
                    else "sortie_invalide"
                )
                donnees.at[indice, "statut_codage"] = type_erreur
                donnees.at[indice, "erreur_codage"] = (
                    f"{type(erreur).__name__}: {str(erreur)[:300]}"
                )
                erreurs += 1
                # Interrompre immédiatement si le système a tué le moteur d'inférence.
                erreurs_consecutives = (
                    3 if (
                        "signal: killed" in str(erreur).lower()
                        or "unexpected eof" in str(erreur).lower()
                    ) else erreurs_consecutives + 1
                )
            barre.progress(
                round(position * 100 / max(1, nombre_total)),
                text=f"Commentaires examinés : {position} / {nombre_total}",
            )
            information.caption(
                f"Analyses abouties : {termines} ; erreurs : {erreurs}. "
                "Les résultats déjà obtenus sont conservés dans la session."
            )
            st.session_state["qwen_donnees"] = donnees
            if erreurs_consecutives >= 3:
                interruption_service = True
                break
    barre.empty()
    information.empty()
    return termines, erreurs, interruption_service


authentifier()

st.title("Qwen3-4B — analyser un corpus avec votre prompt")
st.caption(
    "Qwen fonctionne avec vos consignes. Le modèle traite chaque commentaire "
    "séparément et conserve le texte original."
)
mode_affichage = st.radio(
    "Type d'analyse",
    ["Analyse libre avec mon prompt", "Codage structuré sur la violence"],
    horizontal=True,
    help=(
        "L'analyse libre produit une réponse textuelle pour chaque commentaire. "
        "Le codage structuré conserve les catégories binaires historiques."
    ),
)
mode_analyse = "libre" if mode_affichage.startswith("Analyse libre") else "structure"
prompt = st.text_area(
    "Prompt à transmettre à Qwen pour chaque commentaire",
    value=(
        PROMPT_LIBRE_DEFAUT if mode_analyse == "libre"
        else PROMPT_VIOLENCE_DEFAUT
    ),
    key=f"qwen_prompt_{mode_analyse}",
    height=230,
    help=(
        "Modifiez librement les instructions. En mode structuré, "
        "les colonnes de codage restent fixes ; en mode libre, "
        "la réponse du modèle est conservée dans reponse_qwen."
    ),
)
if mode_analyse == "structure":
    st.info(
        "Le mode structuré conserve les colonnes historiques "
        "violence_evoquee, violence_denoncee, violence_justifiee, "
        "violence_minimisee et interpretation_indeterminee. "
        "Pour toute autre grille de lecture, choisissez Analyse libre."
    )
if not prompt.strip():
    st.error("Vous devez saisir un prompt avant de lancer l'analyse.")

fichiers = st.file_uploader(
    "Importer un ou plusieurs fichiers : commentaires CSV ou corpus IRaMuTeQ TXT",
    type=["csv", "txt"], accept_multiple_files=True,
    help=(
        "CSV : choisissez librement la colonne des commentaires et, "
        "si elle existe, celle des auteurs. Séparateurs : point-virgule, "
        "virgule ou tabulation. TXT : en-têtes IRaMuTeQ ****."
    ),
)
if not fichiers:
    st.stop()


def proposer_colonne(colonnes: list[str], suggestions: tuple[str, ...]) -> str | None:
    """Trouver une colonne habituelle sans imposer son intitulé."""
    normalisees = {nom.strip().casefold(): nom for nom in colonnes}
    for suggestion in suggestions:
        if suggestion in normalisees:
            return normalisees[suggestion]
    return None


st.subheader("Choix des colonnes CSV")
st.caption(
    "Pour chaque fichier CSV, sélectionnez la colonne contenant les "
    "commentaires à analyser. La colonne auteur est facultative. "
    "Les autres colonnes restent disponibles dans le CSV complet exporté."
)
correspondances_csv: list[dict[str, object]] = []
try:
    for numero_fichier, fichier in enumerate(fichiers):
        if not fichier.name.lower().endswith(".csv"):
            continue
        colonnes_csv = lister_colonnes_csv(fichier.getvalue())
        defaut_texte = proposer_colonne(
            colonnes_csv,
            ("texte", "commentaire", "commentaires", "comment", "text",
             "content", "message", "body", "description"),
        ) or colonnes_csv[0]
        cle_fichier = hashlib.sha256(
            f"{numero_fichier}:{fichier.name}:".encode("utf-8")
            + fichier.getvalue()
        ).hexdigest()[:16]
        colonne_gauche, colonne_droite = st.columns(2)
        with colonne_gauche:
            texte_choisi = st.selectbox(
                f"Colonne contenant les commentaires — {fichier.name}",
                options=colonnes_csv,
                index=colonnes_csv.index(defaut_texte),
                key=f"qwen_texte_csv_{cle_fichier}",
            )
        with colonne_droite:
            choix_auteurs = [None] + [
                nom for nom in colonnes_csv if nom != texte_choisi
            ]
            auteur_propose = proposer_colonne(
                colonnes_csv,
                ("nom_affiche", "display_name", "auteur", "author",
                 "utilisateur", "username", "profil"),
            )
            if auteur_propose not in choix_auteurs:
                auteur_propose = None
            auteur_choisi = st.selectbox(
                f"Colonne auteur (facultative) — {fichier.name}",
                options=choix_auteurs,
                index=choix_auteurs.index(auteur_propose),
                format_func=lambda valeur: (
                    "Aucune colonne auteur" if valeur is None else valeur
                ),
                key=f"qwen_auteur_csv_{cle_fichier}",
            )
        correspondances_csv.append({
            "numero_fichier": numero_fichier,
            "nom_fichier": fichier.name,
            "colonne_texte": texte_choisi,
            "colonne_auteur": auteur_choisi,
        })
except (ValueError, UnicodeError) as erreur:
    st.error(f"Impossible de lire les en-têtes CSV : {erreur}")
    st.stop()

choix_par_fichier = {
    int(choix["numero_fichier"]): choix for choix in correspondances_csv
}

try:
    documents = []
    metadonnees = {}
    for numero_fichier, fichier in enumerate(fichiers):
        nom_fichier = fichier.name
        if nom_fichier.lower().endswith(".csv"):
            choix = choix_par_fichier[numero_fichier]
            nouveaux, informations = analyser_commentaires_csv(
                fichier.getvalue(),
                numero_depart=len(documents),
                colonne_texte=str(choix["colonne_texte"]),
                colonne_auteur=choix["colonne_auteur"],
            )
            documents.extend(nouveaux)
            for numero_document, informations_document in informations.items():
                metadonnees[numero_document] = {
                    **informations_document,
                    "fichier_source": nom_fichier,
                    "format_source": "csv_commentaires",
                }
        else:
            extraits = analyser_corpus(fichier.getvalue())
            depart = len(documents)
            documents.extend(
                replace(doc, numero=depart + numero + 1)
                for numero, doc in enumerate(extraits)
            )
            for doc in documents[depart:]:
                metadonnees[doc.numero] = {
                    "nom_affiche": "",
                    "ligne_csv": "",
                    "fichier_source": nom_fichier,
                    "format_source": "iramuteq",
                }

    tableau = tableau_documents(documents)
    colonnes_metadonnees = {
        "nom_affiche", "ligne_csv", "fichier_source", "format_source",
        "colonne_texte_source", "colonne_auteur_source",
    }
    for informations_document in metadonnees.values():
        colonnes_metadonnees.update(informations_document.keys())
    for colonne in sorted(colonnes_metadonnees):
        tableau[colonne] = [
            metadonnees.get(int(numero), {}).get(colonne, "")
            for numero in tableau["numero_document"]
        ]
except (ValueError, UnicodeError) as erreur:
    st.error(str(erreur))
    st.stop()

signature_fichiers = hashlib.sha256(
    b"\0".join(f.getvalue() for f in fichiers)
).hexdigest()
# Les importations historiques conservent leur signature pour les reprises.
selection_personnalisee = any(
    choix["colonne_texte"] != "texte"
    or choix["colonne_auteur"] != "nom_affiche"
    for choix in correspondances_csv
)
signature = (
    hashlib.sha256(
        (signature_fichiers + json.dumps(
            correspondances_csv, ensure_ascii=False, sort_keys=True,
        )).encode("utf-8")
    ).hexdigest()
    if selection_personnalisee else signature_fichiers
)
st.write(
    f"Documents importés : **{len(documents)}** ; "
    f"commentaires non vides : **{int(tableau['texte'].str.strip().ne('').sum())}**."
)
with st.expander("Aperçu des textes et variables", expanded=False):
    st.dataframe(tableau.head(30), use_container_width=True, hide_index=True)

with st.expander("Paramètres complémentaires", expanded=False):
    temperature = st.slider(
        "Température du modèle", 0.0, 0.8, 0.2, 0.05
    )
    contexte_general = st.text_area(
        "Contexte analytique facultatif commun aux commentaires",
        height=100,
        help="Aucune vidéo, image ou donnée sonore n'est récupérée automatiquement.",
    )
    variables = [col for col in tableau if col.startswith("variable_")]
    contexte_variables = st.multiselect(
        "Variables étoilées incluses dans le contexte",
        variables,
        help="Les métadonnées ne remplacent pas les indices textuels.",
    )
    montrer_uniquement_valides = st.checkbox(
        "Afficher uniquement les analyses abouties", value=False
    )

configuration = {
    "modele": MODELE,
    "mode_analyse": mode_analyse,
    "prompt": prompt,
    "temperature": float(temperature),
    "contexte_general": contexte_general,
    "contexte_variables": contexte_variables,
    "signature_corpus": signature,
}
if selection_personnalisee:
    configuration["correspondances_csv"] = correspondances_csv

cle = hashlib.sha256(
    json.dumps(configuration, sort_keys=True, ensure_ascii=False)
    .encode("utf-8")
).hexdigest()

if st.session_state.get("qwen_cle") != cle:
    st.session_state["qwen_cle"] = cle
    st.session_state["qwen_donnees"] = initialiser_tableau(tableau, signature, cle)
    st.session_state["qwen_message"] = ""

checkpoint = st.file_uploader(
    "Reprendre une analyse : importer le CSV de résultats précédent (facultatif)",
    type=["csv"], key="checkpoint",
)
if checkpoint is not None and st.button("Restaurer les résultats enregistrés"):
    try:
        anciens = pd.read_csv(
            io.BytesIO(checkpoint.getvalue()),
            sep=";", encoding="utf-8-sig",
            dtype={"signature_corpus": str, "cle_configuration": str, "texte": str},
        )
        compatible_ancien = (
            mode_analyse == "structure" and prompt == PROMPT_VIOLENCE_DEFAUT
        )
        st.session_state["qwen_donnees"] = restaurer_checkpoint(
            st.session_state["qwen_donnees"],
            anciens,
            signature,
            cle,
            autoriser_ancien_format=compatible_ancien,
        )
        st.success("Résultats restaurés. Vous pouvez poursuivre les analyses restantes.")
        if "cle_configuration" not in anciens.columns:
            st.warning(
                "Cet ancien CSV ne contenait pas la consigne du modèle. "
                "La compatibilité exacte du prompt historique ne peut pas être vérifiée."
            )
    except (ValueError, pd.errors.ParserError) as erreur:
        st.error(f"Reprise impossible : {erreur}")

donnees = st.session_state["qwen_donnees"]
reste = donnees.index[donnees["statut_codage"].eq("non_traite")].tolist()
erreurs = donnees.index[
    donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])
].tolist()
aboutis = int(donnees["statut_codage"].eq("ok").sum())
vides = int(donnees["statut_codage"].eq("vide").sum())
st.write(
    f"Analyses réalisées : **{aboutis}** ; "
    f"à analyser : **{len(reste)}** ; "
    f"en erreur : **{len(erreurs)}** ; "
    f"textes vides : **{vides}**."
)
if st.session_state.get("qwen_message"):
    if erreurs:
        st.error(st.session_state["qwen_message"])
    else:
        st.info(st.session_state["qwen_message"])

if erreurs:
    if any(
        "unexpected eof" in str(valeur).lower()
        for valeur in donnees.loc[erreurs, "erreur_codage"]
    ):
        st.warning(
            "Ollama a perdu la connexion avec le processus d'inférence "
            "(unexpected EOF). Il faut consulter les journaux du conteneur "
            "ollama dans Coolify, au moment exact de l'échec. "
            "Une saturation mémoire, un plantage du moteur ou un problème "
            "de compatibilité sont possibles ; ce message seul ne permet "
            "pas de les départager. Le choix de la colonne CSV ne résout "
            "pas cette panne d'Ollama."
        )
    st.error(
        f"Échec de l'inférence Qwen pour {len(erreurs)} commentaire(s). "
        "Le corpus importé ne constitue pas un résultat du modèle. "
        "Voici les causes techniques, enregistrées par l'application :"
    )
    for numero_erreur, (_, ligne_erreur) in enumerate(
        donnees.loc[erreurs].head(3).iterrows(), start=1
    ):
        st.code(
            f"Commentaire {int(ligne_erreur['numero_document'])} — "
            f"{ligne_erreur['statut_codage']}\n"
            f"{ligne_erreur['erreur_codage'] or 'Détail non fourni'}",
            language="text",
        )

# Lancer une analyse uniquement lorsque l'API répond ET que le modèle est présent.
service_disponible = False
try:
    informations = verifier_service()
    modeles_disponibles = [
        str(modele.get("name", "")) for modele in informations.get("models", [])
    ]
    service_disponible = any(
        nom == MODELE or nom.startswith(MODELE + ":")
        for nom in modeles_disponibles
    )
    if service_disponible:
        st.success(f"Qwen est disponible et prêt à analyser les commentaires : {MODELE}.")
    else:
        st.error(
            f"Ollama répond, mais le modèle {MODELE} est absent. "
            "Aucune analyse ne peut commencer : vérifiez le téléchargement "
            "des poids Qwen dans le service charger_modele de Coolify."
        )
except requests.RequestException as erreur:
    st.error(
        f"Impossible de joindre Ollama ({URL_OLLAMA}) : {type(erreur).__name__} : {erreur}. "
        "Vérifiez le service ollama dans Coolify ; les données CSV "
        "ne constituent pas un résultat d'analyse."
    )

st.subheader("Lancer l'analyse")
st.caption(
    "Le bouton de test analyse un seul commentaire et affiche immédiatement "
    "sa réponse. Le bouton principal analyse ensuite automatiquement "
    "tous les commentaires restants, sans intervention par lots."
)
colonne_test, colonne_analyser, colonne_erreurs = st.columns([1, 2, 1])
tester = colonne_test.button(
    "Tester sur un commentaire",
    disabled=not reste or not prompt.strip() or not service_disponible,
)
lancer = colonne_analyser.button(
    "Analyser tous les commentaires restants",
    type="primary",
    disabled=not reste or not prompt.strip() or not service_disponible,
)
relancer = colonne_erreurs.button(
    "Réessayer les commentaires en erreur",
    disabled=not erreurs or not prompt.strip() or not service_disponible,
)
if tester or lancer or relancer:
    indices = reste[:1] if tester else (reste if lancer else erreurs)
    termines, nombre_erreurs, interrompu = lancer_analyse(
        donnees, indices, mode_analyse, prompt,
        contexte_general, contexte_variables, float(temperature),
    )
    st.session_state["qwen_donnees"] = donnees
    if interrompu:
        indice_derniere_erreur = indices[min(
            len(indices) - 1, termines + nombre_erreurs - 1
        )]
        detail_derniere_erreur = str(
            donnees.at[indice_derniere_erreur, "erreur_codage"]
        )
        st.session_state["qwen_message"] = (
            "Analyse interrompue après trois erreurs consécutives : "
            f"{termines} réussite(s), {nombre_erreurs} erreur(s). "
            f"Dernière cause : {detail_derniere_erreur}. "
            "Les analyses abouties restent conservées."
        )
    elif nombre_erreurs:
        st.session_state["qwen_message"] = (
            f"{termines} analyse(s) aboutie(s), {nombre_erreurs} erreur(s). "
            "Les détails techniques sont visibles dans la rubrique Erreurs de Qwen."
        )
    else:
        st.session_state["qwen_message"] = (
            f"{termines} commentaire(s) analysé(s) avec succès. "
            "Les réponses sont affichées ci-dessous."
        )
    st.rerun()

st.subheader("Réponses produites par Qwen")
reponses_valides = donnees.loc[
    donnees["statut_codage"].eq("ok")
    & donnees["reponse_qwen"].fillna("").astype(str).str.strip().ne("")
].copy()
tableau_erreurs = donnees.loc[
    donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])
].copy()
nombre_a_traiter = int(donnees["statut_codage"].eq("non_traite").sum())

if reponses_valides.empty:
    if not tableau_erreurs.empty:
        st.error(
            "Aucune réponse produite par Qwen : les tentatives ont rencontré "
            "des erreurs. Leur détail est affiché ci-dessous. "
            "Le tableau importé n'est PAS une analyse."
        )
    elif nombre_a_traiter:
        st.info(
            f"Aucune réponse Qwen pour le moment. "
            f"{nombre_a_traiter} commentaire(s) attendent une analyse. "
            "Utilisez « Tester sur un commentaire » pour vérifier "
            "le fonctionnement du modèle avant l'analyse du corpus entier."
        )
    else:
        st.warning(
            "Aucune réponse Qwen disponible. "
            "Consultez le statut des commentaires et les éventuelles erreurs."
        )
else:
    st.success(
        f"{len(reponses_valides)} réponse(s) effectivement générée(s) par le modèle."
    )
    colonnes_principales = [
        "numero_document", "nom_affiche", "texte", "reponse_qwen",
        "statut_codage",
    ]
    if mode_analyse == "structure":
        colonnes_principales += list(CHAMPS_BOOLEENS) + ["acteur_cible"]
    st.dataframe(
        reponses_valides[
            [col for col in colonnes_principales if col in reponses_valides]
        ].head(1000),
        hide_index=True,
        use_container_width=True,
        height=380,
        column_config={
            "texte": st.column_config.TextColumn("Commentaire", width="large"),
            "nom_affiche": st.column_config.TextColumn("Auteur"),
            "reponse_qwen": st.column_config.TextColumn(
                "Analyse produite par Qwen", width="large"
            ),
        },
    )
    if len(reponses_valides) > 1000:
        st.caption(
            "Aperçu limité à 1 000 réponses. Les exports contiennent toutes les lignes."
        )

    identifiants = reponses_valides["numero_document"].astype(int).tolist()
    descriptions = {
        int(ligne.numero_document): (
            f"{int(ligne.numero_document)} — "
            f"{str(ligne.nom_affiche) if str(ligne.nom_affiche).strip() else 'Sans pseudonyme'}"
        )
        for ligne in reponses_valides.itertuples(index=False)
    }
    commentaire_choisi = st.selectbox(
        "Lire intégralement une analyse",
        identifiants,
        format_func=lambda numero: descriptions.get(numero, str(numero)),
    )
    selection = reponses_valides.loc[
        reponses_valides["numero_document"].eq(commentaire_choisi)
    ].iloc[0]
    st.text_area(
        "Commentaire original",
        value=str(selection["texte"]),
        height=100,
        disabled=True,
    )
    st.text_area(
        "Réponse effective de Qwen",
        value=str(selection["reponse_qwen"]),
        height=260,
        disabled=True,
    )

if not tableau_erreurs.empty:
    st.subheader("Erreurs de Qwen")
    st.error(
        f"{len(tableau_erreurs)} commentaire(s) n'ont pas reçu de réponse valide. "
        "Une erreur HTTP, une indisponibilité d'Ollama ou une sortie invalide "
        "n'est pas un résultat d'analyse."
    )
    st.dataframe(
        tableau_erreurs[
            [
                col for col in (
                    "numero_document", "nom_affiche", "texte",
                    "statut_codage", "erreur_codage",
                )
                if col in tableau_erreurs
            ]
        ].head(200),
        hide_index=True,
        use_container_width=True,
        column_config={
            "erreur_codage": st.column_config.TextColumn(
                "Cause technique (Ollama ou modèle)", width="large"
            ),
        },
    )

with st.expander("Tableau complet, métadonnées et variables du corpus", expanded=False):
    vue = (
        donnees.loc[donnees["statut_codage"].eq("ok")]
        if montrer_uniquement_valides else donnees
    )
    st.dataframe(vue.head(1000), hide_index=True, use_container_width=True)
    if len(vue) > 1000:
        st.caption(
            "Aperçu limité à 1 000 lignes. Le ZIP et le CSV "
            "contiennent toutes les lignes."
        )

avec_resultat = donnees.loc[donnees["statut_codage"].eq("ok")]
if mode_analyse == "structure" and not avec_resultat.empty:
    frequences = pd.Series({
        champ: int(avec_resultat[champ].fillna(False).sum())
        for champ in CHAMPS_BOOLEENS
    })
    st.bar_chart(frequences, x_label="Catégorie", y_label="Commentaires codés")
    variables_disponibles = [
        col for col in donnees if col.startswith("variable_")
    ]
    if variables_disponibles:
        variable = st.selectbox(
            "Croiser un codage avec une variable du corpus",
            variables_disponibles,
        )
        categorie = st.selectbox(
            "Catégorie à croiser", list(CHAMPS_BOOLEENS)
        )
        st.dataframe(
            pd.crosstab(
                avec_resultat[variable].fillna("absent"),
                avec_resultat[categorie].astype(str),
            ),
            use_container_width=True,
        )

archive = archive_resultats(
    donnees, documents, signature,
    {**configuration, "correspondances_csv": correspondances_csv},
)
st.download_button(
    "Télécharger tous les résultats, même partiels (ZIP)",
    archive,
    file_name="resultats_qwen3_4b_iramuteq.zip",
    mime="application/zip",
)
st.download_button(
    "Télécharger le CSV de reprise",
    exporter_csv(donnees),
    file_name="codage_commentaires.csv",
    mime="text/csv",
)
