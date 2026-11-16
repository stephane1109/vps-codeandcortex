"""API locale d'exploration sémantique de modèles français spécialisés."""
from __future__ import annotations

import gc
import os
from functools import lru_cache

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoTokenizer

torch.set_num_threads(2)

MODELES_SPECIALISES = {
    "juribert": "dascim/juribert-base",
    "bertweetfr": "Yanzhu/bertweetfr-base",
}

application = FastAPI(title="Encodeurs spécialisés SHS")


class DemandeComparaison(BaseModel):
    """Décrire une comparaison exploratoire pour un seul texte."""

    modele: str
    texte: str = Field(min_length=1, max_length=12000)
    themes: list[dict[str, str]] = Field(min_length=1, max_length=8)


@lru_cache(maxsize=1)
def charger_encodeur(nom_modele: str):
    """Charger un seul encodeur à la fois en mémoire CPU."""
    depot = MODELES_SPECIALISES[nom_modele]
    tokeniseur = AutoTokenizer.from_pretrained(depot, local_files_only=True)
    modele = AutoModel.from_pretrained(depot, local_files_only=True)
    modele.eval()
    return tokeniseur, modele


def encoder_textes(textes: list[str], tokeniseur, modele) -> torch.Tensor:
    """Produire des vecteurs moyens masqués sur les tokens valides."""
    entrees = tokeniseur(
        textes, return_tensors="pt", truncation=True,
        padding=True, max_length=256,
    )
    with torch.inference_mode():
        sorties = modele(**entrees).last_hidden_state
        masque = entrees["attention_mask"].unsqueeze(-1)
        vecteurs = (sorties * masque).sum(dim=1) / masque.sum(dim=1).clamp(min=1)
        return torch.nn.functional.normalize(vecteurs, dim=1)


@application.get("/modeles")
def verifier_modeles() -> dict[str, object]:
    """Exposer les références exactes sans charger les poids des modèles."""
    return {"modeles": MODELES_SPECIALISES}


@application.post("/similarites")
def calculer_similarites(demande: DemandeComparaison) -> dict[str, object]:
    """Comparer un texte aux définitions de thèmes, sans simuler une classification."""
    if demande.modele not in MODELES_SPECIALISES:
        raise HTTPException(status_code=400, detail="Encodeur inconnu.")
    if any(not theme.get("titre") or not theme.get("definition") for theme in demande.themes):
        raise HTTPException(status_code=400, detail="Thèmes incomplets.")
    try:
        tokeniseur, modele = charger_encodeur(demande.modele)
        descriptions = [
            f"{theme['titre']}. {theme['definition']}"
            for theme in demande.themes
        ]
        vecteurs = encoder_textes([demande.texte, *descriptions], tokeniseur, modele)
        similarites = torch.matmul(vecteurs[1:], vecteurs[0]).tolist()
    except (OSError, ValueError, RuntimeError) as erreur:
        gc.collect()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Encodeur {demande.modele} indisponible : {erreur}. "
                "Vérifiez l'exécution de charger_encodeurs dans Coolify."
            ),
        ) from erreur
    return {
        "modele": demande.modele,
        "depot": MODELES_SPECIALISES[demande.modele],
        "scores": [
            {"theme": theme["titre"], "similarite_cosinus": round(float(score), 4)}
            for theme, score in zip(demande.themes, similarites)
        ],
        "nature_scores": "Similarités cosinus non calibrées, sans classification supervisée.",
        "texte_tronque": len(tokeniseur(demande.texte)["input_ids"]) > 256,
    }
