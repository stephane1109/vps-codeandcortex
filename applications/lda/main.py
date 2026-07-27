from __future__ import annotations

import io
import json
import math
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime

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


@dataclass
class UniteAnalyse:
    identifiant: str
    texte: str
    source: str
    type_unite: str


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


def segmenter_document(
    texte: str,
    longueur_min_segment: int,
    taille_segment_mots: int,
    segmenter_sur_ponctuation_forte: bool,
) -> list[str]:
    if segmenter_sur_ponctuation_forte:
        fragments = re.split(r"[\.!\?;:\n]+", texte)
        segments_ponctuation = [
            fragment.strip()
            for fragment in fragments
            if fragment.strip() and len(fragment.strip()) >= longueur_min_segment
        ]
        if segments_ponctuation:
            return segments_ponctuation

    mots = re.findall(r"\S+", texte)
    taille = max(5, int(taille_segment_mots))
    segments = []
    for debut in range(0, len(mots), taille):
        segment = " ".join(mots[debut : debut + taille]).strip()
        if segment and len(segment) >= longueur_min_segment:
            segments.append(segment)
    if segments:
        return segments
    return [texte.strip()] if texte.strip() else []


def construire_unites_analyse(
    documents: list[str],
    noms_sources: list[str],
    mode_unite: str,
    taille_segment_mots: int,
    segmenter_sur_ponctuation_forte: bool,
) -> list[UniteAnalyse]:
    unites: list[UniteAnalyse] = []
    longueur_min_segment = max(10, int(taille_segment_mots) * 4)
    sources = noms_sources if noms_sources else ["corpus"] * len(documents)

    for index_doc, document in enumerate(documents, start=1):
        source = sources[index_doc - 1] if index_doc - 1 < len(sources) else "corpus"
        if mode_unite == "document":
            unites.append(
                UniteAnalyse(
                    identifiant=f"DOC_{index_doc}",
                    texte=document,
                    source=source,
                    type_unite="document",
                )
            )
            continue

        segments = segmenter_document(
            document,
            longueur_min_segment=longueur_min_segment,
            taille_segment_mots=int(taille_segment_mots),
            segmenter_sur_ponctuation_forte=segmenter_sur_ponctuation_forte,
        )
        for index_segment, segment in enumerate(segments, start=1):
            unites.append(
                UniteAnalyse(
                    identifiant=f"DOC_{index_doc}_SEG_{index_segment}",
                    texte=segment,
                    source=source,
                    type_unite="segment",
                )
            )

    return unites


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


def dataframe_top_terms_iramuteq(lda: LdaModel, num_topics: int, num_words: int) -> pd.DataFrame:
    rows = []
    for topic_id, topic_words in lda.show_topics(
        formatted=False,
        num_topics=num_topics,
        num_words=num_words,
    ):
        for word, probability in topic_words:
            rows.append(
                {
                    "topic": f"Topic_{topic_id + 1}",
                    "term": word,
                    "prob": float(probability),
                }
            )
    return pd.DataFrame(rows)


def dataframe_topic_term_matrix(lda: LdaModel, dictionary: corpora.Dictionary) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    topic_term_matrix = lda.get_topics().astype(float)
    terms = []
    for word_id in range(topic_term_matrix.shape[1]):
        try:
            terms.append(dictionary[word_id])
        except KeyError:
            terms.append(str(word_id))
    rows = []
    for word_id, term in enumerate(terms):
        row = {"term": term}
        for topic_id in range(topic_term_matrix.shape[0]):
            row[f"Topic_{topic_id + 1}"] = float(topic_term_matrix[topic_id, word_id])
        rows.append(row)
    return pd.DataFrame(rows), topic_term_matrix, terms


def dataframe_distributions_unites(
    lda: LdaModel,
    corpus: list[list[tuple[int, int]]],
    unites: list[UniteAnalyse],
    textes_bigrams: list[list[str]],
    num_topics: int,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    doc_rows = []
    segment_rows = []
    payload_unites: list[dict[str, object]] = []

    for unite, bow, tokens in zip(unites, corpus, textes_bigrams):
        distribution = np.zeros(num_topics, dtype=float)
        for topic_id, probability in lda.get_document_topics(bow, minimum_probability=0.0):
            if 0 <= int(topic_id) < num_topics:
                distribution[int(topic_id)] = float(probability)

        topic_dominant = int(np.argmax(distribution) + 1) if distribution.size else None
        prob_topic_dominant = float(np.max(distribution)) if distribution.size else None
        topic_columns = {
            f"Topic_{topic_id + 1}": round(float(distribution[topic_id]), 6)
            for topic_id in range(num_topics)
        }

        doc_rows.append({"doc_id": unite.identifiant, **topic_columns})
        segment_rows.append(
            {
                "doc_id": unite.identifiant,
                "type_unite": unite.type_unite,
                "topic_dominant": topic_dominant,
                "prob_topic_dominant": prob_topic_dominant,
                "nb_termes_retenus": len(tokens),
                "segment_exploitable": True,
                "texte": unite.texte,
                **topic_columns,
            }
        )
        payload_unites.append(
            {
                "identifiant": unite.identifiant,
                "type_unite": unite.type_unite,
                "texte": unite.texte,
                "topic_dominant": topic_dominant,
                "prob_topic_dominant": prob_topic_dominant,
                "nb_termes_retenus": len(tokens),
                "segment_exploitable": True,
                "distribution_topics": [float(value) for value in distribution.tolist()],
            }
        )

    return pd.DataFrame(doc_rows), pd.DataFrame(segment_rows), payload_unites


def construire_payload_iramuteq(
    *,
    topics_df: pd.DataFrame,
    terms: list[str],
    topic_term_matrix: np.ndarray,
    unites_payload: list[dict[str, object]],
    mode_unite: str,
    documents_count: int,
    unites_count: int,
    num_topics: int,
    words_per_topic: int,
    no_below: int,
    no_above: float,
    passes: int,
    bigrammes_count: int,
    terms_count: int,
) -> dict[str, object]:
    topics = []
    for topic_id in range(1, num_topics + 1):
        topic_rows = topics_df[topics_df["topic"] == f"Topic_{topic_id}"]
        topics.append(
            {
                "topic": topic_id,
                "mots": [
                    {"mot": str(row["term"]), "poids": float(row["prob"])}
                    for _, row in topic_rows.iterrows()
                ],
            }
        )

    return {
        "succes": True,
        "meta": {
            "mode_unite": mode_unite,
            "nb_documents": documents_count,
            "nb_unites": unites_count,
            "nb_topics": num_topics,
            "nb_mots_par_topic": words_per_topic,
            "min_df": no_below,
            "max_df": no_above,
            "passes": passes,
            "vocabulaire_taille": terms_count,
            "nb_bigrammes_detectes": bigrammes_count,
            "moteur": "gensim",
        },
        "topics": topics,
        "terms": terms,
        "topic_term_matrix": topic_term_matrix.tolist(),
        "unites": unites_payload,
    }


def selectionner_termes_heatmap(
    topic_term_matrix: np.ndarray,
    terms: list[str],
    top_n_par_topic: int,
    max_total_termes: int,
) -> tuple[np.ndarray, list[str]]:
    indices_retenus: list[int] = []
    for topic_id in range(topic_term_matrix.shape[0]):
        poids = topic_term_matrix[topic_id, :]
        ordre = np.argsort(poids)[::-1]
        indices_retenus.extend([int(index) for index in ordre[:top_n_par_topic] if poids[index] > 0])

    if not indices_retenus:
        raise RuntimeError("Aucun terme significatif pour générer la heatmap LDA.")

    indices_uniques = sorted(set(indices_retenus))
    if len(indices_uniques) > max_total_termes:
        scores = [(index, float(np.max(topic_term_matrix[:, index]))) for index in indices_uniques]
        scores.sort(key=lambda item: item[1], reverse=True)
        indices_uniques = sorted(index for index, _ in scores[:max_total_termes])

    def cle_tri(index_terme: int):
        colonne = topic_term_matrix[:, index_terme]
        topic_dominant = int(np.argmax(colonne))
        score_dominant = float(np.max(colonne))
        return (topic_dominant, -score_dominant, terms[index_terme].lower())

    indices_tries = sorted(indices_uniques, key=cle_tri)
    return topic_term_matrix[:, indices_tries].T, [terms[index] for index in indices_tries]


def creer_heatmap_lda(
    topic_term_matrix: np.ndarray,
    terms: list[str],
    top_n_par_topic: int,
    max_total_termes: int,
) -> bytes:
    matrice_termes_topics, termes_selectionnes = selectionner_termes_heatmap(
        topic_term_matrix,
        terms,
        top_n_par_topic=max(1, int(top_n_par_topic)),
        max_total_termes=max(10, int(max_total_termes)),
    )
    n_termes, n_topics = matrice_termes_topics.shape
    largeur = min(12.5, max(6.4, 2.8 + (n_topics * 0.82)))
    hauteur = min(18.0, max(4.6, 1.6 + (n_termes * 0.22)))

    figure, axe = plt.subplots(figsize=(largeur, hauteur), dpi=150)
    image = axe.imshow(
        matrice_termes_topics,
        aspect="auto",
        interpolation="nearest",
        cmap="YlOrRd",
        origin="upper",
    )
    axe.set_title("Heatmap mots x topics", fontsize=12, fontweight="bold", pad=10)
    axe.set_xlabel("Topics", fontsize=10)
    axe.set_ylabel("Mots", fontsize=10)
    axe.set_xticks(np.arange(n_topics))
    axe.set_xticklabels([f"Topic {index}" for index in range(1, n_topics + 1)], rotation=0, fontsize=9)
    axe.set_yticks(np.arange(n_termes))
    axe.set_yticklabels(termes_selectionnes, fontsize=8 if n_termes <= 36 else 7)
    axe.set_xticks(np.arange(-0.5, n_topics, 1), minor=True)
    axe.set_yticks(np.arange(-0.5, n_termes, 1), minor=True)
    axe.grid(which="minor", color="#ffffff", linestyle="-", linewidth=0.6, alpha=0.45)
    axe.tick_params(which="minor", bottom=False, left=False)
    colorbar = figure.colorbar(image, ax=axe, fraction=0.03, pad=0.02)
    colorbar.set_label("Probabilité P(mot | topic)", rotation=90, labelpad=8, fontsize=9)
    colorbar.ax.tick_params(labelsize=8)

    if n_termes * n_topics <= 220:
        seuil = float(np.max(matrice_termes_topics)) * 0.52 if matrice_termes_topics.size else 0.0
        for index_terme in range(n_termes):
            for index_topic in range(n_topics):
                valeur = float(matrice_termes_topics[index_terme, index_topic])
                if not math.isfinite(valeur):
                    continue
                couleur = "#2a120d" if valeur < seuil else "#fffaf5"
                axe.text(
                    index_topic,
                    index_terme,
                    f"{valeur:.3f}",
                    ha="center",
                    va="center",
                    fontsize=6.4,
                    color=couleur,
                )

    buffer = io.BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    return buffer.getvalue()


def creer_reseau_topics_mots(top_terms_df: pd.DataFrame, max_terms_per_topic: int) -> bytes:
    if top_terms_df.empty:
        raise RuntimeError("Aucun terme disponible pour générer le réseau LDA.")

    selected_rows = []
    for topic, group in top_terms_df.groupby("topic", sort=False):
        selected_rows.append(group.sort_values("prob", ascending=False).head(max(1, int(max_terms_per_topic))))
    data = pd.concat(selected_rows, ignore_index=True)
    topics = sorted(data["topic"].unique(), key=lambda value: int(str(value).split("_")[-1]))

    strongest_topic_by_term = (
        data.sort_values("prob", ascending=False)
        .drop_duplicates("term")
        .set_index("term")["topic"]
        .to_dict()
    )
    terms = sorted(
        data["term"].unique(),
        key=lambda term: (
            topics.index(strongest_topic_by_term.get(term, topics[0])),
            -float(data.loc[data["term"] == term, "prob"].max()),
            str(term),
        ),
    )

    topic_y = {topic: value for topic, value in zip(topics, np.linspace(0.92, 0.08, len(topics)))}
    term_y = {term: value for term, value in zip(terms, np.linspace(0.96, 0.04, len(terms)))}
    colors = plt.cm.get_cmap("tab20", max(1, len(topics)))
    topic_color = {topic: colors(index) for index, topic in enumerate(topics)}
    max_prob = max(float(data["prob"].max()), 1e-9)
    hauteur = min(18, max(5.5, len(terms) * 0.24 + 1.8))

    figure, axe = plt.subplots(figsize=(12, hauteur), dpi=150)
    axe.set_title("Réseau topics x mots", fontsize=13, fontweight="bold", pad=14)
    axe.set_xlim(0, 1)
    axe.set_ylim(0, 1)
    axe.axis("off")

    for _, row in data.iterrows():
        topic = row["topic"]
        term = row["term"]
        probability = float(row["prob"])
        strength = max(0.08, min(1.0, probability / max_prob))
        axe.plot(
            [0.16, 0.84],
            [topic_y[topic], term_y[term]],
            color=topic_color[topic],
            linewidth=0.5 + (2.6 * strength),
            alpha=0.16 + (0.52 * strength),
            solid_capstyle="round",
        )

    for topic in topics:
        y = topic_y[topic]
        axe.scatter([0.14], [y], s=520, color=topic_color[topic], edgecolor="#4b2a14", linewidth=1.1, zorder=3)
        axe.text(0.07, y, topic.replace("_", " "), ha="right", va="center", fontsize=10, fontweight="bold")

    for term in terms:
        y = term_y[term]
        color = topic_color[strongest_topic_by_term.get(term, topics[0])]
        axe.scatter([0.86], [y], s=72, color="#fffaf0", edgecolor=color, linewidth=1.2, zorder=3)
        axe.text(0.89, y, str(term), ha="left", va="center", fontsize=8.2)

    buffer = io.BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    return buffer.getvalue()


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def json_result_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


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
    mode_unite: str,
    taille_segment_mots: int,
    segmenter_sur_ponctuation_forte: bool,
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
    progress = st.progress(0, text="Préparation des unités d'analyse")
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)

    unites = construire_unites_analyse(
        documents,
        noms_sources,
        mode_unite=mode_unite,
        taille_segment_mots=int(taille_segment_mots),
        segmenter_sur_ponctuation_forte=segmenter_sur_ponctuation_forte,
    )
    if not unites:
        raise RuntimeError(
            "Aucune unité d'analyse exploitable. En mode segment, diminue la taille minimale des segments."
        )

    progress.progress(10, text="Prétraitement spaCy")
    textes = preprocess_documents(
        [unite.texte for unite in unites],
        model_name=model_name,
        pos_selection=pos_selection,
        retirer_stopwords=retirer_stopwords,
        lemmatiser=lemmatiser,
        min_token_length=min_token_length,
    )
    unites_et_textes = [(unite, texte) for unite, texte in zip(unites, textes) if texte]
    if not unites_et_textes:
        raise RuntimeError("Aucune unité exploitable après prétraitement.")
    unites_valides = [unite for unite, _ in unites_et_textes]
    textes_valides = [texte for _, texte in unites_et_textes]

    progress.progress(25, text="Détection des bigrammes")
    textes_bigrams, bigrammes = appliquer_bigrammes(textes_valides, bigram_min_count, bigram_threshold)

    progress.progress(40, text="Création du dictionnaire")
    dictionary_raw = corpora.Dictionary(textes_bigrams)
    histogramme_png = creer_histogramme_frequences(dictionary_raw)
    stats_freq = dataframe_stats_frequences(dictionary_raw)

    dictionary = corpora.Dictionary(textes_bigrams)
    dictionary.filter_extremes(no_below=no_below, no_above=no_above)
    corpus: list[list[tuple[int, int]]] = []
    textes_modelises: list[list[str]] = []
    unites_modelisees: list[UniteAnalyse] = []
    for unite, texte in zip(unites_valides, textes_bigrams):
        bow = dictionary.doc2bow(texte)
        if not bow:
            continue
        unites_modelisees.append(unite)
        textes_modelises.append(texte)
        corpus.append(bow)

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
    top_terms_df = dataframe_top_terms_iramuteq(lda, num_topics, words_per_topic)
    topic_term_matrix_df, topic_term_matrix, terms = dataframe_topic_term_matrix(lda, dictionary)
    doc_topics_df, segments_topics_df, unites_payload = dataframe_distributions_unites(
        lda,
        corpus,
        unites_modelisees,
        textes_modelises,
        num_topics,
    )
    iramuteq_payload = construire_payload_iramuteq(
        topics_df=top_terms_df,
        terms=terms,
        topic_term_matrix=topic_term_matrix,
        unites_payload=unites_payload,
        mode_unite=mode_unite,
        documents_count=len(documents),
        unites_count=len(unites_modelisees),
        num_topics=num_topics,
        words_per_topic=words_per_topic,
        no_below=no_below,
        no_above=no_above,
        passes=passes,
        bigrammes_count=len(bigrammes),
        terms_count=len(dictionary),
    )
    bigrammes_df = pd.DataFrame({"Bigramme": bigrammes})
    documents_df = pd.DataFrame(
        {
            "Document": range(1, len(textes_modelises) + 1),
            "ID unité": [unite.identifiant for unite in unites_modelisees],
            "Type unité": [unite.type_unite for unite in unites_modelisees],
            "Source": [unite.source for unite in unites_modelisees],
            "Tokens retenus": [len(texte) for texte in textes_modelises],
            "Texte original": [unite.texte for unite in unites_modelisees],
            "Texte prétraité": [" ".join(texte) for texte in textes_modelises],
        }
    )

    progress.progress(86, text="Création des visualisations")
    lda_html = ""
    try:
        lda_display = gensimvis.prepare(lda, corpus, dictionary, sort_topics=False)
        lda_html = pyLDAvis.prepared_data_to_html(lda_display)
    except Exception as exc:
        lda_html = f"<p>Visualisation pyLDAvis indisponible : {exc}</p>"
    wordclouds = creer_wordclouds(lda, num_topics, min(max(words_per_topic, 20), 60))
    heatmap_png = b""
    heatmap_error = ""
    try:
        heatmap_png = creer_heatmap_lda(
            topic_term_matrix,
            terms,
            top_n_par_topic=max(8, int(words_per_topic)),
            max_total_termes=max(30, min(160, int(words_per_topic) * int(num_topics))),
        )
    except Exception as exc:
        heatmap_error = str(exc)

    reseau_png = b""
    reseau_error = ""
    try:
        reseau_png = creer_reseau_topics_mots(top_terms_df, max_terms_per_topic=min(int(words_per_topic), 12))
    except Exception as exc:
        reseau_error = str(exc)

    exports: dict[str, bytes] = {
        "top_terms.csv": csv_bytes(top_terms_df),
        "topic_term_matrix.csv": csv_bytes(topic_term_matrix_df),
        "doc_topics.csv": csv_bytes(doc_topics_df),
        "segments_topics.csv": csv_bytes(segments_topics_df),
        "lda_python_output.json": json_result_bytes(iramuteq_payload),
        "lda_topics.csv": csv_bytes(topics_df),
        "bigrammes_trouves.csv": csv_bytes(bigrammes_df),
        "documents_pretraites.csv": csv_bytes(documents_df),
        "statistiques_frequences.csv": csv_bytes(stats_freq),
        "distribution_frequences.png": histogramme_png,
        "pyldavis.html": lda_html.encode("utf-8"),
        "lda_visualization.html": lda_html.encode("utf-8"),
    }
    if heatmap_png:
        exports["heatmap_lda.png"] = heatmap_png
    if reseau_png:
        exports["reseau_topics_mots.png"] = reseau_png
    exports.update(wordclouds)
    archive = construire_archive(exports)
    progress.progress(100, text="Analyse LDA terminée")

    return {
        "texts": textes_modelises,
        "dictionary": dictionary,
        "topics_df": topics_df,
        "top_terms_df": top_terms_df,
        "topic_term_matrix_df": topic_term_matrix_df,
        "doc_topics_df": doc_topics_df,
        "segments_topics_df": segments_topics_df,
        "iramuteq_payload": iramuteq_payload,
        "bigrammes_df": bigrammes_df,
        "documents_df": documents_df,
        "stats_freq": stats_freq,
        "histogramme_png": histogramme_png,
        "lda_html": lda_html,
        "heatmap_png": heatmap_png,
        "heatmap_error": heatmap_error,
        "reseau_png": reseau_png,
        "reseau_error": reseau_error,
        "wordclouds": wordclouds,
        "archive": archive,
        "documents_count": len(documents),
        "units_count": len(unites_modelisees),
        "terms_count": len(dictionary),
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }


st.set_page_config(page_title="LDA", layout="wide", initial_sidebar_state="expanded")
enforce_streamlit_access(APP_TICKET_DEFAULT_ID, APP_NAME)

st.title("Latent Dirichlet Allocation (LDA)")
st.caption("version 0.2 - modifiée 21-07-2026")
with st.expander("Aide", expanded=False):
    st.markdown(
        'Article de blog sur LDA : '
        '<a href="https://www.codeandcortex.fr/analyse-latent-dirichlet-allocation-analyse-textuelle/" '
        'target="_blank" rel="noopener noreferrer">'
        'https://www.codeandcortex.fr/analyse-latent-dirichlet-allocation-analyse-textuelle/'
        '</a>',
        unsafe_allow_html=True,
    )
st.markdown("<br>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Paramètres LDA")
    st.subheader("Unités d'analyse")
    mode_unite = st.radio(
        "Unité d'analyse",
        options=["segment", "document"],
        format_func=lambda value: "Segment de texte" if value == "segment" else "Document complet",
        index=0,
        help=(
            "Reprend le principe d'iramuteq-lite : l'analyse peut porter sur des segments de texte "
            "ou sur les documents délimités par les lignes ****."
        ),
    )
    taille_segment_mots = st.number_input(
        "Taille des segments LDA (en mots)",
        min_value=5,
        max_value=500,
        value=40,
        step=5,
        disabled=mode_unite != "segment",
        help=(
            "Taille indicative utilisée pour filtrer ou découper les segments. "
            "Comme dans iramuteq-lite, elle sert à éviter les segments trop courts pour une LDA stable."
        ),
    )
    segmenter_sur_ponctuation_forte = st.checkbox(
        "Segmenter à partir de la ponctuation forte (. ! ?)",
        value=True,
        disabled=mode_unite != "segment",
        help=(
            "Si l'option est active, les segments sont découpés sur la ponctuation forte et les retours ligne. "
            "Sinon, le texte est découpé par blocs de mots."
        ),
    )

    st.subheader("Prétraitement")
    spacy_model = st.text_input(
        "Modèle spaCy",
        value=DEFAULT_SPACY_MODEL,
        help=(
            "Nom du modèle linguistique spaCy utilisé pour découper et annoter le texte. "
            "Par défaut, le modèle français moyen fonctionne bien pour la plupart des corpus."
        ),
    )
    pos_selection = st.multiselect(
        "POS à conserver",
        options=ALL_POS,
        default=DEFAULT_POS,
        help=(
            "Sélectionne les catégories grammaticales à garder dans l'analyse. "
            "Conserver surtout les noms, adjectifs et noms propres aide souvent à obtenir des topics plus interprétables."
        ),
    )
    retirer_stopwords = st.checkbox(
        "Retirer les stopwords spaCy",
        value=True,
        help=(
            "Supprime les mots-outils fréquents comme les articles, pronoms ou prépositions. "
            "Coche cette option pour concentrer les topics sur les mots les plus informatifs."
        ),
    )
    lemmatiser = st.checkbox(
        "Lemmatisation",
        value=True,
        help=(
            "Ramène les formes fléchies à leur forme de base, par exemple 'mangeait' vers 'manger'. "
            "Cela regroupe les variantes d'un même mot dans le dictionnaire."
        ),
    )
    min_token_length = st.number_input(
        "Longueur minimale des mots",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
        help=(
            "Ignore les mots trop courts après prétraitement. "
            "Augmenter cette valeur élimine davantage de petits mots, mais peut aussi retirer des sigles utiles."
        ),
    )

    st.subheader("Bigrammes")
    bigram_min_count = st.number_input(
        "min_count",
        min_value=1,
        max_value=50,
        value=5,
        step=1,
        help=(
            "Nombre minimal d'apparitions pour qu'une association de deux mots puisse devenir un bigramme. "
            "Plus la valeur est basse, plus l'application détecte de bigrammes rares ; plus elle est haute, "
            "plus seuls les bigrammes fréquents sont conservés."
        ),
    )
    bigram_threshold = st.number_input(
        "threshold",
        min_value=1.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
        help=(
            "Seuil de solidité statistique des bigrammes dans Gensim. "
            "Une valeur basse crée davantage de bigrammes ; une valeur élevée garde uniquement les associations fortes."
        ),
    )

    st.subheader("Filtrage dictionnaire")
    no_below = st.number_input(
        "no_below",
        min_value=0,
        max_value=100,
        value=1,
        step=1,
        help=(
            "Fréquence documentaire minimale d'un terme. "
            "Par exemple, no_below=3 supprime les mots présents dans moins de 3 documents. "
            "Augmenter cette valeur nettoie le dictionnaire, mais peut supprimer des termes rares importants."
        ),
    )
    no_above = st.slider(
        "no_above",
        min_value=0.05,
        max_value=1.0,
        value=0.6,
        step=0.05,
        help=(
            "Proportion maximale de documents dans lesquels un terme peut apparaître avant d'être supprimé. "
            "Par exemple, 0.60 retire les mots présents dans plus de 60 % des documents, souvent trop généraux pour distinguer les thèmes."
        ),
    )

    st.subheader("Modèle")
    num_topics = st.number_input(
        "Nombre de topics",
        min_value=2,
        max_value=50,
        value=12,
        step=1,
        help=(
            "Nombre de thèmes que le modèle LDA doit extraire du corpus. "
            "Un nombre trop faible regroupe des thèmes différents ; un nombre trop élevé fragmente les résultats."
        ),
    )
    passes = st.number_input(
        "Passes",
        min_value=1,
        max_value=100,
        value=15,
        step=1,
        help=(
            "Nombre de passages d'apprentissage sur le corpus. "
            "Plus la valeur est élevée, plus le modèle peut se stabiliser, mais le calcul devient plus long."
        ),
    )
    random_state = st.number_input(
        "Random state",
        min_value=0,
        max_value=999999,
        value=42,
        step=1,
        help=(
            "Graine aléatoire utilisée pour rendre les résultats reproductibles. "
            "Garde la même valeur pour comparer plusieurs essais avec les mêmes paramètres."
        ),
    )
    words_per_topic = st.number_input(
        "Mots affichés par topic",
        min_value=5,
        max_value=60,
        value=20,
        step=5,
        help=(
            "Nombre de mots affichés pour décrire chaque topic dans les tableaux et nuages de mots. "
            "Cela ne change pas le modèle, seulement la quantité de mots montrés dans les résultats."
        ),
    )

uploaded_files = st.file_uploader(
    "Importer un ou plusieurs corpus texte",
    type=["txt"],
    accept_multiple_files=True,
    help=(
        "Importe un ou plusieurs fichiers texte au format .txt. "
        "Les lignes commençant par **** sont reconnues comme séparateurs de documents IRaMuTeQ."
    ),
)

if "lda_result" not in st.session_state:
    st.session_state.lda_result = None

if st.button(
    "Lancer le test LDA",
    type="primary",
    help="Démarre le prétraitement du corpus, la détection des bigrammes, puis l'entraînement du modèle LDA avec les paramètres choisis.",
):
    documents, noms_sources = lire_fichiers_uploades(uploaded_files)
    if not documents:
        st.error("Importe au moins un fichier texte avant de lancer l'analyse.")
    else:
        try:
            st.session_state.lda_result = run_lda_analysis(
                documents,
                noms_sources,
                mode_unite=mode_unite,
                taille_segment_mots=int(taille_segment_mots),
                segmenter_sur_ponctuation_forte=bool(segmenter_sur_ponctuation_forte),
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
        f"{result['units_count']} unité(s) modélisée(s), "
        f"{result['terms_count']} terme(s) conservé(s)."
    )
    st.download_button(
        "Télécharger l'archive complète",
        data=result["archive"],
        file_name=f"lda_resultats_{result['timestamp']}.zip",
        mime="application/zip",
    )

    (
        onglet_probabilites,
        onglet_segments,
        onglet_visualisation,
        onglet_heatmap,
        onglet_reseau,
        onglet_wordclouds,
        onglet_diagnostics,
    ) = st.tabs(
        [
            "Tableau des probabilités",
            "Documents / segments",
            "pyLDAvis",
            "Heatmap mots x topics",
            "Réseau topics x mots",
            "Nuages de mots",
            "Diagnostics",
        ]
    )

    with onglet_probabilites:
        st.markdown("### Probabilités mot x topic")
        st.caption(
            "Même logique que dans iramuteq-lite : `P(mot | topic)` décrit les mots les plus caractéristiques de chaque topic."
        )
        st.dataframe(result["topic_term_matrix_df"], use_container_width=True, height=420)
        col_matrix, col_terms = st.columns(2)
        with col_matrix:
            st.download_button(
                "Télécharger topic_term_matrix.csv",
                data=csv_bytes(result["topic_term_matrix_df"]),
                file_name="topic_term_matrix.csv",
                mime="text/csv",
            )
        with col_terms:
            st.download_button(
                "Télécharger top_terms.csv",
                data=csv_bytes(result["top_terms_df"]),
                file_name="top_terms.csv",
                mime="text/csv",
            )

        st.markdown("### Mots les plus probables par topic")
        st.dataframe(result["top_terms_df"], use_container_width=True, height=360)

    with onglet_segments:
        st.markdown("### Distribution des topics par unité")
        st.caption("`P(topic | segment/document)` indique le rattachement de chaque unité au topic dominant.")
        st.dataframe(result["segments_topics_df"], use_container_width=True, height=460)
        col_docs, col_segments, col_json = st.columns(3)
        with col_docs:
            st.download_button(
                "Télécharger doc_topics.csv",
                data=csv_bytes(result["doc_topics_df"]),
                file_name="doc_topics.csv",
                mime="text/csv",
            )
        with col_segments:
            st.download_button(
                "Télécharger segments_topics.csv",
                data=csv_bytes(result["segments_topics_df"]),
                file_name="segments_topics.csv",
                mime="text/csv",
            )
        with col_json:
            st.download_button(
                "Télécharger lda_python_output.json",
                data=json_result_bytes(result["iramuteq_payload"]),
                file_name="lda_python_output.json",
                mime="application/json",
            )

    with onglet_visualisation:
        components.html(result["lda_html"], height=820, scrolling=True)

    with onglet_heatmap:
        if result["heatmap_png"]:
            st.image(result["heatmap_png"], caption="Heatmap LDA mots x topics", use_container_width=True)
            st.download_button(
                "Télécharger heatmap_lda.png",
                data=result["heatmap_png"],
                file_name="heatmap_lda.png",
                mime="image/png",
            )
        else:
            st.warning(f"Heatmap LDA indisponible : {result['heatmap_error']}")

    with onglet_reseau:
        if result["reseau_png"]:
            st.image(result["reseau_png"], caption="Réseau topics x mots", use_container_width=True)
            st.download_button(
                "Télécharger reseau_topics_mots.png",
                data=result["reseau_png"],
                file_name="reseau_topics_mots.png",
                mime="image/png",
            )
        else:
            st.warning(f"Réseau topics x mots indisponible : {result['reseau_error']}")

    with onglet_wordclouds:
        for filename, image_bytes in result["wordclouds"].items():
            st.markdown(f"#### {filename.replace('_wordcloud.png', '').replace('_', ' ').title()}")
            st.image(image_bytes, use_container_width=True)

    with onglet_diagnostics:
        st.markdown("### Topics synthétiques")
        st.dataframe(result["topics_df"], use_container_width=True)
        st.download_button(
            "Télécharger lda_topics.csv",
            data=csv_bytes(result["topics_df"]),
            file_name="lda_topics.csv",
            mime="text/csv",
        )
        st.markdown("### Bigrammes trouvés")
        st.dataframe(result["bigrammes_df"], use_container_width=True)
        st.markdown("### Statistiques de fréquence avant filtrage")
        st.dataframe(result["stats_freq"], use_container_width=True)
        st.image(result["histogramme_png"], caption="Distribution des fréquences de mots", use_container_width=True)
        st.markdown("### Documents prétraités")
        st.dataframe(result["documents_df"], use_container_width=True)
