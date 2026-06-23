"""Utilitaires pour gérer différents modèles de détection de visages.

Ce module centralise la création de détecteurs afin de proposer une
interface homogène entre RetinaFace et YOLOv8. Il gère également les
dépendances optionnelles : chaque détecteur est importé et initialisé à
la demande, et des messages explicites sont levés si la bibliothèque
correspondante n'est pas installée.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

try:
    from retinaface import RetinaFace
except Exception:  # pragma: no cover - dépend de l'environnement
    RetinaFace = None

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - dépend de l'environnement
    YOLO = None


@dataclass
class DetectionResult:
    """Résultat d'une détection de visage."""

    box: Tuple[int, int, int, int]
    confidence: float
    landmarks: Optional[Dict[str, Tuple[int, int]]] = None

    def as_slice(
        self, shape: Optional[Tuple[int, int]] = None
    ) -> Tuple[slice, slice]:
        """Retourne les slices x/y correspondant à la boîte (clippée)."""

        x1, y1, x2, y2 = self.box
        if shape is not None:
            height, width = shape[:2]
            x1 = max(0, min(width, x1))
            x2 = max(0, min(width, x2))
            y1 = max(0, min(height, y1))
            y2 = max(0, min(height, y2))
        if x2 <= x1 or y2 <= y1:
            return slice(0, 0), slice(0, 0)
        return slice(y1, y2), slice(x1, x2)


class BaseDetector:
    """Interface commune de tous les détecteurs."""

    backend_name: str = "base"

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        raise NotImplementedError

    @staticmethod
    def _ensure_bgr(image: np.ndarray) -> np.ndarray:
        if image is None:
            raise ValueError("Image invalide (None)")
        if image.ndim == 2:
            return np.stack([image] * 3, axis=-1)
        if image.shape[2] == 4:  # RGBA -> RGB
            return image[:, :, :3]
        return image


class RetinaFaceDetector(BaseDetector):
    backend_name = "retinaface"

    def __init__(self, model: str = "retinaface") -> None:
        if RetinaFace is None:  # pragma: no cover - dépend de l'environnement
            raise ImportError(
                "RetinaFace n'est pas disponible : pip install retina-face"
            )
        self._model = model

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        img = self._ensure_bgr(image)
        detections = RetinaFace.detect_faces(img, model=self._model)
        results: List[DetectionResult] = []
        if isinstance(detections, dict):
            for det in detections.values():
                x1, y1, x2, y2 = det["facial_area"]
                score = float(det.get("score", 0.0))
                landmarks = det.get("landmarks")
                if isinstance(landmarks, dict):
                    lm = {k: (int(v[0]), int(v[1])) for k, v in landmarks.items()}
                else:
                    lm = None
                results.append(
                    DetectionResult((int(x1), int(y1), int(x2), int(y2)), score, lm)
                )
        return results


class YoloV8Detector(BaseDetector):
    backend_name = "yolov8"

    def __init__(self, model_name: str = "yolov8n-face.pt") -> None:
        if YOLO is None:  # pragma: no cover - dépend de l'environnement
            raise ImportError("YOLOv8 n'est pas disponible : pip install ultralytics")
        self._model = YOLO(model_name)

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        img = self._ensure_bgr(image)
        results = self._model(img, verbose=False)
        detections: List[DetectionResult] = []
        for res in results:
            boxes = res.boxes
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy.cpu().numpy().astype(int).tolist()[0]
                conf = float(box.conf.cpu().numpy().tolist()[0])
                detections.append(DetectionResult(tuple(xyxy), conf))
        return detections


_DETECTOR_FACTORIES = {
    RetinaFaceDetector.backend_name: RetinaFaceDetector,
    YoloV8Detector.backend_name: YoloV8Detector,
}


def available_detectors() -> Iterable[str]:
    """Retourne la liste des backends détecteurs disponibles."""

    names: List[str] = []
    for name, cls in _DETECTOR_FACTORIES.items():
        try:
            create_detector(name)
        except Exception:
            continue
        else:
            names.append(name)
    return names


@lru_cache(maxsize=None)
def create_detector(name: str) -> BaseDetector:
    """Instancie (avec mise en cache) un détecteur pour le backend donné."""

    key = name.lower().strip()
    if key not in _DETECTOR_FACTORIES:
        raise ValueError(f"Backend inconnu : {name}")
    cls = _DETECTOR_FACTORIES[key]
    return cls()


def detect(image: np.ndarray, backend: str) -> List[DetectionResult]:
    """Fonction utilitaire directe pour détecter des visages."""

    detector = create_detector(backend)
    return detector.detect(image)
