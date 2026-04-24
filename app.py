from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from sudoku_ar_overlay.board_state import BoardSession, BoardStatus
from sudoku_ar_overlay.config import OverlayConfig, TrackingConfig
from sudoku_ar_overlay.overlay import render_solution_overlay
from sudoku_ar_overlay.smoothing import smooth_corners
from sudoku_ar_overlay.solver_adapter import load_image_bgr, solve_frame


def run_image_mode(args: argparse.Namespace) -> None:
    frame = load_image_bgr(args.image)
    result = solve_frame(frame, use_mock=True)

    out = render_solution_overlay(
        frame=frame,
        corners=result.corners,
        givens=result.givens,
        solution=result.solution,
        cfg=OverlayConfig(),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), out)

    print(f"Wrote overlay image: {out_path}")
    print(f"Solver status: {result.status}")
    print(f"Solve latency: {result.solve_latency_ms:.2f} ms")


def run_webcam_mode(args: argparse.Namespace) -> None:
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {args.camera}")

    session = BoardSession()
    overlay_cfg = OverlayConfig()
    tracking_cfg = TrackingConfig()

    frame_idx = 0
    last_fps_time = time.perf_counter()
    fps = 0.0

    print("Controls: s=solve current frame, r=reset, q=quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        display = frame.copy()

        if (
            session.status == BoardStatus.SOLVED_TRACKING
            and session.givens is not None
            and session.solution is not None
            and session.smoothed_corners is not None
        ):
            display = render_solution_overlay(
                frame=display,
                corners=session.smoothed_corners,
                givens=session.givens,
                solution=session.solution,
                cfg=overlay_cfg,
            )

        now = time.perf_counter()
        dt = now - last_fps_time
        if dt > 0:
            fps = 0.95 * fps + 0.05 * (1.0 / dt) if fps > 0 else 1.0 / dt
        last_fps_time = now

        status_text = (
            f"state={session.status.value} "
            f"fps={fps:.1f} "
            f"solve_ms={session.solve_latency_ms:.1f}"
        )

        cv2.putText(
            display,
            status_text,
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow("sudoku-ar-overlay", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        if key == ord("r"):
            session.reset()
            print("Reset session")

        if key == ord("s"):
            result = solve_frame(frame, use_mock=True)
            smoothed = smooth_corners(
                session.smoothed_corners,
                result.corners,
                alpha=tracking_cfg.smoothing_alpha,
            )
            session.set_solved(
                givens=result.givens,
                solution=result.solution,
                corners=smoothed,
                frame_idx=frame_idx,
                solve_latency_ms=result.solve_latency_ms,
            )
            print(
                f"Solved frame {frame_idx}: "
                f"status={result.status}, latency={result.solve_latency_ms:.2f} ms"
            )

        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="sudoku-ar-overlay")
    parser.add_argument(
        "--mode",
        choices=["image", "webcam"],
        required=True,
        help="Run a static image overlay or webcam overlay.",
    )
    parser.add_argument("--image", type=str, help="Path to input image for image mode.")
    parser.add_argument(
        "--out",
        type=str,
        default="assets/demo/static_overlay.jpg",
        help="Output path for image mode.",
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index for webcam mode.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "image":
        if not args.image:
            raise ValueError("--image is required for image mode.")
        run_image_mode(args)
        return

    if args.mode == "webcam":
        run_webcam_mode(args)
        return

    raise ValueError(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()
