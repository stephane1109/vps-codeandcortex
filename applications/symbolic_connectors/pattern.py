"""### Recherche de motifs logiques avec spaCy

Ce fichier définit les patrons linguistiques, s'appuyant sur spaCy pour les détecter et propose des fonctions
pour annoter et présenter les segments correspondants. Il complète les
analyses regex par une approche structurée des dépendances logiques."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Iterable, List

import spacy
from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span

from regexanalyse import split_segments


@dataclass(frozen=True)
class LogicalPattern:
    """Représente une règle de combinaison de connecteurs logiques."""

    name: str
    label: str
    category: str
    interpretation: str
    token_patterns: List[List[dict]]


DEFAULT_CONNECTOR_DETAILS = {
    "si": LogicalPattern(
        name="LOGICAL_SI",
        label="si",
        category="Condition",
        interpretation="Condition introduite par 'si'.",
        token_patterns=[[{"LEMMA": "si", "POS": {"IN": ["SCONJ", "CCONJ", "ADV"]}}]],
    ),
    "alors": LogicalPattern(
        name="LOGICAL_ALORS",
        label="alors",
        category="Conséquence",
        interpretation="Conséquence ou enchaînement marqué par 'alors'.",
        token_patterns=[[{"LEMMA": "alors", "POS": {"IN": ["SCONJ", "CCONJ", "ADV"]}}]],
    ),
}


def _build_combined_pattern() -> LogicalPattern:
    return LogicalPattern(
        name="LOGICAL_SI_ALORS",
        label="si ... alors",
        category="Structure conditionnelle",
        interpretation="Relation conditionnelle reliant 'si' et 'alors'.",
        token_patterns=[
            [
                {"LEMMA": "si", "POS": {"IN": ["SCONJ", "CCONJ", "ADV"]}},
                {"OP": "*"},
                {"LEMMA": "alors", "POS": {"IN": ["SCONJ", "CCONJ", "ADV"]}},
            ]
        ],
    )


def build_selected_patterns(selected_connectors: Iterable[str]) -> List[LogicalPattern]:
    normalized = {connector.lower().strip() for connector in selected_connectors}
    patterns: List[LogicalPattern] = []

    for connector in ("si", "alors"):
        if connector in normalized:
            patterns.append(DEFAULT_CONNECTOR_DETAILS[connector])

    if {"si", "alors"}.issubset(normalized):
        patterns.append(_build_combined_pattern())

    return patterns


def load_spacy_model(model: str | None = None) -> Language:
    """Charger un modèle spaCy français.

    Essaie d'abord le modèle moyen (md) puis le petit (sm) pour assurer la
    compatibilité avec les environnements où seul l'un des deux est installé.
    """

    candidates = [model] if model else ["fr_core_news_md", "fr_core_news_sm"]
    last_error: Exception | None = None

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            return spacy.load(candidate)
        except OSError as exc:  # noqa: PERF203 - boucle courte
            last_error = exc

    if last_error is not None:
        raise last_error

    raise OSError("Aucun modèle spaCy français n'a été fourni.")


def build_matcher(nlp: Language, patterns: Iterable[LogicalPattern]) -> Matcher:
    matcher = Matcher(nlp.vocab)

    for pattern in patterns:
        matcher.add(pattern.name, pattern.token_patterns)

    return matcher


def find_logical_patterns(
    text: str,
    selected_connectors: Iterable[str] | None = None,
    nlp: Language | None = None,
) -> List[dict]:
    nlp = nlp or load_spacy_model()
    connectors = selected_connectors if selected_connectors is not None else ("si", "alors")
    logical_patterns = build_selected_patterns(connectors)
    matcher = build_matcher(nlp, logical_patterns)

    doc: Doc = nlp(text)
    matches = matcher(doc)

    pattern_map = {pattern.name: pattern for pattern in logical_patterns}
    results: List[dict] = []

    for match_id, start, end in matches:
        name = nlp.vocab.strings[match_id]
        span: Span = doc[start:end]
        logical = pattern_map.get(name)
        if logical is None:
            continue

        results.append(
            {
                "name": logical.name,
                "label": logical.label,
                "category": logical.category,
                "interpretation": logical.interpretation,
                "span": span.text,
                "start": span.start_char,
                "end": span.end_char,
            }
        )

    return results


def find_pattern_segments(text: str, query: str, *, ignore_case: bool = True) -> List[dict]:
    """Rechercher les segments contenant un motif (pattern).

    Le motif est recherché tel quel (non-regex) et gère les signes de ponctuation
    comme « ? ».
    """

    if not query:
        return []

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(query), flags)

    segments = split_segments(text)
    results: List[dict] = []

    for index, segment in enumerate(segments, start=1):
        matches = list(pattern.finditer(segment))
        if not matches:
            continue

        results.append(
            {
                "segment_id": index,
                "segment": segment,
                "occurrences": len(matches),
                "score": len(matches),
                "matches": [match.group(0) for match in matches],
            }
        )

    return results


def _slugify_label(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "motif"


def annotate_user_pattern_html(text: str, query: str, *, ignore_case: bool = True) -> str:
    """Annoter le texte avec le motif fourni par l'utilisateur.

    Les occurrences sont surlignées avec une classe CSS réutilisable dans l'interface
    Streamlit. Les retours à la ligne sont conservés tels quels ; l'affichage dans
    Streamlit repose sur `white-space: pre-wrap` pour respecter la structure du
    texte sans ajouter de lignes vides.
    """

    if not text:
        return ""

    if not query:
        return escape(text)

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(query), flags)
    matches = list(pattern.finditer(text))

    if not matches:
        return escape(text)

    fragments: List[str] = []
    cursor = 0
    label_class = _slugify_label(query)

    for match in matches:
        start, end = match.start(), match.end()

        if start < cursor:
            continue

        fragments.append(escape(text[cursor:start]))
        fragments.append(
            "<span class=\"connector-annotation connector-"
            f"{label_class}\"><span class=\"connector-label\">{escape(query)}</span>"
            f"<span class=\"connector-text\">{escape(match.group(0))}</span></span>"
        )
        cursor = end

    fragments.append(escape(text[cursor:]))

    return "".join(fragments)
