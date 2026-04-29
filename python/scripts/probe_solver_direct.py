from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.sudoku_solver.inference import (
    corners_from_segmentation_prob,
    get_device,
    load_runtime,
    predict_givens_from_bgr,
    predict_mask_prob_letterbox,
    unletterbox_points,
)


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


def count_givens(grid):
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


def get_board_corners_px(frame_bgr: np.ndarray, runtime: dict, device: str) -> np.ndarray:
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
    return np.asarray(corners_px, dtype=np.float32).reshape(4, 2)


image_path = Path("assets/demo/test_image.jpg")
frame = cv2.imread(str(image_path))

if frame is None:
    raise RuntimeError(f"Could not read {image_path}")

runtime = load_runtime()
device = get_device()

print("image:", image_path)
print("shape:", frame.shape)
print("device:", device)
print("runtime keys:", sorted(runtime.keys()))

givens = predict_givens_from_bgr(frame)
corners_px = get_board_corners_px(frame, runtime, device)

grid = np.array(givens, dtype=int).copy()
solution = grid.copy()
ok = solve_sudoku(solution)

result = {
    "status": "solved" if bool(ok) else "failed",
    "image_width": int(frame.shape[1]),
    "image_height": int(frame.shape[0]),
    "corners_px": to_py(corners_px),
    "givens": to_py(grid),
    "solution": to_py(solution) if ok else None,
    "givens_count": count_givens(grid),
}

Path("assets/debug").mkdir(parents=True, exist_ok=True)
Path("assets/debug/probe_solver_direct.json").write_text(json.dumps(result, indent=2))

debug = frame.copy()
pts = np.asarray(corners_px, dtype=np.int32).reshape(-1, 1, 2)
cv2.polylines(debug, [pts], isClosed=True, color=(0, 255, 0), thickness=8)
cv2.imwrite("assets/debug/probe_solver_direct_corners.jpg", debug)

print(json.dumps(result, indent=2))
print("wrote assets/debug/probe_solver_direct.json")
print("wrote assets/debug/probe_solver_direct_corners.jpg")
