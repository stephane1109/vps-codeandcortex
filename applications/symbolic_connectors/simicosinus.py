"""### Similarité cosinus entre modalités

Ce fichier rassemble les fonctions qui agrègent les textes par variable,
nettoient les stopwords et calculent la similarité cosinus à partir de
matrices TF-IDF. Il facilite la comparaison des styles ou thématiques entre
groupes du corpus."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

import pandas as pd
from nltk import download
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def aggregate_texts_by_variable(dataframe: pd.DataFrame, variable: str) -> Dict[str, str]:
    """Assembler les textes par modalité pour une variable donnée.

    Seules les lignes où la variable est définie sont conservées. Les textes vides
    ou manquants sont ignorés afin de ne calculer la similarité qu'à partir de
    contenus existants.
    """

    if variable not in dataframe.columns:
        raise KeyError(f"La variable '{variable}' est absente du tableau fourni.")

    aggregated_texts: Dict[str, str] = {}

    for modality, subset in dataframe.dropna(subset=[variable]).groupby(variable):
        texts = subset["texte"].dropna().astype(str).tolist()
        combined_text = " ".join(texts).strip()

        if combined_text:
            aggregated_texts[str(modality)] = combined_text

    return aggregated_texts


def get_french_stopwords() -> List[str]:
    """Retourner la liste des stopwords français fournie par NLTK.

    Le téléchargement des stopwords est effectué à la volée si nécessaire.
    """

    try:
        return stopwords.words("french")
    except LookupError:
        download("stopwords")
        return stopwords.words("french")


def aggregate_texts_by_variables(
    dataframe: pd.DataFrame, variables: Sequence[str]
) -> Dict[str, str]:
    """Assembler les textes par combinaison de variables/modalités.

    Les groupes sont nommés en concaténant les couples ``variable = valeur`` pour
    chaque modalité non vide. Les groupes sans texte sont ignorés afin de
    conserver uniquement les contenus exploitables pour la similarité cosinus.
    """

    if dataframe.empty:
        return {}

    valid_variables = [var for var in variables if var in dataframe.columns]

    if not valid_variables:
        return {}

    aggregated_texts: Dict[str, str] = {}

    grouped = dataframe.groupby(valid_variables, dropna=False)

    for group_values, subset in grouped:
        values = (
            group_values
            if isinstance(group_values, tuple)
            else (group_values,)
        )
        combination = dict(zip(valid_variables, values, strict=True))

        label_parts: list[str] = []
        for variable, value in combination.items():
            if pd.isna(value) or str(value).strip() == "":
                continue
            label_parts.append(f"{variable} = {value}")

        label = " | ".join(label_parts) if label_parts else "Non spécifié"

        texts = (
            subset.get("texte", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .map(str.strip)
        )

        combined_text = " ".join(text for text in texts if text)

        if combined_text:
            aggregated_texts[label] = combined_text

    return aggregated_texts


def compute_cosine_similarity_matrix(
    texts_by_group: Dict[str, str], stop_words: Iterable[str] | None = None
) -> pd.DataFrame:
    """Calculer une matrice de similarité cosinus à partir de textes regroupés."""

    if len(texts_by_group) < 2:
        return pd.DataFrame()

    labels = list(texts_by_group.keys())
    corpus = list(texts_by_group.values())

    vectorizer = TfidfVectorizer(stop_words=stop_words)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    return pd.DataFrame(similarity_matrix, index=labels, columns=labels)


def compute_cosine_similarity_by_variable(
    dataframe: pd.DataFrame, variable: str, use_stopwords: bool = False
) -> pd.DataFrame:
    """Retourner une matrice de similarité cosinus entre modalités d'une variable."""

    aggregated_texts = aggregate_texts_by_variable(dataframe, variable)

    if len(aggregated_texts) < 2:
        return pd.DataFrame()

    stop_words = get_french_stopwords() if use_stopwords else None

    return compute_cosine_similarity_matrix(aggregated_texts, stop_words=stop_words)


def format_aggregated_texts_for_export(
    aggregated_texts: Dict[str, str], variable: str
) -> str:
    """Construire un export texte avec les contenus concaténés par modalité.

    Chaque modalité est précédée d'un en-tête explicite pour faciliter la lecture
    du fichier téléchargé depuis l'onglet « Simi cosinus ».
    """

    if not aggregated_texts:
        return ""

    parts: list[str] = []

    for modality, text in sorted(aggregated_texts.items()):
        modality_header = f"*{variable} = {modality}"
        parts.append(f"{modality_header}\n{text.strip()}")

    return "\n\n".join(parts).strip()


def build_iramuteq_header(row: pd.Series, variables: Sequence[str]) -> str:
    """Reconstruire une ligne d'entête IRaMuTeQ à partir d'une ligne du DataFrame."""

    tokens: list[str] = ["****"]

    for variable in variables:
        value = row.get(variable, "")

        if pd.isna(value) or str(value).strip() == "":
            continue

        tokens.append(f"*{variable}_{value}")

    header = " ".join(tokens).strip()

    return header if header != "****" else ""


def concatenate_texts_with_headers(
    dataframe: pd.DataFrame, variables: Sequence[str]
) -> str:
    """Concaténer les textes selon les variables/modalités sélectionnées.

    Les lignes du DataFrame sont regroupées par combinaison de variables fournies.
    Pour chaque groupe, la première ligne est reconstituée au format IRaMuTeQ
    (``**** *variable_modalite``) afin de refléter la sélection effectuée dans
    l'onglet « Simi cosinus ».
    """

    if dataframe.empty:
        return ""

    valid_variables = [var for var in variables if var in dataframe.columns]

    if not valid_variables:
        return ""

    parts: list[str] = []

    grouped = dataframe.groupby(valid_variables, dropna=False)

    for _, group in grouped:
        if group.empty:
            continue

        header = build_iramuteq_header(group.iloc[0], valid_variables)
        combined_text = "\n".join(
            text.strip()
            for text in group.get("texte", pd.Series(dtype=str)).dropna().astype(str)
            if text.strip()
        ).strip()

        if not combined_text:
            continue

        if header:
            parts.append(f"{header}\n{combined_text}")
        else:
            parts.append(combined_text)

    return "\n\n".join(parts).strip()
