"""Service CPU pour les encodeurs français et la classification zero-shot NLI."""
from __future__ import annotations

import gc
import threading
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

torch.set_num_threads(2)

MODELES_ENCODEURS = {
    "juribert": "dascim/juribert-base",
    "bertweetfr": "Yanzhu/bertweetfr-base",
}
MODELE_NLI = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
TOUS_MODELES = {**MODELES_ENCODEURS, "nli_multilingue": MODELE_NLI}

application = FastAPI(title="Analyse textuelle spécialisée SHS")
_verrou = threading.Lock()
_nom_charge: str | None = None
_tokeniseur_charge: Any = None
_reseau_charge: Any = None


class DemandeComparaison(BaseModel):
    """Décrire une comparaison exploratoire pour un seul texte."""

    modele: str
    texte: str = Field(min_length=1, max_length=12000)
    themes: list[dict[str, str]] = Field(min_length=1, max_length=8)


def charger_modele(nom_modele: str):
    """Libérer l'ancien réseau avant d'en charger un autre sur le VPS."""
    global _nom_charge, _tokeniseur_charge, _reseau_charge
    if nom_modele not in TOUS_MODELES:
        raise ValueError("Modèle spécialisé inconnu.")
    if _nom_charge == nom_modele and _reseau_charge is not None:
        return _tokeniseur_charge, _reseau_charge
    _nom_charge, _tokeniseur_charge, _reseau_charge = None, None, None
    gc.collect()
    depot = TOUS_MODELES[nom_modele]
    tokeniseur = AutoTokenizer.from_pretrained(depot, local_files_only=True)
    if nom_modele == "nli_multilingue":
        reseau = AutoModelForSequenceClassification.from_pretrained(
            depot, local_files_only=True
        )
    else:
        reseau = AutoModel.from_pretrained(depot, local_files_only=True)
    reseau.eval()
    _nom_charge, _tokeniseur_charge, _reseau_charge = (
        nom_modele, tokeniseur, reseau
    )
    return tokeniseur, reseau


def encoder_textes(textes: list[str], tokeniseur, modele) -> torch.Tensor:
    """Produire des vecteurs exploratoires par moyenne masquée des tokens."""
    entrees = tokeniseur(
        textes, return_tensors="pt", truncation=True,
        padding=True, max_length=256,
    )
    with torch.inference_mode():
        sorties = modele(**entrees).last_hidden_state
        masque = entrees["attention_mask"].unsqueeze(-1)
        vecteurs = (sorties * masque).sum(dim=1) / masque.sum(dim=1).clamp(min=1)
        return torch.nn.functional.normalize(vecteurs, dim=1)


def definir_hypothese(theme: dict[str, str]) -> str:
    """Formuler une hypothèse explicite, distincte d'un mot-clé isolé."""
    titre = theme["titre"].strip()
    definition = theme["definition"].strip()
    hypothese = f"Ce message exprime explicitement : {titre}."
    if not definition.casefold().startswith(
        "le texte comporte un indice explicite relevant du thème"
    ):
        hypothese += " " + definition
    return hypothese


def scores_inference(texte: str, themes: list[dict[str, str]],
                     tokeniseur, modele) -> tuple[list[dict[str, Any]], bool]:
    """Distinguer implication, neutralité et contradiction pour chaque thème."""
    indices = {
        str(nom).casefold(): int(indice)
        for nom, indice in modele.config.label2id.items()
    }
    attendus = ("entailment", "neutral", "contradiction")
    if any(nom not in indices for nom in attendus):
        raise ValueError("Le modèle NLI ne présente pas les trois classes attendues.")
    resultats: list[dict[str, Any]] = []
    troncature = False
    for theme in themes:
        hypothese = definir_hypothese(theme)
        longueur = len(
            tokeniseur(texte, hypothese, truncation=False)["input_ids"]
        )
        troncature |= longueur > 384
        donnees = tokeniseur(
            texte, hypothese,
            truncation="only_first", max_length=384,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = modele(**donnees).logits[0]
            classes = torch.softmax(logits, dim=-1).tolist()
        resultats.append({
            "theme": theme["titre"],
            "hypothese": hypothese,
            "implication": round(float(classes[indices["entailment"]]), 6),
            "neutralite": round(float(classes[indices["neutral"]]), 6),
            "contradiction": round(float(classes[indices["contradiction"]]), 6),
        })
    return resultats, troncature


@application.get("/modeles")
def verifier_modeles() -> dict[str, object]:
    """Lister les modèles connus sans les charger en mémoire."""
    return {"modeles": TOUS_MODELES}


@application.post("/similarites")
def calculer_similarites(demande: DemandeComparaison) -> dict[str, object]:
    """Comparer les représentations sans les interpréter comme des étiquettes."""
    if demande.modele not in MODELES_ENCODEURS:
        raise HTTPException(status_code=400, detail="Encodeur inconnu.")
    if any(not theme.get("titre") or not theme.get("definition")
           for theme in demande.themes):
        raise HTTPException(status_code=400, detail="Thèmes incomplets.")
    try:
        with _verrou:
            tokeniseur, modele = charger_modele(demande.modele)
            descriptions = [
                f"{theme['titre']}. {theme['definition']}"
                for theme in demande.themes
            ]
            vecteurs = encoder_textes(
                [demande.texte, *descriptions], tokeniseur, modele
            )
            valeurs = torch.matmul(vecteurs[1:], vecteurs[0]).tolist()
            tronque = len(tokeniseur(demande.texte)["input_ids"]) > 256
    except (OSError, ValueError, RuntimeError) as erreur:
        gc.collect()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Encodeur {demande.modele} indisponible : {erreur}. "
                "Vérifiez charger_encodeurs dans Coolify."
            ),
        ) from erreur
    return {
        "modele": demande.modele,
        "depot": MODELES_ENCODEURS[demande.modele],
        "scores": [
            {"theme": theme["titre"], "similarite_cosinus": round(float(score), 4)}
            for theme, score in zip(demande.themes, valeurs)
        ],
        "nature_scores": (
            "Cosinus de représentations BERT brutes : impropre pour déduire "
            "la présence d'un thème sans apprentissage supervisé."
        ),
        "texte_tronque": tronque,
    }


@application.post("/inferences")
def calculer_inferences(demande: DemandeComparaison) -> dict[str, object]:
    """Appliquer un modèle explicitement entraîné à l'inférence NLI."""
    if demande.modele != "nli_multilingue":
        raise HTTPException(status_code=400, detail="Modèle NLI inconnu.")
    if any(not theme.get("titre") or not theme.get("definition")
           for theme in demande.themes):
        raise HTTPException(status_code=400, detail="Thèmes incomplets.")
    try:
        with _verrou:
            tokeniseur, modele = charger_modele(demande.modele)
            resultats, tronque = scores_inference(
                demande.texte, demande.themes, tokeniseur, modele
            )
    except (OSError, ValueError, RuntimeError) as erreur:
        gc.collect()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Modèle NLI indisponible : {erreur}. "
                "Vérifiez charger_encodeurs dans Coolify."
            ),
        ) from erreur
    return {
        "modele": demande.modele,
        "depot": MODELE_NLI,
        "scores": resultats,
        "nature_scores": (
            "Répartition NLI de chaque hypothèse : implication, neutralité "
            "et contradiction. Scores non calibrés, validation humaine nécessaire."
        ),
        "texte_tronque": tronque,
    }
