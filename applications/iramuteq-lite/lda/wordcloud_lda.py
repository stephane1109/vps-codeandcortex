#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération de nuages de mots à partir des résultats LDA en JSON.
"""

import argparse
import json
import os
import sys
import traceback
from typing import Dict, List

import matplotlib.pyplot as plt
from wordcloud import WordCloud


def charger_json(chemin_json: str) -> Dict:
    """Charge un fichier JSON en UTF-8."""
    with open(chemin_json, "r", encoding="utf-8") as flux:
        return json.load(flux)


def ecrire_json(chemin_sortie: str, donnees: Dict) -> None:
    """Écrit un fichier JSON de sortie."""
    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as flux:
        json.dump(donnees, flux, ensure_ascii=False, indent=2)


def preparer_frequences_topic(topic: Dict) -> Dict[str, float]:
    """Transforme la structure topic en dictionnaire de fréquences mot -> poids."""
    frequences = {}
    for element in topic.get("mots", []):
        mot = element.get("mot")
        poids = float(element.get("poids", 0.0))
        if mot:
            frequences[mot] = poids
    return frequences


def generer_nuage_topic(
    frequences: Dict[str, float],
    chemin_image: str,
    largeur: int = 1200,
    hauteur: int = 800,
) -> None:
    """Génère un nuage de mots PNG à partir de fréquences."""
    nuage = WordCloud(
        width=largeur,
        height=hauteur,
        background_color="white",
        colormap="viridis",
    ).generate_from_frequencies(frequences)

    plt.figure(figsize=(12, 8))
    plt.imshow(nuage, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(chemin_image, dpi=150)
    plt.close()


def generer_tous_les_nuages(
    resultats_lda: Dict,
    dossier_sortie: str,
    prefixe: str,
) -> List[Dict]:
    """Génère un nuage de mots par topic et retourne la liste des fichiers produits."""
    os.makedirs(dossier_sortie, exist_ok=True)

    sorties = []
    for topic in resultats_lda.get("topics", []):
        numero = int(topic.get("topic", 0))
        frequences = preparer_frequences_topic(topic)
        if not frequences:
            continue

        nom_fichier = f"{prefixe}_topic_{numero}.png"
        chemin_image = os.path.join(dossier_sortie, nom_fichier)

        generer_nuage_topic(frequences, chemin_image)

        sorties.append(
            {
                "topic": numero,
                "image": os.path.abspath(chemin_image),
                "nb_mots": len(frequences),
            }
        )

    return sorties


def analyser_arguments() -> argparse.Namespace:
    """Parse les arguments de la CLI."""
    parser = argparse.ArgumentParser(description="Générateur de nuages de mots LDA.")
    parser.add_argument("--input", required=True, help="Fichier JSON de résultats LDA.")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie des nuages.")
    parser.add_argument("--output-dir", required=True, help="Dossier de sortie des images PNG.")
    parser.add_argument("--prefix", default="wordcloud_lda", help="Préfixe des images générées.")
    return parser.parse_args()


def main() -> int:
    """Point d'entrée principal."""
    args = analyser_arguments()

    try:
        resultats_lda = charger_json(args.input)
        if not resultats_lda.get("succes", False):
            raise ValueError("Les résultats LDA indiquent un échec; impossible de générer des nuages.")

        fichiers = generer_tous_les_nuages(
            resultats_lda=resultats_lda,
            dossier_sortie=args.output_dir,
            prefixe=args.prefix,
        )

        sortie = {
            "succes": True,
            "dossier_sortie": os.path.abspath(args.output_dir),
            "fichiers": fichiers,
        }
        ecrire_json(args.output, sortie)
        return 0
    except Exception as erreur:
        sortie_erreur = {
            "succes": False,
            "erreur": str(erreur),
            "trace": traceback.format_exc(),
        }
        ecrire_json(args.output, sortie_erreur)
        print(f"Erreur pendant la génération des nuages de mots: {erreur}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
