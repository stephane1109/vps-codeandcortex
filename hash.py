"""
Le "hachage" du texte est calculé à partir de la Longueur Moyenne des Segments (LMS)
de texte délimités par les connecteurs détectés dans le texte. L'idée :
- Des segments courts signalent un texte haché, saccadé, algorithmique.
- Des segments longs évoquent une prose fluide, narrative ou explicative.
"""

from __future__ import annotations

import re
from statistics import mean
from functools import lru_cache
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import numpy as np

import pandas as pd

import spacy

from densite import build_text_from_dataframe, filter_dataframe_by_modalities


SegmentationMode = Literal["connecteurs", "connecteurs_et_ponctuation"]
TokenizationMode = Literal["regex", "spacy"]


METADATA_LINE_PATTERN = re.compile(r"^\s*\*{4}")

ECART_TYPE_EXPLANATION = """L'écart-type est une mesure de dispersion. L’écart-type mesure à quel point la longueur des segments varie autour de la LMS : plus il est élevé, plus les segments sont hétérogènes. 
Pour comparer des variables ayant des LMS différentes, le rapport écart-type/LMS indique la dispersion relative : faible = segmentation régulière, élevé = segmentation plus irrégulière.
"""


def _remove_metadata_lines(text: str) -> str:
    """Retirer les lignes de métadonnées en début ou milieu de texte."""

    if not text:
        return text

    lines = text.splitlines()
    cleaned = [line for line in lines if not METADATA_LINE_PATTERN.match(line)]

    if len(cleaned) == len(lines):
        return text

    return "\n".join(cleaned).lstrip()


def _format_segment_with_markers(
    segment: str, previous_connector: Optional[str], next_connector: Optional[str]
) -> str:
    """Afficher le segment avec ses bornes encadrées par des crochets."""

    parts: List[str] = []

    if previous_connector:
        parts.append(f"[{previous_connector}]")

    parts.append(segment.strip())

    if next_connector:
        parts.append(f"[{next_connector}]")

    return " ".join(parts)


def _wrap_connector_regex(key: str) -> str:
    """Encadrer un connecteur de bornes si sa forme le permet."""

    escaped = re.escape(key)

    # Les connecteurs composés uniquement de ponctuation ou d'espaces (ex. retours
    # à la ligne) ne doivent pas être encadrés par des bornes de mots car ils ne
    # seraient jamais reconnus avec \b.
    if not re.search(r"\w", key):
        return escaped

    return rf"\b{escaped}\b"


def _build_connector_pattern(connectors: Dict[str, str]) -> re.Pattern[str] | None:
    """Construire un motif regex sécurisé pour tous les connecteurs fournis."""

    cleaned = [key for key in connectors if key]

    if not cleaned:
        return None

    sorted_keys = sorted(cleaned, key=len, reverse=True)
    escaped = [_wrap_connector_regex(key) for key in sorted_keys]
    pattern = "|".join(escaped)

    return re.compile(rf"({pattern})", re.IGNORECASE)


def _build_boundary_pattern(
    connectors: Dict[str, str],
    include_punctuation: bool,
    connector_pattern: re.Pattern[str] | None = None,
) -> re.Pattern[str] | None:
    """Construire un motif pour les bornes de segment (connecteurs, ponctuation)."""

    connector_pattern = connector_pattern or _build_connector_pattern(connectors)
    punctuation_pattern = r"[\.!?;:]+" if include_punctuation else None

    if connector_pattern is None and not punctuation_pattern:
        return None

    if connector_pattern is None:
        return re.compile(punctuation_pattern, re.IGNORECASE)

    if not punctuation_pattern:
        return connector_pattern

    return re.compile(
        rf"{connector_pattern.pattern}|{punctuation_pattern}",
        re.IGNORECASE,
    )


@lru_cache(maxsize=1)
def _get_spacy_tokenizer():
    """Charger et mettre en cache le tokenizer spaCy français.

    On exclut les composants coûteux pour ne garder que la tokenisation. Si le
    modèle n'est pas installé, une RuntimeError explicite est levée pour être
    relayée dans l'interface.
    """

    try:
        nlp = spacy.load(
            "fr_core_news_md",
            exclude=[
                "parser",
                "ner",
                "lemmatizer",
                "attribute_ruler",
                "textcat",
                "tok2vec",
                "morphologizer",
                "senter",
            ],
        )
    except OSError as exc:
        raise RuntimeError(
            "Le modèle spaCy 'fr_core_news_md' est manquant : installez-le pour utiliser la tokenisation spaCy."
        ) from exc

    return nlp.tokenizer


def _tokenize_regex(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text, flags=re.UNICODE)


def _tokenize_spacy(text: str) -> List[str]:
    tokenizer = _get_spacy_tokenizer()
    return [
        token.text
        for token in tokenizer(text)
        if not token.is_space and not token.is_punct
    ]


def _tokenize(text: str, tokenization_mode: TokenizationMode) -> List[str]:
    if tokenization_mode == "spacy":
        return _tokenize_spacy(text)

    return _tokenize_regex(text)


def _is_connector(boundary: str | None, connector_pattern: re.Pattern[str] | None) -> bool:
    """Vérifier si une borne correspond à un connecteur (et non à de la ponctuation)."""

    if not boundary or connector_pattern is None:
        return False

    return connector_pattern.fullmatch(boundary) is not None


def _segments_with_boundaries(
    text: str,
    pattern: re.Pattern[str],
    connector_pattern: re.Pattern[str] | None,
) -> List[tuple[str, Optional[str], Optional[str]]]:
    """Retourner uniquement les segments bornés par au moins un connecteur."""

    segments: List[tuple[str, Optional[str], Optional[str]]] = []
    last_end = 0
    previous_connector: Optional[str] = None

    for match in pattern.finditer(text):
        segment = text[last_end: match.start()]
        next_connector = match.group(0)

        previous_is_connector = _is_connector(previous_connector, connector_pattern)
        next_is_connector = _is_connector(next_connector, connector_pattern)

        if segment.strip() and (previous_is_connector or next_is_connector):
            segments.append((segment, previous_connector, next_connector))

        previous_connector = next_connector
        last_end = match.end()

    trailing = text[last_end:]

    if trailing.strip() and _is_connector(previous_connector, connector_pattern):
        segments.append((trailing, previous_connector, None))

    return segments


def split_segments_by_connectors(
    text: str, connectors: Dict[str, str], segmentation_mode: SegmentationMode = "connecteurs"
) -> List[str]:
    """Découper le texte en segments entre les connecteurs ou ponctuations choisies."""

    if not text:
        return []

    text = _remove_metadata_lines(text)

    connector_pattern = _build_connector_pattern(connectors)

    if connector_pattern is None:
        return []

    connector_found = connector_pattern.search(text)

    if connector_found is None:
        return [text]

    include_punctuation = segmentation_mode == "connecteurs_et_ponctuation"

    pattern = _build_boundary_pattern(
        connectors, include_punctuation, connector_pattern=connector_pattern
    )

    if pattern is None:
        return []

    segments_with_boundaries = _segments_with_boundaries(
        text, pattern, connector_pattern
    )

    return [segment for segment, _, _ in segments_with_boundaries]


def compute_segment_word_lengths(
    text: str,
    connectors: Dict[str, str],
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> List[int]:
    """Obtenir la longueur (en mots) de chaque segment selon le mode de segmentation.

    Args:
        text: Texte complet à découper.
        connectors: Dictionnaire des connecteurs logiques.
        segmentation_mode: Mode de découpe (avec ou sans ponctuation forte).
        tokenization_mode: Méthode de comptage des mots (regex simple ou spaCy).
    """

    segments = split_segments_by_connectors(text, connectors, segmentation_mode)
    lengths = []

    for segment in segments:
        tokens = _tokenize(segment, tokenization_mode)

        if tokens:
            lengths.append(len(tokens))

    return lengths


def segments_with_word_lengths(
    text: str,
    connectors: Dict[str, str],
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> List[Dict[str, str | int]]:
    """Retourner chaque segment avec sa longueur en mots."""

    if not text:
        return []

    text = _remove_metadata_lines(text)

    connector_pattern = _build_connector_pattern(connectors)

    if connector_pattern is None:
        return []

    connector_found = connector_pattern.search(text)

    if connector_found is None:
        tokens = _tokenize(text, tokenization_mode)
        if tokens:
            return [
                {
                    "segment": text.strip(),
                    "segment_avec_marqueurs": text.strip(),
                    "longueur": len(tokens),
                    "connecteur_precedent": "",
                    "connecteur_suivant": "",
                }
            ]
        return []

    include_punctuation = segmentation_mode == "connecteurs_et_ponctuation"

    pattern = _build_boundary_pattern(
        connectors, include_punctuation, connector_pattern=connector_pattern
    )

    if pattern is None:
        return []

    segments = _segments_with_boundaries(text, pattern, connector_pattern)
    entries: List[Dict[str, str | int]] = []

    for segment, previous_connector, next_connector in segments:
        tokens = _tokenize(segment, tokenization_mode)

        if tokens:
            entries.append(
                {
                    "segment": segment.strip(),
                    "segment_avec_marqueurs": _format_segment_with_markers(
                        segment, previous_connector, next_connector
                    ),
                    "longueur": len(tokens),
                    "connecteur_precedent": (previous_connector or ""),
                    "connecteur_suivant": (next_connector or ""),
                }
            )

    return entries


def average_segment_length(
    text: str,
    connectors: Dict[str, str],
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> float:
    """Calculer la Longueur Moyenne des Segments (LMS)."""

    lengths = compute_segment_word_lengths(
        text, connectors, segmentation_mode, tokenization_mode
    )

    if not lengths:
        return 0.0

    return float(mean(lengths))


def average_segment_length_by_modality(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    modalities: Optional[Iterable[str]] = None,
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
) -> pd.DataFrame:
    """Calculer la LMS par modalité pour une variable donnée."""

    if dataframe.empty:
        return pd.DataFrame(columns=["modalite", "segments", "lms"])

    filtered_df = filter_dataframe_by_modalities(dataframe, variable, modalities)

    if not variable or variable not in filtered_df.columns or filtered_df.empty:
        return pd.DataFrame(columns=["modalite", "segments", "lms"])

    rows: List[Dict[str, float | int | str]] = []

    for modality, subset in filtered_df.groupby(variable):
        text_value = build_text_from_dataframe(subset)
        lengths = compute_segment_word_lengths(
            text_value, connectors, segmentation_mode, tokenization_mode
        )
        lms_value = float(mean(lengths)) if lengths else 0.0

        rows.append(
            {
                "modalite": modality,
                "segments": len(lengths),
                "lms": lms_value,
            }
        )

    return pd.DataFrame(rows).sort_values("modalite").reset_index(drop=True)


def resumer_longueurs_segments(
    longueurs: List[int], seuil_segment_court: int = 10
) -> Optional[Dict[str, float]]:
    """Résumer les longueurs d'une réponse avec des indicateurs robustes.

    - LMS : moyenne des longueurs non nulles
    - Écart-type : dispersion absolue des longueurs
    - Coefficient de variation : écart-type / moyenne (0 si moyenne nulle)
    - Médiane : valeur médiane des longueurs
    - Proportion de segments courts : part des segments dont la longueur est
      inférieure ou égale au ``seuil_segment_court``.
    """

    if not longueurs:
        return None

    valeurs = np.array(longueurs, dtype=float)
    lms = float(np.mean(valeurs)) if valeurs.size else 0.0
    ecart_type = float(np.std(valeurs)) if valeurs.size else 0.0
    coefficient_variation = ecart_type / lms if lms else 0.0
    mediane = float(np.median(valeurs)) if valeurs.size else 0.0
    proportion_courts = 0.0

    if seuil_segment_court > 0:
        proportion_courts = float(np.mean(valeurs <= seuil_segment_court))

    return {
        "n_segments": int(valeurs.size),
        "somme_longueurs": float(valeurs.sum()),
        "lms": lms,
        "ecart_type": ecart_type,
        "coefficient_variation": coefficient_variation,
        "mediane": mediane,
        "proportion_courts": proportion_courts,
    }


def resumer_reponses_par_modalite(
    dataframe: pd.DataFrame,
    variable: Optional[str],
    connectors: Dict[str, str],
    modalities: Optional[Iterable[str]] = None,
    segmentation_mode: SegmentationMode = "connecteurs",
    tokenization_mode: TokenizationMode = "regex",
    seuil_segment_court: int = 10,
) -> Tuple[pd.DataFrame, int]:
    """Calculer les indicateurs par réponse et les regrouper par modalité."""

    if dataframe.empty or not variable or variable not in dataframe.columns:
        return pd.DataFrame(), 0

    filtered_df = filter_dataframe_by_modalities(dataframe, variable, modalities)

    if filtered_df.empty:
        return pd.DataFrame(), 0

    lignes: List[Dict[str, float | str]] = []
    reponses_ignorees = 0

    for _, row in filtered_df.iterrows():
        modalite = row.get(variable)
        texte = build_text_from_dataframe(pd.DataFrame([row]))

        if pd.isna(modalite) or not texte:
            reponses_ignorees += 1
            continue

        longueurs = compute_segment_word_lengths(
            texte, connectors, segmentation_mode, tokenization_mode
        )

        resume = resumer_longueurs_segments(longueurs, seuil_segment_court)

        if resume is None:
            reponses_ignorees += 1
            continue

        lignes.append({"modalite": modalite, **resume})

    return pd.DataFrame(lignes), reponses_ignorees


def statistiques_par_modalite(resumes: pd.DataFrame) -> pd.DataFrame:
    """Agrégations (moyenne, médiane, écart-type, CV, proportion courte) par modalité."""

    if resumes.empty or "modalite" not in resumes.columns:
        return pd.DataFrame()

    colonnes_mesures = {
        "lms",
        "mediane",
        "ecart_type",
        "coefficient_variation",
        "proportion_courts",
        "n_segments",
        "somme_longueurs",
    }

    if not colonnes_mesures.issubset(resumes.columns):
        return pd.DataFrame()

    regroupement = resumes.groupby("modalite")

    stats_df = regroupement.agg(
        somme_longueurs=("somme_longueurs", "sum"),
        n_segments=("n_segments", "sum"),
        mediane_reponses=("mediane", "median"),
        ecart_type_moyen=("ecart_type", "mean"),
        cv_moyen=("coefficient_variation", "mean"),
        proportion_courts_moyenne=("proportion_courts", "mean"),
        n_reponses=("modalite", "size"),
    )

    stats_df["lms_moyenne"] = stats_df.apply(
        lambda row: (row["somme_longueurs"] / row["n_segments"]) if row["n_segments"] else 0.0,
        axis=1,
    )

    return (
        stats_df.reset_index()
        .drop(columns=["somme_longueurs", "n_segments"])
        .rename(columns={"modalite": "modalite"})
        .sort_values("modalite")
    )
