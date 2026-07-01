# pages/analyse_mouvement.py
# Analyse de mouvement à partir d'un FICHIER UPLOADÉ (prioritaire) ou de la vidéo préparée (fallback).
# Pipeline robuste : FFmpeg extrait des frames JPG -> OpenCV calcule le flux optique Farneback -> métriques + vignettes.
# Evite VideoCapture (souvent noir en environnement headless).

import math
import shutil
from pathlib import Path
from typing import Tuple, List

import numpy as np
import streamlit as st

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

# =========================
# Utilitaires système
# =========================

def obtenir_ffmpeg() -> str | None:
    """Retourne le chemin de ffmpeg ou None."""
    p, _ = info_ffmpeg()
    return p

def executer(cmd: list[str]) -> Tuple[bool, str]:
    """Exécute une commande système, renvoie (ok, log stdout+stderr)."""
    import subprocess
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

def charger_cv2():
    """Import différé d'OpenCV. Dépendance à ajouter : opencv-python-headless."""
    try:
        import cv2  # type: ignore
        return cv2, None
    except Exception as e:
        return None, f"OpenCV introuvable : {e}. Ajoute 'opencv-python-headless' dans requirements.txt."

# =========================
# Extraction d'images
# =========================

def extraire_frames_ffmpeg(ffmpeg: str, video: Path, dossier: Path, fps_ech: float, largeur: int) -> Tuple[bool, str]:
    """Extrait des frames JPEG avec FFmpeg à cadence régulière et largeur donnée."""
    if dossier.exists():
        try:
            shutil.rmtree(dossier)
        except Exception:
            pass
    dossier.mkdir(parents=True, exist_ok=True)

    motif = str(dossier / "frame_%06d.jpg")
    filtre = f"fps={fps_ech},scale={largeur}:-2"
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video),
        "-vf", filtre,
        "-q:v", "2",  # qualité JPG correcte
        motif
    ]
    return executer(cmd)

# =========================
# Chargement images
# =========================

def lire_images_gris_et_rgb(cv2, dossier: Path) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    """Charge toutes les frames JPG en niveaux de gris et en RGB pour vignettes."""
    fichiers = sorted(dossier.glob("frame_*.jpg"))
    imgs_gray, imgs_rgb = [], []
    for f in fichiers:
        # Lecture robuste depuis le chemin (cv2.imread directement)
        arr = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if arr is None:
            continue
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        imgs_gray.append(gray)
        imgs_rgb.append(rgb)
    return imgs_gray, imgs_rgb

# =========================
# Flux optique + métriques
# =========================

def calculer_flux_farneback(cv2, prev_gray: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Calcule le flux optique dense Farneback."""
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray,
        None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2,
        flags=0
    )
    return flow  # (H, W, 2)

def metriques_mouvement(mag: np.ndarray, seuil_pix: float) -> dict:
    """Métriques de variation à partir de la magnitude du flux."""
    m = float(np.mean(mag))
    s = float(np.std(mag))
    p95 = float(np.percentile(mag, 95))
    ratio_mobile = float(np.mean(mag > seuil_pix))
    energie = float(np.sum(mag))
    return {
        "magnitude_moyenne": m,
        "magnitude_ecart_type": s,
        "magnitude_p95": p95,
        "ratio_pixels_mobiles": ratio_mobile,
        "energie_mouvement": energie,
    }

# =========================
# Page Streamlit
# =========================

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()

st.set_page_config(page_title="Analyse de mouvement (flux optique)", layout="wide")
enforce_access()
st.title("Analyse de mouvement (flux optique)")

ff = obtenir_ffmpeg()
if not ff:
    st.error("FFmpeg introuvable. Dépose un binaire dans ./bin/ffmpeg ou vérifie /usr/bin/ffmpeg.")
    st.stop()

cv2, err = charger_cv2()
if cv2 is None:
    st.error(err)
    st.stop()

# Choix de la source : UPLOAD prioritaire, sinon vidéo préparée
st.subheader("Source d'analyse")
source = st.radio("Choisir la source", ["Importer un MP4", "Utiliser la vidéo préparée"], index=0, horizontal=True)

video_path: Path | None = None

if source == "Importer un MP4":
    up = st.file_uploader("Importer une vidéo (.mp4)", type=["mp4"], key="analyse_upload")
    if up is not None:
        video_path = REP_TMP / f"analyse_{up.name}"
        with open(video_path, "wb") as g:
            g.write(up.read())
        st.success(f"Fichier uploadé : {video_path.name}")
else:
    if st.session_state.get("video_base"):
        p = Path(st.session_state["video_base"])
        if p.exists():
            video_path = p
            st.info(f"Vidéo préparée utilisée : {p.name}")
        else:
            st.warning("La vidéo préparée est introuvable sur le disque. Importez un MP4.")
    else:
        st.warning("Aucune vidéo préparée en mémoire. Importez un MP4.")

# Paramètres
st.subheader("Paramètres d'analyse")
c1, c2, c3 = st.columns(3)
with c1:
    fps_ech = st.number_input("Cadence d’échantillonnage (images/sec)", min_value=1, max_value=30, value=5, step=1)
with c2:
    largeur_det = st.selectbox("Largeur d’analyse (px)", [480, 640, 960], index=1)
with c3:
    seuil_pix = st.number_input("Seuil pixel 'mobile' (px/frame)", min_value=0.1, max_value=10.0, value=1.5, step=0.1)

c4, c5 = st.columns(2)
with c4:
    nb_vignettes = st.number_input("Nombre de vignettes à afficher", min_value=8, max_value=200, value=40, step=4)
with c5:
    montrer_log = st.checkbox("Afficher le journal FFmpeg", value=False)

lancer = st.button("Lancer l'analyse", type="primary")

if lancer:
    heartbeat()
    if video_path is None:
        st.error("Aucune source vidéo. Importez un MP4 ou sélectionnez la vidéo préparée.")
        st.stop()

    # 1) Extraction d'images avec FFmpeg
    frames_dir = (BASE_DIR / "frames_analysis" / video_path.stem).resolve()
    ok_ext, log_ext = extraire_frames_ffmpeg(ff, video_path, frames_dir, float(fps_ech), int(largeur_det))
    if not ok_ext:
        st.error("Échec extraction des images avec FFmpeg.")
        if montrer_log:
            st.code(log_ext or "(log vide)", language="bash")
        st.stop()

    nb_jpg = len(list(frames_dir.glob("frame_*.jpg")))
    if nb_jpg == 0:
        st.error("Aucune image extraite. La page resterait noire. Causes probables : entrée corrompue ou FFmpeg sans décodage pour ce média.")
        if montrer_log:
            st.code(log_ext or "(log vide)", language="bash")
        st.stop()

    # 2) Chargement des images (gris + RGB)
    imgs_gray, imgs_rgb = lire_images_gris_et_rgb(cv2, frames_dir)
    if len(imgs_gray) < 2:
        st.error("Nombre insuffisant d'images pour calculer un flux optique.")
        st.stop()

    # 3) Flux optique + métriques par pas
    metriques = []
    energies = []
    for i in range(1, len(imgs_gray)):
        if i % 25 == 0:
            heartbeat()
        flow = calculer_flux_farneback(cv2, imgs_gray[i-1], imgs_gray[i])
        mag = np.linalg.norm(flow, axis=2)
        m = metriques_mouvement(mag, float(seuil_pix))
        metriques.append(m)
        energies.append(m["energie_mouvement"])

    # 4) Synthèse et détection de pics
    energies = np.array(energies, dtype=float)
    moy = float(np.mean(energies))
    std = float(np.std(energies))
    seuil_pic = moy + 2.0 * std
    pics_idx = [i+1 for i, e in enumerate(energies) if e >= seuil_pic]  # indices dans la séquence extraite

    st.subheader("Métriques globales")
    st.write(f"Énergie moyenne du mouvement : {moy:.2f}")
    st.write(f"Écart-type de l’énergie : {std:.2f}")
    st.write(f"Seuil de pic (moy + 2σ) : {seuil_pic:.2f}")
    if pics_idx:
        temps_pics = [idx / float(fps_ech) for idx in pics_idx]
        st.write("Pics détectés : " + ", ".join([f"t≈{t:.1f}s (#{idx})" for t, idx in zip(temps_pics, pics_idx)]))
    else:
        st.write("Aucun pic détecté au seuil courant.")

    # 5) Export CSV des métriques
    import pandas as pd
    lignes = []
    for i, m in enumerate(metriques, start=1):
        lignes.append({
            "index_sequence": i,               # index dans la séquence de frames extraites
            "temps_s_approx": i/float(fps_ech),
            "magnitude_moyenne": m["magnitude_moyenne"],
            "magnitude_ecart_type": m["magnitude_ecart_type"],
            "magnitude_p95": m["magnitude_p95"],
            "ratio_pixels_mobiles": m["ratio_pixels_mobiles"],
            "energie_mouvement": m["energie_mouvement"],
        })
    df = pd.DataFrame(lignes)
    st.download_button("Télécharger les métriques (CSV)", data=df.to_csv(index=False).encode("utf-8"),
                       file_name="metriques_flux_optique.csv", mime="text/csv")

    # 6) Grille de vignettes uniformément réparties
    st.subheader("Vignettes réparties sur la vidéo")
    N = len(imgs_rgb)
    indices = np.linspace(0, N-1, num=int(nb_vignettes), dtype=int)
    cols_par_ligne = 8
    lignes_nb = math.ceil(len(indices) / cols_par_ligne)
    k = 0
    for _ in range(lignes_nb):
        cols = st.columns(cols_par_ligne)
        for c in cols:
            if k >= len(indices):
                break
            i = int(indices[k])
            c.image(imgs_rgb[i], caption=f"#{i} • t≈{i/float(fps_ech):.1f}s", use_container_width=False)
            k += 1

    # 7) Journal FFmpeg optionnel
    if montrer_log:
        with st.expander("Journal FFmpeg"):
            st.code(log_ext or "(log vide)", language="bash")
    heartbeat()
