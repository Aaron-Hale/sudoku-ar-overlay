from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from sudoku_ar_overlay.board_state import BoardSession, BoardStatus
from sudoku_ar_overlay.config import OverlayConfig, TrackingConfig
from sudoku_ar_overlay.overlay import draw_board_outline, render_solution_overlay
from sudoku_ar_overlay.smoothing import smooth_corners
from sudoku_ar_overlay.solver_adapter import (
    detect_board_corners_only,
    load_image_bgr,
    solve_frame,
)
from sudoku_ar_overlay.stabilizer import CornerStabilizer
from sudoku_ar_overlay.tracking import score_corners


def print_solver_result(result) -> None:
    print(f"Solver status: {result.status}")
    print(f"Solve latency: {result.solve_latency_ms:.2f} ms")

    if result.latency_breakdown_ms:
        print("Latency breakdown:")
        for key, value in result.latency_breakdown_ms.items():
            print(f"  {key}: {value:.2f} ms")


def draw_text_lines(frame, lines: list[str], x: int = 20, y: int = 35) -> None:
    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (x, y + i * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )


def solve_and_update_session(
    frame,
    session: BoardSession,
    args: argparse.Namespace,
    frame_idx: int,
    tracking_cfg: TrackingConfig,
) -> tuple[bool, str]:
    try:
        print(f"Solving frame {frame_idx} with solver={args.solver}...")
        result = solve_frame(
            frame,
            solver=args.solver,
            repo_root=args.repo_root,
        )

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
        session.tracking_quality = 1.0

        print(f"Solved frame {frame_idx}")
        print_solver_result(result)

        return True, ""

    except Exception as exc:
        msg = f"solve failed: {type(exc).__name__}: {exc}"
        print(msg)
        return False, msg


def run_image_mode(args: argparse.Namespace) -> None:
    frame = load_image_bgr(args.image)

    result = solve_frame(
        frame,
        solver=args.solver,
        repo_root=args.repo_root,
    )

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
    print_solver_result(result)


def update_board_tracking(
    frame,
    session: BoardSession,
    args: argparse.Namespace,
    frame_idx: int,
    stabilizer: CornerStabilizer,
) -> tuple[bool, str, float, float, float]:
    """Detect board corners only, stabilize them, and update session tracking state."""
    try:
        corners, timing = detect_board_corners_only(
            frame,
            repo_root=args.repo_root,
        )

        scored = score_corners(
            corners,
            frame_shape=frame.shape,
            previous_corners=session.smoothed_corners,
        )

        if not scored.detected or scored.corners is None:
            return False, scored.reason, timing.get("segmentation_ms", 0.0), 0.0, 0.0

        stabilized = stabilizer.update(
            detected_corners=scored.corners,
            quality=scored.quality,
            frame_shape=frame.shape,
        )

        if not stabilized.accepted or stabilized.corners is None:
            return (
                False,
                stabilized.reason,
                timing.get("segmentation_ms", 0.0),
                stabilized.alpha_used,
                stabilized.mean_motion_px,
            )

        session.last_corners = scored.corners
        session.smoothed_corners = stabilized.corners
        session.last_seen_frame_idx = frame_idx
        session.tracking_quality = scored.quality

        if session.solution is not None:
            if session.status == BoardStatus.TRACKING_LOST:
                session.status = BoardStatus.REACQUIRED
            else:
                session.status = BoardStatus.SOLVED_TRACKING
        else:
            session.status = BoardStatus.BOARD_DETECTED

        return (
            True,
            stabilized.reason,
            timing.get("segmentation_ms", 0.0),
            stabilized.alpha_used,
            stabilized.mean_motion_px,
        )

    except Exception as exc:
        return False, f"track failed: {type(exc).__name__}: {exc}", 0.0, 0.0, 0.0


def run_webcam_mode(args: argparse.Namespace) -> None:
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {args.camera}")

    session = BoardSession()
    overlay_cfg = OverlayConfig()
    tracking_cfg = TrackingConfig(
        smoothing_alpha=args.smoothing_alpha,
        lost_after_frames=args.lost_after_tracking_attempts,
        detection_every_n_frames=args.track_every_n_frames,
    )

    stabilizer = CornerStabilizer(
        median_window=args.stabilizer_median_window,
        min_quality=args.stabilizer_min_quality,
        static_alpha=args.stabilizer_static_alpha,
        moving_alpha=args.stabilizer_moving_alpha,
        static_motion_px=args.stabilizer_static_motion_px,
        fast_motion_px=args.stabilizer_fast_motion_px,
        max_jump_ratio=args.stabilizer_max_jump_ratio,
    )

    frame_idx = 0
    tracking_attempts_since_seen = 0
    last_track_ms = 0.0
    last_track_reason = ""
    last_stabilizer_alpha = 0.0
    last_mean_motion_px = 0.0

    last_fps_time = time.perf_counter()
    fps = 0.0

    frozen = False
    frozen_frame = None

    auto_solve_enabled = bool(args.auto_solve)
    last_auto_solve_attempt = 0.0
    last_error = ""

    print("Controls:")
    print("  s      solve current/frozen frame")
    print("  f      freeze/unfreeze frame")
    print("  space  freeze/unfreeze frame")
    print("  a      toggle auto-solve")
    print("  r      reset")
    print("  q      quit")
    print()
    print("Tip: press f to freeze a clean frame, then press s to solve it.")
    if args.track_board:
        print(
            f"Tracking enabled: segmentation-only board detection every "
            f"{args.track_every_n_frames} frames."
        )

    while True:
        ok, live_frame = cap.read()
        if not ok:
            break

        if frozen and frozen_frame is not None:
            frame_for_display = frozen_frame.copy()
            frame_for_solve = frozen_frame.copy()
            should_track_this_frame = False
        else:
            frame_for_display = live_frame.copy()
            frame_for_solve = live_frame.copy()
            should_track_this_frame = (
                args.track_board
                and frame_idx % max(args.track_every_n_frames, 1) == 0
            )

        if should_track_this_frame:
            detected, reason, track_ms, stab_alpha, mean_motion_px = update_board_tracking(
                frame=frame_for_solve,
                session=session,
                args=args,
                frame_idx=frame_idx,
                stabilizer=stabilizer,
            )
            last_track_ms = track_ms
            last_track_reason = reason
            last_stabilizer_alpha = stab_alpha
            last_mean_motion_px = mean_motion_px

            if detected:
                tracking_attempts_since_seen = 0
            else:
                tracking_attempts_since_seen += 1

                if (
                    session.solution is not None
                    and tracking_attempts_since_seen >= args.lost_after_tracking_attempts
                ):
                    session.status = BoardStatus.TRACKING_LOST

                if session.solution is None:
                    session.status = BoardStatus.NO_BOARD

        display = frame_for_display.copy()

        if (
            session.solution is None
            and session.smoothed_corners is not None
            and session.status == BoardStatus.BOARD_DETECTED
        ):
            display = draw_board_outline(display, session.smoothed_corners)

        if (
            session.status in {BoardStatus.SOLVED_TRACKING, BoardStatus.REACQUIRED}
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

            if session.status == BoardStatus.REACQUIRED:
                session.status = BoardStatus.SOLVED_TRACKING

        now = time.perf_counter()
        dt = now - last_fps_time
        if dt > 0:
            fps = 0.95 * fps + 0.05 * (1.0 / dt) if fps > 0 else 1.0 / dt
        last_fps_time = now

        if (
            auto_solve_enabled
            and session.status != BoardStatus.SOLVED_TRACKING
            and now - last_auto_solve_attempt >= args.auto_solve_interval_sec
        ):
            last_auto_solve_attempt = now
            _, last_error = solve_and_update_session(
                frame=frame_for_solve,
                session=session,
                args=args,
                frame_idx=frame_idx,
                tracking_cfg=tracking_cfg,
            )

        lines = [
            (
                f"state={session.status.value} fps={fps:.1f} "
                f"solve_ms={session.solve_latency_ms:.1f} "
                f"track_ms={last_track_ms:.1f} q={session.tracking_quality:.2f}"
            ),
            (
                f"track={args.track_board} every={args.track_every_n_frames} "
                f"stab_a={last_stabilizer_alpha:.2f} motion={last_mean_motion_px:.1f}px "
                f"| s solve | r reset | q quit"
            ),
        ]

        if args.solver == "real" and session.status == BoardStatus.NO_BOARD:
            if args.track_board:
                lines.append("Hold board in view. Press s once detected, or f then s.")
            else:
                lines.append("Tip: freeze a clean frame with f, then press s.")

        if last_track_reason and args.debug:
            lines.append(f"tracking: {last_track_reason[:90]}")

        if last_error:
            lines.append(last_error[:95])

        draw_text_lines(display, lines)

        cv2.imshow("sudoku-ar-overlay", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        if key == ord("r"):
            session.reset()
            stabilizer.reset()
            tracking_attempts_since_seen = 0
            last_error = ""
            last_track_reason = ""
            print("Reset session")

        if key == ord("a"):
            auto_solve_enabled = not auto_solve_enabled
            last_auto_solve_attempt = 0.0
            print(f"auto_solve_enabled={auto_solve_enabled}")

        if key == ord("f") or key == ord(" "):
            if frozen:
                frozen = False
                frozen_frame = None
                print("Unfroze frame")
            else:
                frozen = True
                frozen_frame = live_frame.copy()
                print("Froze frame")

        if key == ord("s"):
            _, last_error = solve_and_update_session(
                frame=frame_for_solve,
                session=session,
                args=args,
                frame_idx=frame_idx,
                tracking_cfg=tracking_cfg,
            )

        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()



def run_video_mode(args: argparse.Namespace) -> None:
    """Process a recorded video and write an annotated output video.

    First implementation:
    - read frames from --input
    - solve once at --solve-frame
    - optionally run segmentation-only tracking every N frames
    - render cached solution when tracking is confident
    - hide overlay when tracking is lost
    - write output MP4
    """
    if not args.input:
        raise ValueError("--input is required for video mode.")

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {args.input}")

    input_fps = cap.get(cv2.CAP_PROP_FPS)
    if not input_fps or input_fps <= 1:
        input_fps = 30.0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    out_path = Path(args.out)
    if out_path.suffix.lower() not in {".mp4", ".mov", ".avi"}:
        out_path = Path("assets/demo/processed_video_overlay.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = BoardSession()
    overlay_cfg = OverlayConfig()
    tracking_cfg = TrackingConfig(
        smoothing_alpha=args.smoothing_alpha,
        lost_after_frames=args.lost_after_tracking_attempts,
        detection_every_n_frames=args.track_every_n_frames,
    )

    stabilizer = CornerStabilizer(
        median_window=args.stabilizer_median_window,
        min_quality=args.stabilizer_min_quality,
        static_alpha=args.stabilizer_static_alpha,
        moving_alpha=args.stabilizer_moving_alpha,
        static_motion_px=args.stabilizer_static_motion_px,
        fast_motion_px=args.stabilizer_fast_motion_px,
        max_jump_ratio=args.stabilizer_max_jump_ratio,
    )

    writer = None
    frame_idx = 0
    processed_frames = 0
    tracking_attempts_since_seen = 0

    last_error = ""
    last_track_reason = ""
    last_track_ms = 0.0
    last_stabilizer_alpha = 0.0
    last_mean_motion_px = 0.0

    loss_events = 0
    reacquisition_events = 0
    solved = False

    started = time.perf_counter()

    print(f"Reading video: {args.input}")
    print(f"Writing video: {out_path}")
    print(f"Input FPS: {input_fps:.2f}")
    print(f"Total frames: {total_frames if total_frames else 'unknown'}")
    print(f"Solve frame: {args.solve_frame}")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if args.video_max_frames > 0 and processed_frames >= args.video_max_frames:
            break

        if writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(out_path), fourcc, input_fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError(f"Could not open video writer: {out_path}")

        previous_status = session.status

        # Solve once on the requested frame.
        if frame_idx == args.solve_frame and not solved:
            solved, last_error = solve_and_update_session(
                frame=frame,
                session=session,
                args=args,
                frame_idx=frame_idx,
                tracking_cfg=tracking_cfg,
            )

        # Optional segmentation-only tracking/reacquisition.
        should_track_this_frame = (
            args.track_board
            and frame_idx % max(args.track_every_n_frames, 1) == 0
        )

        if should_track_this_frame:
            detected, reason, track_ms, stab_alpha, mean_motion_px = update_board_tracking(
                frame=frame,
                session=session,
                args=args,
                frame_idx=frame_idx,
                stabilizer=stabilizer,
            )

            last_track_reason = reason
            last_track_ms = track_ms
            last_stabilizer_alpha = stab_alpha
            last_mean_motion_px = mean_motion_px

            if detected:
                tracking_attempts_since_seen = 0
            else:
                tracking_attempts_since_seen += 1

                if (
                    session.solution is not None
                    and tracking_attempts_since_seen >= args.lost_after_tracking_attempts
                ):
                    session.status = BoardStatus.TRACKING_LOST

                if session.solution is None:
                    session.status = BoardStatus.NO_BOARD

        if session.status == BoardStatus.TRACKING_LOST and previous_status != BoardStatus.TRACKING_LOST:
            loss_events += 1

        if session.status == BoardStatus.REACQUIRED and previous_status == BoardStatus.TRACKING_LOST:
            reacquisition_events += 1

        display = frame.copy()

        if (
            session.solution is None
            and session.smoothed_corners is not None
            and session.status == BoardStatus.BOARD_DETECTED
        ):
            display = draw_board_outline(display, session.smoothed_corners)

        if (
            session.status in {BoardStatus.SOLVED_TRACKING, BoardStatus.REACQUIRED}
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

            if session.status == BoardStatus.REACQUIRED:
                session.status = BoardStatus.SOLVED_TRACKING

        if args.debug:
            lines = [
                (
                    f"state={session.status.value} frame={frame_idx} "
                    f"solve_ms={session.solve_latency_ms:.1f} "
                    f"track_ms={last_track_ms:.1f} q={session.tracking_quality:.2f}"
                ),
                (
                    f"track={args.track_board} every={args.track_every_n_frames} "
                    f"stab_a={last_stabilizer_alpha:.2f} "
                    f"motion={last_mean_motion_px:.1f}px"
                ),
                f"loss_events={loss_events} reacq_events={reacquisition_events}",
            ]

            if last_track_reason:
                lines.append(f"tracking: {last_track_reason[:90]}")
            if last_error:
                lines.append(last_error[:95])

            draw_text_lines(display, lines)

        writer.write(display)

        frame_idx += 1
        processed_frames += 1

    elapsed = time.perf_counter() - started

    if writer is not None:
        writer.release()
    cap.release()

    print(f"Wrote output video: {out_path}")
    print(f"Processed frames: {processed_frames}")
    print(f"Wall time: {elapsed:.2f} sec")
    if elapsed > 0:
        print(f"Processing FPS: {processed_frames / elapsed:.2f}")
    print(f"Final state: {session.status.value}")
    print(f"Solve latency ms: {session.solve_latency_ms:.2f}")
    print(f"Tracking loss events: {loss_events}")
    print(f"Reacquisition events: {reacquisition_events}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="sudoku-ar-overlay")

    parser.add_argument(
        "--mode",
        choices=["image", "webcam", "video"],
        required=True,
        help="Run a static image overlay or webcam overlay.",
    )
    parser.add_argument(
        "--solver",
        choices=["mock", "real"],
        default="mock",
        help="Use mock solver or real sudoku-image-solver inference path.",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(Path("~/projects/sudoku-image-solver").expanduser()),
        help="Path to local sudoku-image-solver repo.",
    )
    parser.add_argument("--image", type=str, help="Path to input image for image mode.")
    parser.add_argument("--input", type=str, help="Path to input video for video mode.")
    parser.add_argument("--solve-frame", type=int, default=0, help="Frame index to solve in video mode.")
    parser.add_argument("--video-max-frames", type=int, default=0, help="Maximum frames to process in video mode; 0 means all frames.")
    parser.add_argument(
        "--out",
        type=str,
        default="assets/demo/static_overlay.jpg",
        help="Output path for image mode.",
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index for webcam mode.")

    parser.add_argument(
        "--auto-solve",
        action="store_true",
        help="Attempt to solve automatically until solved.",
    )
    parser.add_argument(
        "--auto-solve-interval-sec",
        type=float,
        default=2.0,
        help="Seconds between auto-solve attempts.",
    )

    parser.add_argument(
        "--track-board",
        action="store_true",
        help="Use segmentation-only board tracking in webcam mode.",
    )
    parser.add_argument(
        "--track-every-n-frames",
        type=int,
        default=10,
        help="Run board-corner tracking every N frames.",
    )
    parser.add_argument(
        "--lost-after-tracking-attempts",
        type=int,
        default=5,
        help="Mark tracking lost after this many failed tracking attempts.",
    )
    parser.add_argument(
        "--smoothing-alpha",
        type=float,
        default=0.25,
        help="Legacy solve-time corner smoothing alpha.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show extra tracking debug text.",
    )

    parser.add_argument("--stabilizer-median-window", type=int, default=5)
    parser.add_argument("--stabilizer-min-quality", type=float, default=0.30)
    parser.add_argument("--stabilizer-static-alpha", type=float, default=0.12)
    parser.add_argument("--stabilizer-moving-alpha", type=float, default=0.55)
    parser.add_argument("--stabilizer-static-motion-px", type=float, default=5.0)
    parser.add_argument("--stabilizer-fast-motion-px", type=float, default=45.0)
    parser.add_argument("--stabilizer-max-jump-ratio", type=float, default=0.25)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "image":
        if not args.image:
            raise ValueError("--image is required for image mode.")
        run_image_mode(args)
        return

    if args.mode == "video":
        run_video_mode(args)
        return

    if args.mode == "webcam":
        run_webcam_mode(args)
        return

    raise ValueError(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()
