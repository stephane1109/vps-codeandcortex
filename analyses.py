"""### Module d'analyse des connecteurs

Ce fichier regroupe les fonctions de chargement, d'annotation HTML et de
comptage des connecteurs logiques. Il sert d'outil central pour préparer les
statistiques utilisées dans l'interface Streamlit et les traitements
aval (densité, AFC, normes lexicographiques)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from html import escape
from typing import Dict, Iterable


NEWLINE_CANONICAL = "\n"
NEWLINE_ALIASES = {"\n", "\r\n"}

IGNORED_NEWLINE_PATTERN = re.compile(r"^\*{4}.*?(\r?\n)", re.MULTILINE)

import pandas as pd


def load_connectors(path: Path) -> Dict[str, str]:
    """Charger le dictionnaire de connecteurs depuis un fichier JSON.

    Paramètres
    ----------
    path:
        Chemin vers le fichier ``connecteurs.json``.
    """

    with path.open(encoding="utf-8") as handle:
        connectors = json.load(handle)

    cleaned_connectors: Dict[str, str] = {}

    for key, value in connectors.items():
        stripped_key = key.strip(" \t")

        if not stripped_key:
            continue

        if stripped_key in NEWLINE_ALIASES:
            cleaned_connectors[NEWLINE_CANONICAL] = value
            continue

        cleaned_connectors[stripped_key] = value

    return cleaned_connectors


def _connector_to_regex(connector: str) -> str:
    """Construire une expression régulière pour un connecteur donné."""

    if not connector:
        return ""

    if connector == NEWLINE_CANONICAL:
        return r"\r?\n"

    escaped = re.escape(connector)
    needs_boundaries = connector[0].isalnum() and connector[-1].isalnum()

    if needs_boundaries:
        return rf"\b{escaped}\b"

    return escaped


def _build_connector_pattern(connectors: Dict[str, str]) -> re.Pattern[str]:
    """Construire un motif regex qui capture chaque connecteur."""

    patterns = []

    for connector in sorted(connectors.keys(), key=len, reverse=True):
        regex = _connector_to_regex(connector)

        if regex:
            patterns.append(regex)

    if not patterns:
        return re.compile(r"^$")

    pattern = "|".join(patterns)

    return re.compile(rf"({pattern})", re.IGNORECASE)


def _find_ignored_newlines(text: str) -> set[int]:
    """Repérer les retours à la ligne qui suivent une ligne étoilée.

    Les lignes commençant par ``****`` décrivent une métadonnée et leur retour
    à la ligne ne doit ni être compté ni être annoté comme connecteur.
    """

    ignored_positions: set[int] = set()

    for match in IGNORED_NEWLINE_PATTERN.finditer(text):
        # Le groupe capture uniquement le retour à la ligne pour cibler
        # précisément la position à ignorer.
        ignored_positions.add(match.start(1))

    return ignored_positions


def annotate_connectors_html(text: str, connectors: Dict[str, str]) -> str:
    """Retourner une version HTML du texte annoté avec les labels des connecteurs.

    Chaque connecteur est entouré d'un conteneur HTML incluant une étiquette de
    label visible. Les caractères spéciaux du texte source sont échappés afin de
    garantir une sortie sécurisée.
    """

    if not text:
        return ""

    cleaned_connectors = {key: value for key, value in connectors.items() if key}
    if not cleaned_connectors:
        return escape(text)

    ignored_newline_positions = _find_ignored_newlines(text)

    pattern = _build_connector_pattern(cleaned_connectors)
    lower_map: Dict[str, str] = {}

    for key, value in cleaned_connectors.items():
        lower_map[key.lower()] = value

        if key == NEWLINE_CANONICAL:
            # Autoriser la correspondance avec les deux représentations (Unix et Windows).
            for alias in NEWLINE_ALIASES:
                lower_map[alias] = value

    def _replacer(match: re.Match[str]) -> str:
        matched_connector = match.group(0)
        label = lower_map.get(matched_connector.lower(), "")
        safe_label = escape(label)
        label_class = _slugify_label(label)

        is_newline = matched_connector in NEWLINE_ALIASES
        if is_newline and match.start() in ignored_newline_positions:
            return "<br />"
        connector_display = "↵" if is_newline else escape(matched_connector)
        connector_markup = (
            f'<span class="connector-annotation connector-{label_class}">'
            f'<span class="connector-label">{safe_label}</span>'
            f'<span class="connector-text">{connector_display}</span>'
            "</span>"
        )

        if is_newline:
            # Conserver le saut de ligne visuellement en ajoutant un saut HTML
            # explicite. Le connecteur reste affiché pour indiquer l'emplacement
            # exact du retour à la ligne dans le texte source.
            return f"{connector_markup}<br />"

        return connector_markup

    escaped_text = escape(text)
    annotated = pattern.sub(_replacer, escaped_text)

    # Conserver la structure du texte tout en évitant les retours à la ligne
    # doublés par le CSS `white-space: pre-wrap`. On normalise seulement les
    # sauts Windows pour préserver l'affichage dans l'HTML brut.
    return annotated.replace("\r\n", "\n")


def count_connectors(text: str, connectors: Dict[str, str]) -> pd.DataFrame:
    """Compter le nombre d'occurrences de chaque connecteur dans le texte."""

    cleaned_connectors = {key: value for key, value in connectors.items() if key}
    rows = []
    ignored_newline_positions = _find_ignored_newlines(text)

    for connector, label in cleaned_connectors.items():
        regex_pattern = _connector_to_regex(connector)

        if not regex_pattern:
            continue

        regex = re.compile(regex_pattern, re.IGNORECASE)
        if connector == NEWLINE_CANONICAL:
            occurrences = sum(
                1
                for match in regex.finditer(text)
                if match.start() not in ignored_newline_positions
            )
        else:
            occurrences = len(regex.findall(text))

        if occurrences:
            rows.append(
                {
                    "connecteur": connector,
                    "label": label,
                    "occurrences": occurrences,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["connecteur", "label", "occurrences"])

    return (
        pd.DataFrame(rows)
        .sort_values(["label", "connecteur"])
        .reset_index(drop=True)
    )


def count_connectors_by_label(text: str, connectors: Dict[str, str]) -> Dict[str, int]:
    """Compter les connecteurs par label dans un texte donné.

    Le comptage s'effectue en parcourant toutes les occurrences des connecteurs
    définis dans ``connectors`` et en agrégeant leurs occurrences par label
    associé.
    """

    cleaned_connectors = {key: value for key, value in connectors.items() if key}

    if not text or not cleaned_connectors:
        return {}

    ignored_newline_positions = _find_ignored_newlines(text)
    pattern = _build_connector_pattern(cleaned_connectors)
    lower_map: Dict[str, str] = {}

    for key, value in cleaned_connectors.items():
        lower_map[key.lower()] = value

        if key == NEWLINE_CANONICAL:
            for alias in NEWLINE_ALIASES:
                lower_map[alias] = value
    label_counts: Dict[str, int] = {}

    for match in pattern.finditer(text):
        matched_connector = match.group(0)
        if matched_connector in NEWLINE_ALIASES and match.start() in ignored_newline_positions:
            continue
        label = lower_map.get(matched_connector.lower())

        if label:
            label_counts[label] = label_counts.get(label, 0) + 1

    return label_counts


def _slugify_label(label: str) -> str:
    """Convertir un label en identifiant CSS sécuritaire."""

    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "label"


def generate_label_colors(labels: Iterable[str]) -> Dict[str, str]:
    """Associer un jeu de couleurs à chaque label disponible."""

    palette = [
        "#1F77B4",
        "#2CA02C",
        "#D62728",
        "#9467BD",
        "#8C564B",
        "#E377C2",
        "#17BECF",
        "#FF7F0E",
        "#BCBD22",
    ]

    unique_labels = sorted({label for label in labels if label})
    return {label: palette[index % len(palette)] for index, label in enumerate(unique_labels)}


def build_label_style_block(label_colors: Dict[str, str]) -> str:
    """Construire un bloc CSS qui colore chaque label de manière distincte."""

    styles = []

    for label, color in label_colors.items():
        label_class = _slugify_label(label)
        styles.append(
            f".connector-annotation.connector-{label_class} {{"
            f" background-color: {color}1a;"
            f" border: 1px solid {color};"
            " }"
        )
        styles.append(
            f".connector-annotation.connector-{label_class} .connector-label {{"
            f" color: {color};"
            " }"
        )

    return "\n".join(styles)
