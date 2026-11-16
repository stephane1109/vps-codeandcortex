"""Détection prudente de la langue des commentaires pour Zero-shot."""
from __future__ import annotations

import re
from typing import Callable

LANGUES_COMPAREES = (
    "FRENCH", "ENGLISH", "SPANISH", "ITALIAN", "PORTUGUESE",
    "GERMAN", "DUTCH", "ARABIC", "TURKISH", "ROMANIAN",
    "RUSSIAN", "POLISH", "UKRAINIAN", "SWEDISH",
)


def creer_detecteur():
    """Initialiser Lingua en chargement paresseux pour limiter la mémoire."""
    from lingua import Language, LanguageDetectorBuilder

    langues = [getattr(Language, nom) for nom in LANGUES_COMPAREES]
    return LanguageDetectorBuilder.from_languages(*langues).build()


def classifier_texte(
    texte: str,
    detecteur,
    minimum_lettres: int = 12,
    seuil_confiance: float = 0.65,
    seuil_ecart: float = 0.15,
) -> dict[str, str | float]:
    """Ne pas rejeter automatiquement les commentaires très courts ou ambigus.

    Les valeurs de confiance sont relatives aux langues examinées et ne
    constituent pas une probabilité de langue calibrée sur TikTok.
    """
    nombre_lettres = sum(c.isalpha() for c in texte)
    if nombre_lettres < minimum_lettres:
        return {
            "langue_detectee": "indetermine",
            "statut_langue": "indetermine",
            "confiance_langue": 0.0,
            "ecart_langue": 0.0,
        }
    valeurs = detecteur.compute_language_confidence_values(texte)
    if not valeurs:
        return {
            "langue_detectee": "indetermine",
            "statut_langue": "indetermine",
            "confiance_langue": 0.0,
            "ecart_langue": 0.0,
        }
    premier = valeurs[0]
    second = valeurs[1].value if len(valeurs) > 1 else 0.0
    score = float(premier.value)
    ecart = score - float(second)
    nom = premier.language.name.lower()
    if score < seuil_confiance or ecart < seuil_ecart:
        statut = "indetermine"
    elif nom == "french":
        statut = "francais"
    else:
        statut = "hors_francais"
    return {
        "langue_detectee": nom,
        "statut_langue": statut,
        "confiance_langue": round(score, 4),
        "ecart_langue": round(ecart, 4),
    }


def detecter_langues(
    textes: list[str],
    minimum_lettres: int = 12,
    seuil_confiance: float = 0.65,
    seuil_ecart: float = 0.15,
    progression: Callable[[float, str], None] | None = None,
) -> list[dict[str, str | float]]:
    """Qualifier tous les textes avant tout échantillonnage thématique."""
    detecteur = creer_detecteur()
    resultats: list[dict[str, str | float]] = []
    total = len(textes)
    for numero, texte in enumerate(textes, 1):
        resultats.append(classifier_texte(
            str(texte), detecteur,
            minimum_lettres=minimum_lettres,
            seuil_confiance=seuil_confiance,
            seuil_ecart=seuil_ecart,
        ))
        if progression and (numero % 250 == 0 or numero == total):
            progression(numero / max(1, total), f"Détection linguistique : {numero}/{total}")
    return resultats
