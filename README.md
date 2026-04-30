# Sudoku AR Overlay

Live iPhone AR prototype that scans a physical Sudoku puzzle, solves it with a local Python backend, and overlays the missing digits back onto the real puzzle using ARKit.

![Demo preview](docs/demo/demo_preview.gif)

[Watch the original MP4 demo](docs/demo/demo.mp4)

---

## What this project does

The app lets a user point an iPhone at a printed Sudoku puzzle, tap **Scan**, and see the missing digits displayed as a virtual overlay on the physical puzzle.

Current mobile flow:

- **Launch app:** corner guide appears.
- **Tap Scan:** app captures the current AR camera frame and sends it to the local Python FastAPI backend.
- **Backend solve:** backend detects the Sudoku board, reads givens, solves the puzzle, and returns board corners plus the solution.
- **AR overlay:** iOS renders the missing digits over the physical puzzle.
- **Tap Re-scan:** solves again if the lock or solution looks wrong.
- **Tap Clear:** removes the virtual solution and returns to scan mode.

---

## Current status

This is a working MVP/prototype, not a polished App Store app.

What works:

- Live iPhone AR camera view
- Physical iPhone deployment through Xcode
- Local Python FastAPI backend
- Sudoku board detection through the existing solver repo
- OCR/givens extraction
- Sudoku solving
- Single transparent solution texture rendered over the puzzle
- ARKit image anchoring for improved alignment
- Mobile UI with **Scan**, **Re-scan**, and **Clear**

Known limitations:

- The Mac backend must be running locally.
- The iPhone and Mac must be on the same Wi-Fi network.
- The backend IP is currently hardcoded in Swift.
- Tracking is best when the puzzle is visible, well lit, and the phone moves slowly.
- Fast movement, blur, steep viewing angles, or moving the puzzle out of frame can cause reacquisition issues.
- The app assumes the puzzle is flat and stationary after scanning.

---

## Architecture

```text
iPhone SwiftUI / ARKit client
  -> AR camera session
  -> captures ARFrame.capturedImage
  -> sends JPEG to local FastAPI backend
  -> receives board corners + givens + solution
  -> renders a solved-board texture in AR
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

The project deliberately keeps the computer vision and solving layer in Python for fast iteration while using ARKit for mobile camera, tracking, and rendering.

---

## Repo layout

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

---

## Requirements

- macOS
- Xcode
- Physical iPhone
- Python virtual environment
- Local Wi-Fi shared by Mac and iPhone
- Existing local Sudoku solver repo at `/Users/aaronhale/projects/sudoku-image-solver`

The backend expects that solver repo to exist locally.

---

## Start the backend

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

PYTHONPATH=. python -m uvicorn python.service.app:app --host 0.0.0.0 --port 8000
```

Or use the helper script:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

./python/scripts/run_service.sh
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

Find your Mac Wi-Fi IP:

```bash
ipconfig getifaddr en0
```

The iOS app currently uses a hardcoded backend URL in:

```text
ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```

Look for:

```swift
let baseURL = URL(string: "http://<MAC_IP>:8000")!
```

Update it if your Mac IP changes.

---

## Run the iOS app

1. Open `ios/SudokuAROverlay/SudokuAROverlay.xcodeproj` in Xcode.
2. Select a physical iPhone as the target.
3. Build and run.
4. Use **Scan** to solve.
5. Use **Clear** to remove the virtual solution and return to scan mode.

---

## API

### `GET /health`

Checks whether the backend is running and whether the local solver repo exists.

Example:

```bash
curl http://127.0.0.1:8000/health
```

Expected response shape:

```json
{
  "status": "ok",
  "solver_repo": "/Users/aaronhale/projects/sudoku-image-solver",
  "solver_repo_exists": true
}
```

### `POST /solve`

Receives an uploaded image and optional metadata.

Returns board corners, detected givens, solved grid, latency, and debug paths.

Example response shape:

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
    "solver_repo": "/Users/aaronhale/projects/sudoku-image-solver",
    "input_path": "assets/debug/last_input_frame.jpg",
    "corners_debug_path": "assets/debug/last_corners.jpg"
  }
}
```

---

## Technical notes

The app uses:

- `ARFrame.capturedImage` for the camera frame
- multipart upload to FastAPI
- one transparent solution texture for all solved digits
- ARKit image anchoring for alignment
- SwiftUI controls for scan, rescan, clear, and status

The solution overlay intentionally avoids `SCNText` meshes because 3D text appeared too floaty and visually disconnected from the paper.

---

## What was tested

What worked best:

```text
ARFrame.capturedImage
+ Python solver backend
+ single transparent solution texture
+ dynamic ARKit image anchoring
```

What was tested and rejected:

```text
pure OpenCV optical-flow tracking
per-digit 3D text nodes
large texture inset calibration
persistent stale image-anchor pose
quick solvePnP pose-estimated world anchor
heavy reacquisition loop using the full solver path
```

---

## Roadmap

High-value next improvements:

- Replace hardcoded backend IP with in-app settings or local discovery.
- Add a lightweight board-detection-only endpoint for faster reacquisition.
- Improve board identity checks to prevent old solutions attaching to new puzzles.
- Improve ARKit reference-image crop quality.
- Add optional debug overlay for detected board corners.
- Package backend dependencies more cleanly.
- Move more perception on-device if targeting a standalone mobile app.

---

## Portfolio summary

This project demonstrates applied computer vision, OCR-backed puzzle understanding, FastAPI inference service design, SwiftUI/ARKit mobile development, AR rendering, and product-minded iteration through real failure modes.

The current result is a credible live AR prototype that solves a real physical Sudoku puzzle and overlays the missing digits back onto the paper.
