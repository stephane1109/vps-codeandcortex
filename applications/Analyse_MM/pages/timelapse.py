# pages/timelapse.py
# Assemblage timelapse à partir d’un dossier d’images (img_%06d.jpg) produit par la page extraction.
# Choix simple : cadence 6/8/10/12/14 i/s et définition (basse 1280p / HD 1920p).

import subprocess
from pathlib import Path
import streamlit as st

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

def _run(cmd: list):
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

def _ffmpeg():
    p, _ = info_ffmpeg()
    return p

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()
st.set_page_config(page_title="Timelapse", layout="wide")
enforce_access()
st.title("Timelapse")
st.markdown("**www.codeandcortex.fr**")

ff = _ffmpeg()
if not ff:
    st.error("FFmpeg introuvable.")
    st.stop()

racine_images = (BASE_DIR / "images").resolve()
dossiers = [str(d) for d in sorted(racine_images.glob("*")) if d.is_dir()] if racine_images.exists() else []
if not dossiers:
    st.info("Aucun dossier d’images détecté. Générez d’abord des images dans la page Extraction.")
    st.stop()

dossier_sel = st.selectbox("Dossier d’images", options=dossiers, index=0)
motif = st.text_input("Motif d’images (printf-style)", value="img_%06d.jpg")

c1, c2 = st.columns(2)
with c1:
    fps = st.selectbox("Cadence (images/s)", [6, 8, 10, 12, 14], index=0)
with c2:
    defn = st.radio("Définition", ["Basse (1280p)", "HD (1920p)"], index=0, horizontal=True)

w = 1280 if defn.startswith("Basse") else 1920
nom_sortie = Path(dossier_sel).name + f"_timelapse_{fps}fps.mp4"
sortie = (BASE_DIR / "timelapse" / nom_sortie).resolve()
sortie.parent.mkdir(parents=True, exist_ok=True)

if st.button("Composer et télécharger"):
    heartbeat()
    cmd = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(int(fps)),
        "-i", str(Path(dossier_sel) / motif),
        "-vf", f"scale={w}:-2",
        "-c:v", "libx264", "-preset", "slow", "-crf", "28" if w == 1280 else "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(sortie)
    ]
    ok, log = _run(cmd)
    if ok and sortie.exists():
        data = sortie.read_bytes()
        heartbeat()
        st.success(f"Timelapse prêt : {sortie.name}")
        st.video(data, format="video/mp4")
        st.download_button("Télécharger le timelapse", data=data, file_name=sortie.name, mime="video/mp4")
        with st.expander("Journal FFmpeg"):
            st.code(log, language="bash")
    else:
        st.error("Échec de la composition timelapse.")
        st.code(log or "Aucun log", language="bash")
