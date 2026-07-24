from __future__ import annotations

import io
import os
import re
import shutil
import uuid
import zipfile
from io import StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import nltk
import numpy as np
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st
from nltk.corpus import stopwords
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from umap import UMAP
from wordcloud import WordCloud

from ticket_gate import enforce_streamlit_access


APP_NAME = "KMeans"
APP_TICKET_DEFAULT_ID = "kmeans"
SENTENCE_MODEL_NAME = os.getenv("KMEANS_SENTENCE_MODEL", "all-MiniLM-L6-v2").strip() or "all-MiniLM-L6-v2"
DEFAULT_SAVE_DIRECTORY = os.getenv("KMEANS_OUTPUT_DIR", "/tmp/kmeans")
STOPWORD_MODE_FRENCH = "Français NLTK"
STOPWORD_MODE_NONE = "Aucun stopword"
STOPWORD_MODE_CUSTOM = "Stopwords personnalisés"
STOPWORD_MODE_FRENCH_CUSTOM = "Français NLTK + personnalisés"
STOPWORD_MODES = (
    STOPWORD_MODE_FRENCH,
    STOPWORD_MODE_NONE,
    STOPWORD_MODE_CUSTOM,
    STOPWORD_MODE_FRENCH_CUSTOM,
)
PAGE_STYLE = """
<style>
  .main .block-container,
  div[data-testid="stMainBlockContainer"] {
    padding-top: 0rem !important;
  }
</style>
"""


@st.cache_resource(show_spinner=False)
def load_sentence_model() -> SentenceTransformer:
    return SentenceTransformer(SENTENCE_MODEL_NAME)


@st.cache_resource(show_spinner=False)
def load_french_stopwords() -> list[str]:
    try:
        return stopwords.words("french")
    except LookupError:
        nltk.download("stopwords", quiet=True)
        return stopwords.words("french")


def parse_custom_stopwords(raw_stopwords: str) -> list[str]:
    parsed_stopwords = set()
    for raw_word in re.split(r"[,;\n]+", raw_stopwords):
        cleaned_word = preprocess_text(raw_word).strip()
        if cleaned_word:
            parsed_stopwords.add(cleaned_word)
    return sorted(parsed_stopwords)


def build_stopwords(stopword_mode: str, custom_stopwords: str) -> list[str]:
    selected_stopwords: set[str] = set()
    if stopword_mode in {STOPWORD_MODE_FRENCH, STOPWORD_MODE_FRENCH_CUSTOM}:
        selected_stopwords.update(load_french_stopwords())
    if stopword_mode in {STOPWORD_MODE_CUSTOM, STOPWORD_MODE_FRENCH_CUSTOM}:
        selected_stopwords.update(parse_custom_stopwords(custom_stopwords))
    return sorted(selected_stopwords)


def remove_stopwords_from_text(text: str, selected_stopwords: list[str]) -> str:
    if not selected_stopwords:
        return text
    stopword_set = set(selected_stopwords)
    tokens = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    return " ".join(token for token in tokens if token not in stopword_set)


@st.cache_data(show_spinner=False)
def encode_documents(contents: tuple[str, ...]) -> np.ndarray:
    sentence_model = load_sentence_model()
    return sentence_model.encode(list(contents), show_progress_bar=False)


def parse_article(article_text: str) -> dict[str, str]:
    lines = article_text.strip().split("\n")
    content = "\n".join(lines[1:]) if len(lines) > 1 else ""
    return {"content": content}


def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


def create_concordance(df: pd.DataFrame, clusters: np.ndarray) -> pd.DataFrame:
    concordance_df = pd.DataFrame(
        {
            "Document": df["content"],
            "Cluster": [f"Cluster {cluster + 1}" for cluster in clusters],
        }
    )
    grouped_concordance = concordance_df.groupby("Cluster")["Document"].apply(lambda x: " ".join(x)).reset_index()
    return grouped_concordance


def ensure_directory(directory: str | Path) -> Path:
    path = Path(directory).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_output_directory() -> Path:
    if "output_directory" not in st.session_state:
        st.session_state.output_directory = str(ensure_directory(Path(DEFAULT_SAVE_DIRECTORY) / uuid.uuid4().hex))
    return ensure_directory(st.session_state.output_directory)


def clear_output_directory(directory: str | Path) -> None:
    path = ensure_directory(directory)
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def save_csv(dataframe: pd.DataFrame, filename: str, directory: str | Path) -> Path:
    path = ensure_directory(directory) / f"{filename}.csv"
    dataframe.to_csv(path, index=False, encoding="utf-8")
    st.success(f"{filename}.csv ajouté aux résultats téléchargeables.")
    return path


def save_matplotlib_figure(fig, filename: str, directory: str | Path) -> Path:
    path = ensure_directory(directory) / filename
    fig.savefig(path, bbox_inches="tight")
    st.success(f"{filename} ajouté aux résultats téléchargeables.")
    return path


def save_plotly_figure(fig, filename: str, directory: str | Path) -> Path | None:
    html_path = (ensure_directory(directory) / filename).with_suffix(".html")
    fig.write_html(html_path)
    st.success(f"{html_path.name} ajouté aux résultats téléchargeables.")
    return html_path


def zip_directory(directory: str | Path) -> bytes:
    path = ensure_directory(directory)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(path.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(path))
    buffer.seek(0)
    return buffer.getvalue()


def reduce_to_2d(values: np.ndarray) -> np.ndarray:
    if len(values) == 1:
        return np.array([[0.0, 0.0]])
    if len(values) == 2:
        return np.array([[0.0, 0.0], [1.0, 0.0]])
    n_neighbors = min(15, max(2, len(values) - 1))
    umap_model = UMAP(n_components=2, random_state=42, n_neighbors=n_neighbors)
    return umap_model.fit_transform(values)


def display_similarity_matrix(embeddings: np.ndarray, cluster_labels: np.ndarray, directory: str | Path) -> None:
    cluster_centers = [embeddings[cluster_labels == i].mean(axis=0) for i in range(max(cluster_labels) + 1)]
    similarity_matrix = cosine_similarity(cluster_centers)
    cluster_names = [f"Cluster {i + 1}" for i in range(len(cluster_centers))]
    similarity_df = pd.DataFrame(similarity_matrix, columns=cluster_names, index=cluster_names)
    st.write("Matrice de Similarité Cosinus entre les Clusters")
    st.dataframe(similarity_df, use_container_width=True)
    save_csv(similarity_df, "kmeans_cluster_similarity_matrix", directory)

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        similarity_df,
        cmap="coolwarm",
        ax=ax,
        annot=True,
        fmt=".2f",
        xticklabels=cluster_names,
        yticklabels=cluster_names,
    )
    ax.set_title("Carte Thermique de Similarité entre les Clusters")
    save_matplotlib_figure(fig, "similarity_heatmap.png", directory)
    st.pyplot(fig)
    plt.close(fig)


def display_wordclouds(
    df: pd.DataFrame,
    cluster_labels: np.ndarray,
    directory: str | Path,
    selected_stopwords: list[str],
    max_words: int,
) -> None:
    wordcloud_stopwords = set(selected_stopwords)
    for cluster in sorted(set(cluster_labels)):
        st.subheader(f"Nuage de Mots pour le Topic {cluster + 1}")
        cluster_data = df["content"][cluster_labels == cluster]
        wordcloud_text = " ".join(cluster_data).strip()
        if not wordcloud_text:
            st.info(f"Aucun texte disponible pour le topic {cluster + 1}.")
            continue

        wordcloud = WordCloud(
            width=800,
            height=400,
            background_color="white",
            stopwords=wordcloud_stopwords,
            max_words=max_words,
        ).generate(wordcloud_text)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        ax.set_title(f"Topic {cluster + 1}")
        filename = f"wordcloud_topic_{cluster + 1}.png"
        save_matplotlib_figure(fig, filename, directory)
        st.pyplot(fig)
        plt.close(fig)


def display_cluster_visualization(embeddings: np.ndarray, labels: np.ndarray, directory: str | Path) -> None:
    reduced_embeddings = reduce_to_2d(embeddings)
    viz_df = pd.DataFrame(
        {
            "x": reduced_embeddings[:, 0],
            "y": reduced_embeddings[:, 1],
            "Cluster": labels,
        }
    )

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.scatterplot(data=viz_df, x="x", y="y", hue="Cluster", palette="viridis", s=50, alpha=0.7, ax=ax)
    ax.set_title("Visualisation des Clusters K-Means")
    ax.set_xlabel("Dimension 1")
    ax.set_ylabel("Dimension 2")
    ax.legend(title="Clusters", bbox_to_anchor=(1.05, 1), loc="upper left")
    save_matplotlib_figure(fig, "kmeans_cluster_2D.png", directory)
    st.pyplot(fig)
    plt.close(fig)


def display_centroid_visualization(embeddings: np.ndarray, cluster_labels: np.ndarray, directory: str | Path) -> None:
    cluster_centers = np.array([embeddings[cluster_labels == i].mean(axis=0) for i in range(max(cluster_labels) + 1)])
    reduced_centroids = reduce_to_2d(cluster_centers)
    df_centroids = pd.DataFrame(
        {
            "x": reduced_centroids[:, 0],
            "y": reduced_centroids[:, 1],
            "Cluster": range(1, len(cluster_centers) + 1),
            "Size": [10] * len(cluster_centers),
        }
    )

    fig = px.scatter(
        df_centroids,
        x="x",
        y="y",
        size="Size",
        color="Cluster",
        title="Visualisation des Centroides des Clusters",
        labels={"x": "Dimension 1", "y": "Dimension 2", "Cluster": "Clusters"},
        hover_data={"Size": False},
    )
    fig.update_traces(marker={"opacity": 0.6})
    st.plotly_chart(fig, use_container_width=True)
    save_plotly_figure(fig, "kmeans_centroid_visualization.png", directory)


def display_grouped_bubble_chart(embeddings: np.ndarray, cluster_labels: np.ndarray, directory: str | Path) -> None:
    cluster_ids = sorted(set(cluster_labels))
    cluster_centers = np.array([embeddings[cluster_labels == cluster].mean(axis=0) for cluster in cluster_ids])
    reduced_centers = reduce_to_2d(cluster_centers)
    cluster_sizes = pd.Series(cluster_labels).value_counts().sort_index()
    total_documents = int(cluster_sizes.sum())
    df = pd.DataFrame(
        {
            "x": reduced_centers[:, 0],
            "y": reduced_centers[:, 1],
            "Cluster": [f"Cluster {cluster + 1}" for cluster in cluster_ids],
            "Nombre d'articles": [int(cluster_sizes[cluster]) for cluster in cluster_ids],
            "Part du corpus": [
                f"{(int(cluster_sizes[cluster]) / total_documents) * 100:.1f} %" for cluster in cluster_ids
            ],
        }
    )

    fig = px.scatter(
        df,
        x="x",
        y="y",
        size="Nombre d'articles",
        color="Cluster",
        hover_data=["Cluster", "Nombre d'articles", "Part du corpus"],
        opacity=0.6,
        size_max=50,
        title="Taille des Clusters sous Forme de Bulles",
        labels={"x": "Dimension 1", "y": "Dimension 2"},
    )
    fig.update_layout(showlegend=True)
    st.caption(
        "Ce graphique sert à contrôler l'équilibre des clusters : chaque bulle représente un cluster, "
        "et sa taille correspond au nombre d'articles regroupés dans ce cluster."
    )
    st.plotly_chart(fig, use_container_width=True)
    save_plotly_figure(fig, "kmeans_grouped_bubble_chart.png", directory)


def dataframe_from_text(file_text: str) -> pd.DataFrame:
    raw_articles = file_text.strip().split("****")
    articles_data = [parse_article(article) for article in raw_articles if article.strip()]
    df = pd.DataFrame(articles_data)
    if "content" not in df.columns:
        df["content"] = []
    df["content"] = df["content"].apply(preprocess_text)
    df = df[df["content"].str.strip().astype(bool)].reset_index(drop=True)
    return df


def render_stopword_settings() -> None:
    st.subheader("Stopwords")
    st.selectbox(
        "Système de stopwords",
        STOPWORD_MODES,
        key="stopword_mode",
        help=(
            "Choisit les mots à ignorer dans les nuages de mots. "
            "Ils peuvent aussi être appliqués au clustering avec l'option suivante."
        ),
    )
    if st.session_state.stopword_mode in {STOPWORD_MODE_CUSTOM, STOPWORD_MODE_FRENCH_CUSTOM}:
        st.text_area(
            "Stopwords personnalisés",
            key="custom_stopwords",
            help="Ajoutez des mots séparés par des virgules, des points-virgules ou des retours à la ligne.",
        )
    st.checkbox(
        "Appliquer les stopwords au clustering",
        key="apply_stopwords_to_clustering",
        help=(
            "Si activé, les stopwords sont retirés des textes avant la création des embeddings. "
            "Par défaut, le clustering conserve le comportement historique."
        ),
    )
    selected_stopwords = build_stopwords(st.session_state.stopword_mode, st.session_state.custom_stopwords)
    st.caption(f"{len(selected_stopwords)} stopwords actifs.")

    st.subheader("Nuages de mots")
    st.slider(
        "Nombre de mots par nuage",
        20,
        500,
        step=10,
        key="wordcloud_max_words",
        help="Définit le nombre maximal de mots affichés dans chaque nuage de mots.",
    )


def render_preparation() -> None:
    st.sidebar.markdown("### Préparation des Données")
    st.subheader("Uploader un Fichier")
    uploaded_file = st.file_uploader("Téléchargez un fichier texte contenant des articles de presse", type="txt")
    if uploaded_file is not None:
        st.session_state.file_name = uploaded_file.name
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8", errors="replace"))
        st.session_state.df = dataframe_from_text(stringio.read())
        st.write(st.session_state.df)
        st.sidebar.text(f"Fichier chargé : {st.session_state.file_name}")

    if st.session_state.df is not None:
        total_articles = len(st.session_state.df)
        st.markdown(f"**Nombre d'articles trouvés : {total_articles}**")
        st.session_state.save_directory = str(get_output_directory())

    render_stopword_settings()


def render_analysis() -> None:
    st.sidebar.markdown("### Analyse des Données")

    if st.session_state.df is None:
        st.error("Veuillez d'abord préparer vos données dans la section précédente.")
        return

    if st.session_state.save_directory is None:
        st.session_state.save_directory = str(get_output_directory())

    if st.session_state.file_name:
        st.sidebar.text(f"Fichier chargé : {st.session_state.file_name}")

    df = st.session_state.df
    save_directory = st.session_state.save_directory
    if len(df) < 2:
        st.error("Le corpus doit contenir au moins 2 articles pour lancer KMeans.")
        return

    stopword_mode = st.session_state.get("stopword_mode", STOPWORD_MODE_FRENCH)
    custom_stopwords = st.session_state.get("custom_stopwords", "")
    selected_stopwords = build_stopwords(stopword_mode, custom_stopwords)
    apply_stopwords_to_clustering = st.session_state.get("apply_stopwords_to_clustering", False)
    wordcloud_max_words = st.session_state.get("wordcloud_max_words", 100)
    st.sidebar.caption(f"Stopwords : {stopword_mode} ({len(selected_stopwords)} actifs)")
    st.sidebar.caption(f"Nuages de mots : {wordcloud_max_words} mots maximum")
    if apply_stopwords_to_clustering:
        st.sidebar.caption("Stopwords appliqués au clustering.")

    embedding_contents = df["content"].tolist()
    if apply_stopwords_to_clustering and selected_stopwords:
        cleaned_contents = [remove_stopwords_from_text(content, selected_stopwords) for content in embedding_contents]
        embedding_contents = [
            cleaned_content if cleaned_content.strip() else original_content
            for cleaned_content, original_content in zip(cleaned_contents, embedding_contents)
        ]

    with st.spinner("Création des embeddings avec SentenceTransformer..."):
        embeddings = encode_documents(tuple(embedding_contents))

    st.sidebar.subheader("Paramètres du Vectorizer")
    min_df = st.sidebar.slider(
        "Min DF (fraction minimale de documents)",
        0.0,
        1.0,
        0.01,
        0.01,
        help="Ignore les termes présents dans une fraction de documents inférieure à cette valeur.",
    )
    max_df = st.sidebar.slider(
        "Max DF (fraction maximale de documents)",
        min_df,
        1.0,
        max(0.95, min_df),
        0.01,
        help="Ignore les termes présents dans une fraction de documents supérieure à cette valeur.",
    )
    vectorizer_model = CountVectorizer(
        stop_words=selected_stopwords or None,
        min_df=min_df,
        max_df=max_df,
        ngram_range=(1, 3),
    )
    _ = vectorizer_model

    st.subheader("Détermination du Nombre Optimal de Clusters")

    n_clusters = st.sidebar.slider(
        "Choisissez le nombre de clusters",
        2,
        20,
        5,
        1,
        help="Nombre de groupes que KMeans doit former dans le corpus.",
    )

    if st.button("Lancer l'Analyse KMeans"):
        if n_clusters > len(df):
            st.error(
                "Le nombre de clusters choisi est supérieur au nombre d'articles disponibles. "
                "Réduisez le nombre de clusters ou ajoutez des articles."
            )
            return

        clear_output_directory(save_directory)

        with st.spinner("Calcul de la méthode du coude..."):
            inertia = []
            valid_k_values = range(2, min(20, len(df)) + 1)
            for k in valid_k_values:
                kmeans = KMeans(n_clusters=k, random_state=42)
                kmeans.fit(embeddings)
                inertia.append(kmeans.inertia_)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(list(valid_k_values), inertia, "bx-")
        ax.set_xlabel("Nombre de Clusters (k)")
        ax.set_ylabel("Inertie")
        ax.set_title("Méthode du Coude Pour Déterminer le Nombre Optimal de Clusters")
        st.pyplot(fig)
        save_matplotlib_figure(fig, "elbow_method.png", save_directory)
        plt.close(fig)

        cluster_model = KMeans(n_clusters=n_clusters, random_state=42)
        kmeans_labels = cluster_model.fit_predict(embeddings)
        unique_clusters = len(set(kmeans_labels))
        st.write(f"Clusters KMeans trouvés : {unique_clusters} (regroupés)")

        if unique_clusters > 0:
            st.subheader("Visualisation des Centroides des Clusters K-Means")
            display_centroid_visualization(embeddings, kmeans_labels, save_directory)

            st.subheader("Taille des Clusters sous Forme de Bulles")
            display_grouped_bubble_chart(embeddings, kmeans_labels, save_directory)

            st.subheader("Visualisation des Clusters en 2D")
            display_cluster_visualization(embeddings, kmeans_labels, save_directory)

            st.subheader("Carte Thermique de Similarité des Clusters")
            display_similarity_matrix(embeddings, kmeans_labels, save_directory)

            concordance_kmeans = create_concordance(df, kmeans_labels)
            st.subheader("Concordancier KMeans")
            st.dataframe(concordance_kmeans, use_container_width=True)
            save_csv(concordance_kmeans, "concordance_kmeans", save_directory)

            display_wordclouds(df, kmeans_labels, save_directory, selected_stopwords, wordcloud_max_words)

            st.download_button(
                "Télécharger les résultats",
                data=zip_directory(save_directory),
                file_name="kmeans_resultats.zip",
                mime="application/zip",
            )


def render_faq() -> None:
    st.sidebar.markdown("### FAQ")
    st.subheader("FAQ : Analyse Textuelle avec K-Means++")
    st.markdown(
        """
### 1. Préparation des Données

Avant d'appliquer l'algorithme K-Means++, il est crucial de préparer correctement vos données.
Le script a été conçu pour fonctionner avec des articles provenant de la plateforme **Europresse**,
et est compatible avec le logiciel **Iramuteq**.

Pour garantir un traitement adéquat, chaque article doit être précédé d'une ligne de démarcation
commençant par `****`. Cette structure est essentielle pour que le script puisse identifier et traiter
chaque article distinctement.

- **Format d'entrée :**
- **Fichiers Texte :** Les fichiers doivent être en format texte, avec des articles séparés par `****`.

### 2. Algorithme K-Means++

**K-Means++** est une amélioration de l'algorithme de clustering K-Means standard. Il est utilisé pour
partitionner les données en un nombre fixe de groupes, appelés clusters. Voici une explication détaillée
de son fonctionnement et de sa mise en œuvre dans votre script.

#### Comment Fonctionne K-Means++ :

- **Initialisation Améliorée :**
- Contrairement à l'initialisation aléatoire de K-Means, K-Means++ choisit les centroïdes initiaux de manière stratégique.
- **Assignation des Points :**
- Chaque point de données est assigné au cluster avec le centroïde le plus proche, généralement calculé avec la distance euclidienne.
- **Mise à jour des Centroïdes :**
- Pour chaque cluster, le centroïde est recalculé comme la moyenne de tous les points assignés à ce cluster.
- **Convergence :**
- L'algorithme répète les étapes d'assignation et de mise à jour jusqu'à ce que les centroïdes se stabilisent ou qu'un nombre maximal d'itérations soit atteint.

#### Visualisation des Résultats :

- **Centroides et Clusters :**
- Le script génère plusieurs graphiques pour visualiser les clusters et leurs centroïdes.
- **Graphique des Centroides :** Visualisation des positions moyennes des clusters après convergence.
- **Carte Thermique de Similarité :** Visualisation des similarités entre les clusters, basée sur la distance entre les centroïdes.
- **Nuages de Mots :** Mots-clés caractéristiques de chaque cluster, permettant de comprendre le contenu textuel de chaque groupe.

### 3. Bibliothèques Python Utilisées :

- **Scikit-learn :** Pour l'implémentation de K-Means++, le calcul des clusters, et la gestion des données de texte.
- **SentenceTransformers :** Pour générer des embeddings à partir des textes, facilitant leur utilisation dans le clustering.
- **Matplotlib, Seaborn, Plotly :** Pour la création de graphiques et la visualisation des résultats.
- **WordCloud :** Pour la génération de nuages de mots permettant d'interpréter facilement les thèmes des clusters.

### 4. Paramètres de K-Means++ :

- **`n_clusters` (Nombre de Clusters) :**
- **Description :** Indique le nombre de clusters que l'algorithme doit former. L'utilisateur doit déterminer cette valeur à l'avance.
- **Impact :** Un nombre trop élevé peut fragmenter des clusters naturels, tandis qu'un nombre trop bas peut regrouper des données disparates.
- **Détermination :** La méthode du coude est souvent utilisée pour déterminer le nombre optimal de clusters.
- **`init` :**
- **Description :** Méthode d'initialisation des centroïdes.
- **Options :** Par défaut, `k-means++` est utilisé pour une meilleure convergence.
- **Impact :** L'initialisation K-Means++ permet d'éviter les mauvaises initialisations qui peuvent conduire à des solutions sous-optimales.
- **`max_iter` :**
- **Description :** Nombre maximal d'itérations pour une exécution de l'algorithme.
- **`tol` :**
- **Description :** Tolérance pour la convergence.
- **`random_state` :**
- **Description :** Assure la reproductibilité des résultats en fixant une graine pour la génération aléatoire.

#### Point Négatif : Détermination du Nombre de Clusters

- **Limitation :** Contrairement à des approches comme LDA ou BERTopic, K-Means++ nécessite que l'utilisateur spécifie *a priori* le nombre de clusters.
- **Comparaison avec LDA et BERTopic :**
- **LDA :** Identifie automatiquement les sujets dans un corpus textuel, utile pour des explorations sans connaissance préalable.
- **BERTopic :** Utilise des méthodes avancées pour découvrir des topics de manière plus flexible.

### 5. Exemples d'Utilisation en Sciences Humaines

- **Analyse Textuelle :**
- **Regroupement de Documents :** Utiliser K-Means++ pour organiser des articles de presse en catégories thématiques.
- **Segmentation des Utilisateurs :** Analyser les comportements ou préférences des utilisateurs en ligne.
- **Sciences Humaines :**
- **Études Littéraires :** Clustering de corpus littéraires pour identifier des styles d'écriture ou des thèmes communs.
- **Analyse Sociologique :** Identifier des groupes d'individus aux comportements ou opinions similaires.

#### Pourquoi Utiliser K-Means++ pour l'Analyse Textuelle ?

- **Simplicité et Efficacité :**
- Facile à comprendre et à implémenter.
- **Adaptabilité :**
- Fonctionne bien sur de grands ensembles de données textuelles.
- **Complémentarité :**
- Peut être utilisé en complément d'autres méthodes d'analyse textuelle.

### Conclusion

K-Means++ est un algorithme puissant pour la segmentation des données, particulièrement utile dans
l'analyse textuelle des sciences humaines. Bien que nécessitant une certaine intuition pour définir le
nombre de clusters, ses résultats peuvent révéler des structures cachées dans les données et fournir une
base solide pour des analyses plus approfondies.
"""
    )


def main() -> None:
    st.set_page_config(page_title="Analyse textuelle avec K-means", layout="wide", initial_sidebar_state="expanded")
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)
    enforce_streamlit_access(APP_TICKET_DEFAULT_ID, APP_NAME)

    st.title("Analyse textuelle avec K-means")
    st.markdown(
        "**Version 0.1 beta - modifiée : 24-07-2026 - Stéphane Meurisse - "
        "[www.codeandcortex.fr](http://www.codeandcortex.fr)**"
    )

    menu_principal = st.radio(
        "Menu Principal",
        ["Préparation des Données", "Analyse des Données", "FAQ"],
        horizontal=True,
    )

    if "df" not in st.session_state:
        st.session_state.df = None
    if "file_name" not in st.session_state:
        st.session_state.file_name = None
    if "save_directory" not in st.session_state:
        st.session_state.save_directory = str(get_output_directory())
    if "stopword_mode" not in st.session_state:
        st.session_state.stopword_mode = STOPWORD_MODE_FRENCH
    if "custom_stopwords" not in st.session_state:
        st.session_state.custom_stopwords = ""
    if "apply_stopwords_to_clustering" not in st.session_state:
        st.session_state.apply_stopwords_to_clustering = False
    if "wordcloud_max_words" not in st.session_state:
        st.session_state.wordcloud_max_words = 100

    if menu_principal == "Préparation des Données":
        render_preparation()
    elif menu_principal == "Analyse des Données":
        render_analysis()
    elif menu_principal == "FAQ":
        render_faq()


if __name__ == "__main__":
    main()
