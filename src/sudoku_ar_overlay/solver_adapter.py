from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class SolverResult:
    status: str
    corners: np.ndarray
    givens: list[list[int]]
    solution: list[list[int]]
    solve_latency_ms: float


def mock_solver_result(frame_bgr: np.ndarray) -> SolverResult:
    """Temporary mock result for building the AR layer before wiring the real solver."""
    start = time.perf_counter()

    h, w = frame_bgr.shape[:2]

    margin_x = int(w * 0.18)
    margin_y = int(h * 0.10)
    side = min(w - 2 * margin_x, h - 2 * margin_y)

    x0 = (w - side) // 2
    y0 = (h - side) // 2
    x1 = x0 + side
    y1 = y0 + side

    corners = np.float32(
        [
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1],
        ]
    )

    givens = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9],
    ]

    solution = [
        [5, 3, 4, 6, 7, 8, 9, 1, 2],
        [6, 7, 2, 1, 9, 5, 3, 4, 8],
        [1, 9, 8, 3, 4, 2, 5, 6, 7],
        [8, 5, 9, 7, 6, 1, 4, 2, 3],
        [4, 2, 6, 8, 5, 3, 7, 9, 1],
        [7, 1, 3, 9, 2, 4, 8, 5, 6],
        [9, 6, 1, 5, 3, 7, 2, 8, 4],
        [2, 8, 7, 4, 1, 9, 6, 3, 5],
        [3, 4, 5, 2, 8, 6, 1, 7, 9],
    ]

    latency_ms = (time.perf_counter() - start) * 1000

    return SolverResult(
        status="mock_solved",
        corners=corners,
        givens=givens,
        solution=solution,
        solve_latency_ms=latency_ms,
    )


def solve_frame(frame_bgr: np.ndarray, use_mock: bool = True) -> SolverResult:
    """Temporary adapter.

    Later this function should call the frozen inference path from sudoku-image-solver.
    For now it returns a deterministic mock result so the AR layer can be built first.
    """
    if use_mock:
        return mock_solver_result(frame_bgr)

    raise NotImplementedError("Real solver integration is not wired yet. Use mock mode for now.")


def load_image_bgr(path: str) -> np.ndarray:
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return frame
