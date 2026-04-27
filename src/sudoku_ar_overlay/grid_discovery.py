from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from sudoku_ar_overlay.grid_validation import validate_sudoku_grid_candidate


@dataclass
class GridDiscoveryResult:
    ok: bool
    corners: np.ndarray | None
    score: float
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


def find_sudoku_grid_candidate(
    frame_bgr: np.ndarray,
    *,
    min_area_frac: float = 0.015,
    max_area_frac: float = 0.45,
    max_aspect_ratio: float = 1.8,
    min_grid_score: float = 0.030,
    min_each_direction_lines: int = 3,
    min_total_lines: int = 7,
) -> GridDiscoveryResult:
    """Find a likely Sudoku grid directly from line/contour structure.

    This is for discovery/reacquisition when segmentation can false-positive
    on a rug, table edge, paper boundary, etc.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    # Emphasize dark printed grid lines/digits.
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        10,
    )

    binary = cv2.dilate(
        binary,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1,
    )

    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    h, w = frame_bgr.shape[:2]
    frame_area = float(h * w)

    best = None

    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_frac = area / frame_area if frame_area > 0 else 0.0

        if area_frac < min_area_frac or area_frac > max_area_frac:
            continue

        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect).astype("float32")

        bw, bh = rect[1]
        if bw < 80 or bh < 80:
            continue

        aspect = max(bw, bh) / max(1.0, min(bw, bh))
        if aspect > max_aspect_ratio:
            continue

        corners = _order_points(box)

        grid = validate_sudoku_grid_candidate(
            frame_bgr,
            corners,
            min_peak=0.020,
            min_strong_lines=min_each_direction_lines,
        )

        total_lines = grid.strong_vertical_lines + grid.strong_horizontal_lines

        passes = (
            grid.score >= min_grid_score
            and grid.strong_vertical_lines >= min_each_direction_lines
            and grid.strong_horizontal_lines >= min_each_direction_lines
            and total_lines >= min_total_lines
        )

        if not passes:
            continue

        # Prefer stronger grid evidence; area is a tie-breaker.
        rank = (grid.score, total_lines, area_frac)

        if best is None or rank > best[0]:
            best = (
                rank,
                corners,
                (
                    f"grid-discovery ok: score={grid.score:.3f} "
                    f"v_peak={grid.vertical_peak:.3f} h_peak={grid.horizontal_peak:.3f} "
                    f"v_lines={grid.strong_vertical_lines} "
                    f"h_lines={grid.strong_horizontal_lines} "
                    f"area={area_frac:.3f}"
                ),
            )

    if best is None:
        return GridDiscoveryResult(
            ok=False,
            corners=None,
            score=0.0,
            reason="grid-discovery rejected: no Sudoku-like grid candidate",
        )

    rank, corners, reason = best

    return GridDiscoveryResult(
        ok=True,
        corners=corners,
        score=float(rank[0]),
        reason=reason,
    )
