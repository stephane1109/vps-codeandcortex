# pages/anomalies.py
# Analyse d'anomalies et TIMELINE D'ANOMALIES EN VIGNETTES (Altair mark_image).
# - Upload MP4 hors formulaire + option "Vidéo préparée"
# - Paramètres d'analyse dans un formulaire : extraction FFmpeg, indicateurs (Farneback), anomalies (LOF/ISO/AE)
# - Résultats persistants en session_state
# - Timeline d'anomalies en vignettes posées sur l'axe du temps (data URI PNG)
# - Curseur de temps dynamique pour faire défiler l'aperçu grand format
# - Projection 2D Altair, timeline des scores, vignettes, tableau, export

import io
import math
import base64
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

# ============================= Utilitaires système =============================

def trouver_ffmpeg() -> Optional[str]:
    """Retourne le chemin de ffmpeg si disponible, sinon None."""
    p, _ = info_ffmpeg()
    return p

def deviner_ffprobe(ffmpeg_path: Optional[str]) -> str:
    """Si ffmpeg est connu, déduire ffprobe, sinon 'ffprobe'."""
    if ffmpeg_path and "ffmpeg" in ffmpeg_path:
        return ffmpeg_path.replace("ffmpeg", "ffprobe")
    return "ffprobe"

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
    """Import d'OpenCV (opencv-python-headless recommandé en requirements.txt)."""
    try:
        import cv2  # type: ignore
        return cv2, None
    except Exception as e:
        return None, f"OpenCV introuvable : {e}. Ajoute 'opencv-python-headless' dans requirements.txt."

# ============================= Extraction d’images (FFmpeg) =============================

@st.cache_data(show_spinner=False)
def extraire_frames_1080p_cache(ffmpeg: str, video: str, dossier: str, mode_extraction: str, fps_ech: int) -> Tuple[bool, str]:
    """Extraction d'images mise en cache pour éviter les recalculs inutiles."""
    return extraire_frames_1080p(ffmpeg, Path(video), Path(dossier), mode_extraction, fps_ech)

def extraire_frames_1080p(
    ffmpeg: str,
    video: Path,
    dossier: Path,
    mode_extraction: str,
    fps_ech: int = 4
) -> Tuple[bool, str]:
    """Extrait des images JPG 1080p. Sortie : frame_%06d.jpg."""
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
        cmd += ["-vf", f"fps={fps_ech},scale=1920:-2", "-q:v", "2", motif]

    return executer(cmd)

# ============================= Timestamps réels (ffprobe) =============================

@st.cache_data(show_spinner=False)
def lire_timestamps_video_cache(ffprobe: str, video: str) -> Tuple[bool, List[float], str]:
    """Lecture des timestamps via ffprobe (mise en cache)."""
    return lire_timestamps_video(ffprobe, Path(video))

def lire_timestamps_video(ffprobe: str, video: Path) -> Tuple[bool, List[float], str]:
    """Renvoie (ok, liste de timestamps en secondes, log)."""
    cmd1 = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video)
    ]
    ok1, log1 = executer(cmd1)
    lignes = []
    if ok1 and log1:
        lignes = [x.strip() for x in log1.splitlines() if x.strip()]

    if not lignes:
        cmd2 = [
            ffprobe, "-v", "error", "-select_streams", "v:0",
            "-show_frames", "-show_entries", "frame=pkt_pts_time",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video)
        ]
        ok2, log2 = executer(cmd2)
        if ok2 and log2:
            lignes = [x.strip() for x in log2.splitlines() if x.strip()]
        ok_global = ok1 or ok2
        log_global = (log1 + "\n" + log2).strip()
    else:
        ok_global = ok1
        log_global = log1

    temps = []
    for s in lignes:
        try:
            temps.append(float(s))
        except Exception:
            continue
    return ok_global and len(temps) > 0, temps, log_global

# ============================= Chargement images (OpenCV) =============================

def lire_images_cv2(cv2, dossier: Path) -> List[np.ndarray]:
    """Lit toutes les images frame_*.jpg en RGB (uint8)."""
    imgs = []
    for f in sorted(dossier.glob("frame_*.jpg")):
        bgr = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        imgs.append(rgb)
    return imgs

def encadrer_rouge_cv2(cv2, img_rgb: np.ndarray, e: int = 8) -> np.ndarray:
    """Dessine un cadre rouge pour signaler une anomalie."""
    vis = img_rgb.copy()
    h, w = vis.shape[:2]
    cv2.rectangle(vis, (0, 0), (w-1, h-1), (255, 0, 0), thickness=max(1, e))
    return vis

def to_gray_norm(cv2, img_rgb: np.ndarray) -> np.ndarray:
    """Convertit RGB -> Gray float32 [0,1]."""
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    return gray

def aligner_taille(cv2, a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Ajuste b à la taille de a si nécessaire (bilinéaire)."""
    if a.shape == b.shape:
        return a, b
    h, w = a.shape[:2]
    b_res = cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    return a, b_res

# ============================= Flux optique Farneback =============================

def calculer_indicateurs_pas(cv2, prev_rgb: np.ndarray, curr_rgb: np.ndarray) -> Optional[Dict[str, float]]:
    """Indicateurs de mouvement pour une paire d'images consécutives."""
    try:
        g0 = to_gray_norm(cv2, prev_rgb)
        g1 = to_gray_norm(cv2, curr_rgb)
        g0, g1 = aligner_taille(cv2, g0, g1)
        flow = cv2.calcOpticalFlowFarneback(
            g0, g1, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )
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
        }
    except Exception:
        return None

# ============================= Prétraitement / features =============================

def construire_X(df: pd.DataFrame, choix_features: str) -> Tuple[np.ndarray, List[str]]:
    """Matrice X selon le choix d'indicateurs."""
    if choix_features == "Magnitude seule":
        cols = ["magnitude_moyenne"]
    elif choix_features == "Magnitude + énergie":
        cols = ["magnitude_moyenne", "energie_mouvement"]
    else:
        cols = ["magnitude_moyenne", "magnitude_ecart_type", "magnitude_p95",
                "energie_mouvement", "direction_dominante_deg", "dispersion_direction"]
    X = df[cols].to_numpy(dtype=np.float64)
    return X, cols

# ============================= Détecteurs d'anomalies =============================

def anomalies_lof(X: np.ndarray, contamination: float, n_neighbors: int = 20) -> Tuple[np.ndarray, np.ndarray]:
    """Local Outlier Factor : scores élevés = plus anormal."""
    from sklearn.neighbors import LocalOutlierFactor
    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination, novelty=False)
    y = lof.fit_predict(X)  # -1 outlier
    scores = -lof.negative_outlier_factor_
    return scores, y

def anomalies_isoforest(X: np.ndarray, contamination: float, n_estimators: int = 200) -> Tuple[np.ndarray, np.ndarray]:
    """Isolation Forest : scores élevés = plus anormal."""
    from sklearn.ensemble import IsolationForest
    iso = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=42, n_jobs=-1)
    y = iso.fit_predict(X)  # -1 outlier
    scores = -iso.decision_function(X)
    return scores, y

def anomalies_autoencodeur(X: np.ndarray, contamination: float, hidden: int = 8, max_iter: int = 400) -> Tuple[np.ndarray, np.ndarray]:
    """Auto-encodeur léger (MLPRegressor) : erreur de reconstruction comme score."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    ae = MLPRegressor(hidden_layer_sizes=(hidden,), activation="relu", solver="adam", max_iter=max_iter, random_state=42)
    ae.fit(Xs, Xs)
    X_pred = ae.predict(Xs)
    err = np.mean((X_pred - Xs) ** 2, axis=1)
    seuil = float(np.quantile(err, 1.0 - contamination))
    y = np.where(err >= seuil, -1, 1)
    return err, y

# ============================= Projection 2D (PCA / t-SNE) =============================

def projeter_2d(X: np.ndarray, methode: str) -> np.ndarray:
    """Retourne une projection 2D (PCA rapide, t-SNE plus lent)."""
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    if methode == "t-SNE (lent)":
        from sklearn.manifold import TSNE
        emb = TSNE(n_components=2, learning_rate="auto", init="pca", perplexity=30, random_state=42).fit_transform(Xs)
    else:
        from sklearn.decomposition import PCA
        emb = PCA(n_components=2, random_state=42).fit_transform(Xs)
    return emb

# ============================= Helpers vignettes (Altair mark_image) =============================

def fabriquer_vignette_datauri(cv2, img_rgb: np.ndarray, largeur: int = 120, cadre_rouge: bool = True) -> str:
    """Crée une petite vignette PNG encadrée et retourne une data URI 'data:image/png;base64,...'."""
    h, w = img_rgb.shape[:2]
    if cadre_rouge:
        img_rgb = encadrer_rouge_cv2(cv2, img_rgb, e=max(2, int(largeur * 0.05)))
    ratio = largeur / max(1, w)
    nv_h = int(max(1, round(h * ratio)))
    import cv2 as _cv2  # éviter confusion type checker
    img_res = _cv2.resize(img_rgb, (largeur, nv_h), interpolation=_cv2.INTER_AREA)
    ok, buf = _cv2.imencode(".png", _cv2.cvtColor(img_res, _cv2.COLOR_RGB2BGR))
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"

# ============================= App Streamlit =============================

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()
st.set_page_config(page_title="Anomalies + Timeline en vignettes", layout="wide")
enforce_access()
st.title("Anomalies + Timeline en vignettes (images posées sur le temps)")
st.markdown("www.codeandcortex.fr")

ffmpeg_path = trouver_ffmpeg()
if not ffmpeg_path:
    st.error("FFmpeg introuvable. Binaire attendu sous /usr/bin/ffmpeg ou similaire.")
    st.stop()
ffprobe_path = deviner_ffprobe(ffmpeg_path)

cv2, cv_err = importer_cv2()
if cv2 is None:
    st.error(cv_err)
    st.stop()

# État global des résultats
st.session_state.setdefault("anom", None)
st.session_state.setdefault("video_upload_path", None)

# ----------------------------- Upload MP4 hors formulaire -----------------------------
st.subheader("Importer un MP4")
up = st.file_uploader("Importer une vidéo (.mp4)", type=["mp4"], key="upload_mp4_global")
if up is not None:
    tmp = REP_TMP / f"anom_{up.name}"
    with open(tmp, "wb") as g:
        g.write(up.read())
    st.session_state["video_upload_path"] = str(tmp)
    st.success(f"Fichier importé : {tmp.name}")

# ----------------------------- Formulaire paramètres -----------------------------
with st.form("params"):
    st.subheader("Paramètres d’analyse")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        source_choisie = st.radio(
            "Source vidéo",
            ["Vidéo importée ci-dessus", "Vidéo préparée"],
            index=0 if st.session_state.get("video_upload_path") else 1,
            horizontal=True
        )
    with c2:
        mode_ext = st.radio("Extraction d’images", ["Frames natives", "Cadence fixe"], index=0)
    with c3:
        fps = st.number_input("Cadence fixe (i/s)", min_value=1, max_value=60, value=4, step=1)
    with c4:
        pas = st.number_input("Pas d’analyse (1 = chaque image)", min_value=1, max_value=200, value=1, step=1)

    c5, c6, c7 = st.columns(3)
    with c5:
        choix_feat = st.selectbox("Indicateurs", ["Magnitude seule", "Magnitude + énergie", "Tous les indicateurs"])
    with c6:
        methode = st.selectbox("Méthode anomalies", ["Local Outlier Factor", "Isolation Forest", "Auto-Encodeur"])
    with c7:
        projection = st.selectbox("Projection 2D", ["PCA (rapide)", "t-SNE (lent)"], index=0)

    c8, c9, c10 = st.columns(3)
    with c8:
        contamination = st.slider("Contamination attendue", 0.01, 0.4, 0.1, 0.01)
    if methode == "Local Outlier Factor":
        with c9:
            n_neighbors = st.number_input("n_neighbors (LOF)", min_value=5, max_value=100, value=20, step=1)
    elif methode == "Isolation Forest":
        with c9:
            n_estimators = st.number_input("n_estimators (ISO)", min_value=50, max_value=1000, value=200, step=50)
    else:
        with c9:
            hidden = st.number_input("Taille couche cachée (Auto-Enc.)", min_value=2, max_value=128, value=8, step=1)

    lancer = st.form_submit_button("Lancer l’analyse", type="primary")

# ----------------------------- Exécution unique de l’analyse -----------------------------
if lancer:
    heartbeat()
    # Résolution de la source vidéo
    video_path: Optional[Path] = None
    if source_choisie == "Vidéo importée ci-dessus":
        vup = st.session_state.get("video_upload_path")
        if vup:
            video_path = Path(vup)
        else:
            st.error("Aucune vidéo importée. Utilise le bouton d’upload en haut de page.")
            st.stop()
    else:
        if st.session_state.get("video_base"):
            p = Path(st.session_state["video_base"])
            if p.exists():
                video_path = p
            else:
                st.error("La vidéo préparée est introuvable sur le disque.")
                st.stop()
        else:
            st.error("Aucune vidéo préparée n’est disponible en session.")
            st.stop()

    frames_dir = (BASE_DIR / "frames_anom" / video_path.stem).resolve()
    mode = "natifs" if mode_ext == "Frames natives" else "fixe"

    ok, log = extraire_frames_1080p_cache(ffmpeg_path, str(video_path), str(frames_dir), mode, int(fps))
    if not ok:
        st.error("Échec extraction d’images avec FFmpeg.")
        st.code(log or "(journal vide)", language="bash")
        st.stop()

    imgs = lire_images_cv2(cv2, frames_dir)
    n = len(imgs)
    if n < 3:
        st.error("Trop peu d’images pour analyser.")
        st.stop()

    # Timestamps par frame
    if mode == "natifs":
        ok_ts, ts_all, _ = lire_timestamps_video_cache(ffprobe_path, str(video_path))
        if ok_ts and len(ts_all) > 0:
            m = min(len(ts_all), n)
            temps_par_frame = np.array(ts_all[:m], dtype=float)
            if m < n:
                dernier = temps_par_frame[-1] if m > 0 else 0.0
                extra = np.linspace(dernier, dernier + (n - m) * 1.0 / max(1, fps), num=(n - m), endpoint=False)
                temps_par_frame = np.concatenate([temps_par_frame, extra])
        else:
            temps_par_frame = np.arange(n, dtype=float)  # fallback si ffprobe indisponible
    else:
        temps_par_frame = np.arange(n, dtype=float) / float(max(1, fps))

    # Indices d’analyse
    indices = list(range(0, n, int(pas)))
    if len(indices) < 2:
        indices = list(range(0, n, 1))

    # Calcul indicateurs par pas
    lignes: List[Dict[str, float]] = []
    for k in range(1, len(indices)):
        if k % 25 == 0:
            heartbeat()
        i0 = indices[k-1]
        i1 = indices[k]
        met = calculer_indicateurs_pas(cv2, imgs[i0], imgs[i1])
        if met is None:
            continue
        d = {"etape": k, "frame_prev": i0, "frame_curr": i1, **met, "t": float(temps_par_frame[i1])}
        lignes.append(d)
    if not lignes:
        st.error("Aucune paire exploitable pour calculer les indicateurs.")
        st.stop()

    df = pd.DataFrame(lignes)
    X, cols = construire_X(df, choix_feat)

    # Détection d’anomalies
    if methode == "Local Outlier Factor":
        scores, ypred = anomalies_lof(X, contamination=float(contamination), n_neighbors=int(n_neighbors))
    elif methode == "Isolation Forest":
        scores, ypred = anomalies_isoforest(X, contamination=float(contamination), n_estimators=int(n_estimators))
    else:
        scores, ypred = anomalies_autoencodeur(X, contamination=float(contamination), hidden=int(hidden))

    df["score_anomalie"] = scores
    df["anomalie"] = (ypred == -1)
    df["etat"] = np.where(df["anomalie"], "Anomalie", "Normal")

    # Projection 2D
    try:
        emb = projeter_2d(X, methode=projection)
        df["x"], df["y"] = emb[:, 0], emb[:, 1]
    except Exception:
        df["x"], df["y"] = np.nan, np.nan

    # Préparation des vignettes anomalies pour Altair
    dfa = df[df["anomalie"]].copy()
    dfa = dfa.sort_values("t", ascending=True).reset_index(drop=True)
    urls = []
    for idx_row, (_, row) in enumerate(dfa.iterrows(), start=1):
        if idx_row % 25 == 0:
            heartbeat()
        fr = int(row["frame_curr"])
        if 0 <= fr < n:
            uri = fabriquer_vignette_datauri(cv2, imgs[fr], largeur=120, cadre_rouge=True)
            urls.append(uri)
        else:
            urls.append("")
    dfa["url"] = urls  # le canal Altair attend "url"

    # Rangées verticales pour éviter le chevauchement
    if len(dfa) > 0:
        nb_lignes = min(3, max(1, len(dfa)//25 + 1))
        espace_vertical = 80
        dfa["y"] = [(i % nb_lignes) * espace_vertical for i in range(len(dfa))]
    else:
        dfa["y"] = []

    # État persistant des résultats
    st.session_state["anom"] = {
        "imgs": imgs,
        "times": temps_par_frame,
        "df": df,
        "dfa": dfa,            # anomalies uniquement avec data URI
        "cols": cols,
        "fps": int(fps),
        "mode": mode,
    }
    heartbeat()

# ----------------------------- Affichage résultats persistants -----------------------------
res = st.session_state.get("anom")
if not res:
    st.info("Importe un MP4 via le bouton ci-dessus ou choisis « Vidéo préparée », puis clique « Lancer l’analyse ».")
    st.stop()

imgs = res["imgs"]
temps_par_frame = res["times"]
df = res["df"]
dfa = res["dfa"]
fps = res["fps"]
mode = res["mode"]
n = len(imgs)

st.subheader("Résumé")
nb_ano = int(df["anomalie"].sum())
st.write(f"Images extraites : {n} • Paires analysées : {len(df)} • Anomalies détectées : {nb_ano}")

# -------- Projection 2D Altair --------
st.subheader("Projection 2D (Altair)")
try:
    if "x" in df and "y" in df and not df["x"].isna().all():
        hover2d = alt.selection_point(fields=["etape"], on="mouseover", nearest=True, empty=False)
        base2d = alt.Chart(df).mark_point(filled=True).encode(
            x=alt.X("x:Q", title="Composante 1"),
            y=alt.Y("y:Q", title="Composante 2"),
            color=alt.Color("etat:N",
                            scale=alt.Scale(domain=["Normal", "Anomalie"], range=["#377eb8", "#e41a1c"]),
                            title="État"),
            size=alt.Size("etat:N", scale=alt.Scale(domain=["Normal", "Anomalie"], range=[30, 70]), legend=None),
            tooltip=[alt.Tooltip("etape:Q", title="Étape"),
                     alt.Tooltip("frame_curr:Q", title="Frame"),
                     alt.Tooltip("t:Q", title="Temps (s)", format=".2f"),
                     alt.Tooltip("score_anomalie:Q", title="Score", format=".3f")]
        ).add_params(hover2d).properties(width=700, height=440)
        st.altair_chart((base2d + base2d.transform_filter(hover2d).mark_point(stroke="black", strokeWidth=1.5)).interactive(),
                        use_container_width=True)
    else:
        st.info("Projection 2D indisponible (échantillon trop faible ou PCA/t-SNE non calculable).")
except Exception as e:
    st.warning(f"Projection indisponible : {e}")

# -------- Timeline des scores (Altair) --------
st.subheader("Timeline des scores")
try:
    x_field = alt.X("t:Q", title="Temps (s)")
    base_line = alt.Chart(df).mark_line().encode(
        x=x_field,
        y=alt.Y("score_anomalie:Q", title="Score d’anomalie"),
    ).properties(width=1000, height=240)
    points_normaux = alt.Chart(df[df["anomalie"] == False]).mark_point(filled=True).encode(
        x=x_field, y=alt.Y("score_anomalie:Q"), color=alt.value("#377eb8"), size=alt.value(30)
    )
    points_anom = alt.Chart(df[df["anomalie"] == True]).mark_point(filled=True).encode(
        x=x_field, y=alt.Y("score_anomalie:Q"), color=alt.value("#e41a1c"), size=alt.value(70)
    )
    st.altair_chart((base_line + points_normaux + points_anom).interactive(), use_container_width=True)
except Exception as e:
    st.warning(f"Timeline des scores indisponible : {e}")

# =========================
# TIMELINE D'ANOMALIES EN VIGNETTES
# =========================
st.subheader("Timeline d’anomalies en vignettes (posées sur le temps)")

if dfa is None or len(dfa) == 0:
    st.info("Aucune anomalie détectée au seuil demandé. Ajuste la contamination ou la méthode.")
else:
    try:
        # Nettoyage : retirer les lignes sans URL (sécurité)
        dfa_plot = dfa[dfa["url"] != ""].copy()
        if len(dfa_plot) == 0:
            st.warning("Aucune vignette disponible pour les anomalies (URLs vides).")
        else:
            # Graphique images posées à (t, y)
            timeline_img = alt.Chart(dfa_plot).mark_image().encode(
                x=alt.X("t:Q", title="Temps (s)"),
                y=alt.Y("y:Q", axis=None),
                url=alt.Url("url:N", title="Vignette"),
                tooltip=[
                    alt.Tooltip("t:Q", title="Temps (s)", format=".2f"),
                    alt.Tooltip("frame_curr:Q", title="Frame"),
                    alt.Tooltip("score_anomalie:Q", title="Score", format=".3f")
                ]
            ).properties(height=int(dfa_plot["y"].max() + 120 if "y" in dfa_plot else 200), width=1000)

            st.altair_chart(timeline_img.interactive(), use_container_width=True)

            # Curseur de temps dynamique hors formulaire
            t_min = float(dfa_plot["t"].min())
            t_max = float(dfa_plot["t"].max())
            st.session_state.setdefault("curseur_t_anom", t_min)
            curseur_t = st.slider(
                "Curseur temps (visualisation dynamique de l’anomalie la plus proche)",
                min_value=t_min, max_value=t_max,
                value=float(st.session_state["curseur_t_anom"]),
                step=max(0.001, (t_max - t_min) / max(1000, len(dfa_plot))),
                key="slider_curseur_t_anom"
            )
            st.session_state["curseur_t_anom"] = float(curseur_t)

            # Trouver l’anomalie la plus proche du curseur et l’afficher en grand immédiatement
            arr_t = dfa_plot["t"].to_numpy(dtype=float)
            idx_proche = int(np.argmin(np.abs(arr_t - st.session_state["curseur_t_anom"])))
            row = dfa_plot.iloc[idx_proche]
            fr_sel = int(row["frame_curr"])
            if 0 <= fr_sel < n:
                img_sel = encadrer_rouge_cv2(cv2, imgs[fr_sel], e=10)
                cap_sel = f"t={float(row['t']):.2f}s • étape {int(row['etape'])} • frame {fr_sel} • score={float(row['score_anomalie']):.3f}"
                st.image(img_sel, caption=cap_sel, use_container_width=True)
            else:
                st.warning("Frame hors limites pour l’aperçu.")
    except Exception as e:
        st.error(f"Erreur d’affichage Altair (timeline vignettes) : {e}")

# -------- Vignettes des anomalies (liste) --------
st.subheader("Vignettes des anomalies (liste)")
if nb_ano == 0:
    st.info("Aucune anomalie détectée.")
else:
    tri = st.selectbox("Tri", ["Score décroissant", "Temps croissant", "Frame croissant"], index=0, key="tri_anom_full")
    dfl = df[df["anomalie"]].copy()
    if tri == "Temps croissant":
        dfl = dfl.sort_values("t", ascending=True)
    elif tri == "Frame croissant":
        dfl = dfl.sort_values("frame_curr", ascending=True)
    else:
        dfl = dfl.sort_values("score_anomalie", ascending=False)

    cols_par_ligne = 8
    k = 0
    max_show = 24
    for _ in range(math.ceil(min(len(dfl), max_show) / cols_par_ligne)):
        cols = st.columns(cols_par_ligne)
        for c in cols:
            if k >= min(len(dfl), max_show):
                break
            r = dfl.iloc[k]
            fr = int(r["frame_curr"])
            if 0 <= fr < n:
                vis = encadrer_rouge_cv2(cv2, imgs[fr], e=8)
                cap = f"t={float(r['t']):.2f}s • frame {fr} • score={float(r['score_anomalie']):.3f}"
                c.image(vis, caption=cap, use_container_width=False)
            k += 1

# -------- Tableau et export --------
st.subheader("Tableau et export")
colonnes_aff = ["t", "etape", "frame_prev", "frame_curr", *res["cols"], "score_anomalie", "anomalie"]
if "x" in df and "y" in df:
    colonnes_aff += ["x", "y"]
st.dataframe(df[colonnes_aff])
st.download_button(
    "Télécharger les scores (CSV)",
    data=df[colonnes_aff].to_csv(index=False).encode("utf-8"),
    file_name="scores_anomalies.csv",
    mime="text/csv"
)
