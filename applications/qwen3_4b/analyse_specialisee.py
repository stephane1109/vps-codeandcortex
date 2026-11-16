"""Interroger le service local des modèles spécialisés sans passer par Ollama."""
from __future__ import annotations

import math
import os
from typing import Any

import requests

from configuration_qwen import MODELES_SPECIALISES
from codage_multithemes import codes_themes, valider_themes


def interroger_encodeur_specialise(
    texte: str,
    themes: list[dict[str, str]],
    modele: str,
    session: requests.Session | None = None,
    delai_lecture: int = 180,
) -> dict[str, Any]:
    """Calculer des similarités cosinus, jamais des probabilités de thème."""
    if modele not in MODELES_SPECIALISES:
        raise ValueError("Modèle spécialisé inconnu.")
    grille = valider_themes(themes)
    if not texte.strip():
        raise ValueError("Le texte est vide.")
    if not 10 <= delai_lecture <= 600:
        raise ValueError("Délai de lecture invalide.")
    url = os.getenv(
        "ENCODEURS_URL", "http://encodeurs:8502"
    ).rstrip("/") + "/similarites"
    reponse = (session or requests).post(
        url,
        json={
            "modele": modele,
            "texte": texte[:12000],
            "themes": grille,
        },
        timeout=(10, delai_lecture),
    )
    try:
        reponse.raise_for_status()
    except requests.HTTPError as erreur:
        raise requests.HTTPError(
            f"Modèle {modele}, HTTP {reponse.status_code} : "
            f"{reponse.text[:1000]}",
            response=reponse,
        ) from erreur
    objet = reponse.json()
    scores = objet.get("scores")
    if not isinstance(scores, list) or len(scores) != len(grille):
        raise ValueError("Réponse de similarités incomplète.")
    resultat: dict[str, Any] = {}
    for code, theme, ligne in zip(codes_themes(grille), grille, scores):
        if not isinstance(ligne, dict) or ligne.get("theme") != theme["titre"]:
            raise ValueError(f"Intitulé de thème inattendu : {code}.")
        valeur = ligne.get("similarite_cosinus")
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            raise ValueError(f"Similarité numérique absente : {code}.")
        valeur = float(valeur)
        if not math.isfinite(valeur) or not -1 <= valeur <= 1:
            raise ValueError(f"Similarité hors de [-1, 1] : {code}.")
        resultat["similarite_" + code] = valeur
    resultat["texte_tronque"] = (
        len(texte) > 12000 or bool(objet.get("texte_tronque", False))
    )
    resultat["mode_analyse"] = "similarite"
    return resultat
