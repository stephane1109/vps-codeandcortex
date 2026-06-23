"""Outils pour calculer la lisibilité d'un texte avec la formule Flesch-Kincaid."""

from __future__ import annotations

import re
from typing import Dict, List

READABILITY_SCALE = [
    {
        "range": "100.00–90.00",
        "min": 90.0,
        "max": 100.0,
        "niveau": "Cours Moyen II ou 7e",
        "description": "Très facile à lire. Facilement compréhensible par un élève moyen de 11 ans.",
    },
    {
        "range": "90.0–80.0",
        "min": 80.0,
        "max": 90.0,
        "niveau": "6e",
        "description": "Facile à lire. Anglais conversationnel pour les consommateurs.",
    },
    {
        "range": "80.0–70.0",
        "min": 70.0,
        "max": 80.0,
        "niveau": "5e",
        "description": "Plutôt facile à lire.",
    },
    {
        "range": "70.0–60.0",
        "min": 60.0,
        "max": 70.0,
        "niveau": "4e et 3e",
        "description": "En clair. Facilement compréhensible par les élèves de 13 à 15 ans.",
    },
    {
        "range": "60.0–50.0",
        "min": 50.0,
        "max": 60.0,
        "niveau": "Seconde vers Terminale",
        "description": "Plutôt difficile à lire.",
    },
    {
        "range": "50.0–30.0",
        "min": 30.0,
        "max": 50.0,
        "niveau": "Université ou Grande Ecole",
        "description": "Difficile à lire.",
    },
    {
        "range": "30.0–0.0",
        "min": 0.0,
        "max": 30.0,
        "niveau": "Diplôme universitaire",
        "description": "Très difficile à lire. Mieux compris par les diplômés universitaires.",
    },
]

VOWELS = "aeiouyàâäéèêëîïôöùûüÿœ"


def split_sentences(text: str) -> List[str]:
    """Découper un texte en phrases approximatives en se basant sur la ponctuation."""

    sentences = re.split(r"[.!?;:]+|\n+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def tokenize_words(text: str) -> List[str]:
    """Extraire les mots du texte en ignorant la ponctuation."""

    return re.findall(r"[\w']+", text.lower())


def count_syllables_in_word(word: str) -> int:
    """Estimer le nombre de syllabes dans un mot en comptant les groupes de voyelles."""

    cleaned = re.sub(r"[^a-zàâäéèêëîïôöùûüÿœç-]", "", word.lower())
    if not cleaned:
        return 0

    vowel_groups = re.findall(rf"[{VOWELS}]+", cleaned)
    syllables = len(vowel_groups)

    if cleaned.endswith("e") and syllables > 1:
        syllables -= 1

    return max(syllables, 1)


def count_syllables(text: str) -> int:
    """Compter les syllabes dans un texte en agrégeant le total des mots."""

    return sum(count_syllables_in_word(word) for word in tokenize_words(text))


def compute_flesch_kincaid_metrics(text: str) -> Dict[str, float]:
    """Calculer les indicateurs de lisibilité Flesch-Kincaid pour un texte."""

    sentences = split_sentences(text)
    words = tokenize_words(text)

    sentence_count = max(len(sentences), 1)
    word_count = len(words)
    syllable_count = count_syllables(text)

    if word_count == 0:
        return {
            "sentences": 0,
            "words": 0,
            "syllables": 0,
            "reading_ease": 0.0,
            "grade_level": 0.0,
        }

    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_count / word_count if word_count else 0

    reading_ease = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    grade_level = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

    return {
        "sentences": sentence_count,
        "words": word_count,
        "syllables": syllable_count,
        "reading_ease": reading_ease,
        "grade_level": grade_level,
    }


def get_readability_band(score: float) -> Dict[str, str | float]:
    """Retourner l'entrée de l'échelle correspondant au score fourni."""

    for band in READABILITY_SCALE:
        if band["min"] <= score <= band["max"]:
            return band

    if score < 0:
        return READABILITY_SCALE[-1]

    return READABILITY_SCALE[0]


def interpret_reading_ease(score: float) -> str:
    """Fournir une interprétation qualitative du score de lisibilité."""

    band = get_readability_band(score)
    return f"{band['description']} ({band['niveau']}, de {band['min']:.1f} à {band['max']:.1f})."
