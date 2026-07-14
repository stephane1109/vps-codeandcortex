import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ticket_gate import enforce_streamlit_access, keep_ticket_alive


RESULT_COLUMNS = [
    "Titre",
    "Description",
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

    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        st.markdown("#### Nombre de videos par date")
        st.bar_chart(chart_df["Nombre de videos"])
    with chart_col_2:
        st.markdown("#### Vues par date")
        st.line_chart(chart_df["Vues"])

    chart_col_3, chart_col_4 = st.columns(2)
    with chart_col_3:
        st.markdown("#### Likes par date")
        st.line_chart(chart_df["Likes"])
    with chart_col_4:
        st.markdown("#### Commentaires par date")
        st.line_chart(chart_df["Commentaires"])


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
        st.dataframe(df_resultats, use_container_width=True)
        st.download_button(
            label="Télécharger les résultats au format Excel",
            data=dataframe_to_excel_bytes(df_resultats),
            file_name=st.session_state.nom_fichier_export,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        render_evolution_charts(df_resultats)
