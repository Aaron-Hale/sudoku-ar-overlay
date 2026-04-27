from pathlib import Path
import csv
import cv2
import numpy as np
import signal

from sudoku_ar_overlay.grid_discovery import find_sudoku_grid_candidate
from sudoku_ar_overlay.grid_refinement import refine_sudoku_grid_corners
from sudoku_ar_overlay.grid_validation import warp_candidate
from sudoku_ar_overlay.solver_adapter import solve_frame


START_FRAME = 732
END_FRAME = 1148
STEP = 2


class SolveTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise SolveTimeout("solve timed out")


def solve_with_timeout(frame, repo_root: str, timeout_sec: float = 6.0):
    old = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_sec)

    try:
        return solve_frame(frame, solver="real", repo_root=repo_root)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def sharpness_score(frame_bgr):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def draw_poly(frame, corners, color, label):
    out = frame.copy()
    pts = np.asarray(corners, dtype="int32").reshape(-1, 1, 2)
    cv2.polylines(out, [pts], True, color, 4)

    for p in pts.reshape(4, 2):
        cv2.circle(out, tuple(p), 7, color, -1)

    cv2.putText(
        out,
        label,
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        color,
        3,
        cv2.LINE_AA,
    )
    return out


repo_root = str(Path("~/projects/sudoku-image-solver").expanduser())
video_path = Path("assets/demo/raw_iphone_aggressive_1080p30.mp4")
out_dir = Path("assets/demo/second_puzzle_debug")
out_dir.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(video_path))
if not cap.isOpened():
    raise RuntimeError(f"Could not open {video_path}")

total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
print(f"Scanning {video_path}")
print(f"total_frames={total}")
print(f"target_range={START_FRAME}-{END_FRAME}, step={STEP}")

rows = []
candidates = []

for frame_idx in range(START_FRAME, min(END_FRAME + 1, total), STEP):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()

    if not ok:
        rows.append([frame_idx, "read_failed", "", "", "", "", ""])
        continue

    cand = find_sudoku_grid_candidate(frame, min_area_frac=0.020)

    if not cand.ok or cand.corners is None:
        rows.append([frame_idx, "no_candidate", "", "", "", "", cand.reason])
        continue

    refined = refine_sudoku_grid_corners(
        frame,
        cand.corners,
        max_mean_error_px=24.0,
        min_found_lines=7,
    )

    if not refined.ok or refined.corners is None:
        rows.append([
            frame_idx,
            "refine_failed",
            f"{cand.score:.4f}",
            "",
            "",
            "",
            refined.reason,
        ])
        continue

    crop = warp_candidate(frame, refined.corners, size=900)
    sharp = sharpness_score(crop)
    area = float(cv2.contourArea(np.asarray(refined.corners, dtype="float32").reshape(-1, 1, 2)))

    score = (
        cand.score * 1000.0
        + sharp * 0.01
        + area * 0.00001
        - refined.mean_error_px * 5.0
    )

    candidates.append({
        "frame_idx": frame_idx,
        "frame": frame.copy(),
        "corners": refined.corners.copy(),
        "crop": crop,
        "grid_score": cand.score,
        "fit_error": refined.mean_error_px,
        "sharpness": sharp,
        "area": area,
        "score": score,
        "reason": refined.reason,
    })

    rows.append([
        frame_idx,
        "candidate",
        f"{cand.score:.4f}",
        f"{refined.mean_error_px:.2f}",
        f"{sharp:.1f}",
        f"{area:.1f}",
        refined.reason,
    ])

cap.release()

csv_path = out_dir / "second_puzzle_candidates.csv"
with csv_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["frame_idx", "status", "grid_score", "fit_error", "sharpness", "area", "reason"])
    writer.writerows(rows)

print(f"candidate_count={len(candidates)}")

candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

selected = []
for c in candidates:
    if all(abs(c["frame_idx"] - s["frame_idx"]) >= 12 for s in selected):
        selected.append(c)
    if len(selected) >= 20:
        break

solve_rows = []
solved_any = False

for rank, c in enumerate(selected, start=1):
    frame_idx = c["frame_idx"]

    crop_path = out_dir / f"rank_{rank:02d}_frame_{frame_idx:04d}_crop.jpg"
    overlay_path = out_dir / f"rank_{rank:02d}_frame_{frame_idx:04d}_overlay.jpg"

    cv2.imwrite(str(crop_path), c["crop"])
    cv2.imwrite(
        str(overlay_path),
        draw_poly(c["frame"], c["corners"], (0, 255, 0), f"rank {rank} frame {frame_idx}"),
    )

    try:
        result = solve_with_timeout(c["crop"], repo_root=repo_root, timeout_sec=6.0)
        print(f"SOLVED rank={rank} frame={frame_idx} latency={result.solve_latency_ms:.1f}ms")
        solve_rows.append([
            rank,
            frame_idx,
            "SOLVED",
            f"{result.solve_latency_ms:.1f}",
            f"{c['grid_score']:.4f}",
            f"{c['fit_error']:.2f}",
            f"{c['sharpness']:.1f}",
            f"{c['score']:.2f}",
        ])
        solved_any = True
        break

    except Exception as exc:
        print(f"failed rank={rank} frame={frame_idx}: {type(exc).__name__}: {exc}")
        solve_rows.append([
            rank,
            frame_idx,
            f"failed: {type(exc).__name__}: {exc}",
            "",
            f"{c['grid_score']:.4f}",
            f"{c['fit_error']:.2f}",
            f"{c['sharpness']:.1f}",
            f"{c['score']:.2f}",
        ])

solve_csv = out_dir / "second_puzzle_solve_attempts.csv"
with solve_csv.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["rank", "frame_idx", "status", "latency_ms", "grid_score", "fit_error", "sharpness", "score"])
    writer.writerows(solve_rows)

print(f"Wrote {csv_path}")
print(f"Wrote {solve_csv}")
print(f"Wrote debug images under {out_dir}")
print(f"solved_any={solved_any}")
