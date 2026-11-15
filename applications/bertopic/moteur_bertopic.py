"""Découverte thématique BERTopic sur CPU pour corpus IRaMuTeQ."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MODELE_PLURILINGUE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELE_ALTERNATIF = "sentence-transformers/distiluse-base-multilingual-cased-v2"
MODELE_ANGLOPHONE = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class ParametresBERTopic:
    """Paramètres de regroupement et de représentation thématique."""

    modele_encodeur: str = MODELE_PLURILINGUE
    taille_lot: int = 16
    taille_minimale_theme: int = 10
    echantillons_minimum: int = 5
    voisins_umap: int = 15
    dimensions_umap: int = 5
    ngram_maximal: int = 2
    frequence_documentaire_minimale: int = 2
    vocabulaire_maximal: int = 10000
    nombre_mots_theme: int = 12
    reduction_themes: str = "aucune"
    nombre_themes_cible: int = 10
    calculer_probabilites: bool = False
    graine: int = 42


def entrainer_bertopic(
    textes: list[str],
    parametres: ParametresBERTopic,
    mots_vides: list[str],
    progression=None,
) -> dict[str, object]:
    """Entraîner BERTopic et exporter ses vraies sorties, sans substitution de modèle."""
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    if len(textes) < 5 or any(not texte.strip() for texte in textes):
        raise ValueError("Fournir au moins cinq textes non vides.")
    if parametres.taille_minimale_theme > len(textes):
        raise ValueError("La taille minimale des thèmes dépasse la taille de l'échantillon.")

    def notifier(valeur: float, message: str) -> None:
        if progression is not None:
            progression(valeur, message)

    notifier(0.05, "Chargement de l'encodeur multilingue")
    encodeur = SentenceTransformer(parametres.modele_encodeur, device="cpu")
    notifier(0.15, "Calcul des représentations sémantiques des documents")
    embeddings = encodeur.encode(
        textes,
        batch_size=parametres.taille_lot,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    voisins = min(max(2, parametres.voisins_umap), len(textes) - 1)
    reduction = UMAP(
        n_neighbors=voisins,
        n_components=parametres.dimensions_umap,
        min_dist=0.0,
        metric="cosine",
        random_state=parametres.graine,
        low_memory=True,
    )
    classification = HDBSCAN(
        min_cluster_size=parametres.taille_minimale_theme,
        min_samples=min(parametres.echantillons_minimum, parametres.taille_minimale_theme),
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    vectoriseur = CountVectorizer(
        ngram_range=(1, parametres.ngram_maximal),
        min_df=parametres.frequence_documentaire_minimale,
        max_features=parametres.vocabulaire_maximal,
        stop_words=sorted(set(mots_vides)) or None,
        token_pattern=r"(?u)\b[\wÀ-ÿ]{2,}\b",
        lowercase=True,
    )
    choix_reduction = {
        "aucune": None, "automatique": "auto", "nombre_fixe": parametres.nombre_themes_cible
    }[parametres.reduction_themes]
    modele = BERTopic(
        embedding_model=encodeur,
        umap_model=reduction,
        hdbscan_model=classification,
        vectorizer_model=vectoriseur,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        top_n_words=parametres.nombre_mots_theme,
        nr_topics=choix_reduction,
        calculate_probabilities=parametres.calculer_probabilites,
        low_memory=True,
        verbose=False,
    )
    notifier(0.55, "Réduction UMAP, regroupement HDBSCAN et représentation c-TF-IDF")
    affectations, probabilites = modele.fit_transform(textes, embeddings=embeddings)
    notifier(0.90, "Construction des sorties et des thèmes représentatifs")
    info_documents = modele.get_document_info(textes)
    if "Probability" in info_documents:
        confiances = pd.to_numeric(info_documents["Probability"], errors="coerce").tolist()
    elif probabilites is not None and np.asarray(probabilites).ndim == 1:
        confiances = np.asarray(probabilites, dtype=float).tolist()
    else:
        confiances = [float("nan")] * len(textes)

    # Une colonne correspond à chaque identifiant positif, dans l'ordre des thèmes.
    identifiants = sorted({int(numero) for numero in affectations if int(numero) >= 0})
    matrice = None
    if parametres.calculer_probabilites and probabilites is not None:
        candidate = np.asarray(probabilites, dtype=float)
        if candidate.ndim == 2 and candidate.shape == (len(textes), len(identifiants)):
            matrice = candidate

    resume: list[dict[str, object]] = []
    vocabulaire: list[dict[str, object]] = []
    representatifs: list[dict[str, object]] = []
    exemples = modele.get_representative_docs() or {}
    for enregistrement in modele.get_topic_info().itertuples(index=False):
        numero = int(enregistrement.Topic)
        termes = modele.get_topic(numero) or []
        termes = [(str(mot), float(poids)) for mot, poids in termes]
        mots = ", ".join(mot for mot, _ in termes)
        resume.append({
            "identifiant_theme": numero,
            "theme_dominant": "hors_theme" if numero == -1 else f"theme_{numero:02d}",
            "nombre_documents": int(enregistrement.Count),
            "mots_caracteristiques": mots,
        })
        for position, (mot, poids) in enumerate(termes, 1):
            vocabulaire.append({
                "identifiant_theme": numero, "rang": position,
                "terme": mot, "poids_ctfidf": poids,
            })
        for rang, texte in enumerate(exemples.get(numero, []), 1):
            representatifs.append({
                "identifiant_theme": numero, "rang": rang, "texte_representatif": texte
            })
    notifier(1.0, "Analyse terminée")
    return {
        "affectations": [int(numero) for numero in affectations],
        "confiances": confiances,
        "matrice_probabilites": matrice,
        "themes_probabilites": identifiants if matrice is not None else [],
        "themes": pd.DataFrame(resume),
        "vocabulaire": pd.DataFrame(vocabulaire),
        "representatifs": pd.DataFrame(representatifs),
        "nombre_hors_theme": sum(numero == -1 for numero in affectations),
        "nombre_themes": len(identifiants),
    }
