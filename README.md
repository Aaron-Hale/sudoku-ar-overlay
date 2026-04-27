# sudoku-ar-overlay

A markerless, recorded-video planar AR-style overlay for Sudoku solving.

This project extends [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) from a static image inference pipeline into a video perception system. It solves a Sudoku puzzle from a clean frame, projects the missing answers onto the board plane, tracks the board with optical-flow homography, hides the overlay when tracking confidence drops, and reacquires known boards using grid refinement, stability gating, and board identity caching.

> This is not visual odometry, SLAM, ARKit, or ARCore. It is a bounded planar tracking system for a flat object.

---

## Demo

![Markerless Sudoku AR overlay demo](docs/images/final_demo_preview.gif)

**Clean demo:**  
[Watch `final_demo_clean.mp4`](https://github.com/Aaron-Hale/sudoku-ar-overlay/releases/download/markerless-video-demo-v1/final_demo_clean.mp4)

**Debug / stress demo:**  
[Watch `processed_iphone_aggressive_known_board_identity.mp4`](https://github.com/Aaron-Hale/sudoku-ar-overlay/releases/download/markerless-video-demo-v1/processed_iphone_aggressive_known_board_identity.mp4)

The demo videos are generated artifacts and are intentionally ignored by Git. The small GIF preview above is committed for quick README viewing; full MP4s are published through the GitHub Release.

---

## What this project demonstrates

This repo shows how a frozen ML/CV model can be wrapped into a product-like video perception application:

1. Detect a normal printed Sudoku puzzle.
2. Solve a clean video frame once using the existing image solver.
3. Cache the solved grid and missing-cell mask.
4. Render solved digits onto the Sudoku board plane.
5. Track the board frame-to-frame using optical flow and homography.
6. Hide the overlay when tracking becomes unreliable.
7. Reacquire the board when it returns to view.
8. Reuse known-board identity to avoid unnecessary re-solving.
9. Report latency, tracking, and reacquisition metrics.

The project is intentionally scoped around **markerless planar AR** rather than full 3D world anchoring.

---

## Current status

Core demo milestone is complete.

Working:

- Static image overlay with the real frozen Sudoku solver
- Recorded-video processing mode
- Solve-once video session state
- Optical-flow homography tracking
- Confidence-gated fail-closed rendering
- Grid-first and segmentation-fallback reacquisition
- Grid-corner refinement
- Candidate stability buffer
- Known-board identity caching for safer reacquisition
- Clean and debug/stress demo run scripts
- Metrics documentation

Known limitations remain, especially under aggressive motion and new-puzzle acquisition.

---

## Architecture

```text
Input video frame
    |
    |-- Initial solve frame
    |     |
    |     |-- sudoku-image-solver
    |     |     |-- board segmentation
    |     |     |-- perspective warp
    |     |     |-- occupancy detection
    |     |     |-- digit OCR
    |     |     |-- Sudoku solve
    |     |
    |     |-- cache givens, solution, board corners, board fingerprint
    |
    |-- Tracking loop
          |
          |-- optical-flow feature tracking
          |-- homography estimation with RANSAC
          |-- board-corner update
          |-- confidence checks
          |
          |-- if confident:
          |     render solved digit overlay
          |
          |-- if not confident:
                hide overlay
                enter reacquisition
```

Reacquisition path:

```text
Tracking lost
    |
    |-- discover candidate board
    |     |-- grid-first discovery
    |     |-- segmentation fallback
    |
    |-- refine candidate corners against Sudoku grid lines
    |
    |-- require candidate stability across frames
    |
    |-- compare candidate against known-board fingerprint
    |
    |-- if known board:
    |     reuse cached solution
    |
    |-- if new/unknown board:
          require fresh solve before rendering
```

---

## Why optical-flow homography, not visual odometry or SLAM?

A Sudoku board is flat. For a flat target, a homography is the right geometric model for projecting points from the board plane into the camera image.

This project uses:

```text
2D optical flow
+ RANSAC homography
+ planar overlay rendering
```

It does **not** estimate a 3D camera trajectory through the world. It does **not** build a map. It does **not** maintain persistent world anchors after the board is completely out of view.

That is intentional. The goal is a credible, bounded MLE/perception demo, not a full mobile AR platform.

---

## Repository layout

```text
.
├── app.py
├── docs/
│   ├── metrics.md
│   ├── project_status.md
│   └── ROADMAP_CONTRACT.md
├── scripts/
│   ├── demo_runs/
│   │   ├── run_aggressive_known_board_identity.sh
│   │   └── run_aggressive_known_board_identity_clean.sh
│   ├── debug_grid_refinement.py
│   ├── debug_reacquisition_stability.py
│   ├── debug_second_puzzle_candidates.py
│   └── debug_second_puzzle_segmentation.py
└── src/sudoku_ar_overlay/
    ├── board_identity.py
    ├── board_state.py
    ├── config.py
    ├── flow_tracker.py
    ├── grid_discovery.py
    ├── grid_refinement.py
    ├── grid_validation.py
    ├── overlay.py
    ├── reacquisition.py
    ├── smoothing.py
    ├── solver_adapter.py
    ├── stabilizer.py
    └── tracking.py
```

---

## Relationship to `sudoku-image-solver`

This repo depends on the frozen model/runtime from the companion repo:

```text
~/projects/sudoku-image-solver
```

The AR overlay repo does not retrain the Sudoku solver. It treats the solver as a model artifact and focuses on the application/perception layer around it:

- video ingestion
- session state
- tracking
- confidence gates
- reacquisition
- overlay rendering
- metrics and demo packaging

This is the intended portfolio signal: taking a trained model pipeline and turning it into a usable video system.

---

## Setup

From this repo:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The real solver path expects the companion repo to exist locally:

```text
$HOME/projects/sudoku-image-solver
```

The demo commands use:

```bash
--repo-root "$HOME/projects/sudoku-image-solver"
```

---

## Run static image mode

```bash
PYTHONPATH=src python app.py \
  --mode image \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --image "$HOME/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg" \
  --out assets/demo/app_static_real_overlay.jpg
```

---

## Run the clean recorded-video demo

The clean demo writes a no-debug MP4 to:

```text
assets/demo/final_demo_clean.mp4
```

Command:

```bash
scripts/demo_runs/run_aggressive_known_board_identity_clean.sh
```

---

## Run the debug/stress recorded-video demo

The debug/stress demo writes an annotated MP4 to:

```text
assets/demo/processed_iphone_aggressive_known_board_identity.mp4
```

Command:

```bash
scripts/demo_runs/run_aggressive_known_board_identity.sh
```

---

## Metrics

Latest clean demo run:

| Metric | Value |
|---|---:|
| Input FPS | 30.00 |
| Total frames | 1,568 |
| Initial solve frame | 10 |
| Initial solve latency | 318.66 ms |
| Segmentation latency | 278.01 ms |
| Warp/crop latency | 1.23 ms |
| OCR latency | 37.20 ms |
| Sudoku solve latency | 2.22 ms |
| Offline processing FPS | 15.31 |
| Tracking uptime | 0.706 |
| Tracking loss events | 3 |
| Reacquisition events | 3 |
| Final state | SOLVED_TRACKING |

See the full metrics file:

```text
docs/metrics.md
```

Important interpretation:

- processing FPS is offline video-processing throughput, not live camera FPS
- input video is a recorded 30 FPS iPhone clip
- the demo prioritizes correct fail-closed behavior over never losing tracking

---

## Key implementation details

### Solve-once inference

The system avoids running OCR every frame. It solves a clean frame once, then reuses the cached solution while tracking the board plane.

### Optical-flow homography tracking

The tracker follows feature points frame-to-frame and estimates a homography with RANSAC. The solved overlay is warped into the current frame using the updated board corners.

### Fail-closed rendering

When tracking becomes implausible, the overlay is hidden rather than forced onto the wrong region.

Checks include:

- flow point count
- inlier ratio
- board area change
- corner jump
- corner quality
- minimum board area

### Grid-first discovery and segmentation fallback

When tracking is lost, the system looks for Sudoku-like board candidates using grid structure and segmentation fallback.

### Grid-corner refinement

Rough candidate corners are refined against detected Sudoku grid-line peaks before the overlay is reattached.

### Candidate stability buffer

The app does not immediately render on the first returned candidate. It waits for a short window of stable detections to avoid attaching to a moving or partially visible board.

### Known-board identity caching

After the initial solve, the app caches a board fingerprint. If the same board returns, the system can reuse the clean original solution instead of re-solving from a degraded later frame.

---

## Failure modes and limitations

This project is a portfolio demo, not a production AR app.

Known limitations:

- Works best on printed Sudoku boards with good lighting and moderate motion.
- Very fast camera movement can trigger tracking loss.
- Reacquisition may be delayed until the board is stable enough.
- New-puzzle acquisition is harder than known-board reacquisition.
- A poor crop can still cause OCR errors.
- A wrong OCR grid can produce a valid but wrong Sudoku solution if accepted from a single frame.
- Known-board identity caching helps previously solved boards but is not a general-purpose object recognition system.
- Webcam mode remains experimental.
- This is not full 3D world anchoring, visual odometry, SLAM, ARKit, or ARCore.

The intended safety behavior is:

```text
uncertain tracking or identity
→ show no overlay
```

A missing overlay is better than a confidently wrong overlay.

---

## Future work

Possible next improvements:

- Multi-frame solve confirmation for new puzzles
- Best-candidate solve ranking across a candidate cluster
- Stronger board identity model
- Lightweight template matching for faster known-board reacquisition
- Cleaner demo GIF generation
- More formal evaluation across multiple videos
- Optional mobile/native AR implementation
- Optional ARKit/ARCore prototype
- Optional full SLAM/VIO comparison

---

## Portfolio framing

This project is meant to show the practical engineering layer between a model and a usable perception product:

- model integration
- latency management
- tracking system design
- confidence gates
- failure-mode analysis
- debug instrumentation
- reproducible demo runs
- honest limitations

The core technical story:

> I took a frozen Sudoku image solver and built a markerless recorded-video planar AR overlay around it, using optical-flow homography tracking, grid refinement, stability-gated reacquisition, and known-board identity caching to produce a credible video perception demo.
