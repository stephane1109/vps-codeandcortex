from __future__ import annotations

import concurrent.futures
import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ticket_gate import enforce_streamlit_access, keep_ticket_alive

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - depend de l'image Docker finale
    WhisperModel = None


APP_NAME = "MP3 to Text"
DEFAULT_YOUTUBE_URL = "https://www.youtube.com/watch?v=WDQqDOXAUIM"
DEFAULT_LANGUAGE = (os.getenv("WHISPER_LANGUAGE_DEFAULT", "fr") or "fr").strip().lower()
DEFAULT_MODEL = "base"
DEFAULT_PROFILE = (os.getenv("WHISPER_PROFILE_DEFAULT", "faster-whisper") or "faster-whisper").strip().lower()
MODEL_OPTIONS = ["tiny", "base", "small", "medium"]
VISIBLE_MODEL_CHOICES = ["fast-whisper", "sm", "md"]
UPLOAD_EXTENSIONS = ["mp3", "wav", "m4a", "mp4", "mpeg", "mpga", "webm"]
WORKDIR = Path(os.getenv("APP_WORKDIR", "/tmp/mp3-to-text")).resolve()
WHISPER_CACHE_DIR = Path(os.getenv("WHISPER_CACHE_DIR", str(WORKDIR / "whisper-cache"))).resolve()
YOUTUBE_COOKIES_DIR = Path(os.getenv("YOUTUBE_COOKIES_DIR", str(WORKDIR / "youtube-cookies"))).resolve()
WHISPER_MODEL_ALIASES: dict[str, str] = {}
USER_AGENT_YOUTUBE_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
YOUTUBE_FORMAT_FALLBACKS: list[str | None] = [
    # Format progressif YouTube très fréquent : vidéo + audio dans un MP4.
    # Il est indispensable pour certaines vidéos qui n'exposent aucun bestaudio.
    "18",
    "22",
    "bestaudio[acodec!=none]/best[acodec!=none]/best",
    "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio[ext=mp4]/bestaudio/best",
    "best[height<=720][acodec!=none][vcodec!=none]/best[height<=480][acodec!=none][vcodec!=none]/best[height<=360][acodec!=none][vcodec!=none]",
    "best[ext=mp4]/best",
    "best[protocol^=http]/best",
    "best[acodec!=none][vcodec!=none]/best[acodec!=none]/best",
    "worst[acodec!=none]/worst/best",
    None,
]
LANGUAGE_OPTIONS = {
    "Auto-détection": "",
    "Français": "fr",
    "Anglais": "en",
    "Espagnol": "es",
    "Allemand": "de",
    "Italien": "it",
    "Portugais": "pt",
    "Arabe": "ar",
}
MODEL_PROFILES = {
    # #### PROFILS DE MODELES AFFICHES DANS L'APPLICATION
    # L'utilisateur voit explicitement ces trois choix dans l'interface.
    "faster-whisper": {
        "backend": "faster-whisper",
        "model_size": "base",
        "label": "fast-whisper",
        "description": "Profil rapide et léger, recommandé par défaut sur le VPS.",
    },
    "sm": {
        "backend": "faster-whisper",
        "model_size": "small",
        "label": "sm",
        "description": "Modèle small, meilleur compromis qualité/temps.",
    },
    "md": {
        "backend": "faster-whisper",
        "model_size": "medium",
        "label": "md",
        "description": "Modèle medium, plus lourd mais souvent plus précis.",
    },
}


class ApplicationError(RuntimeError):
    """Erreur métier à afficher proprement dans l'interface."""


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_filename_fragment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def create_run_directory() -> Path:
    ensure_directory(WORKDIR)
    run_dir = WORKDIR / f"run-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    return ensure_directory(run_dir)


def session_cookie_dir() -> Path:
    session_id = st.session_state.setdefault("session_id", uuid.uuid4().hex)
    return ensure_directory(YOUTUBE_COOKIES_DIR / session_id)


def persisted_youtube_cookies_path() -> Path:
    return session_cookie_dir() / "cookies.txt"


def youtube_cookie_expiration_diagnostic(cookies_path: Path) -> str:
    if not cookies_path.exists():
        return "Aucun cookies.txt mémorisé pour cette session."
    try:
        content = cookies_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Lecture cookies impossible : {exc}"
    if "youtube.com" not in content and ".youtube.com" not in content:
        return "Le cookies.txt ne contient aucune entrée YouTube détectée."

    now = int(time.time())
    expirations: list[int] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        columns = line.replace("#HttpOnly_", "", 1).split("\t")
        if len(columns) < 7:
            continue
        domain = columns[0].lower()
        if "youtube.com" not in domain and "google.com" not in domain:
            continue
        try:
            expires = int(columns[4])
        except ValueError:
            continue
        if expires > 0:
            expirations.append(expires)

    size = cookies_path.stat().st_size
    if size < 1024:
        return f"cookies.txt mémorisé ({size} octets), mais il semble très court : export possiblement incomplet."
    if not expirations:
        return f"cookies.txt mémorisé ({size} octets) ; cookies YouTube/Google détectés sans expiration exploitable."
    remaining = max(expirations) - now
    if remaining <= 0:
        return f"cookies.txt mémorisé ({size} octets), mais les expirations utiles semblent dépassées."
    if remaining < 3600:
        return f"cookies.txt mémorisé ({size} octets) ; attention, expiration utile dans environ {max(1, int(remaining / 60))} min."
    return f"cookies.txt mémorisé ({size} octets) ; expiration utile dans environ {int(remaining / 3600)} h."


def find_downloaded_mp3(run_dir: Path) -> Path:
    candidates = sorted(run_dir.glob("*.mp3"), key=lambda item: item.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    raise ApplicationError("Le téléchargement YouTube est terminé mais aucun fichier MP3 n'a été trouvé.")


def save_youtube_cookies(uploaded_cookies, run_dir: Path) -> Path | None:
    cookies_path = persisted_youtube_cookies_path()
    if uploaded_cookies is None:
        return cookies_path if cookies_path.exists() and cookies_path.stat().st_size > 0 else None
    cookies_path.write_bytes(uploaded_cookies.getbuffer())
    if not cookies_path.read_text(encoding="utf-8", errors="ignore").strip():
        raise ApplicationError("Le fichier cookies YouTube est vide.")
    return cookies_path


def _yt_dlp_base_options(output_template: str) -> dict:
    return {
        "noplaylist": True,
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 1,
        "sleep_interval_requests": 1,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "socket_timeout": 30,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "restrictfilenames": True,
        "trim_file_name": 100,
        "http_headers": {
            "User-Agent": USER_AGENT_YOUTUBE_DEFAULT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.youtube.com/",
        },
        # YouTube change souvent les clients autorisés. On donne plusieurs
        # clients à yt-dlp pour maximiser les chances de récupérer les formats.
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "mweb", "web"]}},
    }


def _format_number(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _youtube_format_score(fmt: dict) -> float:
    ext = str(fmt.get("ext") or "").lower()
    protocol = str(fmt.get("protocol") or "").lower()
    vcodec = str(fmt.get("vcodec") or "none").lower()
    acodec = str(fmt.get("acodec") or "none").lower()
    audio_only_bonus = 600 if vcodec == "none" and acodec != "none" else 0
    ext_bonus = {
        "m4a": 500,
        "mp4": 450,
        "webm": 360,
        "opus": 340,
        "mp3": 320,
        "mkv": 180,
    }.get(ext, 80)
    protocol_penalty = -120 if "m3u8" in protocol else 0
    abr = _format_number(fmt.get("abr") or fmt.get("tbr"), 0)
    filesize = _format_number(fmt.get("filesize") or fmt.get("filesize_approx"), 0)
    return audio_only_bonus + ext_bonus + abr + min(filesize / 1_000_000, 100) + protocol_penalty


def _youtube_format_is_usable(fmt: dict) -> bool:
    format_id = str(fmt.get("format_id") or "").strip().lower()
    ext = str(fmt.get("ext") or "").lower()
    protocol = str(fmt.get("protocol") or "").lower()
    vcodec = str(fmt.get("vcodec") or "none").lower()
    acodec = str(fmt.get("acodec") or "none").lower()
    if not format_id:
        return False
    if ext in {"mhtml", "html", "json"}:
        return False
    if "storyboard" in format_id or "mhtml" in protocol:
        return False
    return acodec != "none" or vcodec != "none"


def _youtube_audio_format_candidates(url: str, base_options: dict) -> list[str]:
    probe_options = dict(base_options)
    probe_options.pop("format", None)
    probe_options.pop("postprocessors", None)
    probe_options.pop("check_formats", None)
    probe_options["skip_download"] = True

    try:
        with YoutubeDL(probe_options) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
    except Exception:
        return []

    formats = info.get("formats") or []
    audio_formats = []
    for fmt in formats:
        format_id = str(fmt.get("format_id") or "").strip()
        acodec = str(fmt.get("acodec") or "none").lower()
        if not format_id or acodec == "none" or not _youtube_format_is_usable(fmt):
            continue
        audio_formats.append(fmt)

    audio_formats.sort(key=_youtube_format_score, reverse=True)
    candidates = []
    for fmt in audio_formats:
        format_id = str(fmt.get("format_id") or "").strip()
        if format_id and format_id not in candidates:
            candidates.append(format_id)
    return candidates


def telecharger_audio_youtube(url: str, run_dir: Path, cookies_path: Path | None = None) -> Path:
    if not url.strip():
        raise ApplicationError("Veuillez entrer une URL YouTube.")

    output_template = str(run_dir / "%(title).120s.%(ext)s")
    options_ydl_base = _yt_dlp_base_options(output_template)
    if cookies_path is not None:
        options_ydl_base["cookiefile"] = str(cookies_path)

    last_error: Exception | None = None
    format_candidates = _youtube_audio_format_candidates(url, options_ydl_base)
    format_candidates.extend(YOUTUBE_FORMAT_FALLBACKS)
    attempted_formats: list[str] = []

    already_tried: set[str] = set()
    for format_choice in format_candidates:
        marker = "__default__" if format_choice is None else str(format_choice)
        if marker in already_tried:
            continue
        already_tried.add(marker)
        attempted_formats.append(marker)

        options_ydl = dict(options_ydl_base)
        if format_choice is not None:
            options_ydl["format"] = format_choice
        try:
            with YoutubeDL(options_ydl) as ydl:
                ydl.extract_info(url.strip(), download=True)
            return find_downloaded_mp3(run_dir)
        except DownloadError as exc:
            last_error = exc
            message = str(exc).lower()
            if "requested format is not available" in message:
                continue
            raise ApplicationError(f"Erreur lors du téléchargement YouTube : {exc}") from exc
        except Exception as exc:  # pragma: no cover - dépend du réseau/runtime
            last_error = exc
            raise ApplicationError(f"Téléchargement YouTube impossible : {exc}") from exc

    raise ApplicationError(
        "Erreur lors du téléchargement YouTube : aucun format audio/vidéo compatible n'a été trouvé. "
        f"{len(attempted_formats)} stratégie(s) tentée(s) : {', '.join(attempted_formats)}. "
        f"Dernière erreur yt-dlp : {last_error}"
    )


def save_uploaded_audio(uploaded_file, run_dir: Path) -> Path:
    if uploaded_file is None:
        raise ApplicationError("Veuillez importer un fichier audio.")

    suffix = Path(uploaded_file.name).suffix.lower()
    if not suffix:
        suffix = ".mp3"

    filename = normalize_filename_fragment(Path(uploaded_file.name).stem, "audio") + suffix
    audio_path = run_dir / filename
    audio_path.write_bytes(uploaded_file.getbuffer())
    return audio_path


@st.cache_resource(show_spinner=False)
def load_whisper_model(model_size: str):
    if WhisperModel is None:
        raise ApplicationError("Le backend faster-whisper n'est pas disponible dans l'application.")
    ensure_directory(WHISPER_CACHE_DIR)
    if model_size not in MODEL_OPTIONS:
        raise ApplicationError(
            f"Le modèle '{model_size}' n'est pas autorisé sur ce VPS. Choisissez tiny, base, small ou medium."
        )
    resolved_model_size = WHISPER_MODEL_ALIASES.get(model_size, model_size)
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    return WhisperModel(
        resolved_model_size,
        device="cpu",
        compute_type=compute_type,
        download_root=str(WHISPER_CACHE_DIR),
    )


def transcrire_audio(audio_path: Path, model_size: str, language_code: str) -> str:
    if not audio_path.exists():
        raise ApplicationError(f"Fichier audio introuvable : {audio_path}")

    model = load_whisper_model(model_size)
    language = (language_code or "").strip() or None

    try:
        segments, _info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join((segment.text or "").strip() for segment in segments).strip()
    except Exception as exc:  # pragma: no cover - depend du backend Whisper
        raise ApplicationError(f"Erreur lors de la transcription Whisper : {exc}") from exc

    if not text:
        raise ApplicationError("Whisper n'a renvoyé aucun texte exploitable.")
    return text


def normalize_model_choice(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "fast-whisper":
        return "faster-whisper"
    if normalized == "sms":
        return "sm"
    return normalized


def resolve_selected_model(selected_choice: str) -> tuple[str, str, str]:
    normalized_key = normalize_model_choice(selected_choice or DEFAULT_PROFILE)
    if normalized_key in MODEL_PROFILES:
        profile = MODEL_PROFILES[normalized_key]
        return (
            str(profile["backend"]),
            str(profile["model_size"]),
            str(profile["label"]),
        )
    if normalized_key in MODEL_OPTIONS:
        return "faster-whisper", normalized_key, f"avance ({normalized_key})"
    return resolve_selected_model("fast-whisper")


def default_language_label() -> str:
    for label, code in LANGUAGE_OPTIONS.items():
        if code == DEFAULT_LANGUAGE:
            return label
    return "Auto-détection"


def save_transcription(transcription_text: str, audio_path: Path) -> Path:
    output_path = audio_path.with_suffix(".txt")
    output_path.write_text(transcription_text, encoding="utf-8")
    return output_path


def run_transcription_with_progress(audio_path: Path, model_size: str, language_code: str, debug_mode: bool) -> str:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(transcrire_audio, audio_path, model_size, language_code)
        progress_bar = st.progress(0)
        progress_text = st.empty()
        progress = 0
        heartbeat_tick = 0

        while not future.done():
            time.sleep(0.2)
            progress = min(95, progress + 1)
            progress_bar.progress(progress)
            heartbeat_tick += 1
            if heartbeat_tick % 20 == 0:
                # Si le traitement devient long, augmente APP_TICKET_TTL_SECONDS
                # dans Coolify ou garde ce heartbeat actif pour ne pas perdre le ticket.
                keep_ticket_alive("mp3_to_text", APP_NAME)
            if debug_mode:
                progress_text.text(f"Progression estimée : {progress}%")

        transcription_text = future.result()
        progress_bar.progress(100)
        progress_text.text("Progression estimée : 100%")
        return transcription_text


def build_sidebar_notes() -> None:
    return None


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    st.markdown(
        '<link rel="icon" href="data:,">',
        unsafe_allow_html=True,
    )
    # #### VARIABLES D'ENVIRONNEMENT - CONTRÔLE D'ACCÈS REDIS POUR LE VPS
    # Variables à modifier dans Coolify si besoin :
    # - REDIS_URL
    # - APP_TICKET_MAX_ACTIVE (laisser 1 pour une application lourde)
    # - APP_TICKET_COST
    # - CAPACITE_SERVEUR
    # - APP_TICKET_TTL_SECONDS
    enforce_streamlit_access("mp3_to_text", APP_NAME)
    st.title("Speech to text avec Whisper - OpenAI")
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.markdown(
        """
        Cette version VPS permet de :

        - télécharger l'audio d'une vidéo YouTube
        - importer un fichier audio local
        - transcrire automatiquement en texte puis télécharger le résultat
        """
    )
    build_sidebar_notes()

    debug_mode = st.checkbox("Mode diagnostic", value=False)
    source = st.radio("Choisissez la source de l'audio", options=["URL YouTube", "Fichier audio"])

    youtube_url = ""
    uploaded_audio = None
    uploaded_cookies = None

    if source == "URL YouTube":
        youtube_url = st.text_input("Entrez l'URL de la vidéo YouTube", value=DEFAULT_YOUTUBE_URL)
        uploaded_cookies = st.file_uploader(
            "Importer un fichier cookies.txt YouTube si YouTube bloque le téléchargement",
            type=["txt"],
            help="Exportez les cookies YouTube avec l'extension cookies.txt depuis Chrome ou Firefox.",
        )
        st.caption(youtube_cookie_expiration_diagnostic(persisted_youtube_cookies_path()))
    else:
        uploaded_audio = st.file_uploader(
            "Importer un fichier audio",
            type=UPLOAD_EXTENSIONS,
            help="Formats conseillés : mp3, wav, m4a, mp4, webm.",
        )

    default_choice = MODEL_PROFILES.get(normalize_model_choice(DEFAULT_PROFILE), MODEL_PROFILES["faster-whisper"])["label"]
    if default_choice not in VISIBLE_MODEL_CHOICES:
        default_choice = "fast-whisper"
    selected_model_choice = st.radio(
        "Modèle de transcription",
        options=VISIBLE_MODEL_CHOICES,
        index=VISIBLE_MODEL_CHOICES.index(default_choice),
        horizontal=True,
        help="fast-whisper charge le profil rapide par défaut, sm charge small, md charge medium.",
    )
    backend_name, model_size, resolved_profile = resolve_selected_model(selected_model_choice)
    selected_language_label = st.selectbox(
        "Langue de transcription",
        options=list(LANGUAGE_OPTIONS.keys()),
        index=list(LANGUAGE_OPTIONS.keys()).index(default_language_label()),
        help=(
            "Le modèle Whisper est multilingue. Ce choix force la langue de transcription ; "
            "Auto-détection laisse Whisper détecter la langue."
        ),
    )
    language_code = LANGUAGE_OPTIONS[selected_language_label]

    st.caption(
        f"Profil actif : `{resolved_profile}` · Backend : `{backend_name}` · "
        f"Modèle chargé : `{model_size}` · Langue : `{selected_language_label}`"
    )

    if st.button("Lancer la transcription", type="primary"):
        run_dir = create_run_directory()
        audio_path: Path | None = None

        try:
            if source == "URL YouTube":
                with st.spinner("Téléchargement de l'audio depuis YouTube..."):
                    cookies_path = save_youtube_cookies(uploaded_cookies, run_dir)
                    audio_path = telecharger_audio_youtube(youtube_url, run_dir, cookies_path)
            else:
                audio_path = save_uploaded_audio(uploaded_audio, run_dir)

            st.success(f"Audio prêt : {audio_path.name}")

            with st.spinner("Transcription en cours..."):
                transcription_text = run_transcription_with_progress(audio_path, model_size, language_code, debug_mode)

            transcription_path = save_transcription(transcription_text, audio_path)
            st.success(f"Transcription enregistrée : {transcription_path.name}")

            if debug_mode:
                st.info(f"Dossier de travail : {run_dir}")
                st.code(
                    "\n".join(
                        [
                            f"Audio : {audio_path}",
                            f"Profil résolu : {resolved_profile}",
                            f"Backend : {backend_name}",
                            f"Transcription : {transcription_path}",
                            f"Modèle : {model_size}",
                            f"Langue : {language_code or 'auto'}",
                            f"Cache Whisper : {WHISPER_CACHE_DIR}",
                        ]
                    )
                )

            st.subheader("Transcription")
            st.text_area("Texte de la transcription", transcription_text, height=320)
            st.download_button(
                "Télécharger la transcription",
                data=transcription_text,
                file_name=transcription_path.name,
                mime="text/plain",
            )
        except ApplicationError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover - garde-fou Streamlit
            st.error(f"Erreur inattendue : {exc}")


if __name__ == "__main__":
    main()
