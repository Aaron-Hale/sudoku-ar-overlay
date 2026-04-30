# Sudoku AR Overlay

Live iPhone ARKit + Python FastAPI prototype that solves printed Sudoku puzzles with a companion computer-vision/OCR backend and overlays missing digits back onto the physical paper.

The current local-backend prototype solved and rendered overlays in **20 / 20 warm validation scans**, with **756.9 ms p50** and **917.2 ms p95** scan-to-overlay latency. This is a **FastAPI-backed demo**, not the final edge architecture: the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo owns the formal OCR/model evaluation and reports a frozen solver hot-path runtime of **233.2 ms mean / 239.6 ms p95**.

<p align="center">
  <img src="docs/demo/demo_preview.gif" alt="Sudoku AR Overlay demo" width="360">
</p>

[Watch the original MP4 demo](docs/demo/demo.mp4)

---

## What this project does

This app lets a user point an iPhone at a printed Sudoku puzzle, tap **Scan**, and see the missing digits displayed as a virtual AR overlay on the physical puzzle.

Current flow:

```text
iPhone AR camera
  -> captures ARFrame.capturedImage
  -> sends JPEG to local Python FastAPI backend
  -> backend calls companion sudoku-image-solver repo
  -> backend returns board corners + givens + solved grid
  -> iOS renders missing digits back onto the physical puzzle
  -> iOS posts prototype timing metrics back to /metrics
```

This repo is the **AR/mobile integration layer**. The companion ML repository is the evaluated Sudoku perception engine.

---

## Why this project exists

The project explores how a real-image Sudoku OCR system can be deployed into a live mobile AR experience. The hard part is not only reading the puzzle; it is registering the solved answer back onto the same physical paper in a way that feels anchored during handheld camera motion.

The final architecture deliberately separates concerns:

```text
Python / ML backend:
  board detection
  OCR
  Sudoku solve
  debug output
  metrics logging

iPhone / ARKit client:
  live camera
  world tracking
  mobile UI
  AR rendering
  scan-to-overlay timing
```

That split keeps the perception stack in Python for fast iteration while using ARKit for the live mobile AR layer. It also makes the production roadmap clear: the current repo proves the integration path; a future edge version should move perception on-device.

---

## Current status

> Working MVP/prototype, not a polished App Store app.

What works:

- Live iPhone AR camera view
- Physical iPhone deployment through Xcode
- Local Python FastAPI backend
- Configurable backend URL in the iOS app
- Backend health check through the app's **Ping** control
- Frame upload from iPhone to backend
- Board detection/OCR through the companion solver repo
- Sudoku solving
- Single transparent solved-board texture rendered over the puzzle
- ARKit/SceneKit anchoring and rendering
- Mobile UI with **Scan**, **Re-scan**, and **Clear**
- App-side scan metrics logging to the local backend

Known limitations:

- A Mac-hosted backend must be running locally.
- The iPhone and Mac must be on the same Wi-Fi network.
- The app works best when the puzzle is flat, stationary, visible, and well lit.
- Fast movement, blur, steep viewing angles, or moving the puzzle out of frame can cause tracking or reacquisition issues.
- `/detect` is experimental and currently reuses the full solve path.
- The app is not yet standalone or fully on-device.
- Pixel-level AR registration error and tracking/reacquisition robustness still need fuller measurement.

---

## Prototype evaluation

Formal OCR/model accuracy and frozen perception benchmarks are reported in the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo. This repo reports mobile/AR integration behavior.

These metrics come from a **warm local-backend validation run** on a physical iPhone using the Mac-hosted FastAPI service on the same Wi-Fi network. They should be read as prototype integration metrics, not as final production edge-deployment numbers.

### FastAPI demo: end-to-end AR path

| Metric | Result | Notes |
|---|---:|---|
| Scan-to-overlay success | **20 / 20** | Successful backend solve and visible AR overlay |
| p50 scan-to-overlay latency | **756.9 ms** | Tap **Scan** → AR overlay placed |
| p95 scan-to-overlay latency | **917.2 ms** | Tap **Scan** → AR overlay placed |

### Backend `/solve`: local service path

| Metric | Result | Notes |
|---|---:|---|
| p50 backend-reported latency | **501.0 ms** | Backend `/solve` reported latency |
| p95 backend-reported latency | **551.1 ms** | Backend `/solve` reported latency |

### Solver runtime: companion ML repo

| Metric | Result | Notes |
|---|---:|---|
| Frozen solver hot-path runtime | **233.2 ms mean / 239.6 ms p95** | Published in [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) |
| Formal OCR/model accuracy | See companion repo | Board accuracy, cell accuracy, and model evaluation live there |

### Measured API / app overhead

| Metric | Result | Notes |
|---|---:|---|
| Implied p50 overhead | **~255.9 ms** | p50 scan-to-overlay minus p50 backend latency |
| Implied p95 overhead | **~366.1 ms** | p95 scan-to-overlay minus p95 backend latency |

The current FastAPI demo proves the live AR + ML service boundary, but it includes local Wi-Fi, HTTP/multipart handling, JSON response handling, and app-side overlay update. A production edge implementation should remove the Wi-Fi/FastAPI dependency and the measured service-boundary overhead. Final on-device latency is not claimed here because the perception stack has not yet been converted to Core ML or benchmarked on-device.

See [`docs/metrics/prototype_metrics_summary.md`](docs/metrics/prototype_metrics_summary.md) for the full breakdown and limitations.

---

## Why ARKit instead of OpenCV tracking?

The first live tracking path tried to keep the overlay attached with image-space computer vision. That was useful for learning the failure modes, but it was not robust enough for a product-feeling handheld AR demo.

What was tried:

```text
OpenCV optical flow / KLT
  -> fast, but drifted during normal handheld motion

SIFT / ORB / KLT-style tracking
  -> closer, but still jittery and unreliable

Segmentation every frame
  -> accurate enough for detection, but too slow for smooth live anchoring

Recorded-video overlay
  -> useful debugging artifact, but not proof of a live iPhone AR product
```

The correct split is:

```text
ARKit:
  visual-inertial tracking
  camera/world pose
  anchoring
  SceneKit rendering

Python:
  board detection
  OCR
  Sudoku solve
  debug outputs
```

The project is stronger because it stopped trying to rebuild product-grade AR tracking with OpenCV and used the platform AR stack for the live anchoring layer.

---

## Rendering choice: one solution texture

Earlier versions rendered separate AR nodes for individual solved digits. That worked technically, but the result felt like many floating stickers.

The current direction renders the solved digits into **one transparent board-sized texture** and places that texture on a single board-aligned AR plane. This makes the solved answer feel more like a transparent sheet over the paper rather than a collection of separate 3D objects.

The current render path is:

```text
solution grid
  -> transparent board-space image
  -> one board-sized SceneKit plane
  -> ARKit/SceneKit overlay
```

This is a practical product decision: visual coherence matters as much as raw OCR output for an AR demo.

---

## Companion ML repository

This app uses the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo as its perception backend.

The solver repo owns the evaluated computer-vision/OCR stack:

- Board localization
- Perspective correction
- Occupancy detection
- Digit recognition
- Calibrated readout
- Frozen artifacts
- Evaluation metrics
- Failure analysis

This repo owns the AR/mobile integration layer:

- iPhone AR camera capture
- Local FastAPI service wrapper
- iOS-to-backend image upload
- ARKit anchoring
- Solved-digit rendering
- Demo UX
- Prototype integration metrics

The separation is intentional. The ML repo demonstrates the evaluated perception system; this repo demonstrates how that system can be deployed behind a local inference service and integrated into a live mobile AR prototype.

---

## Architecture

Runtime architecture:

```text
iPhone SwiftUI / ARKit client
  -> AR camera session
  -> captures ARFrame.capturedImage
  -> sends JPEG multipart upload to local FastAPI backend
  -> receives board corners + givens + solution
  -> renders transparent solved-board texture in AR
  -> posts prototype metrics to /metrics
```

```text
Python FastAPI backend
  -> receives camera frame
  -> calls local sudoku-image-solver pipeline
  -> detects board
  -> extracts givens
  -> solves Sudoku
  -> returns JSON response
  -> appends AR prototype metrics to local CSV
```

Repository layout:

```text
sudoku-ar-overlay/
  ios/
    SudokuAROverlay/
      SudokuAROverlay.xcodeproj
      SudokuAROverlay/
        ContentView.swift
        SudokuAROverlayApp.swift

  python/
    service/
      app.py
      sudoku_solver_client.py
    scripts/
      run_service.sh
      benchmark_solve_endpoint.py
      test_service_image.py
      probe_solver_direct.py

  docs/
    demo/
      demo_preview.gif
      demo.mp4
    metrics/
      prototype_metrics_summary.md

  assets/
    demo/
      test_image.jpg
```

---

## Technical highlights

- Uses `ARFrame.capturedImage` rather than a rendered screen snapshot for the solve image.
- Uses a local FastAPI backend as a clean inference-service boundary.
- Reuses an evaluated real-image OCR pipeline instead of a synthetic-only Sudoku toy model.
- Uses ARKit for live tracking instead of brittle OpenCV-only frame tracking.
- Renders solved digits as one transparent board-sized texture rather than many floating 3D text nodes.
- Logs app-side scan metrics so latency can be decomposed instead of guessed.
- Keeps the current MVP honest: local backend now, edge/on-device deployment as the production direction.

---

## Metrics and benchmarking

This repo includes two lightweight measurement paths:

```text
python/scripts/benchmark_solve_endpoint.py
  -> repeatedly calls FastAPI /solve on a fixed image
  -> isolates backend/solver service latency

POST /metrics
  -> accepts app-side scan timing metrics
  -> appends local CSV rows under assets/metrics/
```

Generated metrics under `assets/metrics/` are local runtime artifacts and are ignored by git. Curated summaries belong under `docs/metrics/`.

Example backend benchmark:

```bash
python python/scripts/benchmark_solve_endpoint.py   --image assets/demo/test_image.jpg   --warmup 3   --trials 20
```

---

## Edge deployment rationale

The current app is intentionally a local-backend prototype. That is the right shape for fast iteration while the perception stack is still Python-first.

The production direction is edge/on-device inference:

```text
iPhone camera
  -> on-device board detection / OCR
  -> local Sudoku solve
  -> AR overlay
```

Apple describes Core ML as running predictions on-device, using CPU/GPU/Neural Engine, and removing the need for a network connection when models run strictly on-device. AWS describes edge computing as moving compute closer to devices/users to improve performance, reduce bandwidth needs, and support faster real-time behavior.

References:

- [Apple Core ML documentation](https://developer.apple.com/documentation/coreml)
- [Apple Core ML overview](https://developer.apple.com/machine-learning/core-ml/)
- [AWS: What is Edge Computing?](https://aws.amazon.com/what-is/edge-computing/)

---

## Requirements

- macOS
- Xcode
- Physical iPhone
- Python 3.10+
- Local Wi-Fi shared by Mac and iPhone
- Local clone of the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo

The iOS simulator is not sufficient for the final AR camera demo. Use a physical iPhone.

---

## Quickstart

Clone both repos side by side:

```bash
mkdir -p "$HOME/projects"

cd "$HOME/projects"
git clone https://github.com/Aaron-Hale/sudoku-image-solver.git
git clone https://github.com/Aaron-Hale/sudoku-ar-overlay.git
```

Set up the AR/backend repo:

```bash
cd "$HOME/projects/sudoku-ar-overlay"

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Configure the solver repo path:

```bash
export SUDOKU_SOLVER_REPO="$HOME/projects/sudoku-image-solver"
```

Start the backend:

```bash
./python/scripts/run_service.sh
```

Or run Uvicorn directly:

```bash
PYTHONPATH=. python -m uvicorn python.service.app:app --host 0.0.0.0 --port 8000
```

Check backend health:

```bash
curl http://127.0.0.1:8000/health
```

Find your Mac Wi-Fi IP for iPhone testing:

```bash
ipconfig getifaddr en0
```

The iPhone must call the Mac's Wi-Fi IP, for example:

```text
http://<MAC_WIFI_IP>:8000
```

---

## Run the iOS app

1. Open `ios/SudokuAROverlay/SudokuAROverlay.xcodeproj` in Xcode.
2. Select a physical iPhone as the target.
3. Set your Apple signing team in Xcode if needed.
4. Build and run.
5. Use the app's **Backend** panel to set `http://<MAC_WIFI_IP>:8000`.
6. Tap **Ping** and confirm the backend is reachable.
7. Use **Scan** to solve.
8. Use **Re-scan** if the solve or tracking looks wrong.
9. Use **Clear** to remove the overlay and return to scan mode.

After the app is installed, it can run untethered from Xcode, but the current MVP still requires the Python backend to be running on the Mac.

---

## API

### `GET /health`

Checks whether the backend is running and whether the companion solver repo exists.

Example:

```bash
curl http://127.0.0.1:8000/health
```

Response shape:

```json
{
  "status": "ok",
  "solver_repo": "/path/to/sudoku-image-solver",
  "solver_repo_exists": true
}
```

### `POST /solve`

Receives an uploaded image and optional metadata.

Input:

```text
multipart/form-data
  image: JPEG/PNG image file
  metadata_json: optional JSON string
```

Response shape:

```json
{
  "status": "solved",
  "message": "solved",
  "latency_ms": 525.4,
  "confidence": 1.0,
  "image_width": 1440,
  "image_height": 1920,
  "corners_px": [[430.0, 547.5], [940.0, 537.5], [950.0, 1050.0], [440.0, 1055.0]],
  "givens": [[8, 7, 0, 6, 0, 0, 0, 0, 0]],
  "solution": [[8, 7, 9, 6, 5, 4, 1, 2, 3]],
  "givens_count": 36,
  "debug": {
    "solver_repo": "/path/to/sudoku-image-solver",
    "input_path": "assets/debug/last_input_frame.jpg",
    "corners_debug_path": "assets/debug/last_corners.jpg"
  }
}
```

### `POST /metrics`

Accepts app-side prototype metrics and appends them to a local CSV under `assets/metrics/`.

Example:

```bash
curl -X POST http://127.0.0.1:8000/metrics   -H "Content-Type: application/json"   -d '{"trial_id":"manual_test","event_source":"curl","status":"solved","total_scan_to_overlay_ms":512}'
```

### `POST /detect`

Experimental reacquisition endpoint.

Important: this currently reuses the full solver path. It is not yet a lightweight real-time board detector.

---

## What was tested and rejected

The current direction came from several failed or weaker approaches:

```text
pure OpenCV optical-flow tracking
  -> fast, but drifted under normal handheld motion

segmentation every frame
  -> accurate enough, but too slow for smooth live AR tracking

sceneView.snapshot() solve path
  -> less reliable than ARFrame.capturedImage

per-digit 3D text nodes
  -> looked floaty and visually disconnected from the paper

single transparent solved-board texture
  -> better visual fit; feels more like writing on the puzzle
```

The main product lesson was to use ARKit for live camera/world tracking and keep Python focused on perception.

---

## Remaining limits

The current prototype measures scan-to-overlay success and latency, but it does not yet fully quantify AR registration quality.

Not yet measured:

- Pixel-level overlay registration error
- Overlay jitter while stationary
- Tracking usability across a timed movement protocol
- Reacquisition success after looking away
- False-attach rate on different puzzles
- Actual Core ML / on-device latency

Current product-trust risks:

- A stale solution should never attach to a different puzzle.
- When tracking is uncertain, hiding/reacquiring is better than showing a floating or confidently wrong overlay.
- Repeated taps or overlapping solve requests can make local inference feel unstable; backend single-flight protection is still worth adding.

---

## Roadmap

Near-term hardening:

- Keep the **Ping Backend** check as a simple local-development health check.
- Add backend single-flight protection for overlapping solve requests.
- Improve user-facing errors when the backend is unreachable.
- Harden **Clear** and **Re-scan** against stale overlays.
- Add board identity checks so a stale solution cannot attach to a different puzzle.
- Add a small registration-quality benchmark using labeled screenshots.
- Keep `/detect` documented as experimental until it becomes a true lightweight detector.

Production direction:

- Move perception on-device with Core ML or another edge deployment path.
- Remove Wi-Fi/backend dependency for normal users.
- Benchmark on-device inference latency on a real iPhone.
- Keep cloud/backend inference optional for diagnostics or model improvement.
- Add confidence-gated overlay behavior.
- Improve board pose/registration using camera intrinsics and known board size.

---

## Portfolio summary

This project demonstrates end-to-end applied ML deployment judgment: a real-image Sudoku OCR solver exposed behind a local inference service, integrated into a live iPhone AR client, with explicit architecture boundaries, demo assets, prototype metrics, known limitations, and a clear productionization roadmap.

The current repo is intentionally a local-backend MVP. The next production step is edge deployment: migrating the perception stack on-device so the app can run without Wi-Fi or a Mac backend.
