"""### Outils autour des n-grammes

Le module fournit la tokenisation simplifiée, la construction de motifs
regex pour détecter des n-grammes et le calcul de statistiques ou de contexte
autour des séquences fréquentes. Il est utilisé pour analyser la répétition
ou la spécificité des expressions dans le corpus."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable, List, Sequence

import pandas as pd

TOKEN_PATTERN = re.compile(r"[\wÀ-ÖØ-öø-ÿ'-]+", re.UNICODE)


def tokenize_text(text: str) -> List[str]:
    """Convertir un texte en liste de mots normalisés."""

    return TOKEN_PATTERN.findall(text.lower())


def build_ngram_pattern(ngram_tokens: Sequence[str]) -> re.Pattern[str]:
    """Construire un motif regex tolérant à la ponctuation pour un n-gram donné."""

    cleaned_tokens = [
        str(token).strip()
        for token in ngram_tokens
        if str(token).strip()
    ]

    if not cleaned_tokens:
        return re.compile(r"$^")

    separator = r"[\W_]+"
    pattern = r"\b" + separator.join(re.escape(token) for token in cleaned_tokens) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def iter_ngrams(words: List[str], n: int) -> Iterable[tuple[str, ...]]:
    """Générer les n-grams pour une liste de mots donnée."""

    if n <= 0:
        return []

    return zip(*(words[i:] for i in range(n)))


def extract_ngram_context(
    text: str, ngram_tokens: tuple[str, ...], header: str | None = None, max_length: int = 240
) -> str:
    """Retourner la phrase (ou un extrait) contenant le n-gram recherché.

    Le contenu n'est pas échappé pour permettre l'affichage HTML en aval lorsque
    le texte source contient déjà du balisage (par exemple dans l'onglet « Texte
    annoté » de l'interface Streamlit).
    """

    pattern = build_ngram_pattern(ngram_tokens)
    sentences = re.split(r"(?<=[.!?;:])\s+", text)

    for sentence in sentences:
        if pattern.search(sentence):
            context = sentence.strip()
            break
    else:
        fallback = text.strip()
        context = fallback[:max_length].strip() if fallback else ""

    if header and context:
        context = f"{header.strip()} – {context}"
    elif header and not context:
        context = header.strip()

    if len(context) > max_length:
        return context[:max_length].rstrip() + "…"

    return context


def _deduplicate_contexts(contexts: list[dict[str, object]]) -> list[dict[str, object]]:
    """Supprimer les doublons d'occurrences tout en préservant l'ordre.

    Les occurrences peuvent être enregistrées plusieurs fois lorsqu'un même n-gram
    apparaît plusieurs fois dans un même texte ou au sein de la même phrase. Pour
    l'affichage, on ne conserve qu'une occurrence unique par combinaison de
    contexte, d'en-tête, de modalités et de texte complet.
    """

    seen = set()
    unique_contexts: list[dict[str, object]] = []

    for entry in contexts:
        key = (
            entry.get("contexte", ""),
            tuple(entry.get("modalites", []) or []),
            entry.get("entete", ""),
            entry.get("texte_complet", ""),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_contexts.append(entry)

    return unique_contexts


def compute_ngram_statistics(
    dataframe: pd.DataFrame,
    min_n: int = 3,
    max_n: int = 6,
    top_k: int = 10,
    specific_n: int | None = None,
    top_modalities: int = 3,
    min_frequency: int = 1,
    exclude_stopwords: bool = False,
    stop_words: Iterable[str] | None = None,
    sort_by: str = "frequency",
) -> pd.DataFrame:
    """Calculer les N-grams les plus fréquents et leur distribution par modalités.

    Parameters
    ----------
    dataframe:
        Table contenant au minimum une colonne ``texte`` et éventuellement des colonnes
        de variables/modalités.
    min_n / max_n:
        Tailles minimale et maximale des n-grams à considérer.
    top_k:
        Nombre d'entrées à conserver dans le classement final.
    specific_n:
        Si fourni, ne calcule que pour cette taille d'``n``. Ignorée si en dehors
        de l'intervalle ``min_n`` / ``max_n``.
    top_modalities:
        Nombre de modalités à afficher pour chaque n-gram.
    min_frequency:
        Fréquence minimale pour conserver un n-gram dans le résultat.
    exclude_stopwords / stop_words:
        Permettent d'ignorer les stopwords (par exemple ceux de NLTK) avant le calcul.
    sort_by:
        Ordre de tri des résultats : "frequency" (par défaut) ou "alphabetical".
    """

    variable_columns = [column for column in dataframe.columns if column not in ("texte", "entete")]

    if specific_n is not None and specific_n <= 0:
        raise ValueError("specific_n doit être supérieur ou égal à 1")

    requested_sizes: Sequence[int] = (
        [specific_n]
        if specific_n is not None and min_n <= specific_n <= max_n
        else list(range(min_n, max_n + 1))
    )

    min_frequency = max(1, int(min_frequency))
    stopword_set = set(stop_words) if stop_words else set()

    counts_by_size: dict[int, Counter[str]] = {size: Counter() for size in requested_sizes}
    modality_counts_by_size: dict[int, dict[str, Counter[str]]] = {
        size: defaultdict(Counter) for size in requested_sizes
    }
    contexts_by_size: dict[int, dict[str, list[dict[str, object]]]] = {
        size: defaultdict(list) for size in requested_sizes
    }

    for _, row in dataframe.iterrows():
        text_value = str(row.get("texte", "") or "")
        words = tokenize_text(text_value)

        if exclude_stopwords and stopword_set:
            words = [word for word in words if word not in stopword_set]

        if not words:
            continue

        modalities = [
            f"{column}={row[column]}" if pd.notna(row[column]) else f"{column}=Non défini"
            for column in variable_columns
        ] or ["Modalité non spécifiée"]

        for n in requested_sizes:
            for ngram_tokens in iter_ngrams(words, n):
                ngram = " ".join(ngram_tokens)
                counts_by_size[n][ngram] += 1

                for modality in modalities:
                    modality_counts_by_size[n][ngram][modality] += 1

                header = str(row.get("entete", "") or "")
                contexts_by_size[n][ngram].append(
                    {
                        "contexte": extract_ngram_context(
                            text_value, ngram_tokens, header=header
                        ),
                        "entete": header,
                        "modalites": modalities,
                        "texte_complet": text_value,
                    }
                )

    rows = []

    for n in requested_sizes:
        filtered_entries = [
            (ngram, frequency)
            for ngram, frequency in counts_by_size[n].items()
            if frequency >= min_frequency
        ]

        if sort_by == "alphabetical":
            selected_entries = sorted(filtered_entries, key=lambda item: item[0])[:top_k]
        else:
            selected_entries = sorted(filtered_entries, key=lambda item: item[1], reverse=True)[:top_k]

        for ngram, frequency in selected_entries:
            modalities_summary = modality_counts_by_size[n].get(ngram)
            modalities_display = (
                ", ".join(
                    f"{modality} ({count})"
                    for modality, count in modalities_summary.most_common(top_modalities)
                )
                if modalities_summary
                else "N/A"
            )

            context_entries = _deduplicate_contexts(contexts_by_size[n].get(ngram, []))
            first_context = context_entries[0].get("contexte", "") if context_entries else ""

            rows.append(
                {
                    "N-gram": ngram,
                    "Taille": len(ngram.split()),
                    "Fréquence": frequency,
                    "Modalités associées": modalities_display,
                    "Contexte": first_context,
                    "Occurrences détaillées": context_entries,
                }
            )

    return pd.DataFrame(rows)
