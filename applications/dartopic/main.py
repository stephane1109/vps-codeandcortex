"""Interface Streamlit pour une reproduction expérimentale de DARTopic."""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile

import numpy as np
import pandas as pd
import streamlit as st

from lecture_iramuteq import analyser_corpus, exporter_csv, exporter_iramuteq, tableau_documents
from modele_dartopic import MODELE_PLURILINGUE, ParametresDARTopic, entrainer_dartopic

st.set_page_config(page_title="DARTopic — IRaMuTeQ", layout="wide")


def authentifier() -> None:
    """Empêcher l'entraînement public non autorisé sur le VPS."""
    mot_de_passe = os.getenv("APP_PASSWORD", "")
    if not mot_de_passe:
        if os.getenv("APP_ALLOW_PUBLIC", "0") != "1":
            st.error("Configuration manquante : renseigner APP_PASSWORD dans Coolify.")
            st.stop()
        st.warning("Mode public activé explicitement : APP_ALLOW_PUBLIC=1.")
        return
    import hmac
    saisie = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(saisie.encode("utf-8"), mot_de_passe.encode("utf-8")):
        st.stop()


def charger_mots_vides(personnalises: str, supprimer: bool) -> list[str]:
    """Utiliser les mots vides français de NLTK lorsqu'ils sont installés."""
    if not supprimer:
        return [mot.strip().lower() for mot in personnalises.splitlines() if mot.strip()]
    try:
        from nltk.corpus import stopwords
        mots = set(stopwords.words("french"))
    except LookupError:
        mots = set("le la les de du des un une et ou mais donc que qui à au aux en dans sur pour par ce cette ces est sont il elle ils elles je tu nous vous on avec ne pas se sa son ses leur leurs".split())
    mots.update(mot.strip().lower() for mot in personnalises.splitlines() if mot.strip())
    return sorted(mots)


def construire_archive(resultats: pd.DataFrame, themes: pd.DataFrame, historique: pd.DataFrame,
                       sortie_iramuteq: bytes, configuration: dict[str, object]) -> bytes:
    """Regrouper les résultats textuels et la provenance méthodologique."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("documents_themes.csv", exporter_csv(resultats))
        archive.writestr("themes_mots.csv", exporter_csv(themes))
        archive.writestr("historique_entrainement.csv", exporter_csv(historique))
        archive.writestr("corpus_themes_iramuteq.txt", sortie_iramuteq)
        archive.writestr("parametres.json", json.dumps(configuration, indent=2, ensure_ascii=False))
    return tampon.getvalue()


authentifier()
st.title("DARTopic — découverte des thèmes")
st.caption("Reproduction expérimentale non officielle de Seo, Cho et Yoo (2026), adaptée au français ; résultats à valider sur le corpus.")
st.info("DARTopic découvre des thèmes latents ; il ne détermine pas directement si un commentaire dénonce ou justifie la violence. Les thèmes doivent être interprétés par le chercheur.")

fichiers = st.file_uploader("Importer un ou plusieurs corpus IRaMuTeQ (.txt)", type=["txt"], accept_multiple_files=True)
if not fichiers:
    st.stop()
try:
    documents = []
    for fichier in fichiers:
        # Numéroter globalement pour préserver l'unicité entre les fichiers.
        nouveau = analyser_corpus(fichier.getvalue())
        from dataclasses import replace
        depart = len(documents)
        documents.extend(replace(doc, numero=depart + indice + 1) for indice, doc in enumerate(nouveau))
    tableau = tableau_documents(documents)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

st.write(f"Documents importés : **{len(documents)}** ; textes non vides : **{int(tableau['texte'].str.strip().ne('').sum())}**")
st.dataframe(tableau.head(25), use_container_width=True, hide_index=True)

with st.expander("Paramètres du modèle", expanded=True):
    colonne_1, colonne_2, colonne_3 = st.columns(3)
    with colonne_1:
        nombre_themes = st.number_input("Nombre de thèmes", min_value=2, max_value=80, value=8, step=1)
        nombre_epoques = st.number_input("Époques d'entraînement", min_value=5, max_value=200, value=35, step=5)
        taille_lot = st.selectbox("Documents par lot", [8, 16, 24, 32], index=1)
    with colonne_2:
        longueur = st.slider("Longueur maximale (tokens)", 16, 128, 64, step=8)
        taille_vocabulaire = st.number_input("Vocabulaire maximal", 100, 5000, 1800, step=100)
        frequence_minimale = st.number_input("Fréquence documentaire minimale", 1, 20, 2)
    with colonne_3:
        seuil = st.slider("Seuil de similarité entre tokens", 0.0, 0.9, 0.2, 0.05)
        poids_kl = st.slider("Poids de régularisation KL", 0.0, 2.0, 0.25, 0.05)
        graine = st.number_input("Graine aléatoire", 0, 999999, 42)
    choix_encodeur = st.selectbox(
        "Encodeur contextuel figé",
        [MODELE_PLURILINGUE, "sentence-transformers/all-MiniLM-L6-v2"],
        help="Le modèle multilingue est conseillé pour le français. L'encodeur anglophone reproduit plus étroitement le protocole de l'article."
    )
    retirer_mots_vides = st.checkbox("Retirer les mots vides français du vocabulaire", value=True)
    mots_sup = st.text_area("Mots exclus supplémentaires (un par ligne)", height=80)
    taille_echantillon = st.number_input("Nombre maximal de textes analysés (échantillon reproductible)", 5, 4000, 1000, step=100)

if len(documents) > 4000:
    st.warning("Pour préserver la mémoire du VPS, un échantillon aléatoire de 4 000 textes maximum peut être traité par calcul.")

empreinte = hashlib.sha256(b"\0".join(f.getvalue() for f in fichiers)).hexdigest()
parametres = ParametresDARTopic(
    nombre_themes=int(nombre_themes), nombre_epoques=int(nombre_epoques), taille_lot=int(taille_lot),
    longueur_maximale=int(longueur), taille_vocabulaire=int(taille_vocabulaire),
    frequence_minimale=int(frequence_minimale), seuil_similarite=float(seuil),
    poids_kl=float(poids_kl), graine=int(graine), modele_encodeur=choix_encodeur,
)
configuration = {**parametres.__dict__, "fichiers": [f.name for f in fichiers],
                 "empreinte_sha256": empreinte, "max_documents": int(taille_echantillon),
                 "mots_vides_francais": bool(retirer_mots_vides), "mots_exclus_supplementaires": mots_sup}
cle_calcul = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode("utf-8")).hexdigest()

if st.button("Lancer la découverte thématique", type="primary"):
    masque_non_vides = tableau["texte"].str.strip().ne("").to_numpy()
    indices_utiles = np.flatnonzero(masque_non_vides)
    if len(indices_utiles) < max(5, nombre_themes):
        st.error("Nombre de commentaires utilisables insuffisant pour le nombre de thèmes choisi.")
        st.stop()
    generateur = np.random.default_rng(int(graine))
    if len(indices_utiles) > taille_echantillon:
        indices_utiles = np.sort(generateur.choice(indices_utiles, size=int(taille_echantillon), replace=False))
    textes = tableau.iloc[indices_utiles]["texte"].tolist()
    barre = st.progress(0, text="Préparation du calcul")

    def progression(fraction: float, message: str) -> None:
        barre.progress(min(100, max(0, int(fraction * 100))), text=message)

    try:
        sortie = entrainer_dartopic(textes, parametres, progression,
                                   charger_mots_vides(mots_sup, retirer_mots_vides))
    except Exception as erreur:
        st.error(f"Échec du calcul : {type(erreur).__name__} : {erreur}")
        st.stop()
    resultat = tableau.copy()
    resultat["theme_dominant"] = "non_analyse"
    resultat["probabilite_theme"] = np.nan
    distribution = sortie["distribution"]
    dominants = np.argmax(distribution, axis=1) + 1
    resultat.loc[indices_utiles, "theme_dominant"] = [f"theme_{k:02d}" for k in dominants]
    resultat.loc[indices_utiles, "probabilite_theme"] = np.max(distribution, axis=1)
    for k in range(distribution.shape[1]):
        colonne = f"probabilite_theme_{k+1:02d}"
        resultat[colonne] = np.nan
        resultat.loc[indices_utiles, colonne] = distribution[:, k]
    themes = pd.DataFrame([{cle: valeur for cle, valeur in theme.items() if cle != "probabilite_mots" and cle != "mots_liste"}
                           for theme in sortie["themes"]])
    historique = pd.DataFrame(sortie["historique"])
    categories = {int(ligne.numero_document): str(ligne.theme_dominant)
                  for ligne in resultat.itertuples(index=False)}
    texte_export = exporter_iramuteq(documents, categories, "dartopic")
    configuration["documents_analyses"] = len(indices_utiles)
    configuration["statut_implementation"] = "reproduction expérimentale non officielle"
    archive = construire_archive(resultat, themes, historique, texte_export, configuration)
    st.session_state["dartopic_resultat"] = (cle_calcul, resultat, themes, historique, archive)

stockage = st.session_state.get("dartopic_resultat")
if stockage and stockage[0] == cle_calcul:
    _, resultat, themes, historique, archive = stockage
    st.subheader("Thèmes découverts")
    st.dataframe(themes, hide_index=True, use_container_width=True)
    effectifs = resultat.loc[resultat["theme_dominant"] != "non_analyse", "theme_dominant"].value_counts().sort_index()
    st.bar_chart(effectifs, x_label="Thème", y_label="Nombre de textes")
    st.subheader("Affectations et incertitude")
    st.dataframe(resultat, hide_index=True, use_container_width=True)
    st.subheader("Historique de l'entraînement")
    st.line_chart(historique.set_index("epoque"))
    variables = [colonne for colonne in resultat if colonne.startswith("variable_") and colonne != "variables_iramuteq"]
    if variables:
        variable = st.selectbox("Croiser les thèmes avec une variable étoilée", variables)
        st.dataframe(pd.crosstab(resultat[variable].fillna("absent"), resultat["theme_dominant"]), use_container_width=True)
    st.download_button("Télécharger tous les résultats (ZIP)", archive,
                       file_name="resultats_dartopic_iramuteq.zip", mime="application/zip")
elif stockage:
    st.info("Les paramètres ont changé ; relancer le calcul pour actualiser les résultats.")
