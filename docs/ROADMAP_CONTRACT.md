# `sudoku-ar-overlay` Roadmap Contract

## Purpose

This document is the working roadmap and execution contract for `sudoku-ar-overlay`, a second portfolio repository that extends the existing `sudoku-image-solver` project from a static ML/CV inference pipeline into a credible markerless AR-style video overlay system.

The goal is not to build production-grade mobile AR, full SLAM, or a native iOS/Android application. The goal is to build a polished, honest, high-probability 3-week portfolio project that demonstrates practical MLE and computer-vision engineering:

- frozen model reuse,
- video ingestion and processing,
- board detection and solving,
- solve-once / render-many session state,
- homography-based planar overlay,
- markerless tracking,
- tracking-confidence gating,
- look-away / look-back reacquisition,
- metrics,
- demo artifacts,
- and clear failure-mode documentation.

## North Star

> Turn the existing Sudoku image solver into a markerless video-based AR overlay system that detects a normal physical Sudoku puzzle, solves it once, projects the missing answers onto the board plane, hides the overlay when tracking confidence is low, and reacquires the solved overlay when the board returns to view.

## Repository Name

```text
sudoku-ar-overlay
```

## Current Strategic Decision

The project has tested several approaches:

1. Static image overlay works.
2. Webcam solve works.
3. Segmentation-only tracking works conceptually but is too slow for smooth tracking.
4. Optical-flow homography tracking improves responsiveness but drifts or fails under normal-speed motion.
5. ArUco/fiducial tracking would improve robustness but is not acceptable as a user-facing product path because the user should not need to add a printed marker.
6. SLAM/ARKit would likely improve world tracking, but it is too large and off-scope for a 3-week Python/OpenCV portfolio project.

The revised direction is:

> Use recorded iPhone video as the primary demo input, keep the system markerless, and engineer a confidence-gated planar tracking/reacquisition pipeline that is impressive, honest, and shippable within three weeks.

## Positioning

This project should be framed as:

> A markerless, video-based planar AR overlay for Sudoku solving using a frozen ML vision pipeline, solve-once session state, homography-based rendering, confidence-gated tracking, and look-away/look-back reacquisition.

Do **not** frame this as:

- a full SLAM system,
- a production mobile AR app,
- an ARKit/ARCore replacement,
- a persistent world-mapping system,
- a fiducial-marker product,
- a bent-paper / deformable-surface tracker,
- or a generic OpenCV webcam demo.

The intended framing is:

> The first repo solves the perception problem. This second repo turns that model into a video perception and AR-style overlay system.

## Target Audience

This project should be credible for roles involving:

- applied machine learning,
- computer vision,
- robotics-adjacent perception,
- defense technology,
- real-time / video inference systems,
- productized ML demos,
- and applied science / MLE portfolio review.

The project should show judgment:

> Instead of trying to bolt on SLAM or require artificial markers, the system uses the Sudoku board itself as the target, processes high-quality iPhone video, tracks only while confident, fails closed when uncertain, and reacquires the cached solution when the board returns.

---

# Product Constraint

The final user-facing demo must work with a **normal Sudoku puzzle**.

The final demo must **not** require:

- ArUco markers,
- AprilTags,
- QR codes,
- special printed fiducials,
- stickers,
- added dots,
- custom board border markers,
- mobile ARKit/ARCore,
- or a SLAM setup.

Diagnostic tools are allowed during development, but the final user-facing path should be markerless.

---

# Scope Definition

## In Scope

The core project should include:

1. Static image overlay.
2. Recorded iPhone video mode.
3. Optional live webcam mode as a secondary / experimental path.
4. Integration with the frozen Sudoku solver.
5. Solve-once session state.
6. Homography-based planar overlay.
7. Markerless tracking from board appearance.
8. Confidence-gated overlay rendering.
9. Look-away / look-back reacquisition.
10. Runtime metrics: FPS, solve latency, tracking uptime, tracking-loss count, reacquisition time.
11. Demo MP4 and optional GIF.
12. Clear README and architecture documentation.
13. Honest limitations and future work.

## Optional Stretch Scope

The stretch path may include:

1. Template-assisted markerless tracking.
2. Board visual fingerprinting.
3. Board-givens fingerprinting.
4. Gridline refinement when visible.
5. `solvePnP` pose/debug visualization with approximate camera intrinsics.
6. Higher-quality iPhone/Continuity Camera live mode.
7. Multi-clip evaluation script.

## Out of Scope for Core Success

The core project does **not** require:

- ORB-SLAM,
- RTAB-Map,
- pySLAM,
- full visual-inertial odometry,
- ARKit/ARCore implementation,
- native mobile deployment,
- ArUco/AprilTag/fiducial user-facing tracking,
- persistent world maps,
- cloud anchors,
- multi-user AR,
- occlusion handling,
- depth estimation,
- arbitrary 3D object tracking,
- bent-paper deformation,
- or production-grade AR persistence.

---

# Success Criteria

The project is successful when it can demonstrate the following:

1. A normal physical Sudoku board appears in a recorded iPhone video.
2. The board is detected.
3. The puzzle is solved once.
4. Only originally empty cells receive overlaid solution digits.
5. The solved overlay stays visually attached to the board during controlled, moderate camera movement.
6. When tracking confidence drops, the overlay hides instead of drifting.
7. When the camera looks away or the board leaves the frame, the system enters `TRACKING_LOST`.
8. When the board re-enters view, the system reacquires it and redraws the cached solved overlay.
9. The repo reports solve latency, render FPS, tracking uptime, tracking-loss events, and reacquisition time.
10. The README clearly explains the engineering tradeoff: planar markerless video tracking and reacquisition were chosen over SLAM, mobile AR, or fiducial markers.

The project does **not** need to track through fast motion. It needs to handle fast motion professionally by failing closed and reacquiring.

---

# Recommended Three-Week Timeline

The revised core project should take approximately **15 working days**.

| Phase | Estimated Time | Outcome |
|---|---:|---|
| 0. Preserve baseline and revise contract | 0.5 day | Existing markerless prototype preserved; roadmap updated |
| 1. Recorded-video mode | 1-2 days | Process iPhone MP4 input and write annotated MP4 output |
| 2. Solve-once video session | 1-2 days | Detect/solve once, cache solution, render across frames |
| 3. Confidence-gated tracking | 2-3 days | Hide overlay when tracking is weak instead of drifting |
| 4. Look-away/look-back reacquisition | 2-3 days | Reattach cached solution when board returns |
| 5. Template-assisted markerless tracking | 2-4 days | Use board appearance to improve drift correction/reacquisition |
| 6. Metrics and evaluation clips | 1-2 days | FPS, latency, tracking uptime, loss events, reacquisition time |
| 7. README and demo polish | 2-3 days | Interview-ready README, architecture diagram, final MP4/GIF |
| 8. Optional pose/debug layer | 1-2 days | Approximate `solvePnP` axis/pose visualization if time remains |

---

# Phase 0 — Preserve Baseline and Revise Contract

## Estimated Time

0.5 day

## Risk

Low

## Portfolio Value

Medium

## Goal

Preserve the work already completed and revise the project direction around a realistic 3-week finish line.

## Completed Baseline

The repo already has:

- static overlay,
- real solver bridge,
- webcam mode,
- freeze-frame solve usability,
- segmentation-only tracking prototype,
- optical-flow homography tracker prototype,
- rendered OpenCV video recording,
- revised understanding of markerless tracking limitations.

## Decision

Keep markerless webcam/flow work as an experimental prototype, but make recorded iPhone video the primary demo path.

## Deliverables

- `docs/ROADMAP_CONTRACT.md` updated with this contract.
- `docs/project_status.md` updated with the strategic pivot.
- Current branches committed cleanly.

## Pass Condition

The repository has a clean roadmap that no longer treats ArUco, ARKit, or SLAM as the active implementation path.

---

# Phase 1 — Recorded-Video Mode

## Estimated Time

1-2 days

## Risk

Low-to-medium

## Portfolio Value

Very high

## Goal

Add first-class recorded-video processing.

The primary demo should process an iPhone-recorded video and write an annotated output MP4. This makes the project repeatable and easier to evaluate than a fragile live webcam demo.

## Target Command

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_lookaway.mp4 \
  --out assets/demo/processed_lookaway_overlay.mp4 \
  --debug
```

## Required Behavior

1. Read input video frame-by-frame.
2. Write a processed output MP4.
3. Preserve original frame size and approximate FPS.
4. Show optional debug text:
   - state,
   - FPS,
   - solve latency,
   - tracking quality,
   - frames since seen,
   - loss/reacquisition events.

## Pass Condition

The app can take a raw iPhone video and produce a rendered output video.

## Kill Criteria

If live display slows development, prioritize offline MP4 output first.

---

# Phase 2 — Solve-Once Video Session

## Estimated Time

1-2 days

## Risk

Low

## Portfolio Value

High

## Goal

Solve the Sudoku board once in a video sequence and reuse the cached solution across frames.

## Required State

The board session should store:

```text
status
givens
solution
missing_mask
last_corners
smoothed_corners
canonical_board_template
solved_at_frame_idx
solve_latency_ms
tracking_quality
tracking_loss_events
reacquisition_events
```

## Required Behavior

1. Detect a board.
2. Solve it once.
3. Cache:
   - givens,
   - solution,
   - missing mask,
   - canonical board template,
   - initial corners.
4. Render only missing digits.
5. Avoid re-solving every frame.

## Pass Condition

A processed video shows solved digits overlaid after one solve event, without repeated OCR/solve calls.

---

# Phase 3 — Confidence-Gated Tracking

## Estimated Time

2-3 days

## Risk

Medium

## Portfolio Value

Very high

## Goal

Make tracking behavior professional by hiding the overlay when confidence is low.

The worst demo failure is a confidently wrong overlay. The system should fail closed.

## Tracking Confidence Signals

Use a composite score from available signals:

- homography inlier ratio,
- number of tracked points,
- board area stability,
- corner jump distance,
- projected board inside image bounds,
- aspect ratio plausibility,
- segmentation score when available,
- template match score when available.

## Required States

```text
NO_BOARD
BOARD_DETECTED
SOLVED_TRACKING
TRACKING_LOST
REACQUIRED
```

## Required Behavior

```text
tracking confidence high
  -> render overlay

tracking confidence low
  -> hide overlay
  -> set TRACKING_LOST

board detected again
  -> set REACQUIRED
  -> redraw cached solution
```

## Pass Condition

In a video with fast movement or a look-away event, the overlay disappears rather than drifting into the wrong location.

---

# Phase 4 — Look-Away / Look-Back Reacquisition

## Estimated Time

2-3 days

## Risk

Medium

## Portfolio Value

Very high

## Goal

Support the most important AR-like behavior:

> Look away, look back, and the solved overlay returns.

This is **not** world-space persistence. It is board reacquisition.

## Definition

When the board leaves the frame:

```text
state = TRACKING_LOST
overlay hidden
solution retained
```

When the board returns:

```text
board detected again
cached solution reused
state = REACQUIRED
overlay redrawn in the correct board position
```

## Reacquisition Levels

### Level 1 — Session-Level Reacquisition

Assume any reacquired Sudoku board in the current session is the same board until the user presses reset.

This is the minimum viable version.

### Level 2 — Visual Template Reacquisition

Compare the reacquired board crop to the cached canonical board template.

Use this to confirm likely same-board identity.

### Level 3 — Givens Fingerprint Reacquisition

If time permits, infer givens again on reacquisition and compare filled-cell positions / digit values to the cached givens.

## Pass Condition

A demo video shows:

1. board solved,
2. overlay visible,
3. camera looks away,
4. overlay hidden,
5. camera looks back,
6. cached overlay returns without re-solving manually.

---

# Phase 5 — Template-Assisted Markerless Tracking

## Estimated Time

2-4 days

## Risk

Medium-high

## Portfolio Value

High

## Goal

Improve tracking/reacquisition by using the locked Sudoku board itself as a natural image target.

This should not depend only on gridlines. Inner gridlines may be faint, thin, blurred, or poorly lit. The tracker should use the full board appearance:

- outer border,
- gridlines when visible,
- printed givens,
- paper texture,
- contrast/shadows,
- stable visual features.

## Implementation Options

Start simple with OpenCV features:

```text
ORB or SIFT features
descriptor matching
RANSAC homography
confidence score from inliers
```

Potential stretch:

```text
SuperPoint / LightGlue style matching
```

Do not start with learned feature matching unless OpenCV features fail badly.

## Target Loop

```text
initial board detection
  -> warp to canonical board
  -> save canonical template
  -> detect template features

each frame
  -> use optical flow prediction
  -> use template feature matching to correct/reacquire
  -> estimate homography
  -> render overlay if confidence is high
```

## Pass Condition

Template-assisted tracking improves reacquisition and reduces drift on recorded iPhone clips compared with optical-flow-only tracking.

## Kill Criteria

If template matching is weak on Sudoku boards, keep optical flow + segmentation reacquisition and document template matching as a tested limitation.

---

# Phase 6 — Metrics and Evaluation Clips

## Estimated Time

1-2 days

## Risk

Low

## Portfolio Value

High

## Goal

Add enough measurement that the project looks engineered rather than hacked together.

## Evaluation Clips

Create 5-10 short iPhone clips:

```text
clip_01_static.mp4
clip_02_slow_pan.mp4
clip_03_tilt.mp4
clip_04_distance_change.mp4
clip_05_fast_motion_loss.mp4
clip_06_lookaway_return.mp4
clip_07_glare_or_low_contrast.mp4
```

## Metrics to Report

| Metric | Target | Notes |
|---|---:|---|
| Solve latency | <350 ms preferred | Use frozen solver latency |
| Render FPS | >20 FPS preferred | Offline processing FPS can be separate |
| Tracking uptime | report only | Percent frames in `SOLVED_TRACKING` |
| Tracking loss count | report only | Number of loss events |
| Reacquisition time | <1-2 sec preferred | Frames/time from return to reacquired |
| Mean/p95 overlay jitter | optional | On stationary clip |
| Failure reasons | required | Drift, blur, low contrast, partial board |

## Deliverables

```text
docs/metrics.md
assets/demo/final_demo.mp4
assets/demo/debug_demo.mp4
assets/demo/final_demo.gif
```

## Pass Condition

The README can honestly describe when the system works, when it fails, and how it behaves under uncertainty.

---

# Phase 7 — README and Architecture Polish

## Estimated Time

2-3 days

## Risk

Low

## Portfolio Value

Very high

## Goal

Turn the project into an interview-ready portfolio asset.

## README Structure

```text
# sudoku-ar-overlay

## Demo

Final MP4/GIF first.

## What This Project Does

Markerless Sudoku AR-style overlay from recorded iPhone video.

## Why This Is an AR Problem

Board detection, plane/homography, anchoring, tracking, loss/reacquisition.

## Architecture

iPhone video -> board detection -> frozen solver -> session state -> markerless tracking -> homography renderer -> metrics/output video.

## Relationship to sudoku-image-solver

Frozen model dependency and separation of concerns.

## Core Technical Choices

- Recorded iPhone video as primary demo path
- Markerless user-facing system
- Solve once, render many
- Homography for planar overlay
- Confidence-gated tracking
- Fail-closed overlay behavior
- Look-away/look-back reacquisition
- Optional template-assisted tracking

## Metrics

Latency, FPS, tracking uptime, reacquisition time, failure reasons.

## Limitations

No full SLAM.
No persistent world map.
No fiducial markers.
Assumes one board at a time.
Assumes approximately planar paper.
Works best with printed boards, good lighting, and moderate movement.
Fast motion can cause tracking loss; the overlay hides and reacquires.

## Future Work

Mobile AR/VIO integration.
Faster board detector.
Learned feature matching.
Better board fingerprinting.
Pose-estimation debug view.
```

## Required Section: Why Not SLAM?

Include language similar to:

> This project does not use SLAM because the primary task is board-plane anchoring, not global camera localization. SLAM could help with world tracking, but it would not remove the need for board detection, board identity, homography rendering, confidence gating, and reacquisition. For a 3-week MLE portfolio build, a markerless planar video pipeline gives a better reliability-to-complexity ratio.

## Required Section: Why No ArUco / Fiducial Markers?

Include language similar to:

> Fiducial markers are useful for debugging planar AR, but they are not acceptable for this product constraint. The final user-facing demo works from a normal Sudoku puzzle without printed codes or added markers.

## Pass Condition

A hiring manager can understand the project, demo, technical choices, limitations, and engineering judgment in 60 seconds.

---

# Optional Phase 8 — Pose/Geometry Debug Layer

## Estimated Time

1-2 days

## Risk

Medium

## Portfolio Value

Medium-high

## Required for Success?

No.

## Goal

Add camera-relative board pose visualization if the core demo is already stable.

## Implementation

Use approximate camera intrinsics and detected board corners:

```text
known board dimensions
detected 2D board corners
solvePnP
draw axis / board normal
```

## Deliverables

```text
src/sudoku_ar_overlay/pose.py
docs/pose_estimation.md
```

## Pass Condition

Debug view shows approximate board pose or projected axes.

## Kill Criteria

If camera calibration or pose stability consumes time, defer.

---

# Engineering Guardrails

## Do Not Overbuild

Do not start with:

- ORB-SLAM,
- RTAB-Map,
- pySLAM,
- native mobile deployment,
- cloud anchors,
- depth estimation,
- full 3D world persistence,
- fiducial-marker product flow,
- bent-paper tracking,
- or multi-board tracking.

## Use a Demo-Friendly Environment

It is acceptable to constrain the demo:

- recorded iPhone video,
- printed puzzle,
- good lighting,
- one board at a time,
- board mostly visible,
- moderate camera movement,
- look-away/look-back sequence,
- reset button for new board.

A constrained, polished demo is better than an ambitious unfinished live AR system.

## Prefer Shipping Over Purity

If a sophisticated approach blocks progress, use a simpler one and document the tradeoff.

Examples:

- Use recorded video before live webcam polish.
- Use session-level reacquisition before board fingerprinting.
- Use optical flow + segmentation before learned feature matching.
- Use fail-closed tracking before chasing perfect fast-motion robustness.
- Use approximate pose debug before camera calibration.

---

# Failure Modes to Document

The README should honestly list likely failure modes:

- poor lighting,
- motion blur,
- fast camera movement,
- severe camera angle,
- partial board occlusion,
- very faint gridlines,
- low-contrast printed puzzles,
- handwritten digits if not supported,
- unusual Sudoku board designs,
- bad segmentation corners,
- tracking loss during fast movement,
- wrong board reacquisition if multiple boards are present,
- significant paper bending that violates planar assumptions.

Honest limitations increase credibility.

---

# Interview Pitch

## Defense-Tech / Robotics-Adjacent Pitch

> I built a markerless video-based AR-style Sudoku overlay to extend a frozen vision model into an interactive perception system. The first repo handles board detection and digit inference. This repo handles recorded-video processing, solve-once state, board-plane tracking, homography-based rendering, tracking confidence, and look-away/look-back reacquisition. I intentionally avoided SLAM and fiducial markers for the core demo because the product requirement is a normal Sudoku board and the task is board-plane anchoring rather than global world mapping.

## Applied AI / MLE Pitch

> The interesting part was turning a model into a product-like video system. I decoupled expensive inference from rendering, cached solved board state, added confidence-gated tracking, failed closed when the overlay was uncertain, and measured latency, tracking uptime, and reacquisition behavior.

## Applied Science Pitch

> This was a full-stack applied ML project: frozen model integration, video ingestion, geometric rendering, markerless tracking, state management, confidence scoring, metrics, and failure-mode documentation.

---

# Final Build Order

Execute in this order:

1. Preserve baseline and update contract/status.
2. Add recorded-video mode.
3. Add solve-once video session.
4. Add confidence-gated tracking.
5. Add look-away/look-back reacquisition.
6. Add template-assisted tracking if needed.
7. Add metrics and evaluation clips.
8. Polish README and demo assets.
9. Optional pose/debug layer.

The project is successful after Step 8.

Step 9 is polish, not a dependency.

---

# Contract Summary

`sudoku-ar-overlay` should be built as a credible, bounded, high-probability AR-style portfolio project.

The core promise is:

> Given a normal Sudoku puzzle in recorded iPhone video, detect the board, solve it once, project the missing answers onto the board plane, hide the overlay when tracking is uncertain, and reacquire the cached solution when the board returns to view.

The core technical bet is:

> For a 3-week MLE portfolio build, markerless planar video tracking with confidence-gated reacquisition is a better reliability-to-complexity tradeoff than SLAM, ARKit, or fiducial markers.

The project should prioritize:

- credibility,
- shippability,
- normal-puzzle user experience,
- clean demo videos,
- clear metrics,
- honest limitations,
- and an interview-ready README.
