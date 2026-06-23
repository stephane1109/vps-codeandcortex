"""### Analyse des segments via des règles regex

Le module charge les motifs décrits dans le dictionnaire JSON, compile les
règles, découpe les segments concernés et génère des surlignages HTML.
Il offre ainsi une alternative rapide aux recherches linguistiques avancées
en appliquant des expressions régulières contrôlées."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Dict, List, Sequence


@dataclass
class RegexPattern:
    """Représente une règle regex issue du dictionnaire."""

    pattern_id: str
    label: str
    category: str
    regex: str
    compiled: re.Pattern[str]


def load_regex_rules(path: Path) -> List[RegexPattern]:
    """Charger les règles regex depuis un fichier JSON."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    patterns: List[RegexPattern] = []

    for entry in payload.get("patterns", []):
        compiled = re.compile(entry["regex"], re.IGNORECASE)
        patterns.append(
            RegexPattern(
                pattern_id=entry.get("id", ""),
                label=entry.get("label", ""),
                category=entry.get("category", ""),
                regex=entry.get("regex", ""),
                compiled=compiled,
            )
        )

    return patterns


def split_segments(text: str) -> List[str]:
    """Découper un texte en segments en fonction de la ponctuation ou des retours à la ligne."""

    raw_segments = re.split(r"(?<=[.!?;:\n])\s+", text)
    return [segment.strip() for segment in raw_segments if segment and segment.strip()]


def _slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "motif"


def _highlight_single_segment(segment: str, patterns: Sequence[RegexPattern]) -> str:
    """Colorer un segment individuel sans chevauchement entre phrases."""

    matches = []
    for pattern in patterns:
        for match in pattern.compiled.finditer(segment):
            matches.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "label": pattern.label,
                    "identifier": pattern.pattern_id or pattern.label,
                    "match_text": match.group(0),
                }
            )

    if not matches:
        return escape(segment)

    matches.sort(key=lambda item: (item["start"], -(item["end"] - item["start"])))

    highlighted_parts: List[str] = []
    cursor = 0

    for match in matches:
        if match["start"] < cursor:
            continue

        highlighted_parts.append(escape(segment[cursor : match["start"]]))
        label_class = _slugify_identifier(match["label"])
        highlighted_parts.append(
            "<span class=\"connector-annotation connector-"
            f"{label_class}\"><span class=\"connector-label\">{escape(match['label'])}</span>"
            f"<span class=\"connector-text\">{escape(match['match_text'])}</span></span>"
        )
        cursor = match["end"]

    highlighted_parts.append(escape(segment[cursor:]))

    return "".join(highlighted_parts)


def _split_text_with_delimiters(text: str) -> List[str]:
    """Découper le texte en conservant les séparateurs.

    Cette variante de ``split_segments`` garde les espaces et retours à la
    ligne séparant les phrases pour permettre de reconstruire le texte HTML
    sans ajouter de lignes vides ni de sauts de ligne artificiels.
    """

    return re.split(r"(?<=[.!?;:\n])(\s+)", text)


def highlight_matches_html(text: str, patterns: Sequence[RegexPattern]) -> str:
    """Retourner le texte en HTML avec surlignage des motifs détectés.

    Les expressions régulières sont appliquées segment par segment afin de
    respecter les bornes de ponctuation et éviter des captures qui
    traverseraient plusieurs phrases. L'affichage conserve l'agencement du
    texte d'origine (pas de lignes vides ajoutées).
    """

    parts = _split_text_with_delimiters(text)

    if not parts:
        return escape(text)

    highlighted_parts: List[str] = []

    for index, part in enumerate(parts):
        if index % 2 == 0:
            if not part:
                continue
            highlighted_parts.append(_highlight_single_segment(part, patterns))
        else:
            highlighted_parts.append(escape(part))

    return "".join(highlighted_parts)


def summarize_matches_by_segment(
    segments: Sequence[str], patterns: Sequence[RegexPattern]
) -> List[Dict[str, object]]:
    """Retourner les segments contenant au moins un motif regex et leurs détails."""

    rows: List[Dict[str, object]] = []

    for index, segment in enumerate(segments, start=1):
        matches = []

        for pattern in patterns:
            occurrences = list(pattern.compiled.finditer(segment))
            if occurrences:
                matches.append(
                    {
                        "id": pattern.pattern_id,
                        "label": pattern.label,
                        "occurrences": len(occurrences),
                    }
                )

        if matches:
            rows.append(
                {
                    "segment_id": index,
                    "segment": segment,
                    "motifs": matches,
                }
            )

    return rows


def count_segments_by_pattern(segment_rows: Sequence[Dict[str, object]]) -> Dict[str, int]:
    """Compter le nombre de segments matchés par motif."""

    counts: Dict[str, int] = {}

    for row in segment_rows:
        for motif in row.get("motifs", []):
            identifier = motif.get("label") or motif.get("id")
            if identifier:
                counts[identifier] = counts.get(identifier, 0) + 1

    return counts
