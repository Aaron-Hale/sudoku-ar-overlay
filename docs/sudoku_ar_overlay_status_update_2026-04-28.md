# Sudoku AR Overlay — Status Update

**Date:** 2026-04-28  
**Project path:** `/Users/aaronhale/Desktop/sudoku-ar-overlay`  
**Current rebuild direction:** Live iPhone ARKit client + Python FastAPI solver backend  
**Current phase:** Phase 1 complete; ready to start Phase 2

---

## 1. Executive Summary

We reset the project after determining that the Python/OpenCV-only live tracking approach was not robust enough for a real live iPhone product.

The earlier recorded-video demo proved that a solved overlay could be rendered on a video, but it did **not** prove a durable live AR experience. The live OpenCV experiments repeatedly showed drift, jitter, low FPS, and failure to recover reliably under normal handheld movement.

The new architecture is now:

```text
iPhone / ARKit:
  live camera
  world tracking
  table/plane anchoring
  solved digit rendering

Python / FastAPI:
  board detection
  OCR
  Sudoku solve
  confidence/debug output
```

This keeps the project Python/MLE-centered while using ARKit for the live AR anchoring layer instead of trying to recreate product-grade AR tracking with OpenCV.

---

## 2. Hard Product Constraint

The product target is:

```text
A live iPhone AR experience that automatically detects a physical Sudoku puzzle,
solves it, and displays the missing digits as a stable overlay anchored to the real puzzle.
```

Important constraints:

```text
- Must work from live iPhone camera feed.
- No ArUco / AprilTag / QR / printed fiducial markers.
- No recorded-video-only demo.
- No more Python/OpenCV tracker rabbit holes as the primary path.
- Python remains the inference/service layer.
- iOS app should stay thin and product-focused.
- The puzzle is assumed stationary on the table after anchoring.
```

---

## 3. What We Learned From the Failed Live Tracker Path

The prior OpenCV-only live attempts were useful because they exposed the real failure modes:

| Attempt | Result |
|---|---|
| Pure optical flow / KLT | Fast, but drifted under normal movement |
| Grid refinement from tracked corners | Could not recover once corners drifted |
| SIFT / ORB / KLT hybrid tracker | Got closer, but remained jittery and unstable |
| OpenCV global grid detector | Failed to reliably detect the board live |
| Segmentation every frame | Accurate enough, but too slow for smooth live anchoring |
| Recorded-video overlay | Useful debug artifact, not a live product |

Conclusion:

```text
The problem was not one bad threshold. We were trying to build a product-grade AR tracker ourselves.
```

The correct pivot is to use ARKit for world/device tracking and anchoring.

---

## 4. Current Clean Architecture

The rebuild now has two clear components:

```text
sudoku-ar-overlay/
  python/
    service/
      app.py
      sudoku_solver_client.py
    scripts/
      test_service_image.py
      probe_solver_direct.py

  ios/
    SudokuAROverlay/      # not created yet

  assets/
    demo/
      test_image.HEIC
      test_image.jpg
    debug/
      last_input_frame.jpg
      last_corners.jpg
      last_solve_response.json

  docs/
    arkit_live_iphone_product_contract.md
```

The old AR overlay tracking code is **not** part of the new baseline.

---

## 5. Phase 1 — Python FastAPI Solver Service

### Status

**Complete.**

We created a clean Python backend that calls `sudoku-image-solver` directly.

Source of truth:

```text
/Users/aaronhale/projects/sudoku-image-solver
```

The service does not depend on the failed OpenCV live overlay code.

### Implemented files

```text
python/service/sudoku_solver_client.py
python/service/app.py
python/scripts/test_service_image.py
python/scripts/probe_solver_direct.py
```

### Service endpoints

```http
GET /health
POST /solve
```

### `/health` result

The backend correctly reports that the solver repo exists:

```json
{
  "status": "ok",
  "solver_repo": "/Users/aaronhale/projects/sudoku-image-solver",
  "solver_repo_exists": true
}
```

### `/solve` result on uploaded iPhone test image

Test image:

```text
assets/demo/test_image.jpg
```

The service returned:

```text
HTTP 200
status: solved
confidence: 1.0
image_width: 3024
image_height: 4032
givens_count: 39
corners_px: present
solution: present
```

Observed latency:

```text
latency_ms: ~1117 ms
```

That may include warmup and full-resolution image processing. Optimization is not the current priority; correctness and clean service boundaries are.

---

## 6. Backend Functional Proof

The uploaded iPhone image was successfully processed end-to-end:

```text
image -> board corners -> givens -> solution
```

The green board outline was visually aligned to the correct Sudoku puzzle.

The returned board corners were:

```json
[
  [766.5, 1911.0],
  [2016.0, 1905.75],
  [2068.5, 3244.5],
  [703.5, 3249.75]
]
```

The solver detected 39 givens and returned a full valid solution.

This is the clean backend foundation required for the ARKit client.

---

## 7. Current Backend Contract

The current `/solve` response shape is:

```json
{
  "status": "solved",
  "message": "solved",
  "latency_ms": 1117.24,
  "confidence": 1.0,
  "image_width": 3024,
  "image_height": 4032,
  "corners_px": [
    [766.5, 1911.0],
    [2016.0, 1905.75],
    [2068.5, 3244.5],
    [703.5, 3249.75]
  ],
  "givens": [[...]],
  "solution": [[...]],
  "givens_count": 39,
  "debug": {
    "device": "mps",
    "solver_repo": "/Users/aaronhale/projects/sudoku-image-solver",
    "input_path": "assets/debug/last_input_frame.jpg",
    "corners_debug_path": "assets/debug/last_corners.jpg"
  }
}
```

This is sufficient for an iPhone client to:

```text
- receive image-space board corners
- receive the solved grid
- render missing digits once world placement is solved
```

---

## 8. Important Current Limitation

The backend currently solves a still image sent to it. It does not yet do:

```text
- live frame sampling from iPhone
- automatic candidate detection
- stability gating
- ARKit world anchoring
- solved digit rendering in AR
```

Those belong to the iOS/ARKit client work beginning in Phase 2.

---

## 9. Next Phase — Minimal ARKit App

### Goal

Prove ARKit anchoring works before involving Sudoku.

The next milestone is:

```text
iPhone app opens AR camera
detects/uses a horizontal table plane
places a test 9x9 grid on the table
user moves phone away and back
grid remains anchored
```

No Sudoku solve yet.

This phase proves that ARKit solves the stability problem that OpenCV tracking failed to solve.

### Acceptance criteria

```text
- App launches on iPhone.
- AR camera opens.
- Horizontal plane/table detection works.
- A debug 9x9 grid or rectangle can be placed on the table.
- The grid remains stable as the phone moves.
- The grid persists when looking away and back.
```

### Why this comes before solver integration

If ARKit cannot place a stable test grid, there is no point wiring in Sudoku. We must prove the anchoring layer first.

---

## 10. Phase 3 Preview — iPhone to Python Service

After ARKit anchoring is proven, we wire the iPhone app to the Python service:

```text
iPhone captures camera frame
iPhone sends JPEG to http://<Mac-IP>:8000/solve
Python returns corners + givens + solution
iPhone displays debug response
```

Before doing that, confirm iPhone can hit:

```text
http://<Mac-IP>:8000/health
```

---

## 11. Phase 4 Preview — Sudoku Geometry to AR Anchor

Once the iPhone can call `/solve`, the next challenge is converting returned image-space board corners into AR world-space geometry.

Primary MVP assumption:

```text
Puzzle is flat on a horizontal table.
Puzzle remains stationary after anchoring.
```

Initial geometry plan:

```text
1. Python returns four board corners in image coordinates.
2. iOS raycasts those image points into the detected table plane.
3. Four world-space intersections define the Sudoku board plane.
4. The app renders solved digits into a 9x9 grid on that plane.
```

Fallback if corner raycasts are unreliable:

```text
- Use center raycast + known board physical size.
- Place a 9x9 board plane on the detected table.
- Improve corner-to-world mapping afterward.
```

---

## 12. Phase 5 Preview — Automatic Detection / Auto-Solve

The final UX should not be “tap Solve.”

The final state machine should be:

```text
SEARCHING
  sampling frames

CANDIDATE_FOUND
  board-like candidate appears

STABILIZING
  app waits for sharp/stable frame

SOLVING
  best frame sent to Python backend

ANCHORED
  solved digits rendered on ARKit world anchor

RETRY / FAILED
  retry automatically or expose debug retry
```

Manual solve/retry can exist as a dev tool, but not as the final demo experience.

---

## 13. Immediate Next Commands

Start the backend service:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

PYTHONPATH=. python -m uvicorn python.service.app:app --host 0.0.0.0 --port 8000
```

Confirm local service:

```bash
curl http://127.0.0.1:8000/health
```

Find Mac IP for iPhone:

```bash
ipconfig getifaddr en0
```

Then from iPhone Safari:

```text
http://<YOUR_MAC_IP>:8000/health
```

If the iPhone can see `/health`, the backend is ready for the future ARKit app.

---

## 14. Recommended Next Work Session

### Step 1

Create a minimal iOS project under:

```text
/Users/aaronhale/Desktop/sudoku-ar-overlay/ios/SudokuAROverlay
```

### Step 2

Implement only:

```text
AR session
horizontal plane detection
tap/debug-place a test 9x9 grid
```

### Step 3

Test on iPhone:

```text
move around table
look away
look back
confirm grid remains stable
```

Only after that works should we wire in `/solve`.

---

## 15. Current Risk Register

| Risk | Current status | Mitigation |
|---|---|---|
| Swift/ARKit setup friction | Not started | Keep app tiny; no polished UI |
| iPhone cannot reach Mac service | Not tested yet | Use `/health` from iPhone Safari |
| Corner-to-world mapping is tricky | Upcoming | First prove simple test grid anchor |
| Backend latency too high | Not urgent | Optimize after AR pipeline works |
| Auto-solve bad frames | Future risk | Stability gate + best-frame buffer |
| Puzzle moves after anchoring | Known limitation | MVP assumes stationary puzzle |

---

## 16. Final Portfolio Direction

The stronger final story is now:

> I built a Sudoku image solver in Python, exposed it through a FastAPI inference service, and deployed it through a thin iPhone ARKit client that automatically selects a stable frame, solves the puzzle, and renders the missing digits as a world-anchored AR overlay.

That is stronger than:

> I tuned OpenCV tracking until it almost worked.

This direction shows applied ML, service design, deployment realism, and good engineering judgment.

## 17. Phase 2 Update — ARKit Anchor Test Passed

**Date:** 2026-04-28  
**Status:** Phase 2 core anchoring proof complete  
**Device:** Personal iPhone connected through Xcode  
**Backend:** Python FastAPI service remains available from iPhone over local network

---

## 17.1 What Changed Since the Last Status Update

We successfully moved beyond backend-only validation and proved the most important AR product assumption:

```text
ARKit can place a virtual 2D grid on a real table,
keep it anchored as the iPhone moves,
and preserve the anchor when the camera looks away and back.
```

This is the exact stability behavior the Python/OpenCV live tracker could not provide.

The current iOS app is still only a minimal ARKit test shell. It does **not** solve Sudoku yet. But it proves the correct anchoring layer.

---

## 17.2 Completed Setup Work

### Xcode and iPhone development setup

The following setup steps are complete:

```text
- Xcode installed.
- Full Xcode developer directory selected.
- iPhone paired/synced with Xcode.
- Personal developer certificate trusted on iPhone.
- Minimal SwiftUI iOS app created under the project repo.
- App successfully launched on the physical iPhone.
```

The project path is:

```text
/Users/aaronhale/Desktop/sudoku-ar-overlay/ios/SudokuAROverlay
```

The app currently contains a minimal ARKit grid placement test.

---

## 17.3 Completed ARKit Proof

The test app now does the following:

```text
1. Opens the iPhone AR camera.
2. Runs ARKit world tracking.
3. Detects/uses a horizontal table plane.
4. Allows a debug tap on the table.
5. Places a virtual 9x9 grid on the table.
6. Keeps that virtual grid anchored as the user moves the phone.
7. Preserves the anchor when the user looks away and then back.
```

User validation:

```text
The virtual grid stayed on the table exactly as desired.
The grid remained stable after looking away and returning.
```

This validates the key architecture decision:

```text
Use ARKit for live world anchoring.
Use Python for Sudoku inference.
Do not continue trying to solve live AR stability with OpenCV-only tracking.
```

---

## 17.4 Why This Matters

This is the first point where the project has demonstrated the live product behavior we actually need.

Previous OpenCV approaches tried to keep the overlay attached through image-space tracking:

```text
image frame -> estimate board corners -> draw overlay -> repeat every frame
```

That produced drift, jitter, and poor recovery.

The ARKit test proves a better model:

```text
detect/anchor once
place virtual content in world space
let ARKit track the phone/world
```

For the MVP assumption — the puzzle stays stationary on the table after anchoring — this is the right product architecture.

---

## 17.5 Updated Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Clean reset | Complete | Project restarted around ARKit + Python backend |
| Phase 1 — Python solver service | Complete | `/health` and `/solve` work |
| Phase 2 — Minimal ARKit anchor app | Core proof complete | Virtual 9x9 grid anchors correctly |
| Phase 3 — iPhone to Python frame send | Next | App must call backend from iPhone |
| Phase 4 — Sudoku solve to AR anchor | Upcoming | Convert returned board geometry into AR placement |
| Phase 5 — Auto-detect / auto-solve | Upcoming | Remove user-facing solve button |
| Phase 6 — Demo polish and metrics | Upcoming | Record final live demo and document metrics |

---

## 17.6 Current Working Pieces

### Python backend

Working:

```text
GET /health
POST /solve
```

Validated behavior:

```text
- iPhone can reach backend over local network.
- Uploaded Sudoku image solves successfully.
- Backend returns board corners, givens, solution, confidence, and debug paths.
```

Backend local URL from Mac:

```text
http://127.0.0.1:8000
```

Backend LAN URL used from iPhone:

```text
http://192.168.1.74:8000
```

### iOS / ARKit client

Working:

```text
- App launches on physical iPhone.
- AR camera opens.
- Plane/table anchoring works.
- Virtual 9x9 grid remains stable.
```

Not yet working / not yet implemented:

```text
- Capturing AR camera frame.
- Sending frame to Python `/solve`.
- Receiving/decoding solve JSON.
- Mapping returned `corners_px` into world coordinates.
- Rendering solved digits on the real puzzle.
- Automatic candidate/stability gate.
```

---

## 17.7 Immediate Next Milestone

The next milestone is **Phase 3: iPhone-to-Python Solve Call**.

Goal:

```text
iPhone app captures current AR camera frame
  -> sends JPEG to Python FastAPI /solve
  -> receives JSON response
  -> displays status, latency, and givens count in the app
```

This milestone still does **not** need final Sudoku overlay geometry. It only proves the iPhone app can call the Python inference backend.

### Acceptance criteria

```text
- Backend service is running on Mac.
- iPhone app can send a camera frame to `http://192.168.1.74:8000/solve`.
- Backend returns `status: solved` or `status: failed`.
- App displays response fields:
  - status
  - latency_ms
  - givens_count
  - message
- No app crash.
```

---

## 17.8 Next Implementation Files

Likely new/updated iOS files:

```text
ios/SudokuAROverlay/SudokuAROverlay/Models.swift
ios/SudokuAROverlay/SudokuAROverlay/SolverClient.swift
ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```

Expected additions:

```text
- Codable structs matching `/solve` JSON.
- HTTP multipart image upload client.
- Debug button to capture/send current AR frame.
- On-screen debug status panel.
```

Important: the debug button is only for this engineering checkpoint. The final UX should remain automatic.

---

## 17.9 Required iOS Network Settings

The iOS app will need local-network / HTTP permissions so it can call the Mac backend.

Expected project settings needed:

```text
- NSLocalNetworkUsageDescription
- App Transport Security exception for local HTTP
```

This is because the development backend is served over local HTTP:

```text
http://192.168.1.74:8000
```

The final portfolio demo can still use local Mac backend because the MVP story is a Python inference service plus thin ARKit client.

---

## 17.10 Key Risk Now

The biggest remaining technical risk has shifted.

Old biggest risk:

```text
Can the overlay stay visually anchored during live movement?
```

Current status:

```text
Solved by ARKit anchor proof.
```

New biggest risk:

```text
Can we accurately map Python-returned image-space board corners onto the ARKit table plane?
```

That becomes Phase 4.

Before Phase 4, we should complete Phase 3 so the iPhone app can reliably get solver responses.

---

## 17.11 Updated Engineering Judgment

The ARKit pivot is now validated.

The project should continue down this path:

```text
Python solver service
+
thin iPhone ARKit client
+
world-anchored solved digit rendering
```

Do **not** return to the OpenCV tracker approach unless it is only used as a diagnostic or supporting backend component. The live anchoring responsibility now belongs to ARKit.

---

## 17.12 Next Work Session Plan

The next work session should do only this:

```text
1. Add `Models.swift`.
2. Add `SolverClient.swift`.
3. Patch iOS project network permissions.
4. Add a debug `Send Frame to Solver` button.
5. Capture the current AR frame.
6. POST it to `/solve`.
7. Display returned status/latency/givens count.
```

Stop after that works.

Do not start corner-to-world mapping until the app can call `/solve` successfully.

---

## 18. Phase 3/4 Update — Fast capturedImage Solve Path Restored and Saved

**Date:** 2026-04-28  
**Status:** Working baseline restored and checkpointed  
**Known-good checkpoint:** `docs/checkpoints/known_good_fast_capturedImage_20260428_192614/`  
**Current known-good path:** `ARFrame.capturedImage` → Python `/solve` → flat blue AR digit overlay

---

### 18.1 Summary

After several experiments with ARKit snapshot-based solving and locked-plane/per-cell geometry, we restored the faster and more reliable captured-camera-frame path.

The current working baseline uses:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> Sudoku solution JSON
  -> flat SCNPlane digit textures rendered in AR
```

This known-good state has been saved under:

```text
docs/checkpoints/known_good_fast_capturedImage_20260428_192614/
```

This checkpoint should be treated as the current recovery point before further AR alignment experiments.

---

### 18.2 What Works Now

```text
- iPhone AR app launches.
- Camera starts normally.
- Backend is reachable at the Mac LAN IP.
- Tap sends a raw AR camera frame to Python.
- Python FastAPI /solve receives the image.
- Python solver returns a solved response.
- The app displays blue solved digits.
- The app uses flat SCNPlane digit textures, not SCNText mesh digits.
- The app no longer shows yellow ARKit feature-point debug dots.
- The app no longer uses sceneView.snapshot() for the solve image.
```

The current working path is intentionally the raw camera-frame path:

```text
frame.capturedImage
```

not:

```text
sceneView.snapshot()
```

---

### 18.3 Important Lesson Learned

The `sceneView.snapshot()` path seemed attractive because screen coordinates would be easier to map back into AR view space. In practice, it made the app slower and less reliable for solving.

The more reliable path is the raw AR camera frame:

```text
ARFrame.capturedImage
```

This should remain the baseline until there is a clear reason to change it.

Large rewrites to the coordinate pipeline caused regressions. The current working approach should be preserved and improved incrementally.

---

### 18.4 Current Limitation

The overlay is working but not yet perfect.

Observed issue:

```text
The blue solved digits can still feel slightly off-plane or shift relative to the paper as the viewing angle changes.
```

Likely causes:

```text
- ARKit is anchoring to an estimated table plane.
- The printed paper/puzzle may sit slightly above the detected table plane.
- The paper may not be perfectly flat or perfectly aligned with the detected plane.
- The current image-to-world mapping remains approximate.
```

This means Phase 4 is **partially working**, not complete.

---

### 18.5 Current Engineering Rule

Do not do another large rewrite until the current working baseline is preserved.

Future changes should be:

```text
- small
- reversible
- tested one at a time
- backed up before each patch
```

The project should avoid returning to broad rewrites like:

```text
- switching back to sceneView.snapshot()
- replacing the full AR geometry pipeline at once
- changing solve capture, raycasting, and rendering in the same patch
```

---

### 18.6 Next Recommended Improvements

Next steps should be conservative:

```text
1. Keep the current capturedImage solve path.
2. Add optional visual alignment diagnostics that can be toggled on/off.
3. Add a tiny configurable plane offset, e.g. 0.5mm to 2mm.
4. Consider simple manual nudge controls for demo alignment.
5. Only after that, revisit better geometry mapping.
```

A useful next improvement is likely a small **paper-plane offset** rather than another coordinate-system rewrite.

Example idea:

```text
table plane + small upward offset
```

This may reduce the feeling that the digits are floating or sliding relative to the paper.

---

### 18.7 Current Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Python solver service | Complete | `/health` and `/solve` work |
| Phase 2 — ARKit anchor proof | Complete | Virtual grid stayed anchored on table |
| Phase 3 — iPhone to Python frame send | Complete | iPhone can POST frames to backend and receive solve response |
| Phase 4 — Manual solve to AR overlay | Partially working | Blue digits render in AR, but alignment still needs improvement |
| Phase 5 — Auto-detect / auto-solve | Not started | Keep manual tap until alignment is stable |

---

### 18.8 Known-Good Restore Procedure

To restore the current working iOS file:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"

cp docs/checkpoints/known_good_fast_capturedImage_20260428_192614/ContentView.swift \
   ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```

Then clean and rerun in Xcode:

```text
Product → Clean Build Folder
Shift + Command + K
Press Play
```

---

### 18.9 Current Recommended Baseline

The current baseline should be described as:

> A live iPhone AR prototype that sends raw AR camera frames to a Python FastAPI Sudoku solver, receives a valid solution, and renders missing digits as flat blue AR plane textures. AR anchoring works, but precise paper-plane alignment still needs tuning.

This is a meaningful working product checkpoint, but not the final MVP yet.

The next work should focus on improving placement quality without breaking the solve path.


## 19. Phase 4 Update — Single-Texture Overlay and Product UI Guidance

**Date:** 2026-04-28  
**Status:** Manual solve-to-AR overlay remains partially working; visual realism improved  
**Current working direction:** `ARFrame.capturedImage` solve path + single transparent solution texture on one AR plane  
**Current phase:** Phase 4 partially working; alignment and robustness still under active tuning

---

### 19.1 Summary

The latest useful improvement was replacing the earlier per-digit AR rendering with a **single board-sized transparent solution texture**.

The previous rendering approach created many individual AR digit planes:

```text
one SCNPlane per solved digit
```

That made the overlay feel more like separate floating AR stickers.

The newer approach renders the solved digits into one transparent board-space texture and places that texture on one board-sized `SCNPlane`:

```text
one transparent 9x9 solution texture
  -> one board-sized SCNPlane
  -> one AR board overlay
```

This made the display feel more natural and less like the digits were floating independently above the paper.

---

### 19.2 Current Known-Good Baseline

The current baseline should preserve the fast camera-frame solve path:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> Sudoku solution JSON
  -> one transparent board-sized SCNPlane solution texture
```

Important: the project should **not** return to the `sceneView.snapshot()` solve path. That path made solving slower and less reliable.

The current baseline also avoids:

```text
- SCNText 3D mesh digits
- yellow ARKit feature-point debug dots
- OpenCV optical-flow tracking as the live AR path
- per-digit AR planes as the main renderer
```

---

### 19.3 Product UI Improvement Added

A pre-solve capture guide was added.

The UI direction is now:

```text
Before solve:
  show faint corner brackets

User action:
  fit puzzle inside brackets
  tap once

During solve:
  hide the brackets

After solve:
  show only the blue solution overlay

On failure:
  show the guide again for retry
```

This is better than a full 9x9 grid because it guides the user without implying that exact grid detection has already happened.

The current guide is intentionally screen-space UI. Since the app sends `ARFrame.capturedImage` rather than `sceneView.snapshot()`, the UI guide should not be included in the solver image.

---

### 19.4 What Worked

The current live prototype can now demonstrate:

```text
- iPhone AR app opens live camera.
- User frames a physical Sudoku puzzle.
- User taps to solve.
- iPhone sends a raw AR camera frame to the local Python FastAPI backend.
- Python detects the board, OCRs givens, solves the Sudoku, and returns JSON.
- iOS renders the missing digits as one transparent blue board texture.
- The display feels more coherent than the earlier separate-digit AR node version.
```

The single-texture overlay is a meaningful improvement because the solved digits now behave visually like one transparent sheet instead of many separate AR objects.

---

### 19.5 What Got Worse / What Was Reverted

A texture-space inset calibration was tested:

```text
draw solved digits inside the inner ~94% of the board texture
```

That made alignment worse and was reverted.

Conclusion:

```text
The main remaining issue is not solved by shrinking/insetting the digit layout.
The main remaining issue is board pose / corner / plane registration.
```

The current no-inset single-texture version appears better than the inset version.

---

### 19.6 Current Limitation

The overlay is improved, but not finished.

Observed issue:

```text
At some angles, the display still appears slightly lifted or not perfectly locked to the paper.
Sometimes the solved digits do not line up exactly with the printed grid cells.
```

Most likely causes:

```text
- ARKit is anchoring to an estimated table plane rather than the exact paper/puzzle plane.
- The paper is slightly above the table plane.
- The paper may be warped, tilted, or not perfectly flat.
- Returned board corners may not exactly match the true printed Sudoku grid corners.
- Current 2D image-corner to AR-world mapping remains approximate.
```

The product is now good enough for a technical demo, but not yet at the final “rock-solid paper registration” level.

---

### 19.7 Backend / Request Stability Finding

During testing, the backend sometimes appeared stuck or stale. The important finding was that the local FastAPI service has no intentional request cap, but repeated taps or overlapping solve requests can make local inference feel unstable.

Recommended backend hardening:

```text
- Add a server-side single-flight solve lock.
- If a solve is already running, return a fast `busy` response.
- Add request IDs and timestamps to debug artifacts.
- Ensure each solve writes fresh debug files.
```

Recommended iOS hardening:

```text
- Ignore taps while `isSolving == true`.
- Add a visible cancel button for long-running solves.
- Keep a URL timeout around 10–12 seconds.
```

This should prevent request pileups and make debugging less confusing.

---

### 19.8 Current Architecture Explanation

The current app does **not** use optical flow for live tracking.

Current pipeline:

```text
ARKit:
  visual-inertial tracking
  camera pose estimation
  table/plane estimation
  raycasting
  SceneKit rendering

Python:
  board segmentation
  OCR
  Sudoku solve
  JSON response

iOS rendering:
  transparent solution texture on one AR plane
```

In short:

> Python solves the puzzle once; ARKit tracks the phone/world; SceneKit renders a transparent solved-board texture in world space.

The old OpenCV approach used image-space tracking and homography-style overlay. That helped the overlay look good in a frame, but it was not robust enough for live handheld motion.

---

### 19.9 Updated Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Python solver service | Complete | `/health` and `/solve` work |
| Phase 2 — ARKit anchor proof | Complete | ARKit table anchoring worked and survived look-away/look-back |
| Phase 3 — iPhone to Python frame send | Complete | iPhone can POST raw AR camera frames to backend |
| Phase 4 — Manual solve to AR overlay | Partially working | Single texture overlay improves realism; alignment still imperfect |
| Phase 5 — Auto-detect / auto-solve | Not started | Keep manual tap until placement is more reliable |
| Phase 6 — Demo polish and metrics | In progress | A screen-recorded demo should be captured while current version works |

---

### 19.10 Recommended Next Steps

Do **not** do another large rewrite immediately.

Next steps should be small and reversible:

```text
1. Save a new checkpoint for the no-inset single-texture overlay version.
2. Record a short screen demo while the current version is working.
3. Add backend single-flight protection to prevent overlapping solve requests.
4. Add cancel/timeout behavior in the iOS app.
5. Add optional diagnostic overlay to show detected board corners/plane.
6. Improve board registration through better corners or board-specific anchoring.
```

The highest-value future technical improvement is likely:

```text
dynamic board/image anchoring
```

or:

```text
proper board pose estimation using detected corners + camera intrinsics + known physical board size
```

But those should be experiments off the preserved working baseline, not replacements made directly on the current working file.

---

### 19.11 Current Portfolio Description

The current honest portfolio description is:

> A live iPhone AR prototype that sends raw AR camera frames to a Python FastAPI Sudoku solver, receives board corners and a solved grid, and renders the missing digits as one transparent AR solution texture over the physical puzzle. ARKit provides visual-inertial world tracking and rendering, while Python handles board detection, OCR, and Sudoku solving. The prototype demonstrates end-to-end live solve and AR overlay; precise paper-plane alignment remains under active tuning.

This is a credible applied ML + AR deployment story, as long as the limitations are stated clearly.

