# emotions.py
# Détection d'émotions sur images fixes synchronisées – sortie 6 labels DeepFace (sans "neutral")

from __future__ import annotations
import io, os, json
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from PIL import Image, ImageOps, ImageDraw, ImageFont

# ===== Dépendances optionnelles
_DEEPFACE_ERR = ""
_CV2_ERR = ""
_XLSX_OK = False
try:
    import xlsxwriter  # type: ignore

    _XLSX_OK = True
except Exception:
    pass

try:
    import cv2  # type: ignore

    _CV2_OK = True
except Exception as exc:
    _CV2_OK = False
    _CV2_ERR = str(exc)

try:
    from deepface import DeepFace  # type: ignore

    _DEEPFACE_OK = True
except Exception as exc:
    _DEEPFACE_OK = False
    _DEEPFACE_ERR = str(exc)

try:
    import mediapipe as mp  # type: ignore

    _MP_OK = True
except Exception:
    _MP_OK = False

from modelesdetect import BaseDetector, create_detector

# ===== Constantes
EMO6 = ["angry", "disgust", "fear", "happy", "sad", "surprise"]  # 6 labels demandés
DETECTOR_BACKEND = "retinaface"
DEEPFACE_EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


# ===== Outils

def _img_from_bytes(b: bytes) -> Image.Image | None:
    try:
        im = Image.open(io.BytesIO(b))
        return ImageOps.exif_transpose(im).convert("RGB")
    except Exception:
        return None


def _to_numpy(im: Image.Image) -> np.ndarray:
    return np.array(im)


def _ensure_6(emotions: Dict[str, float]) -> Dict[str, float]:
    """
    Convertit un dictionnaire de scores d'émotions en 6 labels (sans 'neutral').
    - Supprime neutral s'il existe et renormalise
    - Ajoute les labels manquants à 0.0
    """
    if not isinstance(emotions, dict) or not emotions:
        return {k: 0.0 for k in EMO6}
    # supprime neutral
    emo = {k: float(v) for k, v in emotions.items() if k in EMO6}
    s = sum(emo.values())
    if s > 0:
        emo = {k: v / s for k, v in emo.items()}
    else:
        emo = {k: 0.0 for k in EMO6}
    # complète clés manquantes
    for k in EMO6:
        emo.setdefault(k, 0.0)
    return emo


def _top_emo6(emotions_6: Dict[str, float]) -> Tuple[str, float]:
    if not emotions_6:
        return "none", 0.0
    k = max(emotions_6.items(), key=lambda x: x[1])
    return k[0], float(k[1])


# ===== Modèles

@st.cache_resource(show_spinner=False)
def _load_deepface_emotion_model() -> Tuple[Any | None, str]:
    if not _DEEPFACE_OK:
        msg = "Le paquet `deepface` n’est pas disponible. Installez-le avec `pip install deepface`."
        if _DEEPFACE_ERR:
            msg += f" (détail: {_DEEPFACE_ERR})"
        return None, msg
    try:
        model = DeepFace.build_model("Emotion")  # type: ignore[attr-defined]
        return model, "Modèle d’émotions DeepFace initialisé."
    except Exception as e:
        return None, f"Échec init DeepFace Emotion: {e}"


@st.cache_resource(show_spinner=False)
def _load_detector_backend() -> Tuple[BaseDetector | None, str]:
    try:
        detector = create_detector(DETECTOR_BACKEND)
        return detector, f"Détecteur visage ({DETECTOR_BACKEND}) prêt."
    except Exception as e:
        return None, f"Échec chargement détecteur {DETECTOR_BACKEND}: {e}"


@st.cache_resource(show_spinner=False)
def _load_cv2_face() -> Tuple[Any | None, str]:
    if not _CV2_OK:
        return None, "OpenCV indisponible."
    try:
        cascade = cv2.CascadeClassifier(
            os.path.join(getattr(cv2.data, "haarcascades", ""), "haarcascade_frontalface_default.xml")
        )
        if cascade.empty():
            return None, "Cascade de visage OpenCV introuvable."
        return cascade, "Cascade OpenCV chargée."
    except Exception as e:
        return None, f"Échec cascade OpenCV: {e}"


@st.cache_resource(show_spinner=False)
def _load_mediapipe_face() -> Tuple[Any | None, str]:
    """Charge le détecteur de visage MediaPipe (plus précis pour le centrage)."""
    if not _MP_OK:
        return None, "MediaPipe indisponible."
    try:
        # Retourne juste l'objet mp.solutions.face_detection, pas une instance
        # car on ne peut pas cacher une instance qui doit être fermée
        return mp.solutions.face_detection, "MediaPipe FaceDetection disponible."
    except Exception as e:
        return None, f"Échec MediaPipe: {e}"


# ===== Pipelines

def _detector_faces(detector: BaseDetector | None, arr: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], float]]:
    """Retourne les boîtes détectées par le backend choisi."""

    if detector is None:
        return []
    try:
        detections = detector.detect(arr)
    except Exception:
        return []
    boxes: List[Tuple[Tuple[int, int, int, int], float]] = []
    for det in detections:
        try:
            x1, y1, x2, y2 = [int(v) for v in det.box]
        except Exception:
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        conf = float(getattr(det, "confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
        boxes.append(((x1, y1, x2, y2), conf))
    return boxes


def _predict_deepface_emotions(model: Any | None, face: np.ndarray) -> Tuple[Dict[str, float], str, float]:
    if model is None or face.size == 0:
        return {k: 0.0 for k in EMO6}, "none", 0.0
    try:
        gray = Image.fromarray(face).convert("L").resize((48, 48), Image.BILINEAR)
        arr = np.array(gray, dtype="float32") / 255.0
        arr = arr.reshape((1, 48, 48, 1))
        preds = model.predict(arr, verbose=0)
        preds_arr = np.asarray(preds, dtype="float32").reshape(-1)
        emotions = {
            emo: float(preds_arr[i])
            for i, emo in enumerate(DEEPFACE_EMOTIONS[: len(preds_arr)])
        }
        emo6 = _ensure_6(emotions)
        lab, sc = _top_emo6(emo6)
        return emo6, lab, sc
    except Exception:
        return {k: 0.0 for k in EMO6}, "none", 0.0


def _cv2_faces(cascade: Any, arr: np.ndarray) -> List[Tuple[int, int, int, int]]:
    try:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(36, 36))
        out = []
        for (x, y, w, h) in faces:
            if w > 0 and h > 0:
                out.append((int(x), int(y), int(x + w), int(y + h)))
        return out
    except Exception:
        return []


def _mediapipe_faces(mp_face_detection: Any, arr: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Détecte les visages avec MediaPipe (plus précis pour le centrage)."""
    try:
        H, W = arr.shape[:2]
        with mp_face_detection.FaceDetection(
                model_selection=1,  # 1 = full range (meilleur pour visages éloignés)
                min_detection_confidence=0.5
        ) as face_detection:
            results = face_detection.process(arr)
            if not results.detections:
                return []

            faces = []
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                # Conversion en pixels absolus
                x = int(bbox.xmin * W)
                y = int(bbox.ymin * H)
                w = int(bbox.width * W)
                h = int(bbox.height * H)
                # Borner à l'image
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(W, x + w)
                y2 = min(H, y + h)
                if x2 > x1 and y2 > y1:
                    faces.append((x1, y1, x2, y2))
            return faces
    except Exception:
        return []


def _crop(arr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    x1 = max(0, min(arr.shape[1] - 1, x1))
    y1 = max(0, min(arr.shape[0] - 1, y1))
    x2 = max(x1 + 1, min(arr.shape[1], x2))
    y2 = max(y1 + 1, min(arr.shape[0], y2))
    return arr[y1:y2, x1:x2]


def _analyze_one_image(
        emotion_model: Any | None,
        detector_backend: BaseDetector | None,
        cv2_cascade: Any | None,
        mp_face_detection: Any | None,
        b: bytes
) -> List[Dict[str, Any]]:
    """
    Sortie: liste de {bbox:(x1,y1,x2,y2), emotions_6:dict, label:str, score:float}
    - 1) Détection via le backend configuré (RetinaFace par défaut)
    - 2) Repli MediaPipe si aucune boîte détectée
    - 3) Repli cascade OpenCV en dernier recours
    """
    im = _img_from_bytes(b)
    if im is None:
        return []
    arr = _to_numpy(im)
    results: List[Dict[str, Any]] = []

    # 1) Détection principale via le backend configuré
    candidate_faces = _detector_faces(detector_backend, arr)

    # 2) Fallback : MediaPipe pour les boîtes si rien détecté
    if not candidate_faces and mp_face_detection is not None:
        faces_mediapipe = _mediapipe_faces(mp_face_detection, arr)
        candidate_faces = [((x1, y1, x2, y2), 0.0) for (x1, y1, x2, y2) in faces_mediapipe]

    # 3) Fallback final : cascade OpenCV
    if not candidate_faces and cv2_cascade is not None:
        faces_cv = _cv2_faces(cv2_cascade, arr)
        candidate_faces = [((x1, y1, x2, y2), 0.0) for (x1, y1, x2, y2) in faces_cv]

    for (x1, y1, x2, y2), det_score in candidate_faces:
        face = _crop(arr, x1, y1, x2, y2)
        emo6, lab, sc = _predict_deepface_emotions(emotion_model, face)
        # combine score with detection confidence to prioriser visages crédibles
        score = sc if det_score <= 0 else min(1.0, 0.5 * sc + 0.5 * float(det_score))
        results.append({"bbox": (x1, y1, x2, y2), "emotions_6": emo6, "label": lab, "score": score})

    # Classement: visage le plus crédible en premier (aire * score)
    if results:
        def _rank(r):
            x1, y1, x2, y2 = r["bbox"]
            return (x2 - x1) * (y2 - y1) * (0.25 + float(r.get("score", 0.0)))

        results.sort(key=_rank, reverse=True)
        for i, r in enumerate(results):
            r["face_id"] = i
            r["is_primary_face"] = (i == 0)

    return results


# ===== Rendu

def _draw_boxes(im: Image.Image, detections: List[Dict[str, Any]]) -> Image.Image:
    if not detections:
        return im
    im = im.copy()
    drw = ImageDraw.Draw(im)
    font = ImageFont.load_default()
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        drw.rectangle([(x1, y1), (x2, y2)], outline="green", width=3)
        lab = d["label"];
        sc = float(d.get("score", 0.0))
        tag = f"{'Visage principal' if d.get('is_primary_face') else 'Visage'}: {lab} ({sc:.2f})"
        tw, th = drw.textlength(tag, font=font), 11
        drw.rectangle([(x1, max(0, y1 - th - 6)), (x1 + int(tw) + 6, max(0, y1 - th - 6) + th + 4)], fill=(0, 128, 0))
        drw.text((x1 + 3, max(0, y1 - th - 6) + 2), tag, fill="white", font=font)
    return im


def _timestamp_from_df(df_images: pd.DataFrame | None, name: str) -> float | np.nan:
    if df_images is None or df_images.empty:
        return np.nan
    row = df_images[df_images["fichier_image"] == name]
    if row.empty:
        return np.nan
    v = row.iloc[0].get("t_image", np.nan)
    try:
        return float(v) if pd.notna(v) else np.nan
    except Exception:
        return np.nan


def _export_excel(df: pd.DataFrame, names: List[str]) -> Tuple[bytes | None, Dict[str, List[float]] | None]:
    if not _XLSX_OK:
        return None, None
    try:
        buffer = io.BytesIO()
        with xlsxwriter.Workbook(buffer, {"in_memory": True}) as wb:  # type: ignore[arg-type]
            ws = wb.add_worksheet()
            ws.write(0, 0, "Image")
            for j, emo in enumerate(EMO6, start=1):
                ws.write(0, j, emo)
            emo_data = {k: [] for k in EMO6}
            r = 1
            for name in names:
                sdf = df[df["fichier_image"] == name]
                mean = {k: 0.0 for k in EMO6}
                n = 0
                for _, row in sdf.iterrows():
                    scs = row.get("emotions_6", {})
                    if isinstance(scs, dict) and scs:
                        n += 1
                        for k in EMO6:
                            mean[k] += float(scs.get(k, 0.0))
                if n > 0:
                    for k in EMO6:
                        mean[k] /= n
                ws.write(r, 0, name)
                for j, emo in enumerate(EMO6, start=1):
                    ws.write(r, j, float(mean.get(emo, 0.0)))
                    emo_data[emo].append(float(mean.get(emo, 0.0)))
                r += 1
        buffer.seek(0)
        return buffer.getvalue(), emo_data
    except Exception:
        return None, None


# ===== UI principale

def ui_emotions_images(df_images: pd.DataFrame | None, orientation_images: str | None = None) -> None:
    st.subheader("Analyse des émotions (images, 6 labels DeepFace)")
    # Charger modèles
    emotion_model, msg_model = _load_deepface_emotion_model()
    st.caption(msg_model)
    if emotion_model is None:
        st.warning("Modèle DeepFace indisponible : impossible de lancer l’analyse des émotions.")
        return

    detector_backend, msg_detector = _load_detector_backend()
    st.caption(msg_detector)
    cv_cascade, msg_cv = _load_cv2_face()
    if cv_cascade is None:
        st.caption(msg_cv)
    mp_face_detection, msg_mp = _load_mediapipe_face()
    if mp_face_detection is not None:
        st.caption(msg_mp + " (solution de repli pour la détection)")

    images_store = st.session_state.get("images_store", []) or []
    names = [it["name"] for it in images_store if isinstance(it, dict) and "name" in it]
    if not names:
        st.info("Importe d’abord des images dans l’onglet « 1. Données ».")
        return

    results: List[Dict[str, Any]] = []
    annotated: List[Dict[str, Any]] = []

    with st.spinner("Détection en cours…"):
        for nm in names:
            b = None
            for it in images_store:
                if isinstance(it, dict) and it.get("name") == nm:
                    b = it.get("bytes")
                    break
            if b is None:
                continue

            dets = _analyze_one_image(emotion_model, detector_backend, cv_cascade, mp_face_detection, b)

            # Annoté
            im = _img_from_bytes(b)
            if im is None:
                continue
            annotated.append({"fichier_image": nm, "image": _draw_boxes(im, dets), "dets": dets})

            # Lignes de sortie
            timg = _timestamp_from_df(df_images, nm)
            for d in dets if dets else [
                {"bbox": (), "emotions_6": {k: 0.0 for k in EMO6}, "label": "none", "score": 0.0, "face_id": np.nan,
                 "is_primary_face": False}]:
                row = {
                    "fichier_image": nm,
                    "t_image": timg,
                    "face_id": d.get("face_id", np.nan),
                    "is_primary_face": bool(d.get("is_primary_face", False)),
                    "predicted_emotion": str(d.get("label", "none")),
                    "score": float(d.get("score", 0.0)),
                    "bbox": list(d.get("bbox", ())),
                    "emotions_6": d.get("emotions_6", {k: 0.0 for k in EMO6}),
                }
                results.append(row)

    if not results:
        st.warning("Aucun visage/émotion détecté.")
        return

    df = pd.DataFrame(results)
    # Colonnes 6 labels à plat (pour stats)
    for k in EMO6:
        df[f"emo_{k}"] = df["emotions_6"].apply(lambda d: float(d.get(k, 0.0)) if isinstance(d, dict) else 0.0)

    st.session_state["df_emotions"] = df.copy()

    st.markdown("#### Résultats (par visage)")
    show_cols = ["fichier_image", "t_image", "face_id", "is_primary_face", "predicted_emotion", "score", "bbox"] + [
        f"emo_{k}" for k in EMO6]
    st.dataframe(df[show_cols], use_container_width=True)

    # Distribution
    st.markdown("#### Répartition des émotions (6 labels)")
    distrib = df[df["predicted_emotion"] != "none"]["predicted_emotion"].value_counts().reindex(EMO6, fill_value=0)
    st.bar_chart(distrib)

    # Stream temporel (si timestamps)
    st.markdown("#### Évolution temporelle")
    dft = df[df["predicted_emotion"] != "none"].copy()
    if not dft.empty:
        if dft["t_image"].notna().any():
            dft["axe"] = dft["t_image"]
            xlabel = "Temps (s)"
        else:
            order = {n: i for i, n in enumerate(names)}
            dft["axe"] = dft["fichier_image"].map(order).astype(float)
            xlabel = "Ordre d’image"
        stream = (
            alt.Chart(dft)
            .mark_area()
            .encode(
                x=alt.X("axe:Q", title=xlabel),
                y=alt.Y("score:Q", stack="center", title="Confiance"),
                color=alt.Color("predicted_emotion:N", title="Émotion"),
                tooltip=["fichier_image", "predicted_emotion", "score"]
            ).properties(height=280)
        )
        st.altair_chart(stream, use_container_width=True)
    else:
        st.caption("Aucun point temporel exploitable.")

    # Vignettes annotées
    st.markdown("#### Vignettes annotées")
    size = st.slider("Largeur des vignettes (px)", 200, 800, 320, 20)
    ncols = 3
    rows = [annotated[i:i + ncols] for i in range(0, len(annotated), ncols)]
    for r in rows:
        cols = st.columns(len(r))
        for c, item in zip(cols, r):
            c.image(item["image"], caption=item["fichier_image"], width=size)
            dets = item["dets"]
            if dets:
                lignes = []
                for d in dets:
                    if d.get('is_primary_face'):
                        label_visage = 'Visage principal'
                    else:
                        label_visage = f"Visage {d.get('face_id')}"
                    lignes.append(f"- {label_visage} : **{d['label']}** ({d['score']:.2f})")
                c.markdown("\n".join(lignes))
            else:
                c.markdown("- Aucun visage détecté.")

    # Export
    st.markdown("#### Export")
    csv = df.drop(columns=["emotions_6"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Télécharger (CSV)", data=csv, file_name="emotions_images.csv", mime="text/csv")

    if _XLSX_OK:
        excel_bytes, emo_data = _export_excel(df, names)
        if excel_bytes:
            st.download_button(
                "Télécharger scores (Excel)",
                data=excel_bytes,
                file_name="emotions_scores.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.caption("xlsxwriter indisponible ou export impossible.")
