from pathlib import Path
import sys
import time
import argparse

import cv2
import numpy as np


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=str(Path("~/projects/sudoku-image-solver").expanduser()),
        help="Path to local sudoku-image-solver repo.",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to input Sudoku image.",
    )
    parser.add_argument(
        "--out",
        default="assets/demo/static_real_overlay.jpg",
        help="Output image path.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser()
    image_path = Path(args.image).expanduser()
    out_path = Path(args.out).expanduser()

    if not repo_root.exists():
        raise FileNotFoundError(f"Could not find solver repo: {repo_root}")

    if not image_path.exists():
        raise FileNotFoundError(f"Could not find image: {image_path}")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.sudoku_solver.inference import (
        DEVICE,
        load_runtime,
        order_points,
        predict_mask_prob_letterbox,
        corners_from_segmentation_prob,
        unletterbox_points,
        warp_from_corners,
        extract_equal_cells,
        infer_board_outputs_from_crops,
        apply_occ_calibration,
        apply_digit_calibration,
        greedy_grid_from_calibrated,
    )

    raw_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if raw_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    # --------------------------
    # Load runtime
    # --------------------------
    t_runtime0 = time.perf_counter()
    runtime = load_runtime()
    runtime_load_ms = (time.perf_counter() - t_runtime0) * 1000.0

    frozen = runtime["frozen"]
    warp_size = int(frozen["warp_size"])
    trim_frac = float(frozen["trim_frac"])
    occ_threshold = float(frozen["occ_threshold"])

    # --------------------------
    # Per-image pipeline
    # --------------------------
    t_pipeline0 = time.perf_counter()

    # Segmentation -> board corners
    t0 = time.perf_counter()
    prob, lb_meta, _ = predict_mask_prob_letterbox(
        runtime["seg_model"],
        raw_bgr,
        runtime["seg_image_size"],
        DEVICE,
    )
    pred_pts_lb, _, _ = corners_from_segmentation_prob(prob, post_thr=0.5)
    pred_pts_orig = unletterbox_points(pred_pts_lb, lb_meta).astype(np.float32)
    segmentation_ms = (time.perf_counter() - t0) * 1000.0

    # Warp -> crops
    t0 = time.perf_counter()
    warp_bgr = warp_from_corners(raw_bgr, pred_pts_orig, warp_size=warp_size)
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

    # Overlay
    t0 = time.perf_counter()
    overlay = raw_bgr.copy()

    pts_int = order_points(pred_pts_orig).astype(np.int32)
    cv2.polylines(
        overlay,
        [pts_int.reshape(-1, 1, 2)],
        isClosed=True,
        color=(0, 255, 0),
        thickness=4,
        lineType=cv2.LINE_AA,
    )

    src = order_points(pred_pts_orig).astype(np.float32)
    dst = np.array(
        [
            [0, 0],
            [warp_size - 1, 0],
            [warp_size - 1, warp_size - 1],
            [0, warp_size - 1],
        ],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(src, dst)
    Minv = np.linalg.inv(M)

    cell_step = (warp_size - 1) / 9.0

    for r in range(9):
        for c in range(9):
            if givens_grid[r, c] != 0:
                continue

            val = int(solved_grid[r, c])

            cx = (c + 0.5) * cell_step
            cy = (r + 0.5) * cell_step

            warped_pt = np.array([[[cx, cy]]], dtype=np.float32)
            orig_pt = cv2.perspectiveTransform(warped_pt, Minv)[0, 0]
            x, y = int(round(orig_pt[0])), int(round(orig_pt[1]))

            text = str(val)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.50, min(raw_bgr.shape[:2]) / 1100.0)
            thickness = 5

            (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
            org = (x - tw // 2, y + th // 2)

            # White underlay
            cv2.putText(
                overlay,
                text,
                org,
                font,
                font_scale,
                (255, 255, 255),
                thickness + 2,
                cv2.LINE_AA,
            )

            # Bold blue solved digit
            cv2.putText(
                overlay,
                text,
                org,
                font,
                font_scale,
                (255, 0, 0),
                thickness,
                cv2.LINE_AA,
            )

    overlay_ms = (time.perf_counter() - t0) * 1000.0
    pipeline_ms = (time.perf_counter() - t_pipeline0) * 1000.0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), overlay)

    print(f"Wrote real solver overlay: {out_path}")
    print()
    print("Predicted givens:")
    print(givens_grid)
    print()
    print("Solved grid:")
    print(solved_grid)
    print()
    print("Latency breakdown")
    print(f"Runtime/model load one-time: {runtime_load_ms:.1f} ms")
    print(f"Segmentation + corners:      {segmentation_ms:.1f} ms")
    print(f"Warp + crop extraction:      {warp_crop_ms:.1f} ms")
    print(f"OCR inference + calibration: {ocr_ms:.1f} ms")
    print(f"Sudoku solve:                {solve_ms:.1f} ms")
    print(f"Overlay rendering:           {overlay_ms:.1f} ms")
    print(f"Per-image pipeline total:    {pipeline_ms:.1f} ms")


if __name__ == "__main__":
    main()
