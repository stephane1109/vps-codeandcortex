"""Déterminer la disponibilité des commandes sans bloquer les tests d'inférence."""
from __future__ import annotations


def evaluer_commandes_analyse(
    nombre_restants: int,
    nombre_erreurs: int,
    prompt: str,
    mode_analyse: str,
    grille_valide: bool,
    service_disponible: bool,
) -> dict[str, object]:
    """Retourner les commandes utilisables et les diagnostics explicites.

    L'inventaire Ollama (/api/tags) ne garantit pas une inférence réussie.
    Une réponse manquante à cette vérification ne doit pas empêcher de tester
    directement le modèle et d'en afficher l'erreur éventuelle.
    """
    causes: list[str] = []
    if not prompt.strip():
        causes.append("Le prompt est vide.")
    if not grille_valide:
        causes.append(
            "La grille thématique est invalide : vérifiez les titres "
            "et les définitions dans « Définir les thèmes à partir de votre prompt »."
        )
    if nombre_restants <= 0 and nombre_erreurs <= 0:
        causes.append(
            "Aucun texte en attente. Vérifiez la colonne choisie "
            "et le nombre de textes non vides."
        )

    conditions_valides = bool(prompt.strip()) and grille_valide
    return {
        "tester": conditions_valides and nombre_restants > 0,
        "lancer": conditions_valides and nombre_restants > 0,
        "relancer": conditions_valides and nombre_erreurs > 0,
        "causes": causes,
        "avertissement_service": (
            not service_disponible and conditions_valides
        ),
    }
