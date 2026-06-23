from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _normalize_embedding(vector: np.ndarray | None) -> np.ndarray | None:
    if vector is None:
        return None
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    if array.size == 0:
        return None
    norm = float(np.linalg.norm(array))
    if norm <= 0:
        return None
    return (array / norm).astype(np.float32)


def _box_center(box: tuple[int, int, int, int] | None, fallback: tuple[float, float]) -> tuple[float, float]:
    if not box:
        return fallback
    x1, y1, x2, y2 = box
    return (float(x1 + x2) / 2.0, float(y1 + y2) / 2.0)


def _mouth_corners(box: tuple[int, int, int, int] | None, fallback_left: tuple[float, float], fallback_right: tuple[float, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    if not box:
        return fallback_left, fallback_right
    x1, y1, x2, y2 = box
    mid_y = float(y1 + y2) / 2.0
    return (float(x1), mid_y), (float(x2), mid_y)


def _default_nose(box: tuple[int, int, int, int] | None) -> tuple[float, float]:
    if not box:
        return 0.0, 0.0
    x1, y1, x2, y2 = box
    width = max(1.0, float(x2 - x1))
    height = max(1.0, float(y2 - y1))
    return float(x1) + (width * 0.5), float(y1) + (height * 0.56)


def resolve_arcface_model_path(explicit_model_path: str | Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit_model_path:
        candidates.append(Path(explicit_model_path).expanduser())

    env_path = str(os.environ.get("IRAMUTEQ_ARCFACE_MODEL", "") or "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    base_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            base_dir / "models" / "arcface.onnx",
            base_dir / "models" / "face_recognition_sface_2021dec.onnx",
            base_dir / "models" / "face_recognition_sface_2021dec_int8.onnx",
        ]
    )

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            resolved = candidate
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def build_arcface_face_input(candidate: dict[str, Any]) -> np.ndarray | None:
    roi_box = candidate.get("roi_box")
    if not roi_box or len(roi_box) < 4:
        return None
    x1, y1, x2, y2 = [float(value) for value in roi_box[:4]]
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)

    identity_keypoints = candidate.get("identity_keypoints", {}) or {}
    subboxes = candidate.get("subboxes", {}) or {}

    left_eye = identity_keypoints.get("left_eye")
    right_eye = identity_keypoints.get("right_eye")
    nose = identity_keypoints.get("nose")
    mouth_left = identity_keypoints.get("mouth_left")
    mouth_right = identity_keypoints.get("mouth_right")

    default_left_eye = (x1 + (width * 0.34), y1 + (height * 0.38))
    default_right_eye = (x1 + (width * 0.66), y1 + (height * 0.38))

    left_eye = _box_center(subboxes.get("left_eye"), left_eye or default_left_eye)
    right_eye = _box_center(subboxes.get("right_eye"), right_eye or default_right_eye)

    default_mouth_left = (x1 + (width * 0.38), y1 + (height * 0.74))
    default_mouth_right = (x1 + (width * 0.62), y1 + (height * 0.74))
    mouth_left, mouth_right = _mouth_corners(
        subboxes.get("mouth"),
        mouth_left or default_mouth_left,
        mouth_right or default_mouth_right,
    )
    nose = tuple(nose or _default_nose((int(x1), int(y1), int(x2), int(y2))))

    return np.asarray(
        [
            x1,
            y1,
            width,
            height,
            float(left_eye[0]),
            float(left_eye[1]),
            float(right_eye[0]),
            float(right_eye[1]),
            float(nose[0]),
            float(nose[1]),
            float(mouth_left[0]),
            float(mouth_left[1]),
            float(mouth_right[0]),
            float(mouth_right[1]),
        ],
        dtype=np.float32,
    )


class NullSelectionBackend:
    backend_name = "local"
    active = False
    warning = ""
    model_path = ""

    def annotate_candidates(self, frame_bgr: np.ndarray, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        _ = frame_bgr
        for candidate in candidates:
            candidate.setdefault("identity_backend", self.backend_name)
        return candidates

    def descriptor_from_candidate(self, frame_bgr: np.ndarray, candidate: dict[str, Any]) -> np.ndarray | None:
        _ = frame_bgr
        _ = candidate
        return None


class ArcFaceSelectionBackend(NullSelectionBackend):
    backend_name = "arcface"

    def __init__(self, model_path: Path) -> None:
        self.model_path = str(model_path)
        self.warning = ""
        self.active = True
        self.recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")

    def descriptor_from_candidate(self, frame_bgr: np.ndarray, candidate: dict[str, Any]) -> np.ndarray | None:
        face_input = build_arcface_face_input(candidate)
        if face_input is None:
            return None
        try:
            aligned = self.recognizer.alignCrop(frame_bgr, face_input)
            features = self.recognizer.feature(aligned)
            return _normalize_embedding(np.asarray(features, dtype=np.float32))
        except Exception:
            return None

    def annotate_candidates(self, frame_bgr: np.ndarray, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for candidate in candidates:
            descriptor = self.descriptor_from_candidate(frame_bgr, candidate)
            if descriptor is not None:
                candidate["identity_embedding"] = descriptor
            candidate["identity_backend"] = self.backend_name
        return candidates


def create_face_selection_backend(explicit_model_path: str | Path | None = None):
    model_path = resolve_arcface_model_path(explicit_model_path)
    if model_path is None:
        backend = NullSelectionBackend()
        backend.warning = (
            "ArcFace n'a pas été activé : aucun modèle ONNX n'a été trouvé. "
            "Dépose un modèle dans multimodale/models/arcface.onnx "
            "ou définis IRAMUTEQ_ARCFACE_MODEL."
        )
        return backend
    try:
        return ArcFaceSelectionBackend(model_path)
    except Exception as exc:
        backend = NullSelectionBackend()
        backend.warning = f"ArcFace n'a pas pu être initialisé. Fallback local utilisé. Détail: {exc}"
        return backend
