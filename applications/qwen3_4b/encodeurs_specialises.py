"""Service local d'encodage et d'inférence textuelle pour les SHS.

JuriBERT et BERTweetFR servent aux similarités exploratoires.
Un réseau NLI indépendant assure la classification zero-shot.
"""
from __future__ import annotations

import gc
import threading
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

torch.set_num_threads(2)

MODELES_SPECIALISES = {
    "juribert": "dascim/juribert-base",
    "bertweetfr": "Yanzhu/bertweetfr-base",
}
MODELE_NLI = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
MODELES_DISPONIBLES = {**MODELES_SPECIALISES, "nli_multilingue": MODELE_NLI}

application = FastAPI(title="Analyse spécialisée SHS")
_verrou_inference = threading.Lock()
_nom_reseau_charge: str | None = None
_tokeniseur_charge: Any = None
_reseau_charge: Any = None


class DemandeComparaison(BaseModel):
    """Décrire le texte et les thèmes choisis par le chercheur."""

    modele: str
    texte: str = Field(min_length=1, max_length=12000)
    themes: list[dict[str, str]] = Field(min_length=1, max_length=8)


def charger_reseau(nom_modele: str):
    """Ne conserver qu'un seul réseau spécialisé en mémoire vive."""
    global _nom_reseau_charge, _tokeniseur_charge, _reseau_charge
    if nom_modele not in MODELES_DISPONIBLES:
        raise ValueError("Modèle spécialisé inconnu.")
    if nom_modele == _nom_reseau_charge and _reseau_charge is not None:
        return _tokeniseur_charge, _reseau_charge

    _nom_reseau_charge = None
    _tokeniseur_charge = None
    _reseau_charge = None
    gc.collect()

    depot = MODELES_DISPONIBLES[nom_modele]
    tokeniseur = AutoTokenizer.from_pretrained(depot, local_files_only=True)
    if nom_modele == "nli_multilingue":
        reseau = AutoModelForSequenceClassification.from_pretrained(
            depot, local_files_only=True
        )
    else:
        reseau = AutoModel.from_pretrained(depot, local_files_only=True)
    reseau.eval()
    _nom_reseau_charge = nom_modele
    _tokeniseur_charge = tokeniseur
    _reseau_charge = reseau
    return tokeniseur, reseau


def encoder_textes(textes: list[str], tokeniseur, modele) -> torch.Tensor:
    """Calculer les représentations brutes, sans prétendre classer les thèmes."""
    entrees = tokeniseur(
        textes, return_tensors="pt", truncation=True,
        padding=True, max_length=256,
    )
    with torch.inference_mode():
        sorties = modele(**entrees).last_hidden_state
        masque = entrees["attention_mask"].unsqueeze(-1)
        vecteurs = (sorties * masque).sum(dim=1) / masque.sum(dim=1).clamp(min=1)
        return torch.nn.functional.normalize(vecteurs, dim=1)


def formuler_hypothese(theme: dict[str, str]) -> str:
    """Transformer une définition de grille en hypothèse NLI française."""
    titre = theme["titre"].strip()
    definition = theme["definition"].strip()
    # Les définitions provisoires générées automatiquement sont trop générales.
    if definition.casefold().startswith(
        "le texte comporte un indice explicite relevant du thème"
    ):
        return f"Ce message exprime explicitement le thème « {titre} »."
    if definition.casefold().startswith("le texte "):
        return "Ce message " + definition[9:].rstrip(".") + "."
    return (
        f"Ce message relève du thème « {titre} » : "
        f"{definition.rstrip('.')}."
    )


def evaluer_inferences(texte: str, themes: list[dict[str, str]],
                      tokeniseur, modele) -> tuple[list[dict[str, object]], bool]:
    """Estimer indépendamment trois relations NLI pour chaque thème."""
    labels = {
        str(nom).casefold(): int(indice)
        for nom, indice in modele.config.label2id.items()
    }
    if any(nom not in labels for nom in (
        "entailment", "neutral", "contradiction"
    )):
        raise ValueError("Le modèle NLI ne possède pas les trois classes attendues.")

    evaluations: list[dict[str, object]] = []
    tronque = False
    for theme in themes:
        hypothese = formuler_hypothese(theme)
        longueur = len(tokeniseur(
            texte, hypothese, truncation=False
        )["input_ids"])
        tronque |= longueur > 320
        arguments = tokeniseur(
            texte, hypothese, truncation="only_first",
            max_length=320, return_tensors="pt",
        )
        with torch.inference_mode():
            logits = modele(**arguments).logits[0]
            probabilites = torch.softmax(logits, dim=-1).tolist()
        noms = ("entailment", "neutral", "contradiction")
        meilleur = max(noms, key=lambda nom: probabilites[labels[nom]])
        evaluations.append({
            "theme": theme["titre"],
            "hypothese": hypothese,
            "implication": round(float(probabilites[labels["entailment"]]), 6),
            "neutralite": round(float(probabilites[labels["neutral"]]), 6),
            "contradiction": round(float(probabilites[labels["contradiction"]]), 6),
            "relation_predite": {
                "entailment": "implication",
                "neutral": "neutralite",
                "contradiction": "contradiction",
            }[meilleur],
        })
    return evaluations, tronque


@application.get("/modeles")
def verifier_modeles() -> dict[str, object]:
    """Inventorier les réseaux configurés sans déclencher d'inférence."""
    return {"modeles": MODELES_DISPONIBLES}


@application.post("/similarites")
def calculer_similarites(demande: DemandeComparaison) -> dict[str, object]:
    """Produire les cosinus uniquement avec JuriBERT ou BERTweetFR."""
    if demande.modele not in MODELES_SPECIALISES:
        raise HTTPException(status_code=400, detail="Encodeur inconnu.")
    if any(not theme.get("titre") or not theme.get("definition")
           for theme in demande.themes):
        raise HTTPException(status_code=400, detail="Thèmes incomplets.")
    try:
        with _verrou_inference:
            tokeniseur, modele = charger_reseau(demande.modele)
            descriptions = [
                f"{theme['titre']}. {theme['definition']}"
                for theme in demande.themes
            ]
            vecteurs = encoder_textes(
                [demande.texte, *descriptions], tokeniseur, modele
            )
            similarites = torch.matmul(vecteurs[1:], vecteurs[0]).tolist()
            tronque = len(tokeniseur(demande.texte)["input_ids"]) > 256
    except (OSError, ValueError, RuntimeError) as erreur:
        raise HTTPException(
            status_code=503,
            detail=f"Encodeur {demande.modele} indisponible : {erreur}.",
        ) from erreur

    return {
        "modele": demande.modele,
        "depot": MODELES_SPECIALISES[demande.modele],
        "scores": [
            {"theme": theme["titre"], "similarite_cosinus": round(float(score), 4)}
            for theme, score in zip(demande.themes, similarites)
        ],
        "nature_scores": (
            "Similarités cosinus de représentations brutes : "
            "ne constituent pas une classification."
        ),
        "texte_tronque": tronque,
    }


@application.post("/inferences")
def calculer_inferences(demande: DemandeComparaison) -> dict[str, object]:
    """Évaluer les thèmes par un vrai modèle NLI, distinct des encodeurs."""
    if demande.modele != "nli_multilingue":
        raise HTTPException(status_code=400, detail="Moteur NLI inconnu.")
    if any(not theme.get("titre") or not theme.get("definition")
           for theme in demande.themes):
        raise HTTPException(status_code=400, detail="Thèmes incomplets.")
    try:
        with _verrou_inference:
            tokeniseur, modele = charger_reseau("nli_multilingue")
            scores, tronque = evaluer_inferences(
                demande.texte, demande.themes, tokeniseur, modele
            )
    except (OSError, ValueError, RuntimeError) as erreur:
        raise HTTPException(
            status_code=503,
            detail=f"Modèle NLI indisponible : {erreur}. "
                   "Vérifiez le téléchargement dans charger_encodeurs.",
        ) from erreur
    return {
        "modele": "nli_multilingue",
        "depot": MODELE_NLI,
        "scores": scores,
        "nature_scores": (
            "Scores NLI non calibrés, sans annotation humaine. "
            "La neutralité signifie que le thème n'est pas démontré."
        ),
        "texte_tronque": tronque,
    }
