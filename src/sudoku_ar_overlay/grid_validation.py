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


@dataclass
class GridFitResult:
    ok: bool
    mean_error_px: float
    max_error_px: float
    found_vertical_lines: int
    found_horizontal_lines: int
    reason: str


def evaluate_sudoku_grid_fit(
    frame_bgr: np.ndarray,
    corners: np.ndarray,
    *,
    size: int = 450,
    search_frac: float = 0.035,
    min_line_contrast: float = 0.025,
    min_found_lines: int = 7,
    max_mean_error_px: float = 14.0,
) -> GridFitResult:
    """Check whether candidate corners actually align to a printed Sudoku grid.

    This catches cases where discovery finds a rough board rectangle but the
    overlay would be visibly skewed relative to the real grid lines.
    """
    try:
        warp = warp_candidate(frame_bgr, corners, size=size)
    except Exception as exc:
        return GridFitResult(
            ok=False,
            mean_error_px=999.0,
            max_error_px=999.0,
            found_vertical_lines=0,
            found_horizontal_lines=0,
            reason=f"fit warp failed: {type(exc).__name__}: {exc}",
        )

    gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    darkness = (255.0 - gray.astype("float32")) / 255.0

    n = darkness.shape[0]
    search = max(4, int(n * search_frac))
    expected = np.linspace(0, n - 1, 10).astype(int)

    vertical_errors = []
    horizontal_errors = []

    inner = slice(int(n * 0.05), int(n * 0.95))

    for x in expected:
        lo = max(0, x - search)
        hi = min(n, x + search + 1)
        profile = darkness[inner, lo:hi].mean(axis=0)

        if profile.size == 0:
            continue

        baseline = float(np.median(profile))
        best_offset = int(np.argmax(profile))
        best_strength = float(profile[best_offset])

        if best_strength - baseline >= min_line_contrast:
            found_x = lo + best_offset
            vertical_errors.append(abs(float(found_x - x)))

    for y in expected:
        lo = max(0, y - search)
        hi = min(n, y + search + 1)
        profile = darkness[lo:hi, inner].mean(axis=1)

        if profile.size == 0:
            continue

        baseline = float(np.median(profile))
        best_offset = int(np.argmax(profile))
        best_strength = float(profile[best_offset])

        if best_strength - baseline >= min_line_contrast:
            found_y = lo + best_offset
            horizontal_errors.append(abs(float(found_y - y)))

    all_errors = vertical_errors + horizontal_errors

    if not all_errors:
        return GridFitResult(
            ok=False,
            mean_error_px=999.0,
            max_error_px=999.0,
            found_vertical_lines=0,
            found_horizontal_lines=0,
            reason="fit rejected: no expected grid lines found",
        )

    mean_error = float(np.mean(all_errors))
    max_error = float(np.max(all_errors))
    found_v = len(vertical_errors)
    found_h = len(horizontal_errors)

    ok = (
        found_v >= min_found_lines
        and found_h >= min_found_lines
        and mean_error <= max_mean_error_px
    )

    reason = (
        f"fit {'ok' if ok else 'rejected'}: "
        f"mean_err={mean_error:.1f}px max_err={max_error:.1f}px "
        f"v={found_v} h={found_h}"
    )

    return GridFitResult(
        ok=ok,
        mean_error_px=mean_error,
        max_error_px=max_error,
        found_vertical_lines=found_v,
        found_horizontal_lines=found_h,
        reason=reason,
    )
