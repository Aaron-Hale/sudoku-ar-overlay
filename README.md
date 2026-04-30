# Sudoku AR Overlay

Live iPhone ARKit + Python FastAPI prototype that solves printed Sudoku puzzles with a companion computer-vision/OCR backend and overlays missing digits back onto the physical paper.

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
```

This repo is the **AR/mobile integration layer**. The companion ML repository is the evaluated Sudoku perception engine.

---

## Current status

> Working MVP/prototype, not a polished App Store app.

What works:

- Live iPhone AR camera view
- Physical iPhone deployment through Xcode
- Local Python FastAPI backend
- Frame upload from iPhone to backend
- Board detection/OCR through the companion solver repo
- Sudoku solving
- Single transparent solved-board texture rendered over the puzzle
- ARKit image anchoring for improved alignment
- Mobile UI with **Scan**, **Re-scan**, and **Clear**

Known limitations:

- A Mac-hosted backend must be running locally.
- The iPhone and Mac must be on the same Wi-Fi network.
- The backend URL is currently a local-network development setting.
- The app works best when the puzzle is flat, stationary, visible, and well lit.
- Fast movement, blur, steep viewing angles, or moving the puzzle out of frame can cause tracking or reacquisition issues.
- `/detect` is experimental and currently reuses the full solve path.
- The app is not yet standalone or fully on-device.

---

## Prototype metrics

Formal OCR/model accuracy is reported in the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo. This repo reports mobile/AR integration behavior.

Warm local-backend validation run:

| Metric | Result | Notes |
|---|---:|---|
| Scan-to-overlay success | **20 / 20** | Same local setup, measured after backend warmup |
| p50 scan-to-overlay latency | **756.9 ms** | Tap **Scan** → AR overlay placed |
| p95 scan-to-overlay latency | **917.2 ms** | Tap **Scan** → AR overlay placed |
| p50 backend-reported latency | **501.0 ms** | Backend `/solve` reported latency |
| p95 backend-reported latency | **551.1 ms** | Backend `/solve` reported latency |
| p50 capture + JPEG encode | **23.0 ms** | iPhone frame capture/encode path |
| p50 overlay placement | **18.1 ms** | JSON decoded → AR overlay placed |

These are prototype integration metrics from a warm local-backend run, not formal OCR/model benchmarks and not yet a full multi-condition AR tracking benchmark. See [`docs/metrics/prototype_metrics_summary.md`](docs/metrics/prototype_metrics_summary.md) for details.

---

## Why this project is interesting

This project combines a real-image Sudoku OCR engine with a live mobile AR interface. The product problem is not only reading a puzzle from a camera frame, but also registering the solved answer back onto the same physical paper in a way that feels anchored during handheld camera motion.

The important engineering split is:

```text
Python / ML backend:
  board detection
  OCR
  Sudoku solve
  debug output

iPhone / ARKit client:
  live camera
  world tracking
  mobile UI
  AR rendering
```

That split keeps the perception system in Python for fast iteration while using ARKit for the live mobile AR layer.

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

The separation is intentional. The ML repo demonstrates the evaluated perception system; this repo demonstrates how that system can be deployed behind a local inference service and integrated into a live mobile AR prototype.

---

## Architecture

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
      test_service_image.py
      probe_solver_direct.py

  docs/
    demo/
      demo_preview.gif
      demo.mp4

  assets/
    demo/
      test_image.jpg
```

Runtime architecture:

```text
iPhone SwiftUI / ARKit client
  -> AR camera session
  -> captures ARFrame.capturedImage
  -> sends JPEG multipart upload to local FastAPI backend
  -> receives board corners + givens + solution
  -> renders transparent solved-board texture in AR
```

```text
Python FastAPI backend
  -> receives camera frame
  -> calls local sudoku-image-solver pipeline
  -> detects board
  -> extracts givens
  -> solves Sudoku
  -> returns JSON response
```

---

## Technical highlights

- Uses `ARFrame.capturedImage` rather than a rendered screen snapshot for the solve image.
- Uses a local FastAPI backend as a clean inference-service boundary.
- Reuses an evaluated real-image OCR pipeline instead of a synthetic-only Sudoku toy model.
- Uses ARKit for live tracking instead of brittle OpenCV-only frame tracking.
- Renders solved digits as one transparent board-sized texture rather than many floating 3D text nodes.
- Keeps the current MVP honest: local backend now, edge/on-device deployment as the production direction.

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
4. Use the app's **Backend** panel to set `http://<MAC_WIFI_IP>:8000`, then tap **Ping**.
5. Build and run.
6. Use **Scan** to solve.
7. Use **Re-scan** if the solve or tracking looks wrong.
8. Use **Clear** to remove the overlay and return to scan mode.

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

## Roadmap

Near-term cleanup and hardening:

- Keep the in-app backend setting simple and add local discovery if needed.
- Add a **Ping Backend** check in the app.
- Improve user-facing errors when the backend is unreachable.
- Harden **Clear** and **Re-scan** against stale overlays.
- Keep `/detect` documented as experimental until it becomes a true lightweight detector.

Production direction:

- Move perception on-device with Core ML or another edge deployment path.
- Remove Wi-Fi/backend dependency for normal users.
- Keep cloud/backend inference optional for diagnostics or model improvement.
- Add confidence-gated overlay behavior.
- Improve board pose/registration using a more robust geometry path.

---

## Portfolio summary

This project demonstrates end-to-end applied ML deployment judgment: a real-image Sudoku OCR solver exposed behind a local inference service, integrated into a live iPhone AR client, with explicit architecture boundaries, demo assets, known limitations, and a clear productionization roadmap.

The current repo is intentionally a local-backend MVP. The next production step is edge deployment: migrating the perception stack on-device so the app can run without Wi-Fi or a Mac backend.
