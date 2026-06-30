import io
import re
from datetime import date, datetime
from typing import Iterable

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


RESULT_COLUMNS = [
    "Titre",
    "Description",
    "Date de publication",
    "URL",
    "Channel ID",
    "Nom de la chaine",
    "Categorie",
    "Vues",
    "Likes",
    "Commentaires",
    "Commentaires desactives",
    "Langue par defaut",
    "Langue audio par defaut",
]

INTERNAL_DATE_COLUMN = "_date_publication_utc"

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


def build_date_filter_labels(df: pd.DataFrame) -> list[str]:
    if df.empty or "Date de publication" not in df.columns:
        return []

    labels = (
        pd.to_datetime(df["Date de publication"], errors="coerce")
        .dt.strftime("%Y-%m-%d")
        .dropna()
        .drop_duplicates()
        .sort_values()
    )
    return labels.tolist()


def filter_dataframe_by_checked_dates(df: pd.DataFrame) -> pd.DataFrame:
    available_dates = build_date_filter_labels(df)
    if not available_dates:
        return df

    st.markdown("### 3. Filtrage fin par date")
    st.caption("Decoche une date pour l'exclure du tableau, de l'export et des graphiques.")

    selected_dates: list[str] = []
    columns = st.columns(4)
    for index, date_label in enumerate(available_dates):
        with columns[index % 4]:
            if st.checkbox(date_label, value=True, key=f"youtube_date_filter_{date_label}"):
                selected_dates.append(date_label)

    if not selected_dates:
        return df.iloc[0:0].copy()

    publication_dates = pd.to_datetime(df["Date de publication"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df[publication_dates.isin(selected_dates)].reset_index(drop=True)


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
        st.info("Les graphiques d'evolution ne sont pas disponibles pour ces resultats.")
        return

    st.markdown("### 4. Graphiques d'evolution")
    st.caption("Les valeurs sont regroupees par date de publication a partir des videos actuellement affichees.")

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
    youtube = build("youtube", "v3", developerKey=cle_api)
    category_mapping = build_category_mapping(youtube, region_code)

    page_token = None
    collected_items: list[dict[str, object]] = []

    while True:
        search_params = {
            "q": mot_cle,
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "order": "date",
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
        video_ids = [
            item.get("id", {}).get("videoId")
            for item in search_response.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        for video_id_batch in chunked(video_ids, 50):
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

                if language_code and default_language != language_code and default_audio_language != language_code:
                    continue

                date_iso = snippet.get("publishedAt", "")
                collected_items.append(
                    {
                        "Titre": snippet.get("title", ""),
                        "Description": snippet.get("description", ""),
                        "Date de publication": format_published_at(date_iso),
                        "URL": f"https://www.youtube.com/watch?v={video_id}",
                        "Channel ID": snippet.get("channelId", ""),
                        "Nom de la chaine": snippet.get("channelTitle", ""),
                        "Categorie": category_mapping.get(snippet.get("categoryId", ""), ""),
                        "Vues": int(stats.get("viewCount", 0)),
                        "Likes": int(stats.get("likeCount", 0)),
                        "Commentaires": int(stats.get("commentCount", 0)),
                        "Commentaires desactives": "commentCount" not in stats,
                        "Langue par defaut": default_language,
                        "Langue audio par defaut": default_audio_language,
                        INTERNAL_DATE_COLUMN: date_iso,
                    }
                )

        page_token = search_response.get("nextPageToken")
        if not page_token or len(collected_items) >= 500:
            break

    if not collected_items:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    df = pd.DataFrame(collected_items)
    df[INTERNAL_DATE_COLUMN] = pd.to_datetime(df[INTERNAL_DATE_COLUMN], errors="coerce", utc=True)

    if published_after:
        df = df[df[INTERNAL_DATE_COLUMN] >= pd.to_datetime(published_after, utc=True)]
    if published_before:
        df = df[df[INTERNAL_DATE_COLUMN] <= pd.to_datetime(published_before, utc=True)]

    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=False, na_position="last")

    df = df.head(max_videos).copy()
    formatted_dates = df[INTERNAL_DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.loc[formatted_dates.notna(), "Date de publication"] = formatted_dates[formatted_dates.notna()]
    df = df.reset_index(drop=True)
    return df[RESULT_COLUMNS]


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultats")
    buffer.seek(0)
    return buffer.getvalue()


st.set_page_config(page_title="Extraction infos YouTube", layout="centered")

if "df_resultats" not in st.session_state:
    st.session_state.df_resultats = None
if "nom_fichier_export" not in st.session_state:
    st.session_state.nom_fichier_export = "youtube_resultats.xlsx"

st.title("Extraction d'informations YouTube")
st.caption("Recherche de videos YouTube par mot-cle avec export Excel.")

st.markdown("### 1. Parametres de recherche")

cle_api_input = st.text_input(
    "Cle API YouTube",
    placeholder="Entrez votre cle API YouTube Data v3",
    type="password",
)
mot_cle_input = st.text_input(
    "Mot-cle de recherche",
    placeholder="Ex : IA, Picasso, energie, geopolitique",
)

filters_col_1, filters_col_2, filters_col_3 = st.columns(3)

with filters_col_1:
    region_label = st.selectbox("Region des resultats", options=list(REGION_OPTIONS.keys()), index=0)
    region_code = REGION_OPTIONS[region_label]

with filters_col_2:
    language_label = st.selectbox("Langue declaree", options=list(LANGUAGE_OPTIONS.keys()), index=0)
    language_code = LANGUAGE_OPTIONS[language_label]

with filters_col_3:
    max_videos = st.number_input(
        "Nombre de videos a extraire",
        min_value=1,
        max_value=500,
        value=100,
        step=10,
    )

date_range = st.date_input(
    "Plage de dates de publication",
    value=(date.today().replace(month=1, day=1), date.today()),
)

published_after = None
published_before = None
date_range_valid = isinstance(date_range, (tuple, list)) and len(date_range) == 2

if date_range_valid:
    published_after = date_range[0].strftime("%Y-%m-%dT00:00:00Z")
    published_before = date_range[1].strftime("%Y-%m-%dT23:59:59Z")
else:
    st.warning("Selectionnez une date de debut et une date de fin pour lancer la recherche.")

st.markdown("### 2. Tri des resultats")

sort_by = st.radio(
    "Trier les videos par",
    options=["Vues", "Likes", "Commentaires"],
    horizontal=True,
)

st.info(
    "Une cle API YouTube Data v3 est necessaire. "
    "Le nombre reel de resultats depend de la disponibilite de l'API et des metadonnees exposees par YouTube."
)

if st.button("Lancer la recherche", type="primary", disabled=not date_range_valid):
    if not cle_api_input or not mot_cle_input.strip():
        st.error("Renseignez la cle API et le mot-cle de recherche.")
    else:
        with st.spinner("Recherche des videos en cours..."):
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
                fragment = normaliser_fragment_nom_fichier(mot_cle_input)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state.nom_fichier_export = f"youtube_{fragment}_{timestamp}.xlsx"
            except HttpError as exc:
                st.session_state.df_resultats = None
                st.error(f"Erreur API YouTube : {exc}")
            except Exception as exc:  # pragma: no cover - garde-fou Streamlit
                st.session_state.df_resultats = None
                st.error(f"Erreur lors de la recuperation des videos : {exc}")

df_resultats = st.session_state.df_resultats

if df_resultats is not None:
    if df_resultats.empty:
        st.warning("Aucune video ne correspond aux filtres selectionnes.")
    else:
        df_resultats_filtres = filter_dataframe_by_checked_dates(df_resultats)
        if df_resultats_filtres.empty:
            st.warning("Aucune date n'est actuellement selectionnee. Coche au moins une date pour afficher des resultats.")
        st.success(f"{len(df_resultats_filtres)} video(s) affichee(s) sur {len(df_resultats)} recuperee(s).")
        st.dataframe(df_resultats_filtres, use_container_width=True)
        st.download_button(
            label="Telecharger les resultats au format Excel",
            data=dataframe_to_excel_bytes(df_resultats_filtres),
            file_name=st.session_state.nom_fichier_export,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        render_evolution_charts(df_resultats_filtres)
