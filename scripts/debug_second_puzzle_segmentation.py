from pathlib import Path
import csv
import cv2
import numpy as np

from sudoku_ar_overlay.solver_adapter import detect_board_corners_only
from sudoku_ar_overlay.grid_validation import validate_sudoku_grid_candidate, warp_candidate
from sudoku_ar_overlay.grid_refinement import refine_sudoku_grid_corners


START_FRAME = 732
END_FRAME = 1148
STEP = 10


def draw_poly(frame, corners, color, label):
    out = frame.copy()
    pts = np.asarray(corners, dtype="int32").reshape(-1, 1, 2)
    cv2.polylines(out, [pts], True, color, 4)

    for p in pts.reshape(4, 2):
        cv2.circle(out, tuple(p), 7, color, -1)

    cv2.putText(out, label, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)
    return out


repo_root = str(Path("~/projects/sudoku-image-solver").expanduser())
video_path = Path("assets/demo/raw_iphone_aggressive_1080p30.mp4")
out_dir = Path("assets/demo/second_puzzle_segmentation_debug")
out_dir.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(video_path))
if not cap.isOpened():
    raise RuntimeError(f"Could not open {video_path}")

rows = []
valid_count = 0
refined_count = 0

for frame_idx in range(START_FRAME, END_FRAME + 1, STEP):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        rows.append([frame_idx, "read_failed", "", "", ""])
        continue

    try:
        corners, timing = detect_board_corners_only(frame, repo_root=repo_root)
    except Exception as exc:
        rows.append([frame_idx, "seg_exception", "", "", f"{type(exc).__name__}: {exc}"])
        continue

    grid = validate_sudoku_grid_candidate(
        frame,
        corners,
        min_peak=0.015,
        min_strong_lines=5,
    )

    overlay = draw_poly(
        frame,
        corners,
        (0, 255, 255),
        f"seg frame {frame_idx} grid_ok={grid.ok}",
    )
    cv2.imwrite(str(out_dir / f"frame_{frame_idx:04d}_seg_overlay.jpg"), overlay)

    if grid.ok:
        valid_count += 1
        cv2.imwrite(str(out_dir / f"frame_{frame_idx:04d}_seg_warp.jpg"), warp_candidate(frame, corners, size=900))

    refined = refine_sudoku_grid_corners(
        frame,
        corners,
        max_mean_error_px=28.0,
        min_found_lines=5,
    )

    if refined.ok and refined.corners is not None:
        refined_count += 1
        refined_overlay = draw_poly(
            frame,
            refined.corners,
            (0, 255, 0),
            f"refined frame {frame_idx}",
        )
        cv2.imwrite(str(out_dir / f"frame_{frame_idx:04d}_refined_overlay.jpg"), refined_overlay)
        cv2.imwrite(str(out_dir / f"frame_{frame_idx:04d}_refined_warp.jpg"), warp_candidate(frame, refined.corners, size=900))

    rows.append([
        frame_idx,
        "seg_done",
        grid.ok,
        refined.ok,
        f"grid={grid.reason}; refined={refined.reason}",
    ])

cap.release()

csv_path = out_dir / "second_puzzle_segmentation.csv"
with csv_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["frame_idx", "status", "grid_ok", "refined_ok", "reason"])
    writer.writerows(rows)

print(f"valid_grid_count={valid_count}")
print(f"refined_count={refined_count}")
print(f"Wrote {csv_path}")
print(f"Wrote images under {out_dir}")
