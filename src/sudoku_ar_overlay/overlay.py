from __future__ import annotations

import cv2
import numpy as np

from sudoku_ar_overlay.config import OverlayConfig


def canonical_board_corners(board_size_px: int = 900) -> np.ndarray:
    return np.float32(
        [
            [0, 0],
            [board_size_px, 0],
            [board_size_px, board_size_px],
            [0, board_size_px],
        ]
    )


def order_corners_clockwise(corners: np.ndarray) -> np.ndarray:
    """Return corners ordered as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(corners, dtype="float32").reshape(4, 2)

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)

    top_left = pts[np.argmin(s)]
    bottom_right = pts[np.argmax(s)]
    top_right = pts[np.argmin(diff)]
    bottom_left = pts[np.argmax(diff)]

    return np.float32([top_left, top_right, bottom_right, bottom_left])


def draw_board_outline(frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
    out = frame.copy()
    pts = order_corners_clockwise(corners).astype(int).reshape((-1, 1, 2))
    cv2.polylines(out, [pts], isClosed=True, color=(0, 255, 0), thickness=3)
    return out


def make_solution_canvas(
    givens: list[list[int]],
    solution: list[list[int]],
    cfg: OverlayConfig,
) -> np.ndarray:
    """Render solved digits for empty cells onto a transparent board-space canvas."""
    size = cfg.board_size_px
    cell = cfg.cell_size_px

    canvas = np.zeros((size, size, 4), dtype=np.uint8)

    for r in range(9):
        for c in range(9):
            if givens[r][c] != 0:
                continue

            digit = str(solution[r][c])
            x_center = int((c + 0.5) * cell)
            y_center = int((r + 0.5) * cell)

            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size, _ = cv2.getTextSize(
                digit,
                font,
                cfg.font_scale,
                cfg.font_thickness,
            )
            text_w, text_h = text_size

            x = x_center - text_w // 2
            y = y_center + text_h // 2

            # Blue digits with full alpha.
            cv2.putText(
                canvas,
                digit,
                (x, y),
                font,
                cfg.font_scale,
                (255, 0, 0, 255),
                cfg.font_thickness,
                cv2.LINE_AA,
            )

    return canvas


def alpha_blend_bgra_over_bgr(base_bgr: np.ndarray, overlay_bgra: np.ndarray) -> np.ndarray:
    """Alpha-blend BGRA overlay over BGR base."""
    if overlay_bgra.shape[:2] != base_bgr.shape[:2]:
        raise ValueError("Overlay and base frame must have same height/width.")

    overlay_bgr = overlay_bgra[:, :, :3].astype(np.float32)
    alpha = overlay_bgra[:, :, 3:4].astype(np.float32) / 255.0

    base = base_bgr.astype(np.float32)
    blended = alpha * overlay_bgr + (1.0 - alpha) * base
    return np.clip(blended, 0, 255).astype(np.uint8)


def render_solution_overlay(
    frame: np.ndarray,
    corners: np.ndarray,
    givens: list[list[int]],
    solution: list[list[int]],
    cfg: OverlayConfig | None = None,
) -> np.ndarray:
    """Render solved digits into the board plane and warp them into the camera frame."""
    cfg = cfg or OverlayConfig()

    ordered = order_corners_clockwise(corners)
    src = canonical_board_corners(cfg.board_size_px)
    dst = ordered

    h_matrix, _ = cv2.findHomography(src, dst)
    if h_matrix is None:
        return draw_board_outline(frame, ordered)

    canvas = make_solution_canvas(givens, solution, cfg)

    warped = cv2.warpPerspective(
        canvas,
        h_matrix,
        (frame.shape[1], frame.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    out = alpha_blend_bgra_over_bgr(frame, warped)
    out = draw_board_outline(out, ordered)
    return out
