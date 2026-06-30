#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération d'une heatmap mots × topics à partir des résultats LDA JSON.
"""

import argparse
import json
import math
import os
from typing import List, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


def charger_resultats(chemin_json: str) -> dict:
    with open(chemin_json, "r", encoding="utf-8") as flux:
        donnees = json.load(flux)

    if not isinstance(donnees, dict):
        raise ValueError("Le JSON LDA est invalide.")

    if not donnees.get("succes", False):
        raise ValueError("Les résultats LDA indiquent un échec; impossible de générer la heatmap.")

    return donnees


def extraire_matrice(donnees: dict) -> Tuple[np.ndarray, List[str], List[str]]:
    termes = [str(term) for term in (donnees.get("terms") or []) if str(term).strip()]
    topic_term_matrix = donnees.get("topic_term_matrix") or []

    if (not termes or not topic_term_matrix) and donnees.get("topics"):
        topics_bruts = donnees.get("topics") or []
        vocabulaire = []
        for topic in topics_bruts:
            for mot in (topic.get("mots") or []):
                terme = str(mot.get("mot") or "").strip()
                if terme:
                    vocabulaire.append(terme)
        termes = sorted(set(vocabulaire))
        if not termes:
            raise ValueError("Les résultats LDA ne contiennent pas de matrice topic-terme exploitable.")
        matrice = np.zeros((len(topics_bruts), len(termes)), dtype=float)
        index_termes = {terme: idx for idx, terme in enumerate(termes)}
        for idx_topic, topic in enumerate(topics_bruts):
            mots = topic.get("mots") or []
            poids = np.asarray([float(mot.get("poids") or 0.0) for mot in mots], dtype=float)
            somme = float(np.sum(poids))
            if somme <= 0:
                continue
            for mot in mots:
                terme = str(mot.get("mot") or "").strip()
                if not terme or terme not in index_termes:
                    continue
                matrice[idx_topic, index_termes[terme]] = float(mot.get("poids") or 0.0) / somme
        topics = [f"Topic {idx}" for idx in range(1, matrice.shape[0] + 1)]
        return matrice, termes, topics

    if not termes or not topic_term_matrix:
        raise ValueError("Les résultats LDA ne contiennent pas de matrice topic-terme exploitable.")

    matrice = np.asarray(topic_term_matrix, dtype=float)
    if matrice.ndim != 2:
        raise ValueError("La matrice topic-terme est mal formée.")

    if matrice.shape[1] != len(termes):
        raise ValueError("Le nombre de termes ne correspond pas à la matrice topic-terme.")

    sommes = matrice.sum(axis=1, keepdims=True)
    sommes[sommes == 0] = 1.0
    matrice = matrice / sommes

    topics = [f"Topic {idx}" for idx in range(1, matrice.shape[0] + 1)]
    return matrice, termes, topics


def selectionner_termes(
    matrice: np.ndarray,
    termes: List[str],
    top_n_par_topic: int,
    max_total_termes: int,
) -> Tuple[np.ndarray, List[str]]:
    indices_retenus = []
    n_topics = matrice.shape[0]

    for idx_topic in range(n_topics):
        poids = matrice[idx_topic, :]
        ordre = np.argsort(poids)[::-1]
        ordre = [int(idx) for idx in ordre[:top_n_par_topic] if poids[idx] > 0]
        indices_retenus.extend(ordre)

    if not indices_retenus:
        raise ValueError("Aucun terme significatif n'a été trouvé pour construire la heatmap.")

    indices_uniques = sorted(set(indices_retenus))
    if len(indices_uniques) > max_total_termes:
        scores = [(idx, float(np.max(matrice[:, idx]))) for idx in indices_uniques]
        scores.sort(key=lambda item: item[1], reverse=True)
        indices_uniques = sorted(idx for idx, _ in scores[:max_total_termes])

    def cle_tri(idx_terme: int):
        colonne = matrice[:, idx_terme]
        topic_dominant = int(np.argmax(colonne))
        score_dominant = float(np.max(colonne))
        return (topic_dominant, -score_dominant, termes[idx_terme].lower())

    indices_tries = sorted(indices_uniques, key=cle_tri)
    sous_matrice = matrice[:, indices_tries].T
    termes_selectionnes = [termes[idx] for idx in indices_tries]
    return sous_matrice, termes_selectionnes


def generer_heatmap(
    matrice_termes_topics: np.ndarray,
    termes: List[str],
    topics: List[str],
    chemin_sortie: str,
) -> None:
    n_termes, n_topics = matrice_termes_topics.shape
    largeur = min(12.5, max(6.4, 2.8 + (n_topics * 0.82)))
    hauteur = min(18.0, max(4.6, 1.6 + (n_termes * 0.22)))

    fig, axe = plt.subplots(figsize=(largeur, hauteur), dpi=150)
    image = axe.imshow(
        matrice_termes_topics,
        aspect="auto",
        interpolation="nearest",
        cmap="YlOrRd",
        origin="upper",
    )

    axe.set_title("Heatmap mots × topics", fontsize=12, fontweight="bold", pad=10)
    axe.set_xlabel("Topics", fontsize=10)
    axe.set_ylabel("Mots", fontsize=10)
    axe.set_xticks(np.arange(n_topics))
    axe.set_xticklabels(topics, rotation=0, fontsize=9)
    axe.set_yticks(np.arange(n_termes))
    axe.set_yticklabels(termes, fontsize=8 if n_termes <= 36 else 7)

    axe.set_xticks(np.arange(-0.5, n_topics, 1), minor=True)
    axe.set_yticks(np.arange(-0.5, n_termes, 1), minor=True)
    axe.grid(which="minor", color="#ffffff", linestyle="-", linewidth=0.6, alpha=0.45)
    axe.tick_params(which="minor", bottom=False, left=False)

    colorbar = fig.colorbar(image, ax=axe, fraction=0.03, pad=0.02)
    colorbar.set_label("Probabilité P(mot | topic)", rotation=90, labelpad=8, fontsize=9)
    colorbar.ax.tick_params(labelsize=8)

    if n_termes * n_topics <= 220:
        seuil = float(np.max(matrice_termes_topics)) * 0.52 if matrice_termes_topics.size else 0.0
        for i in range(n_termes):
            for j in range(n_topics):
                valeur = float(matrice_termes_topics[i, j])
                if not math.isfinite(valeur):
                    continue
                couleur = "#2a120d" if valeur < seuil else "#fffaf5"
                axe.text(
                    j,
                    i,
                    f"{valeur:.3f}",
                    ha="center",
                    va="center",
                    fontsize=6.4,
                    color=couleur,
                )

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)
    fig.savefig(chemin_sortie, bbox_inches="tight")
    plt.close(fig)


def analyser_argumentaire() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Générateur de heatmap LDA mots × topics.")
    parser.add_argument("--input", required=True, help="Fichier JSON de résultats LDA.")
    parser.add_argument("--output", required=True, help="Fichier PNG de sortie.")
    parser.add_argument("--top-n-per-topic", type=int, default=12, help="Nombre de mots retenus par topic.")
    parser.add_argument("--max-total-terms", type=int, default=100, help="Nombre maximal total de mots dans la heatmap.")
    return parser.parse_args()


def main() -> int:
    args = analyser_argumentaire()
    donnees = charger_resultats(args.input)
    matrice, termes, topics = extraire_matrice(donnees)
    matrice_termes_topics, termes_selectionnes = selectionner_termes(
        matrice,
        termes,
        top_n_par_topic=max(1, int(args.top_n_per_topic)),
        max_total_termes=max(10, int(args.max_total_terms)),
    )
    generer_heatmap(matrice_termes_topics, termes_selectionnes, topics, args.output)
    print(
        f"Heatmap LDA générée : {len(termes_selectionnes)} mot(s), {len(topics)} topic(s), fichier={args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
