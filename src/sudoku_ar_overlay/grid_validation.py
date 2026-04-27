from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class GridValidationResult:
    ok: bool
    score: float
    vertical_peak: float
    horizontal_peak: float
    strong_vertical_lines: int
    strong_horizontal_lines: int
    reason: str


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype="float32").reshape(4, 2)

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)

    ordered = np.zeros((4, 2), dtype="float32")
    ordered[0] = pts[np.argmin(s)]      # top-left
    ordered[2] = pts[np.argmax(s)]      # bottom-right
    ordered[1] = pts[np.argmin(diff)]   # top-right
    ordered[3] = pts[np.argmax(diff)]   # bottom-left

    return ordered


def warp_candidate(frame_bgr: np.ndarray, corners: np.ndarray, size: int = 450) -> np.ndarray:
    src = _order_points(corners)
    dst = np.array(
        [[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]],
        dtype="float32",
    )
    H = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(frame_bgr, H, (size, size))


def validate_sudoku_grid_candidate(
    frame_bgr: np.ndarray,
    corners: np.ndarray,
    *,
    min_peak: float = 0.025,
    min_strong_lines: int = 7,
    size: int = 450,
) -> GridValidationResult:
    """Reject false board candidates that do not look like Sudoku grids.

    This is intentionally simple and conservative. A real Sudoku warp should
    show repeated dark line peaks at roughly 10 evenly spaced grid positions.
    A rug/carpet rectangle may have texture, but it should not produce strong,
    evenly spaced grid-line peaks.
    """
    try:
        warp = warp_candidate(frame_bgr, corners, size=size)
    except Exception as exc:
        return GridValidationResult(
            ok=False,
            score=0.0,
            vertical_peak=0.0,
            horizontal_peak=0.0,
            strong_vertical_lines=0,
            strong_horizontal_lines=0,
            reason=f"warp failed: {type(exc).__name__}: {exc}",
        )

    gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Darkness signal: grid lines and printed digits should be high.
    darkness = (255.0 - gray.astype("float32")) / 255.0

    n = darkness.shape[0]
    band = max(2, int(n * 0.008))
    inner_slice = slice(int(n * 0.03), int(n * 0.97))

    positions = np.linspace(0, n - 1, 10).astype(int)
    mids = ((positions[:-1] + positions[1:]) / 2).astype(int)

    vertical_line_strengths = []
    horizontal_line_strengths = []

    for x in positions:
        x0 = max(0, x - band)
        x1 = min(n, x + band + 1)
        vertical_line_strengths.append(float(darkness[inner_slice, x0:x1].mean()))

    for y in positions:
        y0 = max(0, y - band)
        y1 = min(n, y + band + 1)
        horizontal_line_strengths.append(float(darkness[y0:y1, inner_slice].mean()))

    vertical_mid_strengths = []
    horizontal_mid_strengths = []

    for x in mids:
        x0 = max(0, x - band)
        x1 = min(n, x + band + 1)
        vertical_mid_strengths.append(float(darkness[inner_slice, x0:x1].mean()))

    for y in mids:
        y0 = max(0, y - band)
        y1 = min(n, y + band + 1)
        horizontal_mid_strengths.append(float(darkness[y0:y1, inner_slice].mean()))

    v_bg = float(np.mean(vertical_mid_strengths))
    h_bg = float(np.mean(horizontal_mid_strengths))

    vertical_peak = float(np.mean(vertical_line_strengths) - v_bg)
    horizontal_peak = float(np.mean(horizontal_line_strengths) - h_bg)

    strong_vertical = sum(s > v_bg + min_peak for s in vertical_line_strengths)
    strong_horizontal = sum(s > h_bg + min_peak for s in horizontal_line_strengths)

    score = 0.5 * vertical_peak + 0.5 * horizontal_peak

    ok = (
        vertical_peak >= min_peak
        and horizontal_peak >= min_peak
        and strong_vertical >= min_strong_lines
        and strong_horizontal >= min_strong_lines
    )

    if not ok:
        reason = (
            f"grid rejected: score={score:.3f} "
            f"v_peak={vertical_peak:.3f} h_peak={horizontal_peak:.3f} "
            f"v_lines={strong_vertical} h_lines={strong_horizontal}"
        )
    else:
        reason = (
            f"grid ok: score={score:.3f} "
            f"v_peak={vertical_peak:.3f} h_peak={horizontal_peak:.3f} "
            f"v_lines={strong_vertical} h_lines={strong_horizontal}"
        )

    return GridValidationResult(
        ok=ok,
        score=score,
        vertical_peak=vertical_peak,
        horizontal_peak=horizontal_peak,
        strong_vertical_lines=strong_vertical,
        strong_horizontal_lines=strong_horizontal,
        reason=reason,
    )
