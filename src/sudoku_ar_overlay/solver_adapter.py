from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


_RUNTIME_CACHE: dict[str, dict] = {}


@dataclass
class SolverResult:
    status: str
    corners: np.ndarray
    givens: list[list[int]]
    solution: list[list[int]]
    solve_latency_ms: float
    latency_breakdown_ms: dict[str, float] = field(default_factory=dict)


# --------------------------
# Simple Sudoku solver
# --------------------------
def find_empty(grid: np.ndarray):
    for r in range(9):
        for c in range(9):
            if grid[r, c] == 0:
                return r, c
    return None


def is_valid(grid: np.ndarray, row: int, col: int, val: int) -> bool:
    if val in grid[row, :]:
        return False

    if val in grid[:, col]:
        return False

    br = (row // 3) * 3
    bc = (col // 3) * 3

    if val in grid[br : br + 3, bc : bc + 3]:
        return False

    return True


def solve_sudoku(grid: np.ndarray) -> bool:
    empty = find_empty(grid)

    if empty is None:
        return True

    r, c = empty

    for val in range(1, 10):
        if is_valid(grid, r, c, val):
            grid[r, c] = val

            if solve_sudoku(grid):
                return True

            grid[r, c] = 0

    return False


# --------------------------
# Mock solver
# --------------------------
def mock_solver_result(frame_bgr: np.ndarray) -> SolverResult:
    """Temporary mock result for building the AR layer before wiring live tracking."""
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
        latency_breakdown_ms={"mock": latency_ms},
    )


# --------------------------
# Real solver bridge
# --------------------------
def load_solver_runtime(repo_root: str | Path) -> dict:
    repo_root = Path(repo_root).expanduser().resolve()
    cache_key = str(repo_root)

    if cache_key in _RUNTIME_CACHE:
        return _RUNTIME_CACHE[cache_key]

    if not repo_root.exists():
        raise FileNotFoundError(f"Could not find sudoku-image-solver repo: {repo_root}")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.sudoku_solver.inference import load_runtime

    runtime = load_runtime()
    _RUNTIME_CACHE[cache_key] = runtime
    return runtime


def real_solver_result(frame_bgr: np.ndarray, repo_root: str | Path) -> SolverResult:
    if frame_bgr is None:
        raise ValueError("frame_bgr cannot be None")

    repo_root = Path(repo_root).expanduser().resolve()

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.sudoku_solver.inference import (
        DEVICE,
        apply_digit_calibration,
        apply_occ_calibration,
        corners_from_segmentation_prob,
        extract_equal_cells,
        greedy_grid_from_calibrated,
        infer_board_outputs_from_crops,
        predict_mask_prob_letterbox,
        unletterbox_points,
        warp_from_corners,
    )

    runtime = load_solver_runtime(repo_root)

    frozen = runtime["frozen"]
    warp_size = int(frozen["warp_size"])
    trim_frac = float(frozen["trim_frac"])
    occ_threshold = float(frozen["occ_threshold"])

    t_pipeline0 = time.perf_counter()

    # Segmentation -> board corners
    t0 = time.perf_counter()
    prob, lb_meta, _ = predict_mask_prob_letterbox(
        runtime["seg_model"],
        frame_bgr,
        runtime["seg_image_size"],
        DEVICE,
    )
    pred_pts_lb, _, _ = corners_from_segmentation_prob(prob, post_thr=0.5)
    pred_pts_orig = unletterbox_points(pred_pts_lb, lb_meta).astype(np.float32)
    segmentation_ms = (time.perf_counter() - t0) * 1000.0

    # Warp -> crops
    t0 = time.perf_counter()
    warp_bgr = warp_from_corners(frame_bgr, pred_pts_orig, warp_size=warp_size)
    crops, _ = extract_equal_cells(warp_bgr, trim_frac=trim_frac)
    warp_crop_ms = (time.perf_counter() - t0) * 1000.0

    # OCR inference
    t0 = time.perf_counter()
    outputs = infer_board_outputs_from_crops(crops, runtime)

    occ_probs = apply_occ_calibration(
        np.asarray(outputs["occ_logits"], dtype=np.float32),
        runtime["occ_cal"],
    )
    digit_probs = apply_digit_calibration(
        np.asarray(outputs["digit_logits"], dtype=np.float32),
        runtime["digit_cal"],
    )

    pred_grid = greedy_grid_from_calibrated(
        occ_probs,
        digit_probs,
        occ_threshold=occ_threshold,
    )
    ocr_ms = (time.perf_counter() - t0) * 1000.0

    # Solve puzzle
    t0 = time.perf_counter()
    givens_grid = pred_grid.copy()
    solved_grid = pred_grid.copy()

    if not solve_sudoku(solved_grid):
        raise RuntimeError(
            "Solver could not find a valid solution from predicted givens. "
            "This usually means OCR introduced a wrong given."
        )

    solve_ms = (time.perf_counter() - t0) * 1000.0
    pipeline_ms = (time.perf_counter() - t_pipeline0) * 1000.0

    return SolverResult(
        status="real_solved",
        corners=pred_pts_orig.astype(np.float32),
        givens=givens_grid.astype(int).tolist(),
        solution=solved_grid.astype(int).tolist(),
        solve_latency_ms=pipeline_ms,
        latency_breakdown_ms={
            "segmentation_ms": segmentation_ms,
            "warp_crop_ms": warp_crop_ms,
            "ocr_ms": ocr_ms,
            "sudoku_solve_ms": solve_ms,
            "pipeline_ms": pipeline_ms,
        },
    )




def detect_board_corners_only(
    frame_bgr: np.ndarray,
    repo_root: str | Path = "~/projects/sudoku-image-solver",
) -> tuple[np.ndarray, dict[str, float]]:
    """Run segmentation only and return detected board corners.

    This is the lightweight tracking path. It avoids OCR and Sudoku solving so the
    live app can update the board plane more often than it solves.
    """
    if frame_bgr is None:
        raise ValueError("frame_bgr cannot be None")

    repo_root = Path(repo_root).expanduser().resolve()

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.sudoku_solver.inference import (
        DEVICE,
        corners_from_segmentation_prob,
        predict_mask_prob_letterbox,
        unletterbox_points,
    )

    runtime = load_solver_runtime(repo_root)

    t0 = time.perf_counter()
    prob, lb_meta, _ = predict_mask_prob_letterbox(
        runtime["seg_model"],
        frame_bgr,
        runtime["seg_image_size"],
        DEVICE,
    )
    pred_pts_lb, _, _ = corners_from_segmentation_prob(prob, post_thr=0.5)
    pred_pts_orig = unletterbox_points(pred_pts_lb, lb_meta).astype(np.float32)
    segmentation_ms = (time.perf_counter() - t0) * 1000.0

    return pred_pts_orig.astype(np.float32), {"segmentation_ms": segmentation_ms}


def solve_frame(
    frame_bgr: np.ndarray,
    solver: str = "mock",
    repo_root: str | Path = "~/projects/sudoku-image-solver",
) -> SolverResult:
    if solver == "mock":
        return mock_solver_result(frame_bgr)

    if solver == "real":
        return real_solver_result(frame_bgr, repo_root=repo_root)

    raise ValueError(f"Unsupported solver mode: {solver}")


def load_image_bgr(path: str) -> np.ndarray:
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return frame
