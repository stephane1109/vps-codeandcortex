"""### Construction d'un sous-corpus IRaMuTeQ

Ce module filtre les enregistrements importés, vérifie la présence du préfixe
de prompt GPT et reconstruit les segments pertinents contenant des connecteurs.
Il sert à extraire automatiquement les passages utiles avant les analyses
statistiques ou linguistiques."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from analyses import load_connectors


MODEL_PROMPT_PREFIX = "****"


def has_header_markers(record: Dict[str, str]) -> bool:
    """Vérifie que l'entête correspond à un encodage de prompt GPT."""

    entete = record.get("entete", "").strip()
    return entete.startswith(MODEL_PROMPT_PREFIX)


def build_subcorpus(
    records: List[Dict[str, str]], connectors: Dict[str, str] | None = None
) -> List[str]:
    """Construit la liste des segments du sous-corpus à partir des enregistrements IRaMuTeQ.

    Seuls les textes dont la première ligne commence par `****` sont pris en compte.
    La première ligne est conservée telle quelle, puis les
    phrases ou lignes contenant au moins un connecteur sont concaténées pour
    reconstruire le sous-corpus.

    Les connecteurs peuvent être fournis pour respecter la sélection de l'utilisateur.
    S'ils sont absents, le dictionnaire complet est utilisé.
    """

    connectors = connectors or load_connectors(
        Path(__file__).parent / "dictionnaires" / "connecteurs.json"
    )
    connector_pattern = _build_connector_pattern(connectors)

    if connector_pattern is None:
        return []

    subcorpus_segments: List[str] = []

    for record in records:
        if not has_header_markers(record):
            continue

        entete = record.get("entete", "")
        texte = record.get("texte", "").strip()

        filtered_segments = [
            segment for segment in _split_text_segments(texte) if connector_pattern.search(segment)
        ]

        if filtered_segments:
            combined_segment = "\n".join([entete] + filtered_segments)
        else:
            combined_segment = entete

        subcorpus_segments.append(combined_segment)

    return subcorpus_segments


def _build_connector_pattern(connectors: Dict[str, str]) -> re.Pattern[str] | None:
    """Construire un motif regex qui identifie les connecteurs présents dans le texte."""

    cleaned_connectors = [key.strip() for key in connectors if key.strip()]

    if not cleaned_connectors:
        return None

    sorted_keys = sorted(cleaned_connectors, key=len, reverse=True)
    escaped = [re.escape(key) for key in sorted_keys]
    pattern = "|".join(escaped)

    return re.compile(rf"\b({pattern})\b", re.IGNORECASE)


def _split_text_segments(text: str) -> List[str]:
    """Diviser le texte en segments utilisables pour le sous-corpus.

    Les segments sont découpés sur les retours à la ligne ou après les
    ponctuations fortes de fin de phrase. Les blancs superflus sont retirés.
    """

    raw_segments = re.split(r"(?:\r?\n+|(?<=[.!?])\s+)", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]
