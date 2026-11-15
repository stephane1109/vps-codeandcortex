"""Interface Streamlit pour une reproduction expérimentale de DARTopic."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import threading
import zipfile

import numpy as np
import pandas as pd
import streamlit as st

from lecture_iramuteq import analyser_corpus, exporter_csv, exporter_iramuteq, tableau_documents
from lecture_commentaires import analyser_commentaires_csv
from detection_langue import detecter_langues
from modele_dartopic import MODELE_PLURILINGUE, ParametresDARTopic, entrainer_dartopic

st.set_page_config(page_title="DARTopic — IRaMuTeQ et CSV", layout="wide")


@st.cache_resource(show_spinner=False)
def obtenir_verrou() -> threading.Lock:
    """Empêcher les entraînements concurrents sur ce processus VPS."""
    return threading.Lock()


VERROU_ENTRAINEMENT = obtenir_verrou()


def authentifier() -> None:
    """Empêcher l'entraînement public non autorisé sur le VPS."""
    mot_de_passe = os.getenv("APP_PASSWORD", "")
    if not mot_de_passe:
        if os.getenv("APP_ALLOW_PUBLIC", "0") != "1":
            st.error("Configuration manquante : renseigner APP_PASSWORD dans Coolify.")
            st.stop()
        st.warning("Mode public activé explicitement : APP_ALLOW_PUBLIC=1.")
        return
    saisie = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(saisie.encode("utf-8"), mot_de_passe.encode("utf-8")):
        st.stop()


NEGATIONS_A_CONSERVER = frozenset({
    "ne", "n", "n'", "pas", "plus", "jamais", "aucun", "aucune",
    "ni", "rien", "personne", "non", "sans", "nul", "nulle",
})


def charger_mots_vides(
    personnalises: str, supprimer: bool, conserver_negations: bool = False
) -> list[str]:
    """Charger NLTK français, avec conservation facultative des négations."""
    mots = set()
    if supprimer:
        try:
            from nltk.corpus import stopwords
            mots.update(stopwords.words("french"))
        except LookupError as erreur:
            raise RuntimeError(
                "La liste NLTK française n'est pas installée. "
                "Vérifier l'installation des données NLTK dans Docker."
            ) from erreur
        if conserver_negations:
            mots.difference_update(NEGATIONS_A_CONSERVER)
    # Les exclusions manuelles restent prioritaires, même pour une négation.
    mots.update(mot.strip().lower() for mot in personnalises.splitlines() if mot.strip())
    return sorted(mots)


def construire_archive(resultats: pd.DataFrame, themes: pd.DataFrame, historique: pd.DataFrame,
                       sortie_iramuteq: bytes, configuration: dict[str, object],
                       bilan_langues: pd.DataFrame | None = None) -> bytes:
    """Regrouper les résultats textuels et la provenance méthodologique."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("documents_themes.csv", exporter_csv(resultats))
        archive.writestr("themes_mots.csv", exporter_csv(themes))
        archive.writestr("historique_entrainement.csv", exporter_csv(historique))
        if bilan_langues is not None:
            archive.writestr("bilan_langues.csv", exporter_csv(bilan_langues))
        archive.writestr("corpus_themes_iramuteq.txt", sortie_iramuteq)
        archive.writestr("parametres.json", json.dumps(configuration, indent=2, ensure_ascii=False))
    return tampon.getvalue()


authentifier()
st.title("DARTopic — découverte des thèmes")
st.caption("Reproduction expérimentale non officielle de Seo, Cho et Yoo (2026), adaptée au français ; résultats à valider sur le corpus.")
st.info("DARTopic découvre des thèmes latents ; il ne détermine pas directement si un commentaire dénonce ou justifie la violence. Les thèmes doivent être interprétés par le chercheur.")

st.caption(
    "Importer des commentaires CSV (colonnes nom_affiche et texte) ou des corpus IRaMuTeQ. "
    "Le nom affiché et le texte des commentaires sont conservés sans réécriture."
)
fichiers = st.file_uploader(
    "Importer un ou plusieurs fichiers CSV de commentaires ou TXT IRaMuTeQ",
    type=["csv", "txt"], accept_multiple_files=True,
)
if not fichiers:
    st.stop()
try:
    from dataclasses import replace

    documents = []
    metadonnees = {}
    for fichier in fichiers:
        nom_fichier = fichier.name
        if nom_fichier.lower().endswith(".csv"):
            nouveaux, informations = analyser_commentaires_csv(
                fichier.getvalue(), numero_depart=len(documents)
            )
            documents.extend(nouveaux)
            for numero, infos in informations.items():
                metadonnees[numero] = {
                    **infos, "fichier_source": nom_fichier,
                    "format_source": "csv_commentaires",
                }
        else:
            nouveaux = analyser_corpus(fichier.getvalue())
            depart = len(documents)
            documents.extend(
                replace(doc, numero=depart + indice + 1)
                for indice, doc in enumerate(nouveaux)
            )
            for doc in documents[depart:]:
                metadonnees[doc.numero] = {
                    "nom_affiche": "", "fichier_source": nom_fichier,
                    "format_source": "iramuteq",
                }
    tableau = tableau_documents(documents)
    for colonne in ("nom_affiche", "fichier_source", "format_source", "ligne_csv"):
        tableau[colonne] = [
            metadonnees.get(int(numero), {}).get(colonne, "")
            for numero in tableau["numero_document"]
        ]
except (ValueError, UnicodeError) as erreur:
    st.error(str(erreur))
    st.stop()

textes_non_vides = int(tableau["texte"].str.strip().ne("").sum())
st.write(
    f"Documents importés : **{len(documents)}** ; "
    f"textes non vides : **{textes_non_vides}** ; "
    f"textes vides : **{len(documents) - textes_non_vides}**"
)
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
        frequence_maximale = st.slider(
            "Fréquence documentaire maximale (proportion)", 0.50, 1.00, 0.95, 0.01,
            help="Exclut du vocabulaire les termes présents dans trop de documents. "
                 "Ne concerne pas l'encodeur sémantique.",
        )
    with colonne_3:
        seuil = st.slider("Seuil de similarité entre tokens", 0.0, 0.9, 0.2, 0.05)
        poids_kl = st.slider(
            "Poids de régularisation KL", 0.0, 0.5, 0.02, 0.01,
            help="Une régularisation trop forte peut uniformiser les thèmes.",
        )
        poids_ancrage = st.slider(
            "Ancrage lexical non supervisé NMF", 0.0, 2.0, 0.8, 0.1,
            help="Initialise les thèmes avec NMF et guide l'encodeur pour limiter "
                 "l'effondrement thématique ; adaptation expérimentale non officielle.",
        )
        graine = st.number_input("Graine aléatoire", 0, 999999, 42)
    choix_encodeur = st.selectbox(
        "Encodeur contextuel figé",
        [MODELE_PLURILINGUE, "sentence-transformers/all-MiniLM-L6-v2"],
        help="Le modèle multilingue est conseillé pour le français. L'encodeur anglophone reproduit plus étroitement le protocole de l'article."
    )
    retirer_mots_vides = st.checkbox(
        "Exclure les stopwords français NLTK du vocabulaire lexical", value=True,
        help="NLTK fournit la liste française. L'encodeur sémantique reçoit toujours les textes complets.",
    )
    conserver_negations = st.checkbox(
        "Conserver les négations (ne, pas, jamais, plus, rien, non...)",
        value=False, disabled=not retirer_mots_vides,
        help="Utile pour l'analyse des prises de position. Décochez pour retrouver le filtrage NLTK intégral.",
    )
    mots_sup = st.text_area("Mots exclus supplémentaires (un par ligne)", height=80)
    taille_echantillon = st.number_input(
        "Nombre maximal de textes analysés (échantillon reproductible)",
        min_value=5, max_value=30000, value=30000, step=100,
    )

with st.expander("Filtrage de la langue des commentaires", expanded=True):
    filtre_francais = st.checkbox(
        "Exclure les commentaires identifiés comme non francophones",
        value=True,
        help="Détection automatique Lingua avant échantillonnage. "
             "Une langue indéterminée reste distinguée d'une langue étrangère.",
    )
    conserver_indetermines = st.checkbox(
        "Conserver les commentaires dont la langue est indéterminée",
        value=True, disabled=not filtre_francais,
        help="Conseillé pour les commentaires très courts, les fautes et les sigles.",
    )
    minimum_lettres = st.number_input(
        "Nombre minimal de lettres pour détecter la langue",
        min_value=5, max_value=100, value=12,
        disabled=not filtre_francais,
    )
    seuil_confiance = st.slider(
        "Confiance relative minimale du détecteur", 0.50, 0.99, 0.65, 0.01,
        disabled=not filtre_francais,
        help="La confiance relative Lingua n'est pas une probabilité calibrée.",
    )
    seuil_ecart = st.slider(
        "Écart minimal entre les deux langues candidates",
        0.0, 0.5, 0.15, 0.01, disabled=not filtre_francais,
    )
    st.caption(
        "Les commentaires exclus restent dans l'archive, avec leur texte, "
        "leur auteur et le statut non_analyse_langue. "
        "La détection peut se tromper sur les textes très courts."
    )

try:
    mots_vides = charger_mots_vides(mots_sup, retirer_mots_vides, conserver_negations)
except RuntimeError as erreur:
    st.error(str(erreur))
    st.stop()
with st.expander(f"Liste effective des mots exclus du vocabulaire ({len(mots_vides)})"):
    st.write(", ".join(mots_vides) if mots_vides else "Aucun mot exclu.")
    st.caption("Ces mots restent présents dans les textes transmis au Transformer ; seule la matrice lexicale est filtrée.")

if len(documents) > 30000:
    st.warning(
        "Au maximum 30 000 textes admissibles seront analysés ; les autres "
        "resteront dans les exports, avec le statut non_analyse."
    )
if taille_echantillon > 10000:
    st.warning(
        "Analyse volumineuse sur CPU : le calcul de 30 000 textes peut être très long. "
        "Les embeddings et les graphes utilisent temporairement plusieurs Go de disque. "
        "Évitez de lancer Qwen ou BERTopic en parallèle."
    )

empreinte = hashlib.sha256(b"\0".join(f.getvalue() for f in fichiers)).hexdigest()
parametres = ParametresDARTopic(
    nombre_themes=int(nombre_themes), nombre_epoques=int(nombre_epoques), taille_lot=int(taille_lot),
    longueur_maximale=int(longueur), taille_vocabulaire=int(taille_vocabulaire),
    frequence_minimale=int(frequence_minimale),
    frequence_maximale=float(frequence_maximale),
    seuil_similarite=float(seuil), poids_kl=float(poids_kl),
    poids_ancrage=float(poids_ancrage),
    graine=int(graine), modele_encodeur=choix_encodeur,
)
configuration = {**parametres.__dict__, "fichiers": [f.name for f in fichiers],
                 "empreinte_sha256": empreinte, "max_documents": int(taille_echantillon),
                 "mots_vides_francais": bool(retirer_mots_vides), "mots_exclus_supplementaires": mots_sup,
                 "conserver_negations": bool(conserver_negations),
                 "stopwords_source": "NLTK - français", "nombre_stopwords": len(mots_vides),
                 "filtre_francais": bool(filtre_francais),
                 "conserver_langue_indeterminee": bool(conserver_indetermines),
                 "langue_minimum_lettres": int(minimum_lettres),
                 "langue_seuil_confiance": float(seuil_confiance),
                 "langue_seuil_ecart": float(seuil_ecart),
                 "langue_methode": "Lingua (14 langues candidates, détection probabiliste)"}
cle_calcul = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode("utf-8")).hexdigest()

if st.button("Lancer la découverte thématique", type="primary"):
    analyse = tableau.copy()
    analyse["langue_detectee"] = "non_controle"
    analyse["statut_langue"] = "non_controle"
    analyse["confiance_langue"] = np.nan
    analyse["ecart_langue"] = np.nan
    analyse["statut_analyse"] = "non_analyse"
    masque_non_vides = analyse["texte"].str.strip().ne("").to_numpy()

    if filtre_francais:
        barre_langue = st.progress(0, text="Détection linguistique")
        try:
            informations_langue = detecter_langues(
                analyse["texte"].tolist(),
                minimum_lettres=int(minimum_lettres),
                seuil_confiance=float(seuil_confiance),
                seuil_ecart=float(seuil_ecart),
                progression=lambda fraction, message: barre_langue.progress(
                    min(100, int(fraction * 100)), text=message
                ),
            )
        except Exception as erreur:
            st.error(
                f"Échec du filtrage linguistique : {type(erreur).__name__} : {erreur}"
            )
            st.stop()
        finally:
            barre_langue.empty()
        for colonne in (
            "langue_detectee", "statut_langue",
            "confiance_langue", "ecart_langue",
        ):
            analyse[colonne] = [ligne[colonne] for ligne in informations_langue]
        autorises = analyse["statut_langue"].eq("francais").to_numpy()
        if conserver_indetermines:
            autorises |= analyse["statut_langue"].eq("indetermine").to_numpy()
        exclus_langue = masque_non_vides & ~autorises
        analyse.loc[exclus_langue, "statut_analyse"] = "non_analyse_langue"
        indices_utiles = np.flatnonzero(masque_non_vides & autorises)
    else:
        indices_utiles = np.flatnonzero(masque_non_vides)
        exclus_langue = np.zeros(len(analyse), dtype=bool)

    total_admissibles = len(indices_utiles)
    if total_admissibles < max(5, int(nombre_themes)):
        st.error(
            "Nombre de commentaires admissibles insuffisant après le filtrage. "
            "Conservez les langues indéterminées ou réduisez le nombre de thèmes."
        )
        st.stop()
    generateur = np.random.default_rng(int(graine))
    if total_admissibles > int(taille_echantillon):
        indices_utiles = np.sort(
            generateur.choice(
                indices_utiles, size=int(taille_echantillon), replace=False
            )
        )
    textes = analyse.iloc[indices_utiles]["texte"].tolist()
    st.info(
        f"Textes admissibles : {total_admissibles} ; "
        f"exclus par langue : {int(exclus_langue.sum())} ; "
        f"retenus pour l'analyse : {len(indices_utiles)}."
    )
    barre = st.progress(0, text="Préparation du calcul")

    def progression(fraction: float, message: str) -> None:
        barre.progress(min(100, max(0, int(fraction * 100))), text=message)

    if not VERROU_ENTRAINEMENT.acquire(blocking=False):
        st.error("Un entraînement DARTopic est déjà en cours sur le VPS.")
        st.stop()
    try:
        sortie = entrainer_dartopic(textes, parametres, progression, mots_vides)
    except Exception as erreur:
        st.error(f"Échec du calcul : {type(erreur).__name__} : {erreur}")
        st.stop()
    finally:
        VERROU_ENTRAINEMENT.release()
        barre.empty()

    resultat = analyse.copy()
    resultat["theme_dominant"] = np.where(
        resultat["statut_analyse"].eq("non_analyse_langue"),
        "non_analyse_langue", "non_analyse",
    )
    resultat["probabilite_theme"] = np.nan
    distribution = sortie["distribution"]
    dominants = np.argmax(distribution, axis=1) + 1
    resultat.loc[indices_utiles, "theme_dominant"] = [
        f"theme_{k:02d}" for k in dominants
    ]
    resultat.loc[indices_utiles, "statut_analyse"] = "analyse"
    resultat.loc[indices_utiles, "probabilite_theme"] = np.max(
        distribution, axis=1
    )
    for k in range(distribution.shape[1]):
        colonne = f"probabilite_theme_{k+1:02d}"
        resultat[colonne] = np.nan
        resultat.loc[indices_utiles, colonne] = distribution[:, k]
    themes = pd.DataFrame([
        {cle: valeur for cle, valeur in theme.items()
         if cle not in {"probabilite_mots", "mots_liste"}}
        for theme in sortie["themes"]
    ])
    historique = pd.DataFrame(sortie["historique"])
    categories = {
        int(ligne.numero_document): str(ligne.theme_dominant)
        for ligne in resultat.itertuples(index=False)
    }
    texte_export = exporter_iramuteq(documents, categories, "dartopic")
    bilan_langues = (
        resultat["statut_langue"].value_counts(dropna=False)
        .rename_axis("statut_langue").reset_index(name="nombre_documents")
    )
    configuration["documents_analyses"] = len(indices_utiles)
    configuration["documents_admissibles"] = total_admissibles
    configuration["documents_exclus_langue"] = int(exclus_langue.sum())
    configuration["diagnostic_themes"] = sortie["diagnostic"]
    configuration["statut_implementation"] = (
        "GCN-VAE expérimental avec initialisation et ancrage NMF, non officiel"
    )
    archive = construire_archive(
        resultat, themes, historique, texte_export, configuration,
        bilan_langues=bilan_langues,
    )
    st.session_state["dartopic_resultat"] = (
        cle_calcul, resultat, themes, historique, archive,
        sortie["diagnostic"], bilan_langues,
    )

stockage = st.session_state.get("dartopic_resultat")
if stockage and stockage[0] == cle_calcul:
    _, resultat, themes, historique, archive, diagnostic, bilan_langues = stockage
    st.subheader("Bilan du filtrage linguistique")
    st.dataframe(bilan_langues, hide_index=True, use_container_width=True)
    st.subheader("Diagnostic de la différenciation thématique")
    a, b = st.columns(2)
    a.metric("Chevauchement moyen des 15 mots distinctifs", f"{diagnostic['chevauchement_moyen_mots']:.1%}")
    b.metric("Thèmes sans attribution dominante", diagnostic["themes_sans_document_dominant"])
    if diagnostic["alerte_themes_similaires"]:
        st.error(
            "Les thèmes restent insuffisamment différenciés. "
            "Évitez de les interpréter comme des classes sociologiques ; "
            "essayez moins de thèmes et comparez avec BERTopic."
        )
    st.subheader("Thèmes découverts")
    st.dataframe(themes, hide_index=True, use_container_width=True)
    effectifs = resultat.loc[
        resultat["statut_analyse"].eq("analyse"), "theme_dominant"
    ].value_counts().sort_index()
    st.bar_chart(effectifs, x_label="Thème", y_label="Nombre de textes")
    st.subheader("Affectations et incertitude")
    st.dataframe(resultat.head(2000), hide_index=True, use_container_width=True)
    if len(resultat) > 2000:
        st.caption("Aperçu limité aux 2 000 premiers documents ; le ZIP contient tous les documents.")
    st.subheader("Historique de l'entraînement")
    st.line_chart(historique.set_index("epoque"))
    variables = [
        colonne for colonne in resultat
        if colonne.startswith("variable_") and colonne != "variables_iramuteq"
    ]
    variables.extend(["nom_affiche", "fichier_source", "format_source"])
    if variables:
        variable = st.selectbox("Croiser les thèmes avec une variable étoilée ou une colonne CSV", variables)
        st.dataframe(pd.crosstab(resultat[variable].fillna("absent"), resultat["theme_dominant"]), use_container_width=True)
    st.download_button("Télécharger tous les résultats (ZIP)", archive,
                       file_name="resultats_dartopic_iramuteq.zip", mime="application/zip")
elif stockage:
    st.info("Les paramètres ont changé ; relancer le calcul pour actualiser les résultats.")
