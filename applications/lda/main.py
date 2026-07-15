from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyLDAvis
import pyLDAvis.gensim_models as gensimvis
import spacy
import streamlit as st
import streamlit.components.v1 as components
from gensim import corpora
from gensim.models.ldamodel import LdaModel
from gensim.models.phrases import Phraser, Phrases
from wordcloud import WordCloud

from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_NAME = "LDA"
APP_TICKET_DEFAULT_ID = "lda"
DEFAULT_SPACY_MODEL = os.getenv("LDA_SPACY_MODEL", "fr_core_news_md").strip() or "fr_core_news_md"
DEFAULT_POS = ["NOUN", "ADJ", "PROPN"]
ALL_POS = [
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
]


def normaliser_nom_fichier(value: str, fallback: str = "lda") -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or fallback


@st.cache_resource(show_spinner=False)
def charger_modele_spacy(model_name: str):
    try:
        return spacy.load(model_name, disable=["ner"])
    except Exception as exc:
        raise RuntimeError(
            f"Le modèle spaCy `{model_name}` n'est pas disponible dans l'image Docker. "
            "Modifie LDA_SPACY_MODEL ou installe le modèle dans le Dockerfile."
        ) from exc


def lire_corpus_iramuuteq(contenu: str) -> list[str]:
    documents: list[str] = []
    courant: list[str] = []
    for ligne in contenu.splitlines():
        if ligne.strip().startswith("****"):
            if courant:
                documents.append("\n".join(courant).strip())
                courant = []
            continue
        if ligne.strip():
            courant.append(ligne.strip())
    if courant:
        documents.append("\n".join(courant).strip())
    if not documents and contenu.strip():
        documents = [contenu.strip()]
    return [document for document in documents if document]


def lire_fichiers_uploades(fichiers) -> tuple[list[str], list[str]]:
    documents: list[str] = []
    noms_sources: list[str] = []
    for fichier in fichiers or []:
        texte = fichier.getvalue().decode("utf-8", errors="replace")
        docs = lire_corpus_iramuuteq(texte)
        documents.extend(docs)
        noms_sources.extend([fichier.name] * len(docs))
    return documents, noms_sources


def preprocess_documents(
    documents: list[str],
    model_name: str,
    pos_selection: list[str],
    retirer_stopwords: bool,
    lemmatiser: bool,
    min_token_length: int,
) -> list[list[str]]:
    nlp = charger_modele_spacy(model_name)
    textes: list[list[str]] = []
    pos_set = set(pos_selection)
    for doc in nlp.pipe(documents, batch_size=20):
        tokens: list[str] = []
        for token in doc:
            if not token.is_alpha:
                continue
            if retirer_stopwords and token.is_stop:
                continue
            if pos_set and token.pos_ not in pos_set:
                continue
            value = token.lemma_ if lemmatiser else token.text
            value = value.strip().lower()
            if len(value) < min_token_length:
                continue
            tokens.append(value)
        textes.append(tokens)
    return textes


def appliquer_bigrammes(textes: list[list[str]], min_count: int, threshold: float) -> tuple[list[list[str]], list[str]]:
    if not textes:
        return textes, []
    phrases = Phrases(textes, min_count=min_count, threshold=threshold)
    bigram = Phraser(phrases)
    textes_bigrams = [bigram[texte] for texte in textes]
    bigrammes = sorted({mot for texte in textes_bigrams for mot in texte if "_" in mot})
    return textes_bigrams, bigrammes


def creer_histogramme_frequences(dictionary: corpora.Dictionary) -> bytes:
    frequences = [dictionary.dfs[word_id] for word_id in dictionary.keys()]
    figure, axe = plt.subplots(figsize=(10, 6))
    if frequences:
        axe.hist(frequences, bins=80, log=True, color="#f97316", edgecolor="#7c2d12", alpha=0.82)
    axe.set_title("Distribution des fréquences de mots")
    axe.set_xlabel("Fréquence du mot")
    axe.set_ylabel("Nombre de mots")
    axe.grid(alpha=0.2)
    buffer = io.BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=160)
    plt.close(figure)
    buffer.seek(0)
    return buffer.getvalue()


def dataframe_stats_frequences(dictionary: corpora.Dictionary) -> pd.DataFrame:
    frequences = np.array([dictionary.dfs[word_id] for word_id in dictionary.keys()], dtype=float)
    if len(frequences) == 0:
        return pd.DataFrame(
            [{"Moyenne": 0, "Médiane": 0, "Percentile 10": 0, "Percentile 90": 0, "Termes": 0}]
        )
    return pd.DataFrame(
        [
            {
                "Moyenne": round(float(np.mean(frequences)), 2),
                "Médiane": round(float(np.median(frequences)), 2),
                "Percentile 10": round(float(np.percentile(frequences, 10)), 2),
                "Percentile 90": round(float(np.percentile(frequences, 90)), 2),
                "Termes": int(len(frequences)),
            }
        ]
    )


def dataframe_topics(lda: LdaModel, num_topics: int, num_words: int) -> pd.DataFrame:
    rows = []
    for topic_id, topic_words in lda.show_topics(
        formatted=False,
        num_topics=num_topics,
        num_words=num_words,
    ):
        for rang, (word, probability) in enumerate(topic_words, start=1):
            rows.append(
                {
                    "Topic": topic_id + 1,
                    "Rang": rang,
                    "Mot": word,
                    "Probabilité": round(float(probability), 6),
                }
            )
    return pd.DataFrame(rows)


def creer_wordclouds(lda: LdaModel, num_topics: int, num_words: int) -> dict[str, bytes]:
    images: dict[str, bytes] = {}
    for topic_id, topic_words in lda.show_topics(
        formatted=False,
        num_topics=num_topics,
        num_words=num_words,
    ):
        frequencies = {word: float(probability) for word, probability in topic_words}
        if not frequencies:
            continue
        wordcloud = WordCloud(
            width=1200,
            height=800,
            background_color="white",
            colormap="Oranges",
        ).generate_from_frequencies(frequencies)
        buffer = io.BytesIO()
        wordcloud.to_image().save(buffer, format="PNG")
        buffer.seek(0)
        images[f"topic_{topic_id + 1:02d}_wordcloud.png"] = buffer.getvalue()
    return images


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def construire_archive(exports: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in exports.items():
            archive.writestr(filename, content)
    buffer.seek(0)
    return buffer.getvalue()


def run_lda_analysis(
    documents: list[str],
    noms_sources: list[str],
    *,
    model_name: str,
    pos_selection: list[str],
    retirer_stopwords: bool,
    lemmatiser: bool,
    min_token_length: int,
    bigram_min_count: int,
    bigram_threshold: float,
    no_below: int,
    no_above: float,
    num_topics: int,
    passes: int,
    random_state: int,
    words_per_topic: int,
) -> dict[str, object]:
    progress = st.progress(0, text="Préparation du corpus")
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    progress.progress(10, text="Prétraitement spaCy")
    textes = preprocess_documents(
        documents,
        model_name=model_name,
        pos_selection=pos_selection,
        retirer_stopwords=retirer_stopwords,
        lemmatiser=lemmatiser,
        min_token_length=min_token_length,
    )
    textes = [texte for texte in textes if texte]
    if not textes:
        raise RuntimeError("Aucun document exploitable après prétraitement.")

    progress.progress(25, text="Détection des bigrammes")
    textes_bigrams, bigrammes = appliquer_bigrammes(textes, bigram_min_count, bigram_threshold)

    progress.progress(40, text="Création du dictionnaire")
    dictionary_raw = corpora.Dictionary(textes_bigrams)
    histogramme_png = creer_histogramme_frequences(dictionary_raw)
    stats_freq = dataframe_stats_frequences(dictionary_raw)

    dictionary = corpora.Dictionary(textes_bigrams)
    dictionary.filter_extremes(no_below=no_below, no_above=no_above)
    corpus = [dictionary.doc2bow(texte) for texte in textes_bigrams]
    corpus = [doc for doc in corpus if doc]
    if len(dictionary) == 0 or not corpus:
        raise RuntimeError("Le dictionnaire est vide après filtrage. Diminue no_below ou augmente no_above.")

    progress.progress(58, text="Calcul du modèle LDA")
    lda = LdaModel(
        corpus=corpus,
        num_topics=num_topics,
        id2word=dictionary,
        passes=passes,
        random_state=random_state,
        minimum_probability=0.0,
    )

    progress.progress(74, text="Préparation des résultats")
    topics_df = dataframe_topics(lda, num_topics, words_per_topic)
    bigrammes_df = pd.DataFrame({"Bigramme": bigrammes})
    documents_df = pd.DataFrame(
        {
            "Document": range(1, len(textes_bigrams) + 1),
            "Source": noms_sources[: len(textes_bigrams)] if noms_sources else ["corpus"] * len(textes_bigrams),
            "Tokens retenus": [len(texte) for texte in textes_bigrams],
            "Texte prétraité": [" ".join(texte) for texte in textes_bigrams],
        }
    )

    progress.progress(86, text="Création pyLDAvis et wordclouds")
    lda_html = ""
    try:
        lda_display = gensimvis.prepare(lda, corpus, dictionary, sort_topics=False)
        lda_html = pyLDAvis.prepared_data_to_html(lda_display)
    except Exception as exc:
        lda_html = f"<p>Visualisation pyLDAvis indisponible : {exc}</p>"
    wordclouds = creer_wordclouds(lda, num_topics, min(max(words_per_topic, 20), 60))

    exports: dict[str, bytes] = {
        "lda_topics.csv": csv_bytes(topics_df),
        "bigrammes_trouves.csv": csv_bytes(bigrammes_df),
        "documents_pretraites.csv": csv_bytes(documents_df),
        "statistiques_frequences.csv": csv_bytes(stats_freq),
        "distribution_frequences.png": histogramme_png,
        "lda_visualization.html": lda_html.encode("utf-8"),
    }
    exports.update(wordclouds)
    archive = construire_archive(exports)
    progress.progress(100, text="Analyse LDA terminée")

    return {
        "texts": textes_bigrams,
        "dictionary": dictionary,
        "topics_df": topics_df,
        "bigrammes_df": bigrammes_df,
        "documents_df": documents_df,
        "stats_freq": stats_freq,
        "histogramme_png": histogramme_png,
        "lda_html": lda_html,
        "wordclouds": wordclouds,
        "archive": archive,
        "documents_count": len(textes_bigrams),
        "terms_count": len(dictionary),
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }


st.set_page_config(page_title="LDA", layout="wide", initial_sidebar_state="expanded")
enforce_streamlit_access(APP_TICKET_DEFAULT_ID, APP_NAME)

st.title("Analyse discriminante linéaire (LDA)")
st.caption("version VPS - www.codeandcortex.fr")
st.markdown("<br>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Paramètres LDA")
    spacy_model = st.text_input("Modèle spaCy", value=DEFAULT_SPACY_MODEL)
    pos_selection = st.multiselect("POS à conserver", options=ALL_POS, default=DEFAULT_POS)
    retirer_stopwords = st.checkbox("Retirer les stopwords spaCy", value=True)
    lemmatiser = st.checkbox("Lemmatisation", value=True)
    min_token_length = st.number_input("Longueur minimale des mots", min_value=1, max_value=10, value=2, step=1)

    st.subheader("Bigrammes")
    bigram_min_count = st.number_input("min_count", min_value=1, max_value=50, value=5, step=1)
    bigram_threshold = st.number_input("threshold", min_value=1.0, max_value=100.0, value=10.0, step=1.0)

    st.subheader("Filtrage dictionnaire")
    no_below = st.number_input("no_below", min_value=0, max_value=100, value=1, step=1)
    no_above = st.slider("no_above", min_value=0.05, max_value=1.0, value=0.6, step=0.05)

    st.subheader("Modèle")
    num_topics = st.number_input("Nombre de topics", min_value=2, max_value=50, value=12, step=1)
    passes = st.number_input("Passes", min_value=1, max_value=100, value=15, step=1)
    random_state = st.number_input("Random state", min_value=0, max_value=999999, value=42, step=1)
    words_per_topic = st.number_input("Mots affichés par topic", min_value=5, max_value=60, value=20, step=5)

uploaded_files = st.file_uploader(
    "Importer un ou plusieurs corpus texte",
    type=["txt"],
    accept_multiple_files=True,
    help="Les lignes commençant par **** sont reconnues comme séparateurs de documents IRaMuTeQ.",
)

st.info(
    "Le script source est adapté pour le VPS : import texte, segmentation IRaMuTeQ, "
    "prétraitement spaCy, bigrammes, filtrage du dictionnaire, LDA, pyLDAvis, CSV et wordclouds."
)

if "lda_result" not in st.session_state:
    st.session_state.lda_result = None

if st.button("Lancer le test LDA", type="primary"):
    documents, noms_sources = lire_fichiers_uploades(uploaded_files)
    if not documents:
        st.error("Importe au moins un fichier texte avant de lancer l'analyse.")
    else:
        try:
            st.session_state.lda_result = run_lda_analysis(
                documents,
                noms_sources,
                model_name=spacy_model,
                pos_selection=pos_selection,
                retirer_stopwords=retirer_stopwords,
                lemmatiser=lemmatiser,
                min_token_length=int(min_token_length),
                bigram_min_count=int(bigram_min_count),
                bigram_threshold=float(bigram_threshold),
                no_below=int(no_below),
                no_above=float(no_above),
                num_topics=int(num_topics),
                passes=int(passes),
                random_state=int(random_state),
                words_per_topic=int(words_per_topic),
            )
        except Exception as exc:
            st.session_state.lda_result = None
            st.error(f"Erreur LDA : {exc}")

result = st.session_state.lda_result
if result:
    st.success(
        f"Analyse terminée : {result['documents_count']} document(s), "
        f"{result['terms_count']} terme(s) conservé(s)."
    )
    st.download_button(
        "Télécharger l'archive complète",
        data=result["archive"],
        file_name=f"lda_resultats_{result['timestamp']}.zip",
        mime="application/zip",
    )

    onglet_topics, onglet_visualisation, onglet_wordclouds, onglet_diagnostics = st.tabs(
        ["Topics", "pyLDAvis", "Nuages de mots", "Diagnostics"]
    )

    with onglet_topics:
        st.dataframe(result["topics_df"], use_container_width=True)
        st.download_button(
            "Télécharger les topics CSV",
            data=csv_bytes(result["topics_df"]),
            file_name="lda_topics.csv",
            mime="text/csv",
        )

    with onglet_visualisation:
        components.html(result["lda_html"], height=820, scrolling=True)

    with onglet_wordclouds:
        for filename, image_bytes in result["wordclouds"].items():
            st.markdown(f"#### {filename.replace('_wordcloud.png', '').replace('_', ' ').title()}")
            st.image(image_bytes, use_container_width=True)

    with onglet_diagnostics:
        st.markdown("### Bigrammes trouvés")
        st.dataframe(result["bigrammes_df"], use_container_width=True)
        st.markdown("### Statistiques de fréquence avant filtrage")
        st.dataframe(result["stats_freq"], use_container_width=True)
        st.image(result["histogramme_png"], caption="Distribution des fréquences de mots", use_container_width=True)
        st.markdown("### Documents prétraités")
        st.dataframe(result["documents_df"], use_container_width=True)
