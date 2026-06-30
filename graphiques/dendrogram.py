"""Génération d'un dendrogramme à partir d'une matrice de similarité cosinus."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform


@dataclass
class DendrogramConfig:
    """Paramètres de configuration du dendrogramme de similarité.

    Attributes:
        method: Méthode de liaison hiérarchique (ex. "average", "complete").
        color_threshold: Seuil de distance pour colorer les branches.
    """

    method: str = "average"
    color_threshold: float | None = None


def create_cosine_dendrogram_figure(
    similarity_matrix: np.ndarray,
    labels: Sequence[str],
    config: DendrogramConfig | None = None,
) -> plt.Figure:
    """Construit une figure Matplotlib représentant le dendrogramme hiérarchique.

    Args:
        similarity_matrix: Matrice carrée des similarités cosinus.
        labels: Noms des modalités/modèles.
        config: Paramètres optionnels du dendrogramme.

    Returns:
        Une figure Matplotlib prête à être exportée.
    """

    cfg = config or DendrogramConfig()
    similarities = np.asarray(similarity_matrix, dtype=float)

    if similarities.shape[0] != similarities.shape[1]:
        raise ValueError("La matrice de similarité doit être carrée")
    if len(labels) != similarities.shape[0]:
        raise ValueError("Le nombre de labels doit correspondre à la matrice")

    # Conversion en distance (1 - similarité) puis en forme condensée.
    distances = 1.0 - similarities
    np.fill_diagonal(distances, 0.0)
    condensed_distances = squareform(distances, checks=False)

    linkage_matrix = hierarchy.linkage(condensed_distances, method=cfg.method)

    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    hierarchy.dendrogram(
        linkage_matrix,
        labels=list(labels),
        orientation="top",
        color_threshold=cfg.color_threshold,
        ax=ax,
    )

    ax.set_ylabel("Distance (1 - similarité cosinus)")
    ax.set_title("Dendrogramme des similarités cosinus", fontsize=14)
    fig.tight_layout()
    return fig


def create_cosine_dendrogram_image(
    similarity_matrix: np.ndarray,
    labels: Sequence[str],
    config: DendrogramConfig | None = None,
    dpi: int = 150,
) -> BytesIO:
    """Génère une image PNG centrée du dendrogramme hiérarchique."""

    figure = create_cosine_dendrogram_figure(similarity_matrix, labels, config)
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    buffer.seek(0)
    plt.close(figure)
    return buffer
