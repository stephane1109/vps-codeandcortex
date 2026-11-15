"""Streamlit : codage de corpus IRaMuTeQ avec le modèle local Qwen3-4B."""
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

from codage_qwen import CHAMPS_BOOLEENS, MODELE, URL_OLLAMA, coder_commentaire, verifier_service
from lecture_iramuteq import analyser_corpus, exporter_csv, exporter_iramuteq, tableau_documents

st.set_page_config(page_title="Qwen3-4B — codage discursif", layout="wide")


def authentifier() -> None:
    """Contrôler le droit d'utiliser l'inférence CPU."""
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


def archive_resultats(tableau: pd.DataFrame, documents, signature: str,
                      parametres: dict[str, object]) -> bytes:
    """Produire un ZIP unique exportable et réimportable pour reprise."""
    # Éviter d'interpréter les échecs comme des réponses négatives.
    categories = {}
    def est_vrai(valeur: object) -> bool:
        return bool(valeur) if pd.notna(valeur) else False

    for ligne in tableau.itertuples(index=False):
        if ligne.statut_codage != "ok":
            categorie = "indetermine"
        elif est_vrai(ligne.interpretation_indeterminee):
            categorie = "indetermine"
        elif est_vrai(ligne.violence_justifiee) and est_vrai(ligne.violence_denoncee):
            categorie = "ambivalent"
        elif est_vrai(ligne.violence_justifiee):
            categorie = "justification"
        elif est_vrai(ligne.violence_denoncee):
            categorie = "denonciation"
        elif est_vrai(ligne.violence_minimisee):
            categorie = "minimisation"
        elif est_vrai(ligne.violence_evoquee):
            categorie = "evocation"
        else:
            categorie = "hors_violence"
        categories[int(ligne.numero_document)] = categorie
    texte = exporter_iramuteq(documents, categories, "qwen_position")
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("codage_commentaires.csv", exporter_csv(tableau))
        zipf.writestr("corpus_qwen_iramuteq.txt", texte)
        zipf.writestr("parametres.json", json.dumps({**parametres, "signature": signature}, indent=2, ensure_ascii=False))
    return tampon.getvalue()


def initialiser_tableau(tableau: pd.DataFrame, signature: str) -> pd.DataFrame:
    """Préparer toutes les lignes, y compris les commentaires vides."""
    donnees = tableau.copy()
    donnees["signature_corpus"] = signature
    donnees["statut_codage"] = "non_traite"
    for champ in CHAMPS_BOOLEENS:
        donnees[champ] = pd.Series([pd.NA] * len(donnees), dtype="boolean")
    for champ in ("acteur_cible", "indice_textuel", "justification", "erreur_codage"):
        donnees[champ] = ""
    for champ in ("texte_tronque", "contexte_tronque"):
        donnees[champ] = pd.Series([pd.NA] * len(donnees), dtype="boolean")
    donnees.loc[donnees["texte"].str.strip().eq(""), "statut_codage"] = "vide"
    return donnees


authentifier()
st.title("Qwen3-4B — codage des discours sur la violence")
st.caption("Modèle local via Ollama, avec catégories proposées par LLM et contrôle nécessaire par le chercheur.")
st.info("Chaque commentaire est conservé dans le corpus. Les textes impossibles à coder et les erreurs restent identifiés. Les catégories dénonciation, justification et minimisation ne sont pas exclusives.")
try:
    informations = verifier_service()
    disponibles = [modele.get("name", "") for modele in informations.get("models", [])]
    if not any(nom == MODELE or nom.startswith(MODELE + ":") for nom in disponibles):
        st.warning(f"Le service Ollama répond, mais le modèle {MODELE} n'est pas présent : lancer `ollama pull {MODELE}` dans le conteneur Ollama.")
    else:
        st.success(f"Ollama disponible : {MODELE}.")
except requests.RequestException as erreur:
    st.error(f"Service Ollama inaccessible ({URL_OLLAMA}) : {erreur}")

fichiers = st.file_uploader("Importer les fichiers IRaMuTeQ (.txt)", type=["txt"], accept_multiple_files=True)
if not fichiers:
    st.stop()
try:
    documents = []
    for fichier in fichiers:
        extrait = analyser_corpus(fichier.getvalue())
        depart = len(documents)
        documents.extend(replace(doc, numero=depart + indice + 1) for indice, doc in enumerate(extrait))
    tableau = tableau_documents(documents)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

signature = hashlib.sha256(b"\0".join(f.getvalue() for f in fichiers)).hexdigest()
st.write(f"Documents importés : **{len(documents)}**")
st.dataframe(tableau.head(20), use_container_width=True, hide_index=True)

with st.expander("Configuration du codage", expanded=True):
    lots = st.number_input("Nombre de commentaires par lot", 1, 100, 20)
    temperature = st.slider("Température du modèle", 0.0, 0.8, 0.2, 0.05)
    contexte_general = st.text_area("Contexte analytique facultatif commun aux commentaires", height=100,
                                    help="Décrivez éventuellement la vidéo analysée. Aucun contenu vidéo n'est récupéré automatiquement.")
    variables = [col for col in tableau if col.startswith("variable_")]
    contexte_variables = st.multiselect("Variables étoilées incluses dans le contexte", variables,
                                       help="Les métadonnées sont fournies au modèle comme contexte, mais ne doivent pas justifier une position sans indice textuel.")
    montrer_uniquement_valides = st.checkbox("Afficher uniquement les codages aboutis", value=False)

configuration = {"modele": MODELE, "temperature": float(temperature),
                 "contexte_general": contexte_general, "contexte_variables": contexte_variables,
                 "signature_corpus": signature}
cle = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode("utf-8")).hexdigest()
checkpoint = st.file_uploader("Reprendre une analyse : importer le CSV codage_commentaires.csv précédemment exporté (facultatif)", type=["csv"], key="checkpoint")

if st.session_state.get("qwen_cle") != cle:
    st.session_state["qwen_cle"] = cle
    st.session_state["qwen_donnees"] = initialiser_tableau(tableau, signature)

if checkpoint is not None and st.button("Restaurer le CSV de reprise"):
    try:
        anciens = pd.read_csv(io.BytesIO(checkpoint.getvalue()), sep=";", encoding="utf-8-sig", dtype={"signature_corpus": str})
        champs = ["numero_document", "signature_corpus", "texte", "statut_codage", *CHAMPS_BOOLEENS,
                  "acteur_cible", "indice_textuel", "justification", "erreur_codage",
                  "texte_tronque", "contexte_tronque"]
        if any(champ not in anciens.columns for champ in champs):
            raise ValueError("Colonnes de reprise incomplètes.")
        if (len(anciens) != len(tableau) or anciens["signature_corpus"].nunique() != 1
                or anciens["signature_corpus"].iloc[0] != signature
                or not anciens["numero_document"].equals(tableau["numero_document"])):
            raise ValueError("CSV de reprise incompatible avec le corpus courant.")
        donnees = st.session_state["qwen_donnees"]
        donnees.loc[:, [champ for champ in champs if champ not in ("numero_document", "signature_corpus", "texte")]] = anciens[
            [champ for champ in champs if champ not in ("numero_document", "signature_corpus", "texte")]
        ].to_numpy()
        st.success("Codages restaurés. Les lignes non traitées peuvent être poursuivies.")
    except (ValueError, pd.errors.ParserError) as erreur:
        st.error(f"Reprise impossible : {erreur}")

donnees = st.session_state["qwen_donnees"]
reste = donnees.index[donnees["statut_codage"].eq("non_traite")].tolist()
erreurs = donnees.index[donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])].tolist()
st.write(f"Codages aboutis : **{int(donnees['statut_codage'].eq('ok').sum())}** ; à traiter : **{len(reste)}** ; erreurs : **{len(erreurs)}**")

colonne_traitement, colonne_reprise = st.columns(2)
traiter = colonne_traitement.button("Traiter le prochain lot", type="primary", disabled=not reste)
reessayer = colonne_reprise.button("Réessayer un lot en erreur", disabled=not erreurs)
if traiter or reessayer:
    indices = (reste if traiter else erreurs)[:int(lots)]
    barre = st.progress(0, text="Codage en cours")
    with requests.Session() as session:
        for position, indice in enumerate(indices):
            ligne = donnees.loc[indice]
            contexte_details = "\n".join(f"{colonne}: {ligne[colonne]}" for colonne in contexte_variables
                                          if pd.notna(ligne.get(colonne)))
            contexte = contexte_general + "\n" + contexte_details
            try:
                resultat = coder_commentaire(str(ligne["texte"]), contexte, float(temperature), session=session)
                for champ, valeur in resultat.items():
                    donnees.at[indice, champ] = valeur
                donnees.at[indice, "statut_codage"] = "ok"
                donnees.at[indice, "erreur_codage"] = ""
            except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError) as erreur:
                donnees.at[indice, "statut_codage"] = "erreur_service" if isinstance(erreur, requests.RequestException) else "sortie_invalide"
                donnees.at[indice, "erreur_codage"] = f"{type(erreur).__name__}: {str(erreur)[:300]}"
            barre.progress(round((position + 1) / len(indices) * 100),
                           text=f"Commentaire {position + 1}/{len(indices)}")
    st.session_state["qwen_donnees"] = donnees
    st.rerun()

st.subheader("Résultats")
vue = donnees.loc[donnees["statut_codage"].eq("ok")] if montrer_uniquement_valides else donnees
st.dataframe(vue, hide_index=True, use_container_width=True)
avec_resultat = donnees[donnees["statut_codage"].eq("ok")]
if not avec_resultat.empty:
    frequences = pd.Series({champ: int(avec_resultat[champ].fillna(False).sum()) for champ in CHAMPS_BOOLEENS})
    st.bar_chart(frequences, x_label="Catégorie", y_label="Commentaires codés")
    variables_disponibles = [col for col in donnees if col.startswith("variable_")]
    if variables_disponibles:
        variable = st.selectbox("Croiser un codage avec une variable du corpus", variables_disponibles)
        categorie = st.selectbox("Catégorie à croiser", list(CHAMPS_BOOLEENS))
        st.dataframe(pd.crosstab(avec_resultat[variable].fillna("absent"),
                                avec_resultat[categorie].astype(str)), use_container_width=True)

archive = archive_resultats(donnees, documents, signature, configuration)
st.download_button("Télécharger tous les résultats, même partiels (ZIP)", archive,
                   file_name="resultats_qwen3_4b_iramuteq.zip", mime="application/zip")
st.download_button("Télécharger le CSV de reprise", exporter_csv(donnees),
                   file_name="codage_commentaires.csv", mime="text/csv")
