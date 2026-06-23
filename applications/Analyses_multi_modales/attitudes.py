# attitudes.py
# Extraction d'attitudes non verbales à partir d'IMAGES (pas de vidéo)
# Si DeepFace et YOLOv8 sont disponibles, on calcule quelques indicateurs simples :
# - ouverture de la bouche (bouche_ouverture) via les repères du détecteur facial
# - orientation approximative de la tête (orientation_tete) via les yeux
# - ouverture des épaules (ouverture_epaules) via le modèle pose YOLOv8
# - nombre de mains visibles (nb_mains) via les poignets détectés
# Les résultats sont renvoyés par image + une agrégation temporelle (seconde).

import io
import math
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw
import altair as alt

try:
    from deepface_compat import DEFAULT_BACKEND as _DF_BACKEND, detect_faces as _df_detect_faces
    _deepface_ok = True
    _deepface_err = ""
except Exception as exc:  # pragma: no cover - dépend des installs
    _deepface_ok = False
    _deepface_err = str(exc)
    _df_detect_faces = None  # type: ignore[assignment]
    _DF_BACKEND = "retinaface"

try:
    from ultralytics import YOLO
except Exception as exc:  # pragma: no cover - dépend des installs
    YOLO = None  # type: ignore[assignment]
    _yolo_ok = False
    _yolo_err = str(exc)
else:
    _yolo_ok = True
    _yolo_err = ""

_POSE_MODEL_NAME = "yolov8n-pose.pt"
_POSE_MODEL = None
_POSE_MODEL_FAILED = False
_POSE_MODEL_ERR = ""


# =========================
# utilitaires internes
# =========================

def _pil_from_bytes(b: bytes):
    """ouvrir une image PIL depuis des octets."""
    try:
        return Image.open(io.BytesIO(b)).convert("RGB")
    except Exception:
        return None

def _to_np(img_pil):
    """convertir PIL -> np.array float32 [0..1] en RGB."""
    arr = np.asarray(img_pil)
    if arr.dtype != np.uint8:
        arr = (255 * (arr / np.max(arr))).astype(np.uint8)
    return arr

def _dist(p1, p2):
    """distance euclidienne 2D."""
    return float(math.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def _ensure_pose_model():
    """Charge le modèle YOLOv8 pose une seule fois (si disponible)."""

    global _POSE_MODEL, _POSE_MODEL_FAILED, _POSE_MODEL_ERR
    if not _yolo_ok or YOLO is None:
        return None
    if _POSE_MODEL is not None:
        return _POSE_MODEL
    if _POSE_MODEL_FAILED:
        return None
    try:
        _POSE_MODEL = YOLO(_POSE_MODEL_NAME)
        return _POSE_MODEL
    except Exception as exc:  # pragma: no cover - dépend des installs
        _POSE_MODEL_FAILED = True
        _POSE_MODEL_ERR = str(exc)
        return None

def _draw_boxes_on_image(
    img: Image.Image,
    boxes: list[tuple[int, int, int, int]],
    color=(0, 255, 0),
    width: int = 4,
) -> Image.Image:
    """Dessine des rectangles de couleur sur une copie de l'image fournie."""
    annotated = img.copy()
    draw = ImageDraw.Draw(annotated)
    for box in boxes:
        draw.rectangle(box, outline=color, width=width)
    return annotated


# =========================
# calcul indicateurs (DeepFace + YOLOv8 si dispo)
# =========================

def _analyse_image_deepface(arr_rgb: np.ndarray, backend: str | None = None) -> dict:
    """Analyse du visage via DeepFace (ou implémentation locale)."""

    if not _deepface_ok or _df_detect_faces is None:
        return {
            "bouche_ouverture": np.nan,
            "orientation_tete": np.nan,
            "face_box": None,
        }

    try:
        detections = _df_detect_faces(
            arr_rgb,
            detector_backend=(backend or _DF_BACKEND),
            align=False,
            enforce_detection=False,
        )
    except Exception:
        detections = []

    if not detections:
        return {
            "bouche_ouverture": np.nan,
            "orientation_tete": np.nan,
            "face_box": None,
        }

    best = max(detections, key=lambda d: float(d.get("confidence", 0.0)))
    landmarks = best.get("landmarks") or {}

    def _lm(key):
        pt = landmarks.get(key)
        if pt is None:
            return None
        try:
            x, y = float(pt[0]), float(pt[1])
        except Exception:
            return None
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return (x, y)

    left_eye = _lm("left_eye")
    right_eye = _lm("right_eye")
    mouth_left = _lm("mouth_left")
    mouth_right = _lm("mouth_right")

    bouche_ouverture = np.nan
    orientation_tete = np.nan

    if left_eye and right_eye:
        dx = right_eye[0] - left_eye[0]
        dy = right_eye[1] - left_eye[1]
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            orientation_tete = float(math.degrees(math.atan2(dy, dx)))

    if left_eye and right_eye and mouth_left and mouth_right:
        inter_oc = _dist(left_eye, right_eye)
        bouche = _dist(mouth_left, mouth_right)
        if inter_oc > 1e-6:
            bouche_ouverture = bouche / inter_oc

    return {
        "bouche_ouverture": bouche_ouverture,
        "orientation_tete": orientation_tete,
        "face_box": tuple(best.get("box", ())) or None,
    }


def _analyse_image_pose(arr_rgb: np.ndarray) -> dict:
    """Analyse du corps via YOLOv8 pose (épaules + mains)."""

    h, w = arr_rgb.shape[:2]
    default = {
        "ouverture_epaules": np.nan,
        "nb_mains": 0,
        "hand_boxes": [],
    }

    model = _ensure_pose_model()
    if model is None:
        return default

    try:
        results = model(arr_rgb, verbose=False)
    except Exception:
        return default

    if not results:
        return default

    pred = results[0]
    keypoints = getattr(pred, "keypoints", None)
    if keypoints is None or getattr(keypoints, "xy", None) is None:
        return default

    def _tensor_to_np(tensor):
        try:
            return tensor.detach().cpu().numpy()
        except Exception:
            try:
                return tensor.cpu().numpy()
            except Exception:
                return None

    kp_xy = _tensor_to_np(keypoints.xy)
    if kp_xy is None or kp_xy.size == 0:
        return default

    boxes = getattr(pred, "boxes", None)
    kp_conf = getattr(keypoints, "conf", None)
    conf_arr = _tensor_to_np(kp_conf) if kp_conf is not None else None
    boxes_conf = None
    if boxes is not None and getattr(boxes, "conf", None) is not None:
        boxes_conf = _tensor_to_np(boxes.conf)

    idx = 0
    if boxes_conf is not None and boxes_conf.size > 0:
        idx = int(np.argmax(boxes_conf))
    idx = max(0, min(idx, kp_xy.shape[0] - 1))

    pts = kp_xy[idx]
    conf_idx = conf_arr[idx] if conf_arr is not None and conf_arr.ndim >= 2 else (
        conf_arr if conf_arr is not None else None
    )

    def _kp(idk: int):
        if idk >= pts.shape[0]:
            return None
        x, y = float(pts[idk][0]), float(pts[idk][1])
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        if conf_idx is not None:
            try:
                cval = float(conf_idx[idk])
            except Exception:
                cval = float(conf_idx)
            if cval < 0.25:
                return None
        return (x, y)

    left_shoulder = _kp(5)
    right_shoulder = _kp(6)
    left_wrist = _kp(9)
    right_wrist = _kp(10)

    ouverture_epaules = np.nan
    if left_shoulder and right_shoulder:
        ouverture_epaules = _dist(left_shoulder, right_shoulder) / max(1.0, float(w))

    nb_mains = sum(1 for pt in (left_wrist, right_wrist) if pt is not None)

    boxes_xyxy = None
    if boxes is not None and getattr(boxes, "xyxy", None) is not None:
        boxes_xyxy = _tensor_to_np(boxes.xyxy)

    ref_size = 0.15 * min(float(w), float(h))
    if boxes_xyxy is not None and len(boxes_xyxy) > idx:
        x1, y1, x2, y2 = boxes_xyxy[idx]
        bw = float(x2 - x1)
        bh = float(y2 - y1)
        ref_size = max(20.0, 0.3 * min(abs(bw), abs(bh)))
    else:
        ref_size = max(20.0, ref_size)

    def _box_from_point(pt):
        if pt is None:
            return None
        size = ref_size
        x1 = int(max(0.0, pt[0] - size / 2.0))
        y1 = int(max(0.0, pt[1] - size / 2.0))
        x2 = int(min(float(w), pt[0] + size / 2.0))
        y2 = int(min(float(h), pt[1] + size / 2.0))
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1, y1, x2, y2)

    hand_boxes = [
        box
        for box in (_box_from_point(left_wrist), _box_from_point(right_wrist))
        if box is not None
    ]

    return {
        "ouverture_epaules": ouverture_epaules,
        "nb_mains": int(nb_mains),
        "hand_boxes": hand_boxes,
    }


# =========================
# API demandée par main.py
# =========================

def calculer_attitudes_depuis_images(
    images_store,
    activer_openface: bool = True,
    activer_mediapipe: bool = True,
    activer_openpose: bool = False,
    chemin_openface: str = "FeatureExtraction",
    binaire_openpose: str = "openpose",
    activer_deepface: bool = True,
    activer_yolov8: bool = True,
    backend_deepface: str | None = None,
    modele_yolov8_pose: str | None = None,
):
    """
    calculer les attitudes à partir des images déjà chargées dans st.session_state["images_store"]
    images_store: liste de dicts {"name": str, "bytes": bytes}
    renvoie (df_nv_images, df_nv_agrege)

    Remarque :
    - OpenFace et OpenPose ne sont pas exécutés ici (binaire externe requis).
      On expose malgré tout des colonnes 'au_*' et 'openpose_ok' à NaN/False pour compatibilité.
    - Si DeepFace ou YOLOv8 ne sont pas disponibles (ou désactivés), des NaN seront renvoyés et un avertissement affiché.
    - Les timestamps sont récupérés depuis st.session_state["df_images"] (colonne t_image).
    """

    global _POSE_MODEL_NAME, _POSE_MODEL, _POSE_MODEL_FAILED, _POSE_MODEL_ERR

    if not activer_mediapipe:
        activer_deepface = False
        activer_yolov8 = False

    if modele_yolov8_pose and modele_yolov8_pose != _POSE_MODEL_NAME:
        _POSE_MODEL_NAME = modele_yolov8_pose
        _POSE_MODEL = None
        _POSE_MODEL_FAILED = False
        _POSE_MODEL_ERR = ""

    if images_store is None or len(images_store) == 0:
        return pd.DataFrame(columns=[
            "fichier_image", "t_image",
            "bouche_ouverture", "orientation_tete", "ouverture_epaules", "nb_mains",
            "au_01", "au_02", "au_04", "au_06", "au_12", "openpose_ok"
        ]), pd.DataFrame()

    df_images_meta = st.session_state.get("df_images")
    if df_images_meta is None or df_images_meta.empty:
        # on crée une meta minimale sans timestamp
        df_images_meta = pd.DataFrame([{"fichier_image": it["name"], "t_image": np.nan} for it in images_store])

    # index rapide: nom -> t_image
    t_by_name = {row["fichier_image"]: row["t_image"] for _, row in df_images_meta.iterrows()}

    lignes = []
    for it in images_store:
        name = it["name"]
        b = it["bytes"]

        img = _pil_from_bytes(b)
        if img is None:
            # image illisible
            lignes.append({
                "fichier_image": name,
                "t_image": float(t_by_name.get(name, np.nan)),
                "bouche_ouverture": np.nan,
                "orientation_tete": np.nan,
                "ouverture_epaules": np.nan,
                "nb_mains": 0,
                "hand_boxes": [],
                "image_annotee": None,
                # placeholders OpenFace/OpenPose
                "au_01": np.nan, "au_02": np.nan, "au_04": np.nan, "au_06": np.nan, "au_12": np.nan,
                "openpose_ok": False
            })
            continue

        arr = _to_np(img)

        # DeepFace / YOLOv8 si demandés et disponibles
        if activer_deepface and _deepface_ok:
            face_feats = _analyse_image_deepface(arr, backend=backend_deepface)
        else:
            face_feats = {"bouche_ouverture": np.nan, "orientation_tete": np.nan, "face_box": None}

        if activer_yolov8:
            pose_feats = _analyse_image_pose(arr)
        else:
            pose_feats = {"ouverture_epaules": np.nan, "nb_mains": 0, "hand_boxes": []}

        hand_boxes = pose_feats.get("hand_boxes", [])
        try:
            annotated_img = _draw_boxes_on_image(img, hand_boxes)
            buf = io.BytesIO()
            annotated_img.save(buf, format="PNG")
            annotated_bytes = buf.getvalue()
        except Exception:
            annotated_bytes = None

        # OpenFace / OpenPose non exécutés ici (binaire externe requis)
        au_01 = np.nan
        au_02 = np.nan
        au_04 = np.nan
        au_06 = np.nan
        au_12 = np.nan
        openpose_ok = False

        lignes.append({
            "fichier_image": name,
            "t_image": float(t_by_name.get(name, np.nan)),
            "bouche_ouverture": face_feats.get("bouche_ouverture", np.nan),
            "orientation_tete": face_feats.get("orientation_tete", np.nan),
            "ouverture_epaules": pose_feats.get("ouverture_epaules", np.nan),
            "nb_mains": pose_feats.get("nb_mains", 0),
            "hand_boxes": hand_boxes,
            "image_annotee": annotated_bytes,
            "au_01": au_01, "au_02": au_02, "au_04": au_04, "au_06": au_06, "au_12": au_12,
            "openpose_ok": openpose_ok
        })

    df_nv_images = pd.DataFrame(lignes)

    # agrégation simple par seconde (floor)
    df_agg = df_nv_images.copy()
    if "t_image" in df_agg.columns:
        df_agg["t_sec"] = np.floor(df_agg["t_image"].astype(float)).astype("Int64")
    else:
        df_agg["t_sec"] = pd.NA

    agg_cols_mean = ["bouche_ouverture", "orientation_tete", "ouverture_epaules"]
    agg_cols_sum = ["nb_mains"]

    df_mean = df_agg.groupby("t_sec", dropna=True)[agg_cols_mean].mean().reset_index()
    df_sum  = df_agg.groupby("t_sec", dropna=True)[agg_cols_sum].sum().reset_index()
    df_nv_agrege = pd.merge(df_mean, df_sum, on="t_sec", how="outer").sort_values("t_sec")

    if activer_deepface and (not _deepface_ok or _df_detect_faces is None):
        msg = "DeepFace n’est pas disponible. Les indicateurs visage sont renvoyés en NaN."
        if _deepface_err:
            msg += f" (détail: {_deepface_err})"
        st.warning(msg)
    if activer_yolov8:
        if not _yolo_ok or YOLO is None:
            msg = "YOLOv8 n’est pas disponible. Les indicateurs pose/mains sont renvoyés en NaN."
            if _yolo_err:
                msg += f" (détail: {_yolo_err})"
            st.warning(msg)
        elif _POSE_MODEL_FAILED:
            msg = (
                f"Le modèle YOLOv8 pose '{_POSE_MODEL_NAME}' n’a pas pu être chargé. "
                "Les indicateurs pose/mains sont renvoyés en NaN."
            )
            if _POSE_MODEL_ERR:
                msg += f" (détail: {_POSE_MODEL_ERR})"
            st.warning(msg)

    return df_nv_images, df_nv_agrege


def ui_attitudes_images(df_nv_images: pd.DataFrame, df_nv_agrege: pd.DataFrame):
    """
    interface Streamlit pour visualiser les attitudes calculées à partir des images.
    Affiche tableaux + graphiques Altair temporels (par seconde).
    """
    if df_nv_images is None or df_nv_images.empty:
        st.info("Aucun résultat d’attitudes à afficher pour les images.")
        return

    st.markdown("**Résultats par image**")
    df_affichage = df_nv_images.drop(columns=["image_annotee", "hand_boxes"], errors="ignore")
    st.dataframe(df_affichage)

    if df_nv_agrege is not None and not df_nv_agrege.empty:
        st.markdown("**Agrégation temporelle (par seconde)**")
        st.dataframe(df_nv_agrege)

        # courbe bouche_ouverture
        if "bouche_ouverture" in df_nv_agrege.columns:
            c1 = alt.Chart(df_nv_agrege).mark_line(point=True).encode(
                x=alt.X("t_sec:Q", title="Temps (s)"),
                y=alt.Y("bouche_ouverture:Q", title="Ouverture de la bouche (rat.)")
            ).properties(height=220, title="Bouche – ouverture")
            st.altair_chart(c1, use_container_width=True)

        # courbe orientation_tete
        if "orientation_tete" in df_nv_agrege.columns:
            c2 = alt.Chart(df_nv_agrege).mark_line(point=True).encode(
                x=alt.X("t_sec:Q", title="Temps (s)"),
                y=alt.Y("orientation_tete:Q", title="Orientation tête (°)")
            ).properties(height=220, title="Tête – orientation (approx.)")
            st.altair_chart(c2, use_container_width=True)

        # courbe ouverture_epaules
        if "ouverture_epaules" in df_nv_agrege.columns:
            c3 = alt.Chart(df_nv_agrege).mark_line(point=True).encode(
                x=alt.X("t_sec:Q", title="Temps (s)"),
                y=alt.Y("ouverture_epaules:Q", title="Ouverture épaules (norm.)")
            ).properties(height=220, title="Posture – ouverture des épaules")
            st.altair_chart(c3, use_container_width=True)

        # barres sur nb_mains
        if "nb_mains" in df_nv_agrege.columns:
            c4 = alt.Chart(df_nv_agrege).mark_bar().encode(
                x=alt.X("t_sec:Q", title="Temps (s)"),
                y=alt.Y("nb_mains:Q", title="Mains visibles (somme)")
            ).properties(height=220, title="Mains visibles")
            st.altair_chart(c4, use_container_width=True)

    else:
        st.caption("Aucune agrégation disponible.")

    # prévisualisations d'images annotées
    images_annotees: list[bytes] = []
    captions: list[str] = []
    for _, row in df_nv_images.iterrows():
        data = row.get("image_annotee")
        if not isinstance(data, (bytes, bytearray)):
            continue
        images_annotees.append(bytes(data))
        nom = row.get("fichier_image", "") or ""
        nb_mains = row.get("nb_mains")
        try:
            nb_mains_txt = int(nb_mains) if pd.notna(nb_mains) else "NA"
        except Exception:
            nb_mains_txt = nb_mains
        t_val = row.get("t_image")
        if isinstance(t_val, (int, float)) and np.isfinite(t_val):
            t_txt = f"t={t_val:.2f}s"
        else:
            t_txt = "t=?"
        captions.append(f"{nom} – {t_txt} – mains: {nb_mains_txt}")

    if images_annotees:
        st.markdown("**Images annotées (mains encadrées en vert)**")
        st.image(images_annotees, caption=captions, width=260)
