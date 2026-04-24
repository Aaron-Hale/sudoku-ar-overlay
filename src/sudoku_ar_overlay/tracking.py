from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from sudoku_ar_overlay.overlay import order_corners_clockwise


@dataclass
class TrackingResult:
    detected: bool
    corners: np.ndarray | None
    quality: float
    reason: str = ""


def polygon_area(corners: np.ndarray) -> float:
    pts = order_corners_clockwise(corners).astype("float32")
    return float(cv2.contourArea(pts.reshape(-1, 1, 2)))


def aspect_ratio_from_corners(corners: np.ndarray) -> float:
    pts = order_corners_clockwise(corners).astype("float32")

    tl, tr, br, bl = pts

    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)

    width = max((width_top + width_bottom) / 2.0, 1.0)
    height = max((height_left + height_right) / 2.0, 1.0)

    return float(width / height)


def corners_inside_frame(corners: np.ndarray, frame_shape: tuple[int, int, int], margin: int = 30) -> bool:
    h, w = frame_shape[:2]
    pts = np.asarray(corners, dtype="float32").reshape(4, 2)

    return bool(
        np.all(pts[:, 0] >= -margin)
        and np.all(pts[:, 0] <= w + margin)
        and np.all(pts[:, 1] >= -margin)
        and np.all(pts[:, 1] <= h + margin)
    )


def score_corners(
    corners: np.ndarray,
    frame_shape: tuple[int, int, int],
    previous_corners: np.ndarray | None = None,
) -> TrackingResult:
    """Lightweight sanity scoring for detected board corners.

    This is intentionally heuristic. The goal is to reject obviously bad detections
    and provide a useful debug score, not to create a formal AR benchmark.
    """
    if corners is None:
        return TrackingResult(False, None, 0.0, "no corners")

    ordered = order_corners_clockwise(corners).astype("float32")
    frame_h, frame_w = frame_shape[:2]
    frame_area = float(frame_h * frame_w)

    area = polygon_area(ordered)
    if area <= 0:
        return TrackingResult(False, None, 0.0, "invalid area")

    area_ratio = area / max(frame_area, 1.0)

    # Reject tiny detections and absurdly huge detections.
    if area_ratio < 0.02:
        return TrackingResult(False, None, 0.0, f"area too small: {area_ratio:.3f}")

    if area_ratio > 0.95:
        return TrackingResult(False, None, 0.0, f"area too large: {area_ratio:.3f}")

    ar = aspect_ratio_from_corners(ordered)

    # Perspective can distort the apparent aspect ratio, so keep this loose.
    if ar < 0.45 or ar > 2.25:
        return TrackingResult(False, None, 0.0, f"bad aspect ratio: {ar:.2f}")

    if not corners_inside_frame(ordered, frame_shape):
        return TrackingResult(False, None, 0.0, "corners outside frame")

    # Base quality from area and aspect plausibility.
    quality = 0.5

    # Prefer a board that occupies a healthy part of the frame.
    if 0.08 <= area_ratio <= 0.65:
        quality += 0.25
    else:
        quality += 0.10

    # Prefer roughly square.
    aspect_penalty = min(abs(np.log(ar)), 1.0)
    quality += 0.20 * (1.0 - aspect_penalty)

    # Prefer temporal consistency when previous corners exist.
    if previous_corners is not None:
        previous = order_corners_clockwise(previous_corners).astype("float32")
        mean_motion = float(np.mean(np.linalg.norm(ordered - previous, axis=1)))
        diag = float(np.hypot(frame_w, frame_h))
        motion_ratio = mean_motion / max(diag, 1.0)

        if motion_ratio < 0.05:
            quality += 0.05
        elif motion_ratio > 0.35:
            quality -= 0.20

    quality = float(np.clip(quality, 0.0, 1.0))

    if quality < 0.25:
        return TrackingResult(False, ordered, quality, "low quality")

    return TrackingResult(True, ordered, quality, "ok")
