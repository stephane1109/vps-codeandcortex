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
DEFAULT_LANGUAGE = "fr"
DEFAULT_MODEL = "base"
DEFAULT_PROFILE = (os.getenv("WHISPER_PROFILE_DEFAULT", "faster-whisper") or "faster-whisper").strip().lower()
MODEL_OPTIONS = ["tiny", "base", "small", "medium"]
VISIBLE_MODEL_CHOICES = ["fast-whisper", "sm", "md", "tiny", "base", "small", "medium"]
UPLOAD_EXTENSIONS = ["mp3", "wav", "m4a", "mp4", "mpeg", "mpga", "webm"]
WORKDIR = Path(os.getenv("APP_WORKDIR", "/tmp/mp3-to-text")).resolve()
WHISPER_CACHE_DIR = Path(os.getenv("WHISPER_CACHE_DIR", str(WORKDIR / "whisper-cache"))).resolve()
WHISPER_MODEL_ALIASES: dict[str, str] = {}
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


def find_downloaded_mp3(run_dir: Path) -> Path:
    candidates = sorted(run_dir.glob("*.mp3"), key=lambda item: item.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    raise ApplicationError("Le téléchargement YouTube est terminé mais aucun fichier MP3 n'a été trouvé.")


def telecharger_audio_youtube(url: str, run_dir: Path) -> Path:
    if not url.strip():
        raise ApplicationError("Veuillez entrer une URL YouTube.")

    output_template = str(run_dir / "%(title).120s.%(ext)s")
    options_ydl = {
        "format": "bestaudio/best",
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
    }

    try:
        with YoutubeDL(options_ydl) as ydl:
            ydl.extract_info(url.strip(), download=True)
    except DownloadError as exc:
        raise ApplicationError(f"Erreur lors du téléchargement YouTube : {exc}") from exc
    except Exception as exc:  # pragma: no cover - dépend du réseau/runtime
        raise ApplicationError(f"Téléchargement YouTube impossible : {exc}") from exc

    return find_downloaded_mp3(run_dir)


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
    with st.sidebar:
        st.header("Exécution VPS")
        st.caption("Le modèle choisi est téléchargé au premier usage puis réutilisé depuis le cache du conteneur.")
        st.markdown(
            "\n".join(
                [
                    "- Source audio : YouTube ou fichier local",
                    "- Modèles disponibles : fast-whisper, sm, md, tiny, base, small, medium",
                    "- Backend Docker : Whisper CPU compatible VPS",
                    "- Export final : transcription `.txt`",
                    "- Dossier temporaire : `APP_WORKDIR`",
                ]
            )
        )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="centered")
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
    st.caption("version modifié le 13-07-2026")
    st.markdown("<hr style='margin:0.35rem 0 1.2rem; border:0; border-top:1px solid rgba(15,23,42,0.12);'>", unsafe_allow_html=True)
    build_sidebar_notes()

    debug_mode = st.checkbox("Mode diagnostic", value=False)
    source = st.radio("Choisissez la source de l'audio", options=["URL YouTube", "Fichier audio"])

    youtube_url = ""
    uploaded_audio = None

    if source == "URL YouTube":
        youtube_url = st.text_input("Entrez l'URL de la vidéo YouTube", value=DEFAULT_YOUTUBE_URL)
    else:
        uploaded_audio = st.file_uploader(
            "Importer un fichier audio",
            type=UPLOAD_EXTENSIONS,
            help="Formats conseillés : mp3, wav, m4a, mp4, webm.",
        )

    default_choice = normalize_model_choice(DEFAULT_PROFILE)
    if default_choice == "faster-whisper":
        default_choice = "fast-whisper"
    if default_choice not in VISIBLE_MODEL_CHOICES:
        default_choice = DEFAULT_MODEL if DEFAULT_MODEL in VISIBLE_MODEL_CHOICES else "fast-whisper"

    selected_model_choice = st.selectbox(
        "Choisissez le modèle Whisper",
        options=VISIBLE_MODEL_CHOICES,
        index=VISIBLE_MODEL_CHOICES.index(default_choice),
        help="Mode unique : fast-whisper, sm, md, tiny, base, small ou medium.",
    )

    backend_name, model_size, resolved_profile = resolve_selected_model(selected_model_choice)
    language_code = st.text_input(
        "Code langue pour la transcription",
        value=DEFAULT_LANGUAGE,
        help="Exemple : fr, en, es. Laissez vide pour laisser Whisper détecter la langue.",
    )

    st.caption(f"Profil actif : `{resolved_profile}` · Backend : `{backend_name}` · Modèle chargé : `{model_size}`")

    if st.button("Lancer la transcription", type="primary"):
        run_dir = create_run_directory()
        audio_path: Path | None = None

        try:
            if source == "URL YouTube":
                with st.spinner("Téléchargement de l'audio depuis YouTube..."):
                    audio_path = telecharger_audio_youtube(youtube_url, run_dir)
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
                            f"Choix de l'interface : {selected_model_choice}",
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
