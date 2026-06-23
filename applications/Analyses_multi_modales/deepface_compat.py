"""Shim local compatible DeepFace pour la détection de visages.

Le paquet `deepface` propose plusieurs backends de détection.  Dans ce
projet nous n'avons besoin que de la partie "détection", que nous
ré-implémentons avec une API compatible en nous appuyant sur
``modelesdetect``.  Les dépendances (OpenCV pour l'alignement,
RetinaFace, YOLOv8) restent optionnelles : seules celles réellement
utilisées doivent être installées.
"""
from __future__ import annotations

from typing import Iterable, List

import numpy as np

from modelesdetect import DetectionResult, available_detectors, create_detector

try:
    import cv2
except Exception as exc:  # pragma: no cover - dépend de l'environnement
    cv2 = None
    _cv2_error = exc
else:
    _cv2_error = None

DEFAULT_BACKEND = "retinaface"


def list_backends() -> Iterable[str]:
    """Expose la liste des backends disponibles."""

    return available_detectors()


def _load_image(img) -> np.ndarray:
    if isinstance(img, str):
        if cv2 is None:  # pragma: no cover - dépend de l'environnement
            raise ImportError(
                "OpenCV est requis pour charger un fichier image depuis un chemin."
            ) from _cv2_error
        data = cv2.imread(img)
        if data is None:
            raise ValueError(f"Impossible de lire l'image : {img}")
        return data

    arr = np.asarray(img)
    if arr.ndim not in (2, 3):
        raise ValueError(
            "L'image doit être un tableau 2D (niveau de gris) ou 3D (couleur)."
        )
    return arr


def _align_face(image: np.ndarray, detection: DetectionResult) -> np.ndarray:
    """Réaligne approximativement le visage si les yeux sont disponibles."""

    if cv2 is None or not detection.landmarks:
        y_slice, x_slice = detection.as_slice(image.shape)
        return image[y_slice, x_slice].copy()

    left = detection.landmarks.get("left_eye")
    right = detection.landmarks.get("right_eye")
    if not left or not right:
        y_slice, x_slice = detection.as_slice(image.shape)
        return image[y_slice, x_slice].copy()

    left_pt = np.array(left, dtype=np.float32)
    right_pt = np.array(right, dtype=np.float32)
    dy, dx = right_pt[1] - left_pt[1], right_pt[0] - left_pt[0]
    angle = np.degrees(np.arctan2(dy, dx))

    center_x = (detection.box[0] + detection.box[2]) / 2.0
    center_y = (detection.box[1] + detection.box[3]) / 2.0
    rot_mat = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)
    rotated = cv2.warpAffine(image, rot_mat, (image.shape[1], image.shape[0]))

    y_slice, x_slice = detection.as_slice(image.shape)
    return rotated[y_slice, x_slice].copy()


def detect_faces(
    img,
    detector_backend: str = DEFAULT_BACKEND,
    align: bool = True,
    enforce_detection: bool = True,
) -> List[dict]:
    """Détecte les visages et retourne une structure proche de DeepFace."""

    image = _load_image(img)
    detector = create_detector(detector_backend)
    detections = detector.detect(image)

    if enforce_detection and not detections:
        raise ValueError(
            "Aucun visage détecté. Désactivez `enforce_detection` pour continuer."
        )

    faces: List[dict] = []
    for det in detections:
        if align:
            crop = _align_face(image, det)
        else:
            y_slice, x_slice = det.as_slice(image.shape)
            crop = image[y_slice, x_slice].copy()
        faces.append(
            {
                "face": crop,
                "box": det.box,
                "confidence": det.confidence,
                "landmarks": det.landmarks,
            }
        )
    return faces


def extract_faces(
    img,
    detector_backend: str = DEFAULT_BACKEND,
    align: bool = True,
    enforce_detection: bool = True,
) -> List[np.ndarray]:
    """Retourne uniquement les crops de visages pour compatibilité DeepFace."""

    faces = detect_faces(
        img,
        detector_backend=detector_backend,
        align=align,
        enforce_detection=enforce_detection,
    )
    return [entry["face"] for entry in faces]


def verify_has_face(img, detector_backend: str = DEFAULT_BACKEND) -> bool:
    """Renvoie True si au moins un visage est détecté."""

    try:
        faces = detect_faces(img, detector_backend=detector_backend, align=False)
    except Exception:
        return False
    return bool(faces)


__all__ = [
    "DEFAULT_BACKEND",
    "detect_faces",
    "extract_faces",
    "list_backends",
    "verify_has_face",
]
