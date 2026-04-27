from pathlib import Path

import cv2
import numpy as np

from sudoku_ar_overlay.grid_discovery import find_sudoku_grid_candidate
from sudoku_ar_overlay.grid_refinement import refine_sudoku_grid_corners
from sudoku_ar_overlay.grid_validation import warp_candidate


def draw_poly(frame, corners, color, label):
    out = frame.copy()
    pts = np.asarray(corners, dtype="int32").reshape(-1, 1, 2)
    cv2.polylines(out, [pts], True, color, 4)

    for p in pts.reshape(4, 2):
        cv2.circle(out, tuple(p), 8, color, -1)

    cv2.putText(out, label, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3, cv2.LINE_AA)
    return out


frame_path = Path("assets/demo/compare_frames/frame_0670.jpg")
out_dir = Path("assets/demo/compare_frames/refinement")
out_dir.mkdir(parents=True, exist_ok=True)

frame = cv2.imread(str(frame_path))
if frame is None:
    raise RuntimeError(f"Could not read {frame_path}")

candidate = find_sudoku_grid_candidate(frame, min_area_frac=0.025)

print("candidate:", candidate.ok, candidate.reason)
if not candidate.ok or candidate.corners is None:
    raise SystemExit(1)

refined = refine_sudoku_grid_corners(frame, candidate.corners)

print("refined:", refined.ok, refined.reason)

rough_overlay = draw_poly(frame, candidate.corners, (0, 0, 255), "rough")
cv2.imwrite(str(out_dir / "rough_overlay.jpg"), rough_overlay)
cv2.imwrite(str(out_dir / "rough_warp.jpg"), warp_candidate(frame, candidate.corners, size=900))

if refined.ok and refined.corners is not None:
    refined_overlay = draw_poly(frame, refined.corners, (0, 255, 0), "refined")
    cv2.imwrite(str(out_dir / "refined_overlay.jpg"), refined_overlay)
    cv2.imwrite(str(out_dir / "refined_warp.jpg"), warp_candidate(frame, refined.corners, size=900))

print(f"Wrote {out_dir}")
