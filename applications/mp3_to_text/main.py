from __future__ import annotations

import concurrent.futures
import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st
import whisper
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_NAME = "MP3 to Text"
DEFAULT_YOUTUBE_URL = "https://www.youtube.com/watch?v=WDQqDOXAUIM"
DEFAULT_LANGUAGE = "fr"
DEFAULT_MODEL = "base"
MODEL_OPTIONS = ["tiny", "base", "small", "medium", "large"]
UPLOAD_EXTENSIONS = ["mp3", "wav", "m4a", "mp4", "mpeg", "mpga", "webm"]
WORKDIR = Path(os.getenv("APP_WORKDIR", "/tmp/mp3-to-text")).resolve()
WHISPER_CACHE_DIR = Path(os.getenv("WHISPER_CACHE_DIR", str(WORKDIR / "whisper-cache"))).resolve()


class ApplicationError(RuntimeError):
    """Erreur metier a afficher proprement dans l'interface."""


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
    raise ApplicationError("Le telechargement YouTube est termine mais aucun fichier MP3 n'a ete trouve.")


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
        raise ApplicationError(f"Erreur lors du telechargement YouTube : {exc}") from exc
    except Exception as exc:  # pragma: no cover - depend du reseau/runtime
        raise ApplicationError(f"Telechargement YouTube impossible : {exc}") from exc

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
    ensure_directory(WHISPER_CACHE_DIR)
    return whisper.load_model(model_size, download_root=str(WHISPER_CACHE_DIR))


def transcrire_audio(audio_path: Path, model_size: str, language_code: str) -> str:
    if not audio_path.exists():
        raise ApplicationError(f"Fichier audio introuvable : {audio_path}")

    model = load_whisper_model(model_size)
    language = (language_code or "").strip() or None

    try:
        result = model.transcribe(str(audio_path), language=language, fp16=False)
    except Exception as exc:  # pragma: no cover - depend du backend Whisper
        raise ApplicationError(f"Erreur lors de la transcription Whisper : {exc}") from exc

    text = str(result.get("text") or "").strip()
    if not text:
        raise ApplicationError("Whisper n'a renvoye aucun texte exploitable.")
    return text


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
                progress_text.text(f"Progression estimee : {progress}%")

        transcription_text = future.result()
        progress_bar.progress(100)
        progress_text.text("Progression estimee : 100%")
        return transcription_text


def build_sidebar_notes() -> None:
    with st.sidebar:
        st.header("Execution VPS")
        st.caption("Le modele Whisper est telecharge au premier usage puis reutilise depuis le cache du conteneur.")
        st.markdown(
            "\n".join(
                [
                    "- Source audio : YouTube ou fichier local",
                    "- Modeles : tiny a large",
                    "- Export final : transcription `.txt`",
                    "- Dossier temporaire : `APP_WORKDIR`",
                ]
            )
        )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🎙️", layout="centered")
    # #### VARIABLES D'ENVIRONNEMENT - CONTROLE D'ACCES REDIS POUR LE VPS
    # Variables a modifier dans Coolify si besoin :
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

        - telecharger l'audio d'une video YouTube
        - importer un fichier audio local
        - choisir la taille du modele Whisper
        - transcrire automatiquement en texte puis telecharger le resultat
        """
    )
    build_sidebar_notes()

    debug_mode = st.checkbox("Mode debug", value=False)
    source = st.radio("Choisissez la source de l'audio", options=["URL YouTube", "Fichier audio"])

    youtube_url = ""
    uploaded_audio = None

    if source == "URL YouTube":
        youtube_url = st.text_input("Entrez l'URL de la video YouTube", value=DEFAULT_YOUTUBE_URL)
    else:
        uploaded_audio = st.file_uploader(
            "Importer un fichier audio",
            type=UPLOAD_EXTENSIONS,
            help="Formats conseilles : mp3, wav, m4a, mp4, webm.",
        )

    model_size = st.selectbox("Choisissez la taille du modele Whisper", options=MODEL_OPTIONS, index=1)
    language_code = st.text_input(
        "Code langue pour la transcription",
        value=DEFAULT_LANGUAGE,
        help="Exemple : fr, en, es. Laissez vide pour laisser Whisper detecter la langue.",
    )

    if st.button("Lancer la transcription", type="primary"):
        run_dir = create_run_directory()
        audio_path: Path | None = None

        try:
            if source == "URL YouTube":
                with st.spinner("Telechargement de l'audio depuis YouTube..."):
                    audio_path = telecharger_audio_youtube(youtube_url, run_dir)
            else:
                audio_path = save_uploaded_audio(uploaded_audio, run_dir)

            st.success(f"Audio pret : {audio_path.name}")

            with st.spinner("Transcription en cours..."):
                transcription_text = run_transcription_with_progress(audio_path, model_size, language_code, debug_mode)

            transcription_path = save_transcription(transcription_text, audio_path)
            st.success(f"Transcription enregistree : {transcription_path.name}")

            if debug_mode:
                st.info(f"Dossier de travail : {run_dir}")
                st.code(
                    "\n".join(
                        [
                            f"Audio : {audio_path}",
                            f"Transcription : {transcription_path}",
                            f"Modele : {model_size}",
                            f"Langue : {language_code or 'auto'}",
                            f"Cache Whisper : {WHISPER_CACHE_DIR}",
                        ]
                    )
                )

            st.subheader("Transcription")
            st.text_area("Texte de la transcription", transcription_text, height=320)
            st.download_button(
                "Telecharger la transcription",
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
