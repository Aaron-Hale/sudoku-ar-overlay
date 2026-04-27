from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from sudoku_ar_overlay.grid_validation import warp_candidate


@dataclass
class GridRefinementResult:
    ok: bool
    corners: np.ndarray | None
    mean_error_px: float
    reason: str


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype="float32").reshape(4, 2)

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)

    ordered = np.zeros((4, 2), dtype="float32")
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _find_grid_peaks(profile: np.ndarray, expected: np.ndarray, search_px: int, min_contrast: float):
    peaks = []

    for pos in expected:
        lo = max(0, int(pos) - search_px)
        hi = min(len(profile), int(pos) + search_px + 1)

        if hi <= lo:
            peaks.append(None)
            continue

        window = profile[lo:hi]
        baseline = float(np.median(window))
        idx = int(np.argmax(window))
        strength = float(window[idx])

        if strength - baseline < min_contrast:
            peaks.append(None)
        else:
            peaks.append(float(lo + idx))

    return peaks


def refine_sudoku_grid_corners(
    frame_bgr: np.ndarray,
    rough_corners: np.ndarray,
    *,
    size: int = 900,
    search_frac: float = 0.045,
    min_contrast: float = 0.018,
    min_found_lines: int = 7,
    max_mean_error_px: float = 18.0,
) -> GridRefinementResult:
    """Refine rough candidate corners to the actual outer Sudoku grid.

    The input corners only need to roughly cover the board. The output corners
    are adjusted to align with detected grid-line peaks in canonical space.
    """
    rough = _order_points(rough_corners)

    try:
        warp = warp_candidate(frame_bgr, rough, size=size)
    except Exception as exc:
        return GridRefinementResult(False, None, 999.0, f"warp failed: {type(exc).__name__}: {exc}")

    gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    darkness = (255.0 - gray.astype("float32")) / 255.0

    margin = int(size * 0.04)
    inner = slice(margin, size - margin)

    vertical_profile = darkness[inner, :].mean(axis=0)
    horizontal_profile = darkness[:, inner].mean(axis=1)

    expected = np.linspace(0, size - 1, 10)
    search_px = max(8, int(size * search_frac))

    x_peaks = _find_grid_peaks(vertical_profile, expected, search_px, min_contrast)
    y_peaks = _find_grid_peaks(horizontal_profile, expected, search_px, min_contrast)

    x_found = [p for p in x_peaks if p is not None]
    y_found = [p for p in y_peaks if p is not None]

    if len(x_found) < min_found_lines or len(y_found) < min_found_lines:
        return GridRefinementResult(
            False,
            None,
            999.0,
            f"not enough grid lines: x={len(x_found)} y={len(y_found)}",
        )

    x_pairs = [(expected[i], x_peaks[i]) for i in range(10) if x_peaks[i] is not None]
    y_pairs = [(expected[i], y_peaks[i]) for i in range(10) if y_peaks[i] is not None]

    x_expected = np.array([p[0] for p in x_pairs], dtype="float32")
    x_actual = np.array([p[1] for p in x_pairs], dtype="float32")
    y_expected = np.array([p[0] for p in y_pairs], dtype="float32")
    y_actual = np.array([p[1] for p in y_pairs], dtype="float32")

    ax, bx = np.polyfit(x_expected, x_actual, 1)
    ay, by = np.polyfit(y_expected, y_actual, 1)

    x0 = float(ax * 0 + bx)
    x1 = float(ax * (size - 1) + bx)
    y0 = float(ay * 0 + by)
    y1 = float(ay * (size - 1) + by)

    refined_canonical = np.array(
        [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
        dtype="float32",
    )

    dst = np.array(
        [[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]],
        dtype="float32",
    )

    H = cv2.getPerspectiveTransform(rough, dst)
    H_inv = np.linalg.inv(H)

    refined_frame = cv2.perspectiveTransform(
        refined_canonical.reshape(1, 4, 2),
        H_inv,
    ).reshape(4, 2)

    x_err = np.abs((ax * x_expected + bx) - x_actual)
    y_err = np.abs((ay * y_expected + by) - y_actual)
    mean_error = float(np.concatenate([x_err, y_err]).mean())

    ok = mean_error <= max_mean_error_px

    return GridRefinementResult(
        ok=ok,
        corners=refined_frame.astype("float32") if ok else None,
        mean_error_px=mean_error,
        reason=(
            f"{'refined' if ok else 'refine rejected'}: "
            f"mean_err={mean_error:.1f}px x_lines={len(x_found)} y_lines={len(y_found)} "
            f"x0={x0:.1f} x1={x1:.1f} y0={y0:.1f} y1={y1:.1f}"
        ),
    )
