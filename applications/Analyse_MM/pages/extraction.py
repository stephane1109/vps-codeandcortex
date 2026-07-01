# pages/extraction.py
# Extraction et téléchargement : MP4 (HD / basse def), MP3, WAV, images (1/25/N fps), extrait par intervalle.
# Interface : 1 radio pour la qualité, des cases à cocher pour sélectionner les artefacts à générer,
# un seul bouton pour lancer, puis uniquement des boutons de téléchargement.
# La vidéo source préparée est attendue dans st.session_state["video_base"] (définie par main.py).

import shutil
import subprocess
from pathlib import Path
import streamlit as st

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

# ----------------- utilitaires -----------------

def executer_commande(cmd: list):
    """Exécute une commande système FFmpeg et retourne (ok, log)."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        log = "\n".join([s for s in (out, err) if s]).strip()
        return True, log
    except subprocess.CalledProcessError as e:
        out = (e.stdout or "").strip()
        err = (e.stderr or "").strip()
        log = "\n".join([s for s in (out, err) if s]).strip() or str(e)
        return False, log
    except Exception as e:
        return False, f"Erreur d'exécution : {e}"

def chemin_ffmpeg():
    """Retourne le chemin de ffmpeg ou None."""
    chemin, _ = info_ffmpeg()
    return chemin

def hhmmss_ou_secondes(valeur):
    """Accepte HH:MM:SS ou un nombre de secondes ; retourne toujours HH:MM:SS."""
    s = str(valeur).strip()
    if s.count(":") in (1, 2):
        return s
    try:
        x = max(0, float(s))
    except Exception:
        x = 0.0
    h = int(x // 3600)
    m = int((x % 3600) // 60)
    sec = int(x % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

def zipper_dossier(dossier: Path) -> Path:
    """Crée un zip du dossier et retourne le chemin du zip."""
    zip_path = dossier.parent / f"{dossier.name}.zip"
    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception:
            pass
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=dossier)
    return zip_path

# ----------------- page -----------------

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()
st.set_page_config(page_title="Extraction", layout="wide")
enforce_access()
st.title("Extraction")

# Vidéo de base préparée par main.py
if not st.session_state.get("video_base"):
    st.warning("Aucune vidéo préparée. Va d’abord sur la page d’accueil pour préparer la source.")
    st.stop()

video_base = Path(st.session_state["video_base"])
if not video_base.exists():
    st.warning("La vidéo préparée n’existe plus sur le disque. Relance la préparation dans la page d’accueil.")
    st.stop()

nom_base = st.session_state.get("base_court") or video_base.stem
ff = chemin_ffmpeg()
if not ff:
    st.error("FFmpeg introuvable.")
    st.stop()

# ----------------- Paramètres d’extraction -----------------

st.subheader("Qualité de sortie")
qualite = st.radio("Choix global", ["Basse définition (1280p)", "HD"], index=0, horizontal=True)
qual_is_basse = qualite.startswith("Basse")

st.subheader("Que veux-tu générer ?")
colA, colB, colC = st.columns(3)
with colA:
    want_mp4 = st.checkbox("Vidéo MP4", value=True)
    want_mp3 = st.checkbox("Audio MP3", value=False)
with colB:
    want_wav = st.checkbox("Audio WAV", value=False)
    want_images = st.checkbox("Images (JPG)", value=False)
with colC:
    want_interval = st.checkbox("Extrait par intervalle (MP4)", value=False)

# Options images
if want_images:
    c1, c2, c3 = st.columns(3)
    with c1:
        mode_img = st.selectbox("Fréquence", ["1 image/s", "25 images/s", "N images/s"], index=0)
    with c2:
        n_fps = st.number_input("N (si mode N)", min_value=1, max_value=120, value=10, step=1)
    with c3:
        def_img = st.radio("Définition images", ["Basse (1280p)", "HD (1920p)"], index=0, horizontal=True)

# Options intervalle
if want_interval:
    c4, c5, c6 = st.columns(3)
    with c4:
        iv_debut = st.text_input("Début (HH:MM:SS ou s)", value="00:00:05")
    with c5:
        iv_fin = st.text_input("Fin (HH:MM:SS ou s)", value="00:00:25")
    with c6:
        iv_qual = st.radio("Qualité extrait", ["Copie directe", "Basse def", "HD"], index=0, horizontal=False)

# ----------------- Lancement -----------------

logs = []
artefacts = []

if st.button("Lancer l’extraction", type="primary"):
    # Vidéo MP4 globale
    if want_mp4:
        heartbeat()
        if qual_is_basse:
            sortie = REP_SORTIE / f"{nom_base}_basse.mp4"
            cmd = [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video_base),
                "-vf", "scale=1280:-2",
                "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", "-ac", "2",
                "-movflags", "+faststart",
                str(sortie)
            ]
        else:
            sortie = REP_SORTIE / f"{nom_base}_hd.mp4"
            cmd = [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video_base),
                "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ac", "2",
                "-movflags", "+faststart",
                str(sortie)
            ]
        ok, log = executer_commande(cmd)
        logs.append(("MP4", ok, log))
        if ok and sortie.exists():
            artefacts.append(sortie)
            heartbeat()

    # MP3
    if want_mp3:
        heartbeat()
        sortie = REP_SORTIE / f"{nom_base}.mp3"
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_base),
            "-vn", "-c:a", "libmp3lame", "-b:a", "128k",
            str(sortie)
        ]
        ok, log = executer_commande(cmd)
        logs.append(("MP3", ok, log))
        if ok and sortie.exists():
            artefacts.append(sortie)
            heartbeat()

    # WAV
    if want_wav:
        heartbeat()
        sortie = REP_SORTIE / f"{nom_base}.wav"
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_base),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(sortie)
        ]
        ok, log = executer_commande(cmd)
        logs.append(("WAV", ok, log))
        if ok and sortie.exists():
            artefacts.append(sortie)
            heartbeat()

    # Images
    if want_images:
        heartbeat()
        fps = 1 if mode_img == "1 image/s" else (25 if mode_img == "25 images/s" else int(n_fps))
        wimg = 1280 if def_img.startswith("Basse") else 1920
        dossier = (BASE_DIR / "images" / f"{nom_base}").resolve()
        dossier.mkdir(parents=True, exist_ok=True)
        motif = str(dossier / "img_%06d.jpg")
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_base),
            "-vf", f"fps={fps},scale={wimg}:-2",
            "-q:v", "2",
            motif
        ]
        ok, log = executer_commande(cmd)
        logs.append((f"Images ({fps} i/s)", ok, log))
        if ok and any(dossier.glob("img_*.jpg")):
            # Préparer un zip pour téléchargement direct
            try:
                zip_path = zipper_dossier(dossier)
                artefacts.append(zip_path)
                heartbeat()
            except Exception as e:
                logs.append(("ZIP images", False, f"Zippage des images impossible : {e}"))

    # Intervalle
    if want_interval:
        heartbeat()
        t0 = hhmmss_ou_secondes(iv_debut)
        t1 = hhmmss_ou_secondes(iv_fin)
        sortie = REP_SORTIE / f"{nom_base}_intervalle.mp4"
        if iv_qual.startswith("Copie"):
            cmd = [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", t0, "-to", t1,
                "-i", str(video_base),
                "-c", "copy",
                "-movflags", "+faststart",
                str(sortie)
            ]
        elif iv_qual.startswith("Basse"):
            cmd = [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", t0, "-to", t1,
                "-i", str(video_base),
                "-vf", "scale=1280:-2",
                "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", "-ac", "2",
                "-movflags", "+faststart",
                str(sortie)
            ]
        else:
            cmd = [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", t0, "-to", t1,
                "-i", str(video_base),
                "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ac", "2",
                "-movflags", "+faststart",
                str(sortie)
            ]
        ok, log = executer_commande(cmd)
        logs.append(("Intervalle", ok, log))
        if ok and sortie.exists():
            artefacts.append(sortie)
            heartbeat()

    # ----------------- téléchargements -----------------
    st.subheader("Téléchargements")
    if not artefacts:
        st.info("Aucun fichier généré. Vérifie les cases cochées et les messages du journal.")
    else:
        for p in artefacts:
            data = p.read_bytes()
            mime = (
                "video/mp4" if p.suffix.lower() == ".mp4" else
                "audio/mpeg" if p.suffix.lower() == ".mp3" else
                "audio/wav" if p.suffix.lower() == ".wav" else
                "application/zip" if p.suffix.lower() == ".zip" else
                "application/octet-stream"
            )
            st.download_button(f"Télécharger {p.name}", data=data, file_name=p.name, mime=mime)

    # ----------------- journal -----------------
    with st.expander("Journal FFmpeg"):
        for titre, ok, log in logs:
            st.write(f"### {titre} — {'OK' if ok else 'ÉCHEC'}")
            st.code(log or "(vide)", language="bash")
