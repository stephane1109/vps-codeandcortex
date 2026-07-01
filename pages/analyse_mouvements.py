# pages/analyse_mouvements.py
# Analyse des mouvements avec garantie de scores :
# 1) Extraction FFmpeg 1080p en frames natives (timelapse) ou cadence fixe
# 2) Choix du pas d’analyse (intervalle entre frames analysées)
# 3) Calcul principal : flux optique Farneback (OpenCV)
# 4) Mode secours automatique si Farneback échoue : MAE entre frames (différence absolue)
# 5) Scores, anomalies (z-score), vignettes encadrées en rouge, graphiques et CSV
# 6) Aperçu global basé sur toutes les images extraites
#
# Remarques :
# - Si OpenCV est indisponible ou si trop de paires échouent, le script bascule vers le mode secours (MAE).
# - Les « anomalies » sont détectées sur un score composite standardisé. En Farneback : moyenne_magnitude + énergie.
#   En mode secours : MAE + énergie_diff (somme des différences).
# - Tout est expliqué dans l’interface et des diagnostics détaillent les paires traitées/échouées.

import math
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd
import streamlit as st

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

# =============================
# Utilitaires système
# =============================

def trouver_ffmpeg() -> Optional[str]:
    """Retourne le chemin de ffmpeg si disponible, sinon None."""
    p, _ = info_ffmpeg()
    return p

def executer(cmd: List[str]) -> Tuple[bool, str]:
    """Exécute une commande système et retourne (ok, log)."""
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

def importer_cv2():
    """Import différé d'OpenCV (opencv-python-headless recommandé)."""
    try:
        import cv2  # type: ignore
        return cv2, None
    except Exception as e:
        return None, f"OpenCV introuvable : {e}. Ajoute 'opencv-python-headless' dans requirements.txt."

# =============================
# Extraction d’images (FFmpeg)
# =============================

def extraire_frames_1080p(
    ffmpeg: str,
    video: Path,
    dossier: Path,
    mode_extraction: str,
    fps_ech: int = 4,
) -> Tuple[bool, str]:
    """
    Extrait des images JPG en 1080p (largeur 1920).
    mode_extraction = "natifs" -> toutes les frames sources (timelapse, VFR), -vsync vfr.
    mode_extraction = "fixe"   -> fps_ech images/seconde (uniforme).
    Sortie : frame_%06d.jpg
    """
    if dossier.exists():
        try:
            shutil.rmtree(dossier)
        except Exception:
            pass
    dossier.mkdir(parents=True, exist_ok=True)

    motif = str(dossier / "frame_%06d.jpg")
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]

    if mode_extraction == "natifs":
        cmd += ["-vf", "scale=1920:-2", "-vsync", "vfr", "-q:v", "2", motif]
    else:
        filtre = f"fps={fps_ech},scale=1920:-2"
        cmd += ["-vf", filtre, "-q:v", "2", motif]

    return executer(cmd)

# =============================
# Chargement et affichage images (PIL)
# =============================

def charger_images_pil(dossier: Path) -> Tuple[List[np.ndarray], List[Path]]:
    """
    Charge les images via PIL pour fiabiliser l'affichage.
    Retourne une liste d'images RGB (numpy uint8) + la liste de chemins.
    """
    from PIL import Image
    fichiers = sorted(dossier.glob("frame_*.jpg"))
    rgbs = []
    for f in fichiers:
        try:
            with Image.open(f) as im:
                im = im.convert("RGB")
                rgbs.append(np.array(im))
        except Exception:
            continue
    return rgbs, fichiers

def encadrer_rouge(img_rgb: np.ndarray, epaisseur: int = 8) -> np.ndarray:
    """Encadre une image RGB avec un cadre rouge (numpy direct)."""
    vis = img_rgb.copy()
    h, w = vis.shape[:2]
    e = max(1, int(epaisseur))
    vis[:e, :, :] = [255, 0, 0]
    vis[-e:, :, :] = [255, 0, 0]
    vis[:, :e, :] = [255, 0, 0]
    vis[:, -e:, :] = [255, 0, 0]
    return vis

# =============================
# Outils calculs (Farneback et Secours MAE)
# =============================

def convertir_gris_cv2(cv2, img_rgb: np.ndarray) -> np.ndarray:
    """Convertit une image RGB (numpy uint8) en niveaux de gris OpenCV."""
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return gray

def redimensionner_si_diff(cv2, a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Si tailles différentes, redimensionne b sur la taille de a (bilinéaire)."""
    if a.shape[:2] == b.shape[:2]:
        return a, b
    h, w = a.shape[:2]
    b_resize = cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    return a, b_resize

def farneback_flow(cv2, prev_gray: np.ndarray, gray: np.ndarray) -> Optional[np.ndarray]:
    """Flux optique dense Farneback, retourne (H, W, 2) ou None."""
    try:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray,
            None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2,
            flags=0
        )
        return flow
    except Exception:
        return None

def metriques_farneback(flow: np.ndarray) -> Dict[str, float]:
    """Métriques à partir du champ de flux Farneback."""
    mag = np.linalg.norm(flow, axis=2).astype(np.float32)
    dx = flow[..., 0].astype(np.float32)
    dy = flow[..., 1].astype(np.float32)
    angle = np.arctan2(dy, dx)
    ux, uy = np.cos(angle), np.sin(angle)
    R_x, R_y = float(np.mean(ux)), float(np.mean(uy))
    R = float(np.sqrt(R_x**2 + R_y**2))
    direction_deg = float(np.degrees(np.arctan2(R_y, R_x)))
    dispersion = float(1.0 - R)
    return {
        "magnitude_moyenne": float(np.mean(mag)),
        "magnitude_ecart_type": float(np.std(mag)),
        "magnitude_p95": float(np.percentile(mag, 95)),
        "energie_mouvement": float(np.sum(mag)),
        "direction_dominante_deg": direction_deg,
        "dispersion_direction": dispersion,
        "mode": "farneback",
    }

def metriques_secours_mae(prev_rgb: np.ndarray, curr_rgb: np.ndarray) -> Dict[str, float]:
    """
    Mode secours : métriques à partir de la différence absolue entre frames.
    magnitude_moyenne -> MAE pixel-à-pixel
    énergie_mouvement -> somme des |diff|
    direction/diffusion non pertinentes : on renvoie NaN.
    """
    diff = np.abs(curr_rgb.astype(np.float32) - prev_rgb.astype(np.float32))
    mae = float(np.mean(diff))
    p95 = float(np.percentile(diff, 95))
    energie = float(np.sum(diff))
    # Pour homogénéité des colonnes :
    return {
        "magnitude_moyenne": mae,
        "magnitude_ecart_type": float(np.std(diff)),
        "magnitude_p95": p95,
        "energie_mouvement": energie,
        "direction_dominante_deg": float("nan"),
        "dispersion_direction": float("nan"),
        "mode": "secours_mae",
    }

def zscore(x: np.ndarray) -> Tuple[np.ndarray, float, float]:
    """Standardise x → z = (x - mu) / sigma. Retourne (z, mu, sigma)."""
    mu = float(np.mean(x))
    sigma = float(np.std(x))
    if sigma < 1e-12:
        sigma = 1.0
    return (x - mu) / sigma, mu, sigma

# =============================
# Page Streamlit
# =============================

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()

st.set_page_config(page_title="Analyse des mouvements (scores garantis)", layout="wide")
enforce_access()
st.title("Analyse des mouvements avec pas d’analyse, Farneback et secours MAE")
st.markdown("**www.codeandcortex.fr**")

st.markdown(
    "Principe. Les images sont extraites en 1080p, soit à cadence fixe, soit en conservant toutes les frames natives. "
    "Le calcul principal repose sur le flux optique Farneback entre paires d’images espacées par le pas d’analyse. "
    "Si Farneback échoue ou est indisponible, un mode secours calcule des indices par différence absolue (MAE) pour garantir les scores. "
    "À chaque pas, on obtient la magnitude moyenne, l’écart-type, le 95e percentile, une énergie globale et, quand c’est possible, la direction dominante et sa dispersion. "
    "Un score composite standardisé sert à détecter des anomalies, visualisées par un encadrement rouge."
)

ff = trouver_ffmpeg()
if not ff:
    st.error("FFmpeg introuvable. Fournis un binaire ./bin/ffmpeg ou vérifie /usr/bin/ffmpeg.")
    st.stop()

cv2, cv_err = importer_cv2()
opencv_ok = cv2 is not None

if not opencv_ok:
    st.warning("OpenCV indisponible : le calcul se fera automatiquement en mode secours (MAE).")

# Source vidéo
st.subheader("Source vidéo")
source = st.radio("Choisir la source", ["Importer un MP4", "Utiliser la vidéo préparée"], index=0, horizontal=True)

video_path: Optional[Path] = None
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

# Paramètres d’extraction et d’analyse
st.subheader("Paramètres d’extraction et d’analyse")
col1, col2, col3 = st.columns(3)
with col1:
    mode_extraction = st.radio("Mode d’extraction d’images", ["Toutes les frames (timelapse/natif)", "Cadence fixe (i/s)"], index=0)
with col2:
    fps_ech = st.number_input("Cadence fixe (si sélectionnée)", min_value=1, max_value=60, value=4, step=1)
with col3:
    pas_analyse = st.number_input("Pas d’analyse (1 = chaque image)", min_value=1, max_value=100, value=1, step=1)

st.caption(
    "Pas d’analyse = intervalle entre frames analysées (1, 2, 3…). En timelapse, garde 1. "
    "Si tu vois peu de vignettes, utilise « frames natives » ou augmente la cadence fixe."
)

lancer = st.button("Analyser", type="primary")

if lancer:
    heartbeat()
    if video_path is None:
        st.error("Aucune source vidéo. Importez un MP4 ou sélectionnez la vidéo préparée.")
        st.stop()

    frames_dir = (BASE_DIR / "frames_analysis" / video_path.stem).resolve()
    mode = "natifs" if mode_extraction.startswith("Toutes") else "fixe"
    ok_ext, log_ext = extraire_frames_1080p(ff, video_path, frames_dir, mode_extraction=mode, fps_ech=int(fps_ech))
    if not ok_ext:
        st.error("Échec extraction des images avec FFmpeg.")
        with st.expander("Journal FFmpeg"):
            st.code(log_ext or "(vide)", language="bash")
        st.stop()

    # Chargement et aperçu immédiat
    imgs_rgb, fichiers = charger_images_pil(frames_dir)
    total_frames = len(imgs_rgb)
    if total_frames < 2:
        st.error("Trop peu d’images extraites pour analyser (ou échec de lecture des JPG).")
        with st.expander("Diagnostic extraction"):
            st.write(f"Dossier : {frames_dir}")
            st.write(f"Fichiers JPG détectés : {len(list(frames_dir.glob('frame_*.jpg')))}")
            st.code(log_ext or "(vide)", language="bash")
        st.stop()

    st.info(f"Images extraites : {total_frames} ({'frames natives' if mode=='natifs' else f'cadence fixe = {int(fps_ech)} i/s'}). "
            f"Si ce nombre est trop faible, choisis « frames natives » ou augmente la cadence fixe.")

    st.subheader("Aperçu immédiat des images extraites")
    Nprev = len(imgs_rgb)
    nb_prev = min(24, Nprev)
    idx_prev = np.linspace(0, Nprev - 1, num=nb_prev, dtype=int)
    cols = st.columns(6)
    for i, idx in enumerate(idx_prev):
        cols[i % 6].image(imgs_rgb[int(idx)], caption=f"frame #{int(idx)}", use_container_width=False)

    # Construction des indices pour le pas d’analyse
    pas = int(pas_analyse)
    indices = list(range(0, total_frames, pas))
    if len(indices) < 2:
        st.warning("Pas d’analyse trop grand pour la longueur de la séquence. Utilisation automatique de pas=1.")
        pas = 1
        indices = list(range(0, total_frames, pas))

    # Calculs
    lignes: List[Dict[str, float]] = []
    echecs_pairs = 0
    first_error_msg = None
    mode_utilise = "farneback" if opencv_ok else "secours_mae"
    paires_total = max(0, len(indices) - 1)

    for k in range(1, len(indices)):
        if k % 25 == 0:
            heartbeat()
        i_prev = indices[k-1]
        i_curr = indices[k]

        # Farneback si possible
        if opencv_ok:
            try:
                gray_prev = convertir_gris_cv2(cv2, imgs_rgb[i_prev])
                gray_curr = convertir_gris_cv2(cv2, imgs_rgb[i_curr])
                gray_prev, gray_curr = redimensionner_si_diff(cv2, gray_prev, gray_curr)
                flow = farneback_flow(cv2, gray_prev, gray_curr)
                if flow is not None:
                    met = metriques_farneback(flow)
                else:
                    raise RuntimeError("Farneback a renvoyé None")
            except Exception as e:
                echecs_pairs += 1
                if first_error_msg is None:
                    first_error_msg = f"Farneback échec (frame {i_prev}->{i_curr}) : {e}"
                # Mode secours pour cette paire
                met = metriques_secours_mae(imgs_rgb[i_prev], imgs_rgb[i_curr])
                mode_utilise = "mixte"
        else:
            # OpenCV indisponible : mode secours
            met = metriques_secours_mae(imgs_rgb[i_prev], imgs_rgb[i_curr])

        lignes.append({
            "etape": k,
            "frame_prev": i_prev,
            "frame_curr": i_curr,
            **met,
        })

    st.caption(f"Paires totales : {paires_total} | Paires en Farneback échouées : {echecs_pairs} | Mode utilisé : {mode_utilise}")
    if first_error_msg:
        with st.expander("Première erreur rencontrée (diagnostic)"):
            st.code(first_error_msg)

    if not lignes:
        st.error("Aucune paire exploitable. Essaie pas=1 et « frames natives » ; sinon vérifie opencv-python-headless.")
        st.stop()

    df = pd.DataFrame(lignes)

    # Résumés, scores, anomalies
    colonnes_scalaires = ["magnitude_moyenne", "magnitude_ecart_type", "magnitude_p95",
                          "energie_mouvement", "direction_dominante_deg", "dispersion_direction"]
    moyennes_globales = df[colonnes_scalaires].mean(numeric_only=True).to_dict()

    # Score composite selon le mode : Farneback/MAE partagent magnitude_moyenne et energie_mouvement
    zM, _, _ = zscore(df["magnitude_moyenne"].to_numpy(dtype=np.float64))
    zE, _, _ = zscore(df["energie_mouvement"].to_numpy(dtype=np.float64))
    df["score_composite_z"] = (zM + zE) / 2.0
    seuil_z = 2.5
    df["anomalie"] = df["score_composite_z"] >= seuil_z

    st.subheader("Moyennes globales (baseline)")
    st.dataframe(pd.DataFrame([moyennes_globales]).T.rename(columns={0: "valeur"}))

    st.subheader("Scores et anomalies")
    st.write(f"Seuil d’anomalie : z ≥ {seuil_z:.1f}")
    # Affiche toujours un graphique simple
    st.line_chart(df.set_index("etape")[["magnitude_moyenne", "energie_mouvement", "score_composite_z"]])

    nb_ano = int(df["anomalie"].sum())
    st.write(f"Nombre d’anomalies détectées : {nb_ano}")

    st.subheader("Vignettes des anomalies (encadrées en rouge)")
    if nb_ano > 0:
        ord_ano = df[df["anomalie"]].sort_values("score_composite_z", ascending=False)
        top = ord_ano.head(16)
        cols_par_ligne = 8
        k = 0
        for _ in range(math.ceil(len(top) / cols_par_ligne)):
            cols = st.columns(cols_par_ligne)
            for c in cols:
                if k >= len(top):
                    break
                row = top.iloc[k]
                idx = int(row["frame_curr"])
                z_here = float(row["score_composite_z"])
                if 0 <= idx < len(imgs_rgb):
                    vis = encadrer_rouge(imgs_rgb[idx], epaisseur=8)
                    c.image(vis, caption=f"frame #{idx} • z={z_here:.2f}", use_container_width=False)
                k += 1
    else:
        st.info("Aucune anomalie forte détectée.")

    # Table et export
    st.subheader("Tableau des indices par pas")
    st.dataframe(df)

    st.subheader("Téléchargements (CSV)")
    st.download_button(
        "Indices et anomalies par pas",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="indices_mouvement_et_anomalies.csv",
        mime="text/csv"
    )
    heartbeat()

    # Aperçu global sur toutes les images extraites
    st.subheader("Aperçu global (vignettes réparties, anomalies encadrées)")
    N = len(imgs_rgb)
    nb_vignettes = min(96, N)
    idxs = np.linspace(0, N - 1, num=nb_vignettes, dtype=int)

    frames_anormales = set(df[df["anomalie"]]["frame_curr"].astype(int).tolist())
    z_map = {int(r["frame_curr"]): float(r["score_composite_z"]) for _, r in df.iterrows()}

    cols_par_ligne = 8
    k = 0
    for _ in range(math.ceil(len(idxs) / cols_par_ligne)):
        cols = st.columns(cols_par_ligne)
        for c in cols:
            if k >= len(idxs):
                break
            fr = int(idxs[k])
            img = encadrer_rouge(imgs_rgb[fr], epaisseur=6) if fr in frames_anormales else imgs_rgb[fr]
            z_here = z_map.get(fr, None)
            cap = f"frame #{fr}" + (f" • z={z_here:.2f}" if z_here is not None else "")
            c.image(img, caption=cap, use_container_width=False)
            k += 1

    # Explications
    st.subheader("Explications et interprétation")
    st.markdown(
        "Le flux optique mesure les déplacements apparents des pixels entre deux images. "
        "Le mode principal (Farneback) fournit des indices de magnitude et, quand c’est pertinent, d’orientation moyenne et de dispersion. "
        "Le mode secours (MAE) utilise la différence absolue entre images et garantit des scores même si OpenCV est absent ou instable. "
        "Le score composite regroupe magnitude moyenne et énergie en z-score, puis marque les écarts forts comme anomalies. "
        "En timelapse, garde un pas d’analyse de 1 pour exploiter chaque image extraite ; augmente-le uniquement si le volume est trop élevé."
    )
