"""Interface Streamlit BERTopic pour commentaires et textes au format IRaMuTeQ."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import threading
import zipfile
from dataclasses import asdict, replace
from importlib.metadata import version

import numpy as np
import pandas as pd
import streamlit as st

from lecture_iramuteq import analyser_corpus, exporter_csv, exporter_iramuteq, tableau_documents
from moteur_bertopic import (
    MODELE_ALTERNATIF, MODELE_ANGLOPHONE, MODELE_PLURILINGUE,
    ParametresBERTopic, entrainer_bertopic,
)
from traitements import construire_croisement, enrichir_documents

st.set_page_config(page_title="BERTopic — IRaMuTeQ", layout="wide")
VERROU_ENTRAINEMENT = threading.Lock()


def authentifier() -> None:
    """Refuser l'accès public au modèle sans authentification explicite."""
    mot_de_passe = os.getenv("APP_PASSWORD", "")
    if not mot_de_passe:
        if os.getenv("APP_ALLOW_PUBLIC", "0") != "1":
            st.error("Définir APP_PASSWORD dans Coolify avant de démarrer l'application.")
            st.stop()
        st.warning("Mode public activé explicitement.")
        return
    saisie = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(saisie.encode("utf-8"), mot_de_passe.encode("utf-8")):
        st.stop()


def charger_mots_vides(supprimer_francais: bool, lignes_personnalisees: str) -> list[str]:
    """Utiliser les stopwords français NLTK et les exclusions choisies."""
    mots = set()
    if supprimer_francais:
        try:
            from nltk.corpus import stopwords
            mots.update(stopwords.words("french"))
        except LookupError:
            mots.update("le la les de du des un une et ou mais que qui à au aux en dans sur pour par ce cette ces est sont il elle ils elles je tu nous vous on avec ne pas se sa son ses leur leurs".split())
    mots.update(ligne.strip().lower() for ligne in lignes_personnalisees.splitlines() if ligne.strip())
    return sorted(mots)


def creer_archive(
    documents: pd.DataFrame,
    themes: pd.DataFrame,
    vocabulaire: pd.DataFrame,
    representatifs: pd.DataFrame,
    iramuteq: bytes,
    configuration: dict[str, object],
) -> bytes:
    """Construire une archive unique sans données personnelles supplémentaires."""
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("documents_themes.csv", exporter_csv(documents))
        archive.writestr("themes.csv", exporter_csv(themes))
        archive.writestr("themes_mots.csv", exporter_csv(vocabulaire))
        archive.writestr("textes_representatifs.csv", exporter_csv(representatifs))
        archive.writestr("corpus_themes_iramuteq.txt", iramuteq)
        archive.writestr("parametres.json", json.dumps(configuration, ensure_ascii=False, indent=2))
    return sortie.getvalue()


authentifier()
st.title("BERTopic — découverte thématique")
st.caption("BERTopic 0.17.4 : embeddings multilingues, UMAP, HDBSCAN et c-TF-IDF.")
st.info(
    "Un thème n'est pas une prise de position axiologique ni une représentation sociale. "
    "BERTopic identifie des proximités discursives à interpréter et à valider."
)

fichiers = st.file_uploader(
    "Importer un ou plusieurs fichiers IRaMuTeQ (.txt)",
    type=["txt"], accept_multiple_files=True,
)
if not fichiers:
    st.stop()
try:
    documents = []
    contenus = [fichier.getvalue() for fichier in fichiers]
    for contenu in contenus:
        bloc = analyser_corpus(contenu)
        depart = len(documents)
        documents.extend(replace(doc, numero=depart + position + 1)
                         for position, doc in enumerate(bloc))
    tableau = tableau_documents(documents)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

utilisables = int(tableau["texte"].str.strip().ne("").sum())
colonne_1, colonne_2, colonne_3 = st.columns(3)
colonne_1.metric("Documents importés", len(tableau))
colonne_2.metric("Textes non vides", utilisables)
colonne_3.metric("Textes vides", len(tableau) - utilisables)
with st.expander("Aperçu du corpus et des variables", expanded=False):
    st.dataframe(tableau.head(40), use_container_width=True, hide_index=True)

with st.expander("Paramètres de BERTopic", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        encodeur = st.selectbox("Encodeur sémantique", [
            MODELE_PLURILINGUE, MODELE_ALTERNATIF, MODELE_ANGLOPHONE,
        ], help="Privilégier le premier pour des commentaires en français.")
        taille_lot = st.selectbox("Documents par lot", [8, 16, 24, 32], index=1)
        taille_theme = st.number_input("Taille minimale d'un thème (HDBSCAN)", 5, 200, 10)
        min_echantillon = st.number_input(
            "Min. échantillons HDBSCAN (densité)", 1, 50, 5,
            help="Une valeur élevée peut produire plus de textes hors thème."
        )
    with c2:
        voisins = st.number_input("Voisins UMAP", 2, 100, 15)
        dimensions = st.slider("Dimensions UMAP", 2, 15, 5)
        ng_max = st.selectbox("N-grammes pour les mots des thèmes", [1, 2, 3], index=1)
        freq_doc = st.number_input("Fréquence documentaire minimale", 1, 20, 2)
        vocab_max = st.number_input("Vocabulaire maximal", 500, 30000, 10000, step=500)
    with c3:
        mots_theme = st.slider("Mots représentatifs par thème", 5, 20, 12)
        reduction = st.selectbox(
            "Réduction du nombre de thèmes", ["aucune", "automatique", "nombre_fixe"],
            help="Le regroupement découvre d'abord les thèmes. Le nombre fixe les fusionne ensuite."
        )
        cible = st.number_input("Nombre cible de thèmes (si réduction fixe)", 2, 80, 10)
        probabilites = st.checkbox(
            "Calculer la matrice des probabilités de tous les thèmes", value=False,
            help="Coûteux en mémoire et calcul ; désactivé par défaut sur VPS."
        )
        graine = st.number_input("Graine aléatoire", 0, 999999, 42)
    supprimer_fr = st.checkbox("Exclure les mots vides français du vocabulaire c-TF-IDF", value=True)
    autres_mots = st.text_area("Mots supplémentaires à exclure (un par ligne)", height=80)
    plafond = st.number_input(
        "Nombre maximal de textes analysés (échantillon reproductible)",
        min_value=5, max_value=4000, value=1000, step=100,
    )

parametres = ParametresBERTopic(
    modele_encodeur=encodeur,
    taille_lot=int(taille_lot),
    taille_minimale_theme=int(taille_theme),
    echantillons_minimum=int(min_echantillon),
    voisins_umap=int(voisins),
    dimensions_umap=int(dimensions),
    ngram_maximal=int(ng_max),
    frequence_documentaire_minimale=int(freq_doc),
    vocabulaire_maximal=int(vocab_max),
    nombre_mots_theme=int(mots_theme),
    reduction_themes=reduction,
    nombre_themes_cible=int(cible),
    calculer_probabilites=bool(probabilites),
    graine=int(graine),
)
empreinte = hashlib.sha256(b"\0".join(contenus)).hexdigest()
configuration = {
    **asdict(parametres),
    "fichiers": [f.name for f in fichiers],
    "empreinte_sha256": empreinte,
    "limite_documents": int(plafond),
    "mots_vides_francais": bool(supprimer_fr),
    "mots_personnalises": autres_mots,
}
cle_calcul = hashlib.sha256(
    json.dumps(configuration, sort_keys=True, ensure_ascii=False).encode("utf-8")
).hexdigest()

if len(tableau) > int(plafond):
    st.warning(
        "Le corpus dépasse la limite retenue. Les documents hors échantillon seront "
        "conservés dans l'export, avec le statut non_analyse."
    )
if st.button("Lancer la découverte thématique", type="primary"):
    indices_non_vides = np.flatnonzero(tableau["texte"].str.strip().ne("").to_numpy())
    if len(indices_non_vides) < 5:
        st.error("Il faut au moins cinq textes non vides.")
        st.stop()
    generateur = np.random.default_rng(int(graine))
    if len(indices_non_vides) > int(plafond):
        indices_non_vides = np.sort(
            generateur.choice(indices_non_vides, size=int(plafond), replace=False)
        )
    if len(indices_non_vides) < int(taille_theme):
        st.error("La taille minimale d'un thème dépasse le nombre de textes analysables.")
        st.stop()
    textes = tableau.iloc[indices_non_vides]["texte"].tolist()
    if not VERROU_ENTRAINEMENT.acquire(blocking=False):
        st.error("Une analyse est déjà en cours sur le VPS. Réessayer après sa fin.")
        st.stop()
    barre = st.progress(0, text="Préparation de BERTopic")

    def progression(fraction: float, message: str) -> None:
        barre.progress(min(100, max(0, int(fraction * 100))), text=message)

    try:
        sortie = entrainer_bertopic(
            textes, parametres,
            charger_mots_vides(supprimer_fr, autres_mots),
            progression,
        )
        resultat = enrichir_documents(
            tableau, indices_non_vides, sortie["affectations"],
            sortie["confiances"], sortie["matrice_probabilites"],
            sortie["themes_probabilites"],
        )
        categories = {
            int(ligne.numero_document): str(ligne.theme_dominant)
            for ligne in resultat.itertuples(index=False)
        }
        iramuteq = exporter_iramuteq(documents, categories, "bertopic")
        configuration["documents_analyses"] = len(indices_non_vides)
        configuration["nombre_themes_trouves"] = sortie["nombre_themes"]
        configuration["documents_hors_theme"] = sortie["nombre_hors_theme"]
        configuration["version_bertopic"] = version("bertopic")
        archive = creer_archive(
            resultat, sortie["themes"], sortie["vocabulaire"],
            sortie["representatifs"], iramuteq, configuration,
        )
        st.session_state["bertopic_resultat"] = {
            "cle": cle_calcul,
            "resultat": resultat,
            "themes": sortie["themes"],
            "vocabulaire": sortie["vocabulaire"],
            "representatifs": sortie["representatifs"],
            "archive": archive,
            "effectif": len(indices_non_vides),
            "nombre_themes": sortie["nombre_themes"],
            "hors_theme": sortie["nombre_hors_theme"],
        }
    except Exception as erreur:
        st.error(f"Échec BERTopic : {type(erreur).__name__} : {erreur}")
        st.info(
            "En cas de vocabulaire vide, réduire la fréquence documentaire minimale "
            "ou désactiver les mots vides ; si tous les textes sont hors thème, "
            "réduire la taille minimale HDBSCAN et le nombre d'échantillons."
        )
    finally:
        VERROU_ENTRAINEMENT.release()
        barre.empty()

donnees = st.session_state.get("bertopic_resultat")
if donnees and donnees["cle"] == cle_calcul:
    a, b, c = st.columns(3)
    a.metric("Textes analysés", donnees["effectif"])
    b.metric("Thèmes découverts", donnees["nombre_themes"])
    c.metric("Textes hors thème (-1)", donnees["hors_theme"])
    if donnees["nombre_themes"] == 0:
        st.warning("Aucun thème identifié. Les textes restent exportables avec la modalité hors_theme.")
    st.subheader("Thèmes et mots caractéristiques")
    st.dataframe(donnees["themes"], use_container_width=True, hide_index=True)
    st.subheader("Répartition des textes")
    effectifs = donnees["resultat"].loc[
        donnees["resultat"]["statut_analyse"].ne("non_analyse"), "theme_dominant"
    ].value_counts().sort_index()
    st.bar_chart(effectifs, x_label="Thème", y_label="Nombre de textes")
    st.subheader("Affectations documentaires")
    st.dataframe(donnees["resultat"], use_container_width=True, hide_index=True)
    with st.expander("Mots pondérés par c-TF-IDF et textes représentatifs"):
        st.dataframe(donnees["vocabulaire"], use_container_width=True, hide_index=True)
        st.dataframe(donnees["representatifs"], use_container_width=True, hide_index=True)

    variables = sorted(
        colonne for colonne in donnees["resultat"].columns
        if colonne.startswith("variable_") and colonne != "variables_iramuteq"
    )
    if variables:
        st.subheader("Croisements avec les variables étoilées")
        variable = st.selectbox("Choisir la variable", variables)
        inclure_hors_theme = st.checkbox("Inclure les textes hors thème", value=True)
        effectifs, pourcentages = construire_croisement(
            donnees["resultat"], variable, inclure_hors_theme,
        )
        if not effectifs.empty:
            st.write("Effectifs observés")
            st.dataframe(effectifs, use_container_width=True)
            st.write("Pourcentages par modalité de la variable")
            st.dataframe(pourcentages, use_container_width=True)
            st.download_button(
                "Télécharger ce croisement (CSV)",
                exporter_csv(effectifs.reset_index()),
                file_name="croisement_bertopic.csv", mime="text/csv",
            )
            if effectifs.shape[0] >= 2 and effectifs.shape[1] >= 2:
                from scipy.stats import chi2_contingency
                try:
                    chi2, pvaleur, ddl, attendus = chi2_contingency(effectifs.to_numpy())
                    nombre = int(effectifs.to_numpy().sum())
                    cramer = np.sqrt(
                        chi2 / (nombre * min(effectifs.shape[0] - 1, effectifs.shape[1] - 1))
                    )
                    st.caption(
                        f"χ² = {chi2:.2f} ; ddl = {ddl} ; p = {pvaleur:.4g} ; "
                        f"V de Cramér = {cramer:.3f} ; N = {nombre}."
                    )
                    if np.any(attendus < 5):
                        st.warning("Effectifs théoriques < 5 : interpréter le χ² avec prudence.")
                except ValueError as erreur:
                    st.warning(f"Test χ² impossible : {erreur}")
    st.download_button(
        "Télécharger tous les résultats (ZIP)",
        donnees["archive"], file_name="resultats_bertopic_iramuteq.zip",
        mime="application/zip",
    )
elif donnees:
    st.info("Le corpus ou les paramètres ont changé : relancer l'analyse pour actualiser les résultats.")
