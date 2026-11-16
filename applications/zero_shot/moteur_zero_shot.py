"""Classification zero-shot multilingue par inférence textuelle sur CPU."""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from typing import Any

MODELE_DEFAUT = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
NOMBRE_CATEGORIES_MAX = 30


def preparer_categories(texte: str, multilabel: bool = True) -> list[str]:
    """Nettoyer des étiquettes libres sans imposer de vocabulaire thématique."""
    categories = []
    deja_vues = set()
    for ligne in texte.splitlines():
        etiquette = " ".join(ligne.strip().split())
        if not etiquette or etiquette.startswith("#"):
            continue
        if len(etiquette) > 120:
            raise ValueError(f"Une catégorie dépasse 120 caractères : {etiquette[:60]}")
        cle = etiquette.casefold()
        if cle not in deja_vues:
            categories.append(etiquette)
            deja_vues.add(cle)
    if len(categories) > NOMBRE_CATEGORIES_MAX:
        raise ValueError(f"Maximum : {NOMBRE_CATEGORIES_MAX} catégories.")
    if not categories:
        raise ValueError("Saisissez au moins une catégorie, une par ligne.")
    if not multilabel and len(categories) < 2:
        raise ValueError("Le mode exclusif exige au moins deux catégories.")
    return categories


def verifier_hypothese(modele_phrase: str) -> str:
    """Contrôler la phrase d'hypothèse soumise au modèle NLI."""
    modele_phrase = modele_phrase.strip()
    if modele_phrase.count("{}") != 1:
        raise ValueError("La phrase d'hypothèse doit contenir exactement un {}.")
    if len(modele_phrase) > 350:
        raise ValueError("La phrase d'hypothèse ne peut pas dépasser 350 caractères.")
    return modele_phrase


def identifiant_categorie(etiquette: str) -> str:
    """Produire un identifiant IRaMuTeQ stable pour chaque catégorie."""
    normalisee = unicodedata.normalize("NFKD", etiquette)
    ascii_texte = normalisee.encode("ascii", errors="ignore").decode("ascii").lower()
    racine = re.sub(r"[^a-z0-9]+", "_", ascii_texte).strip("_")[:35] or "categorie"
    empreinte = hashlib.sha256(etiquette.encode("utf-8")).hexdigest()[:8]
    return f"{racine}_{empreinte}"


def charger_classifieur(identifiant_modele: str = MODELE_DEFAUT):
    """Charger un modèle NLI en mémoire uniquement à la première analyse."""
    import torch
    from transformers import pipeline

    torch.set_num_threads(max(1, min(2, os.cpu_count() or 2)))
    return pipeline(
        task="zero-shot-classification",
        model=identifiant_modele,
        tokenizer=identifiant_modele,
        device=-1,
    )


def classifier_textes(
    classifieur: Any,
    textes: list[str],
    categories: list[str],
    hypothese: str,
    multilabel: bool,
    seuil: float,
) -> list[dict[str, Any]]:
    """Analyser plusieurs textes sans changer leurs positions d'origine.

    Les scores sont des scores du modèle, non des probabilités calibrées
    de justesse. Une catégorie sous le seuil n'est pas attribuée.
    """
    if not textes:
        return []
    sortie = classifieur(
        textes,
        candidate_labels=categories,
        hypothesis_template=verifier_hypothese(hypothese),
        multi_label=bool(multilabel),
        batch_size=4,
        truncation=True,
    )
    if isinstance(sortie, dict):
        sortie = [sortie]
    if len(sortie) != len(textes):
        raise RuntimeError(
            "Le modèle n'a pas retourné autant de résultats que de textes analysés."
        )
    resultats = []
    for resultat in sortie:
        scores = {
            str(etiquette): float(score)
            for etiquette, score in zip(resultat["labels"], resultat["scores"])
        }
        if any(categorie not in scores for categorie in categories):
            raise ValueError("Le modèle a omis une catégorie.")
        meilleur = max(categories, key=lambda categorie: scores[categorie])
        score_maximum = scores[meilleur]
        if multilabel:
            retenues = [
                categorie for categorie in categories if scores[categorie] >= seuil
            ]
        else:
            retenues = [meilleur] if score_maximum >= seuil else []
        resultats.append({
            "scores": {categorie: scores[categorie] for categorie in categories},
            "categorie_principale": meilleur if retenues else "indetermine",
            "categorie_mieux_classee": meilleur,
            "score_maximum": score_maximum,
            "categories_retenues": retenues,
        })
    return resultats


def exporter_documents_iramuteq(documents, tableau, categories: list[str]) -> bytes:
    """Exporter les métadonnées originelles et les catégories retenues."""
    index = {int(ligne["numero_document"]): ligne for _, ligne in tableau.iterrows()}
    identifiants = {categorie: identifiant_categorie(categorie) for categorie in categories}
    parties = []
    for document in documents:
        resultat = index.get(document.numero)
        statut = str(resultat["statut_analyse"]) if resultat is not None else "non_traite"
        categorie_principale = (
            str(resultat["categorie_principale"])
            if resultat is not None and statut == "ok" else "indetermine"
        )
        valeur_principale = identifiants.get(categorie_principale, "indetermine")
        entete = (
            document.entete
            + f" *zs_statut_{statut}"
            + f" *zs_principale_{valeur_principale}"
        )
        if resultat is not None and statut == "ok":
            for position, categorie in enumerate(categories, start=1):
                valeur = resultat.get(f"classe_{position:02d}")
                if valeur is not None and str(valeur).lower() in ("true", "1", "oui"):
                    entete += f" *zs_{identifiants[categorie]}_oui"
        parties.append(entete + "\n" + document.texte)
    return ("\n\n".join(parties) + "\n").encode("utf-8")
