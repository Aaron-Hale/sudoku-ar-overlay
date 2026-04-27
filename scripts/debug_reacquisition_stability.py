from pathlib import Path
import csv
import math

import cv2
import numpy as np

from sudoku_ar_overlay.grid_discovery import find_sudoku_grid_candidate
from sudoku_ar_overlay.grid_refinement import refine_sudoku_grid_corners
from sudoku_ar_overlay.grid_validation import warp_candidate
from sudoku_ar_overlay.reacquisition import (
    CandidateStabilityBuffer,
    ReacquisitionCandidate,
)


def draw_poly(frame, corners, color, label):
    out = frame.copy()
    pts = np.asarray(corners, dtype="int32").reshape(-1, 1, 2)
    cv2.polylines(out, [pts], True, color, 4)

    for p in pts.reshape(4, 2):
        cv2.circle(out, tuple(p), 7, color, -1)

    cv2.putText(out, label, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)
    return out


video_path = Path("assets/demo/raw_iphone_demo2_1080p30.mp4")
out_dir = Path("assets/demo/reacq_stability_debug")
out_dir.mkdir(parents=True, exist_ok=True)

buffer = CandidateStabilityBuffer(
    min_frames=4,
    max_history=12,
    max_center_motion_frac=0.025,
    max_area_ratio=1.18,
    max_corner_motion_frac=0.035,
    max_fit_error_px=14.0,
)

rows = []
thumbs = []
first_stable_saved = False

cap = cv2.VideoCapture(str(video_path))
if not cap.isOpened():
    raise RuntimeError(f"Could not open {video_path}")

for frame_idx in range(540, 736, 5):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        rows.append([frame_idx, "read_failed", "", "", "", "", ""])
        continue

    candidate = find_sudoku_grid_candidate(frame, min_area_frac=0.025)

    if not candidate.ok or candidate.corners is None:
        buffer.reset()
        rows.append([frame_idx, "no_candidate", "", "", "", "", candidate.reason])
        thumb = cv2.resize(frame, (420, int(frame.shape[0] * 420 / frame.shape[1])))
        cv2.putText(thumb, f"{frame_idx} no cand", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        thumbs.append(thumb)
        continue

    refined = refine_sudoku_grid_corners(frame, candidate.corners)

    if not refined.ok or refined.corners is None:
        buffer.reset()
        rows.append([frame_idx, "refine_failed", "", "", "", "", refined.reason])
        overlay = draw_poly(frame, candidate.corners, (0, 0, 255), f"{frame_idx} rough only")
        thumb = cv2.resize(overlay, (420, int(frame.shape[0] * 420 / frame.shape[1])))
        thumbs.append(thumb)
        continue

    reacq_candidate = ReacquisitionCandidate(
        frame_idx=frame_idx,
        corners=refined.corners,
        frame_shape=frame.shape,
        fit_error_px=refined.mean_error_px,
        score=candidate.score,
        reason=refined.reason,
    )

    stable = buffer.push(reacq_candidate)

    status = "stable" if stable.stable else "unstable"
    rows.append([
        frame_idx,
        status,
        f"{stable.center_motion_frac:.4f}",
        f"{stable.area_ratio:.3f}",
        f"{stable.corner_motion_frac:.4f}",
        f"{refined.mean_error_px:.2f}",
        stable.reason,
    ])

    color = (0, 255, 0) if stable.stable else (0, 255, 255)
    overlay = draw_poly(frame, refined.corners, color, f"{frame_idx} {status}")
    thumb = cv2.resize(overlay, (420, int(frame.shape[0] * 420 / frame.shape[1])))
    thumbs.append(thumb)

    if stable.stable and not first_stable_saved:
        first_stable_saved = True
        cv2.imwrite(str(out_dir / "first_stable_overlay.jpg"), overlay)
        cv2.imwrite(str(out_dir / "first_stable_warp.jpg"), warp_candidate(frame, refined.corners, size=900))
        print(f"First stable candidate at frame {frame_idx}: {stable.reason}")

cap.release()

csv_path = out_dir / "reacq_stability.csv"
with csv_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "frame_idx",
        "status",
        "center_motion_frac",
        "area_ratio",
        "corner_motion_frac",
        "fit_error_px",
        "reason",
    ])
    writer.writerows(rows)

if thumbs:
    cols = 4
    rows_needed = math.ceil(len(thumbs) / cols)
    h = max(t.shape[0] for t in thumbs)
    w = max(t.shape[1] for t in thumbs)
    blank = np.full((h, w, 3), 255, dtype=np.uint8)

    grid_rows = []
    for r in range(rows_needed):
        row_imgs = []
        for c in range(cols):
            i = r * cols + c
            if i < len(thumbs):
                img = thumbs[i]
                if img.shape[0] < h:
                    pad = np.full((h - img.shape[0], img.shape[1], 3), 255, dtype=np.uint8)
                    img = np.vstack([img, pad])
                row_imgs.append(img)
            else:
                row_imgs.append(blank.copy())
        grid_rows.append(np.hstack(row_imgs))

    montage = np.vstack(grid_rows)
    cv2.imwrite(str(out_dir / "reacq_stability_montage.jpg"), montage)

print(f"Wrote {csv_path}")
print(f"Wrote {out_dir}")
