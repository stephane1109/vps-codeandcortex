import io
import hashlib
import math
import json
import re
import tempfile
from collections import defaultdict
from datetime import date, datetime
from html import escape
from itertools import combinations
from pathlib import Path
from typing import Iterable

import networkx as nx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pyvis.network import Network
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ticket_gate import enforce_streamlit_access, keep_ticket_alive


RESULT_COLUMNS = [
    "Titre",
    "Description",
    "Tags",
    "Date de publication",
    "URL",
    "Channel ID",
    "Nom de la chaine",
    "Catégorie",
    "Vues",
    "Likes",
    "Commentaires",
    "Commentaires désactivés",
    "Langue par défaut",
    "Langue audio par défaut",
]

INTERNAL_DATE_COLUMN = "_date_publication_utc"
APP_NAME = "Extraction d'informations YouTube"
APP_TICKET_DEFAULT_ID = "Extraction_infos_YouTube"
APP_DIR = Path(__file__).resolve().parent
HELP_PATH = APP_DIR / "aide.md"

REGION_OPTIONS = {
    "Toutes": None,
    "France": "FR",
    "Etats-Unis": "US",
}

LANGUAGE_OPTIONS = {
    "Toutes": None,
    "fr": "fr",
    "en": "en",
}

YOUTUBE_FIRST_PUBLIC_DATE = date(2005, 2, 14)
NETWORK_STOPWORDS = {
    "avec", "dans", "des", "les", "pour", "sur", "une", "aux", "par", "que", "qui", "est", "sont", "plus", "moins",
    "this", "that", "with", "from", "your", "have", "video", "youtube", "vous", "nous", "leur", "leurs", "the",
    "and", "for", "are", "www", "http", "https", "com", "comment", "comme", "tout", "tous", "toutes",
}
NETWORK_COLORS = [
    "#ea580c", "#2563eb", "#16a34a", "#9333ea", "#dc2626", "#0891b2", "#ca8a04", "#be185d",
    "#4f46e5", "#0f766e", "#a16207", "#7c3aed", "#15803d", "#b91c1c", "#0369a1",
]
COMMENTER_COLUMNS = [
    "Commentateurs",
    "Auteurs commentaires",
    "Auteurs des commentaires",
    "Comment authors",
    "Commentateurs communs",
]


def safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def empty_results_with_diagnostic(messages: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(columns=RESULT_COLUMNS)
    df.attrs["diagnostic"] = messages
    return df


def normaliser_fragment_nom_fichier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "recherche"


def chunked(values: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def format_published_at(date_iso: str) -> str:
    if not date_iso:
        return ""
    try:
        return datetime.fromisoformat(date_iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return date_iso


def build_evolution_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Date de publication" not in df.columns:
        return pd.DataFrame()

    working_df = df.copy()
    working_df["_jour_publication"] = pd.to_datetime(
        working_df["Date de publication"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")
    working_df = working_df.dropna(subset=["_jour_publication"])
    if working_df.empty:
        return pd.DataFrame()

    evolution_df = (
        working_df.groupby("_jour_publication", as_index=False)
        .agg(
            videos=("Titre", "size"),
            vues=("Vues", "sum"),
            likes=("Likes", "sum"),
            commentaires=("Commentaires", "sum"),
        )
        .rename(
            columns={
                "_jour_publication": "Date",
                "videos": "Nombre de videos",
                "vues": "Vues",
                "likes": "Likes",
                "commentaires": "Commentaires",
            }
        )
        .sort_values("Date")
    )
    return evolution_df


def render_evolution_charts(df: pd.DataFrame) -> None:
    evolution_df = build_evolution_dataframe(df)
    if evolution_df.empty:
        st.info("Les graphiques d'évolution ne sont pas disponibles pour ces résultats.")
        return

    st.markdown("### 3. Graphiques d'évolution")
    st.caption("Les valeurs sont regroupées par date de publication à partir des vidéos actuellement affichées.")

    chart_df = evolution_df.set_index("Date")

    st.markdown("#### Nombre de vidéos par date")
    st.bar_chart(chart_df["Nombre de videos"], use_container_width=True)

    st.markdown("#### Vues par date")
    st.line_chart(chart_df["Vues"], use_container_width=True)

    st.markdown("#### Likes par date")
    st.line_chart(chart_df["Likes"], use_container_width=True)

    st.markdown("#### Commentaires par date")
    st.line_chart(chart_df["Commentaires"], use_container_width=True)


def truncate_label(value: object, limit: int = 42) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def render_network_graph(df: pd.DataFrame) -> None:
    if df.empty or "Nom de la chaine" not in df.columns or "Titre" not in df.columns:
        st.info("Le graphe réseau n'est pas disponible pour ces résultats.")
        return

    graph_df = df.copy()
    graph_df["Nom de la chaine"] = graph_df["Nom de la chaine"].fillna("Chaîne inconnue").replace("", "Chaîne inconnue")
    graph_df["Titre"] = graph_df["Titre"].fillna("Vidéo sans titre").replace("", "Vidéo sans titre")
    graph_df["Vues"] = pd.to_numeric(graph_df.get("Vues", 0), errors="coerce").fillna(0)
    graph_df = graph_df.sort_values("Vues", ascending=False).head(60).reset_index(drop=True)

    if graph_df.empty:
        st.info("Le graphe réseau n'est pas disponible pour ces résultats.")
        return

    channels = list(dict.fromkeys(graph_df["Nom de la chaine"].tolist()))
    width = 1180
    height = max(620, min(1400, 240 + max(len(channels), len(graph_df)) * 22))
    left_x = 220
    right_x = 900
    channel_step = height / (len(channels) + 1)
    video_step = height / (len(graph_df) + 1)
    max_views = max(float(graph_df["Vues"].max()), 1.0)

    channel_positions = {
        channel: (left_x, int((index + 1) * channel_step))
        for index, channel in enumerate(channels)
    }

    edges_svg: list[str] = []
    channels_svg: list[str] = []
    videos_svg: list[str] = []

    for channel, (x, y) in channel_positions.items():
        count = int((graph_df["Nom de la chaine"] == channel).sum())
        radius = min(34, 14 + count * 3)
        label = escape(truncate_label(channel, 34))
        channel_title = escape(str(channel))
        channels_svg.append(
            f"""
            <g class="node channel-node">
                <circle cx="{x}" cy="{y}" r="{radius}"></circle>
                <text x="{x - radius - 12}" y="{y + 5}" text-anchor="end">{label}</text>
                <title>{channel_title} - {count} vidéo(s)</title>
            </g>
            """
        )

    for index, row in graph_df.iterrows():
        video_x = right_x
        video_y = int((index + 1) * video_step)
        channel_x, channel_y = channel_positions[row["Nom de la chaine"]]
        views = float(row["Vues"])
        radius = 7 + (views / max_views) * 18
        title = str(row["Titre"])
        label = escape(truncate_label(title, 46))
        escaped_title = escape(title)
        url = escape(str(row.get("URL", "") or ""), quote=True)
        stroke_width = 1.2 + (views / max_views) * 3

        edges_svg.append(
            f"""
            <line
                class="edge"
                x1="{channel_x + 24}"
                y1="{channel_y}"
                x2="{video_x - 24}"
                y2="{video_y}"
                stroke-width="{stroke_width:.2f}"
            />
            """
        )
        videos_svg.append(
            f"""
            <a href="{url}" target="_blank" rel="noopener noreferrer">
                <g class="node video-node">
                    <circle cx="{video_x}" cy="{video_y}" r="{radius:.1f}"></circle>
                    <text x="{video_x + radius + 10}" y="{video_y + 5}">{label}</text>
                    <title>{escaped_title} - {int(views):,} vue(s)</title>
                </g>
            </a>
            """
        )

    html = f"""
    <style>
        .youtube-network {{
            width: 100%;
            min-height: {height}px;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            background: linear-gradient(135deg, #fffaf2 0%, #f8fafc 58%, #eef7ff 100%);
            overflow: auto;
        }}
        .youtube-network svg {{
            width: 100%;
            min-width: 1120px;
            height: {height}px;
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .youtube-network .edge {{
            stroke: rgba(234, 88, 12, 0.34);
        }}
        .youtube-network .channel-node circle {{
            fill: #fff7ed;
            stroke: #ea580c;
            stroke-width: 2.5;
        }}
        .youtube-network .video-node circle {{
            fill: #2563eb;
            fill-opacity: 0.82;
            stroke: #1d4ed8;
            stroke-width: 1.5;
        }}
        .youtube-network text {{
            fill: #1f2937;
            font-size: 13px;
            font-weight: 650;
        }}
    </style>
    <div class="youtube-network" role="img" aria-label="Graphe réseau des chaînes YouTube et des vidéos récupérées">
        <svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMin meet">
            <text x="{left_x}" y="34" text-anchor="middle" style="font-size:18px;fill:#9a3412;">Chaînes</text>
            <text x="{right_x}" y="34" text-anchor="middle" style="font-size:18px;fill:#1d4ed8;">Vidéos</text>
            {"".join(edges_svg)}
            {"".join(channels_svg)}
            {"".join(videos_svg)}
        </svg>
    </div>
    """

    st.markdown("### 4. Graphe réseau chaînes / vidéos")
    st.caption("Chaque lien relie une chaîne aux vidéos récupérées. La taille des vidéos dépend du nombre de vues.")
    components.html(html, height=min(height + 40, 1500), scrolling=True)


def extraire_video_id_youtube(value: object) -> str:
    text = str(value or "")
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([A-Za-z0-9_-]{6,})",
        r"[?&]v=([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def extraire_liens_youtube_description(value: object) -> set[str]:
    text = str(value or "")
    ids = set()
    for pattern in [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([A-Za-z0-9_-]{6,})",
        r"[?&]v=([A-Za-z0-9_-]{6,})",
    ]:
        ids.update(re.findall(pattern, text))
    return ids


def extraire_mots_cles_reseau(*values: object) -> set[str]:
    text = " ".join(str(value or "") for value in values).lower()
    tokens = re.findall(r"[a-zà-ÿ0-9][a-zà-ÿ0-9_-]{2,}", text)
    return {token.strip("_-") for token in tokens if token.strip("_-") not in NETWORK_STOPWORDS}


def extraire_commentateurs_reseau(row: pd.Series) -> set[str]:
    values = [row.get(column, "") for column in COMMENTER_COLUMNS if column in row.index]
    text = " ".join(str(value or "") for value in values)
    if not text.strip():
        return set()
    return {item.strip().lower() for item in re.split(r"[,;|\n\r\t]+", text) if item.strip()}


def couleur_stable(value: object) -> str:
    digest = hashlib.md5(str(value or "inconnu").encode("utf-8")).hexdigest()
    return NETWORK_COLORS[int(digest, 16) % len(NETWORK_COLORS)]


def calculer_matrice_similarite_textuelle(graph_df: pd.DataFrame) -> list[list[float]]:
    textes = (
        graph_df["Titre"].fillna("").astype(str)
        + " "
        + graph_df["Description"].fillna("").astype(str)
        + " "
        + graph_df.get("Tags", pd.Series([""] * len(graph_df))).fillna("").astype(str)
    ).tolist()
    if len(textes) < 2 or not any(texte.strip() for texte in textes):
        return [[0.0 for _ in textes] for _ in textes]
    try:
        matrix = TfidfVectorizer(max_features=2500, ngram_range=(1, 2), min_df=1).fit_transform(textes)
        return cosine_similarity(matrix).tolist()
    except ValueError:
        return [[0.0 for _ in textes] for _ in textes]


def score_proximite_dates(date_a: object, date_b: object, fenetre_jours: int) -> float:
    if fenetre_jours <= 0:
        return 0.0
    parsed_a = pd.to_datetime(date_a, errors="coerce")
    parsed_b = pd.to_datetime(date_b, errors="coerce")
    if pd.isna(parsed_a) or pd.isna(parsed_b):
        return 0.0
    delta = abs((parsed_a - parsed_b).days)
    if delta > fenetre_jours:
        return 0.0
    return max(0.0, 1.0 - (delta / fenetre_jours))


def construire_reseau_video(
    df: pd.DataFrame,
    type_relation: str,
    seuil: float,
    max_liens_par_video: int,
    fenetre_jours: int,
    max_videos: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    graph_df = df.copy().head(max_videos).reset_index(drop=True)
    if graph_df.empty:
        return graph_df, pd.DataFrame()

    graph_df["video_id"] = graph_df["URL"].apply(extraire_video_id_youtube)
    graph_df.loc[graph_df["video_id"].eq(""), "video_id"] = graph_df.index.map(lambda index: f"video_{index}")
    graph_df["Titre"] = graph_df["Titre"].fillna("Vidéo sans titre").replace("", "Vidéo sans titre")
    graph_df["Description"] = graph_df["Description"].fillna("")
    graph_df["Tags"] = graph_df.get("Tags", pd.Series([""] * len(graph_df))).fillna("")
    graph_df["Nom de la chaine"] = graph_df["Nom de la chaine"].fillna("Chaîne inconnue").replace("", "Chaîne inconnue")

    similarites = calculer_matrice_similarite_textuelle(graph_df)
    mots_cles = [
        extraire_mots_cles_reseau(row["Titre"], row["Description"], row.get("Tags", ""))
        for _, row in graph_df.iterrows()
    ]
    liens_description = [extraire_liens_youtube_description(value) for value in graph_df["Description"]]
    commentateurs = [extraire_commentateurs_reseau(row) for _, row in graph_df.iterrows()]

    candidates: list[dict[str, object]] = []
    for source, target in combinations(range(len(graph_df)), 2):
        row_a = graph_df.iloc[source]
        row_b = graph_df.iloc[target]

        score_texte = float(similarites[source][target])
        meme_chaine = 1.0 if row_a["Channel ID"] and row_a["Channel ID"] == row_b["Channel ID"] else 0.0
        union_mots = mots_cles[source] | mots_cles[target]
        score_mots = (len(mots_cles[source] & mots_cles[target]) / len(union_mots)) if union_mots else 0.0
        score_dates = score_proximite_dates(row_a["Date de publication"], row_b["Date de publication"], fenetre_jours)
        score_liens = 1.0 if row_a["video_id"] in liens_description[target] or row_b["video_id"] in liens_description[source] else 0.0
        union_commentateurs = commentateurs[source] | commentateurs[target]
        score_commentateurs = (
            len(commentateurs[source] & commentateurs[target]) / len(union_commentateurs)
            if union_commentateurs else 0.0
        )

        if type_relation == "Similarité texte":
            score = score_texte
        elif type_relation == "Même chaîne":
            score = meme_chaine
        elif type_relation == "Mots-clés communs":
            score = score_mots
        elif type_relation == "Proximité temporelle":
            score = score_dates
        elif type_relation == "Liens descriptions":
            score = score_liens
        elif type_relation == "Même commentateur":
            score = score_commentateurs
        else:
            score = (
                (0.40 * score_texte)
                + (0.18 * meme_chaine)
                + (0.14 * score_mots)
                + (0.10 * score_dates)
                + (0.08 * score_liens)
                + (0.10 * score_commentateurs)
            )
            if score_liens:
                score = max(score, 0.85)
            if meme_chaine and score_texte < 0.05:
                score = max(score, 0.35)
            if score_mots >= 0.20:
                score = max(score, 0.40 + (0.30 * score_mots))
            if score_commentateurs > 0:
                score = max(score, 0.55 + (0.35 * score_commentateurs))

        if score < seuil:
            continue

        raisons = []
        if score_texte > 0:
            raisons.append(f"texte={score_texte:.2f}")
        if meme_chaine:
            raisons.append("même chaîne")
        if score_mots > 0:
            raisons.append(f"mots-clés={score_mots:.2f}")
        if score_dates > 0:
            raisons.append(f"dates={score_dates:.2f}")
        if score_liens:
            raisons.append("lien description")
        if score_commentateurs > 0:
            raisons.append(f"commentateurs={score_commentateurs:.2f}")

        candidates.append(
            {
                "source": row_a["video_id"],
                "target": row_b["video_id"],
                "source_title": row_a["Titre"],
                "target_title": row_b["Titre"],
                "poids": round(float(score), 4),
                "relation": ", ".join(raisons) or type_relation,
                "similarite_texte": round(score_texte, 4),
                "meme_chaine": int(meme_chaine),
                "mots_cles_communs": round(score_mots, 4),
                "proximite_temporelle": round(score_dates, 4),
                "liens_description": int(score_liens),
                "commentateurs_communs": round(score_commentateurs, 4),
            }
        )

    candidates = sorted(candidates, key=lambda edge: float(edge["poids"]), reverse=True)
    degres: defaultdict[str, int] = defaultdict(int)
    edges: list[dict[str, object]] = []
    for edge in candidates:
        source = str(edge["source"])
        target = str(edge["target"])
        if degres[source] >= max_liens_par_video or degres[target] >= max_liens_par_video:
            continue
        edges.append(edge)
        degres[source] += 1
        degres[target] += 1

    return graph_df, pd.DataFrame(edges)


def rendre_html_pyvis(graph_df: pd.DataFrame, edges_df: pd.DataFrame, taille_noeud: str, couleur_noeud: str) -> tuple[str, nx.Graph]:
    graph = nx.Graph()
    for _, row in graph_df.iterrows():
        graph.add_node(row["video_id"], **row.to_dict())
    for _, edge in edges_df.iterrows():
        graph.add_edge(edge["source"], edge["target"], weight=float(edge["poids"]), label=edge["relation"])

    if couleur_noeud == "Cluster" and graph.number_of_edges() > 0:
        try:
            communautes = nx.algorithms.community.greedy_modularity_communities(graph)
        except Exception:
            communautes = [set(component) for component in nx.connected_components(graph)]
        cluster_map = {node: index for index, cluster in enumerate(communautes) for node in cluster}
    else:
        cluster_map = {}

    max_metric = max(float(pd.to_numeric(graph_df.get(taille_noeud, 0), errors="coerce").fillna(0).max()), 1.0)
    network = Network(height="760px", width="100%", bgcolor="#ffffff", font_color="#1f2937", cdn_resources="in_line")
    network.barnes_hut(gravity=-26000, central_gravity=0.22, spring_length=180, spring_strength=0.025, damping=0.82)

    url_map: dict[str, str] = {}
    for _, row in graph_df.iterrows():
        metric_value = float(pd.to_numeric(pd.Series([row.get(taille_noeud, 0)]), errors="coerce").fillna(0).iloc[0])
        size = 14 + 34 * math.sqrt(metric_value / max_metric)
        if couleur_noeud == "Chaîne":
            color = couleur_stable(row["Nom de la chaine"])
            group_label = row["Nom de la chaine"]
        elif couleur_noeud == "Période":
            date_value = pd.to_datetime(row["Date de publication"], errors="coerce")
            group_label = date_value.strftime("%Y-%m") if not pd.isna(date_value) else "Date inconnue"
            color = couleur_stable(group_label)
        else:
            group_label = f"Cluster {cluster_map.get(row['video_id'], 0) + 1}"
            color = couleur_stable(group_label)

        url = str(row.get("URL", "") or "")
        url_map[str(row["video_id"])] = url
        title = (
            f"<b>{escape(str(row['Titre']))}</b><br>"
            f"Chaîne : {escape(str(row['Nom de la chaine']))}<br>"
            f"Date : {escape(str(row.get('Date de publication', '')))}<br>"
            f"Vues : {safe_int(row.get('Vues', 0)):,}<br>"
            f"Likes : {safe_int(row.get('Likes', 0)):,}<br>"
            f"Commentaires : {safe_int(row.get('Commentaires', 0)):,}<br>"
            f"{escape(str(group_label))}<br>"
            "Double-clic : ouvrir la vidéo"
        )
        network.add_node(
            str(row["video_id"]),
            label=truncate_label(row["Titre"], 34),
            title=title,
            size=size,
            color=color,
            borderWidth=2,
        )

    for _, edge in edges_df.iterrows():
        network.add_edge(
            str(edge["source"]),
            str(edge["target"]),
            value=max(float(edge["poids"]) * 10, 1.0),
            title=f"{escape(str(edge['relation']))}<br>Score : {float(edge['poids']):.2f}",
            color="rgba(234, 88, 12, 0.42)",
        )

    with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False, encoding="utf-8") as tmp:
        output_path = Path(tmp.name)
    network.save_graph(str(output_path))
    html = output_path.read_text(encoding="utf-8")
    output_path.unlink(missing_ok=True)
    script = f"""
    <script>
    const codexVideoUrls = {json.dumps(url_map)};
    if (typeof network !== "undefined") {{
        network.on("doubleClick", function(params) {{
            if (params.nodes.length > 0) {{
                const url = codexVideoUrls[params.nodes[0]];
                if (url) {{
                    window.open(url, "_blank", "noopener,noreferrer");
                }}
            }}
        }});
    }}
    </script>
    """
    return html.replace("</body>", script + "</body>"), graph


def render_dynamic_video_network(df: pd.DataFrame) -> None:
    if df.empty or len(df) < 2:
        st.info("Le réseau dynamique nécessite au moins deux vidéos.")
        return

    st.markdown("### Réseau dynamique de similarité entre vidéos")
    st.caption("Les liens sont calculés à partir des métadonnées récupérées : titre, description, tags, chaîne, dates et liens YouTube cités.")

    col_1, col_2, col_3 = st.columns(3)
    with col_1:
        type_relation = st.selectbox(
            "Type de relation",
            [
                "Mixte",
                "Similarité texte",
                "Même chaîne",
                "Mots-clés communs",
                "Proximité temporelle",
                "Liens descriptions",
                "Même commentateur",
            ],
            help=(
                "Choisit la logique des liens entre vidéos. Mixte combine texte, chaîne, mots-clés, dates, liens cités "
                "et commentateurs si ces données existent. Même commentateur nécessite une colonne de commentateurs, "
                "car l'API vidéo standard ne fournit pas les auteurs de commentaires."
            ),
        )
        taille_noeud = st.selectbox(
            "Taille des nœuds selon",
            ["Vues", "Likes", "Commentaires"],
            help="Détermine la taille visuelle de chaque vidéo : plus la métrique choisie est élevée, plus le nœud est grand.",
        )
    with col_2:
        seuil = st.slider(
            "Seuil de similarité",
            min_value=0.0,
            max_value=1.0,
            value=0.25,
            step=0.05,
            help="Filtre les liens faibles. Une valeur basse affiche plus de liens ; une valeur haute garde seulement les relations fortes.",
        )
        couleur_noeud = st.selectbox(
            "Couleur selon",
            ["Chaîne", "Période", "Cluster"],
            help="Définit la couleur des nœuds : chaîne YouTube, mois de publication ou communauté calculée dans le graphe.",
        )
    with col_3:
        max_liens = st.slider(
            "Nombre maximum de liens par vidéo",
            min_value=1,
            max_value=12,
            value=4,
            help="Limite le nombre d'arêtes par vidéo pour éviter un graphe illisible quand beaucoup de vidéos sont proches.",
        )
        max_videos = st.slider(
            "Nombre maximum de vidéos dans le graphe",
            min_value=10,
            max_value=min(200, max(10, len(df))),
            value=min(80, max(10, len(df))),
            step=1,
            help="Limite le nombre de vidéos affichées pour préserver la lisibilité et les performances du graphe interactif.",
        )

    fenetre_jours = st.slider(
        "Fenêtre de proximité temporelle (jours)",
        min_value=1,
        max_value=365,
        value=30,
        help="Deux vidéos sont considérées proches dans le temps si leurs dates de publication sont dans cette fenêtre.",
    )
    if type_relation == "Même commentateur" and not any(column in df.columns for column in COMMENTER_COLUMNS):
        st.info(
            "L'option Même commentateur est prête, mais les résultats actuels ne contiennent pas encore les auteurs de commentaires. "
            "Pour l'activer réellement, il faudra ajouter une collecte de commentaires YouTube avec l'API commentThreads."
        )

    graph_df, edges_df = construire_reseau_video(
        df,
        type_relation=type_relation,
        seuil=float(seuil),
        max_liens_par_video=int(max_liens),
        fenetre_jours=int(fenetre_jours),
        max_videos=int(max_videos),
    )

    if graph_df.empty:
        st.info("Aucune vidéo exploitable pour le réseau.")
        return
    if edges_df.empty:
        st.warning("Aucun lien ne passe le seuil actuel. Diminue le seuil ou choisis le mode Mixte.")

    html, graph = rendre_html_pyvis(graph_df, edges_df, taille_noeud, couleur_noeud)
    st.caption(f"{graph.number_of_nodes()} nœud(s), {graph.number_of_edges()} lien(s). Double-clique sur un nœud pour ouvrir la vidéo YouTube.")
    components.html(html, height=820, scrolling=True)

    export_col_1, export_col_2 = st.columns(2)
    with export_col_1:
        st.download_button(
            "Télécharger le graphe HTML",
            data=html.encode("utf-8"),
            file_name="reseau_videos_youtube.html",
            mime="text/html",
        )
    with export_col_2:
        st.download_button(
            "Télécharger les relations CSV",
            data=edges_df.to_csv(index=False).encode("utf-8"),
            file_name="relations_videos_youtube.csv",
            mime="text/csv",
            disabled=edges_df.empty,
        )

    with st.expander("Voir les relations calculées", expanded=False):
        st.dataframe(edges_df, use_container_width=True, hide_index=True)


def build_category_mapping(youtube, region_code: str | None) -> dict[str, str]:
    if not region_code:
        return {}

    categories = youtube.videoCategories().list(part="snippet", regionCode=region_code).execute()
    return {
        item["id"]: item.get("snippet", {}).get("title", "")
        for item in categories.get("items", [])
    }


def rechercher_videos_youtube(
    cle_api: str,
    mot_cle: str,
    region_code: str | None = None,
    language_code: str | None = None,
    published_after: str | None = None,
    published_before: str | None = None,
    max_videos: int = 100,
    sort_by: str = "Vues",
) -> pd.DataFrame:
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    youtube = build("youtube", "v3", developerKey=cle_api)
    category_mapping = build_category_mapping(youtube, region_code)

    page_token = None
    collected_items: list[dict[str, object]] = []
    seen_video_ids: set[str] = set()
    diagnostic_messages: list[str] = []
    search_order = "viewCount" if sort_by == "Vues" else "relevance"
    target_pool_size = min(500, max(50, max_videos * 4))

    while True:
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
        search_params = {
            "q": mot_cle,
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "order": search_order,
            "safeSearch": "none",
        }
        if page_token:
            search_params["pageToken"] = page_token
        if region_code:
            search_params["regionCode"] = region_code
        if language_code:
            search_params["relevanceLanguage"] = language_code
        if published_after:
            search_params["publishedAfter"] = published_after
        if published_before:
            search_params["publishedBefore"] = published_before

        search_response = youtube.search().list(**search_params).execute()
        keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
        search_items = search_response.get("items", [])
        video_ids = [
            item.get("id", {}).get("videoId")
            for item in search_items
            if item.get("id", {}).get("videoId") and item.get("id", {}).get("videoId") not in seen_video_ids
        ]
        seen_video_ids.update(video_ids)
        diagnostic_messages.append(
            f"Page API : {len(search_items)} élément(s), {len(video_ids)} nouvelle(s) vidéo(s), ordre={search_order}."
        )

        for video_id_batch in chunked(video_ids, 50):
            keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
            videos_response = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_id_batch),
            ).execute()

            for video in videos_response.get("items", []):
                snippet = video.get("snippet", {})
                stats = video.get("statistics", {})
                video_id = video.get("id", "")

                default_language = snippet.get("defaultLanguage")
                default_audio_language = snippet.get("defaultAudioLanguage")

                date_iso = snippet.get("publishedAt", "")
                collected_items.append(
                    {
                        "Titre": snippet.get("title", ""),
                        "Description": snippet.get("description", ""),
                        "Tags": ", ".join(snippet.get("tags", []) or []),
                        "Date de publication": format_published_at(date_iso),
                        "URL": f"https://www.youtube.com/watch?v={video_id}",
                        "Channel ID": snippet.get("channelId", ""),
                        "Nom de la chaine": snippet.get("channelTitle", ""),
                        "Catégorie": category_mapping.get(snippet.get("categoryId", ""), ""),
                        "Vues": safe_int(stats.get("viewCount", 0)),
                        "Likes": safe_int(stats.get("likeCount", 0)),
                        "Commentaires": safe_int(stats.get("commentCount", 0)),
                        "Commentaires désactivés": "commentCount" not in stats,
                        "Langue par défaut": default_language,
                        "Langue audio par défaut": default_audio_language,
                        INTERNAL_DATE_COLUMN: date_iso,
                    }
                )

        page_token = search_response.get("nextPageToken")
        if not page_token or len(collected_items) >= target_pool_size:
            break

    if not collected_items:
        diagnostic_messages.append("Aucune vidéo récupérée depuis YouTube search.list/videos.list.")
        return empty_results_with_diagnostic(diagnostic_messages)

    df = pd.DataFrame(collected_items)
    df[INTERNAL_DATE_COLUMN] = pd.to_datetime(df[INTERNAL_DATE_COLUMN], errors="coerce", utc=True)
    collected_count = len(df)

    if published_after:
        df = df[df[INTERNAL_DATE_COLUMN] >= pd.to_datetime(published_after, utc=True)]
    if published_before:
        df = df[df[INTERNAL_DATE_COLUMN] <= pd.to_datetime(published_before, utc=True)]

    if df.empty:
        diagnostic_messages.append(
            f"{collected_count} vidéo(s) récupérée(s), mais aucune ne reste après filtrage par plage de dates."
        )
        return empty_results_with_diagnostic(diagnostic_messages)

    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=False, na_position="last")

    df = df.head(max_videos).copy()
    formatted_dates = df[INTERNAL_DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.loc[formatted_dates.notna(), "Date de publication"] = formatted_dates[formatted_dates.notna()]
    df = df.reset_index(drop=True)
    diagnostic_messages.append(f"{len(df)} vidéo(s) conservée(s) après filtrage et tri.")
    keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
    result_df = df[RESULT_COLUMNS].copy()
    result_df.attrs["diagnostic"] = diagnostic_messages
    return result_df


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Résultats")
    buffer.seek(0)
    return buffer.getvalue()


def load_help_markdown() -> str:
    try:
        return HELP_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Le fichier `aide.md` est introuvable pour cette application."


def render_help_tab() -> None:
    with st.expander("Aide - clé API YouTube Data v3", expanded=False):
        st.markdown(load_help_markdown(), unsafe_allow_html=True)


# La sidebar doit rester visible par défaut pour afficher nettement
# l'état utilisateur / file d'attente / libération d'accès.
st.set_page_config(
    page_title="Extraction infos YouTube",
    layout="wide",
    initial_sidebar_state="expanded",
)
enforce_streamlit_access(APP_TICKET_DEFAULT_ID, APP_NAME)

if "df_resultats" not in st.session_state:
    st.session_state.df_resultats = None
if "nom_fichier_export" not in st.session_state:
    st.session_state.nom_fichier_export = "youtube_resultats.xlsx"
if "youtube_search_diagnostic" not in st.session_state:
    st.session_state.youtube_search_diagnostic = []

st.title("Extraction d'informations YouTube")
st.caption("Recherche de vidéos YouTube par mot-clé avec export Excel.")
render_help_tab()

st.markdown("### 1. Paramètres de recherche")

cle_api_input = st.text_input(
    "Clé API YouTube",
    placeholder="Entrez votre clé API YouTube Data v3",
    type="password",
)
mot_cle_input = st.text_input(
    "Mot-clé de recherche",
    placeholder="Ex : IA, Picasso, energie, geopolitique",
)

filters_col_1, filters_col_2, filters_col_3 = st.columns(3)

with filters_col_1:
    region_label = st.selectbox("Région des résultats", options=list(REGION_OPTIONS.keys()), index=0)
    region_code = REGION_OPTIONS[region_label]

with filters_col_2:
    language_label = st.selectbox("Langue déclarée", options=list(LANGUAGE_OPTIONS.keys()), index=0)
    language_code = LANGUAGE_OPTIONS[language_label]

with filters_col_3:
    max_videos = st.number_input(
        "Nombre de vidéos à extraire",
        min_value=1,
        max_value=500,
        value=100,
        step=10,
    )

published_after = None
published_before = None
date_range_valid = True
use_date_range = st.checkbox(
    "Limiter la recherche à une plage de dates",
    value=False,
    help="Décochez cette option pour interroger YouTube sans restriction de date, puis filtrez les dates avec les cases du tableau.",
)

if use_date_range:
    date_range = st.date_input(
        "Plage de dates de publication",
        value=(YOUTUBE_FIRST_PUBLIC_DATE, date.today()),
    )
    date_range_valid = isinstance(date_range, (tuple, list)) and len(date_range) == 2
    if date_range_valid:
        published_after = date_range[0].strftime("%Y-%m-%dT00:00:00Z")
        published_before = date_range[1].strftime("%Y-%m-%dT23:59:59Z")
    else:
        st.warning("Sélectionnez une date de début et une date de fin pour lancer la recherche.")
else:
    st.caption("La recherche n'est pas limitée par date. Les dates récupérées pourront ensuite être filtrées avec les cases à cocher.")

st.markdown("### 2. Tri des résultats")

sort_by = st.radio(
    "Trier les vidéos par",
    options=["Vues", "Likes", "Commentaires"],
    horizontal=True,
)

st.info(
    "Une clé API YouTube Data v3 est nécessaire. "
    "Le nombre réel de résultats dépend de la disponibilité de l'API et des métadonnées exposées par YouTube."
)

if st.button("Lancer la recherche", type="primary", disabled=not date_range_valid):
    if not cle_api_input or not mot_cle_input.strip():
        st.error("Renseignez la clé API et le mot-clé de recherche.")
    else:
        with st.spinner("Recherche des vidéos en cours..."):
            keep_ticket_alive(APP_TICKET_DEFAULT_ID, APP_NAME)
            try:
                df_resultats = rechercher_videos_youtube(
                    cle_api=cle_api_input.strip(),
                    mot_cle=mot_cle_input.strip(),
                    region_code=region_code,
                    language_code=language_code,
                    published_after=published_after,
                    published_before=published_before,
                    max_videos=int(max_videos),
                    sort_by=sort_by,
                )
                st.session_state.df_resultats = df_resultats
                st.session_state.youtube_search_diagnostic = df_resultats.attrs.get("diagnostic", [])
                fragment = normaliser_fragment_nom_fichier(mot_cle_input)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state.nom_fichier_export = f"youtube_{fragment}_{timestamp}.xlsx"
            except HttpError as exc:
                st.session_state.df_resultats = None
                st.session_state.youtube_search_diagnostic = []
                st.error(f"Erreur API YouTube : {exc}")
            except Exception as exc:  # pragma: no cover - garde-fou Streamlit
                st.session_state.df_resultats = None
                st.session_state.youtube_search_diagnostic = []
                st.error(f"Erreur lors de la récupération des vidéos : {exc}")

df_resultats = st.session_state.df_resultats

if df_resultats is not None:
    if df_resultats.empty:
        st.warning("Aucune vidéo ne correspond aux filtres sélectionnés.")
        if st.session_state.youtube_search_diagnostic:
            with st.expander("Diagnostic de recherche YouTube", expanded=True):
                for message in st.session_state.youtube_search_diagnostic:
                    st.write(message)
    else:
        st.success(f"{len(df_resultats)} vidéo(s) récupérée(s).")
        tab_resultats, tab_graphiques, tab_reseau = st.tabs(["Résultats", "Graphiques", "Réseau dynamique"])

        with tab_resultats:
            st.dataframe(df_resultats, use_container_width=True)
            st.download_button(
                label="Télécharger les résultats au format Excel",
                data=dataframe_to_excel_bytes(df_resultats),
                file_name=st.session_state.nom_fichier_export,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            if st.session_state.youtube_search_diagnostic:
                with st.expander("Diagnostic de recherche YouTube", expanded=False):
                    for message in st.session_state.youtube_search_diagnostic:
                        st.write(message)

        with tab_graphiques:
            render_evolution_charts(df_resultats)

        with tab_reseau:
            render_dynamic_video_network(df_resultats)
