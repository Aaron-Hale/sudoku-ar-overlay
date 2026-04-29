# Sudoku AR Overlay — Live iPhone Product Rebuild Contract

## Purpose

This document resets the project around the product that actually matters:

> A live iPhone AR experience that automatically detects a physical Sudoku puzzle, solves it, and displays the missing digits as a stable overlay anchored to the real puzzle on a table.

This is not a recorded-video demo contract. Recorded video may be used later for regression tests and portfolio evidence, but it is not the product.

The live test device is:

```text
iPhone live camera feed
Mac as development machine
Python backend on Mac for solver/inference
Thin iOS/ARKit client for camera, AR tracking, and rendering
```

---

## Hard Decision

We are stopping the Python/OpenCV-only live tracking path as the primary product route.

### Why

The prior OpenCV experiments showed:

```text
Pure optical flow:
  fast, but drifts under normal movement

Grid refinement:
  unable to recover once the tracker drifts away

SIFT/ORB/KLT reference matching:
  closer, but still jittery and not stable enough

OpenCV global grid detection:
  not reliable enough live

Segmentation every frame:
  accurate enough, but too slow for smooth live anchoring
```

This means the failure is not one bad parameter. The core problem is that we were trying to build a product-grade AR tracking stack ourselves.

### New product architecture

Use the right tool for the right layer:

```text
ARKit:
  live camera
  device/world tracking
  anchors
  rendering

Python:
  Sudoku board detection
  OCR
  solve
  confidence scoring
  metrics/debug artifacts
```

The Python solver remains the core ML/MLE asset. ARKit is the deployment shell that handles live AR anchoring.

---

## Non-Negotiable Product Constraints

1. **Must run on live iPhone camera feed.**
2. **No ArUco, AprilTag, QR, or printed fiducial markers.**
3. **No recorded-video-only claim.**
4. **No more OpenCV tracker rabbit holes as the primary path.**
5. **No “tap Solve” as the final user experience.**
6. **Manual controls are allowed only as debug fallback.**
7. **The product assumes the puzzle is stationary on a table after detection.**
8. **If the puzzle moves while out of frame, we do not claim tracking continuity.**
9. **Python remains the inference/evaluation/service layer.**
10. **The iOS app must stay thin and product-focused.**

---

## Final User Experience

The target user flow:

```text
1. User opens the iPhone app.
2. App shows live AR camera view.
3. User points at a physical Sudoku puzzle lying flat on a table.
4. App automatically detects a candidate board.
5. App waits briefly for a stable/sharp frame.
6. App sends the best frame to the Python solver.
7. Python returns:
   - givens
   - solution
   - board corners in image coordinates
   - confidence
   - latency
8. iOS client places solved digits on an ARKit world anchor.
9. User can move the iPhone normally.
10. Overlay remains stable because ARKit tracks the phone/world.
11. If user looks away and back, overlay remains in the remembered world position, assuming the puzzle stayed still.
```

Debug fallback:

```text
Manual Solve / Retry button may exist in dev mode only.
```

The portfolio demo should feel automatic:

```text
Scanning...
Board found
Hold steady
Solving
Solved
```

---

## Core Technical Bet

For a stationary puzzle on a table, the right abstraction is:

```text
detect board once
anchor solved overlay in world space
track camera/world with ARKit
```

Not:

```text
track board corners forever in image space using OpenCV
```

The previous approach tried to keep the overlay attached by continuously estimating image-space homographies. The new approach places the overlay into AR world coordinates and lets ARKit handle device/world tracking.

---

## Architecture

### High-level architecture

```text
iPhone ARKit App
  |
  | live AR camera frames
  v
Auto-capture / stability gate
  |
  | selected best frame
  v
Python FastAPI Solver Service
  |
  | strict JSON response
  v
ARKit world anchor + overlay renderer
```

### Repo structure

Recommended structure after reset:

```text
sudoku-ar-overlay/
  README.md

  docs/
    arkit_live_product_contract.md
    architecture.md
    api_contract.md
    metrics.md
    limitations.md

  python/
    service/
      app.py
      schemas.py
      solver_client.py
    scripts/
      run_service.sh
      test_service_image.py
    tests/

  ios/
    SudokuAROverlay/
      SudokuAROverlay.xcodeproj
      SudokuAROverlay/
        ARViewController.swift
        SolverClient.swift
        AutoCaptureStateMachine.swift
        BoardAnchorRenderer.swift
        Models.swift

  assets/
    demo/
    debug/
```

If we keep the existing Python package layout from the current repo, that is fine, but the intent should be clear:

```text
Python = inference service and evaluation
iOS = thin AR client
```

---

## System Components

### 1. Python FastAPI Solver Service

Responsibilities:

```text
- Accept image frame from iPhone.
- Run existing Sudoku image solver.
- Return strict JSON with:
  - status
  - solution
  - givens
  - board corners in image coordinates
  - confidence
  - latency
  - error/debug fields
- Save debug artifacts for failures.
```

Endpoint:

```http
GET /health
POST /solve
```

Request:

```text
image: JPEG/PNG frame from iPhone
metadata_json:
  camera frame width/height
  timestamp
  optional ARKit intrinsics/camera transform
```

Response:

```json
{
  "status": "solved",
  "message": "",
  "latency_ms": 342.5,
  "confidence": 0.91,
  "image_width": 1920,
  "image_height": 1080,
  "corners_px": [
    [385.0, 295.0],
    [967.5, 307.5],
    [950.0, 842.5],
    [282.5, 820.0]
  ],
  "givens": [[0,0,3,0,0,0,0,0,0]],
  "solution": [[1,2,3,4,5,6,7,8,9]],
  "debug": {
    "segmentation_ms": 270.0,
    "ocr_ms": 35.0,
    "sudoku_solve_ms": 2.0,
    "givens_count": 39
  }
}
```

Failure response:

```json
{
  "status": "failed",
  "message": "Solver could not find a valid solution from predicted givens.",
  "latency_ms": 315.0,
  "confidence": 0.0,
  "corners_px": null,
  "givens": null,
  "solution": null,
  "debug": {
    "reason": "bad_ocr_or_blur",
    "saved_frame_path": "assets/debug/last_failed_solve.jpg"
  }
}
```

---

### 2. iOS ARKit Client

Responsibilities:

```text
- Run ARKit world tracking session.
- Show live camera feed.
- Maintain auto-capture state machine.
- Send best frame to Python service.
- Receive solution/corners.
- Convert image-space board geometry into AR world-space placement.
- Render solved digits on the board plane.
- Persist overlay as an AR anchor while the puzzle remains stationary.
```

Thin-client rule:

```text
Do not put Sudoku inference logic in Swift for MVP.
Do not convert models to Core ML for MVP.
Do not build a polished consumer UI before anchoring works.
```

---

### 3. Auto-Capture State Machine

Final flow:

```text
SEARCHING
  App samples frames and looks for candidate board signals.

CANDIDATE_FOUND
  Board-like candidate appears.

STABILIZING
  App waits until recent frames are stable/sharp enough.

SOLVING
  App sends best buffered frame to Python solver.

ANCHORED
  App renders solved digits on AR world anchor.

RETRY / FAILED
  App waits for another stable candidate or allows manual debug retry.
```

MVP may start with a debug button internally, but the demo target is automatic.

---

### 4. Board-to-World Anchor Placement

Primary MVP assumption:

```text
Puzzle lies flat on a horizontal table.
Puzzle stays stationary after anchoring.
```

Recommended MVP geometry:

```text
1. Python returns board corners in image coordinates.
2. iOS uses ARKit raycasting from those image points.
3. Raycast intersects the detected/estimated horizontal table plane.
4. Four 3D world points define the board plane.
5. Solved digits are placed as small text/plane nodes in a 9x9 grid on that plane.
```

Fallback geometry if raycasting all four corners fails:

```text
- Use center raycast to table plane.
- Use known physical board width/height.
- Use camera orientation and image-corner geometry to estimate board transform.
```

Future stronger approach:

```text
- Known physical puzzle size.
- Camera intrinsics.
- solvePnP / plane pose estimation.
```

But MVP should start with table-plane raycast because it is conceptually simplest.

---

## Out of Scope for MVP

These are explicitly not part of the first rebuild:

```text
- ArUco / AprilTag / QR markers
- ORB-SLAM
- Visual odometry integration
- Core ML model conversion
- Fully standalone offline mobile inference
- Multiple simultaneous puzzles
- Puzzle moving while out of frame
- Perfect consumer UI polish
- Recorded-video-only demo
- More Python/OpenCV markerless tracking experiments as primary path
```

---

## Why Not ORB-SLAM?

ORB-SLAM is not the fastest recovery path for this product.

It would add:

```text
- camera calibration
- monocular scale ambiguity
- C++ build complexity
- custom object anchoring
- custom rendering
- map/relocalization management
```

It still would not solve:

```text
- Sudoku board detection
- OCR
- Sudoku solving
- iPhone app deployment
- product UI
```

ARKit already provides the phone/world tracking layer on the actual target device.

---

## Why Not ArUco / AprilTag?

Fiducials would make planar tracking much easier, but the product constraint is:

```text
normal Sudoku puzzle, no printed code next to it
```

So marker-assisted tracking is not acceptable for the main product.

It can remain a future engineering fallback or diagnostic baseline, but not the demo target.

---

## MVP Acceptance Criteria

The first acceptable product demo must show:

```text
1. iPhone app opens live AR camera.
2. App automatically detects/stabilizes on a Sudoku puzzle.
3. App sends a selected frame to Python service.
4. Python returns a valid solution and board corners.
5. Solved digits appear on the physical puzzle.
6. User moves the iPhone normally around the table.
7. Overlay stays fixed to the puzzle plane.
8. User looks away and back.
9. Overlay remains in the correct world location, assuming puzzle did not move.
10. Debug metrics are saved.
```

Minimum measurable bar:

| Metric | MVP Target |
|---|---:|
| Auto-capture time after board visible | <= 2 sec |
| Python solve latency | <= 750 ms acceptable, <= 400 ms preferred |
| AR render FPS | native smooth ARKit feel |
| Wrong overlay placement | 0 tolerated |
| Overlay persistence after looking away/back | works in demo |
| Manual debug retry | available |
| No fiducial marker | required |

---

## Phased Roadmap

## Phase 0 — Clean Reset

### Goal

Start from a clean Desktop folder and create a new contract-driven project.

### Actions

```text
- Delete current Desktop working folder contents.
- Keep only this contract initially.
- Pull/copy only the previous resources needed:
  - existing Python solver adapter
  - existing frozen solver dependency
  - docs if helpful
- Do not bring over failed OpenCV live tracker experiments.
```

### Pass condition

```text
Desktop repo contains a clean contract and no accidental failed-tracker state.
```

---

## Phase 1 — Python Solver Service

### Goal

Expose the working Sudoku solver through a stable HTTP API.

### Deliverables

```text
python/service/app.py
python/service/schemas.py
python/scripts/run_service.sh
python/scripts/test_service_image.py
```

### Endpoint

```http
GET /health
POST /solve
```

### Acceptance test

Run service:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate
python -m uvicorn python.service.app:app --host 0.0.0.0 --port 8000
```

Test image:

```bash
python python/scripts/test_service_image.py   --image path/to/sample_sudoku.jpg   --url http://localhost:8000/solve
```

Pass condition:

```text
Service returns solved JSON with corners, givens, solution, latency, confidence.
```

---

## Phase 2 — Minimal ARKit App

### Goal

Create the smallest possible iPhone app that runs ARKit and displays a test overlay.

### Deliverables

```text
ios/SudokuAROverlay/
  Xcode project
  ARViewController.swift
  BoardAnchorRenderer.swift
```

### Behavior

```text
- App launches on iPhone.
- AR session starts.
- App detects/uses horizontal plane.
- App can place a test 9x9 board/text grid on the plane.
```

### Acceptance test

```text
Open app on iPhone.
Point at table.
Tap/debug-place a test grid.
Move phone.
Grid stays on table.
Look away/back.
Grid remains anchored.
```

This phase proves ARKit anchoring solves the stability problem before Sudoku is involved.

---

## Phase 3 — iPhone to Python Frame Send

### Goal

Let the iPhone send a captured AR camera frame to the Python service.

### Deliverables

```text
SolverClient.swift
Models.swift
Python /solve endpoint tested from iPhone
```

### Behavior

```text
- App captures current camera frame.
- App sends JPEG to Mac FastAPI service.
- App receives JSON.
- App displays solve status and latency.
```

### Acceptance test

```text
iPhone and Mac on same network.
Python service running on Mac.
iPhone app successfully calls /solve.
Response visible in app debug overlay.
```

---

## Phase 4 — Manual Debug Solve to AR Anchor

### Goal

Use a debug button to prove the end-to-end geometry.

This is not the final UX. It is an engineering checkpoint.

### Behavior

```text
- User points at puzzle.
- Debug solve is triggered.
- Python returns board corners and solution.
- iOS raycasts corners into table plane.
- App places solved digits on board plane.
- Overlay remains stable as user moves phone.
```

### Acceptance test

```text
Solved digits appear near correct cells.
Overlay is world-stable.
Looking away/back preserves placement.
```

Important:

```text
This phase may use a debug button because the goal is geometry validation, not final UX.
```

---

## Phase 5 — Automatic Candidate / Stability Gate

### Goal

Remove the user-facing solve button.

### Behavior

```text
App continuously samples frames.
App runs lightweight candidate checks.
App buffers recent frames.
When board appears stable, app sends best frame to solver automatically.
```

### Stability gate features

```text
- recent frame sharpness
- low inter-frame motion
- board/corner confidence returned by backend
- area large enough
- solve succeeds with valid Sudoku
```

### Practical MVP strategy

To avoid running the full solver too often:

```text
1. iOS samples frames at low frequency, e.g. 2 FPS.
2. Backend has cheap detect-only mode or solve mode.
3. Once detect-only confidence is high and stable, backend runs full solve.
```

If detect-only mode is not available immediately:

```text
Send candidate frames every ~0.5–1.0 sec until a valid solve returns.
```

### Acceptance test

```text
No user tap.
App detects board automatically.
App solves automatically after brief hold.
```

---

## Phase 6 — Demo Polish and Metrics

### Goal

Produce an honest demo artifact.

### Required demo

```text
Open app.
Point at puzzle.
App auto-solves.
Solved digits appear.
Move around table.
Look away/back.
Overlay persists.
```

### Metrics

```text
- time from board visible to solve request
- solve latency
- total time to overlay
- number of failed solve attempts
- AR tracking state
- anchor placement success/failure
```

### Artifacts

```text
assets/demo/arkit_live_mvp.mp4
docs/metrics.md
docs/architecture.md
```

---

## Risk Register

### Risk 1 — Swift/ARKit setup takes longer than expected

Mitigation:

```text
Keep iOS app tiny.
No polished UI.
No local inference.
No Core ML.
Use basic ARKit/SceneKit or RealityKit rendering.
```

### Risk 2 — Raycasting image corners to table plane is tricky

Mitigation:

```text
Start with center + known physical board size.
Then improve corner-based placement.
Use debug visualization of corner rays and anchor plane.
```

### Risk 3 — Python service call from iPhone has network friction

Mitigation:

```text
Use Mac and iPhone on same Wi-Fi.
Use Mac local IP address.
Expose /health endpoint.
Add connection status in app.
```

### Risk 4 — Auto-solve triggers on bad frames

Mitigation:

```text
Require solve confidence.
Require valid Sudoku solution.
Keep recent frame buffer.
Only accept stable frame.
Allow automatic retry.
```

### Risk 5 — Puzzle moves after anchoring

Mitigation:

```text
State limitation clearly:
MVP assumes puzzle remains stationary after solve.
If puzzle moves, user resets/re-solves.
```

---

## Recommended Timeline

This is the fastest credible recovery plan.

### Day 1

```text
Build Python FastAPI /solve service.
Test service on stored images.
```

### Day 2

```text
Create minimal ARKit app.
Show AR camera.
Place test grid/text on table plane.
Confirm look-away/look-back stability.
```

### Day 3

```text
Send iPhone frame to Python service.
Receive solve JSON.
Display debug response.
```

### Day 4

```text
Convert returned board geometry into AR world placement.
Render solved digits on board plane.
```

### Day 5

```text
Replace debug solve with automatic stability gate.
Add retry logic.
```

### Day 6–7

```text
Polish demo.
Record live iPhone demo.
Document architecture and metrics.
```

Realistic range:

```text
Best case: 5–7 focused days.
If Xcode/ARKit geometry fights us: 1–2 weeks.
If we try to make it fully polished/standalone: several weeks.
```

---

## Stop Conditions

Stop and reassess if any of these happen:

```text
- ARKit plane anchoring cannot place a test grid stably on the table.
- iPhone cannot reliably send frames to Python service.
- Corner-to-world mapping is not accurate enough after two focused days.
- Solver confidence on iPhone frames is poor even with stable capture.
```

If a stop condition occurs, the fallback is:

```text
Python service + static iPhone capture demo
or
Core ML/export investigation
or
accept this project as static-image MLE portfolio rather than AR product.
```

---

## Final Portfolio Story After Success

The finished story should be:

> I built a Sudoku image solver in Python, then deployed it through a live iPhone AR prototype. The app automatically detects a physical Sudoku puzzle, selects a stable frame, calls a Python inference service for board detection/OCR/solve, and renders the missing digits as an ARKit world-anchored overlay that remains stable as the user moves around the table.

This is a better story than:

> I tuned OpenCV optical flow until it almost worked.

It shows applied ML, product judgment, service design, and deployment realism.

---

## Final Warning

The goal is not to build a fancy mobile app.

The goal is to use a thin ARKit client to make the live AR anchoring reliable, while keeping the ML/inference system Python-first.

Do not let Swift UI polish, Core ML conversion, or iOS app architecture sprawl take over the project.
