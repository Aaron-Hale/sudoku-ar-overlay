from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from sudoku_ar_overlay.board_state import BoardSession, BoardStatus
from sudoku_ar_overlay.flow_tracker import FlowHomographyTracker
from sudoku_ar_overlay.overlay import draw_board_outline, render_solution_overlay
from sudoku_ar_overlay.solver_adapter import detect_board_corners_only, solve_frame


def draw_text_lines(frame, lines: list[str], x: int = 20, y: int = 35) -> None:
    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (x, y + i * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optical-flow Sudoku AR tracking demo")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--repo-root", type=str, default="~/projects/sudoku-image-solver")
    parser.add_argument("--seg-refresh-frames", type=int, default=90)
    parser.add_argument("--max-corners", type=int, default=250)
    parser.add_argument("--min-points", type=int, default=25)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.45)
    parser.add_argument("--ransac-reproj-threshold", type=float, default=4.0)
    parser.add_argument("--refresh-points-every", type=int, default=15)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--record-out",
        type=str,
        default=None,
        help="Optional path to save the rendered OpenCV output as an MP4.",
    )
    parser.add_argument(
        "--record-fps",
        type=float,
        default=30.0,
        help="FPS to use for saved recording.",
    )
    parser.add_argument(
        "--auto-solve-on-lock",
        action="store_true",
        help="When pressing l, lock the board and immediately solve it.",
    )
    return parser.parse_args()


def lock_board(frame, session: BoardSession, flow: FlowHomographyTracker, args, frame_idx: int):
    print("Locking board with segmentation...")
    corners, timing = detect_board_corners_only(frame, repo_root=args.repo_root)
    seg_ms = timing.get("segmentation_ms", 0.0)

    init_result = flow.initialize(frame, corners)
    reason = f"manual lock: {init_result.reason}"

    if init_result.ok and init_result.corners is not None:
        session.smoothed_corners = init_result.corners
        session.last_corners = init_result.corners
        session.last_seen_frame_idx = frame_idx
        session.status = (
            BoardStatus.SOLVED_TRACKING
            if session.solution is not None
            else BoardStatus.BOARD_DETECTED
        )
        print(reason)
        return True, reason, seg_ms

    print(reason)
    return False, reason, seg_ms


def solve_board(frame, session: BoardSession, flow: FlowHomographyTracker, args, frame_idx: int):
    print("Solving current frame...")
    result = solve_frame(frame, solver="real", repo_root=args.repo_root)

    session.set_solved(
        givens=result.givens,
        solution=result.solution,
        corners=result.corners,
        frame_idx=frame_idx,
        solve_latency_ms=result.solve_latency_ms,
    )

    init_result = flow.initialize(frame, result.corners)
    reason = f"solve + flow init: {init_result.reason}"

    if init_result.ok and init_result.corners is not None:
        session.smoothed_corners = init_result.corners
        session.last_corners = init_result.corners
        session.last_seen_frame_idx = frame_idx
        session.status = BoardStatus.SOLVED_TRACKING

    print(f"Solved: {result.solve_latency_ms:.1f} ms")
    print(reason)
    return init_result.ok, reason


def main() -> None:
    args = parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {args.camera}")

    session = BoardSession()
    flow = FlowHomographyTracker(
        max_corners=args.max_corners,
        min_points=args.min_points,
        min_inlier_ratio=args.min_inlier_ratio,
        ransac_reproj_threshold=args.ransac_reproj_threshold,
        refresh_points_every=args.refresh_points_every,
    )

    frame_idx = 0
    fps = 0.0
    last_time = time.perf_counter()

    last_reason = ""
    last_flow_points = 0
    last_inliers = 0
    last_inlier_ratio = 0.0
    last_seg_ms = 0.0
    flow_ok = False

    video_writer = None

    print("Controls:")
    print("  l  lock/reacquire board using segmentation")
    print("  s  solve current frame and initialize tracker")
    print("  r  reset")
    print("  q  quit")
    print()
    print("Recommended flow:")
    print("  1. Put board in view")
    print("  2. Press l to lock board")
    print("  3. Press s to solve, unless using --auto-solve-on-lock")
    print("  4. Move slowly and watch overlay follow with optical flow")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            display = frame.copy()

            # Fast per-frame flow update.
            if flow.initialized:
                flow_result = flow.update(frame)

                if flow_result.ok and flow_result.corners is not None:
                    flow_ok = True
                    session.smoothed_corners = flow_result.corners
                    session.last_corners = flow_result.corners
                    session.last_seen_frame_idx = frame_idx

                    last_reason = flow_result.reason
                    last_flow_points = flow_result.num_points
                    last_inliers = flow_result.num_inliers
                    last_inlier_ratio = flow_result.inlier_ratio

                    if session.solution is not None:
                        session.status = BoardStatus.SOLVED_TRACKING
                    else:
                        session.status = BoardStatus.BOARD_DETECTED

                else:
                    flow_ok = False
                    last_reason = flow_result.reason
                    if session.solution is not None:
                        session.status = BoardStatus.TRACKING_LOST
                    else:
                        session.status = BoardStatus.NO_BOARD

            # Slow automatic segmentation reacquisition only when flow is not initialized.
            should_seg_refresh = (
                frame_idx % max(args.seg_refresh_frames, 1) == 0
                and not flow.initialized
            )

            if should_seg_refresh:
                try:
                    locked, reason, seg_ms = lock_board(frame, session, flow, args, frame_idx)
                    flow_ok = locked
                    last_reason = f"auto {reason}"
                    last_seg_ms = seg_ms

                except Exception as exc:
                    last_reason = f"seg failed: {type(exc).__name__}: {exc}"
                    flow_ok = False

            # Draw outline or solved overlay.
            if (
                session.status == BoardStatus.BOARD_DETECTED
                and session.smoothed_corners is not None
            ):
                display = draw_board_outline(display, session.smoothed_corners)

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
                )

            now = time.perf_counter()
            dt = now - last_time
            if dt > 0:
                fps = 0.95 * fps + 0.05 * (1.0 / dt) if fps > 0 else 1.0 / dt
            last_time = now

            lines = [
                f"state={session.status.value} fps={fps:.1f} flow={flow_ok} points={last_flow_points}",
                f"inliers={last_inliers} ratio={last_inlier_ratio:.2f} seg_ms={last_seg_ms:.1f}",
                "l lock/reacquire | s solve | r reset | q quit",
            ]

            if args.debug:
                lines.append(f"reason: {last_reason[:100]}")

            draw_text_lines(display, lines)

            if args.record_out:
                if video_writer is None:
                    out_path = Path(args.record_out).expanduser()
                    out_path.parent.mkdir(parents=True, exist_ok=True)

                    height, width = display.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    video_writer = cv2.VideoWriter(
                        str(out_path),
                        fourcc,
                        args.record_fps,
                        (width, height),
                    )

                    if not video_writer.isOpened():
                        raise RuntimeError(f"Could not open video writer: {out_path}")

                    print(f"Recording rendered output to: {out_path}")

                video_writer.write(display)

            cv2.imshow("sudoku-ar-flow-tracking-demo", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("r"):
                session.reset()
                flow.reset()
                flow_ok = False
                last_reason = "reset"
                print("Reset")

            if key == ord("l"):
                try:
                    locked, reason, seg_ms = lock_board(frame, session, flow, args, frame_idx)
                    flow_ok = locked
                    last_reason = reason
                    last_seg_ms = seg_ms

                    if locked and args.auto_solve_on_lock:
                        solved, solve_reason = solve_board(frame, session, flow, args, frame_idx)
                        flow_ok = solved
                        last_reason = solve_reason

                except Exception as exc:
                    last_reason = f"lock failed: {type(exc).__name__}: {exc}"
                    print(last_reason)
                    flow_ok = False

            if key == ord("s"):
                try:
                    solved, reason = solve_board(frame, session, flow, args, frame_idx)
                    flow_ok = solved
                    last_reason = reason

                except Exception as exc:
                    last_reason = f"solve failed: {type(exc).__name__}: {exc}"
                    print(last_reason)
                    flow_ok = False

            frame_idx += 1

    finally:
        if video_writer is not None:
            video_writer.release()
            print(f"Saved recording to: {args.record_out}")

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
