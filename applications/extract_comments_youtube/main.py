import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


RESULT_COLUMNS = [
    "Auteur",
    "Date",
    "Type",
    "Commentaire",
    "ID commentaire",
    "ID parent",
]

DEFAULT_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
APP_DIR = Path(__file__).resolve().parent
HELP_PATH = APP_DIR / "aide.md"


class CommentsDisabledError(Exception):
    """Raised when comments are disabled for the selected video."""


def normaliser_fragment_nom_fichier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "youtube_comments"


def remove_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F700-\U0001F77F"
        u"\U0001F780-\U0001F7FF"
        u"\U0001F800-\U0001F8FF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def nettoyer_texte(text: str, clean_emojis: bool, lowercase: bool = False) -> str:
    value = text or ""
    if clean_emojis:
        value = remove_emojis(value)
    value = value.strip()
    if lowercase:
        value = value.lower()
    return value


def is_valid_video_id(candidate: str | None) -> bool:
    return bool(candidate and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate))


def extraire_video_id(url_video: str) -> str:
    url_video = url_video.strip()
    if not url_video:
        raise ValueError("Renseignez une URL YouTube ou YouTube Shorts.")

    parsed = urlparse(url_video)
    host = parsed.netloc.lower()

    if host.endswith("youtu.be"):
        candidate = parsed.path.lstrip("/").split("/")[0]
        if is_valid_video_id(candidate):
            return candidate

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if is_valid_video_id(query_video_id):
            return query_video_id

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live", "v", "videos"}:
            candidate = path_parts[1]
            if is_valid_video_id(candidate):
                return candidate

    match = re.search(r"([A-Za-z0-9_-]{11})", url_video)
    if match:
        return match.group(1)

    raise ValueError("Impossible d'extraire un identifiant video valide depuis cette URL.")


def parse_api_error(exc: HttpError) -> tuple[str | None, str]:
    fallback_message = f"Erreur API YouTube ({exc.resp.status})."
    raw_content = getattr(exc, "content", b"") or b""

    try:
        payload = json.loads(raw_content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, fallback_message

    error_block = payload.get("error", {})
    message = error_block.get("message") or fallback_message
    errors = error_block.get("errors", [])
    reason = errors[0].get("reason") if errors else None

    custom_messages = {
        "commentsDisabled": "Les commentaires sont desactives pour cette video.",
        "quotaExceeded": "Le quota de l'API YouTube est depasse. Reessayez plus tard ou utilisez une autre cle API.",
        "dailyLimitExceeded": "La limite quotidienne de l'API YouTube est atteinte pour cette cle.",
        "keyInvalid": "La cle API YouTube semble invalide.",
        "videoNotFound": "La video est introuvable ou non accessible via l'API.",
        "forbidden": "Acces refuse par l'API YouTube pour cette requete.",
    }

    return reason, custom_messages.get(reason, message)


def format_datetime_label(date_iso: str) -> str:
    if not date_iso:
        return ""
    try:
        return datetime.fromisoformat(date_iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return date_iso


def format_date_label(date_iso: str) -> str:
    if not date_iso:
        return ""
    try:
        return datetime.fromisoformat(date_iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_iso


def format_export_date_label(date_iso: str) -> str:
    if not date_iso:
        return ""
    try:
        return datetime.fromisoformat(date_iso.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except ValueError:
        return date_iso


def build_youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def get_video_details(youtube, video_id: str, clean_emojis: bool) -> dict[str, object]:
    response = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    items = response.get("items", [])
    if not items:
        raise ValueError("Aucune video YouTube n'a ete trouvee pour cette URL.")

    item = items[0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    published_at = snippet.get("publishedAt", "")
    title = nettoyer_texte(snippet.get("title", ""), clean_emojis=clean_emojis)
    channel_title = nettoyer_texte(snippet.get("channelTitle", ""), clean_emojis=clean_emojis)

    comment_count = statistics.get("commentCount")
    return {
        "Video ID": video_id,
        "URL": f"https://www.youtube.com/watch?v={video_id}",
        "Titre": title,
        "Nom de la chaine": channel_title,
        "Date de publication": format_datetime_label(published_at),
        "Date publication export": format_export_date_label(published_at),
        "Date ISO": published_at,
        "Vues": int(statistics.get("viewCount", 0)),
        "Likes": int(statistics.get("likeCount", 0)),
        "Commentaires exposes par YouTube": int(comment_count) if comment_count is not None else None,
        "Commentaires desactives": comment_count is None,
    }


def fetch_replies(
    youtube,
    parent_comment_id: str,
    max_results: int,
    clean_emojis: bool,
    lowercase_comments: bool,
) -> list[dict[str, str]]:
    replies: list[dict[str, str]] = []
    page_token = None

    while len(replies) < max_results:
        request_params = {
            "part": "snippet",
            "parentId": parent_comment_id,
            "textFormat": "plainText",
            "maxResults": min(100, max_results - len(replies)),
        }
        if page_token:
            request_params["pageToken"] = page_token

        response = youtube.comments().list(**request_params).execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            author = nettoyer_texte(snippet.get("authorDisplayName", "").replace("@", ""), clean_emojis=clean_emojis)
            comment = nettoyer_texte(
                snippet.get("textDisplay", ""),
                clean_emojis=clean_emojis,
                lowercase=lowercase_comments,
            )
            replies.append(
                {
                    "Auteur": author,
                    "Date": format_date_label(snippet.get("publishedAt", "")),
                    "Type": "Reponse",
                    "Commentaire": comment,
                    "ID commentaire": item.get("id", ""),
                    "ID parent": parent_comment_id,
                }
            )

            if len(replies) >= max_results:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return replies


def fetch_comments(
    youtube,
    video_id: str,
    max_results: int,
    include_replies: bool,
    clean_emojis: bool,
    lowercase_comments: bool,
) -> pd.DataFrame:
    comments: list[dict[str, str]] = []
    page_token = None

    while len(comments) < max_results:
        try:
            request_params = {
                "part": "snippet",
                "videoId": video_id,
                "textFormat": "plainText",
                "maxResults": min(100, max_results - len(comments)),
                "order": "time",
            }
            if page_token:
                request_params["pageToken"] = page_token

            response = youtube.commentThreads().list(**request_params).execute()
        except HttpError as exc:
            reason, message = parse_api_error(exc)
            if reason == "commentsDisabled":
                raise CommentsDisabledError(message) from exc
            raise

        items = response.get("items", [])
        if not items:
            break

        for item in items:
            top_level_comment = item.get("snippet", {}).get("topLevelComment", {})
            snippet = top_level_comment.get("snippet", {})
            comment_id = top_level_comment.get("id", "")

            author = nettoyer_texte(snippet.get("authorDisplayName", "").replace("@", ""), clean_emojis=clean_emojis)
            comment = nettoyer_texte(
                snippet.get("textDisplay", ""),
                clean_emojis=clean_emojis,
                lowercase=lowercase_comments,
            )
            comments.append(
                {
                    "Auteur": author,
                    "Date": format_date_label(snippet.get("publishedAt", "")),
                    "Type": "Commentaire",
                    "Commentaire": comment,
                    "ID commentaire": comment_id,
                    "ID parent": "",
                }
            )

            if len(comments) >= max_results:
                break

            total_reply_count = int(item.get("snippet", {}).get("totalReplyCount", 0) or 0)
            if include_replies and total_reply_count > 0 and len(comments) < max_results:
                replies = fetch_replies(
                    youtube=youtube,
                    parent_comment_id=comment_id,
                    max_results=max_results - len(comments),
                    clean_emojis=clean_emojis,
                    lowercase_comments=lowercase_comments,
                )
                comments.extend(replies)

                if len(comments) >= max_results:
                    break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return pd.DataFrame(comments, columns=RESULT_COLUMNS)


def video_details_to_dataframe(video_details: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Titre": video_details.get("Titre", ""),
                "Nom de la chaine": video_details.get("Nom de la chaine", ""),
                "Date de publication": video_details.get("Date de publication", ""),
                "URL": video_details.get("URL", ""),
                "Video ID": video_details.get("Video ID", ""),
                "Vues": video_details.get("Vues", 0),
                "Likes": video_details.get("Likes", 0),
                "Commentaires exposes par YouTube": video_details.get("Commentaires exposes par YouTube", ""),
                "Commentaires desactives": video_details.get("Commentaires desactives", False),
            }
        ]
    )


def comments_to_txt_bytes(video_details: dict[str, object], df_comments: pd.DataFrame) -> bytes:
    lines = [
        f"Channel: {video_details.get('Nom de la chaine', '')}",
        (
            f"Title: {video_details.get('Titre', '')} - "
            f"{video_details.get('Date publication export', '')}"
        ),
        f"URL: {video_details.get('URL', '')}",
        "",
        "Comments:",
        "",
    ]

    if df_comments.empty:
        lines.append("Aucun commentaire recupere.")
    else:
        for row in df_comments.itertuples(index=False):
            prefix = "Reponse : " if row.Type == "Reponse" else ""
            lines.append(f"{prefix}{row.Auteur} - {row.Date}".strip())
            lines.append(row.Commentaire)
            lines.append("")

    return "\n".join(lines).encode("utf-8")


def dataframes_to_excel_bytes(video_df: pd.DataFrame, comments_df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        video_df.to_excel(writer, index=False, sheet_name="Video")
        comments_df.to_excel(writer, index=False, sheet_name="Commentaires")
    buffer.seek(0)
    return buffer.getvalue()


def load_help_markdown() -> str:
    try:
        return HELP_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Le fichier `aide.md` est introuvable pour cette application."


st.set_page_config(page_title="Extract Comments YouTube", layout="wide")

if "video_details" not in st.session_state:
    st.session_state.video_details = None
if "df_comments" not in st.session_state:
    st.session_state.df_comments = None
if "result_message" not in st.session_state:
    st.session_state.result_message = None
if "txt_export_name" not in st.session_state:
    st.session_state.txt_export_name = "youtube_comments.txt"
if "xlsx_export_name" not in st.session_state:
    st.session_state.xlsx_export_name = "youtube_comments.xlsx"

st.title("Extraction des commentaires YouTube")
st.caption(
    "Recuperez les commentaires d'une video YouTube ou YouTube Shorts, "
    "puis telechargez-les au format texte ou Excel."
)

with st.expander("Aide"):
    st.markdown(load_help_markdown())

st.markdown("### 1. Parametres")

api_key_input = st.text_input(
    "Cle API YouTube",
    value=DEFAULT_API_KEY,
    placeholder="Entrez votre cle API YouTube Data v3",
    type="password",
)
video_url_input = st.text_input(
    "URL de la video",
    placeholder="https://www.youtube.com/watch?v=... ou https://youtube.com/shorts/...",
)

options_col_1, options_col_2, options_col_3 = st.columns(3)

with options_col_1:
    max_comments = st.number_input(
        "Nombre maximum de commentaires",
        min_value=1,
        max_value=5000,
        value=100,
        step=50,
    )

with options_col_2:
    include_replies = st.checkbox("Inclure les reponses", value=False)
    lowercase_comments = st.checkbox("Mettre les commentaires en minuscules", value=True)

with options_col_3:
    clean_emojis = st.checkbox("Supprimer les emojis", value=True)

if st.button("Extraire les commentaires", type="primary"):
    st.session_state.video_details = None
    st.session_state.df_comments = None
    st.session_state.result_message = None

    if not api_key_input.strip() or not video_url_input.strip():
        st.error("Renseignez la cle API YouTube et l'URL de la video.")
    else:
        video_details = None
        try:
            with st.spinner("Extraction des commentaires en cours..."):
                video_id = extraire_video_id(video_url_input)
                youtube = build_youtube_client(api_key_input.strip())
                video_details = get_video_details(youtube, video_id, clean_emojis=clean_emojis)
                df_comments = fetch_comments(
                    youtube=youtube,
                    video_id=video_id,
                    max_results=int(max_comments),
                    include_replies=include_replies,
                    clean_emojis=clean_emojis,
                    lowercase_comments=lowercase_comments,
                )

            st.session_state.video_details = video_details
            st.session_state.df_comments = df_comments

            fragment = normaliser_fragment_nom_fichier(str(video_details.get("Titre") or video_id))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.txt_export_name = f"youtube_comments_{fragment}_{timestamp}.txt"
            st.session_state.xlsx_export_name = f"youtube_comments_{fragment}_{timestamp}.xlsx"

            if df_comments.empty:
                st.session_state.result_message = "Aucun commentaire recupere pour cette video."
        except CommentsDisabledError as exc:
            st.session_state.video_details = video_details
            st.session_state.df_comments = pd.DataFrame(columns=RESULT_COLUMNS)
            st.session_state.result_message = str(exc)

            fragment_source = ""
            if video_details:
                fragment_source = str(video_details.get("Titre") or video_details.get("Video ID") or "")
            fragment = normaliser_fragment_nom_fichier(fragment_source or "youtube_comments")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.txt_export_name = f"youtube_comments_{fragment}_{timestamp}.txt"
            st.session_state.xlsx_export_name = f"youtube_comments_{fragment}_{timestamp}.xlsx"
        except ValueError as exc:
            st.error(str(exc))
        except HttpError as exc:
            _, message = parse_api_error(exc)
            st.error(message)
        except Exception as exc:  # pragma: no cover - garde-fou Streamlit
            st.error(f"Erreur lors de l'extraction des commentaires : {exc}")

video_details = st.session_state.video_details
df_comments = st.session_state.df_comments
result_message = st.session_state.result_message

if video_details is not None:
    st.markdown("### 2. Informations video")

    meta_col_1, meta_col_2, meta_col_3 = st.columns(3)
    with meta_col_1:
        st.metric("Nom de la chaine", value=str(video_details.get("Nom de la chaine", "")) or "n/d")
    with meta_col_2:
        st.metric("Date de publication", value=str(video_details.get("Date de publication", "")) or "n/d")
    with meta_col_3:
        comments_count = video_details.get("Commentaires exposes par YouTube")
        st.metric(
            "Commentaires exposes",
            value="desactives" if comments_count is None else str(comments_count),
        )

    st.markdown(f"**Titre** : {video_details.get('Titre', '')}")
    st.markdown(f"**URL** : {video_details.get('URL', '')}")

    if result_message:
        st.warning(result_message)

    st.markdown("### 3. Resultats")

    if df_comments is not None and not df_comments.empty:
        st.success(f"{len(df_comments)} commentaire(s) recupere(s).")
        st.dataframe(df_comments, use_container_width=True)
    elif df_comments is not None:
        st.info("Aucun commentaire a afficher.")

    video_df = video_details_to_dataframe(video_details)
    comments_df = df_comments if df_comments is not None else pd.DataFrame(columns=RESULT_COLUMNS)
    export_col_1, export_col_2 = st.columns(2)

    with export_col_1:
        st.download_button(
            label="Telecharger le fichier texte",
            data=comments_to_txt_bytes(video_details, comments_df),
            file_name=st.session_state.txt_export_name,
            mime="text/plain",
        )

    with export_col_2:
        st.download_button(
            label="Telecharger le fichier Excel",
            data=dataframes_to_excel_bytes(video_df, comments_df),
            file_name=st.session_state.xlsx_export_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
