# `sudoku-ar-overlay` Roadmap Contract

## Purpose

This document is the working roadmap and execution contract for `sudoku-ar-overlay`, a second portfolio repository that extends the existing `sudoku-image-solver` project from a static ML/CV inference pipeline into a credible AR-style live overlay system.

The goal is not to build a production-grade mobile AR/SLAM platform. The goal is to build a polished, honest, high-probability portfolio project that demonstrates practical familiarity with augmented reality concepts: camera feed processing, planar tracking, homography-based rendering, temporal smoothing, session state, reacquisition after tracking loss, and measured real-time performance.

## North Star

> Turn the existing Sudoku image solver into a real-time planar AR overlay system that detects a physical Sudoku puzzle, solves it once, anchors answers to the board plane, stabilizes them across video frames, and reacquires the board after temporary tracking loss.

## Repository Name

```text
sudoku-ar-overlay
```

## Positioning

This project should be framed as:

> A real-time planar AR overlay for Sudoku solving using a frozen ML vision pipeline, homography-based board tracking, temporal smoothing, and board reacquisition.

Do **not** frame this as:

- a full SLAM system,
- a production mobile AR app,
- an ARKit/ARCore replacement,
- a persistent world-mapping system,
- or a generic OpenCV webcam demo.

The intended framing is:

> The first repo solves the perception problem. This second repo turns that model into an interactive AR-style system.

## Target Audience

This project should be credible for roles involving:

- applied machine learning,
- computer vision,
- robotics-adjacent perception,
- defense technology,
- real-time inference systems,
- productized ML demos,
- and applied science / MLE portfolio review.

The project should show judgment: use the right level of geometric computer vision for a planar object rather than overcomplicating the work with full SLAM before the core system is shipped.

---

# Scope Definition

## In Scope

The core project should include:

1. Static image overlay.
2. Live webcam or recorded-video mode.
3. Integration with the frozen Sudoku solver.
4. Solve-once session state.
5. Homography-based planar overlay.
6. Temporal smoothing.
7. Board tracking state machine.
8. Look-away / look-back reacquisition.
9. Runtime metrics: FPS, solve latency, tracking quality.
10. Demo video or GIF.
11. Clear README and architecture documentation.
12. Honest limitations and future work section.

## Optional Stretch Scope

The stretch path may include:

1. Camera calibration helper.
2. `solvePnP` pose estimation.
3. 3D axis / board-normal debug visualization.
4. ARKit/ARCore design document.
5. Native mobile prototype.

## Out of Scope for Core Success

The core project does **not** require:

- ORB-SLAM integration,
- full visual-inertial odometry,
- persistent world maps,
- cloud anchors,
- multi-user AR,
- mobile-native deployment,
- occlusion handling,
- depth estimation,
- arbitrary 3D object tracking,
- or production-grade AR persistence.

---

# Success Criteria

The project is successful when it can demonstrate the following:

1. A physical Sudoku board appears in a live camera or recorded-video feed.
2. The board is detected and outlined.
3. The puzzle is solved once.
4. Only the originally empty cells receive overlaid solution digits.
5. The digits stay visually attached to the board plane during moderate camera movement.
6. The overlay is smoothed enough that it does not visibly jitter in a distracting way.
7. If the camera looks away, the overlay disappears.
8. When the board re-enters view, the solved overlay is reacquired and redrawn.
9. The repo reports latency, FPS, and known failure modes.
10. The README clearly explains why planar tracking was chosen over full SLAM.

A native ARKit/ARCore implementation is **not required** for the project to be considered successful.

---

# Recommended Timeline

The core project should take approximately **10–15 working days**.

The stretch version with pose estimation and additional AR design polish may take **15–25 working days**.

| Phase | Estimated Time | Outcome |
|---|---:|---|
| 0. Repo + adapter setup | 0.5–1 day | Clean second repo that can call the frozen solver |
| 1. Static AR overlay | 1 day | Single-image overlay works end-to-end |
| 2. Webcam/video loop | 1–2 days | Live board detection and overlay foundation |
| 3. Solve-once session state | 1–2 days | Stable solved board state, no re-solving every frame |
| 4. Homography-based planar tracking | 2–3 days | Digits stay attached to board under camera motion |
| 5. Temporal smoothing + reacquisition | 3–5 days | AR-like behavior; handles look-away/look-back |
| 6. Metrics + demo artifacts | 1–2 days | FPS, latency, tracking quality, demo GIF/video |
| 7. README + architecture polish | 1–2 days | Interview-ready repo |
| 8. Optional pose-estimation layer | 2–4 days | `solvePnP`, board pose, 3D axis/debug view |
| 9. Optional ARKit/ARCore bridge | 5–10+ days | Design doc or lightweight mobile prototype |

---

# Phase 0 — Repo Setup and Solver Adapter

## Estimated Time

0.5–1 day

## Risk

Low

## Portfolio Value

Medium

## Goal

Create a clean second repository that focuses on AR-style tracking and overlay, while using the existing Sudoku model as a frozen inference dependency.

The new repo should not become another training or notebook-heavy ML repo. It should be an application/integration repo.

## Recommended Repository Structure

```text
sudoku-ar-overlay/
  README.md
  pyproject.toml
  app.py
  src/
    sudoku_ar_overlay/
      __init__.py
      solver_adapter.py
      camera.py
      board_state.py
      overlay.py
      tracking.py
      smoothing.py
      metrics.py
      config.py
  docs/
    architecture.md
    tracking_notes.md
    pose_estimation.md
    mobile_ar_design.md
  assets/
    demo/
    images/
```

## Solver Adapter Contract

Create a single clean adapter function:

```python
result = solve_sudoku_image(frame_bgr)
```

The return object should include:

```python
{
    "status": "solved",
    "corners": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
    "givens": [[...]],
    "solution": [[...]],
    "confidence": {
        "board": 0.98,
        "occupancy_mean": 0.94,
        "digit_mean": 0.91
    },
    "latency_ms": {
        "total": 235,
        "segmentation": 40,
        "ocr": 180,
        "solve": 2
    }
}
```

The exact confidence fields can evolve, but the adapter must provide:

- board corners,
- givens,
- solution,
- status,
- and latency.

## Deliverables

Command-line smoke test:

```bash
python -m sudoku_ar_overlay.solver_adapter --image path/to/test.jpg
```

Expected result:

- prints solved grid,
- prints detected corners,
- prints latency,
- optionally writes a debug image.

## Pass Condition

The AR repo can call the frozen solver on a static image and receive the data needed for overlay rendering.

## Kill Criteria

None. If importing from the original repo becomes cumbersome, copy only the minimum frozen inference code into the AR repo and document the source.

---

# Phase 1 — Static AR Overlay

## Estimated Time

1 day

## Risk

Low

## Portfolio Value

Medium-high

## Goal

Given one image, render the solved digits onto the original board image in the correct empty cells.

## Why This Phase Matters

Static overlay isolates the geometry and rendering problem before live video adds additional failure modes.

This phase validates:

- corner ordering,
- board coordinate system,
- cell-center projection,
- font sizing,
- alpha blending,
- givens mask,
- and visual style.

## Coordinate System

Use a canonical square board coordinate system:

```text
top-left     = (0, 0)
top-right    = (900, 0)
bottom-right = (900, 900)
bottom-left  = (0, 900)
```

Each cell center is:

```python
cx = (col + 0.5) * 100
cy = (row + 0.5) * 100
```

## Rendering Rule

Only draw digits where the original puzzle had an empty cell.

```python
if givens[row][col] == 0:
    draw(solution[row][col])
```

## Deliverables

Static image command:

```bash
python app.py --mode image --image examples/board.jpg --out assets/demo/static_overlay.jpg
```

Output:

- original image with board outline,
- solved digits in empty cells,
- optional debug image with projected grid points.

## Pass Condition

Overlay alignment looks correct on at least 5 representative images.

## Kill Criteria

If static overlay alignment is poor, do not move to video. Fix:

- corner order,
- homography direction,
- cell-center calculation,
- board size assumptions,
- or original solver corner quality.

---

# Phase 2 — Webcam / Recorded-Video Loop

## Estimated Time

1–2 days

## Risk

Low-to-medium

## Portfolio Value

High

## Goal

Create a live application loop that reads frames from a webcam or video file and displays the board outline / overlay.

## Initial Controls

```text
q     quit
s     solve current frame
r     reset session
d     toggle debug view
space pause/resume
```

## Modes

Webcam mode:

```bash
python app.py --mode webcam --camera 0
```

Recorded-video mode:

```bash
python app.py --mode video --input assets/demo/raw_demo.mp4
```

Recorded-video mode is important because it makes the demo more reproducible for GitHub reviewers.

## First Implementation

Start simple:

1. Display camera frame.
2. Run board detection every N frames.
3. Draw board outline.
4. Press `s` to solve current frame.
5. Overlay solution after solve.

Do not require full-frame-rate ML inference.

## Pass Condition

The system can detect and outline a printed Sudoku board from a webcam or recorded video.

## Kill Criteria

If full inference is too slow, switch immediately to:

- solving on keypress,
- detecting every 5–10 frames,
- rendering every frame,
- and tracking/smoothing between detections.

Do not waste time trying to run the full ML pipeline at camera FPS if that hurts demo quality.

---

# Phase 3 — Solve-Once Session State

## Estimated Time

1–2 days

## Risk

Low

## Portfolio Value

High

## Goal

Once a board is solved, freeze the solved puzzle and keep rendering the same solution as the board moves.

The system should not repeatedly OCR and solve the board every frame.

## Board Session Object

Implement a state object similar to:

```python
@dataclass
class BoardSession:
    status: Literal[
        "empty",
        "detecting",
        "solved_tracking",
        "tracking_lost",
        "reacquired",
    ]
    givens: list[list[int]] | None
    solution: list[list[int]] | None
    missing_mask: list[list[bool]] | None
    last_corners: np.ndarray | None
    smoothed_corners: np.ndarray | None
    last_seen_frame_idx: int
    solved_at_frame_idx: int
    solve_latency_ms: float
    tracking_quality: float
```

## Why This Matters

This is one of the main engineering signals in the project.

The repo should show that expensive inference is decoupled from real-time rendering:

- Solve once.
- Track/render many times.
- Reset only when needed.

## Deliverables

The application should show clear states:

```text
state: DETECTING
state: SOLVED_TRACKING
state: TRACKING_LOST
state: REACQUIRED
```

## Pass Condition

After solving, the same solution remains active without re-running OCR every frame.

## Kill Criteria

None. This phase is required and should be straightforward.

---

# Phase 4 — Homography-Based Planar Tracking

## Estimated Time

2–3 days

## Risk

Medium

## Portfolio Value

Very high

## Goal

Use homography to anchor the solved digits to the Sudoku board plane.

The board is a flat object, so planar tracking is the correct first-order AR abstraction.

## Implementation

Canonical board corners:

```python
src = np.float32([
    [0, 0],
    [900, 0],
    [900, 900],
    [0, 900],
])
```

Detected frame corners:

```python
dst = np.float32([
    top_left,
    top_right,
    bottom_right,
    bottom_left,
])
```

Homography:

```python
H, _ = cv2.findHomography(src, dst)
```

Project a cell center:

```python
pt_board = np.array([[[cx, cy]]], dtype=np.float32)
pt_img = cv2.perspectiveTransform(pt_board, H)
```

## Preferred Rendering Method

Render digits onto a transparent 900x900 canonical board canvas, then warp that canvas into the camera frame.

Steps:

1. Create transparent overlay canvas in board coordinates.
2. Draw only solved missing digits onto that canvas.
3. Warp canvas into frame using `cv2.warpPerspective`.
4. Alpha-blend warped overlay with the live frame.

This usually looks more stable and more AR-like than drawing each digit directly into the camera frame.

## Deliverables

Files:

```text
src/sudoku_ar_overlay/overlay.py
src/sudoku_ar_overlay/tracking.py
```

Debug views:

- detected corners,
- canonical overlay canvas,
- warped overlay,
- final blended frame.

## Pass Condition

When the camera moves moderately, the answer digits remain visually attached to the corresponding Sudoku cells.

## Kill Criteria

If jitter is visible but alignment is basically correct, continue to Phase 5.

If alignment is systematically wrong, fix:

- corner order,
- homography direction,
- canonical board scaling,
- or cell-center math.

---

# Phase 5 — Temporal Smoothing and Reacquisition

## Estimated Time

3–5 days

## Risk

Medium

## Portfolio Value

Very high

## Goal

Make the system feel like a real AR-style experience by reducing jitter and handling temporary tracking loss.

## Corner Smoothing

Start with exponential moving average smoothing:

```python
smoothed_corners = alpha * detected_corners + (1 - alpha) * previous_smoothed_corners
```

Initial parameter:

```python
alpha = 0.25
```

Tune from there.

## Tracking Quality Score

Create a lightweight tracking quality score using heuristics such as:

- board detection confidence,
- corner movement from previous frame,
- board area stability,
- aspect ratio stability,
- whether the projected board remains inside image bounds,
- homography sanity checks.

Example checks:

```text
- board area should not change by 3x frame-to-frame
- corner order should remain clockwise
- projected grid should remain mostly inside the frame
- aspect ratio should remain plausible
```

## State Machine

Use explicit states:

```text
NO_BOARD
BOARD_DETECTED
SOLVED_TRACKING
TRACKING_LOST
REACQUIRED
```

Behavior:

```text
NO_BOARD          -> no overlay
BOARD_DETECTED    -> show outline
SOLVED_TRACKING   -> show solved digits
TRACKING_LOST     -> keep solved state, hide overlay
REACQUIRED        -> reattach solution to newly detected board
```

## Reacquisition Logic

Minimum viable reacquisition:

1. If board is not detected for N frames, set state to `TRACKING_LOST`.
2. Keep `solution` and `missing_mask` in memory.
3. When a board is detected again, assume same board during the current session.
4. Reuse solution and redraw overlay.
5. User can press `r` to reset for a new board.

Better reacquisition:

1. Compute a board fingerprint from the givens.
2. Compare newly detected givens to cached givens.
3. If similarity is high, reacquire the same board.
4. If not, ask the user to solve/reset.

Possible board fingerprint:

```text
- filled-cell positions
- detected digit values
- givens hash
- count of matching filled cells
```

## Deliverables

Live debug panel:

```text
state: SOLVED_TRACKING
fps: 21.4
tracking_quality: 0.87
solve_latency: 238 ms
frames_since_seen: 0
```

Demo sequence:

1. Board appears.
2. Solve overlay appears.
3. Camera moves.
4. Overlay stays attached.
5. Camera looks away.
6. Camera returns.
7. Overlay reappears.

## Pass Condition

A 20–30 second video demonstrates stable overlay and successful look-away/look-back reacquisition.

## Kill Criteria

If board fingerprinting is too time-consuming, simplify to session-level reacquisition and document the limitation.

Do not allow fingerprinting to block the core demo.

---

# Phase 6 — Metrics and Evaluation

## Estimated Time

1–2 days

## Risk

Low

## Portfolio Value

High

## Goal

Add enough measurement that the project looks engineered rather than hacked together.

## Metrics to Report

| Metric | Target | Notes |
|---|---:|---|
| Solve latency | <300 ms preferred | Use frozen solver latency if available |
| Render FPS after solve | >20 FPS preferred | Measures live overlay experience |
| Detection cadence | Configurable | Example: every 5 frames |
| Reacquisition time | <1 sec preferred | Measured from demo/video logs |
| Tracking quality | Heuristic score | Useful for debug and docs |
| Overlay jitter | Optional pixel metric | Useful credibility booster |

## Optional Overlay Stability Metric

For a mostly stationary board, track projected cell centers over time.

Report:

```text
mean projected cell-center movement in pixels
p95 projected cell-center movement in pixels
```

This does not need to be a formal AR benchmark. It just needs to show that stability was measured.

## Deliverables

```text
docs/metrics.md
assets/demo/demo.mp4
assets/demo/demo.gif
assets/demo/debug_view.jpg
```

## Pass Condition

The README can honestly say:

> After the puzzle is solved, rendering runs at interactive frame rates and the overlay remains anchored to the detected board plane under moderate camera movement.

## Kill Criteria

None. If a metric is weak, report it honestly and explain the limitation.

---

# Phase 7 — README and Architecture Polish

## Estimated Time

1–2 days

## Risk

Low

## Portfolio Value

Very high

## Goal

Turn the working project into an interview-ready portfolio asset.

## README Structure

```text
# sudoku-ar-overlay

## Demo

GIF/video first.

## What This Project Does

Short explanation of the live AR-style overlay.

## Why This Is an AR Problem

Planar board detection, pose/homography, overlay anchoring, tracking state.

## Architecture

Camera frame -> board detection -> solve once -> board session state -> homography tracking -> overlay renderer.

## Relationship to sudoku-image-solver

Frozen model dependency and separation of concerns.

## Core Technical Choices

- Homography for planar overlay
- Solve once, render many
- Temporal smoothing
- Reacquisition state machine
- Optional pose estimation

## Metrics

Latency, FPS, reacquisition, tracking quality.

## Limitations

No full SLAM.
No persistent world map.
Assumes one board at a time.
Works best with printed boards and reasonable lighting.

## Future Work

ARKit/ARCore anchor version.
ORB-SLAM comparison.
Mobile deployment.
```

## Required Section: Why Planar Tracking Instead of Full SLAM?

Include a section with language similar to:

> This project intentionally uses planar tracking because the target object is a flat Sudoku board. Full SLAM is better suited for persistent localization in broader unknown 3D environments. For this use case, homography-based board tracking gives a better reliability-to-complexity ratio while still demonstrating core AR concepts: pose, anchoring, temporal stability, and reacquisition.

## Pass Condition

A hiring manager can understand the project, demo, and technical choices in 60 seconds.

## Kill Criteria

None. Documentation polish is required before calling the repo finished.

---

# Phase 8 — Optional Pose-Estimation Credibility Layer

## Estimated Time

2–4 days

## Risk

Medium

## Portfolio Value

High

## Required for Success?

No. This is optional but valuable if Phases 0–7 are already stable.

## Goal

Add camera-relative board pose estimation using `solvePnP`.

This moves the project from pure 2D overlay into camera-space pose reasoning.

## Implementation

Define board points in physical units:

```python
board_width_mm = 180
cell_size_mm = board_width_mm / 9
```

Object points:

```python
object_points = np.float32([
    [0, 0, 0],
    [180, 0, 0],
    [180, 180, 0],
    [0, 180, 0],
])
```

Image points:

```python
image_points = detected_corners
```

Pose estimate:

```python
success, rvec, tvec = cv2.solvePnP(
    object_points,
    image_points,
    camera_matrix,
    dist_coeffs,
)
```

## Camera Calibration

Preferred:

- Add a simple chessboard calibration script.

Acceptable for demo:

- Use approximate intrinsics and document that pose is approximate.

Do not allow calibration to derail the project.

## Visual Debug Output

Draw:

- board normal,
- XYZ mini axes,
- pose values,
- optional camera-to-board distance estimate.

## Deliverables

```text
src/sudoku_ar_overlay/pose.py
scripts/calibrate_camera.py
docs/pose_estimation.md
```

## Pass Condition

Debug view shows a stable pose estimate or projected 3D axis on the board.

## Kill Criteria

If camera calibration becomes a time sink, use approximate intrinsics and label this clearly as demo mode.

---

# Phase 9 — Optional ARKit / ARCore Bridge

## Estimated Time

5–10+ days

## Risk

Medium-high

## Portfolio Value

High if completed, but not required

## Recommendation

Do this only after the OpenCV planar AR repo is already successful.

## Goal

Document or prototype how the system would map to a native AR stack.

The architecture would be:

```text
ML/CV Sudoku detector -> board plane estimate -> AR anchor -> render solved digits on anchor
```

## Minimum Deliverable

Create:

```text
docs/mobile_ar_design.md
```

Include:

- what the Sudoku model owns,
- what ARKit/ARCore owns,
- how the board plane maps to an anchor,
- how solved digits map to 2D/3D text on the plane,
- expected failure modes,
- and why this was left as future work.

## Optional Native Prototype

If implemented later:

- iOS + Swift + ARKit is the likely path if developing on Mac.
- Keep the solver path simple.
- Do not try to train or optimize models inside the mobile app first.
- The native prototype should prove anchoring/rendering, not redo the entire solver.

## Pass Condition

The repo contains a credible design path from the planar OpenCV implementation to native mobile AR.

## Kill Criteria

If native app setup starts consuming multiple days before the core repo is polished, defer it.

---

# Engineering Guardrails

## Do Not Overbuild

Do not start with:

- ORB-SLAM,
- native mobile deployment,
- cloud anchors,
- depth estimation,
- full 3D world persistence,
- or multi-board tracking.

## Use a Demo-Friendly Environment

It is acceptable to constrain the first demo:

- printed puzzle,
- reasonable lighting,
- one board at a time,
- camera 1–3 feet away,
- board mostly visible,
- reset button for new board.

A constrained demo is better than an ambitious unfinished repo.

## Prefer Shipping Over Purity

If a sophisticated approach blocks progress, use a simpler one and document the tradeoff.

Examples:

- Use keypress solve before automatic solve.
- Use session-level reacquisition before fingerprint matching.
- Use approximate camera intrinsics before full calibration.
- Use recorded video mode before fully robust webcam mode.

---

# Failure Modes to Document

The README should honestly list likely failure modes:

- poor lighting,
- motion blur,
- severe camera angle,
- partial board occlusion,
- handwritten digits if not supported,
- unusual Sudoku board designs,
- bad segmentation corners,
- cell misalignment from border artifacts,
- tracking loss during fast camera movement,
- wrong board reacquisition if multiple boards are present.

Honest limitations increase credibility.

---

# Interview Pitch

## Defense-Tech / Robotics-Adjacent Pitch

> I built a real-time AR-style Sudoku overlay to extend a vision model into an interactive perception system. The first repo handles board detection and digit inference. This repo handles the live camera loop, board-plane tracking, homography-based rendering, temporal smoothing, and reacquisition after tracking loss. I intentionally used planar tracking rather than full SLAM because the target is a flat board, but I documented how the same architecture would map to ARKit/ARCore anchors or a SLAM-backed tracker.

## Applied AI / MLE Pitch

> The interesting part was turning a model into a product-like system. I decoupled expensive inference from real-time rendering, used session state to avoid re-solving every frame, added tracking quality checks, and measured latency/FPS so the app behaved predictably.

## Applied Science Pitch

> This was a full-stack applied ML project: model packaging, inference adapter, real-time video loop, geometry-based post-processing, state management, tracking metrics, and failure-mode documentation.

---

# Final Build Order

Execute in this order:

1. Static overlay.
2. Live webcam/video overlay.
3. Solve-once session state.
4. Homography tracking.
5. Temporal smoothing.
6. Reacquisition.
7. Metrics and README.
8. Optional `solvePnP` pose estimation.
9. Optional ARKit/ARCore design doc or prototype.

The project is successful after Step 7.

The project becomes notably stronger after Step 8.

Step 9 is polish, not a dependency.

---

# Contract Summary

`sudoku-ar-overlay` should be built as a credible, bounded, high-probability AR-style portfolio project.

The core promise is:

> Detect a physical Sudoku board, solve it once, project the missing answers onto the board plane, stabilize the projection across frames, and reacquire the overlay after temporary tracking loss.

The core technical bet is:

> Planar tracking is the correct first implementation because the target object is flat. Full SLAM is useful future work, not the dependency for project success.

The project should prioritize:

- credibility,
- shippability,
- clear metrics,
- honest limitations,
- and an interview-ready demo.
