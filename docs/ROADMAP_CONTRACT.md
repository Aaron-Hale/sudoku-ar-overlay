# `sudoku-ar-overlay` Revised Roadmap Contract

**Revision date:** 2026-04-24  
**Revision reason:** The project moved from a purely markerless planar-tracking direction to a two-mode tracking strategy. Markerless tracking remains useful and credible, but the reliable demo path will use fiducial-assisted tracking with ArUco/ChArUco markers. ARKit/ARCore and ORB-SLAM are no longer part of the planned scope.

---

## 1. Purpose

This document is the working roadmap and execution contract for `sudoku-ar-overlay`, a portfolio repository that extends the existing `sudoku-image-solver` project from a static ML/CV inference pipeline into a credible AR-style live overlay system.

The goal is to build a polished, honest, high-probability portfolio project that demonstrates practical familiarity with:

- live camera processing,
- frozen ML model reuse,
- planar AR overlay rendering,
- homography-based projection,
- solve-once session state,
- tracking state machines,
- fiducial-assisted visual anchoring,
- markerless tracking limitations,
- reacquisition after tracking loss,
- and measured real-time performance.

The project is **not** intended to become a production mobile AR app, a full SLAM system, an ARKit/ARCore implementation, or an ORB-SLAM integration.

---

## 2. North Star

> Build a real-time Sudoku AR overlay system that detects a physical puzzle, solves it once, projects missing digits onto the board plane, and keeps that overlay attached using practical planar tracking.

The final portfolio version should include two tracking modes:

1. **Markerless experimental mode**
   - ML segmentation initializes/reacquires the Sudoku board.
   - Optical flow + homography tracks frame-to-frame board motion.
   - This demonstrates the harder perception/tracking path and documents limitations.

2. **Fiducial-assisted reliable mode**
   - ArUco or ChArUco markers provide stable per-frame board anchoring.
   - The solved overlay is rendered on the board plane with less drift and better reacquisition.
   - This becomes the polished demo path.

---

## 3. Repository Name

```text
sudoku-ar-overlay
```

---

## 4. Positioning

Frame this project as:

> A real-time Sudoku AR overlay that turns a frozen ML vision solver into an interactive planar AR system with markerless and fiducial-assisted tracking modes.

The intended story:

> The first repo solves the perception problem. This second repo turns that model into an interactive AR-style application. It includes a markerless tracking prototype to demonstrate perception-to-tracking integration and a fiducial-assisted mode to provide a robust, polished planar AR demo.

Do **not** frame this as:

- a full SLAM system,
- an ORB-SLAM project,
- a production mobile AR app,
- an ARKit/ARCore replacement,
- a persistent world-mapping system,
- a non-rigid/deformable paper tracker,
- or a generic OpenCV webcam demo.

---

## 5. Target Audience

This project should be credible for roles involving:

- applied machine learning,
- computer vision,
- robotics-adjacent perception,
- defense technology,
- real-time inference systems,
- productized ML demos,
- and applied science / MLE portfolio review.

The project should show judgment:

> Use the right level of computer vision for the problem. Do not overbuild with full SLAM or mobile AR when a planar, marker-assisted OpenCV solution is the more reliable and shippable path.

---

# 6. Scope Definition

## 6.1 In Scope

The core project should include:

1. Static image overlay.
2. Live webcam mode.
3. Optional recorded-video mode.
4. Integration with the frozen `sudoku-image-solver`.
5. Solve-once session state.
6. Homography-based planar overlay.
7. Markerless tracking prototype:
   - segmentation initialization,
   - optical-flow frame-to-frame tracking,
   - homography update,
   - fail-fast behavior.
8. Fiducial-assisted reliable tracking mode:
   - ArUco or ChArUco marker detection,
   - marker-based board homography,
   - fast reacquisition,
   - stable overlay.
9. Tracking state machine:
   - no board,
   - board detected,
   - solved tracking,
   - tracking lost,
   - reacquired.
10. Runtime metrics:
   - solve latency,
   - render FPS,
   - marker detection latency,
   - tracking confidence / inliers,
   - reacquisition time.
11. Demo video or GIF.
12. Clear README and architecture documentation.
13. Honest limitations and future work.

## 6.2 Optional Stretch Scope

The stretch path may include:

1. Camera calibration helper.
2. `solvePnP` pose estimation.
3. 3D axis / board-normal debug visualization.
4. ChArUco calibration / pose-estimation mode.
5. Multi-frame OCR probability aggregation.

## 6.3 Out of Scope

The project does **not** require:

- ARKit,
- ARCore,
- ORB-SLAM,
- native mobile deployment,
- visual-inertial odometry,
- persistent world maps,
- cloud anchors,
- multi-user AR,
- non-rigid paper deformation,
- depth estimation,
- occlusion handling,
- arbitrary 3D object tracking,
- or production-grade spatial persistence.

These may be mentioned as related concepts, but they should not become implementation dependencies.

---

# 7. Success Criteria

The project is successful when it can demonstrate the following:

1. A physical Sudoku board appears in a live webcam or recorded-video feed.
2. The board is detected and outlined.
3. The puzzle is solved once.
4. Only originally empty cells receive overlaid solution digits.
5. In fiducial-assisted mode, the digits remain visually attached to the board during normal controlled hand/camera movement.
6. In markerless mode, the project demonstrates segmentation + optical flow tracking and documents expected limitations.
7. If tracking confidence drops, the overlay hides rather than drifting confidently into the wrong location.
8. When the board/marker re-enters view, the solved overlay is reacquired and redrawn.
9. The repo reports useful latency/FPS/tracking metrics.
10. The README clearly explains:
    - why planar tracking was chosen,
    - why markerless tracking is limited,
    - why fiducial-assisted tracking is the reliable demo mode,
    - and why full SLAM/mobile AR was intentionally cut.

---

# 8. Recommended Timeline

The revised core project should take approximately **8–14 working days** from the current state.

| Phase | Estimated Time | Outcome |
|---|---:|---|
| 0. Existing base | Done | Static solver overlay, webcam, manual solve, markerless experiments |
| 1. Stabilize current work | 0.5 day | Commit current markerless / status / recording work |
| 2. ArUco marker generation | 0.5 day | Generate printable marker(s) |
| 3. One-marker ArUco prototype | 1–2 days | Detect marker, estimate board plane from fixed offset |
| 4. Four-marker ArUco board | 2–3 days | Stable board homography from markers near corners |
| 5. Solve-on-lock + cached overlay | 1 day | Lock marker layout, solve once, render overlay |
| 6. Reacquisition / fail-fast state machine | 1–2 days | Hide on low confidence, reacquire quickly |
| 7. Metrics + demo recording | 1–2 days | FPS, marker latency, solve latency, demo video |
| 8. README + docs polish | 1–2 days | Interview-ready repo |
| 9. Optional `solvePnP` pose debug | 1–3 days | Board pose / 3D axis credibility layer |
| 10. Optional multi-frame OCR ensemble | 1–3 days | Reduce bad digit inference risk |

---

# 9. Architecture

## 9.1 Shared Solver and Overlay Architecture

```text
camera/image frame
  -> Sudoku solver adapter
  -> givens + solution + board corners
  -> board session state
  -> overlay renderer
  -> rendered frame/video
```

The frozen Sudoku solver owns:

- board detection,
- board warp,
- occupancy inference,
- digit inference,
- Sudoku solving.

The AR overlay repo owns:

- live camera loop,
- tracking mode selection,
- board session state,
- homography projection,
- marker tracking,
- optical-flow tracking prototype,
- overlay rendering,
- metrics,
- demo packaging.

## 9.2 Markerless Experimental Mode

```text
camera frame
  -> ML segmentation detects board corners
  -> optical flow tracks points frame-to-frame
  -> homography updates board corners
  -> cached solution overlay is warped to current board plane
```

Purpose:

- demonstrate markerless ML/CV tracking pipeline,
- show practical limits of optical flow under normal movement,
- fail cleanly when tracking confidence drops.

Known limitation:

> Markerless optical flow works under slow controlled motion but is fragile under normal hand movement, motion blur, and poor feature tracking.

## 9.3 Fiducial-Assisted Reliable Mode

```text
camera frame
  -> ArUco/ChArUco marker detection
  -> marker geometry defines board plane
  -> homography maps canonical Sudoku board to camera frame
  -> cached solution overlay is warped to current board plane
```

Purpose:

- provide the reliable portfolio demo,
- track under more normal controlled movement,
- reacquire quickly after look-away/look-back,
- demonstrate practical AR anchoring.

---

# 10. Tracking Modes

## 10.1 `markerless`

Description:

> Experimental mode using ML segmentation, optical flow, and homography.

Expected command shape:

```bash
PYTHONPATH=src python scripts/webcam_flow_tracking_demo.py   --repo-root "$HOME/projects/sudoku-image-solver"   --debug
```

Acceptable limitations:

- works best with slow movement,
- can lose tracking under normal speed,
- can drift if feature points are weak,
- should hide overlay when confidence drops.

## 10.2 `aruco`

Description:

> Reliable demo mode using printed ArUco markers to anchor the board plane.

Expected command shape:

```bash
PYTHONPATH=src python scripts/aruco_tracking_demo.py   --repo-root "$HOME/projects/sudoku-image-solver"   --record-out assets/demo/aruco_tracking_demo.mp4
```

Target behavior:

- marker detection every frame,
- stable board outline,
- solve once,
- overlay follows the board under normal controlled movement,
- fast reacquisition when the marker/board returns.

## 10.3 `charuco` optional

Description:

> More precise marker/chessboard hybrid mode for calibration or pose-estimation credibility.

Only implement after ArUco mode works.

---

# 11. Phase Details

## Phase 1 — Stabilize Current Work

Estimated time: 0.5 day.

Goal:

Commit the current markerless prototype, status log, and video-recording support before pivoting to ArUco.

Deliverables:

- committed `flow_tracker.py`,
- committed `webcam_flow_tracking_demo.py`,
- committed status log update,
- current demo video saved under `assets/demo/`.

Pass condition:

`main` or a feature branch has a clean checkpoint of markerless work.

---

## Phase 2 — ArUco Marker Generation

Estimated time: 0.5 day.

Goal:

Create scripts to generate printable markers.

Deliverables:

```text
scripts/generate_aruco_marker.py
assets/markers/aruco_23.png
assets/markers/aruco_23_printable.pdf or .png
```

Pass condition:

A marker can be printed and detected by OpenCV.

---

## Phase 3 — One-Marker ArUco Prototype

Estimated time: 1–2 days.

Goal:

Use one marker near the Sudoku board to compute an approximate board plane from known physical offsets.

Deliverables:

```text
src/sudoku_ar_overlay/aruco_tracker.py
scripts/aruco_tracking_demo.py
```

Expected behavior:

- detect marker every frame,
- draw marker outline,
- infer approximate Sudoku board corners using configured marker-to-board offset,
- draw board outline.

Pass condition:

Board outline follows the marker reliably under normal controlled movement.

Kill criteria:

If one-marker offset is too fragile, move quickly to four markers.

---

## Phase 4 — Four-Marker ArUco Board

Estimated time: 2–3 days.

Goal:

Use four markers near the board corners so marker detections define the board homography directly.

Recommended marker layout:

```text
marker 10 near top-left
marker 11 near top-right
marker 12 near bottom-right
marker 13 near bottom-left
```

Deliverables:

- printable marker layout,
- marker ID mapping,
- board-corner estimation from marker detections,
- robust board outline.

Pass condition:

The board outline remains stable under normal controlled movement and reacquires quickly after leaving/re-entering view.

---

## Phase 5 — Solve-on-Lock + Cached Overlay

Estimated time: 1 day.

Goal:

Once the board is anchored, solve the Sudoku and render the cached solution using the marker-based board homography.

Behavior:

```text
lock board
  -> solve once
  -> cache givens/solution/missing mask
  -> render overlay every frame using marker-based homography
```

Deliverables:

- `l` lock + solve,
- optional `--auto-solve-on-lock`,
- `r` reset,
- `q` quit,
- rendered video support.

Pass condition:

The solved overlay follows the board in ArUco mode.

---

## Phase 6 — Reacquisition and Fail-Fast Behavior

Estimated time: 1–2 days.

Goal:

Make the app robust in failure cases.

Behavior:

```text
markers visible and valid -> show overlay
markers missing/low confidence -> hide overlay
markers return -> reacquire and redraw cached solution
reset -> clear solution and tracking immediately
```

Deliverables:

- tracking status panel,
- confidence score,
- fast hide-on-loss,
- fast reacquisition.

Pass condition:

A demo video shows board tracking, tracking loss, and clean reacquisition.

---

## Phase 7 — Metrics and Demo Artifacts

Estimated time: 1–2 days.

Goal:

Measure and package the project.

Metrics:

- solve latency,
- marker detection latency,
- render FPS,
- tracking state transitions,
- reacquisition time,
- known failure modes.

Deliverables:

```text
docs/metrics.md
assets/demo/aruco_tracking_demo.mp4
assets/demo/markerless_tracking_demo.mp4
assets/demo/static_overlay.jpg
```

Pass condition:

README can honestly state the measured performance and limitations.

---

## Phase 8 — README and Architecture Polish

Estimated time: 1–2 days.

Goal:

Make the repo interview-ready.

README structure:

```text
# sudoku-ar-overlay

## Demo

Show static, markerless, and ArUco-assisted demos.

## What This Project Does

Explain the Sudoku AR overlay.

## Tracking Modes

1. Markerless experimental mode.
2. Fiducial-assisted reliable mode.

## Architecture

Frozen solver -> session state -> tracking mode -> homography overlay.

## Why Not Full SLAM / ARKit / ARCore?

Explain scope and tradeoff.

## Metrics

Latency, FPS, reacquisition.

## Limitations

Markerless fragile under fast motion; ArUco requires printed markers; assumes planar board.

## Future Work

ChArUco pose, solvePnP, multi-frame OCR aggregation, non-rigid mesh warping.
```

Pass condition:

A hiring manager can understand the project, demo, and technical choices in 60 seconds.

---

## Phase 9 — Optional `solvePnP` Pose Debug

Estimated time: 1–3 days.

Goal:

Add camera-relative board pose visualization using known marker/board geometry.

Deliverables:

- board normal / 3D axis overlay,
- approximate camera-to-board pose,
- `docs/pose_estimation.md`.

Pass condition:

Debug view shows projected axes or board normal.

---

## Phase 10 — Optional Multi-Frame OCR Ensemble

Estimated time: 1–3 days.

Goal:

Reduce bad digit inference from a single frame.

Preferred method:

1. Capture 3–5 frames after lock.
2. Run OCR/readout on each.
3. Aggregate cell-level occupancy and digit probabilities.
4. Build one givens grid.
5. Solve once.

Do **not** vote on final solved boards first. Aggregate cell probabilities first.

Pass condition:

Static or live solve-on-lock is less sensitive to a single bad frame.

---

# 12. Repository Changes Required

The repo should be updated to reflect the revised direction.

## 12.1 Replace Roadmap Contract

Replace:

```text
docs/ROADMAP_CONTRACT.md
```

with this revised contract.

## 12.2 Update README

The README should no longer present ARKit/ARCore as a planned implementation path.

It should describe:

- static solver overlay,
- markerless experimental tracking,
- fiducial-assisted reliable tracking,
- current project status,
- and future stretch work.

## 12.3 Update Dependencies

ArUco support may require OpenCV contrib modules.

Preferred dependency:

```toml
dependencies = [
    "numpy>=1.24",
    "opencv-contrib-python>=4.8",
    "pydantic>=2.0",
    "rich>=13.0",
]
```

Avoid installing both `opencv-python` and `opencv-contrib-python` unless necessary.

## 12.4 Add Marker Assets

Add:

```text
assets/markers/
assets/demo/
```

## 12.5 Add New Scripts

Add:

```text
scripts/generate_aruco_marker.py
scripts/aruco_tracking_demo.py
```

## 12.6 Add New Source Modules

Add:

```text
src/sudoku_ar_overlay/aruco_tracker.py
```

Optional later:

```text
src/sudoku_ar_overlay/pose.py
src/sudoku_ar_overlay/metrics.py
```

---

# 13. Engineering Guardrails

## 13.1 Do Not Overbuild

Do not start with:

- ORB-SLAM,
- ARKit,
- ARCore,
- native mobile deployment,
- cloud anchors,
- depth estimation,
- full 3D world persistence,
- non-rigid paper deformation,
- or multi-board tracking.

## 13.2 Use a Demo-Friendly Environment

It is acceptable to constrain the first demo:

- printed puzzle,
- printed ArUco markers,
- reasonable lighting,
- one board at a time,
- camera 1–3 feet away,
- board mostly visible,
- reset button for new board.

A constrained demo is better than an ambitious unfinished repo.

## 13.3 Prefer Shipping Over Purity

If a sophisticated approach blocks progress, use a simpler one and document the tradeoff.

Examples:

- use one marker before four markers,
- use four markers before ChArUco,
- use homography before solvePnP,
- use solve-on-lock before automatic solve,
- use session-level reacquisition before fingerprint matching,
- use recorded demo video before fully polished webcam UX.

---

# 14. Failure Modes to Document

The README should honestly list failure modes:

## Markerless mode

- fragile under normal-speed motion,
- can drift when feature points are weak,
- sensitive to blur and lighting,
- requires fail-fast hiding when confidence drops.

## ArUco-assisted mode

- requires printed markers,
- marker occlusion can cause tracking loss,
- assumes fixed marker-to-board geometry,
- assumes board is approximately planar,
- paper bending violates the homography assumption.

## Solver

- bad digit inference can produce a wrong givens grid,
- handwritten or unusual fonts may fail,
- poor lighting can hurt OCR.

---

# 15. Interview Pitch

## Defense-Tech / Robotics-Adjacent Pitch

> I built a real-time Sudoku AR overlay that turns a frozen ML vision model into an interactive perception system. The repo includes a markerless mode using segmentation and optical-flow homography tracking, plus a fiducial-assisted mode using ArUco markers for robust planar anchoring. I intentionally cut full SLAM and mobile AR because the target is a planar object and the project needed a reliable, shippable demo.

## Applied AI / MLE Pitch

> The interesting part was turning model inference into a product-like system. I decoupled expensive solving from real-time rendering, used session state to avoid re-solving every frame, compared markerless and fiducial-assisted tracking strategies, and measured latency/FPS/reacquisition behavior.

## Applied Science Pitch

> This was a full-stack applied ML/CV project: model packaging, inference adapter, real-time camera loop, geometric projection, optical-flow tracking, fiducial anchoring, state management, tracking metrics, and failure-mode documentation.

---

# 16. Final Build Order

Execute in this order:

1. Commit current markerless optical-flow prototype.
2. Replace roadmap contract.
3. Update README scope.
4. Update dependencies for ArUco support.
5. Generate printable ArUco marker(s).
6. Build one-marker ArUco demo.
7. Upgrade to four-marker board homography if needed.
8. Add solve-on-lock in ArUco mode.
9. Add fail-fast tracking loss and reacquisition.
10. Record demo video.
11. Add metrics.
12. Polish README.
13. Optional `solvePnP` pose debug.
14. Optional multi-frame OCR ensemble.

The project is successful after:

> static overlay + markerless experimental demo + reliable ArUco-assisted demo + metrics + honest README.

---

# 17. Contract Summary

`sudoku-ar-overlay` should now be built as a two-mode planar AR portfolio project:

1. **Markerless experimental mode**
   - demonstrates ML segmentation + optical-flow homography tracking,
   - documents why markerless webcam tracking is fragile under normal movement.

2. **Fiducial-assisted reliable mode**
   - uses ArUco/ChArUco markers to provide a stable planar AR anchor,
   - becomes the polished demo path.

The core technical decision is:

> Full SLAM and mobile AR are intentionally cut. The project stays in Python/OpenCV and uses marker-assisted planar tracking for robustness and shippability.

The project should prioritize:

- credibility,
- shippability,
- robustness,
- clear metrics,
- honest limitations,
- and an interview-ready demo.
