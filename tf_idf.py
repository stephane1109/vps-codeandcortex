"""### Visualisations TF-IDF et nuages de mots

Le module propose les composants Streamlit dédiés au calcul TF-IDF par
modalité, à la sélection des groupes étudiés et à la génération de nuages de
mots. Il s'appuie sur la similarité cosinus pour comparer les textes et offrir
un aperçu synthétique du vocabulaire saillant."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from wordcloud import WordCloud

from simicosinus import aggregate_texts_by_variable, get_french_stopwords


def _filter_modalities(
    dataframe: pd.DataFrame, variable: str, selected_modalities: Sequence[str] | None
) -> Dict[str, str]:
    """Assembler les textes en fonction des modalités choisies."""

    aggregated_texts = aggregate_texts_by_variable(dataframe, variable)

    if not selected_modalities:
        return aggregated_texts

    allowed_modalities = {str(modality) for modality in selected_modalities}
    return {
        modality: text
        for modality, text in aggregated_texts.items()
        if modality in allowed_modalities
    }


def compute_tfidf_scores(
    dataframe: pd.DataFrame,
    variable: str,
    selected_modalities: Sequence[str] | None = None,
    use_stopwords: bool = False,
    top_n: int = 20,
) -> Dict[str, List[tuple[str, float]]]:
    """Calculer les scores TF-IDF pour chaque modalité d'une variable."""

    if variable not in dataframe.columns:
        raise KeyError(f"La variable '{variable}' est absente du tableau fourni.")

    cleaned_df = dataframe.dropna(subset=["texte", variable])
    if cleaned_df.empty:
        return {}

    aggregated_texts = _filter_modalities(cleaned_df, variable, selected_modalities)

    if not aggregated_texts:
        return {}

    corpus = list(aggregated_texts.values())
    stop_words: Iterable[str] | None = get_french_stopwords() if use_stopwords else None

    vectorizer = TfidfVectorizer(stop_words=stop_words)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()

    results: Dict[str, List[tuple[str, float]]] = {}
    safe_top_n = max(1, int(top_n))

    for idx, modality in enumerate(aggregated_texts.keys()):
        row = tfidf_matrix[idx].toarray().ravel()
        nonzero_indices = row.nonzero()[0]

        if len(nonzero_indices) == 0:
            continue

        sorted_indices = nonzero_indices[row[nonzero_indices].argsort()[::-1]]
        top_indices = sorted_indices[:safe_top_n]

        top_terms = [
            (feature_names[i], float(row[i]))
            for i in top_indices
            if row[i] > 0
        ]

        if top_terms:
            results[str(modality)] = top_terms

    return results


def build_tfidf_dataframe(tfidf_scores: Dict[str, List[tuple[str, float]]]) -> pd.DataFrame:
    """Convertir les scores TF-IDF en tableau long."""

    rows: List[Dict[str, float | str]] = []

    for modality, terms in tfidf_scores.items():
        for term, score in terms:
            rows.append({"modalite": modality, "terme": term, "score_tfidf": score})

    return pd.DataFrame(rows)


def render_wordcloud(top_terms: List[tuple[str, float]]) -> None:
    """Afficher un nuage de mots pour les termes fournis."""

    if not top_terms:
        st.info("Aucun terme disponible pour générer un nuage de mots.")
        return

    frequencies = {term: score for term, score in top_terms}
    wordcloud = WordCloud(width=800, height=500, background_color="white")
    cloud_image = wordcloud.generate_from_frequencies(frequencies)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    ax.imshow(cloud_image, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout()

    st.pyplot(fig, use_container_width=True)

    plt.close(fig)


def render_tfidf_tab(dataframe: pd.DataFrame) -> None:
    """Afficher l'onglet TF-IDF pour explorer les modalités d'une variable."""

    st.subheader("Analyse TF-IDF par variable")

    st.markdown(
        """
        Le TF-IDF (Term Frequency – Inverse Document Frequency) mesure l'importance
        d'un terme dans un document en combinant :

        - la fréquence du terme dans le document (TF) ;
        - la rareté du terme dans l'ensemble des documents (IDF), ce qui réduit le poids des mots courants.

        Dans cette application, chaque modalité concatène l'ensemble de ses textes avant
        le calcul : les scores sont donc basés sur le texte complet de chaque modalité,
        et non sur des extraits filtrés par les connecteurs.
        """
    )

    if dataframe.empty:
        st.info("Aucune donnée disponible après filtrage.")
        return

    excluded_variables = {"texte", "entete"}
    available_variables = [
        column for column in dataframe.columns if column not in excluded_variables
    ]
    if not available_variables:
        st.info("Aucune variable disponible pour calculer le TF-IDF.")
        return

    st.subheader("Sélection des variables/modalités")
    variable_choice = st.selectbox(
        "Variable à analyser",
        available_variables,
        help="Choisissez la variable pour laquelle calculer le TF-IDF et sélectionner ses modalités.",
    )

    modality_options = sorted(
        dataframe[variable_choice].dropna().astype(str).unique().tolist()
    )
    selected_modalities = st.multiselect(
        "Modalités à inclure",
        modality_options,
        default=modality_options,
        help="Sélectionnez les modalités pour lesquelles calculer les scores TF-IDF.",
    )

    filtered_df = dataframe[
        dataframe[variable_choice].astype(str).isin(selected_modalities)
    ]

    if filtered_df.empty:
        st.info("Aucun texte ne correspond aux modalités sélectionnées.")
        return

    top_n = st.slider(
        "Nombre de termes à afficher",
        min_value=5,
        max_value=50,
        value=20,
        step=1,
    )

    use_stopwords = st.checkbox(
        "Supprimer les stopwords français (NLTK)",
        value=False,
        help="Retire les mots vides avant le calcul des scores TF-IDF.",
    )

    tfidf_scores = compute_tfidf_scores(
        filtered_df,
        variable_choice,
        selected_modalities=selected_modalities or None,
        use_stopwords=use_stopwords,
        top_n=top_n,
    )

    if not tfidf_scores:
        st.info("Aucun terme significatif trouvé pour les paramètres sélectionnés.")
        return

    tfidf_df = build_tfidf_dataframe(tfidf_scores)
    st.dataframe(
        tfidf_df.sort_values(["modalite", "score_tfidf"], ascending=[True, False]),
        use_container_width=True,
    )

    for modality in sorted(tfidf_scores.keys()):
        st.markdown(f"#### Nuage de mots – {variable_choice} : {modality}")
        render_wordcloud(tfidf_scores.get(modality, []))
