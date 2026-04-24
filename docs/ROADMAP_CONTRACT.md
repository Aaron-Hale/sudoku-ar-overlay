# sudoku-ar-overlay Roadmap Contract

## North Star

Turn the existing Sudoku image solver into a credible real-time planar AR system that detects a physical puzzle, solves it once, anchors answers to the board plane, stabilizes them across video frames, and reacquires the board after temporary tracking loss.

## Positioning

This project should be framed as:

> A lightweight planar AR overlay for Sudoku solving using a frozen ML vision pipeline, homography-based tracking, temporal smoothing, and board reacquisition.

It should not be framed as full SLAM, production mobile AR, or persistent world mapping.

## Core principle

Do not make ORB-SLAM, ARKit, ARCore, or mobile deployment a dependency for project success.

The first credible version should use:

- OpenCV camera loop
- board-plane homography
- solve-once state
- temporal smoothing
- reacquisition logic
- metrics and demo video

## Stage 0 — Repo and adapter setup

Estimated time: 0.5–1 day.

Goal:

Create a clean second repo that wraps the frozen solver from `sudoku-image-solver`.

Deliverables:

- clean package structure
- `solver_adapter.py`
- result schema
- static mock mode
- basic README

Pass condition:

A single command can run the app in mock static mode.

## Stage 1 — Static AR overlay

Estimated time: 1 day.

Goal:

Given one image and a solver result, draw:

- board border
- solved digits only in empty cells
- optional debug grid

Pass condition:

Overlay aligns correctly on representative still images.

## Stage 2 — Webcam/video loop

Estimated time: 1–2 days.

Goal:

Open a live webcam or video file and render board outline / overlay.

Pass condition:

A printed Sudoku board can be shown in the camera feed and visually outlined.

## Stage 3 — Solve-once session state

Estimated time: 1–2 days.

Goal:

Run expensive solver once, then reuse the solution while tracking/rendering each frame.

Pass condition:

The same solved board state persists until reset.

## Stage 4 — Homography-based planar tracking

Estimated time: 2–3 days.

Goal:

Project solved digits from canonical board coordinates into the live camera frame using homography.

Pass condition:

Digits remain visually attached to the board under moderate camera motion.

## Stage 5 — Temporal smoothing and reacquisition

Estimated time: 3–5 days.

Goal:

Reduce jitter, track state, and reacquire after temporary board loss.

States:

- NO_BOARD
- BOARD_DETECTED
- SOLVED_TRACKING
- TRACKING_LOST
- REACQUIRED

Pass condition:

A demo video shows look-away/look-back behavior with overlay reacquisition.

## Stage 6 — Metrics and evaluation

Estimated time: 1–2 days.

Goal:

Report useful system metrics:

- solve latency
- rendering FPS
- detection cadence
- reacquisition time
- overlay stability
- known failure modes

Pass condition:

README includes a small honest metrics table.

## Stage 7 — README and architecture polish

Estimated time: 1–2 days.

Goal:

Make the repo interview-ready.

Required README sections:

- demo
- what this project does
- architecture
- relationship to `sudoku-image-solver`
- why planar tracking instead of full SLAM
- metrics
- limitations
- future work

Pass condition:

A hiring manager can understand the project in 60 seconds.

## Stage 8 — Optional pose-estimation layer

Estimated time: 2–4 days.

Goal:

Add camera calibration and `solvePnP` pose estimation.

Deliverables:

- board pose estimate
- projected 3D axis/debug view
- `docs/pose_estimation.md`

Pass condition:

The repo shows camera-relative board pose, not just 2D image overlay.

## Stage 9 — Optional ARKit/ARCore bridge

Estimated time: 5–10+ days.

Goal:

Document or prototype how this would map to native mobile AR anchors.

This is optional and should not block publishing.

## Kill criteria

Do not continue into higher-complexity work if:

- live board detection fails badly
- overlay alignment is systematically wrong
- smoothing cannot reduce jitter enough for a readable demo
- native/mobile work starts consuming time before the core OpenCV demo is polished

## Fallbacks

Acceptable fallback options:

- recorded video mode instead of live webcam
- manual solve trigger
- manual reset
- solve once on keypress
- constrained lighting/demo environment
- same-board assumption during one session
- static image mode retained as reliable baseline

## Final publishing bar

Do not publish as finished until the repo has:

1. demo GIF or video
2. static image mode
3. webcam or video mode
4. solve-once state
5. homography overlay
6. smoothing
7. reacquisition
8. metrics
9. honest limitations
10. future path to ARKit/ARCore/SLAM
