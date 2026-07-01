######################
# www.codeandcortex.fr
######################

from __future__ import annotations

import os
import re
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

import altair as alt
import pandas as pd
from yt_dlp import YoutubeDL


# #### VARIABLES D'ENVIRONNEMENT VPS
# - APP_DATA_DIR : racine de stockage serveur pour les exports de l'application
# - WHISPER_MODEL_NAME : modele Whisper charge dans le conteneur (small par defaut)
APP_STORAGE_ROOT = Path(os.getenv("APP_DATA_DIR", "/data/app")).resolve()
WHISPER_MODEL_NAME = (os.getenv("WHISPER_MODEL_NAME", "small") or "small").strip() or "small"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Fonction utilitaire : formatage d'un timestamp en HH:MM:SS
# =============================================================================
def format_timestamp(seconds: float) -> str:
    """Convertit un temps en secondes en format HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# =============================================================================
# Fonction de nettoyage du nom de fichier
# =============================================================================
def sanitize_filename(filename: str) -> str:
    """
    Nettoie le nom de fichier en retirant accents, espaces et caractères non autorisés.
    """
    nfkd_form = unicodedata.normalize("NFKD", filename)
    ascii_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace(" ", "_")
    ascii_text = re.sub(r"[^\w\-_.]", "", ascii_text)
    return ascii_text


def sanitize_directory_name(value: str, fallback: str = "analyse-debit-parole") -> str:
    cleaned = sanitize_filename((value or "").strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def resolve_storage_directory(repertoire: str) -> Path:
    """
    Convertit le nom saisi dans l'interface en dossier reel sur le serveur VPS.

    L'utilisateur conserve l'option "repertoire de stockage", mais l'ecriture
    est volontairement canalisee sous APP_DATA_DIR pour eviter toute ecriture
    hors de l'espace prevu pour l'application.
    """
    output_dir = APP_STORAGE_ROOT / sanitize_directory_name(repertoire)
    return ensure_directory(output_dir)


# =============================================================================
# Extraction d'un sous-clip vidéo avec ré-encodage (vidéo et audio)
# =============================================================================
def extract_subclip_custom(input_path: str | Path, t1: float, t2: float, output_path: str | Path) -> None:
    """
    Extrait un sous-clip de la vidéo entre t1 et t2 (en secondes) en ré-encodant la vidéo et l'audio.
    Cela garantit la présence d'une piste audio.
    """
    commande = [
        "ffmpeg",
        "-y",
        "-i",
        os.fspath(input_path),
        "-ss",
        str(t1),
        "-to",
        str(t2),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        os.fspath(output_path),
    ]
    result = subprocess.run(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        error_message = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"Erreur lors de l'extraction du sous-clip : {error_message}")


# =============================================================================
# Téléchargement de la vidéo YouTube et renommage
# =============================================================================
def telecharger_video(video_url: str, repertoire: str | Path) -> Path:
    """
    Télécharge la vidéo YouTube via yt-dlp et la sauvegarde dans le répertoire spécifié
    avec un nom basé sur le titre (après nettoyage).
    """
    output_dir = ensure_directory(Path(repertoire))
    options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "quiet": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)
        original_filename = Path(ydl.prepare_filename(info))
        sanitized_title = sanitize_filename(info.get("title", "video"))
        extension = original_filename.suffix or ".mp4"
        sanitized_filename = output_dir / f"{sanitized_title}{extension}"
        if original_filename != sanitized_filename and original_filename.exists():
            original_filename.rename(sanitized_filename)
        return sanitized_filename


@lru_cache(maxsize=2)
def load_whisper_model(model_name: str):
    try:
        import whisper
    except ImportError as exc:
        raise ImportError("Installez 'openai-whisper' avec pip install -U openai-whisper") from exc
    return whisper.load_model(model_name)


def transcrire_clip_whisper(clip_path: Path) -> dict:
    model = load_whisper_model(WHISPER_MODEL_NAME)
    return model.transcribe(os.fspath(clip_path), language="fr")


# =============================================================================
# Transcription par Whisper (mode "whisper")
# =============================================================================
def obtenir_transcription_whisper(video_path: str | Path, start_time: float, end_time: float, repertoire: str | Path):
    """
    Découpe le clip vidéo entre start_time et end_time via extract_subclip_custom et le transcrit avec Whisper.

    Si Whisper retourne des segments internes (resultat['segments'] non vide), on retourne ces segments.
    Sinon, on renvoie un segment global couvrant l'intervalle entier.
    """
    video_path = Path(video_path)
    clip_path = video_path.with_name(f"{video_path.stem}_{int(start_time)}_{int(end_time)}{video_path.suffix}")
    extract_subclip_custom(video_path, start_time, end_time, clip_path)
    try:
        result = transcrire_clip_whisper(clip_path)
        segments = result.get("segments", [])
        if segments:
            return segments
        full_text = result.get("text", "").strip()
        return [{"start": start_time, "end": end_time, "text": full_text}]
    finally:
        try:
            clip_path.unlink(missing_ok=True)
        except OSError:
            pass


# =============================================================================
# Transcription par segmentation ponctuation (mode "ponctuation")
# =============================================================================
def obtenir_transcription_ponctuation(video_path: str | Path, start_time: float, end_time: float, repertoire: str | Path):
    """
    Réalise la transcription globale du clip vidéo entre start_time et end_time avec Whisper,
    découpe le texte par ponctuation en exigeant que la ponctuation soit suivie d'un espace et d'une majuscule,
    répartit uniformément les timestamps sur l'intervalle et filtre les doublons consécutifs.
    Renvoie une liste de segments (dictionnaires) avec 'start', 'end' et 'text'.
    """
    video_path = Path(video_path)
    clip_path = video_path.with_name(f"{video_path.stem}_{int(start_time)}_{int(end_time)}{video_path.suffix}")
    extract_subclip_custom(video_path, start_time, end_time, clip_path)
    try:
        result = transcrire_clip_whisper(clip_path)
        full_text = result.get("text", "").strip()
    finally:
        try:
            clip_path.unlink(missing_ok=True)
        except OSError:
            pass

    phrases = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý])", full_text)
    filtered_phrases = []
    for phrase in phrases:
        phrase = phrase.strip()
        if phrase and (not filtered_phrases or phrase != filtered_phrases[-1]):
            filtered_phrases.append(phrase)

    segments = []
    n = len(filtered_phrases)
    if n == 0:
        segments = [{"start": start_time, "end": end_time, "text": full_text}]
    else:
        total_duration = end_time - start_time
        interval = total_duration / n
        for i, phrase in enumerate(filtered_phrases):
            seg_start = start_time + i * interval
            seg_end = seg_start + interval
            segments.append({"start": seg_start, "end": seg_end, "text": phrase})
    return segments


# =============================================================================
# Calcul du débit de parole par segment
# =============================================================================
def calculer_debit(transcript_segments):
    """
    Calcule le débit (mots par minute) pour chaque segment.
    """
    debits = []
    for segment in transcript_segments:
        debut = float(segment["start"])
        fin = float(segment.get("end", debut))
        texte = segment["text"]
        nb_mots = len(texte.split())
        duree = fin - debut if fin - debut > 0 else 1
        debit = (nb_mots / duree) * 60
        debits.append(
            {
                "start": debut,
                "end": fin,
                "nb_mots": nb_mots,
                "duree": round(duree, 2),
                "debit_mpm": round(debit, 2),
            }
        )
    return debits


# =============================================================================
# Calcul du débit global moyen
# =============================================================================
def calculer_debit_global(transcript_segments):
    """
    Calcule le débit global moyen (mots par minute) sur tous les segments.
    """
    total_mots = sum(len(seg["text"].split()) for seg in transcript_segments)
    total_duree = sum(float(seg.get("end", seg["start"])) - float(seg["start"]) for seg in transcript_segments)
    debit_global = (total_mots / total_duree * 60) if total_duree > 0 else 0
    return debit_global


# =============================================================================
# Export de la DataFrame en CSV
# =============================================================================
def exporter_dataframe(df: pd.DataFrame, repertoire: str | Path, nom_fichier: str = "segments.csv") -> str:
    output_dir = ensure_directory(Path(repertoire))
    chemin = output_dir / nom_fichier
    df.to_csv(chemin, index=False)
    return str(chemin)


# =============================================================================
# Export d'un graphique Altair en HTML
# =============================================================================
def exporter_graphique_html(chart: alt.Chart, repertoire: str | Path, nom_fichier: str = "graphique.html") -> str:
    output_dir = ensure_directory(Path(repertoire))
    chemin = output_dir / nom_fichier
    chart.save(str(chemin))
    return str(chemin)


# =============================================================================
# Export d'un graphique Altair en PNG
# =============================================================================
def exporter_graphique_png(chart: alt.Chart, repertoire: str | Path, nom_fichier: str = "graphique.png") -> str:
    """
    Exporte un graphique Altair en PNG.
    Nécessite 'vl-convert-python' (pip install vl-convert-python).
    """
    output_dir = ensure_directory(Path(repertoire))
    chemin = output_dir / nom_fichier
    chart.save(str(chemin), scale_factor=2.0)
    return str(chemin)


# =============================================================================
# Génération du rapport texte avec timestamps formatés
# =============================================================================
def generer_export_texte(transcript_segments, debit_global):
    """
    Génère un rapport texte détaillé pour chaque segment, avec timestamps en HH:MM:SS.
    """
    lignes = []
    for i, seg in enumerate(transcript_segments, start=1):
        debut = float(seg["start"])
        fin = float(seg.get("end", debut))
        texte = seg["text"].strip()
        nb_mots = len(texte.split())
        duree = fin - debut if fin - debut > 0 else 1
        debit = (nb_mots / duree) * 60
        lignes.append(
            f"Segment {i}: {format_timestamp(debut)} ({debut:.2f}s) à {format_timestamp(fin)} ({fin:.2f}s), {nb_mots} mots, débit = {debit:.2f} mots/min"
        )
        lignes.append("Transcription:")
        phrases = re.split(r"(?<=[.!?])\s+", texte)
        for phrase in phrases:
            if phrase:
                lignes.append(f"  - {phrase}")
        lignes.append("")
    lignes.append(f"Débit global moyen = {debit_global:.2f} mots/min")
    return "\n".join(lignes)


# =============================================================================
# Export du rapport texte dans un fichier
# =============================================================================
def exporter_rapport(export_text: str, repertoire: str | Path, nom_fichier: str = "rapport_transcription.txt") -> str:
    output_dir = ensure_directory(Path(repertoire))
    chemin = output_dir / nom_fichier
    chemin.write_text(export_text, encoding="utf-8")
    return str(chemin)


# =============================================================================
# Fonction principale d'analyse du débit de parole
# =============================================================================
def analyser_debit(video_url, start_time, end_time, repertoire, segmentation_mode="whisper"):
    """
    Analyse complète du débit de parole pour une vidéo YouTube en utilisant Whisper.

    Modes disponibles :
      - "whisper": segmentation automatique par Whisper (utilise les segments internes détectés).
      - "ponctuation": découpage de la transcription globale par ponctuation avec répartition des timestamps.

    Renvoie :
      - df_debit : DataFrame des segments.
      - chart_barres : Graphique en barres (avec ligne rouge pour la moyenne).
      - chart_combine : Graphique en ligne combiné (courbe + ligne du débit global).
      - export_text : Rapport texte détaillé.
      - export_fichier : Chemin du rapport texte exporté.
      - df_csv : Chemin du CSV exporté.
      - graph_barres_html : Chemin du graphique en barres HTML.
      - graph_barres_png : Chemin du graphique en barres PNG.
      - graph_combine_html : Chemin du graphique combiné HTML.
      - graph_combine_png : Chemin du graphique combiné PNG.
      - dialogue_file : Chemin du fichier "dialogues.txt" (pour le mode ponctuation, sinon vide).
      - transcript_segments : Segments réellement analysés.
      - output_dir : Répertoire serveur dans lequel les exports sont stockés.
    """
    output_dir = resolve_storage_directory(repertoire)
    video_path = telecharger_video(video_url, output_dir)
    dialogue_file = ""

    if segmentation_mode == "whisper":
        transcript_segments = obtenir_transcription_whisper(video_path, start_time, end_time, output_dir)
        segments_plot = transcript_segments
    elif segmentation_mode == "ponctuation":
        transcript_segments = obtenir_transcription_ponctuation(video_path, start_time, end_time, output_dir)
        segments_plot = transcript_segments
        whisper_segments = obtenir_transcription_whisper(video_path, start_time, end_time, output_dir)
        global_transcript = " ".join(seg.get("text", "").strip() for seg in whisper_segments if seg.get("text", "").strip())
        dialogue_file = exporter_rapport(global_transcript, output_dir, nom_fichier="dialogues.txt")
    else:
        raise ValueError("Mode de segmentation non supporté.")

    debits = calculer_debit(segments_plot)
    df_debit = pd.DataFrame(debits)
    debit_global = calculer_debit_global(transcript_segments)

    chart_barres = alt.Chart(df_debit).mark_bar().encode(
        x=alt.X(
            "start:Q",
            title="Début du segment (s)",
            scale=alt.Scale(domain=[0, df_debit["start"].max()]),
        ),
        y=alt.Y(
            "debit_mpm:Q",
            axis=alt.Axis(format=".2f", title="Débit (mots/min)"),
        ),
        tooltip=[
            alt.Tooltip("start:Q", format=".2f", title="Start (s)"),
            alt.Tooltip("end:Q", format=".2f", title="End (s)"),
            alt.Tooltip("nb_mots:Q", format=".2f", title="Nb Mots"),
            alt.Tooltip("debit_mpm:Q", format=".2f", title="Débit"),
        ],
    ).properties(
        title="Débit de parole par segment (barres)",
        width=600,
        height=300,
    )

    rule = alt.Chart(
        pd.DataFrame(
            {
                "start": [0, df_debit["start"].max()],
                "avg": [debit_global, debit_global],
            }
        )
    ).mark_rule(color="red").encode(
        y=alt.Y("avg:Q", axis=alt.Axis(format=".2f"))
    )
    chart_barres = chart_barres + rule

    chart_ligne = alt.Chart(df_debit).mark_line(point=True).encode(
        x=alt.X("start:Q", title="Début du segment (s)"),
        y=alt.Y(
            "debit_mpm:Q",
            axis=alt.Axis(format=".2f", title="Débit (mots/min)"),
        ),
        tooltip=[
            alt.Tooltip("start:Q", format=".2f", title="Start (s)"),
            alt.Tooltip("end:Q", format=".2f", title="End (s)"),
            alt.Tooltip("nb_mots:Q", format=".2f", title="Nb Mots"),
            alt.Tooltip("debit_mpm:Q", format=".2f", title="Débit"),
        ],
    )
    moyenne_df = pd.DataFrame(
        {
            "start": [0, df_debit["start"].max()],
            "debit_global": [debit_global, debit_global],
        }
    )
    ligne_moyenne = alt.Chart(moyenne_df).mark_rule(color="red").encode(
        y=alt.Y("debit_global:Q", axis=alt.Axis(format=".2f"))
    )
    chart_combine = (chart_ligne + ligne_moyenne).properties(
        title="Évolution du débit avec débit global moyen",
        width=600,
        height=300,
    )

    export_text = generer_export_texte(transcript_segments, debit_global)
    export_fichier = exporter_rapport(export_text, output_dir, nom_fichier="rapport_transcription.txt")
    df_csv = exporter_dataframe(df_debit, output_dir, nom_fichier="segments.csv")
    graph_barres_html = exporter_graphique_html(chart_barres, output_dir, nom_fichier="chart_barres.html")
    graph_barres_png = exporter_graphique_png(chart_barres, output_dir, nom_fichier="chart_barres.png")
    graph_combine_html = exporter_graphique_html(chart_combine, output_dir, nom_fichier="chart_combine.html")
    graph_combine_png = exporter_graphique_png(chart_combine, output_dir, nom_fichier="chart_combine.png")

    return (
        df_debit,
        chart_barres,
        chart_combine,
        export_text,
        export_fichier,
        df_csv,
        graph_barres_html,
        graph_barres_png,
        graph_combine_html,
        graph_combine_png,
        dialogue_file,
        transcript_segments,
        str(output_dir),
    )
