from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import cv2
import numpy as np


Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class TrackedFace:
    track_id: int
    box: Box
    face_order: int
    hits: int = 1
    age: int = 0
    missed: int = 0


def clamp_box(box: Box, shape: tuple[int, int] | tuple[int, int, int]) -> Box:
    height, width = shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(round(x1))))
    y1 = max(0, min(height - 1, int(round(y1))))
    x2 = max(x1 + 1, min(width, int(round(x2))))
    y2 = max(y1 + 1, min(height, int(round(y2))))
    return x1, y1, x2, y2


def box_area(box: Box | None) -> int:
    if not box:
        return 0
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def box_center(box: Box | None) -> tuple[float, float]:
    if not box:
        return 0.0, 0.0
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def box_center_norm(box: Box | None, shape: tuple[int, int] | tuple[int, int, int]) -> tuple[float, float]:
    if not box:
        return 0.0, 0.0
    height, width = shape[:2]
    cx, cy = box_center(box)
    return float(cx) / max(1, width), float(cy) / max(1, height)


def center_distance(box_a: Box | None, box_b: Box | None) -> float:
    ax, ay = box_center(box_a)
    bx, by = box_center(box_b)
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def intersection_over_union(box_a: Box | None, box_b: Box | None) -> float:
    if not box_a or not box_b:
        return 0.0
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    if inter_area <= 0:
        return 0.0
    union = box_area(box_a) + box_area(box_b) - inter_area
    if union <= 0:
        return 0.0
    return float(inter_area) / float(union)


def opencv_rects_to_xyxy(rects: Any) -> list[Box]:
    boxes: list[Box] = []
    if rects is None:
        return boxes
    for item in rects:
        if len(item) < 4:
            continue
        x, y, w, h = [int(v) for v in item[:4]]
        boxes.append((x, y, x + w, y + h))
    return boxes


def sort_boxes_left_to_right(boxes: list[Box], shape: tuple[int, int] | tuple[int, int, int]) -> list[Box]:
    clamped = [clamp_box(box, shape) for box in boxes if box_area(box) > 0]
    return sorted(clamped, key=lambda box: (box_center(box)[0], box_center(box)[1], -box_area(box)))


def select_primary_box(boxes: list[Box], shape: tuple[int, int] | tuple[int, int, int]) -> Box | None:
    if not boxes:
        return None
    clamped = [clamp_box(box, shape) for box in boxes]
    return max(clamped, key=box_area)


def create_face_records(
    boxes: list[Box],
    shape: tuple[int, int] | tuple[int, int, int],
    tracks: list[TrackedFace] | None = None,
) -> list[dict[str, Any]]:
    if tracks:
        ordered_tracks = sorted(tracks, key=lambda track: track.face_order)
        return [
            {
                "face_id": int(track.track_id),
                "face_order": int(track.face_order),
                "face_box_x1": int(track.box[0]),
                "face_box_y1": int(track.box[1]),
                "face_box_x2": int(track.box[2]),
                "face_box_y2": int(track.box[3]),
                "face_center_x_norm": round(box_center_norm(track.box, shape)[0], 6),
                "face_center_y_norm": round(box_center_norm(track.box, shape)[1], 6),
                "face_area_ratio": round(float(box_area(track.box)) / max(1, shape[0] * shape[1]), 6),
                "track_hits": int(track.hits),
                "track_age": int(track.age),
            }
            for track in ordered_tracks
        ]

    ordered_boxes = sort_boxes_left_to_right(boxes, shape)
    records: list[dict[str, Any]] = []
    for face_order, box in enumerate(ordered_boxes, start=1):
        center_x_norm, center_y_norm = box_center_norm(box, shape)
        records.append(
            {
                "face_id": face_order,
                "face_order": face_order,
                "face_box_x1": int(box[0]),
                "face_box_y1": int(box[1]),
                "face_box_x2": int(box[2]),
                "face_box_y2": int(box[3]),
                "face_center_x_norm": round(center_x_norm, 6),
                "face_center_y_norm": round(center_y_norm, 6),
                "face_area_ratio": round(float(box_area(box)) / max(1, shape[0] * shape[1]), 6),
                "track_hits": 1,
                "track_age": 0,
            }
        )
    return records


def track_detected_faces(
    boxes: list[Box],
    previous_tracks: list[TrackedFace],
    shape: tuple[int, int] | tuple[int, int, int],
    next_track_id: int,
    *,
    max_center_ratio: float = 0.18,
    min_iou: float = 0.08,
) -> tuple[list[TrackedFace], int]:
    ordered_boxes = sort_boxes_left_to_right(boxes, shape)
    if not ordered_boxes:
        return [], next_track_id

    height, width = shape[:2]
    frame_diag = math.sqrt(float(width * width + height * height))
    max_center_distance = max(24.0, frame_diag * max_center_ratio)
    available_previous = {index for index in range(len(previous_tracks))}
    tracks: list[TrackedFace] = []

    for face_order, box in enumerate(ordered_boxes, start=1):
        best_previous_index: int | None = None
        best_score = float("-inf")
        for previous_index in sorted(available_previous):
            previous_track = previous_tracks[previous_index]
            iou = intersection_over_union(box, previous_track.box)
            distance = center_distance(box, previous_track.box)
            if iou < min_iou and distance > max_center_distance:
                continue
            score = (iou * 2.0) + max(0.0, 1.0 - (distance / max_center_distance))
            if score > best_score:
                best_score = score
                best_previous_index = previous_index

        if best_previous_index is None:
            tracks.append(
                TrackedFace(
                    track_id=next_track_id,
                    box=box,
                    face_order=face_order,
                    hits=1,
                    age=0,
                    missed=0,
                )
            )
            next_track_id += 1
            continue

        previous_track = previous_tracks[best_previous_index]
        available_previous.discard(best_previous_index)
        tracks.append(
            TrackedFace(
                track_id=previous_track.track_id,
                box=box,
                face_order=face_order,
                hits=previous_track.hits + 1,
                age=previous_track.age + 1,
                missed=0,
            )
        )

    return tracks, next_track_id


def find_track_for_box(box: Box | None, tracks: list[TrackedFace]) -> TrackedFace | None:
    if not box:
        return None
    for track in tracks:
        if tuple(track.box) == tuple(box):
            return track
    best_track = None
    best_iou = 0.0
    for track in tracks:
        iou = intersection_over_union(box, track.box)
        if iou > best_iou:
            best_iou = iou
            best_track = track
    return best_track


def normalize_vector(vector: np.ndarray | None) -> np.ndarray | None:
    if vector is None:
        return None
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    if array.size == 0:
        return None
    norm = float(np.linalg.norm(array))
    if norm <= 0:
        return None
    return (array / norm).astype(np.float32)


def extract_face_crop(gray_frame: np.ndarray, box: Box | None, *, size: int = 96) -> np.ndarray | None:
    if box is None:
        return None
    x1, y1, x2, y2 = clamp_box(box, gray_frame.shape)
    crop = gray_frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    crop = cv2.equalizeHist(crop)
    return crop


def compute_lbp_histogram(image: np.ndarray, bins: int = 32) -> np.ndarray:
    if image.size == 0 or image.shape[0] < 3 or image.shape[1] < 3:
        return np.zeros((bins,), dtype=np.float32)
    center = image[1:-1, 1:-1]
    lbp = np.zeros_like(center, dtype=np.uint8)
    neighbors = [
        image[:-2, :-2],
        image[:-2, 1:-1],
        image[:-2, 2:],
        image[1:-1, 2:],
        image[2:, 2:],
        image[2:, 1:-1],
        image[2:, :-2],
        image[1:-1, :-2],
    ]
    for index, neighbor in enumerate(neighbors):
        lbp |= ((neighbor >= center).astype(np.uint8) << index)
    hist, _ = np.histogram(lbp, bins=bins, range=(0, 256))
    hist = hist.astype(np.float32)
    total = float(np.sum(hist))
    if total > 0:
        hist /= total
    return hist


def compute_hog_embedding(image: np.ndarray, cells: int = 4, bins: int = 8) -> np.ndarray:
    if image.size == 0:
        return np.zeros((cells * cells * bins,), dtype=np.float32)
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    angle = angle % 180.0
    height, width = image.shape[:2]
    cell_h = max(1, height // cells)
    cell_w = max(1, width // cells)
    features: list[np.ndarray] = []
    for row in range(cells):
        for col in range(cells):
            y1 = row * cell_h
            y2 = height if row == cells - 1 else min(height, (row + 1) * cell_h)
            x1 = col * cell_w
            x2 = width if col == cells - 1 else min(width, (col + 1) * cell_w)
            cell_mag = magnitude[y1:y2, x1:x2]
            cell_angle = angle[y1:y2, x1:x2]
            hist, _ = np.histogram(cell_angle, bins=bins, range=(0.0, 180.0), weights=cell_mag)
            hist = hist.astype(np.float32)
            norm = float(np.linalg.norm(hist))
            if norm > 0:
                hist /= norm
            features.append(hist)
    if not features:
        return np.zeros((cells * cells * bins,), dtype=np.float32)
    return np.concatenate(features).astype(np.float32)


def compute_dct_embedding(image: np.ndarray, block_size: int = 8) -> np.ndarray:
    if image.size == 0:
        return np.zeros((block_size * block_size - 1,), dtype=np.float32)
    float_image = image.astype(np.float32) / 255.0
    dct = cv2.dct(float_image)
    block = dct[:block_size, :block_size].reshape(-1)
    if block.size <= 1:
        return np.zeros((block_size * block_size - 1,), dtype=np.float32)
    block = block[1:]
    block = np.clip(block, -2.0, 2.0)
    return block.astype(np.float32)


def compute_candidate_geometry_embedding(candidate: dict[str, Any] | None, box: Box | None) -> np.ndarray:
    dims = 4 + (5 * 4) + (16 * 2) + 4 + 128
    if not candidate or not box:
        return np.zeros((dims,), dtype=np.float32)
    x1, y1, x2, y2 = box
    width = max(1.0, float(x2 - x1))
    height = max(1.0, float(y2 - y1))
    aspect = width / height
    base = [
        width / max(1.0, width + height),
        height / max(1.0, width + height),
        aspect / max(1.0, aspect),
        min(width, height) / max(width, height),
    ]
    ordered_subboxes = ["left_eye", "right_eye", "mouth", "left_brow", "right_brow"]
    subbox_values: list[float] = []
    subboxes = candidate.get("subboxes", {}) or {}
    for key in ordered_subboxes:
        subbox = subboxes.get(key)
        if not subbox:
            subbox_values.extend([0.0, 0.0, 0.0, 0.0])
            continue
        sx1, sy1, sx2, sy2 = subbox
        subbox_values.extend(
            [
                (((sx1 + sx2) / 2.0) - x1) / width,
                (((sy1 + sy2) / 2.0) - y1) / height,
                max(1.0, float(sx2 - sx1)) / width,
                max(1.0, float(sy2 - sy1)) / height,
            ]
        )
    landmark_points = candidate.get("landmark_points", []) or []
    landmark_values: list[float] = []
    for point in landmark_points[:16]:
        if len(point) < 2:
            continue
        landmark_values.extend(
            [
                (float(point[0]) - x1) / width,
                (float(point[1]) - y1) / height,
            ]
        )
    while len(landmark_values) < 32:
        landmark_values.extend([0.0, 0.0])
    metric_values = [
        float(candidate.get("mouth_opening", 0.0) or 0.0),
        float(candidate.get("left_eye_opening", 0.0) or 0.0),
        float(candidate.get("right_eye_opening", 0.0) or 0.0),
        float(candidate.get("left_right_asymmetry", 0.0) or 0.0),
    ]
    identity_signature = list(candidate.get("identity_signature", []) or [])
    identity_signature = [float(value) for value in identity_signature[:128]]
    while len(identity_signature) < 128:
        identity_signature.append(0.0)
    return np.asarray(base + subbox_values + landmark_values[:32] + metric_values + identity_signature, dtype=np.float32)


def compute_face_identity_embedding(
    gray_frame: np.ndarray,
    box: Box | None,
    *,
    candidate: dict[str, Any] | None = None,
) -> np.ndarray | None:
    crop = extract_face_crop(gray_frame, box, size=96)
    if crop is None:
        return None
    hog_embedding = compute_hog_embedding(crop, cells=4, bins=8)
    lbp_embedding = compute_lbp_histogram(crop, bins=32)
    dct_embedding = compute_dct_embedding(crop, block_size=8)
    geometry_embedding = compute_candidate_geometry_embedding(candidate, box)
    features = np.concatenate(
        [
            hog_embedding * 1.8,
            lbp_embedding * 1.1,
            dct_embedding * 1.2,
            geometry_embedding * 1.5,
        ]
    ).astype(np.float32)
    return normalize_vector(features)


def compute_face_descriptor(
    gray_frame: np.ndarray,
    box: Box | None,
    *,
    candidate: dict[str, Any] | None = None,
    bins: int = 24,
) -> np.ndarray | None:
    _ = bins
    return compute_face_identity_embedding(gray_frame, box, candidate=candidate)


def cosine_similarity(vector_a: np.ndarray | None, vector_b: np.ndarray | None) -> float:
    if vector_a is None or vector_b is None:
        return 0.0
    denom = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denom <= 0:
        return 0.0
    similarity = float(np.dot(vector_a, vector_b) / denom)
    return max(0.0, min(1.0, similarity))


def size_similarity(box_a: Box | None, box_b: Box | None) -> float:
    if not box_a or not box_b:
        return 0.0
    area_a = max(1, box_area(box_a))
    area_b = max(1, box_area(box_b))
    width_a = max(1, box_a[2] - box_a[0])
    width_b = max(1, box_b[2] - box_b[0])
    height_a = max(1, box_a[3] - box_a[1])
    height_b = max(1, box_b[3] - box_b[1])
    ratios = [
        min(area_a, area_b) / max(area_a, area_b),
        min(width_a, width_b) / max(width_a, width_b),
        min(height_a, height_b) / max(height_a, height_b),
    ]
    return float(sum(ratios) / len(ratios))


def position_similarity(
    box_a: Box | None,
    box_b: Box | None,
    shape: tuple[int, int] | tuple[int, int, int],
    *,
    max_ratio: float = 0.28,
) -> float:
    if not box_a or not box_b:
        return 0.0
    height, width = shape[:2]
    diag = math.sqrt(float(width * width + height * height))
    max_distance = max(24.0, diag * max_ratio)
    distance = center_distance(box_a, box_b)
    return max(0.0, 1.0 - min(1.0, distance / max_distance))


def choose_face_candidate_with_tracking(
    candidates: list[dict[str, Any]],
    gray_frame: np.ndarray,
    *,
    reference_box: Box | None,
    previous_box: Box | None = None,
    reference_descriptor: np.ndarray | None = None,
    previous_descriptor: np.ndarray | None = None,
    minimum_confidence: float = 0.42,
) -> tuple[dict[str, Any] | None, np.ndarray | None, float, dict[str, float]]:
    if not candidates:
        return None, None, 0.0, {}

    best_candidate: dict[str, Any] | None = None
    best_descriptor: np.ndarray | None = None
    best_confidence = float("-inf")
    best_components: dict[str, float] = {}

    for candidate in candidates:
        candidate_box = candidate.get("roi_box")
        if not candidate_box:
            continue

        descriptor = candidate.get("identity_embedding")
        if descriptor is None:
            descriptor = compute_face_descriptor(gray_frame, candidate_box, candidate=candidate)
        identity_backend = str(candidate.get("identity_backend") or "").strip().lower()
        arcface_mode = identity_backend == "arcface" and reference_descriptor is not None
        ref_position = position_similarity(candidate_box, reference_box, gray_frame.shape)
        prev_position = position_similarity(candidate_box, previous_box, gray_frame.shape)
        ref_iou = intersection_over_union(candidate_box, reference_box)
        prev_iou = intersection_over_union(candidate_box, previous_box)
        ref_size = size_similarity(candidate_box, reference_box)
        prev_size = size_similarity(candidate_box, previous_box)
        ref_appearance = cosine_similarity(descriptor, reference_descriptor)
        prev_appearance = cosine_similarity(descriptor, previous_descriptor)

        if previous_box:
            geometry_score = (max(prev_iou, prev_position) * 0.55) + (prev_size * 0.45)
        else:
            geometry_score = (max(ref_iou, ref_position) * 0.6) + (ref_size * 0.4)

        if reference_descriptor is not None:
            appearance_score = (
                (ref_appearance * 0.7) + (prev_appearance * 0.3)
                if previous_descriptor is not None
                else ref_appearance
            )
        else:
            appearance_score = 0.0

        anchor_score = max(ref_iou, ref_position, prev_iou, prev_position)
        if reference_descriptor is None:
            confidence = (anchor_score * 0.68) + (geometry_score * 0.32)
        elif arcface_mode:
            confidence = (appearance_score * 0.82) + (geometry_score * 0.10) + (anchor_score * 0.08)
        else:
            confidence = (appearance_score * 0.52) + (geometry_score * 0.24) + (anchor_score * 0.24)

        # In ArcFace mode, identity should dominate even after strong shot/layout changes.
        if arcface_mode:
            if ref_appearance >= 0.78:
                confidence = max(confidence, min(0.98, 0.80 + ((ref_appearance - 0.78) * 0.9)))
            elif ref_appearance >= 0.68:
                confidence = max(confidence, min(0.90, 0.62 + ((ref_appearance - 0.68) * 1.4)))
            elif ref_appearance < 0.42:
                confidence *= 0.22
            elif ref_appearance < 0.55:
                confidence *= 0.55
            if previous_descriptor is not None and prev_appearance < 0.35 and ref_appearance < 0.60:
                confidence *= 0.55
        else:
            # Be conservative: if continuity is weak, do not silently jump to another nearby face.
            if reference_box is not None and ref_iou < 0.03 and ref_position < 0.42:
                confidence *= 0.28
            if previous_box is not None and prev_iou < 0.03 and prev_position < 0.42:
                confidence *= 0.20

            if reference_descriptor is not None:
                if ref_appearance < 0.52:
                    confidence *= 0.42
                elif ref_appearance < 0.64:
                    confidence *= 0.72
            if previous_descriptor is not None:
                if prev_appearance < 0.48:
                    confidence *= 0.55
                elif prev_appearance < 0.60:
                    confidence *= 0.82

        if confidence > best_confidence:
            best_candidate = candidate
            best_descriptor = descriptor
            best_confidence = confidence
            best_components = {
                "appearance_score": round(float(appearance_score), 6),
                "geometry_score": round(float(geometry_score), 6),
                "anchor_score": round(float(anchor_score), 6),
                "ref_appearance": round(float(ref_appearance), 6),
                "prev_appearance": round(float(prev_appearance), 6),
                "ref_iou": round(float(ref_iou), 6),
                "prev_iou": round(float(prev_iou), 6),
                "ref_position": round(float(ref_position), 6),
                "prev_position": round(float(prev_position), 6),
            }

    if best_confidence < minimum_confidence:
        if float(best_components.get("ref_appearance", 0.0) or 0.0) >= 0.68:
            best_components["lock_mode"] = 2.0
            return best_candidate, best_descriptor, max(0.0, min(1.0, float(best_confidence))), best_components
        continuity_score = max(
            float(best_components.get("prev_iou", 0.0) or 0.0),
            float(best_components.get("prev_position", 0.0) or 0.0),
        )
        identity_score = max(
            float(best_components.get("ref_appearance", 0.0) or 0.0),
            float(best_components.get("appearance_score", 0.0) or 0.0),
        )
        if best_candidate is not None and len(candidates) == 1 and continuity_score >= 0.74:
            relaxed_confidence = max(float(best_confidence), min(0.64, (continuity_score * 0.72) + (identity_score * 0.28)))
            best_components["lock_mode"] = 1.0
            return best_candidate, best_descriptor, max(0.0, min(1.0, relaxed_confidence)), best_components
        if best_candidate is not None and len(candidates) <= 2 and continuity_score >= 0.84 and identity_score >= 0.28:
            relaxed_confidence = max(float(best_confidence), min(0.62, (continuity_score * 0.66) + (identity_score * 0.34)))
            best_components["lock_mode"] = 1.0
            return best_candidate, best_descriptor, max(0.0, min(1.0, relaxed_confidence)), best_components
        if best_candidate is not None and continuity_score >= 0.72 and identity_score >= 0.52:
            relaxed_confidence = max(float(best_confidence), min(0.66, (continuity_score * 0.58) + (identity_score * 0.42)))
            best_components["lock_mode"] = 1.0
            return best_candidate, best_descriptor, max(0.0, min(1.0, relaxed_confidence)), best_components
        return None, best_descriptor, max(0.0, float(best_confidence)), best_components

    return best_candidate, best_descriptor, max(0.0, min(1.0, float(best_confidence))), best_components
