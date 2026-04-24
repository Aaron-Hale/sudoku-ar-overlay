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
    tracking_cfg: TrackingConfig,
) -> tuple[bool, str, float]:
    """Detect board corners only, smooth them, and update session tracking state."""
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
            return False, scored.reason, timing.get("segmentation_ms", 0.0)

        smoothed = smooth_corners(
            session.smoothed_corners,
            scored.corners,
            alpha=tracking_cfg.smoothing_alpha,
        )

        session.last_corners = scored.corners
        session.smoothed_corners = smoothed
        session.last_seen_frame_idx = frame_idx
        session.tracking_quality = scored.quality

        if session.solution is not None:
            if session.status == BoardStatus.TRACKING_LOST:
                session.status = BoardStatus.REACQUIRED
            else:
                session.status = BoardStatus.SOLVED_TRACKING
        else:
            session.status = BoardStatus.BOARD_DETECTED

        return True, scored.reason, timing.get("segmentation_ms", 0.0)

    except Exception as exc:
        return False, f"track failed: {type(exc).__name__}: {exc}", 0.0


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

    frame_idx = 0
    tracking_attempts_since_seen = 0
    last_track_ms = 0.0
    last_track_reason = ""

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
            detected, reason, track_ms = update_board_tracking(
                frame=frame_for_solve,
                session=session,
                args=args,
                frame_idx=frame_idx,
                tracking_cfg=tracking_cfg,
            )
            last_track_ms = track_ms
            last_track_reason = reason

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

        # Draw board outline before solving if tracking has corners.
        if (
            session.solution is None
            and session.smoothed_corners is not None
            and session.status == BoardStatus.BOARD_DETECTED
        ):
            display = draw_board_outline(display, session.smoothed_corners)

        # Draw solved overlay if solved and currently tracked/reacquired.
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

        # Optional auto-solve. Only attempt while unsolved.
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
                f"f/space freeze={frozen} | s solve | a auto={auto_solve_enabled} | r reset | q quit"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="sudoku-ar-overlay")

    parser.add_argument(
        "--mode",
        choices=["image", "webcam"],
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
        help="Corner smoothing alpha. Higher follows motion faster; lower reduces jitter.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show extra tracking debug text.",
    )

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
