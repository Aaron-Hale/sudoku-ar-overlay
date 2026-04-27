from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

import cv2
import numpy as np

from sudoku_ar_overlay.board_state import BoardSession, BoardStatus
from sudoku_ar_overlay.board_identity import KnownBoardRegistry
from sudoku_ar_overlay.config import OverlayConfig, TrackingConfig
from sudoku_ar_overlay.flow_tracker import FlowHomographyTracker
from sudoku_ar_overlay.grid_validation import validate_sudoku_grid_candidate, warp_candidate, evaluate_sudoku_grid_fit
from sudoku_ar_overlay.grid_discovery import find_sudoku_grid_candidate
from sudoku_ar_overlay.grid_refinement import refine_sudoku_grid_corners
from sudoku_ar_overlay.reacquisition import CandidateStabilityBuffer, ReacquisitionCandidate
from sudoku_ar_overlay.overlay import draw_board_outline, render_solution_overlay
from sudoku_ar_overlay.smoothing import smooth_corners
from sudoku_ar_overlay.solver_adapter import (
    detect_board_corners_only,
    load_image_bgr,
    solve_frame,
)
from sudoku_ar_overlay.stabilizer import CornerStabilizer
from sudoku_ar_overlay.tracking import score_corners



def count_givens(givens) -> int:
    return sum(1 for row in givens for value in row if int(value) != 0)



class SolveTimeoutError(RuntimeError):
    pass


def _solve_timeout_handler(signum, frame):
    raise SolveTimeoutError("solve_frame timed out")


def solve_frame_with_timeout(frame, args: argparse.Namespace):
    timeout_sec = float(getattr(args, "solve_timeout_sec", 0.0) or 0.0)

    if timeout_sec <= 0:
        return solve_frame(
            frame,
            solver=args.solver,
            repo_root=args.repo_root,
        )

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _solve_timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_sec)

    try:
        return solve_frame(
            frame,
            solver=args.solver,
            repo_root=args.repo_root,
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


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
        result = solve_frame_with_timeout(frame, args)

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

    result = solve_frame_with_timeout(frame, args)

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







def _quad_area_px(corners) -> float:
    arr = np.asarray(corners, dtype="float32").reshape(4, 2)
    return float(abs(cv2.contourArea(arr.reshape(-1, 1, 2))))


def _quad_center_px(corners) -> np.ndarray:
    return np.asarray(corners, dtype="float32").reshape(4, 2).mean(axis=0)


def _mean_corner_jump_px(current, previous) -> float:
    if current is None or previous is None:
        return 0.0
    cur = np.asarray(current, dtype="float32").reshape(4, 2)
    prev = np.asarray(previous, dtype="float32").reshape(4, 2)
    dists = np.linalg.norm(cur - prev, axis=1)
    return float(dists.mean())


def run_video_mode(args: argparse.Namespace) -> None:
    """Process a recorded video and write an annotated output video.

    Cleaned video state machine:
    - solve once on --solve-frame
    - track with optical-flow homography while motion is plausible
    - hide overlay immediately when tracking becomes implausible
    - discover Sudoku-grid candidates using grid-first discovery, not segmentation alone
    - allow fast cached reacquisition only when the candidate appears near the last pose
    - require fresh candidate solve for far/different-pose candidates when enabled
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

    flow = FlowHomographyTracker(
        max_corners=args.flow_max_corners,
        min_points=args.flow_min_points,
        min_inlier_ratio=args.flow_min_inlier_ratio,
        ransac_reproj_threshold=args.flow_ransac_reproj_threshold,
        refresh_points_every=args.flow_refresh_points_every,
    )

    writer = None
    frame_idx = 0
    processed_frames = 0

    solved = False
    flow_ok = False
    last_error = ""
    last_reason = ""
    last_track_ms = 0.0
    last_flow_points = 0
    last_flow_inliers = 0
    last_flow_ratio = 0.0

    last_good_area_px = None
    last_good_center_px = None
    pending_candidate_corners = None
    pending_candidate_count = 0

    reacq_buffer = CandidateStabilityBuffer(
        min_frames=args.reacq_stable_min_frames,
        max_history=max(args.reacq_stable_min_frames * 3, 12),
        max_center_motion_frac=args.reacq_stable_max_center_motion_frac,
        max_area_ratio=args.reacq_stable_max_area_ratio,
        max_corner_motion_frac=args.reacq_stable_max_corner_motion_frac,
        max_fit_error_px=args.fit_max_mean_error_px,
    )

    known_boards = KnownBoardRegistry(
        max_boards=args.known_board_max_items,
        match_threshold=args.known_board_match_threshold,
        size=args.known_board_fingerprint_size,
    )

    loss_events = 0
    reacquisition_events = 0
    tracking_frames = 0
    lost_frames = 0
    discovery_solve_attempts = 0
    last_discovery_solve_frame = -1_000_000

    started = time.perf_counter()

    def remember_good_pose(corners) -> None:
        nonlocal last_good_area_px, last_good_center_px
        if corners is None:
            return
        last_good_area_px = _quad_area_px(corners)
        last_good_center_px = _quad_center_px(corners)

    def remember_known_board(frame, corners, frame_idx: int, label: str) -> None:
        """Cache solved board identity so known puzzles can reacquire without OCR."""
        if corners is None or session.givens is None or session.solution is None:
            return

        try:
            board = known_boards.add(
                frame_bgr=frame,
                corners=corners,
                givens=session.givens,
                solution=session.solution,
                frame_idx=frame_idx,
                solve_latency_ms=session.solve_latency_ms,
                label=label,
            )
            if args.debug:
                print(f"Registered known board id={board.board_id} label={board.label}")
        except Exception as exc:
            if args.debug:
                print(f"Known-board registration failed: {type(exc).__name__}: {exc}")

    def mark_lost(reason: str) -> None:
        """Hide overlay and preserve last good pose/session for possible same-board reacq."""
        nonlocal flow_ok, last_reason, loss_events
        nonlocal pending_candidate_corners, pending_candidate_count

        if session.smoothed_corners is not None:
            remember_good_pose(session.smoothed_corners)

        flow_ok = False
        last_reason = reason
        flow.reset()

        # Keep givens/solution cached, but do not render stale geometry.
        session.last_corners = None
        session.smoothed_corners = None
        session.tracking_quality = 0.0
        session.status = BoardStatus.TRACKING_LOST

        pending_candidate_corners = None
        pending_candidate_count = 0
        reacq_buffer.reset()
        loss_events += 1

    def validate_tracked_corners(corners, previous_corners, frame_shape) -> tuple[bool, str, float]:
        h, w = frame_shape[:2]
        frame_area = float(h * w)
        max_dim = float(max(h, w))

        if corners is None:
            return False, "no corners", 0.0

        area = _quad_area_px(corners)
        area_frac = area / frame_area if frame_area > 0 else 0.0

        if area_frac < args.video_min_board_area_frac:
            return False, f"board too small: area_frac={area_frac:.4f}", area

        if last_good_area_px is not None and last_good_area_px > 1:
            ratio = area / last_good_area_px
            if ratio < args.video_min_area_change_ratio or ratio > args.video_max_area_change_ratio:
                return False, f"area jump: ratio={ratio:.2f}", area

        if previous_corners is not None:
            jump = _mean_corner_jump_px(corners, previous_corners)
            if jump > max_dim * args.video_max_corner_jump_frac:
                return False, f"corner jump too large: {jump:.1f}px", area

        scored = score_corners(
            corners,
            frame_shape=frame_shape,
            previous_corners=previous_corners,
        )

        if not scored.detected or scored.corners is None:
            return False, f"corner score failed: {scored.reason}", area

        if scored.quality < args.video_min_score_quality:
            return False, f"low corner quality: {scored.quality:.2f}", area

        return True, "ok", area

    def validate_segmentation_candidate(corners, frame):
        """Validate a segmentation proposal before treating it as a Sudoku candidate."""
        scored = score_corners(
            corners,
            frame_shape=frame.shape,
            previous_corners=None,
        )

        if not scored.detected or scored.corners is None:
            return False, f"seg score failed: {scored.reason}", None

        h, w = frame.shape[:2]
        frame_area = float(h * w)
        area = _quad_area_px(scored.corners)
        area_frac = area / frame_area if frame_area > 0 else 0.0

        if area_frac < args.reacquire_min_board_area_frac:
            return False, f"seg too small: area_frac={area_frac:.4f}", None

        if area_frac > args.reacquire_max_board_area_frac:
            return False, f"seg too large: area_frac={area_frac:.4f}", None

        if scored.quality < args.reacquire_min_score_quality:
            return False, f"seg low quality: q={scored.quality:.2f}", None

        grid_result = validate_sudoku_grid_candidate(
            frame,
            scored.corners,
            min_peak=args.grid_min_peak,
            min_strong_lines=args.grid_min_strong_lines,
        )

        if not grid_result.ok:
            return False, grid_result.reason, None

        return True, f"seg candidate ok: q={scored.quality:.2f}; {grid_result.reason}", scored.corners

    def initialize_from_fresh_solve(frame, frame_idx: int, label: str) -> bool:
        nonlocal solved, flow_ok, last_error, last_reason
        nonlocal pending_candidate_corners, pending_candidate_count

        ok, last_error = solve_and_update_session(
            frame=frame,
            session=session,
            args=args,
            frame_idx=frame_idx,
            tracking_cfg=tracking_cfg,
        )

        if not ok or session.smoothed_corners is None:
            solved = False
            flow_ok = False
            session.reset()
            last_reason = f"{label}: solve failed"
            return False

        init_result = flow.initialize(frame, session.smoothed_corners)

        if init_result.ok and init_result.corners is not None:
            solved = True
            flow_ok = True
            session.smoothed_corners = init_result.corners
            session.last_corners = init_result.corners
            session.last_seen_frame_idx = frame_idx
            session.status = BoardStatus.SOLVED_TRACKING
            session.tracking_quality = 1.0
            remember_good_pose(init_result.corners)
            remember_known_board(frame, init_result.corners, frame_idx, label)
            pending_candidate_corners = None
            pending_candidate_count = 0
            last_reason = f"{label}: solved and initialized flow"
            return True

        solved = False
        flow_ok = False
        session.reset()
        pending_candidate_corners = None
        pending_candidate_count = 0
        last_reason = f"{label}: flow init failed: {init_result.reason}"
        return False

    def initialize_from_candidate_solve(frame, corners, frame_idx: int, label: str) -> bool:
        """Solve a discovered candidate crop and attach solution to original-frame corners."""
        nonlocal solved, flow_ok, last_error, last_reason, reacquisition_events
        nonlocal pending_candidate_corners, pending_candidate_count
        nonlocal discovery_solve_attempts, last_discovery_solve_frame

        try:
            candidate = warp_candidate(frame, corners, size=args.candidate_solve_size)

            pad = int(args.candidate_solve_pad)
            if pad > 0:
                candidate = cv2.copyMakeBorder(
                    candidate,
                    pad,
                    pad,
                    pad,
                    pad,
                    cv2.BORDER_CONSTANT,
                    value=(255, 255, 255),
                )

            result = solve_frame_with_timeout(candidate, args)

            session.set_solved(
                givens=result.givens,
                solution=result.solution,
                corners=corners,
                frame_idx=frame_idx,
                solve_latency_ms=result.solve_latency_ms,
            )

            init_result = flow.initialize(frame, corners)
            if init_result.ok and init_result.corners is not None:
                solved = True
                flow_ok = True
                session.smoothed_corners = init_result.corners
                session.last_corners = init_result.corners
                session.last_seen_frame_idx = frame_idx
                session.status = BoardStatus.SOLVED_TRACKING
                session.tracking_quality = 1.0
                remember_good_pose(init_result.corners)
                if args.register_discovery_solves_as_known:
                    remember_known_board(frame, init_result.corners, frame_idx, label)
                pending_candidate_corners = None
                pending_candidate_count = 0
                reacquisition_events += 1
                last_reason = f"{label}: candidate solved and flow initialized"
                return True

            solved = False
            flow_ok = False
            session.reset()
            last_reason = f"{label}: candidate solved but flow init failed: {init_result.reason}"
            return False

        except Exception as exc:
            solved = False
            flow_ok = False
            last_error = f"{label}: candidate solve failed: {type(exc).__name__}: {exc}"
            last_reason = last_error
            return False

    def maybe_reacquire_cached_solution(frame, corners, frame_idx: int, pose_reason: str, fit_reason: str) -> bool:
        """Fast path for likely same-board reacquisition."""
        nonlocal solved, flow_ok, last_reason, reacquisition_events
        nonlocal pending_candidate_corners, pending_candidate_count

        if session.givens is None or session.solution is None:
            return False

        init_result = flow.initialize(frame, corners)
        if init_result.ok and init_result.corners is not None:
            solved = True
            flow_ok = True
            session.smoothed_corners = init_result.corners
            session.last_corners = init_result.corners
            session.last_seen_frame_idx = frame_idx
            session.status = BoardStatus.REACQUIRED
            session.tracking_quality = 1.0
            remember_good_pose(init_result.corners)
            pending_candidate_corners = None
            pending_candidate_count = 0
            reacquisition_events += 1
            last_reason = f"same-pose cached reacq: {pose_reason}; {fit_reason}"
            return True

        flow_ok = False
        pending_candidate_corners = None
        pending_candidate_count = 0
        last_reason = f"same-pose cached reacq failed: {init_result.reason}"
        return False

    def reacquire_known_board(match, frame, corners, frame_idx: int, stability_reason: str) -> bool:
        """Attach a previously solved known board without running OCR again."""
        nonlocal solved, flow_ok, last_reason, reacquisition_events
        nonlocal pending_candidate_corners, pending_candidate_count

        known = match.known_board
        if known is None:
            return False

        session.set_solved(
            givens=known.givens,
            solution=known.solution,
            corners=corners,
            frame_idx=frame_idx,
            solve_latency_ms=known.solve_latency_ms,
        )

        init_result = flow.initialize(frame, corners)
        if init_result.ok and init_result.corners is not None:
            solved = True
            flow_ok = True
            session.smoothed_corners = init_result.corners
            session.last_corners = init_result.corners
            session.last_seen_frame_idx = frame_idx
            session.status = BoardStatus.REACQUIRED
            session.tracking_quality = 1.0
            remember_good_pose(init_result.corners)
            pending_candidate_corners = None
            pending_candidate_count = 0
            reacquisition_events += 1
            last_reason = f"known-board reacq: {match.reason}; {stability_reason}"
            return True

        flow_ok = False
        last_reason = f"known-board reacq flow init failed: {init_result.reason}; {match.reason}"
        return False

    def discover_candidate_and_maybe_solve(frame, frame_idx: int) -> None:
        """Grid-first discovery with refinement + stability gating.

        This intentionally does not attach or solve on the first candidate frame.
        Returned boards often enter from the side while moving, which can produce
        rough/skewed corners. We refine the grid and require a short stable
        candidate window before cached reacquisition or fresh solving.
        """
        nonlocal flow_ok, last_reason, last_track_ms
        nonlocal pending_candidate_corners, pending_candidate_count
        nonlocal discovery_solve_attempts, last_discovery_solve_frame

        try:
            t0 = time.perf_counter()

            # 1) Prefer grid-first discovery. Segmentation remains a fallback only.
            grid_candidate = find_sudoku_grid_candidate(
                frame,
                min_area_frac=args.reacquire_min_board_area_frac,
            )

            if grid_candidate.ok and grid_candidate.corners is not None:
                cand_ok = True
                cand_reason = grid_candidate.reason
                cand_corners = grid_candidate.corners
                cand_score = grid_candidate.score
                last_track_ms = (time.perf_counter() - t0) * 1000.0
            else:
                corners, timing = detect_board_corners_only(
                    frame,
                    repo_root=args.repo_root,
                )
                last_track_ms = timing.get(
                    "segmentation_ms",
                    (time.perf_counter() - t0) * 1000.0,
                )
                cand_ok, cand_reason, cand_corners = validate_segmentation_candidate(corners, frame)
                cand_score = 0.0

            if not cand_ok or cand_corners is None:
                pending_candidate_corners = None
                pending_candidate_count = 0
                reacq_buffer.reset()
                flow_ok = False
                last_reason = f"discover rejected: {cand_reason}"
                return

            # 2) Refine rough discovery corners to printed-grid corners.
            refined = refine_sudoku_grid_corners(
                frame,
                cand_corners,
                min_found_lines=args.refine_min_found_lines,
                max_mean_error_px=args.refine_max_mean_error_px,
            )

            if not refined.ok or refined.corners is None:
                pending_candidate_corners = None
                pending_candidate_count = 0
                reacq_buffer.reset()
                flow_ok = False
                last_reason = f"discover refine rejected: {refined.reason}"
                return

            pending_candidate_corners = refined.corners.copy()
            pending_candidate_count += 1

            # 3) Push refined candidate into stability buffer. No rendering/solving yet.
            stability = reacq_buffer.push(
                ReacquisitionCandidate(
                    frame_idx=frame_idx,
                    corners=refined.corners,
                    frame_shape=frame.shape,
                    fit_error_px=refined.mean_error_px,
                    score=float(cand_score),
                    reason=refined.reason,
                )
            )

            if not stability.stable or stability.candidate is None:
                flow_ok = False
                last_reason = (
                    f"discover candidate waiting: {stability.reason}; "
                    f"{refined.reason}; {cand_reason}"
                )
                return

            stable_corners = stability.candidate.corners

            # 4) Prefer known-board identity over fresh OCR.
            # This prevents a previously solved puzzle from being re-solved from a worse late-frame crop.
            known_match = known_boards.match(frame, stable_corners)
            if known_match.ok and reacquire_known_board(
                known_match,
                frame,
                stable_corners,
                frame_idx,
                stability.reason,
            ):
                reacq_buffer.reset()
                return

            # 5) Decide whether this is plausibly the same board location.
            same_pose_likely = False
            pose_reason = "no last pose"
            if last_good_center_px is not None and last_good_area_px is not None and last_good_area_px > 1:
                cand_center = _quad_center_px(stable_corners)
                cand_area = _quad_area_px(stable_corners)
                frame_diag = float((frame.shape[0] ** 2 + frame.shape[1] ** 2) ** 0.5)
                center_frac = float(np.linalg.norm(cand_center - last_good_center_px) / max(frame_diag, 1.0))
                area_ratio = cand_area / last_good_area_px
                same_pose_likely = (
                    center_frac <= args.same_pose_center_frac
                    and args.same_pose_min_area_ratio <= area_ratio <= args.same_pose_max_area_ratio
                )
                pose_reason = f"center_frac={center_frac:.2f} area_ratio={area_ratio:.2f}"

            # 5) Fast path: same-pose known board gets cached reacq after stability gate.
            if same_pose_likely and maybe_reacquire_cached_solution(
                frame,
                stable_corners,
                frame_idx,
                pose_reason,
                stability.reason,
            ):
                reacq_buffer.reset()
                return

            # 6) Different/far pose: require fresh candidate solve before rendering.
            if not args.enable_discovery_solve:
                flow_ok = False
                last_reason = (
                    f"stable new/different pose candidate; fresh solve disabled: "
                    f"{pose_reason}; {stability.reason}"
                )
                return

            frames_since_attempt = frame_idx - last_discovery_solve_frame
            if discovery_solve_attempts >= args.discover_max_solve_attempts:
                flow_ok = False
                last_reason = (
                    "stable candidate, but max fresh-solve attempts reached: "
                    f"{discovery_solve_attempts}; {pose_reason}; {stability.reason}"
                )
                return

            if frames_since_attempt < args.discover_solve_cooldown_frames:
                flow_ok = False
                last_reason = (
                    "stable candidate, but solve cooldown active: "
                    f"{frames_since_attempt}/{args.discover_solve_cooldown_frames} frames; "
                    f"{pose_reason}; {stability.reason}"
                )
                return

            discovery_solve_attempts += 1
            last_discovery_solve_frame = frame_idx
            solved_candidate = initialize_from_candidate_solve(
                frame=frame,
                corners=stable_corners,
                frame_idx=frame_idx,
                label="stable grid discovery",
            )
            if solved_candidate:
                reacq_buffer.reset()

        except Exception as exc:
            pending_candidate_corners = None
            pending_candidate_count = 0
            reacq_buffer.reset()
            flow_ok = False
            last_reason = f"discover failed: {type(exc).__name__}: {exc}"


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

        if frame_idx == args.solve_frame and not solved:
            initialize_from_fresh_solve(frame=frame, frame_idx=frame_idx, label="initial solve")

        elif (
            (not solved or session.status == BoardStatus.TRACKING_LOST)
            and frame_idx > args.solve_frame
            and frame_idx % max(args.discover_every_n_frames, 1) == 0
        ):
            discover_candidate_and_maybe_solve(frame, frame_idx)

        elif solved and flow.initialized and session.status != BoardStatus.TRACKING_LOST:
            previous_corners = None if session.smoothed_corners is None else session.smoothed_corners.copy()

            t0 = time.perf_counter()
            flow_result = flow.update(frame)
            last_track_ms = (time.perf_counter() - t0) * 1000.0

            last_flow_points = flow_result.num_points
            last_flow_inliers = flow_result.num_inliers
            last_flow_ratio = flow_result.inlier_ratio

            if flow_result.ok and flow_result.corners is not None:
                gate_ok, gate_reason, area = validate_tracked_corners(
                    flow_result.corners,
                    previous_corners,
                    frame.shape,
                )

                if gate_ok:
                    flow_ok = True
                    session.smoothed_corners = flow_result.corners
                    session.last_corners = flow_result.corners
                    session.last_seen_frame_idx = frame_idx
                    session.tracking_quality = max(0.0, min(1.0, flow_result.inlier_ratio))
                    session.status = BoardStatus.SOLVED_TRACKING
                    remember_good_pose(flow_result.corners)
                    last_reason = flow_result.reason
                    tracking_frames += 1
                else:
                    mark_lost(f"flow rejected: {gate_reason}")
                    lost_frames += 1
            else:
                mark_lost(f"flow failed: {flow_result.reason}")
                lost_frames += 1

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
                    f"flow_ms={last_track_ms:.1f} q={session.tracking_quality:.2f}"
                ),
                (
                    f"flow={flow_ok} pts={last_flow_points} "
                    f"inliers={last_flow_inliers} ratio={last_flow_ratio:.2f}"
                ),
                f"loss_events={loss_events} reacq_events={reacquisition_events}",
            ]

            if last_reason:
                lines.append(f"tracking: {last_reason[:95]}")
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

    tracking_uptime = (tracking_frames / processed_frames) if processed_frames else 0.0

    print(f"Wrote output video: {out_path}")
    print(f"Processed frames: {processed_frames}")
    print(f"Wall time: {elapsed:.2f} sec")
    if elapsed > 0:
        print(f"Processing FPS: {processed_frames / elapsed:.2f}")
    print(f"Final state: {session.status.value}")
    print(f"Solve latency ms: {session.solve_latency_ms:.2f}")
    print(f"Tracking uptime: {tracking_uptime:.3f}")
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

    parser.add_argument("--flow-max-corners", type=int, default=600)
    parser.add_argument("--flow-min-points", type=int, default=18)
    parser.add_argument("--flow-min-inlier-ratio", type=float, default=0.45)
    parser.add_argument("--flow-ransac-reproj-threshold", type=float, default=4.0)
    parser.add_argument("--flow-refresh-points-every", type=int, default=5)
    parser.add_argument("--video-min-board-area-frac", type=float, default=0.025)
    parser.add_argument("--video-min-area-change-ratio", type=float, default=0.45)
    parser.add_argument("--video-max-area-change-ratio", type=float, default=2.20)
    parser.add_argument("--video-max-corner-jump-frac", type=float, default=0.35)
    parser.add_argument("--video-min-score-quality", type=float, default=0.25)
    parser.add_argument(
        "--reacquire-every-n-frames",
        type=int,
        default=15,
        help="When tracking is lost in video mode, try segmentation reacquisition every N frames.",
    )
    parser.add_argument(
        "--discover-every-n-frames",
        type=int,
        default=10,
        help="When no board is being tracked, try fresh board discovery every N frames.",
    )
    parser.add_argument(
        "--discover-confirm-frames",
        type=int,
        default=2,
        help="Require this many stable discovery candidates before running a fresh solve.",
    )
    parser.add_argument(
        "--enable-discovery-solve",
        action="store_true",
        help="Allow discovery mode to run a fresh full solve after confirmed candidate detections.",
    )
    parser.add_argument(
        "--solve-timeout-sec",
        type=float,
        default=2.5,
        help="Max seconds allowed for each solve attempt. Use 0 to disable timeout.",
    )
    parser.add_argument(
        "--candidate-solve-size",
        type=int,
        default=900,
        help="Canonical warp size used when solving a discovered grid candidate.",
    )
    parser.add_argument(
        "--candidate-solve-pad",
        type=int,
        default=80,
        help="White padding around discovered grid candidate before solving.",
    )
    parser.add_argument("--same-pose-center-frac", type=float, default=0.35)
    parser.add_argument("--same-pose-min-area-ratio", type=float, default=0.45)
    parser.add_argument("--same-pose-max-area-ratio", type=float, default=2.25)
    parser.add_argument("--fit-max-mean-error-px", type=float, default=14.0)
    parser.add_argument("--fit-min-found-lines", type=int, default=7)
    parser.add_argument("--refine-max-mean-error-px", type=float, default=18.0)
    parser.add_argument("--refine-min-found-lines", type=int, default=7)
    parser.add_argument("--reacq-stable-min-frames", type=int, default=4)
    parser.add_argument("--reacq-stable-max-center-motion-frac", type=float, default=0.025)
    parser.add_argument("--reacq-stable-max-area-ratio", type=float, default=1.18)
    parser.add_argument("--reacq-stable-max-corner-motion-frac", type=float, default=0.035)
    parser.add_argument("--known-board-match-threshold", type=float, default=0.78)
    parser.add_argument("--known-board-fingerprint-size", type=int, default=450)
    parser.add_argument("--known-board-max-items", type=int, default=8)
    parser.add_argument(
        "--register-discovery-solves-as-known",
        action="store_true",
        help="If set, successful fresh discovery solves are added to the known-board registry. Default off to avoid caching wrong single-frame solves.",
    )
    parser.add_argument(
        "--discover-solve-cooldown-frames",
        type=int,
        default=90,
        help="Minimum frames between fresh solve attempts during discovery.",
    )
    parser.add_argument(
        "--discover-max-solve-attempts",
        type=int,
        default=3,
        help="Maximum fresh solve attempts during discovery for one video.",
    )
    parser.add_argument(
        "--reacquire-with-solve",
        action="store_true",
        default=False,
        help="After tracking loss, require a fresh solve before reattaching any overlay.",
    )
    parser.add_argument(
        "--reacquire-min-givens",
        type=int,
        default=10,
        help="Reject reacquisition solves with too few detected givens.",
    )
    parser.add_argument(
        "--reacquire-max-givens",
        type=int,
        default=55,
        help="Reject reacquisition solves with too many detected givens.",
    )
    parser.add_argument(
        "--reacquire-confirm-frames",
        type=int,
        default=2,
        help="Require this many consecutive credible detections before reacquiring.",
    )
    parser.add_argument("--reacquire-min-score-quality", type=float, default=0.45)
    parser.add_argument("--reacquire-min-board-area-frac", type=float, default=0.025)
    parser.add_argument(
        "--grid-min-peak",
        type=float,
        default=0.025,
        help="Minimum grid-line peak contrast required for discovery/reacquisition candidates.",
    )
    parser.add_argument(
        "--grid-min-strong-lines",
        type=int,
        default=7,
        help="Minimum expected vertical/horizontal Sudoku grid lines required.",
    )
    parser.add_argument("--reacquire-max-board-area-frac", type=float, default=0.80)
    parser.add_argument("--reacquire-max-candidate-shift-frac", type=float, default=0.18)

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
