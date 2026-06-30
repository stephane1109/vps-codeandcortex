"""Outils pour calculer la lisibilite d'un texte avec la formule Flesch-Kincaid."""

from __future__ import annotations

import re
from typing import Dict, List

READABILITY_SCALE = [
    {
        "range": "100.00–90.00",
        "min": 90.0,
        "max": 100.0,
        "niveau": "Cours Moyen II ou 7e",
        "description": "Tres facile a lire. Facilement comprehensible par un eleve moyen de 11 ans.",
    },
    {
        "range": "90.0–80.0",
        "min": 80.0,
        "max": 90.0,
        "niveau": "6e",
        "description": "Facile a lire. Anglais conversationnel pour les consommateurs.",
    },
    {
        "range": "80.0–70.0",
        "min": 70.0,
        "max": 80.0,
        "niveau": "5e",
        "description": "Plutot facile a lire.",
    },
    {
        "range": "70.0–60.0",
        "min": 60.0,
        "max": 70.0,
        "niveau": "4e et 3e",
        "description": "En clair. Facilement comprehensible par les eleves de 13 a 15 ans.",
    },
    {
        "range": "60.0–50.0",
        "min": 50.0,
        "max": 60.0,
        "niveau": "Seconde vers Terminale",
        "description": "Plutot difficile a lire.",
    },
    {
        "range": "50.0–30.0",
        "min": 30.0,
        "max": 50.0,
        "niveau": "Universite ou Grande Ecole",
        "description": "Difficile a lire.",
    },
    {
        "range": "30.0–0.0",
        "min": 0.0,
        "max": 30.0,
        "niveau": "Diplome universitaire",
        "description": "Tres difficile a lire. Mieux compris par les diplomes universitaires.",
    },
]

VOWELS = "aeiouyàâäéèêëîïôöùûüÿœ"


def split_sentences(text: str) -> List[str]:
    """Decouper un texte en phrases approximatives en se basant sur la ponctuation."""

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
    """Compter les syllabes dans un texte en agregeant le total des mots."""

    return sum(count_syllables_in_word(word) for word in tokenize_words(text))


def compute_flesch_kincaid_metrics(text: str) -> Dict[str, float]:
    """Calculer les indicateurs de lisibilite Flesch-Kincaid pour un texte."""

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
    """Retourner l'entree de l'echelle correspondant au score fourni."""

    for band in READABILITY_SCALE:
        if band["min"] <= score <= band["max"]:
            return band

    if score < 0:
        return READABILITY_SCALE[-1]

    return READABILITY_SCALE[0]


def interpret_reading_ease(score: float) -> str:
    """Fournir une interpretation qualitative du score de lisibilite."""

    band = get_readability_band(score)
    return f"{band['description']} ({band['niveau']}, de {band['min']:.1f} a {band['max']:.1f})."
