from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


DEFAULT_SOLVER_REPO = str(Path("~/projects/sudoku-image-solver").expanduser())


@dataclass
class SudokuSolveResult:
    status: str
    message: str
    latency_ms: float
    confidence: float
    image_width: int
    image_height: int
    corners_px: list[list[float]] | None
    givens: list[list[int]] | None
    solution: list[list[int]] | None
    givens_count: int
    debug: dict[str, Any]


def ensure_solver_repo_on_path(repo_root: str) -> None:
    repo = Path(repo_root).expanduser()
    if not repo.exists():
        raise FileNotFoundError(f"sudoku-image-solver repo not found: {repo}")

    repo_str = str(repo)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


def to_py(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, dict):
        return {str(k): to_py(v) for k, v in x.items()}
    if isinstance(x, list):
        return [to_py(v) for v in x]
    if isinstance(x, tuple):
        return [to_py(v) for v in x]
    return x


def count_givens(grid) -> int:
    if grid is None:
        return 0
    return sum(1 for row in grid for value in row if int(value) != 0)


def find_empty(grid: np.ndarray):
    for r in range(9):
        for c in range(9):
            if int(grid[r, c]) == 0:
                return r, c
    return None


def is_valid(grid: np.ndarray, row: int, col: int, val: int) -> bool:
    if any(int(grid[row, c]) == val for c in range(9)):
        return False
    if any(int(grid[r, col]) == val for r in range(9)):
        return False

    br = (row // 3) * 3
    bc = (col // 3) * 3

    for r in range(br, br + 3):
        for c in range(bc, bc + 3):
            if int(grid[r, c]) == val:
                return False

    return True


def solve_sudoku(grid: np.ndarray) -> bool:
    empty = find_empty(grid)
    if empty is None:
        return True

    row, col = empty

    for val in range(1, 10):
        if is_valid(grid, row, col, val):
            grid[row, col] = val
            if solve_sudoku(grid):
                return True
            grid[row, col] = 0

    return False


def unpack_mask_result(mask_result):
    if not isinstance(mask_result, (tuple, list)):
        raise RuntimeError(f"Unexpected predict_mask_prob_letterbox return type: {type(mask_result)}")

    prob = None
    meta = None

    for item in mask_result:
        if isinstance(item, np.ndarray) and item.ndim == 2:
            prob = item
        if isinstance(item, dict):
            meta = item

    if prob is None:
        raise RuntimeError(
            "Could not find 2D segmentation probability array in "
            f"predict_mask_prob_letterbox return: {[type(x) for x in mask_result]}"
        )

    if meta is None:
        raise RuntimeError(
            "Could not find letterbox metadata dict in "
            f"predict_mask_prob_letterbox return: {[type(x) for x in mask_result]}"
        )

    return prob, meta


def unpack_corners_result(corners_result):
    if isinstance(corners_result, np.ndarray):
        arr = np.asarray(corners_result, dtype=np.float32)
        return arr.reshape(4, 2)

    if isinstance(corners_result, (tuple, list)):
        for item in corners_result:
            if isinstance(item, np.ndarray):
                arr = np.asarray(item, dtype=np.float32)
                try:
                    reshaped = arr.reshape(-1, 2)
                except Exception:
                    continue
                if reshaped.shape[0] == 4:
                    return reshaped.reshape(4, 2)

    raise RuntimeError(
        "Could not find 4x2 corners in corners_from_segmentation_prob return. "
        f"type={type(corners_result)} repr={repr(corners_result)[:500]}"
    )


def solve_frame_for_ar(
    frame_bgr: np.ndarray,
    *,
    repo_root: str = DEFAULT_SOLVER_REPO,
    debug_dir: str | Path = "assets/debug",
) -> SudokuSolveResult:
    started = time.perf_counter()
    debug_path = Path(debug_dir)
    debug_path.mkdir(parents=True, exist_ok=True)

    ensure_solver_repo_on_path(repo_root)

    from src.sudoku_solver.inference import (
        corners_from_segmentation_prob,
        get_device,
        load_runtime,
        predict_givens_from_bgr,
        predict_mask_prob_letterbox,
        unletterbox_points,
    )

    image_h, image_w = frame_bgr.shape[:2]

    cv2.imwrite(str(debug_path / "last_input_frame.jpg"), frame_bgr)

    try:
        runtime = load_runtime()
        device = get_device()

        givens = predict_givens_from_bgr(frame_bgr)

        mask_result = predict_mask_prob_letterbox(
            runtime["seg_model"],
            frame_bgr,
            runtime["seg_image_size"],
            device,
        )
        prob, meta = unpack_mask_result(mask_result)

        corners_result = corners_from_segmentation_prob(prob)
        corners_letterbox = unpack_corners_result(corners_result)
        corners_px = unletterbox_points(corners_letterbox, meta)
        corners_px = np.asarray(corners_px, dtype=np.float32).reshape(4, 2)

        grid = np.array(givens, dtype=int).copy()
        solution = grid.copy()
        ok = solve_sudoku(solution)

        status = "solved" if bool(ok) else "failed"
        message = "solved" if bool(ok) else "Predicted givens did not produce a valid Sudoku solution."

        result = SudokuSolveResult(
            status=status,
            message=message,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            confidence=1.0 if bool(ok) else 0.0,
            image_width=int(image_w),
            image_height=int(image_h),
            corners_px=to_py(corners_px),
            givens=to_py(grid),
            solution=to_py(solution) if bool(ok) else None,
            givens_count=count_givens(grid),
            debug={
                "device": device,
                "solver_repo": str(Path(repo_root).expanduser()),
                "input_path": str(debug_path / "last_input_frame.jpg"),
            },
        )

        if result.corners_px is not None:
            debug = frame_bgr.copy()
            pts = np.asarray(result.corners_px, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(debug, [pts], isClosed=True, color=(0, 255, 0), thickness=8)
            cv2.imwrite(str(debug_path / "last_corners.jpg"), debug)
            result.debug["corners_debug_path"] = str(debug_path / "last_corners.jpg")

        (debug_path / "last_solve_response.json").write_text(
            json.dumps(to_py(result.__dict__), indent=2)
        )

        return result

    except Exception as exc:
        result = SudokuSolveResult(
            status="failed",
            message=f"{type(exc).__name__}: {exc}",
            latency_ms=(time.perf_counter() - started) * 1000.0,
            confidence=0.0,
            image_width=int(image_w),
            image_height=int(image_h),
            corners_px=None,
            givens=None,
            solution=None,
            givens_count=0,
            debug={
                "solver_repo": str(Path(repo_root).expanduser()),
                "input_path": str(debug_path / "last_input_frame.jpg"),
                "reason": "solver_exception",
            },
        )

        (debug_path / "last_failed_solve_response.json").write_text(
            json.dumps(to_py(result.__dict__), indent=2)
        )

        return result
