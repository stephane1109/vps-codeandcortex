from __future__ import annotations

import argparse
import csv
import math
import re
from functools import lru_cache
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from multimodale.common import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    clip_video_interval,
    ensure_directory,
    ensure_video_mp4,
    is_youtube_url,
    resolve_media_source,
    utc_session_id,
    write_json,
    write_jsonl,
)
from multimodale.multivisage import (
    center_distance,
    choose_face_candidate_with_tracking,
    compute_face_descriptor,
    create_face_records,
    find_track_for_box,
    intersection_over_union,
    opencv_rects_to_xyxy,
    select_primary_box,
    track_detected_faces,
)
from multimodale.progression import write_progress_snapshot
from multimodale.selectvisage import create_face_selection_backend
from multimodale.visualisations import altair_available, configure_chart, save_chart

try:
    import cv2
except ImportError as exc:  # pragma: no cover - dépendance externe
    raise RuntimeError("opencv-python est requis pour multimodale/mouvements.py") from exc

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - dépendance externe
    raise RuntimeError("numpy est requis pour multimodale/mouvements.py") from exc

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - dépendance externe
    Image = None
    ImageDraw = None
    ImageFont = None


PANEL_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/SFNS.ttf",
]

MEDIAPIPE_IDENTITY_LANDMARK_INDICES = [
    10, 67, 54, 103, 109, 338, 297, 332, 284, 251,
    21, 71, 68, 104, 69, 108, 151, 337, 299, 333,
    298, 301, 33, 160, 158, 133, 153, 144, 362, 385,
    387, 263, 373, 380, 70, 63, 105, 66, 107, 336,
    296, 334, 293, 300, 61, 40, 37, 0, 267, 270,
    291, 78, 81, 13, 14, 311, 308, 152, 148, 176,
    149, 150, 136, 172,
]


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def project_rows(rows: list[dict[str, Any]], preferred_columns: list[str]) -> list[dict[str, Any]]:
    if not rows:
        return []

    available_columns: set[str] = set()
    for row in rows:
        available_columns.update(row.keys())
    selected_columns = [column for column in preferred_columns if column in available_columns]
    return [{column: row.get(column, "") for column in selected_columns} for row in rows]


def write_csv_variants(path: str | Path, rows: list[dict[str, Any]], essential_columns: list[str]) -> tuple[str, str, str]:
    destination = Path(path)
    legacy_path = destination
    complete_path = destination.with_name(f"{destination.stem}_complet{destination.suffix}")
    essential_path = destination.with_name(f"{destination.stem}_essentiel{destination.suffix}")
    essential_rows = project_rows(rows, essential_columns)
    write_csv(legacy_path, rows)
    write_csv(complete_path, rows)
    write_csv(essential_path, essential_rows)
    return (str(legacy_path), str(complete_path), str(essential_path))


MOUVEMENTS_FRAME_ESSENTIAL_COLUMNS = [
    "frame_index",
    "time_sec",
    "frame_role",
    "image_path",
    "frame_preview_path",
    "magnitude_preview_path",
    "directional_entropy_preview_path",
    "hsv_preview_path",
    "vectors_preview_path",
    "overlay_preview_path",
    "annotated_preview_path",
    "anatomy_mode",
    "face_analysis_mode",
    "motion_mean",
    "motion_peak_p95",
    "direction_label",
    "roi_directional_entropy",
    "roi_directional_entropy_norm",
    "roi_motion_energy",
    "face_count",
    "tracked_face_status",
    "tracked_face_confidence",
    "tracked_face_identity_similarity",
    "mouth_opening",
    "left_right_asymmetry",
]

MOUVEMENTS_MULTIVISAGE_ESSENTIAL_COLUMNS = [
    "frame_index",
    "time_sec",
    "image_path",
    "face_id",
    "face_order",
    "is_primary_face",
    "face_box_x1",
    "face_box_y1",
    "face_box_x2",
    "face_box_y2",
    "face_flow_mean",
    "face_motion_energy",
    "face_directional_entropy",
    "face_directional_entropy_norm",
    "anatomy_backend",
]

MOUVEMENTS_WINDOWS_ESSENTIAL_COLUMNS = [
    "window_id",
    "start_sec",
    "end_sec",
    "keyframe_path",
    "motion_mean",
    "motion_peak_p95",
    "motion_active_ratio",
    "direction_label",
    "roi_directional_entropy",
    "roi_directional_entropy_norm",
    "roi_motion_energy",
]


def natural_sort_key(value: str) -> list[Any]:
    text = str(value or "")
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", text)]


@lru_cache(maxsize=16)
def get_panel_font(size: int, bold: bool = False):
    if ImageFont is None:
        return None
    for candidate in PANEL_FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def draw_panel_text(
    panel: np.ndarray,
    text: str,
    xy: tuple[int, int],
    *,
    size: int = 20,
    color: tuple[int, int, int] = (35, 35, 35),
) -> np.ndarray:
    if Image is None or ImageDraw is None or ImageFont is None:
        cv2.putText(panel, text, xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        return panel
    rgb = cv2.cvtColor(panel, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    font = get_panel_font(size)
    draw.text(xy, text, font=font, fill=(int(color[2]), int(color[1]), int(color[0])))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def build_movement_altair_chart(window_rows: list[dict[str, Any]], output_path: str | Path) -> str:
    if not window_rows or not altair_available():
        return ""

    import altair as alt  # pragma: no cover - dépendance externe

    rows = []
    for row in window_rows:
        rows.append(
            {
                "start_sec": float(row.get("start_sec", 0.0) or 0.0),
                "end_sec": float(row.get("end_sec", 0.0) or 0.0),
                "motion_mean": float(row.get("motion_mean", 0.0) or 0.0),
                "motion_peak_p95": float(row.get("motion_peak_p95", 0.0) or 0.0),
                "dominant_direction": str(row.get("dominant_direction", "") or ""),
            }
        )

    base = alt.Chart(alt.Data(values=rows)).encode(
        x=alt.X("start_sec:Q", title="Temps (s)")
    )

    agitation = base.mark_line(color="#8d1b1d", point=alt.OverlayMarkDef(size=56, filled=True)).encode(
        y=alt.Y("motion_mean:Q", title="Mouvement moyen"),
        tooltip=[
            alt.Tooltip("start_sec:Q", title="Début (s)", format=".2f"),
            alt.Tooltip("end_sec:Q", title="Fin (s)", format=".2f"),
            alt.Tooltip("motion_mean:Q", title="Mouvement moyen", format=".4f"),
            alt.Tooltip("motion_peak_p95:Q", title="Pic p95", format=".4f"),
            alt.Tooltip("dominant_direction:N", title="Direction"),
        ],
    ).properties(width=760, height=320)

    chart = configure_chart(
        agitation,
        "Analyse mouvements multimodale",
    )
    return save_chart(chart, output_path)


def flow_direction_label(dx: float, dy: float, min_norm: float = 0.01) -> str:
    norm = math.sqrt(dx * dx + dy * dy)
    if norm < min_norm:
        return "stable"

    if abs(dx) >= abs(dy):
        return "droite" if dx > 0 else "gauche"
    return "bas" if dy > 0 else "haut"


def compute_color_metrics(frame_bgr: np.ndarray) -> dict[str, float]:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return {
        "brightness_mean": float(np.mean(gray)),
        "contrast_std": float(np.std(gray)),
        "hue_mean": float(np.mean(hsv[..., 0])),
        "saturation_mean": float(np.mean(hsv[..., 1])),
        "red_mean": float(np.mean(rgb[..., 0])),
        "green_mean": float(np.mean(rgb[..., 1])),
        "blue_mean": float(np.mean(rgb[..., 2])),
    }


def build_magnitude_preview(magnitude: np.ndarray) -> np.ndarray:
    normalised = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.applyColorMap(normalised.astype(np.uint8), cv2.COLORMAP_TURBO)


def build_flow_hsv_preview(flow: np.ndarray, magnitude: np.ndarray) -> np.ndarray:
    angle = cv2.phase(flow[..., 0], flow[..., 1], angleInDegrees=False)
    hsv = np.zeros((flow.shape[0], flow.shape[1], 3), dtype=np.uint8)
    hsv[..., 0] = np.uint8((angle * 180.0 / np.pi) / 2.0)
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def build_flow_vectors_preview(
    frame_bgr: np.ndarray,
    flow: np.ndarray,
    step: int = 24,
    scale: float = 2.0,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    preview = frame_bgr.copy()
    height, width = frame_bgr.shape[:2]
    ys, xs = np.mgrid[step // 2:height:step, step // 2:width:step].astype(int)
    if ys.size == 0 or xs.size == 0:
        return preview
    if mask is not None and mask.size:
        selection = mask[ys, xs]
        xs = xs[selection]
        ys = ys[selection]
        if xs.size == 0 or ys.size == 0:
            return preview
    dxs = flow[ys, xs, 0]
    dys = flow[ys, xs, 1]
    for x, y, dx, dy in zip(xs.flat, ys.flat, dxs.flat, dys.flat):
        end_point = (int(round(x + dx * scale)), int(round(y + dy * scale)))
        cv2.arrowedLine(preview, (int(x), int(y)), end_point, (0, 255, 255), 1, tipLength=0.28)
    return preview


def compute_directional_histogram(
    flow: np.ndarray,
    magnitude: np.ndarray,
    mask: np.ndarray | None = None,
    bins: int = 12,
) -> tuple[np.ndarray, float, float]:
    if mask is not None and np.any(mask):
        roi_mag = magnitude[mask]
        roi_dx = flow[..., 0][mask]
        roi_dy = flow[..., 1][mask]
    else:
        roi_mag = magnitude.reshape(-1)
        roi_dx = flow[..., 0].reshape(-1)
        roi_dy = flow[..., 1].reshape(-1)

    if roi_mag.size == 0 or float(np.sum(roi_mag)) <= 0:
        return np.zeros((bins,), dtype=np.float32), 0.0, float(math.log2(max(bins, 2)))

    angles = (np.arctan2(roi_dy, roi_dx) + (2 * np.pi)) % (2 * np.pi)
    hist, _ = np.histogram(angles, bins=bins, range=(0, 2 * np.pi), weights=roi_mag)
    weights = hist.astype(np.float32)
    if float(np.sum(weights)) <= 0:
        return np.zeros((bins,), dtype=np.float32), 0.0, float(math.log2(max(bins, 2)))

    prob = weights / float(np.sum(weights))
    entropy = max(0.0, float(-np.sum(prob[prob > 0] * np.log2(prob[prob > 0]))))
    max_entropy = float(math.log2(max(bins, 2)))
    return prob, entropy, max_entropy


def build_directional_entropy_preview(
    frame_bgr: np.ndarray,
    flow: np.ndarray,
    magnitude: np.ndarray,
    mask: np.ndarray | None = None,
    bins: int = 12,
) -> np.ndarray:
    # OpenCV expects colors in BGR order.
    observed_blue_bgr = (212, 143, 92)
    dominant_orange_bgr = (61, 128, 214)

    prob, entropy, max_entropy = compute_directional_histogram(flow, magnitude, mask=mask, bins=bins)
    vectors_preview = build_flow_vectors_preview(frame_bgr, flow, step=24, scale=2.0, mask=mask)

    if mask is not None and np.any(mask):
        dimmed = vectors_preview.copy()
        dimmed[~mask] = np.clip((dimmed[~mask].astype(np.float32) * 0.38) + 150.0, 0, 255).astype(np.uint8)
        vectors_preview = dimmed

    height = vectors_preview.shape[0]
    panel_width = 540
    panel = np.full((height, panel_width, 3), 255, dtype=np.uint8)
    panel = draw_panel_text(panel, "Entropie directionnelle", (16, 16), size=28, color=(30, 30, 30))
    panel = draw_panel_text(panel, "Comment le mouvement se répartit dans les directions", (16, 50), size=18, color=(70, 70, 70))

    entropy_ratio = (entropy / max_entropy) if max_entropy > 0 else 0.0
    if entropy_ratio < 0.33:
        entropy_label = "faible"
        entropy_reading = "mouvement surtout concentré dans une direction"
    elif entropy_ratio < 0.66:
        entropy_label = "moyenne"
        entropy_reading = "mouvement partagé entre plusieurs directions"
    else:
        entropy_label = "élevée"
        entropy_reading = "mouvement réparti dans de nombreuses directions"

    dominant_bin = int(np.argmax(prob)) if prob.size else -1
    dominant_value = float(prob[dominant_bin]) if dominant_bin >= 0 else 0.0
    angle_step = 360.0 / max(bins, 1)
    dominant_angle_deg = ((dominant_bin + 0.5) * angle_step) % 360.0 if dominant_bin >= 0 else 0.0
    dominant_range_start = int(round(dominant_bin * angle_step)) if dominant_bin >= 0 else 0
    dominant_range_end = int(round((dominant_bin + 1) * angle_step)) if dominant_bin >= 0 else 0
    panel = draw_panel_text(panel, f"Niveau de dispersion : {entropy_label}", (16, 84), size=22)
    panel = draw_panel_text(panel, f"Score : {entropy:.3f} sur {max_entropy:.3f}", (16, 114), size=19)
    panel = draw_panel_text(panel, f"Score normalisé : {entropy_ratio:.3f} / 1.000", (16, 142), size=18, color=(70, 70, 70))
    panel = draw_panel_text(panel, entropy_reading, (16, 168), size=17, color=(70, 70, 70))

    panel = draw_panel_text(panel, "Le secteur orange montre la direction dominante.", (16, 198), size=18, color=(70, 70, 70))

    rose_top = 270
    rose_box_height = min(260, max(180, height - 430))
    rose_box_bottom = rose_top + rose_box_height
    rose_center = (panel_width // 2, rose_top + (rose_box_height // 2))
    rose_radius = min(120, max(80, (rose_box_height // 2) - 18))
    cv2.rectangle(panel, (22, rose_top), (panel_width - 22, rose_box_bottom), (220, 220, 220), 1)

    max_prob = float(np.max(prob)) if prob.size and float(np.max(prob)) > 0 else 1.0
    for ring_ratio in (0.33, 0.66, 1.0):
        cv2.circle(panel, rose_center, max(1, int(rose_radius * ring_ratio)), (228, 228, 228), 1, cv2.LINE_AA)

    display_angle_offset_deg = -90.0

    for index in range(bins):
        angle_deg = index * angle_step
        angle_rad = math.radians(angle_deg + display_angle_offset_deg)
        end_x = int(round(rose_center[0] + math.cos(angle_rad) * rose_radius))
        end_y = int(round(rose_center[1] + math.sin(angle_rad) * rose_radius))
        cv2.line(panel, rose_center, (end_x, end_y), (232, 232, 232), 1, cv2.LINE_AA)

    for index, value in enumerate(prob):
        if float(value) <= 0.0:
            continue
        start_deg = index * angle_step
        end_deg = (index + 1) * angle_step
        sector_radius = max(14, int(rose_radius * (float(value) / max_prob)))
        sector_points = [rose_center]
        for sample_deg in np.linspace(start_deg, end_deg, num=10):
            sample_rad = math.radians(float(sample_deg) + display_angle_offset_deg)
            point_x = int(round(rose_center[0] + math.cos(sample_rad) * sector_radius))
            point_y = int(round(rose_center[1] + math.sin(sample_rad) * sector_radius))
            sector_points.append((point_x, point_y))
        color = dominant_orange_bgr if index == dominant_bin and dominant_value > 0 else observed_blue_bgr
        cv2.fillConvexPoly(panel, np.array(sector_points, dtype=np.int32), color, lineType=cv2.LINE_AA)

    cv2.circle(panel, rose_center, rose_radius, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.circle(panel, rose_center, 3, (120, 120, 120), -1, cv2.LINE_AA)

    degree_labels = [
        ("0°", (rose_center[0] - 12, rose_center[1] - rose_radius - 26)),
        ("90°", (rose_center[0] + rose_radius + 10, rose_center[1] - 10)),
        ("180°", (rose_center[0] - 18, rose_center[1] + rose_radius + 10)),
        ("270°", (rose_center[0] - rose_radius - 48, rose_center[1] - 10)),
    ]
    for text, position in degree_labels:
        panel = draw_panel_text(panel, text, position, size=18, color=(90, 90, 90))

    legend_y = rose_box_bottom + 24
    cv2.rectangle(panel, (16, legend_y - 6), (30, legend_y + 8), observed_blue_bgr, -1)
    panel = draw_panel_text(panel, "Bleu = directions observées", (40, legend_y - 8), size=17, color=(70, 70, 70))
    cv2.rectangle(panel, (16, legend_y + 20), (30, legend_y + 34), dominant_orange_bgr, -1)
    panel = draw_panel_text(panel, "Orange = direction dominante", (40, legend_y + 18), size=17, color=(70, 70, 70))

    return np.hstack([vectors_preview, panel])


def build_labeled_panel(image_bgr: np.ndarray, label: str, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    panel = cv2.resize(image_bgr, (width, height), interpolation=cv2.INTER_AREA)
    cv2.rectangle(panel, (0, 0), (width, 24), (20, 20, 20), -1)
    cv2.putText(panel, label, (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    return panel


def build_flow_analysis_panel(frame_bgr: np.ndarray, flow: np.ndarray, magnitude: np.ndarray) -> np.ndarray:
    magnitude_preview = build_magnitude_preview(magnitude)
    hsv_preview = build_flow_hsv_preview(flow, magnitude)
    overlay_preview = cv2.addWeighted(frame_bgr, 0.58, hsv_preview, 0.42, 0.0)
    vectors_preview = build_flow_vectors_preview(frame_bgr, flow)

    panel_size = (220, 148)
    top_left = build_labeled_panel(magnitude_preview, "Magnitude optique", panel_size)
    top_right = build_labeled_panel(hsv_preview, "Analyse HSV", panel_size)
    bottom_left = build_labeled_panel(overlay_preview, "Superposition", panel_size)
    bottom_right = build_labeled_panel(vectors_preview, "Vecteurs", panel_size)
    top_row = np.hstack([top_left, top_right])
    bottom_row = np.hstack([bottom_left, bottom_right])
    return np.vstack([top_row, bottom_row])


def save_flow_view_images(
    frame_bgr: np.ndarray,
    flow: np.ndarray,
    magnitude: np.ndarray,
    *,
    stem: str,
    magnitude_dir: Path,
    hsv_dir: Path,
    overlay_dir: Path,
    vectors_dir: Path,
    entropy_dir: Path,
    panel_dir: Path,
    entropy_mask: np.ndarray | None = None,
) -> dict[str, str]:
    magnitude_preview = build_magnitude_preview(magnitude)
    hsv_preview = build_flow_hsv_preview(flow, magnitude)
    overlay_preview = cv2.addWeighted(frame_bgr, 0.58, hsv_preview, 0.42, 0.0)
    vectors_preview = build_flow_vectors_preview(frame_bgr, flow)
    entropy_preview = build_directional_entropy_preview(frame_bgr, flow, magnitude, mask=entropy_mask)
    panel_preview = build_flow_analysis_panel(frame_bgr, flow, magnitude)

    magnitude_path = magnitude_dir / f"{stem}_magnitude.jpg"
    hsv_path = hsv_dir / f"{stem}_hsv.jpg"
    overlay_path = overlay_dir / f"{stem}_superposition.jpg"
    vectors_path = vectors_dir / f"{stem}_vecteurs.jpg"
    entropy_path = entropy_dir / f"{stem}_entropie_directionnelle.jpg"
    panel_path = panel_dir / f"{stem}_flow_panel.jpg"

    cv2.imwrite(str(magnitude_path), magnitude_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    cv2.imwrite(str(hsv_path), hsv_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    cv2.imwrite(str(overlay_path), overlay_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    cv2.imwrite(str(vectors_path), vectors_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    cv2.imwrite(str(entropy_path), entropy_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    cv2.imwrite(str(panel_path), panel_preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])

    return {
        "magnitude_preview_path": str(magnitude_path),
        "hsv_preview_path": str(hsv_path),
        "overlay_preview_path": str(overlay_path),
        "vectors_preview_path": str(vectors_path),
        "directional_entropy_preview_path": str(entropy_path),
        "flow_panel_path": str(panel_path),
    }


def load_face_detector() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("Impossible de charger le détecteur de visages OpenCV.")
    return detector


def load_eye_detector() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("Impossible de charger le détecteur d'yeux OpenCV.")
    return detector


def load_smile_detector() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_smile.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("Impossible de charger le détecteur de sourire OpenCV.")
    return detector


def load_body_detector() -> cv2.HOGDescriptor:
    detector = cv2.HOGDescriptor()
    detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return detector


def load_mediapipe_module():
    try:
        import mediapipe as mp  # pragma: no cover - dépendance externe
    except ImportError as exc:  # pragma: no cover - dépendance externe
        raise RuntimeError(
            "MediaPipe n'est pas disponible dans le runtime Python isolé. "
            "Relance le bootstrap Python ou choisis le backend OpenCV."
        ) from exc
    return mp


def load_mediapipe_face_mesh():
    mp = load_mediapipe_module()
    return mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=5,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def load_mediapipe_pose_detector():
    mp = load_mediapipe_module()
    return mp.solutions.pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        enable_segmentation=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def clamp_box(box: tuple[int, int, int, int], shape: tuple[int, int]) -> tuple[int, int, int, int]:
    height, width = shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(round(x1))))
    y1 = max(0, min(height - 1, int(round(y1))))
    x2 = max(x1 + 1, min(width, int(round(x2))))
    y2 = max(y1 + 1, min(height, int(round(y2))))
    return x1, y1, x2, y2


def box_to_mask(shape: tuple[int, int], box: tuple[int, int, int, int] | None) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=bool)
    if not box:
        return mask
    x1, y1, x2, y2 = clamp_box(box, shape)
    mask[y1:y2, x1:x2] = True
    return mask


def box_center_norm(box: tuple[int, int, int, int] | None, shape: tuple[int, int]) -> tuple[float, float]:
    if not box:
        return 0.0, 0.0
    height, width = shape[:2]
    x1, y1, x2, y2 = clamp_box(box, shape)
    return float((x1 + x2) / 2.0) / max(1, width), float((y1 + y2) / 2.0) / max(1, height)


def box_area(box: tuple[int, int, int, int] | None) -> int:
    if not box:
        return 0
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def choose_largest_box(boxes: list[tuple[int, int, int, int]] | tuple | np.ndarray | None) -> tuple[int, int, int, int] | None:
    if boxes is None:
        return None
    candidates = []
    for item in boxes:
        if len(item) >= 4:
            x, y, w, h = [int(v) for v in item[:4]]
            candidates.append((x, y, x + w, y + h))
    if not candidates:
        return None
    return max(candidates, key=box_area)


def default_face_subboxes(face_box: tuple[int, int, int, int]) -> dict[str, tuple[int, int, int, int]]:
    x1, y1, x2, y2 = face_box
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    left_eye = (x1 + int(width * 0.16), y1 + int(height * 0.24), x1 + int(width * 0.38), y1 + int(height * 0.40))
    right_eye = (x1 + int(width * 0.62), y1 + int(height * 0.24), x1 + int(width * 0.84), y1 + int(height * 0.40))
    left_brow = (left_eye[0], max(y1, left_eye[1] - int(height * 0.12)), left_eye[2], max(y1 + 1, left_eye[1] - int(height * 0.03)))
    right_brow = (right_eye[0], max(y1, right_eye[1] - int(height * 0.12)), right_eye[2], max(y1 + 1, right_eye[1] - int(height * 0.03)))
    mouth = (x1 + int(width * 0.28), y1 + int(height * 0.62), x1 + int(width * 0.72), y1 + int(height * 0.84))
    return {
        "left_eye": left_eye,
        "right_eye": right_eye,
        "left_brow": left_brow,
        "right_brow": right_brow,
        "mouth": mouth,
    }


def build_face_candidate_from_box(
    face_box: tuple[int, int, int, int],
    shape: tuple[int, int],
    *,
    backend: str,
    subboxes: dict[str, tuple[int, int, int, int]] | None = None,
    landmark_points: list[tuple[int, int]] | None = None,
    landmark_edges: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
    identity_signature: list[float] | None = None,
    mouth_opening: float | None = None,
    left_eye_opening: float | None = None,
    right_eye_opening: float | None = None,
    left_right_asymmetry: float | None = None,
) -> dict[str, Any]:
    x1, y1, x2, y2 = clamp_box(face_box, shape)
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    candidate_subboxes = dict(subboxes or default_face_subboxes((x1, y1, x2, y2)))
    mouth_box = candidate_subboxes.get("mouth") or (x1, y1, x2, y2)
    left_eye_box = candidate_subboxes.get("left_eye") or (x1, y1, x2, y2)
    right_eye_box = candidate_subboxes.get("right_eye") or (x1, y1, x2, y2)
    center_x_norm, center_y_norm = box_center_norm((x1, y1, x2, y2), shape)

    computed_mouth_opening = float(max(1, mouth_box[3] - mouth_box[1])) / height
    computed_left_eye_opening = float(max(1, left_eye_box[3] - left_eye_box[1])) / height
    computed_right_eye_opening = float(max(1, right_eye_box[3] - right_eye_box[1])) / height

    return {
        "mode": "visage",
        "backend": backend,
        "roi_box": (x1, y1, x2, y2),
        "roi_mask": box_to_mask(shape, (x1, y1, x2, y2)),
        "subboxes": candidate_subboxes,
        "face_area_ratio": float(width * height) / float(shape[0] * shape[1]),
        "roi_center_x_norm": center_x_norm,
        "roi_center_y_norm": center_y_norm,
        "mouth_opening": round(float(computed_mouth_opening if mouth_opening is None else mouth_opening), 6),
        "left_eye_opening": round(float(computed_left_eye_opening if left_eye_opening is None else left_eye_opening), 6),
        "right_eye_opening": round(float(computed_right_eye_opening if right_eye_opening is None else right_eye_opening), 6),
        "left_right_asymmetry": round(
            float(
                abs(computed_left_eye_opening - computed_right_eye_opening)
                if left_right_asymmetry is None
                else left_right_asymmetry
            ),
            6,
        ),
        "landmark_points": landmark_points or [],
        "landmark_edges": landmark_edges or [],
        "identity_signature": list(identity_signature or []),
    }


def parse_selected_face_box(value: str | None) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4:
        raise RuntimeError("Le rectangle de sélection du visage doit contenir 4 coordonnées normalisées.")
    coords = [max(0.0, min(1.0, float(part))) for part in parts]
    x1, y1, x2, y2 = coords
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("Le rectangle de sélection du visage est invalide.")
    return x1, y1, x2, y2


def denormalize_selected_face_box(
    normalized_box: tuple[float, float, float, float] | None,
    shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if not normalized_box:
        return None
    height, width = shape[:2]
    x1, y1, x2, y2 = normalized_box
    return clamp_box(
        (
            int(round(x1 * width)),
            int(round(y1 * height)),
            int(round(x2 * width)),
            int(round(y2 * height)),
        ),
        shape,
    )


def choose_face_candidate_for_reference(
    candidates: list[dict[str, Any]],
    reference_box: tuple[int, int, int, int] | None,
) -> dict[str, Any] | None:
    if not candidates:
        return None
    if not reference_box:
        return max(candidates, key=lambda candidate: box_area(candidate.get("roi_box")))

    best_candidate = None
    best_score = float("-inf")
    for candidate in candidates:
        candidate_box = candidate.get("roi_box")
        if not candidate_box:
            continue
        iou = intersection_over_union(candidate_box, reference_box)
        distance = center_distance(candidate_box, reference_box)
        score = (iou * 2.0) + max(0.0, 1.0 - (distance / max(24.0, math.sqrt(box_area(reference_box) or 1.0) * 1.6)))
        if score > best_score:
            best_score = score
            best_candidate = candidate
    return best_candidate


def choose_face_candidate_for_metrics(
    candidates: list[dict[str, Any]],
    *,
    selected_box: tuple[int, int, int, int] | None,
    frame_shape: tuple[int, int],
    selected_descriptor: np.ndarray | None = None,
    reference_descriptor: np.ndarray | None = None,
    minimum_score: float = 0.48,
) -> tuple[dict[str, Any] | None, float]:
    if not candidates or not selected_box:
        return None, 0.0

    frame_diag = math.sqrt(float(frame_shape[0] * frame_shape[0] + frame_shape[1] * frame_shape[1]))
    best_candidate = None
    best_score = float("-inf")

    for candidate in candidates:
        candidate_box = candidate.get("roi_box")
        if not candidate_box:
            continue

        iou_score = intersection_over_union(candidate_box, selected_box)
        distance = center_distance(candidate_box, selected_box)
        position_score = max(0.0, 1.0 - min(1.0, distance / max(24.0, frame_diag * 0.18)))
        spatial_score = max(iou_score, position_score)

        candidate_descriptor = candidate.get("identity_embedding")
        selected_similarity = 0.0
        reference_similarity = 0.0
        if candidate_descriptor is not None and selected_descriptor is not None:
            selected_similarity = float(np.dot(candidate_descriptor, selected_descriptor))
        if candidate_descriptor is not None and reference_descriptor is not None:
            reference_similarity = float(np.dot(candidate_descriptor, reference_descriptor))

        if selected_descriptor is not None and candidate_descriptor is not None:
            score = (selected_similarity * 0.62) + (reference_similarity * 0.18) + (spatial_score * 0.20)
        elif reference_descriptor is not None and candidate_descriptor is not None:
            score = (reference_similarity * 0.72) + (spatial_score * 0.28)
        else:
            score = (iou_score * 0.55) + (position_score * 0.45)

        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_score < minimum_score:
        return None, max(0.0, float(best_score))
    return best_candidate, max(0.0, float(best_score))


def clamp_landmark_point(
    x_norm: float,
    y_norm: float,
    shape: tuple[int, int],
) -> tuple[int, int]:
    height, width = shape[:2]
    x = int(round(max(0.0, min(1.0, x_norm)) * max(1, width - 1)))
    y = int(round(max(0.0, min(1.0, y_norm)) * max(1, height - 1)))
    return x, y


def points_to_box(
    points: list[tuple[int, int]],
    shape: tuple[int, int],
    *,
    padding_ratio: float = 0.03,
) -> tuple[int, int, int, int] | None:
    if not points:
        return None
    height, width = shape[:2]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    pad_x = max(2, int(round(width * padding_ratio)))
    pad_y = max(2, int(round(height * padding_ratio)))
    return clamp_box(
        (
            min(xs) - pad_x,
            min(ys) - pad_y,
            max(xs) + pad_x,
            max(ys) + pad_y,
        ),
        shape,
    )


def build_landmark_identity_signature(
    landmark_lookup: dict[int, tuple[int, int]],
    roi_box: tuple[int, int, int, int] | None,
    indices: list[int],
) -> list[float]:
    if not roi_box:
        return []
    x1, y1, x2, y2 = roi_box
    width = max(1.0, float(x2 - x1))
    height = max(1.0, float(y2 - y1))
    values: list[float] = []
    for index in indices:
        point = landmark_lookup.get(index)
        if not point or len(point) < 2:
            values.extend([0.0, 0.0])
            continue
        values.extend(
            [
                (float(point[0]) - x1) / width,
                (float(point[1]) - y1) / height,
            ]
        )
    return values


def box_from_landmark_indices(
    landmark_lookup: dict[int, tuple[int, int]],
    indices: list[int],
    shape: tuple[int, int],
    *,
    padding_ratio: float = 0.015,
) -> tuple[int, int, int, int] | None:
    points = [landmark_lookup[index] for index in indices if index in landmark_lookup]
    return points_to_box(points, shape, padding_ratio=padding_ratio)


def landmark_edges_from_connections(
    landmark_lookup: dict[int, tuple[int, int]],
    connections: Any,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    for start, end in connections:
        key = (min(int(start), int(end)), max(int(start), int(end)))
        if key in seen:
            continue
        seen.add(key)
        if int(start) in landmark_lookup and int(end) in landmark_lookup:
            edges.append((landmark_lookup[int(start)], landmark_lookup[int(end)]))
    return edges


def mask_to_box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    if mask is None or not np.any(mask):
        return None
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def detect_face_anatomy(
    frame_bgr: np.ndarray,
    gray: np.ndarray,
    face_detector: cv2.CascadeClassifier,
    eye_detector: cv2.CascadeClassifier | None = None,
    smile_detector: cv2.CascadeClassifier | None = None,
) -> dict[str, Any]:
    faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    face_boxes = opencv_rects_to_xyxy(faces)
    face_box = select_primary_box(face_boxes, gray.shape)
    if not face_box:
        return {
            "mode": "visage",
            "backend": "opencv_face_bbox",
            "roi_box": None,
            "roi_mask": np.zeros(gray.shape, dtype=bool),
            "subboxes": {},
            "face_count": 0,
            "face_boxes": [],
            "faces_detected": [],
            "face_candidates": [],
            "face_area_ratio": 0.0,
            "roi_center_x_norm": 0.0,
            "roi_center_y_norm": 0.0,
            "mouth_opening": 0.0,
            "left_eye_opening": 0.0,
            "right_eye_opening": 0.0,
            "left_right_asymmetry": 0.0,
            "landmark_points": [],
        }

    face_candidates = [build_face_candidate_from_box(candidate_box, gray.shape, backend="opencv_face_bbox") for candidate_box in face_boxes]

    height, width = gray.shape[:2]
    x1, y1, x2, y2 = clamp_box(face_box, gray.shape)
    face_roi_gray = gray[y1:y2, x1:x2]
    subboxes = default_face_subboxes((x1, y1, x2, y2))

    if eye_detector is not None and face_roi_gray.size:
        detected_eyes = eye_detector.detectMultiScale(face_roi_gray[: max(1, (y2 - y1) // 2), :], scaleFactor=1.1, minNeighbors=4, minSize=(12, 12))
        eye_boxes = []
        for ex, ey, ew, eh in detected_eyes:
            eye_boxes.append((x1 + int(ex), y1 + int(ey), x1 + int(ex + ew), y1 + int(ey + eh)))
        eye_boxes = sorted(eye_boxes, key=lambda box: (box[0], -box_area(box)))[:2]
        if len(eye_boxes) >= 2:
            subboxes["left_eye"], subboxes["right_eye"] = eye_boxes[0], eye_boxes[1]
            subboxes["left_brow"] = (
                eye_boxes[0][0],
                max(y1, eye_boxes[0][1] - int((y2 - y1) * 0.12)),
                eye_boxes[0][2],
                max(y1 + 1, eye_boxes[0][1] - int((y2 - y1) * 0.03)),
            )
            subboxes["right_brow"] = (
                eye_boxes[1][0],
                max(y1, eye_boxes[1][1] - int((y2 - y1) * 0.12)),
                eye_boxes[1][2],
                max(y1 + 1, eye_boxes[1][1] - int((y2 - y1) * 0.03)),
            )

    if smile_detector is not None and face_roi_gray.size:
        lower_start = max(0, (y2 - y1) // 2)
        lower_gray = face_roi_gray[lower_start:, :]
        mouths = smile_detector.detectMultiScale(lower_gray, scaleFactor=1.5, minNeighbors=15, minSize=(20, 20))
        mouth_box = choose_largest_box(mouths)
        if mouth_box:
            mx1, my1, mx2, my2 = mouth_box
            subboxes["mouth"] = (x1 + mx1, y1 + lower_start + my1, x1 + mx2, y1 + lower_start + my2)

    mouth_box = subboxes["mouth"]
    left_eye_box = subboxes["left_eye"]
    right_eye_box = subboxes["right_eye"]
    landmark_points = [
        ((x1 + x2) // 2, (y1 + y2) // 2),
        ((left_eye_box[0] + left_eye_box[2]) // 2, (left_eye_box[1] + left_eye_box[3]) // 2),
        ((right_eye_box[0] + right_eye_box[2]) // 2, (right_eye_box[1] + right_eye_box[3]) // 2),
        ((mouth_box[0] + mouth_box[2]) // 2, (mouth_box[1] + mouth_box[3]) // 2),
    ]
    primary_candidate = build_face_candidate_from_box(
        (x1, y1, x2, y2),
        gray.shape,
        backend="opencv_face_bbox",
        subboxes=subboxes,
        landmark_points=landmark_points,
    )
    return {
        **primary_candidate,
        "face_count": int(len(faces)),
        "face_boxes": face_boxes,
        "faces_detected": create_face_records(face_boxes, gray.shape),
        "face_candidates": face_candidates,
    }


def detect_face_identity_candidates(
    frame_bgr: np.ndarray,
    gray: np.ndarray,
    face_detector: cv2.CascadeClassifier | None,
    identity_backend: Any | None = None,
) -> list[dict[str, Any]]:
    if face_detector is None:
        return []
    faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    face_boxes = opencv_rects_to_xyxy(faces)
    candidates = [
        build_face_candidate_from_box(candidate_box, gray.shape, backend="opencv_face_bbox")
        for candidate_box in face_boxes
    ]
    if identity_backend is not None and candidates:
        candidates = identity_backend.annotate_candidates(frame_bgr, candidates)
    return candidates


def detect_face_anatomy_mediapipe(
    frame_bgr: np.ndarray,
    face_mesh_detector: Any,
) -> dict[str, Any]:
    mp = load_mediapipe_module()
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = face_mesh_detector.process(frame_rgb)
    face_landmarks = getattr(result, "multi_face_landmarks", None) or []
    if not face_landmarks:
        empty_mask = np.zeros(frame_bgr.shape[:2], dtype=bool)
        return {
            "mode": "visage",
            "backend": "mediapipe_face_mesh",
            "roi_box": None,
            "roi_mask": empty_mask,
            "subboxes": {},
            "face_count": 0,
            "face_boxes": [],
            "faces_detected": [],
            "face_candidates": [],
            "face_area_ratio": 0.0,
            "roi_center_x_norm": 0.0,
            "roi_center_y_norm": 0.0,
            "mouth_opening": 0.0,
            "left_eye_opening": 0.0,
            "right_eye_opening": 0.0,
            "left_right_asymmetry": 0.0,
            "landmark_points": [],
            "landmark_edges": [],
        }

    face_candidates_meta: list[dict[str, Any]] = []
    for face_landmark in face_landmarks:
        landmark_lookup = {
            index: clamp_landmark_point(landmark.x, landmark.y, frame_bgr.shape)
            for index, landmark in enumerate(face_landmark.landmark)
        }
        face_points = list(landmark_lookup.values())
        roi_box = points_to_box(face_points, frame_bgr.shape, padding_ratio=0.02)
        if roi_box is None:
            continue
        mouth_indices = [61, 291, 13, 14, 78, 308, 0, 17, 81, 178, 311, 402]
        left_eye_indices = [33, 133, 160, 159, 158, 157, 173, 144, 145, 153, 154, 155]
        right_eye_indices = [362, 263, 387, 386, 385, 384, 398, 373, 374, 380, 381, 382]
        left_brow_indices = [70, 63, 105, 66, 107, 55, 52, 53, 65]
        right_brow_indices = [336, 296, 334, 293, 300, 285, 282, 283, 295]
        subboxes = {
            "mouth": box_from_landmark_indices(landmark_lookup, mouth_indices, frame_bgr.shape, padding_ratio=0.01),
            "left_eye": box_from_landmark_indices(landmark_lookup, left_eye_indices, frame_bgr.shape, padding_ratio=0.01),
            "right_eye": box_from_landmark_indices(landmark_lookup, right_eye_indices, frame_bgr.shape, padding_ratio=0.01),
            "left_brow": box_from_landmark_indices(landmark_lookup, left_brow_indices, frame_bgr.shape, padding_ratio=0.01),
            "right_brow": box_from_landmark_indices(landmark_lookup, right_brow_indices, frame_bgr.shape, padding_ratio=0.01),
        }
        subboxes = {name: box for name, box in subboxes.items() if box is not None}

        face_height = max(1.0, float((roi_box[3] - roi_box[1]) if roi_box else frame_bgr.shape[0]))
        mouth_opening = abs(landmark_lookup[14][1] - landmark_lookup[13][1]) / face_height if 13 in landmark_lookup and 14 in landmark_lookup else 0.0
        left_eye_opening = abs(landmark_lookup[145][1] - landmark_lookup[159][1]) / face_height if 145 in landmark_lookup and 159 in landmark_lookup else 0.0
        right_eye_opening = abs(landmark_lookup[374][1] - landmark_lookup[386][1]) / face_height if 374 in landmark_lookup and 386 in landmark_lookup else 0.0

        connections: list[tuple[int, int]] = []
        for group in [
            mp.solutions.face_mesh.FACEMESH_FACE_OVAL,
            mp.solutions.face_mesh.FACEMESH_LEFT_EYE,
            mp.solutions.face_mesh.FACEMESH_RIGHT_EYE,
            mp.solutions.face_mesh.FACEMESH_LIPS,
            mp.solutions.face_mesh.FACEMESH_LEFT_EYEBROW,
            mp.solutions.face_mesh.FACEMESH_RIGHT_EYEBROW,
        ]:
            connections.extend((int(start), int(end)) for start, end in group)

        landmark_points = [
            landmark_lookup[index]
            for index in [1, 13, 14, 33, 133, 159, 145, 362, 263, 386, 374, 61, 291]
            if index in landmark_lookup
        ]
        identity_signature = build_landmark_identity_signature(
            landmark_lookup,
            roi_box,
            MEDIAPIPE_IDENTITY_LANDMARK_INDICES,
        )

        face_candidates_meta.append(
            build_face_candidate_from_box(
                roi_box,
                frame_bgr.shape,
                backend="mediapipe_face_mesh",
                subboxes=subboxes,
                landmark_points=landmark_points,
                landmark_edges=landmark_edges_from_connections(landmark_lookup, connections),
                identity_signature=identity_signature,
                mouth_opening=mouth_opening,
                left_eye_opening=left_eye_opening,
                right_eye_opening=right_eye_opening,
                left_right_asymmetry=abs(float(left_eye_opening) - float(right_eye_opening)),
            )
        )

    if not face_candidates_meta:
        empty_mask = np.zeros(frame_bgr.shape[:2], dtype=bool)
        return {
            "mode": "visage",
            "backend": "mediapipe_face_mesh",
            "roi_box": None,
            "roi_mask": empty_mask,
            "subboxes": {},
            "face_count": 0,
            "face_boxes": [],
            "faces_detected": [],
            "face_candidates": [],
            "face_area_ratio": 0.0,
            "roi_center_x_norm": 0.0,
            "roi_center_y_norm": 0.0,
            "mouth_opening": 0.0,
            "left_eye_opening": 0.0,
            "right_eye_opening": 0.0,
            "left_right_asymmetry": 0.0,
            "landmark_points": [],
            "landmark_edges": [],
        }

    face_boxes = [candidate.get("roi_box") for candidate in face_candidates_meta if candidate.get("roi_box")]
    primary_candidate = max(face_candidates_meta, key=lambda candidate: box_area(candidate.get("roi_box")))
    return {
        **primary_candidate,
        "face_count": int(len(face_landmarks)),
        "face_boxes": face_boxes,
        "faces_detected": create_face_records(face_boxes, frame_bgr.shape),
        "face_candidates": face_candidates_meta,
    }


def detect_body_anatomy(
    frame_bgr: np.ndarray,
    body_detector: cv2.HOGDescriptor,
) -> dict[str, Any]:
    height, width = frame_bgr.shape[:2]
    rects, _weights = body_detector.detectMultiScale(frame_bgr, winStride=(8, 8), padding=(8, 8), scale=1.05)
    body_box = choose_largest_box(rects)
    if not body_box:
        body_box = (0, 0, width, height)
        backend = "frame_fallback"
    else:
        backend = "hog_person_detector"

    x1, y1, x2, y2 = clamp_box(body_box, frame_bgr.shape)
    body_width = max(1, x2 - x1)
    body_height = max(1, y2 - y1)
    subboxes = {
        "head": (x1 + int(body_width * 0.25), y1, x1 + int(body_width * 0.75), y1 + int(body_height * 0.2)),
        "torso": (x1 + int(body_width * 0.18), y1 + int(body_height * 0.2), x1 + int(body_width * 0.82), y1 + int(body_height * 0.62)),
        "left_arm": (x1, y1 + int(body_height * 0.18), x1 + int(body_width * 0.32), y1 + int(body_height * 0.72)),
        "right_arm": (x1 + int(body_width * 0.68), y1 + int(body_height * 0.18), x2, y1 + int(body_height * 0.72)),
    }
    center_x_norm, center_y_norm = box_center_norm((x1, y1, x2, y2), frame_bgr.shape)
    landmark_points = [
        ((x1 + x2) // 2, y1 + int(body_height * 0.1)),
        ((x1 + x2) // 2, y1 + int(body_height * 0.4)),
        (x1 + int(body_width * 0.22), y1 + int(body_height * 0.34)),
        (x1 + int(body_width * 0.78), y1 + int(body_height * 0.34)),
        (x1 + int(body_width * 0.38), y1 + int(body_height * 0.82)),
        (x1 + int(body_width * 0.62), y1 + int(body_height * 0.82)),
    ]
    return {
        "mode": "corps_entier",
        "backend": backend,
        "roi_box": (x1, y1, x2, y2),
        "roi_mask": box_to_mask(frame_bgr.shape, (x1, y1, x2, y2)),
        "subboxes": subboxes,
        "roi_center_x_norm": center_x_norm,
        "roi_center_y_norm": center_y_norm,
        "landmark_points": landmark_points,
    }


def detect_body_anatomy_mediapipe(
    frame_bgr: np.ndarray,
    pose_detector: Any,
) -> dict[str, Any]:
    mp = load_mediapipe_module()
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = pose_detector.process(frame_rgb)
    pose_landmarks = getattr(result, "pose_landmarks", None)
    segmentation_mask = getattr(result, "segmentation_mask", None)

    if pose_landmarks is None:
        full_box = (0, 0, frame_bgr.shape[1], frame_bgr.shape[0])
        return {
            "mode": "corps_entier",
            "backend": "mediapipe_pose_fallback",
            "roi_box": full_box,
            "roi_mask": box_to_mask(frame_bgr.shape, full_box),
            "subboxes": {},
            "roi_center_x_norm": 0.5,
            "roi_center_y_norm": 0.5,
            "landmark_points": [],
            "landmark_edges": [],
        }

    landmark_lookup: dict[int, tuple[int, int]] = {}
    for index, landmark in enumerate(pose_landmarks.landmark):
        visibility = float(getattr(landmark, "visibility", 1.0) or 0.0)
        if visibility < 0.35:
            continue
        landmark_lookup[index] = clamp_landmark_point(landmark.x, landmark.y, frame_bgr.shape)

    roi_mask = None
    if segmentation_mask is not None:
        roi_mask = np.asarray(segmentation_mask) > 0.35
    if roi_mask is None or not np.any(roi_mask):
        roi_box = points_to_box(list(landmark_lookup.values()), frame_bgr.shape, padding_ratio=0.03)
        roi_mask = box_to_mask(frame_bgr.shape, roi_box)
    else:
        roi_box = mask_to_box(roi_mask)

    roi_center_x_norm, roi_center_y_norm = box_center_norm(roi_box, frame_bgr.shape)
    subboxes = {
        "head": box_from_landmark_indices(landmark_lookup, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], frame_bgr.shape, padding_ratio=0.01),
        "torso": box_from_landmark_indices(landmark_lookup, [11, 12, 23, 24], frame_bgr.shape, padding_ratio=0.02),
        "left_arm": box_from_landmark_indices(landmark_lookup, [11, 13, 15, 17, 19, 21], frame_bgr.shape, padding_ratio=0.02),
        "right_arm": box_from_landmark_indices(landmark_lookup, [12, 14, 16, 18, 20, 22], frame_bgr.shape, padding_ratio=0.02),
    }
    subboxes = {name: box for name, box in subboxes.items() if box is not None}

    landmark_points = list(landmark_lookup.values())
    return {
        "mode": "corps_entier",
        "backend": "mediapipe_pose",
        "roi_box": roi_box,
        "roi_mask": roi_mask,
        "subboxes": subboxes,
        "roi_center_x_norm": roi_center_x_norm,
        "roi_center_y_norm": roi_center_y_norm,
        "landmark_points": landmark_points,
        "landmark_edges": landmark_edges_from_connections(landmark_lookup, mp.solutions.pose.POSE_CONNECTIONS),
    }


def compute_mask_flow_metrics(
    flow: np.ndarray,
    magnitude: np.ndarray,
    mask: np.ndarray,
    motion_threshold: float,
) -> dict[str, float]:
    if mask is None or not np.any(mask):
        return {
            "mean": 0.0,
            "std": 0.0,
            "max": 0.0,
            "active_ratio": 0.0,
            "energy": 0.0,
            "direction_coherence": 0.0,
            "directional_entropy": 0.0,
            "directional_entropy_norm": 0.0,
            "divergence_abs_mean": 0.0,
            "curl_abs_mean": 0.0,
        }

    roi_mag = magnitude[mask]
    roi_dx = flow[..., 0][mask]
    roi_dy = flow[..., 1][mask]
    total_weight = float(np.sum(roi_mag)) + 1e-9
    unit_x = roi_dx / (roi_mag + 1e-9)
    unit_y = roi_dy / (roi_mag + 1e-9)
    coherence = math.sqrt(float(np.sum(unit_x * roi_mag)) ** 2 + float(np.sum(unit_y * roi_mag)) ** 2) / total_weight

    _prob, entropy, max_entropy = compute_directional_histogram(flow, magnitude, mask=mask, bins=12)
    entropy_norm = max(0.0, (float(entropy) / float(max_entropy)) if max_entropy > 0 else 0.0)

    du_dx = np.gradient(flow[..., 0], axis=1)
    dv_dy = np.gradient(flow[..., 1], axis=0)
    dv_dx = np.gradient(flow[..., 1], axis=1)
    du_dy = np.gradient(flow[..., 0], axis=0)
    divergence = du_dx + dv_dy
    curl = dv_dx - du_dy

    return {
        "mean": float(np.mean(roi_mag)),
        "std": float(np.std(roi_mag)),
        "max": float(np.max(roi_mag)),
        "active_ratio": float(np.mean(roi_mag >= motion_threshold)),
        "energy": float(np.mean(np.square(roi_mag))),
        "direction_coherence": float(coherence),
        "directional_entropy": float(entropy),
        "directional_entropy_norm": float(entropy_norm),
        "divergence_abs_mean": float(np.mean(np.abs(divergence[mask]))),
        "curl_abs_mean": float(np.mean(np.abs(curl[mask]))),
    }


def annotate_frame_with_anatomy(
    frame_bgr: np.ndarray,
    flow: np.ndarray,
    anatomy: dict[str, Any],
    metrics: dict[str, Any],
    *,
    time_sec: float,
) -> np.ndarray:
    annotated = frame_bgr.copy()
    roi_box = anatomy.get("roi_box")
    mode = str(anatomy.get("mode", "") or "")
    subboxes = anatomy.get("subboxes", {}) or {}
    landmark_points = anatomy.get("landmark_points", []) or []
    landmark_edges = anatomy.get("landmark_edges", []) or []
    if roi_box:
        x1, y1, x2, y2 = clamp_box(roi_box, frame_bgr.shape)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 90), 2)

    box_colors = {
        "mouth": (0, 140, 255),
        "left_eye": (255, 180, 0),
        "right_eye": (255, 180, 0),
        "left_brow": (180, 0, 255),
        "right_brow": (180, 0, 255),
        "head": (255, 170, 0),
        "torso": (0, 180, 255),
        "left_arm": (180, 255, 0),
        "right_arm": (180, 255, 0),
    }
    for name, box in subboxes.items():
        x1, y1, x2, y2 = clamp_box(box, frame_bgr.shape)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_colors.get(name, (255, 255, 255)), 1)
        cv2.putText(annotated, name, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, box_colors.get(name, (255, 255, 255)), 1, cv2.LINE_AA)

    for start, end in landmark_edges:
        if len(start) >= 2 and len(end) >= 2:
            cv2.line(
                annotated,
                (int(start[0]), int(start[1])),
                (int(end[0]), int(end[1])),
                (80, 220, 255),
                1,
                cv2.LINE_AA,
            )

    for point in landmark_points:
        if len(point) >= 2:
            cv2.circle(annotated, (int(point[0]), int(point[1])), 2, (255, 255, 255), -1)

    roi_mask = anatomy.get("roi_mask")
    vectors_preview = build_flow_vectors_preview(annotated, flow, step=24, scale=2.0, mask=roi_mask)
    height = vectors_preview.shape[0]
    panel_width = 340
    panel = np.full((height, panel_width, 3), 245, dtype=np.uint8)
    lines = [
        f"Mode: {mode}",
        f"Temps: {time_sec:.2f} s",
        f"Flow ROI: {float(metrics.get('roi_flow_mean', 0.0) or 0.0):.3f}",
        f"Energie ROI: {float(metrics.get('roi_motion_energy', 0.0) or 0.0):.3f}",
        f"Ratio actif: {float(metrics.get('roi_active_ratio', 0.0) or 0.0):.3f}",
        f"Coherence: {float(metrics.get('roi_direction_coherence', 0.0) or 0.0):.3f}",
        f"Entropie dir.: {float(metrics.get('roi_directional_entropy', 0.0) or 0.0):.3f}",
        f"Entropie norm.: {float(metrics.get('roi_directional_entropy_norm', 0.0) or 0.0):.3f}",
    ]
    tracking_status = str(metrics.get("tracked_face_status", "") or "").strip()
    if tracking_status:
        lines.extend([
            f"Suivi: {tracking_status}",
            f"Confiance: {float(metrics.get('tracked_face_confidence', 0.0) or 0.0):.3f}",
            f"Id. visage: {float(metrics.get('tracked_face_identity_similarity', 0.0) or 0.0):.3f}",
            f"Backend id.: {str(metrics.get('tracked_face_identity_backend', '') or '')}",
        ])
        if str(metrics.get("tracked_face_lost", "") or "").strip().lower() == "oui":
            lines.append(f"Perdu: oui ({int(metrics.get('tracked_face_loss_streak', 0) or 0)})")
    if mode == "visage":
        lines.extend([
            f"Bouche: {float(metrics.get('mouth_opening', 0.0) or 0.0):.3f}",
            f"Oeil G: {float(metrics.get('left_eye_opening', 0.0) or 0.0):.3f}",
            f"Oeil D: {float(metrics.get('right_eye_opening', 0.0) or 0.0):.3f}",
            f"Asymetrie: {float(metrics.get('left_right_asymmetry', 0.0) or 0.0):.3f}",
            f"E bouche: {float(metrics.get('mouth_motion_energy', 0.0) or 0.0):.3f}",
            f"E yeux: {float(metrics.get('eyes_motion_energy', 0.0) or 0.0):.3f}",
            f"E sourcils: {float(metrics.get('brows_motion_energy', 0.0) or 0.0):.3f}",
        ])
    else:
        lines.extend([
            f"Centre deplacement: {float(metrics.get('body_center_displacement', 0.0) or 0.0):.3f}",
            f"E tete: {float(metrics.get('head_motion_energy', 0.0) or 0.0):.3f}",
            f"E torse: {float(metrics.get('torso_motion_energy', 0.0) or 0.0):.3f}",
            f"E bras G: {float(metrics.get('left_arm_motion_energy', 0.0) or 0.0):.3f}",
            f"E bras D: {float(metrics.get('right_arm_motion_energy', 0.0) or 0.0):.3f}",
        ])
    lines.extend([
        f"Divergence: {float(metrics.get('roi_divergence_abs_mean', 0.0) or 0.0):.3f}",
        f"Rotationnel: {float(metrics.get('roi_curl_abs_mean', 0.0) or 0.0):.3f}",
        f"dE/dt: {float(metrics.get('energy_time_derivative', 0.0) or 0.0):.3f}",
        f"Pic activite: {metrics.get('activity_peak_flag', 'non') or 'non'}",
    ])
    for idx, line in enumerate(lines):
        y = 24 + idx * 22
        if y >= height - 8:
            break
        cv2.putText(panel, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (35, 35, 35), 1, cv2.LINE_AA)
    return np.hstack([vectors_preview, panel])


def build_anatomy_metrics(
    anatomy: dict[str, Any],
    flow: np.ndarray,
    magnitude: np.ndarray,
    motion_threshold: float,
    previous_roi_energy: float | None = None,
    previous_center: tuple[float, float] | None = None,
) -> dict[str, Any]:
    roi_mask = anatomy.get("roi_mask")
    roi_metrics = compute_mask_flow_metrics(flow, magnitude, roi_mask, motion_threshold)
    roi_box = anatomy.get("roi_box")
    roi_surface_px = int(np.count_nonzero(roi_mask)) if roi_mask is not None else 0
    center_x_norm = float(anatomy.get("roi_center_x_norm", 0.0) or 0.0)
    center_y_norm = float(anatomy.get("roi_center_y_norm", 0.0) or 0.0)
    out: dict[str, Any] = {
        "anatomy_mode": anatomy.get("mode", ""),
        "anatomy_backend": anatomy.get("backend", ""),
        "face_analysis_mode": anatomy.get("face_analysis_mode", ""),
        "roi_surface_px": roi_surface_px,
        "roi_surface_ratio": round(float(roi_surface_px) / max(1, magnitude.shape[0] * magnitude.shape[1]), 6),
        "roi_center_x_norm": round(center_x_norm, 6),
        "roi_center_y_norm": round(center_y_norm, 6),
        "roi_flow_mean": round(roi_metrics["mean"], 6),
        "roi_flow_std": round(roi_metrics["std"], 6),
        "roi_flow_max": round(roi_metrics["max"], 6),
        "roi_active_ratio": round(roi_metrics["active_ratio"], 6),
        "roi_motion_energy": round(roi_metrics["energy"], 6),
        "roi_direction_coherence": round(roi_metrics["direction_coherence"], 6),
        "roi_directional_entropy": round(roi_metrics["directional_entropy"], 6),
        "roi_directional_entropy_norm": round(roi_metrics["directional_entropy_norm"], 6),
        "roi_divergence_abs_mean": round(roi_metrics["divergence_abs_mean"], 6),
        "roi_curl_abs_mean": round(roi_metrics["curl_abs_mean"], 6),
        "energy_time_derivative": round(roi_metrics["energy"] - (previous_roi_energy or 0.0), 6),
        "activity_peak_flag": "non",
        "tracked_face_locked": anatomy.get("tracked_face_locked", ""),
        "tracked_face_confidence": round(float(anatomy.get("tracked_face_confidence", 0.0) or 0.0), 6),
        "tracked_face_identity_similarity": round(float(anatomy.get("tracked_face_identity_similarity", 0.0) or 0.0), 6),
        "tracked_face_identity_backend": anatomy.get("tracked_face_identity_backend", ""),
        "tracked_face_lost": anatomy.get("tracked_face_lost", ""),
        "tracked_face_status": anatomy.get("tracked_face_status", ""),
        "tracked_face_loss_streak": int(anatomy.get("tracked_face_loss_streak", 0) or 0),
    }
    if roi_box:
        x1, y1, x2, y2 = roi_box
        out["roi_box_x1"] = x1
        out["roi_box_y1"] = y1
        out["roi_box_x2"] = x2
        out["roi_box_y2"] = y2

    subboxes = anatomy.get("subboxes", {}) or {}
    if anatomy.get("mode") == "visage":
        mouth_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("mouth")), motion_threshold)
        left_eye_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("left_eye")), motion_threshold)
        right_eye_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("right_eye")), motion_threshold)
        left_brow_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("left_brow")), motion_threshold)
        right_brow_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("right_brow")), motion_threshold)
        out.update({
            "mouth_opening": anatomy.get("mouth_opening", 0.0),
            "left_eye_opening": anatomy.get("left_eye_opening", 0.0),
            "right_eye_opening": anatomy.get("right_eye_opening", 0.0),
            "left_right_asymmetry": anatomy.get("left_right_asymmetry", 0.0),
            "mouth_motion_energy": round(mouth_metrics["energy"], 6),
            "eyes_motion_energy": round((left_eye_metrics["energy"] + right_eye_metrics["energy"]) / 2.0, 6),
            "brows_motion_energy": round((left_brow_metrics["energy"] + right_brow_metrics["energy"]) / 2.0, 6),
            "face_count": anatomy.get("face_count", 0),
            "tracked_face_count": len(anatomy.get("tracked_faces", []) or anatomy.get("faces_detected", []) or []),
            "primary_face_track_id": int(anatomy.get("primary_face_track_id", 0) or 0),
            "primary_face_order": int(anatomy.get("primary_face_order", 0) or 0),
            "face_area_ratio": round(float(anatomy.get("face_area_ratio", 0.0) or 0.0), 6),
        })
    else:
        head_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("head")), motion_threshold)
        torso_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("torso")), motion_threshold)
        left_arm_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("left_arm")), motion_threshold)
        right_arm_metrics = compute_mask_flow_metrics(flow, magnitude, box_to_mask(magnitude.shape, subboxes.get("right_arm")), motion_threshold)
        current_center = (center_x_norm, center_y_norm)
        displacement = 0.0
        if previous_center is not None:
            displacement = math.sqrt((current_center[0] - previous_center[0]) ** 2 + (current_center[1] - previous_center[1]) ** 2)
        out.update({
            "body_center_displacement": round(displacement, 6),
            "head_motion_energy": round(head_metrics["energy"], 6),
            "torso_motion_energy": round(torso_metrics["energy"], 6),
            "left_arm_motion_energy": round(left_arm_metrics["energy"], 6),
            "right_arm_motion_energy": round(right_arm_metrics["energy"], 6),
        })
    return out


def apply_simple_activity_peaks(rows: list[dict[str, Any]], key: str = "roi_motion_energy") -> None:
    if len(rows) < 3:
        return
    values = np.array([float(row.get(key, 0.0) or 0.0) for row in rows], dtype=float)
    threshold = float(np.mean(values) + np.std(values))
    for index in range(1, len(rows) - 1):
        current = values[index]
        if current >= values[index - 1] and current >= values[index + 1] and current >= threshold:
            rows[index]["activity_peak_flag"] = "oui"


def save_heatmap_png(heatmap: np.ndarray, output_path: str | Path) -> None:
    if heatmap.size == 0 or float(np.max(heatmap)) <= 0:
        return

    normalised = heatmap / float(np.max(heatmap))
    image = np.uint8(np.clip(normalised * 255.0, 0, 255))
    image = cv2.resize(image, (960, 540), interpolation=cv2.INTER_CUBIC)
    image = cv2.applyColorMap(image, cv2.COLORMAP_INFERNO)
    cv2.imwrite(str(output_path), image)


def resize_frame_to_reference(
    frame_bgr: np.ndarray,
    reference_shape: tuple[int, int] | None,
) -> np.ndarray:
    if reference_shape is None or frame_bgr is None:
        return frame_bgr
    reference_height, reference_width = reference_shape[:2]
    frame_height, frame_width = frame_bgr.shape[:2]
    if frame_height == reference_height and frame_width == reference_width:
        return frame_bgr
    interpolation = cv2.INTER_AREA if frame_height > reference_height or frame_width > reference_width else cv2.INTER_LINEAR
    return cv2.resize(frame_bgr, (reference_width, reference_height), interpolation=interpolation)


def list_image_sequence(source_dir: str | Path) -> list[Path]:
    base = Path(source_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise FileNotFoundError(f"Dossier d'images introuvable: {base}")
    return sorted(
        (
            path for path in base.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: natural_sort_key(path.name),
    )


def is_image_directory(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    return any(
        child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
        for child in path.iterdir()
    )


def resolve_video_file_candidate(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_file():
        return candidate
    if candidate.is_dir():
        video_candidates = sorted(
            (
                child for child in candidate.rglob("*")
                if child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS
            ),
            key=lambda child: child.stat().st_mtime,
            reverse=True,
        )
        if video_candidates:
            return video_candidates[0]
        raise ValueError(f"Aucun fichier vidéo n'a été trouvé dans le dossier source : {candidate}")
    raise ValueError(f"Source vidéo introuvable ou invalide : {candidate}")


def analyse_video(
    source: str,
    output_dir: str | Path,
    sample_fps: float = 1.0,
    window_sec: float = 1.0,
    motion_threshold: float = 0.6,
    cookies_path: str | None = None,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> dict[str, Any]:
    """
    Analyse vidéo :
    - optical flow dense (Farneback)
    - détection simple des visages
    - heatmap globale des mouvements
    - agrégation par fenêtres temporelles
    """
    destination = ensure_directory(output_dir)
    session_id = utc_session_id("mouvements")
    progress_path = write_progress_snapshot(
        destination,
        "mouvements",
        "prepare_source",
        6,
        "Préparation de la source vidéo."
    )
    raw_source_path = resolve_media_source(
        source,
        output_dir=destination / "downloads",
        prefer="video",
        cookies_path=cookies_path,
        start_sec=start_sec if is_youtube_url(source) else None,
        end_sec=end_sec if is_youtube_url(source) else None,
    )
    raw_source_path = resolve_video_file_candidate(raw_source_path)
    write_progress_snapshot(
        destination,
        "mouvements",
        "normalise_source",
        16,
        "Normalisation de la source vidéo.",
        {"source_resolved": str(raw_source_path)}
    )

    source_path = ensure_video_mp4(
        source_path=raw_source_path,
        output_dir=destination / "downloads",
    )
    if not is_youtube_url(source) and (start_sec is not None or end_sec is not None):
        source_path = clip_video_interval(
            source_path=source_path,
            output_dir=destination / "downloads",
            start_sec=start_sec,
            end_sec=end_sec,
        )
    write_progress_snapshot(
        destination,
        "mouvements",
        "open_video",
        24,
        "Ouverture de la vidéo et préparation de l'échantillonnage.",
        {"source_prepared": str(source_path)}
    )

    detector = load_face_detector()

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir la vidéo: {source_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_sec = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    frame_step = max(1, int(round(fps / max(0.5, sample_fps))))
    heatmap_grid = np.zeros((18, 32), dtype=np.float32)

    frame_rows: list[dict[str, Any]] = []
    window_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    keyframe_paths: dict[int, str] = {}

    frame_index = 0
    sampled_index = 0
    previous_gray = None
    previous_time = None
    reference_frame_shape: tuple[int, int] | None = None
    flow_panel_dir = ensure_directory(destination / "flow_panels")
    frame_preview_dir = ensure_directory(destination / "sampled_frames")
    magnitude_dir = ensure_directory(destination / "magnitude")
    hsv_dir = ensure_directory(destination / "hsv")
    overlay_dir = ensure_directory(destination / "superposition")
    vectors_dir = ensure_directory(destination / "vecteurs")
    entropy_dir = ensure_directory(destination / "entropie_directionnelle")

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        if reference_frame_shape is None:
            reference_frame_shape = frame.shape[:2]
        else:
            frame = resize_frame_to_reference(frame, reference_frame_shape)

        frame_index += 1
        if frame_index % frame_step != 0:
            continue

        sampled_index += 1
        time_sec = frame_index / fps if fps > 0 else 0.0
        if frame_count > 0 and sampled_index % 20 == 0:
            loop_progress = min(74, 30 + int((frame_index / max(frame_count, 1)) * 40))
            write_progress_snapshot(
                destination,
                "mouvements",
                "analyse_flux",
                loop_progress,
                "Calcul de l'optical flow et des indicateurs visuels.",
                {"sampled_frames": sampled_index, "time_sec": round(time_sec, 3)}
            )
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        face_count = int(len(faces))
        face_area_ratio = 0.0
        largest_face = None
        if face_count:
            largest_face = max(faces, key=lambda item: item[2] * item[3])
            face_area_ratio = float(largest_face[2] * largest_face[3]) / float(frame.shape[0] * frame.shape[1])

        if previous_gray is None:
            panel_stem = Path(image_path).stem
            frame_preview_path = frame_preview_dir / f"{panel_stem}_brute.jpg"
            cv2.imwrite(str(frame_preview_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            frame_rows.append(
                {
                    "frame_index": sampled_index,
                    "time_sec": round(time_sec, 6),
                    "delta_sec": 0.0,
                    "image_path": str(image_path),
                    "frame_preview_path": str(frame_preview_path),
                    "anatomy_mode": anatomy_mode,
                    "anatomy_backend": "",
                    "frame_role": "reference",
                }
            )
            previous_gray = gray
            previous_time = time_sec
            continue

        flow = cv2.calcOpticalFlowFarneback(
            previous_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        magnitude, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=False)
        motion_mean = float(np.mean(magnitude))
        motion_std = float(np.std(magnitude))
        motion_peak = float(np.percentile(magnitude, 95))
        active_ratio = float(np.mean(magnitude >= motion_threshold))

        weights = magnitude + 1e-9
        dx = float(np.sum(flow[..., 0] * weights) / np.sum(weights))
        dy = float(np.sum(flow[..., 1] * weights) / np.sum(weights))
        motion_vector_norm = math.sqrt(dx * dx + dy * dy)
        motion_angle_deg = math.degrees(math.atan2(dy, dx)) if motion_vector_norm > 0 else 0.0
        direction_label = flow_direction_label(dx, dy)
        color_metrics = compute_color_metrics(frame)

        reduced = cv2.resize(magnitude, (heatmap_grid.shape[1], heatmap_grid.shape[0]), interpolation=cv2.INTER_AREA)
        heatmap_grid += reduced.astype(np.float32)
        frame_preview_path = frame_preview_dir / f"frame_{frame_index:06d}.jpg"
        cv2.imwrite(str(frame_preview_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        view_paths = save_flow_view_images(
            frame,
            flow,
            magnitude,
            stem=f"frame_{frame_index:06d}",
            magnitude_dir=magnitude_dir,
            hsv_dir=hsv_dir,
            overlay_dir=overlay_dir,
            vectors_dir=vectors_dir,
            entropy_dir=entropy_dir,
            panel_dir=flow_panel_dir,
            entropy_mask=None,
        )

        hottest_idx = np.unravel_index(int(np.argmax(reduced)), reduced.shape)
        heat_y, heat_x = hottest_idx
        heat_x_norm = round(float(heat_x) / max(1, reduced.shape[1] - 1), 6)
        heat_y_norm = round(float(heat_y) / max(1, reduced.shape[0] - 1), 6)

        row = {
            "frame_index": frame_index,
            "time_sec": round(time_sec, 6),
            "delta_sec": round(max(0.0, time_sec - (previous_time or time_sec)), 6),
            "motion_mean": round(motion_mean, 6),
            "motion_std": round(motion_std, 6),
            "motion_peak_p95": round(motion_peak, 6),
            "motion_active_ratio": round(active_ratio, 6),
            "direction_dx": round(dx, 6),
            "direction_dy": round(dy, 6),
            "motion_vector_norm": round(motion_vector_norm, 6),
            "motion_angle_deg": round(motion_angle_deg, 6),
            "direction_label": direction_label,
            "heat_x_norm": heat_x_norm,
            "heat_y_norm": heat_y_norm,
            "face_count": face_count,
            "face_area_ratio": round(face_area_ratio, 6),
            "brightness_mean": round(color_metrics["brightness_mean"], 6),
            "contrast_std": round(color_metrics["contrast_std"], 6),
            "hue_mean": round(color_metrics["hue_mean"], 6),
            "saturation_mean": round(color_metrics["saturation_mean"], 6),
            "red_mean": round(color_metrics["red_mean"], 6),
            "green_mean": round(color_metrics["green_mean"], 6),
            "blue_mean": round(color_metrics["blue_mean"], 6),
            "frame_preview_path": str(frame_preview_path),
            **view_paths,
        }
        frame_rows.append(row)

        window_id = int(time_sec // max(0.25, window_sec))
        window_buckets[window_id].append(row)

        if window_id not in keyframe_paths:
            keyframe_dir = ensure_directory(destination / "keyframes")
            keyframe_path = keyframe_dir / f"window_{window_id:04d}.jpg"
            cv2.imwrite(str(keyframe_path), frame)
            keyframe_paths[window_id] = str(keyframe_path)

        previous_gray = gray
        previous_time = time_sec

    capture.release()

    window_rows: list[dict[str, Any]] = []
    write_progress_snapshot(
        destination,
        "mouvements",
        "aggregate_windows",
        82,
        "Agrégation des fenêtres temporelles."
    )
    for window_id in sorted(window_buckets):
        rows = window_buckets[window_id]
        start_sec = window_id * window_sec
        end_sec = start_sec + window_sec

        numeric_keys = [
            "motion_mean",
            "motion_std",
            "motion_peak_p95",
            "motion_active_ratio",
            "direction_dx",
            "direction_dy",
            "motion_vector_norm",
            "motion_angle_deg",
            "heat_x_norm",
            "heat_y_norm",
            "face_count",
            "face_area_ratio",
            "brightness_mean",
            "contrast_std",
            "hue_mean",
            "saturation_mean",
            "red_mean",
            "green_mean",
            "blue_mean",
        ]
        numeric_values = {
            key: round(float(np.mean([float(row[key]) for row in rows])), 6)
            for key in numeric_keys
        }

        direction_counter = Counter(row["direction_label"] for row in rows if row["direction_label"])
        dominant_direction = direction_counter.most_common(1)[0][0] if direction_counter else ""

        window_rows.append(
            {
                "window_id": window_id,
                "start_sec": round(start_sec, 6),
                "end_sec": round(min(end_sec, duration_sec) if duration_sec else end_sec, 6),
                "frame_samples": len(rows),
                **numeric_values,
                "dominant_direction": dominant_direction,
                "keyframe_path": keyframe_paths.get(window_id, ""),
            }
        )

    heatmap_path = destination / "motion_heatmap.png"
    save_heatmap_png(heatmap_grid, heatmap_path)

    chart_path = build_movement_altair_chart(window_rows, destination / "mouvements_timeline_altair.png")
    write_progress_snapshot(
        destination,
        "mouvements",
        "write_exports",
        94,
        "Écriture des exports mouvements."
    )

    summary = {
        "session_id": session_id,
        "source": source,
        "cookies_path": cookies_path,
        "source_resolved": str(raw_source_path),
        "source_prepared": str(source_path),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "fps_original": round(float(fps), 6),
        "duration_sec": round(float(duration_sec), 6),
        "sample_fps": round(float(sample_fps), 6),
        "window_sec": round(float(window_sec), 6),
        "frame_samples": len(frame_rows),
        "window_count": len(window_rows),
        "chart_png": chart_path,
        "progression_json": str(progress_path),
        "indicateurs_video": {
            "motion_mean": "Agitation moyenne dans la fenêtre.",
            "motion_peak_p95": "Pic de mouvement robuste.",
            "motion_active_ratio": "Part de l'image en mouvement actif.",
            "dominant_direction": "Direction dominante du flux optique.",
            "motion_vector_norm / motion_angle_deg": "Norme et orientation du vecteur moyen de mouvement.",
            "heat_x_norm / heat_y_norm": "Zone chaude du mouvement dans l'image.",
            "brightness_mean / contrast_std / saturation_mean": "Niveau lumineux, contraste et saturation de l'image.",
            "red_mean / green_mean / blue_mean": "Composition colorimétrique moyenne.",
            "face_area_ratio": "Poids relatif du visage principal dans l'image.",
            "roi_directional_entropy": "Entropie directionnelle brute.",
            "roi_directional_entropy_norm": "Entropie directionnelle normalisée entre 0 et 1.",
        },
        "pistes_bateson": [
            "Comparer les ruptures verbales aux pics d'agitation visuelle.",
            "Observer les changements de direction autour des segments sensibles.",
            "Repérer les fenêtres où le verbal, la prosodie et le non-verbal divergent.",
        ],
    }

    frames_csv_path, frames_csv_complete_path, frames_csv_essential_path = write_csv_variants(
        destination / "mouvements_frames.csv",
        frame_rows,
        MOUVEMENTS_FRAME_ESSENTIAL_COLUMNS,
    )
    windows_csv_path, windows_csv_complete_path, windows_csv_essential_path = write_csv_variants(
        destination / "mouvements_windows.csv",
        window_rows,
        MOUVEMENTS_WINDOWS_ESSENTIAL_COLUMNS,
    )
    write_jsonl(destination / "mouvements_windows.jsonl", window_rows)
    write_json(destination / "mouvements_summary.json", summary)
    progress_path = write_progress_snapshot(
        destination,
        "mouvements",
        "completed",
        100,
        "Analyse mouvements terminée.",
        {"frame_samples": len(frame_rows), "window_count": len(window_rows)}
    )

    return {
        "session_id": session_id,
        "source_path": str(source_path),
        "frames_csv": frames_csv_path,
        "frames_csv_complet": frames_csv_complete_path,
        "frames_csv_essentiel": frames_csv_essential_path,
        "windows_csv": windows_csv_path,
        "windows_csv_complet": windows_csv_complete_path,
        "windows_csv_essentiel": windows_csv_essential_path,
        "windows_jsonl": str(destination / "mouvements_windows.jsonl"),
        "heatmap_png": str(heatmap_path),
        "chart_png": str(chart_path),
        "summary_json": str(destination / "mouvements_summary.json"),
        "progression_json": str(progress_path),
        "window_count": len(window_rows),
    }


def analyse_images(
    source: str,
    output_dir: str | Path,
    sample_fps: float = 1.0,
    window_sec: float = 1.0,
    motion_threshold: float = 0.6,
    anatomy_mode: str = "visage",
    anatomy_backend: str = "opencv",
    face_analysis_mode: str = "principal",
    selected_face_box: tuple[float, float, float, float] | None = None,
    selected_face_source_name: str | None = None,
    selected_face_source_index: int | None = None,
) -> dict[str, Any]:
    destination = ensure_directory(output_dir)
    session_id = utc_session_id("mouvements_images")
    progress_path = write_progress_snapshot(
        destination,
        "mouvements",
        "prepare_source",
        8,
        "Préparation de la séquence d'images."
    )
    image_paths = list_image_sequence(source)
    if len(image_paths) < 2:
        raise RuntimeError("Au moins deux images sont nécessaires pour calculer l'optical flow.")

    effective_face_analysis_mode = (
        "multivisage"
        if anatomy_mode == "visage" and str(face_analysis_mode or "").strip().lower() == "multivisage"
        else "manuel"
        if anatomy_mode == "visage" and str(face_analysis_mode or "").strip().lower() == "manuel"
        else "principal"
    )
    manual_selected_source_name = str(selected_face_source_name or "").strip()
    manual_selected_source_index = int(selected_face_source_index) if selected_face_source_index is not None and int(selected_face_source_index) >= 0 else None

    effective_anatomy_backend = anatomy_backend
    backend_warning = ""
    face_mesh_detector = None
    pose_detector = None
    if anatomy_backend == "mediapipe":
        try:
            if anatomy_mode == "visage":
                face_mesh_detector = load_mediapipe_face_mesh()
            else:
                pose_detector = load_mediapipe_pose_detector()
        except Exception as exc:
            effective_anatomy_backend = "opencv"
            backend_warning = (
                "MediaPipe a été demandé mais n'a pas pu être initialisé dans ce contexte. "
                f"Fallback OpenCV utilisé. Détail: {exc}"
            )

    face_detector = load_face_detector() if anatomy_mode == "visage" and (
        effective_anatomy_backend == "opencv" or effective_face_analysis_mode == "manuel"
    ) else None
    eye_detector = load_eye_detector() if effective_anatomy_backend == "opencv" and anatomy_mode == "visage" else None
    smile_detector = load_smile_detector() if effective_anatomy_backend == "opencv" and anatomy_mode == "visage" else None
    body_detector = load_body_detector() if effective_anatomy_backend == "opencv" and anatomy_mode == "corps_entier" else None
    heatmap_grid = np.zeros((18, 32), dtype=np.float32)
    frame_rows: list[dict[str, Any]] = []
    multiface_rows: list[dict[str, Any]] = []
    window_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    keyframe_paths: dict[int, str] = {}
    previous_gray = None
    previous_time = None
    reference_frame_shape: tuple[int, int] | None = None
    previous_face_tracks: list[Any] = []
    next_face_track_id = 1
    flow_panel_dir = ensure_directory(destination / "flow_panels")
    frame_preview_dir = ensure_directory(destination / "sampled_frames")
    magnitude_dir = ensure_directory(destination / "magnitude")
    hsv_dir = ensure_directory(destination / "hsv")
    overlay_dir = ensure_directory(destination / "superposition")
    vectors_dir = ensure_directory(destination / "vecteurs")
    entropy_dir = ensure_directory(destination / "entropie_directionnelle")
    annotated_dir = ensure_directory(destination / "anatomie")
    previous_roi_energy: float | None = None
    previous_roi_center: tuple[float, float] | None = None
    manual_reference_box: tuple[int, int, int, int] | None = None
    manual_reference_descriptor: np.ndarray | None = None
    manual_previous_box: tuple[int, int, int, int] | None = None
    manual_previous_descriptor: np.ndarray | None = None
    manual_loss_streak = 0
    manual_identity_backend = create_face_selection_backend() if anatomy_mode == "visage" and effective_face_analysis_mode == "manuel" else None
    manual_identity_backend_name = getattr(manual_identity_backend, "backend_name", "")
    manual_identity_warning = str(getattr(manual_identity_backend, "warning", "") or "")

    try:
        for sampled_index, image_path in enumerate(image_paths, start=1):
            frame = cv2.imread(str(image_path))
            if frame is None:
                continue

            if reference_frame_shape is None:
                reference_frame_shape = frame.shape[:2]
            else:
                frame = resize_frame_to_reference(frame, reference_frame_shape)

            time_sec = (sampled_index - 1) / max(sample_fps, 0.5)
            if sampled_index % 20 == 0:
                loop_progress = min(74, 24 + int((sampled_index / max(len(image_paths), 1)) * 44))
                write_progress_snapshot(
                    destination,
                    "mouvements",
                    "analyse_flux",
                    loop_progress,
                    "Calcul de l'optical flow sur la séquence d'images.",
                    {"sampled_frames": sampled_index, "time_sec": round(time_sec, 3)}
                )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            manual_anchor_ready = (
                effective_face_analysis_mode == "manuel"
                and manual_reference_box is None
                and bool(selected_face_box)
                and (
                    (manual_selected_source_index is not None and (sampled_index - 1) == manual_selected_source_index)
                    or (
                        manual_selected_source_index is None
                        and not manual_selected_source_name
                    )
                    or Path(image_path).name == manual_selected_source_name
                )
            )
            if manual_anchor_ready:
                manual_reference_box = denormalize_selected_face_box(selected_face_box, gray.shape)
            if (
                effective_face_analysis_mode == "manuel"
                and manual_reference_box is not None
                and manual_reference_descriptor is None
                and not getattr(manual_identity_backend, "active", False)
            ):
                manual_reference_descriptor = compute_face_descriptor(gray, manual_reference_box)

            if previous_gray is None:
                if anatomy_mode == "visage" and effective_face_analysis_mode == "manuel" and manual_reference_box is not None:
                    if effective_anatomy_backend == "mediapipe":
                        initial_anatomy = detect_face_anatomy_mediapipe(frame, face_mesh_detector)
                    else:
                        initial_anatomy = detect_face_anatomy(frame, gray, face_detector, eye_detector, smile_detector)
                    initial_tracking_candidates = initial_anatomy.get("face_candidates", []) or []
                    if manual_identity_backend is not None and initial_tracking_candidates:
                        initial_tracking_candidates = manual_identity_backend.annotate_candidates(
                            frame,
                            initial_tracking_candidates,
                        )
                    initial_anatomy["face_candidates"] = initial_tracking_candidates
                    if not initial_tracking_candidates and getattr(manual_identity_backend, "active", False) and face_detector is not None:
                        initial_tracking_candidates = detect_face_identity_candidates(
                            frame,
                            gray,
                            face_detector,
                            manual_identity_backend,
                        )
                    initial_candidate = choose_face_candidate_for_reference(
                        initial_tracking_candidates,
                        manual_reference_box,
                    )
                    if initial_candidate is not None:
                        snapped_box = initial_candidate.get("roi_box") or manual_reference_box
                        manual_reference_box = snapped_box
                        manual_previous_box = snapped_box
                        snapped_descriptor = None
                        if manual_identity_backend is not None:
                            snapped_descriptor = manual_identity_backend.descriptor_from_candidate(frame, initial_candidate)
                        if snapped_descriptor is None:
                            snapped_descriptor = compute_face_descriptor(gray, snapped_box, candidate=initial_candidate)
                        if snapped_descriptor is not None:
                            manual_reference_descriptor = snapped_descriptor
                            manual_previous_descriptor = snapped_descriptor
                previous_gray = gray
                previous_time = time_sec
                continue

            flow = cv2.calcOpticalFlowFarneback(
                previous_gray,
                gray,
                None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0,
            )
            magnitude, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=False)
            motion_mean = float(np.mean(magnitude))
            motion_std = float(np.std(magnitude))
            motion_peak = float(np.percentile(magnitude, 95))
            active_ratio = float(np.mean(magnitude >= motion_threshold))

            weights = magnitude + 1e-9
            dx = float(np.sum(flow[..., 0] * weights) / np.sum(weights))
            dy = float(np.sum(flow[..., 1] * weights) / np.sum(weights))
            motion_vector_norm = math.sqrt(dx * dx + dy * dy)
            motion_angle_deg = math.degrees(math.atan2(dy, dx)) if motion_vector_norm > 0 else 0.0
            direction_label = flow_direction_label(dx, dy)
            color_metrics = compute_color_metrics(frame)

            reduced = cv2.resize(magnitude, (heatmap_grid.shape[1], heatmap_grid.shape[0]), interpolation=cv2.INTER_AREA)
            heatmap_grid += reduced.astype(np.float32)
            panel_stem = Path(image_path).stem
            frame_preview_path = frame_preview_dir / f"{panel_stem}_brute.jpg"
            cv2.imwrite(str(frame_preview_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])

            hottest_idx = np.unravel_index(int(np.argmax(reduced)), reduced.shape)
            heat_y, heat_x = hottest_idx
            heat_x_norm = round(float(heat_x) / max(1, reduced.shape[1] - 1), 6)
            heat_y_norm = round(float(heat_y) / max(1, reduced.shape[0] - 1), 6)

            if anatomy_mode == "corps_entier":
                if effective_anatomy_backend == "mediapipe":
                    anatomy = detect_body_anatomy_mediapipe(frame, pose_detector)
                else:
                    anatomy = detect_body_anatomy(frame, body_detector) if body_detector is not None else {
                        "mode": "corps_entier",
                        "backend": "frame_fallback",
                        "roi_box": (0, 0, frame.shape[1], frame.shape[0]),
                        "roi_mask": np.ones(gray.shape, dtype=bool),
                        "subboxes": {},
                        "roi_center_x_norm": 0.5,
                        "roi_center_y_norm": 0.5,
                        "landmark_points": [],
                        "landmark_edges": [],
                    }
            else:
                if effective_anatomy_backend == "mediapipe":
                    anatomy = detect_face_anatomy_mediapipe(frame, face_mesh_detector)
                else:
                    anatomy = detect_face_anatomy(frame, gray, face_detector, eye_detector, smile_detector)
            anatomy["face_analysis_mode"] = effective_face_analysis_mode
            if anatomy_mode == "visage" and effective_face_analysis_mode == "manuel":
                tracking_candidates = anatomy.get("face_candidates", []) or []
                if manual_identity_backend is not None and tracking_candidates:
                    tracking_candidates = manual_identity_backend.annotate_candidates(
                        frame,
                        tracking_candidates,
                    )
                anatomy["face_candidates"] = tracking_candidates
                if not tracking_candidates and getattr(manual_identity_backend, "active", False) and face_detector is not None:
                    tracking_candidates = detect_face_identity_candidates(
                        frame,
                        gray,
                        face_detector,
                        manual_identity_backend,
                    )
            else:
                tracking_candidates = anatomy.get("face_candidates", []) or []

            if anatomy_mode == "visage" and effective_face_analysis_mode == "multivisage":
                tracked_faces, next_face_track_id = track_detected_faces(
                    anatomy.get("face_boxes", []) or [],
                    previous_face_tracks,
                    gray.shape,
                    next_face_track_id,
                )
                anatomy["tracked_faces"] = create_face_records([], gray.shape, tracks=tracked_faces)
                primary_track = find_track_for_box(anatomy.get("roi_box"), tracked_faces)
                anatomy["primary_face_track_id"] = int(primary_track.track_id) if primary_track is not None else 0
                anatomy["primary_face_order"] = int(primary_track.face_order) if primary_track is not None else 0
                previous_face_tracks = tracked_faces
            else:
                anatomy["tracked_faces"] = []
                anatomy["primary_face_track_id"] = 0
                anatomy["primary_face_order"] = 0
                previous_face_tracks = []

            if anatomy_mode == "visage" and effective_face_analysis_mode == "manuel":
                if manual_reference_box is None:
                    anatomy = {
                        **anatomy,
                        "mode": "visage",
                        "roi_box": None,
                        "roi_mask": np.zeros(gray.shape, dtype=bool),
                        "subboxes": {},
                        "face_area_ratio": 0.0,
                        "roi_center_x_norm": 0.0,
                        "roi_center_y_norm": 0.0,
                        "mouth_opening": 0.0,
                        "left_eye_opening": 0.0,
                        "right_eye_opening": 0.0,
                        "left_right_asymmetry": 0.0,
                        "landmark_points": [],
                        "landmark_edges": [],
                        "tracked_faces": [],
                        "primary_face_track_id": 0,
                        "primary_face_order": 0,
                        "face_analysis_mode": effective_face_analysis_mode,
                        "tracked_face_locked": "non",
                        "tracked_face_confidence": 0.0,
                        "tracked_face_identity_similarity": 0.0,
                        "tracked_face_identity_backend": str(manual_identity_backend_name or "local"),
                        "tracked_face_lost": "",
                        "tracked_face_status": "attente image de référence",
                        "tracked_face_loss_streak": 0,
                    }
                else:
                    if manual_anchor_ready and manual_reference_descriptor is None:
                        initial_candidate = choose_face_candidate_for_reference(
                            tracking_candidates,
                            manual_reference_box,
                        )
                        if initial_candidate is not None:
                            snapped_box = initial_candidate.get("roi_box") or manual_reference_box
                            manual_reference_box = snapped_box
                            manual_previous_box = snapped_box
                            snapped_descriptor = None
                            if manual_identity_backend is not None:
                                snapped_descriptor = manual_identity_backend.descriptor_from_candidate(frame, initial_candidate)
                            if snapped_descriptor is None:
                                snapped_descriptor = compute_face_descriptor(gray, snapped_box, candidate=initial_candidate)
                            if snapped_descriptor is not None:
                                manual_reference_descriptor = snapped_descriptor
                                manual_previous_descriptor = snapped_descriptor

                    selected_candidate, selected_descriptor, tracking_confidence, _tracking_components = choose_face_candidate_with_tracking(
                        tracking_candidates,
                        gray,
                        reference_box=manual_reference_box,
                        previous_box=manual_previous_box,
                        reference_descriptor=manual_reference_descriptor,
                        previous_descriptor=manual_previous_descriptor,
                        minimum_confidence=0.52,
                    )
                    if selected_candidate is not None:
                        selected_anatomy_candidate, anatomy_match_score = choose_face_candidate_for_metrics(
                            anatomy.get("face_candidates", []) or [],
                            selected_box=selected_candidate.get("roi_box"),
                            frame_shape=gray.shape,
                            selected_descriptor=selected_descriptor,
                            reference_descriptor=manual_reference_descriptor,
                        )
                        _tracking_components["anatomy_match_score"] = round(float(anatomy_match_score), 6)
                        metrics_candidate = selected_anatomy_candidate
                        if metrics_candidate is None and (anatomy.get("face_candidates") or []):
                            selected_candidate = None
                        else:
                            metrics_candidate = metrics_candidate or selected_candidate
                    if selected_candidate is not None:
                        lock_mode = "continuité" if float(_tracking_components.get("lock_mode", 0.0) or 0.0) > 0.5 else "identité"
                        anatomy = {
                            **metrics_candidate,
                            "face_count": anatomy.get("face_count", 0),
                            "face_boxes": anatomy.get("face_boxes", []),
                            "faces_detected": anatomy.get("faces_detected", []),
                            "face_candidates": anatomy.get("face_candidates", []),
                            "tracked_faces": [],
                            "primary_face_track_id": 0,
                            "primary_face_order": 0,
                            "face_analysis_mode": effective_face_analysis_mode,
                        }
                        manual_previous_box = selected_candidate.get("roi_box") or manual_previous_box
                        if selected_descriptor is not None:
                            manual_previous_descriptor = selected_descriptor
                            if manual_reference_descriptor is None:
                                manual_reference_descriptor = selected_descriptor
                        manual_loss_streak = 0
                        anatomy["tracked_face_locked"] = "oui"
                        anatomy["tracked_face_confidence"] = round(float(tracking_confidence), 6)
                        anatomy["tracked_face_identity_similarity"] = round(float(_tracking_components.get("ref_appearance", 0.0) or 0.0), 6)
                        anatomy["tracked_face_identity_backend"] = str(selected_candidate.get("identity_backend") or manual_identity_backend_name or "local")
                        anatomy["tracked_face_lost"] = "non"
                        anatomy["tracked_face_status"] = f"verrouillé ({lock_mode})"
                        anatomy["tracked_face_loss_streak"] = 0
                    else:
                        manual_loss_streak += 1
                        anatomy = {
                            **anatomy,
                            "mode": "visage",
                            "roi_box": None,
                            "roi_mask": np.zeros(gray.shape, dtype=bool),
                            "subboxes": {},
                            "face_area_ratio": 0.0,
                            "roi_center_x_norm": 0.0,
                            "roi_center_y_norm": 0.0,
                            "mouth_opening": 0.0,
                            "left_eye_opening": 0.0,
                            "right_eye_opening": 0.0,
                            "left_right_asymmetry": 0.0,
                            "landmark_points": [],
                            "landmark_edges": [],
                            "tracked_faces": [],
                            "primary_face_track_id": 0,
                            "primary_face_order": 0,
                            "face_analysis_mode": effective_face_analysis_mode,
                            "tracked_face_locked": "non",
                            "tracked_face_confidence": round(float(tracking_confidence), 6),
                            "tracked_face_identity_similarity": round(float(_tracking_components.get("ref_appearance", 0.0) or 0.0), 6),
                            "tracked_face_identity_backend": str(manual_identity_backend_name or "local"),
                            "tracked_face_lost": "oui",
                            "tracked_face_status": "perdu",
                            "tracked_face_loss_streak": manual_loss_streak,
                        }
            elif anatomy_mode == "visage":
                anatomy["tracked_face_locked"] = ""
                anatomy["tracked_face_confidence"] = 0.0
                anatomy["tracked_face_identity_similarity"] = 0.0
                anatomy["tracked_face_identity_backend"] = ""
                anatomy["tracked_face_lost"] = ""
                anatomy["tracked_face_status"] = ""
                anatomy["tracked_face_loss_streak"] = 0

            view_paths = save_flow_view_images(
                frame,
                flow,
                magnitude,
                stem=panel_stem,
                magnitude_dir=magnitude_dir,
                hsv_dir=hsv_dir,
                overlay_dir=overlay_dir,
                vectors_dir=vectors_dir,
                entropy_dir=entropy_dir,
                panel_dir=flow_panel_dir,
                entropy_mask=anatomy.get("roi_mask"),
            )

            face_count = int(anatomy.get("face_count", 0) or 0)
            face_area_ratio = float(anatomy.get("face_area_ratio", 0.0) or 0.0)
            anatomy_metrics = build_anatomy_metrics(
                anatomy,
                flow,
                magnitude,
                motion_threshold,
                previous_roi_energy=previous_roi_energy,
                previous_center=previous_roi_center,
            )
            annotated_panel = annotate_frame_with_anatomy(
                frame,
                flow,
                anatomy,
                anatomy_metrics,
                time_sec=time_sec,
            )
            annotated_preview_path = annotated_dir / f"{panel_stem}_anatomie.jpg"
            cv2.imwrite(str(annotated_preview_path), annotated_panel, [int(cv2.IMWRITE_JPEG_QUALITY), 86])

            row = {
                "frame_index": sampled_index,
                "time_sec": round(time_sec, 6),
                "delta_sec": round(max(0.0, time_sec - (previous_time or time_sec)), 6),
                "motion_mean": round(motion_mean, 6),
                "motion_std": round(motion_std, 6),
                "motion_peak_p95": round(motion_peak, 6),
                "motion_active_ratio": round(active_ratio, 6),
                "direction_dx": round(dx, 6),
                "direction_dy": round(dy, 6),
                "motion_vector_norm": round(motion_vector_norm, 6),
                "motion_angle_deg": round(motion_angle_deg, 6),
                "direction_label": direction_label,
                "heat_x_norm": heat_x_norm,
                "heat_y_norm": heat_y_norm,
                "face_count": face_count,
                "tracked_face_count": len(anatomy.get("tracked_faces", []) or []),
                "face_area_ratio": round(face_area_ratio, 6),
                "brightness_mean": round(color_metrics["brightness_mean"], 6),
                "contrast_std": round(color_metrics["contrast_std"], 6),
                "hue_mean": round(color_metrics["hue_mean"], 6),
                "saturation_mean": round(color_metrics["saturation_mean"], 6),
                "red_mean": round(color_metrics["red_mean"], 6),
                "green_mean": round(color_metrics["green_mean"], 6),
                "blue_mean": round(color_metrics["blue_mean"], 6),
                "image_path": str(image_path),
                "frame_preview_path": str(frame_preview_path),
                "annotated_preview_path": str(annotated_preview_path),
                "anatomy_mode": anatomy_mode,
                "anatomy_backend": str(anatomy_metrics.get("anatomy_backend", "")),
                **view_paths,
                **anatomy_metrics,
            }
            frame_rows.append(row)

            if anatomy_mode == "visage" and effective_face_analysis_mode == "multivisage":
                for face_record in anatomy.get("tracked_faces", []) or []:
                    face_box = (
                        int(face_record.get("face_box_x1", 0) or 0),
                        int(face_record.get("face_box_y1", 0) or 0),
                        int(face_record.get("face_box_x2", 0) or 0),
                        int(face_record.get("face_box_y2", 0) or 0),
                    )
                    face_mask = box_to_mask(magnitude.shape, face_box)
                    face_metrics = compute_mask_flow_metrics(flow, magnitude, face_mask, motion_threshold)
                    multiface_rows.append(
                        {
                            "frame_index": sampled_index,
                            "time_sec": round(time_sec, 6),
                            "image_path": str(image_path),
                            "frame_preview_path": str(frame_preview_path),
                            "face_id": int(face_record.get("face_id", 0) or 0),
                            "face_order": int(face_record.get("face_order", 0) or 0),
                            "face_box_x1": face_box[0],
                            "face_box_y1": face_box[1],
                            "face_box_x2": face_box[2],
                            "face_box_y2": face_box[3],
                            "face_center_x_norm": round(float(face_record.get("face_center_x_norm", 0.0) or 0.0), 6),
                            "face_center_y_norm": round(float(face_record.get("face_center_y_norm", 0.0) or 0.0), 6),
                            "face_area_ratio": round(float(face_record.get("face_area_ratio", 0.0) or 0.0), 6),
                            "track_hits": int(face_record.get("track_hits", 0) or 0),
                            "track_age": int(face_record.get("track_age", 0) or 0),
                            "is_primary_face": "oui" if int(face_record.get("face_id", 0) or 0) == int(anatomy.get("primary_face_track_id", 0) or 0) else "non",
                            "face_flow_mean": round(face_metrics["mean"], 6),
                            "face_flow_std": round(face_metrics["std"], 6),
                            "face_flow_max": round(face_metrics["max"], 6),
                            "face_active_ratio": round(face_metrics["active_ratio"], 6),
                            "face_motion_energy": round(face_metrics["energy"], 6),
                            "face_direction_coherence": round(face_metrics["direction_coherence"], 6),
                            "face_directional_entropy": round(face_metrics["directional_entropy"], 6),
                            "face_directional_entropy_norm": round(face_metrics["directional_entropy_norm"], 6),
                            "face_divergence_abs_mean": round(face_metrics["divergence_abs_mean"], 6),
                            "face_curl_abs_mean": round(face_metrics["curl_abs_mean"], 6),
                            "anatomy_backend": str(anatomy_metrics.get("anatomy_backend", "")),
                        }
                    )

            window_id = int(time_sec // max(0.25, window_sec))
            window_buckets[window_id].append(row)
            if window_id not in keyframe_paths:
                keyframe_paths[window_id] = str(image_path)

            previous_gray = gray
            previous_time = time_sec
            previous_roi_energy = float(anatomy_metrics.get("roi_motion_energy", 0.0) or 0.0)
            previous_roi_center = (
                float(anatomy_metrics.get("roi_center_x_norm", 0.0) or 0.0),
                float(anatomy_metrics.get("roi_center_y_norm", 0.0) or 0.0),
            )
    finally:
        if face_mesh_detector is not None:
            face_mesh_detector.close()
        if pose_detector is not None:
            pose_detector.close()

    window_rows: list[dict[str, Any]] = []
    write_progress_snapshot(
        destination,
        "mouvements",
        "aggregate_windows",
        82,
        "Agrégation des fenêtres temporelles."
    )
    for window_id in sorted(window_buckets):
        rows = window_buckets[window_id]
        start_sec = window_id * window_sec
        end_sec = start_sec + window_sec
        numeric_keys = [
            "motion_mean",
            "motion_std",
            "motion_peak_p95",
            "motion_active_ratio",
            "direction_dx",
            "direction_dy",
            "motion_vector_norm",
            "motion_angle_deg",
            "heat_x_norm",
            "heat_y_norm",
            "face_count",
            "face_area_ratio",
            "brightness_mean",
            "contrast_std",
            "hue_mean",
            "saturation_mean",
            "red_mean",
            "green_mean",
            "blue_mean",
            "roi_surface_px",
            "roi_surface_ratio",
            "roi_center_x_norm",
            "roi_center_y_norm",
            "roi_flow_mean",
            "roi_flow_std",
            "roi_flow_max",
            "roi_active_ratio",
            "roi_motion_energy",
            "roi_direction_coherence",
            "roi_directional_entropy",
            "roi_directional_entropy_norm",
            "roi_divergence_abs_mean",
            "roi_curl_abs_mean",
            "energy_time_derivative",
        ]
        if anatomy_mode == "visage":
            numeric_keys.extend([
                "mouth_opening",
                "left_eye_opening",
                "right_eye_opening",
                "left_right_asymmetry",
                "mouth_motion_energy",
                "eyes_motion_energy",
                "brows_motion_energy",
            ])
        else:
            numeric_keys.extend([
                "body_center_displacement",
                "head_motion_energy",
                "torso_motion_energy",
                "left_arm_motion_energy",
                "right_arm_motion_energy",
            ])
        numeric_values = {
            key: round(float(np.mean([float(row[key]) for row in rows])), 6)
            for key in numeric_keys
        }
        direction_counter = Counter(row["direction_label"] for row in rows if row["direction_label"])
        dominant_direction = direction_counter.most_common(1)[0][0] if direction_counter else ""
        window_rows.append(
            {
                "window_id": window_id,
                "start_sec": round(start_sec, 6),
                "end_sec": round(end_sec, 6),
                "frame_samples": len(rows),
                **numeric_values,
                "anatomy_mode": anatomy_mode,
                "anatomy_backend": rows[0].get("anatomy_backend", ""),
                "dominant_direction": dominant_direction,
                "keyframe_path": keyframe_paths.get(window_id, ""),
            }
        )

    apply_simple_activity_peaks(frame_rows)

    heatmap_path = destination / "motion_heatmap.png"
    save_heatmap_png(heatmap_grid, heatmap_path)
    chart_path = build_movement_altair_chart(window_rows, destination / "mouvements_timeline_altair.png")
    write_progress_snapshot(
        destination,
        "mouvements",
        "write_exports",
        94,
        "Écriture des exports mouvements."
    )
    summary = {
        "session_id": session_id,
        "source": source,
        "source_mode": "images",
        "anatomy_mode": anatomy_mode,
        "face_analysis_mode": effective_face_analysis_mode,
        "selected_face_box": list(selected_face_box) if selected_face_box else [],
        "selected_face_source_name": manual_selected_source_name,
        "selected_face_source_index": manual_selected_source_index if manual_selected_source_index is not None else -1,
        "manual_identity_backend": manual_identity_backend_name,
        "manual_identity_warning": manual_identity_warning,
        "anatomy_backend_requested": anatomy_backend,
        "anatomy_backend_effective": effective_anatomy_backend,
        "anatomy_backend_warning": backend_warning,
        "frame_samples": len(frame_rows),
        "window_count": len(window_rows),
        "multiface_rows": len(multiface_rows),
        "sample_fps": round(float(sample_fps), 6),
        "window_sec": round(float(window_sec), 6),
        "anatomy_backend": frame_rows[0].get("anatomy_backend", "") if frame_rows else "",
        "chart_png": chart_path,
        "progression_json": str(progress_path),
    }
    frames_csv_path, frames_csv_complete_path, frames_csv_essential_path = write_csv_variants(
        destination / "mouvements_frames.csv",
        frame_rows,
        MOUVEMENTS_FRAME_ESSENTIAL_COLUMNS,
    )
    multiface_csv_path, multiface_csv_complete_path, multiface_csv_essential_path = write_csv_variants(
        destination / "mouvements_multivisage.csv",
        multiface_rows,
        MOUVEMENTS_MULTIVISAGE_ESSENTIAL_COLUMNS,
    )
    windows_csv_path, windows_csv_complete_path, windows_csv_essential_path = write_csv_variants(
        destination / "mouvements_windows.csv",
        window_rows,
        MOUVEMENTS_WINDOWS_ESSENTIAL_COLUMNS,
    )
    write_jsonl(destination / "mouvements_windows.jsonl", window_rows)
    write_json(destination / "mouvements_summary.json", summary)
    progress_path = write_progress_snapshot(
        destination,
        "mouvements",
        "completed",
        100,
        "Analyse mouvements terminée.",
        {"frame_samples": len(frame_rows), "window_count": len(window_rows)}
    )
    return {
        "session_id": session_id,
        "source_path": str(Path(source).expanduser().resolve()),
        "frames_csv": frames_csv_path,
        "frames_csv_complet": frames_csv_complete_path,
        "frames_csv_essentiel": frames_csv_essential_path,
        "windows_csv": windows_csv_path,
        "windows_csv_complet": windows_csv_complete_path,
        "windows_csv_essentiel": windows_csv_essential_path,
        "multiface_csv": multiface_csv_path,
        "multiface_csv_complet": multiface_csv_complete_path,
        "multiface_csv_essentiel": multiface_csv_essential_path,
        "windows_jsonl": str(destination / "mouvements_windows.jsonl"),
        "heatmap_png": str(heatmap_path),
        "chart_png": str(chart_path),
        "summary_json": str(destination / "mouvements_summary.json"),
        "progression_json": str(progress_path),
        "window_count": len(window_rows),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse visuelle d'une séquence d'images : optical flow, couleurs et agrégation temporelle."
    )
    parser.add_argument("--source", required=True, help="Dossier local contenant une séquence d'images.")
    parser.add_argument("--output-dir", default="multimodale/exports/mouvements", help="Dossier d'export.")
    parser.add_argument("--sample-fps", type=float, default=1.0, help="Nombre d'images analysées par seconde.")
    parser.add_argument("--window-sec", type=float, default=1.0, help="Taille des fenêtres temporelles.")
    parser.add_argument("--motion-threshold", type=float, default=0.6, help="Seuil de mouvement actif.")
    parser.add_argument("--anatomy-mode", default="visage", choices=["visage", "corps_entier"], help="Mode anatomique appliqué à la ROI.")
    parser.add_argument("--anatomy-backend", default="opencv", choices=["opencv", "mediapipe"], help="Backend anatomique utilisé pour définir la ROI.")
    parser.add_argument("--face-analysis-mode", default="principal", choices=["principal", "multivisage", "manuel"], help="Analyse sur le visage principal, plusieurs visages, ou une sélection manuelle.")
    parser.add_argument("--selected-face-box", default="", help="Rectangle normalisé x1,y1,x2,y2 choisi à la souris sur le visage cible.")
    parser.add_argument("--selected-face-source-name", default="", help="Nom du fichier image servant d'ancre à la sélection manuelle du visage.")
    parser.add_argument("--selected-face-source-index", type=int, default=-1, help="Index 0-based de l'image servant d'ancre à la sélection manuelle du visage.")
    parser.add_argument(
        "--cookies",
        default="",
        help="Chemin vers un fichier cookies.txt ou .cookies pour les téléchargements YouTube.",
    )
    parser.add_argument("--start-sec", type=float, default=None, help="Début de l'intervalle à traiter.")
    parser.add_argument("--end-sec", type=float, default=None, help="Fin de l'intervalle à traiter.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    source_path = Path(str(args.source)).expanduser()
    if not (source_path.exists() and source_path.is_dir() and is_image_directory(source_path)):
        raise RuntimeError(
            "L'analyse des mouvements fonctionne uniquement à partir d'un dossier d'images. "
            "Extrais d'abord les images dans 'Extraction des sources' puis importe-les dans 'Analyse mouvements'."
        )

    result = analyse_images(
        source=args.source,
        output_dir=args.output_dir,
        sample_fps=args.sample_fps,
        window_sec=args.window_sec,
        motion_threshold=args.motion_threshold,
        anatomy_mode=args.anatomy_mode,
        anatomy_backend=args.anatomy_backend,
        face_analysis_mode=args.face_analysis_mode,
        selected_face_box=parse_selected_face_box(args.selected_face_box),
        selected_face_source_name=str(args.selected_face_source_name or "").strip() or None,
        selected_face_source_index=args.selected_face_source_index if int(args.selected_face_source_index) >= 0 else None,
    )

    print("Analyse mouvements terminée.")
    print(f"Fenêtres : {result['window_count']}")
    print(f"CSV fenêtres : {result['windows_csv']}")
    print(f"Heatmap : {result['heatmap_png']}")


if __name__ == "__main__":
    main()
