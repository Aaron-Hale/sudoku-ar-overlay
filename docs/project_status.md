# `sudoku-ar-overlay` Project Status Log

**Last updated:** 2026-04-24  
**Purpose:** This file summarizes what has been completed so far in the `sudoku-ar-overlay` project so future work can continue from the right context without re-discovering prior setup, fixes, or decisions.

---

## 1. Project Goal

`sudo​ku-ar-overlay` is the second portfolio repo that extends the existing `sudoku-image-solver` project from a static ML/CV image solver into a live AR-style overlay system.

The intended portfolio framing is:

> A real-time planar AR overlay for Sudoku solving using a frozen ML vision pipeline, homography-based board tracking, temporal smoothing, and board reacquisition.

This project is **not** intended to be full SLAM, ARKit/ARCore replacement, native mobile AR, or production-grade spatial persistence. The goal is a credible, bounded AR-style project that shows practical understanding of:

- live camera processing,
- model reuse,
- planar object tracking,
- homography-based rendering,
- solve-once session state,
- temporal smoothing,
- board reacquisition,
- and latency/FPS measurement.

The core technical bet remains:

> Because a Sudoku board is flat, planar tracking is the correct first implementation. Full SLAM is future work, not a dependency for project success.

---

## 2. Local Project Location

The project is being built locally here:

```bash
$HOME/Desktop/sudoku-ar-overlay
```

The existing model repo is here:

```bash
$HOME/projects/sudoku-image-solver
```

The working test image used most recently was:

```bash
$HOME/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg
```

---

## 3. Git State Confirmed So Far

The repo was initialized locally and the branch was renamed to `main`.

Confirmed commit history from the user's terminal:

```text
c25f2ca (HEAD -> main) Wire app image mode to real sudoku solver
f6b40c7 Add real static solver overlay smoke test
10cd9e7 Initialize sudoku-ar-overlay scaffold
```

Current known branch:

```text
main
```

A later usability patch for webcam controls was provided. It may need to be confirmed with:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
git status
git log --oneline -5
```

If the webcam usability patch exists but is not committed yet, commit it with:

```bash
git add app.py
git commit -m "Improve webcam solve controls"
```

---

## 4. Files Created / Modified So Far

### Core repo files

```text
README.md
pyproject.toml
.gitignore
app.py
```

### Package files

```text
src/sudoku_ar_overlay/__init__.py
src/sudoku_ar_overlay/config.py
src/sudoku_ar_overlay/board_state.py
src/sudoku_ar_overlay/smoothing.py
src/sudoku_ar_overlay/overlay.py
src/sudoku_ar_overlay/solver_adapter.py
```

### Docs

```text
docs/ROADMAP_CONTRACT.md
```

### Scripts

```text
scripts/static_real_overlay_from_solver.py
```

### Asset folders

```text
assets/demo/
examples/
```

---

## 5. Environment Setup

A new virtual environment was created under the AR repo:

```bash
$HOME/Desktop/sudoku-ar-overlay/.venv
```

The package was installed editable into that environment:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

This fixed the earlier import error:

```text
ModuleNotFoundError: No module named 'sudoku_ar_overlay'
```

Validation command that passed:

```bash
python -c "import sudoku_ar_overlay; print(sudoku_ar_overlay.__version__)"
```

Observed output:

```text
0.1.0
```

---

## 6. Important Environment Fixes / Lessons Learned

### 6.1 The solver repo did not have its own `.venv`

This failed because there was no `.venv` in the solver repo:

```bash
cd "$HOME/projects/sudoku-image-solver"
source .venv/bin/activate
```

Observed error:

```text
source: no such file or directory: .venv/bin/activate
```

Decision: use the AR repo `.venv` as the working environment and make sure it can import the solver runtime.

### 6.2 The AR repo needs access to the solver repo path

The old working notebook/script added the solver repo to `sys.path` before importing:

```python
REPO_ROOT = Path("~/projects/sudoku-image-solver").expanduser()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
```

Without that, this failed:

```python
from src.sudoku_solver.inference import load_runtime
```

With `sys.path` set correctly, this worked:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

python - <<'PY'
from pathlib import Path
import sys

REPO_ROOT = Path("~/projects/sudoku-image-solver").expanduser()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.sudoku_solver.inference import load_runtime

runtime = load_runtime()
print("runtime loaded")
print(runtime.keys())
PY
```

Observed output:

```text
runtime loaded
dict_keys(['frozen', 'seg_model', 'seg_image_size', 'occ_model', 'digit_model', 'digit_image_size', 'digit_info', 'occ_cal', 'digit_cal'])
```

### 6.3 PyTorch was missing at first

The first real solver import failed because the AR venv did not have `torch`.

Observed error:

```text
ModuleNotFoundError: No module named 'torch'
```

Root cause: the AR repo environment was lightweight and did not initially have the ML dependencies needed by `sudoku-image-solver`.

Resolution: install the needed solver dependencies into the AR venv.

---

## 7. Confirmed Working Commands

### 7.1 Static real overlay using the one-off script

This command worked:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

python scripts/static_real_overlay_from_solver.py \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --image "/Users/aaronhale/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg" \
  --out assets/demo/static_real_overlay.jpg

open assets/demo/static_real_overlay.jpg
```

This proved the AR repo could call the frozen model path, detect the board, solve it, and render solved digits on the original image.

### 7.2 Static real overlay through `app.py`

After refactoring the real solver path into `solver_adapter.py` and updating `app.py`, this command worked:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

python app.py \
  --mode image \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --image "$HOME/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg" \
  --out assets/demo/app_static_real_overlay.jpg

open assets/demo/app_static_real_overlay.jpg
```

Observed terminal output:

```text
Wrote overlay image: assets/demo/app_static_real_overlay.jpg
Solver status: real_solved
Solve latency: 336.03 ms
Latency breakdown:
  segmentation_ms: 293.06 ms
  warp_crop_ms: 0.96 ms
  ocr_ms: 41.53 ms
  sudoku_solve_ms: 0.48 ms
  pipeline_ms: 336.03 ms
```

This is the strongest confirmed gate so far.

### 7.3 Webcam opened successfully after permission/camera issue

The first webcam attempt failed due to macOS camera permission:

```text
OpenCV: not authorized to capture video
RuntimeError: Could not open camera: 0
```

Resolution:

- Give Terminal / iTerm / VS Code / Cursor camera permission in macOS:
  - System Settings → Privacy & Security → Camera
- Then retry webcam mode.

The camera later opened successfully. A screenshot showed the webcam feed with status:

```text
state=NO_BOARD fps=25.0 solve_ms=0.0 solver=real
```

Important: at that point the app did **not** auto-solve. It required pressing `s`.

---

## 8. Current Application Behavior

### 8.1 `app.py --mode image --solver real`

Confirmed working.

Purpose:

- Load one static image.
- Run real frozen solver.
- Detect board corners.
- Infer givens.
- Solve puzzle.
- Render solved digits into empty cells.
- Write output image.

### 8.2 `app.py --mode webcam --solver real`

Confirmed camera opens.

Current expected behavior:

- Opens live webcam feed.
- Does not auto-solve by default.
- User must press `s` to solve the current frame.
- After solving, overlay persists using the detected corners from that solved frame.
- This is still clunky and not yet true AR tracking.

### 8.3 Webcam usability patch provided

A patch was provided to improve the webcam mode with:

```text
s      solve current/frozen frame
f      freeze/unfreeze frame
space  freeze/unfreeze frame
a      toggle auto-solve
r      reset
q      quit
```

Recommended workflow after patch:

```text
1. Hold puzzle in view.
2. Press f to freeze a clean frame.
3. Press s to solve that frozen frame.
4. Press r to reset.
5. Press q to quit.
```

This was intended as a usability bridge before true tracking.

Confirm whether it is committed:

```bash
git log --oneline -5
```

If not committed:

```bash
git add app.py
git commit -m "Improve webcam solve controls"
```

---

## 9. What Has Been Completed Relative to Roadmap

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Repo setup and adapter | Mostly done | Repo, package, adapter, environment, real solver bridge exist |
| Phase 1 — Static AR overlay | Done | `app.py --mode image --solver real` works |
| Phase 2 — Webcam/video loop | Partially done | Webcam opens; manual solve exists; recorded-video mode not yet built |
| Phase 3 — Solve-once session state | Partially done | `BoardSession` exists; webcam stores solution after solve |
| Phase 4 — Homography-based planar tracking | Not yet done | Overlay does not yet follow updated board corners live |
| Phase 5 — Temporal smoothing + reacquisition | Not yet done | Basic smoothing function exists, but no full tracking/reacquisition loop |
| Phase 6 — Metrics + demo artifacts | Partially started | Static latency breakdown printed; no metrics doc/demo video yet |
| Phase 7 — README polish | Not yet final | Initial README exists, but not interview-ready |
| Phase 8 — Pose estimation | Not started | Optional later |
| Phase 9 — ARKit/ARCore bridge | Not started | Optional later |

---

## 10. Current Technical Architecture

### 10.1 `solver_adapter.py`

Currently responsible for:

- defining `SolverResult`,
- providing a mock solver,
- loading the real solver runtime from `sudoku-image-solver`,
- running segmentation,
- warping/cropping,
- running OCR,
- applying calibrations,
- solving the Sudoku,
- returning corners/givens/solution/latency.

Key current function:

```python
solve_frame(
    frame_bgr,
    solver="mock" or "real",
    repo_root="~/projects/sudoku-image-solver",
)
```

### 10.2 `overlay.py`

Currently responsible for:

- ordering board corners,
- drawing green board outline,
- rendering solved digits onto a canonical transparent board canvas,
- warping the canvas into the camera/original image using homography,
- alpha blending the overlay over the frame.

Important design choice:

> Solved digits are rendered on a transparent 900x900 canonical board canvas, then warped into the frame. This is the right approach for planar AR-style overlay.

### 10.3 `board_state.py`

Currently responsible for:

- tracking app state,
- storing givens,
- storing solution,
- storing missing-cell mask,
- storing last/smoothed corners,
- storing solve latency.

States currently defined:

```text
NO_BOARD
BOARD_DETECTED
SOLVED_TRACKING
TRACKING_LOST
REACQUIRED
```

### 10.4 `smoothing.py`

Currently has basic exponential moving average corner smoothing:

```python
smoothed = alpha * current + (1 - alpha) * previous
```

This is not yet fully used for live tracking.

---

## 11. Important Design Decisions Already Made

### 11.1 Do not start with ORB-SLAM

Decision:

- Do not make ORB-SLAM a dependency for success.
- Use planar tracking first because the Sudoku board is flat.
- Mention SLAM/ARKit/ARCore as future work.

Rationale:

- Higher likelihood of shipping.
- More appropriate for a planar object.
- Better portfolio story: chose the right geometry for the problem.

### 11.2 Manual solve is acceptable at first

Current manual flow is acceptable for this gate:

```text
camera feed → press s → solve current/frozen frame → render cached overlay
```

But it is not the final demo.

### 11.3 Full OCR should not run every frame

The measured static pipeline was about 336 ms on one image, with segmentation taking about 293 ms.

Therefore, the next live version should:

- solve once,
- run segmentation-only tracking periodically,
- smooth corners,
- render every frame,
- avoid full OCR every frame.

### 11.4 The next major milestone is live planar tracking

The next value jump is not another static image improvement. It is:

> Update board corners over time and make the solved overlay follow the board.

---

## 12. Problems Encountered and Fixes

### Problem: Tried to execute folder

Command accidentally run:

```bash
/Users/aaronhale/Desktop/sudoku-ar-overlay
```

Error:

```text
zsh: permission denied
```

Fix:

```bash
cd /Users/aaronhale/Desktop/sudoku-ar-overlay
```

### Problem: Shell got stuck at `quote>`

Cause: unclosed quote/heredoc in terminal.

Fix:

```text
Ctrl + C
```

Then use simpler one-line Python commands when possible.

### Problem: Missing `torch`

Cause: AR venv did not include solver runtime dependencies.

Fix: install needed ML/CV deps into AR venv.

### Problem: `src.sudoku_solver` import failed

Cause: solver repo root was not added to `sys.path`.

Fix: insert `$HOME/projects/sudoku-image-solver` into `sys.path` before importing from `src.sudoku_solver.inference`.

### Problem: `sudoku_ar_overlay` import failed

Cause: AR package was not installed editable.

Fix:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### Problem: Camera failed to open

Cause: macOS camera permission.

Fix:

- Enable camera access for terminal/editor app.
- If needed:

```bash
tccutil reset Camera
```

### Problem: Webcam did not auto-solve

Cause: current version requires manual keypress.

Fix / current behavior:

```text
press s to solve
```

Usability patch added/was provided:

```text
press f to freeze a clean frame, then s to solve
```

---

## 13. Current Known Limitations

The project is not yet a full AR-style demo.

Current limitations:

- Webcam solve is manual/clunky.
- Overlay does not yet track updated board corners after solve.
- Board reacquisition is not yet implemented.
- Recorded-video mode is not yet implemented.
- No metrics file yet.
- No demo GIF/video yet.
- README is not yet portfolio-polished.
- Camera permission/setup may be needed on macOS.
- Real solver dependency is currently imported from local repo via `sys.path`, not packaged cleanly.

---

## 14. Recommended Next Step

Before starting tracking, confirm current state:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

git status
git log --oneline -5
```

Then create a branch for tracking:

```bash
git switch -c planar-tracking 2>/dev/null || git switch planar-tracking
```

The next technical implementation should add:

```text
src/sudoku_ar_overlay/tracking.py
```

and update:

```text
src/sudoku_ar_overlay/solver_adapter.py
app.py
```

### Next behavior to build

New command target:

```bash
python app.py \
  --mode webcam \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --track-board \
  --track-every-n-frames 10
```

Expected next behavior:

1. Camera opens.
2. App periodically detects board corners.
3. Board outline updates while board is visible.
4. Press `s` once to solve.
5. Move the board/camera slowly.
6. Overlay follows the board because corners are updated.
7. If board leaves frame, overlay hides.
8. When board returns, cached solved overlay reappears.

This is the next true portfolio milestone.

---

## 15. Next Stage Definition

The next stage is:

# Phase 4 — Homography-Based Planar Tracking

Objective:

> Run segmentation-only board detection every few frames, smooth the detected corners, and render the already-solved digits onto the current board plane.

Do **not** run full OCR every frame.

The live loop should become:

```text
camera frame
  ↓
every N frames: detect board corners only
  ↓
smooth corners
  ↓
if solved: warp solved digit overlay onto current board corners
  ↓
if board disappears: hide overlay but keep solution in memory
  ↓
if board comes back: reuse solution and redraw overlay
```

This phase is what turns the project from:

```text
webcam solve demo
```

into:

```text
AR-style planar overlay demo
```

---

## 16. Short Current Status Summary

As of now:

> `sudoku-ar-overlay` has a working local repo, real solver integration, static image overlay through `app.py`, a functioning webcam feed, and manual webcam solving. The next major task is live planar board tracking so the solved overlay follows the Sudoku board across frames instead of staying tied to the frame captured when the user pressed solve.



## 17. Update — Segmentation Tracking Test and Next Architecture Decision

**Date:** 2026-04-24  
**Branch during this work:** planar-tracking

### 17.1 What was added

After the manual webcam solve flow worked, the project moved into live planar tracking.

The following tracking-related pieces were added or tested:

- `src/sudoku_ar_overlay/tracking.py`
- `src/sudoku_ar_overlay/stabilizer.py`
- segmentation-only board-corner detection in `solver_adapter.py`
- tracking-related flags in `app.py`

The goal was to avoid running full OCR and Sudoku solving every frame. Instead, the app now attempts to run segmentation-only board detection every few frames, update the board corners, smooth/stabilize those corners, and render the cached solved overlay on the current board plane.

### 17.2 Confirmed working behavior

The following behavior is confirmed:

- static image mode works
- webcam mode opens
- manual webcam solve works
- real solver integration works
- segmentation-only tracking can detect and outline the board
- solved overlay can render using tracked board corners

Representative image-mode command:

    PYTHONPATH=src python app.py \
      --mode image \
      --solver real \
      --repo-root "$HOME/projects/sudoku-image-solver" \
      --image "$HOME/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg" \
      --out assets/demo/app_static_real_overlay.jpg

Representative webcam tracking command tested:

    PYTHONPATH=src python app.py \
      --mode webcam \
      --solver real \
      --repo-root "$HOME/projects/sudoku-image-solver" \
      --track-board \
      --track-every-n-frames 5 \
      --lost-after-tracking-attempts 3 \
      --stabilizer-median-window 3 \
      --stabilizer-static-alpha 0.10 \
      --stabilizer-moving-alpha 0.99 \
      --stabilizer-static-motion-px 5 \
      --stabilizer-fast-motion-px 10 \
      --debug

### 17.3 Key finding

Segmentation-only tracking works conceptually, but it is too slow to feel like smooth AR when the board or camera moves.

Observed problem:

- the board outline and overlay lag behind the physical puzzle during movement
- increasing stabilizer responsiveness helps, but does not remove the lag
- high responsiveness settings reduce smoothing benefits and make jitter more visible

The main issue is architectural:

> The segmentation model is being used as both the detector and the tracker.

Segmentation is useful for finding or reacquiring the board, but it is too slow to serve as the per-frame AR tracker.

### 17.4 Stabilizer lesson

The stabilizer clarified the tradeoff:

- more smoothing reduces jitter but increases lag
- less smoothing improves responsiveness but increases jitter
- high moving-alpha values mostly trust raw detections
- remaining lag is mostly caused by slow segmentation inference, not smoothing alone

This means parameter tuning alone is unlikely to make the overlay feel truly AR-like.

### 17.5 Updated architecture decision

The next architecture should separate slow absolute detection from fast frame-to-frame tracking.

The new intended loop is:

1. Segmentation detects board corners.
2. A fast tracker initializes on the board region.
3. Every camera frame:
   - track feature points with optical flow
   - estimate homography
   - update board corners
   - render overlay
4. Every N frames:
   - segmentation refreshes or corrects the tracker
5. If tracking fails:
   - hide overlay
   - wait for segmentation reacquisition

Updated component roles:

| Component | Purpose | Expected speed |
|---|---|---:|
| Segmentation | absolute board detection and reacquisition | slow |
| Optical flow plus homography | frame-to-frame board tracking | fast |
| Stabilizer | reduce corner jitter | fast |
| Session state | retain solved board and missing-cell mask | constant |
| Overlay renderer | warp cached solution to current board plane | fast |

### 17.6 Next technical milestone

Add:

- `src/sudoku_ar_overlay/flow_tracker.py`

Expected OpenCV techniques:

- `cv2.goodFeaturesToTrack`
- `cv2.calcOpticalFlowPyrLK`
- `cv2.findHomography` with RANSAC
- `cv2.perspectiveTransform`

Target behavior:

- segmentation finds the board once
- optical flow tracks board motion every frame
- overlay follows the board with less lag
- segmentation occasionally corrects drift
- if the board leaves frame, tracking is lost
- if the board returns, segmentation reacquires it

### 17.7 Revised roadmap status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Repo setup and adapter | Done | Real solver bridge works |
| Phase 1 — Static AR overlay | Done | Static image overlay works |
| Phase 2 — Webcam/video loop | Mostly done | Webcam works; video-file mode still not built |
| Phase 3 — Solve-once session state | Mostly done | Cached solution persists after solve |
| Phase 4 — Homography-based planar tracking | Partially done | Segmentation-only tracking works but is too slow for smooth motion |
| Phase 5 — Temporal smoothing and reacquisition | Partially started | Stabilizer exists, but full tracking stack needs optical flow |
| Phase 6 — Metrics and demo artifacts | Not done | Needs metrics after tracking architecture improves |
| Phase 7 — README polish | Not done | Wait until tracking design stabilizes |
| Phase 8 — Pose estimation | Not started | Optional |
| Phase 9 — ARKit/ARCore bridge | Not started | Optional |

### 17.8 Current interpretation

This is not a project failure. It is a useful engineering discovery.

The current conclusion is:

> A slow ML segmentation model can initialize and reacquire the board, but it should not be the per-frame AR tracker.

Next step:

> Add fast optical-flow/homography tracking between segmentation detections.



---

## 18. Update — Pivot to ArUco-Assisted Reliable Tracking

**Date:** 2026-04-24  
**Current branch:** aruco-assisted-tracking

### 18.1 Current repo state

The markerless tracking work has been committed and merged back into `main`.

Known recent commits:

- `48bd61f` — Add markerless flow tracking prototype and revise roadmap
- `738480d` — Use OpenCV contrib for ArUco support
- `98bdea3` — Restore OpenCV dependency after contrib import issue

The active branch is now:

    aruco-assisted-tracking

This branch was created after merging the markerless tracking prototype into `main`.

### 18.2 Markerless tracking conclusion

The markerless pipeline now works as a proof-of-concept:

- segmentation can initialize board corners
- optical flow plus homography can track the board frame-to-frame
- solved overlays can follow the board when movement is very slow
- rendered video output can be recorded directly from the OpenCV app

However, testing showed that markerless optical-flow tracking breaks under normal hand/camera movement.

Observed behavior:

- very slow movement works reasonably well
- normal-speed motion causes drift, incorrect corners, or tracking loss
- the overlay can become visibly detached from the puzzle
- reacquisition is slower than desired because it depends on segmentation

Conclusion:

> Markerless tracking is useful as an experimental/technical mode, but it is not robust enough to be the final polished demo path.

### 18.3 Architecture decision

The project is pivoting to a two-mode tracking architecture:

| Mode | Purpose | Status |
|---|---|---|
| Markerless mode | Demonstrates ML segmentation, optical flow, homography tracking, and known limitations | Prototype built |
| ArUco-assisted mode | Provides reliable planar anchoring for the final demo | Starting now |

This is a deliberate engineering choice.

The final project should not pretend the markerless tracker is more robust than it is. Instead, the repo should show practical judgment:

> Markerless tracking is technically interesting but fragile. Fiducial-assisted tracking gives a reliable AR anchor and a cleaner demo while staying fully in Python/OpenCV.

### 18.4 Revised scope decision

ARKit / ARCore implementation has been cut from the active project scope.

Reason:

- ARKit is mainly valuable when building an iPhone/iPad/Apple AR app with device motion tracking and native AR anchors.
- This repo is a Python/OpenCV webcam project.
- Adding ARKit would require a separate mobile/native app path and would distract from finishing the portfolio repo.

ORB-SLAM is also not being added.

Reason:

- ORB-SLAM solves camera/world localization, not direct Sudoku board anchoring.
- It would introduce substantial build, calibration, and integration complexity.
- It is likely to become a time sink relative to the project goal.

New direction:

> Stay in Python/OpenCV. Use ArUco-assisted planar tracking as the reliable final demo path. Optionally add `solvePnP` pose/debug visualization later for credibility.

### 18.5 Contract update

The roadmap contract was revised to reflect the new direction:

- markerless tracking remains as an experimental mode
- ArUco-assisted tracking becomes the reliable demo path
- ARKit / ARCore / ORB-SLAM are cut from implementation scope
- optional pose estimation remains in scope through OpenCV `solvePnP`
- final demo should prioritize reliability, clear metrics, and honest limitations

The revised contract is stored at:

    docs/ROADMAP_CONTRACT.md

### 18.6 Dependency issue and resolution

An attempt was made to switch from `opencv-python` to `opencv-contrib-python` for ArUco support.

That caused a `cv2` import failure:

    Library not loaded: @loader_path/.dylibs/libtesseract.5.dylib

Resolution:

- uninstall `opencv-contrib-python`
- reinstall regular `opencv-python`
- verify that regular OpenCV already includes ArUco support in this environment

Successful validation output:

    cv2 version: 4.13.0
    aruco available: True
    ArucoDetector available: True
    DICT_4X4_50 available: True

The dependency was restored in `pyproject.toml`:

    "opencv-python>=4.8"

This means no OpenCV contrib package is needed for the current ArUco plan.

### 18.7 Current implementation status

Completed:

- static real solver overlay
- webcam manual solve
- freeze-frame solve usability
- segmentation-only tracking prototype
- adaptive stabilizer prototype
- optical-flow homography tracker prototype
- rendered video recording from OpenCV output
- revised roadmap contract
- OpenCV ArUco availability confirmed

Not yet completed:

- ArUco marker generation script
- ArUco marker detection demo
- ArUco-assisted Sudoku board anchor
- ArUco-assisted solved overlay
- final tracking-mode integration into `app.py`
- README update for two-mode tracking
- metrics documentation
- polished demo video/GIF

### 18.8 Immediate next step

Next implementation milestone:

> Generate a printable ArUco marker and prove webcam detection works.

Files to add next:

- `scripts/generate_aruco_marker.py`
- `src/sudoku_ar_overlay/aruco_tracker.py`
- `scripts/aruco_marker_demo.py`

First target behavior:

1. Generate marker ID 23.
2. Open or print the marker sheet.
3. Show the marker to the webcam.
4. Detect the marker every frame.
5. Draw marker outline, center, and ID.
6. Optionally record the rendered output.

Representative target commands:

    PYTHONPATH=src python scripts/generate_aruco_marker.py \
      --marker-id 23 \
      --out assets/markers/aruco_23.png \
      --sheet-out assets/markers/aruco_23_sheet.png

    open assets/markers/aruco_23_sheet.png

    PYTHONPATH=src python scripts/aruco_marker_demo.py \
      --marker-id 23 \
      --record-out assets/demo/aruco_marker_demo.mp4

### 18.9 Next milestone after marker detection

After basic marker detection works, the next step is to use the marker as a board anchor.

Initial target:

> Use one ArUco marker next to the Sudoku board with a known offset to estimate the Sudoku board plane.

Later target:

> Use four ArUco markers around the board for a more stable final demo.

Recommended final tracking modes:

| Tracking mode | Description |
|---|---|
| Markerless experimental | ML segmentation plus optical-flow homography tracking |
| ArUco-assisted reliable | Fiducial-assisted board anchoring for stable final demo |

### 18.10 Current interpretation

The project has made an important design turn.

The markerless mode is still valuable, but the reliable final demo should be ArUco-assisted.

This gives the strongest portfolio story:

> I built the markerless version, identified its limits under normal motion, and added a fiducial-assisted mode to produce a robust AR-style overlay while keeping the architecture bounded, practical, and honest.

---

## 19. Update — Final 3-Week Direction: Markerless Recorded-Video Demo

**Date:** 2026-04-24  
**Current working context:** Post-ArUco reconsideration  
**Recommended next branch:** `markerless-video-demo`

### 19.1 Why this update exists

After further review, the ArUco-assisted direction was rejected as the final product/demo path.

Reason:

> A real end user should not need a printed fiducial marker, QR code, ArUco tag, AprilTag, or other artificial marker for the Sudoku overlay to work.

ArUco remains useful as a diagnostic or internal calibration concept, but it should not be part of the user-facing demo or the main portfolio story.

This section supersedes the ArUco final-demo direction described in Section 18.

### 19.2 Current best project goal

The best 3-week Anduril-facing portfolio goal is now:

> Build a markerless, recorded-iPhone-video Sudoku AR overlay system with confidence-gated tracking and look-away/look-back reacquisition.

The project should show that a frozen ML/CV model can be turned into a product-like video perception system:

1. Detect a normal Sudoku puzzle.
2. Solve it once.
3. Cache the solved board state.
4. Project missing digits onto the board plane.
5. Track/render while confidence is high.
6. Hide the overlay when tracking confidence drops.
7. Reacquire the board when it returns.
8. Report metrics and failure modes.

### 19.3 Why recorded iPhone video is now the primary demo path

Live USB webcam tracking proved too fragile under normal handheld motion.

Recorded iPhone video is a better primary demo input because it offers:

- higher resolution,
- better exposure and focus,
- less noise,
- better motion handling,
- repeatable test clips,
- easier debugging,
- easier metrics generation,
- and cleaner final demo assets.

The webcam path remains useful as a secondary live/experimental mode, but it should not define the quality bar for the final portfolio demo.

### 19.4 What has already been learned

The project has already tested several approaches:

| Approach | Result | Decision |
|---|---|---|
| Static image overlay | Works | Keep |
| Webcam manual solve | Works but clunky | Keep as secondary |
| Segmentation-only tracking | Detects board but too slow/laggy | Not enough |
| Corner stabilizer | Helps explain jitter/lag tradeoff | Keep ideas, not sufficient alone |
| Optical-flow homography tracking | Better; works under very slow movement | Keep as experimental component |
| ArUco-assisted tracking | Technically robust but product-inappropriate | Cut from final path |
| Gridline-only tracking | Risky because inner lines can disappear | Do not use as primary anchor |
| SLAM / ARKit | Too large for 3-week repo goal | Cut from active scope |

### 19.5 Final architecture direction

The final user-facing path should be:

> Markerless template-assisted planar tracking from recorded iPhone video.

High-level pipeline:

1. Read iPhone video frame-by-frame.
2. Detect Sudoku board using the existing segmentation/solver pipeline.
3. Solve once on a clean frame.
4. Cache:
   - givens grid,
   - solved grid,
   - missing-cell mask,
   - canonical board crop/template,
   - last reliable board homography.
5. Track board motion using optical flow and/or template-assisted homography.
6. Optionally refine with visible grid/border cues when available.
7. Render solved digits onto the board plane.
8. Hide overlay when tracking confidence drops.
9. Reacquire when the board returns to view.
10. Write processed MP4 and metrics.

### 19.6 Look-away / look-back definition

The project should support look-away/look-back behavior, but it should be defined correctly.

Out of scope:

> Persistent 3D world-space anchoring while the board is completely off camera.

That would require ARKit/ARCore/VIO/SLAM-style tracking and is not part of the 3-week goal.

In scope:

> Cache the solved board state, hide the overlay when tracking is lost, detect the board again when it returns, and reattach the cached solved overlay.

Expected behavior:

1. Board visible.
2. System detects and solves board.
3. Overlay appears.
4. Camera looks away or board leaves frame.
5. State becomes `TRACKING_LOST`.
6. Overlay disappears.
7. Camera looks back.
8. Board is detected/reacquired.
9. State becomes `REACQUIRED`.
10. Cached solution appears again.

This is product-credible and achievable.

### 19.7 What should be cut from the active 3-week plan

Do not pursue these as implementation goals for the current portfolio deadline:

- ORB-SLAM integration,
- ARKit/ARCore implementation,
- ArUco/AprilTag/fiducial marker product path,
- bent-paper deformation,
- perfect fast-motion tracking,
- consumer-grade live webcam robustness,
- full mobile-native app.

These can be mentioned as future work or rejected alternatives, but they should not block the repo.

### 19.8 What should remain in scope

Keep the project focused on:

- static image overlay,
- recorded-video processing mode,
- iPhone video as primary demo input,
- webcam as secondary experimental mode,
- solve-once session state,
- homography-based rendering,
- markerless optical-flow/template tracking,
- confidence-gated overlay rendering,
- tracking-loss state,
- look-away/look-back reacquisition,
- metrics and demo assets,
- README architecture polish.

### 19.9 Recommended next implementation milestone

The next technical milestone should be recorded-video mode:

Target command:

    PYTHONPATH=src python app.py \
      --mode video \
      --solver real \
      --repo-root "$HOME/projects/sudoku-image-solver" \
      --input assets/demo/raw_iphone_lookaway.mp4 \
      --out assets/demo/processed_lookaway_overlay.mp4

Expected first pass:

1. Read a video file.
2. Let the user specify or auto-select a solve frame.
3. Solve once.
4. Render overlay across subsequent frames.
5. Hide overlay when tracking confidence is too low.
6. Save processed output video.
7. Print basic metrics.

### 19.10 Three-week build plan

#### Week 1 — Recorded-video foundation

Build:

- `--mode video`
- direct MP4 output
- solve-once video session
- overlay rendering across frames
- tracking confidence score
- hide overlay on tracking loss

Pass condition:

> One iPhone video produces a processed overlay video where the overlay looks good under controlled moderate motion and disappears instead of drifting when tracking fails.

#### Week 2 — Reacquisition and template-assisted tracking

Build:

- canonical board template after solve,
- template/feature-assisted reacquisition,
- session-level same-board assumption,
- optional board fingerprint from givens/template,
- look-away/look-back clip support,
- tracking-loss and reacquisition metrics.

Pass condition:

> Camera can look away, return to the board, and the cached solved overlay reappears.

#### Week 3 — Portfolio polish

Build:

- `assets/demo/final_demo.mp4`
- `assets/demo/debug_demo.mp4`
- `docs/metrics.md`
- README architecture diagram
- README demo section
- README limitations section
- concise Anduril-facing technical narrative

Pass condition:

> A reviewer can understand the system, watch the demo, see metrics, and understand the engineering tradeoffs in under two minutes.

### 19.11 Confidence assessment

Current confidence:

| Goal | Confidence | Notes |
|---|---:|---|
| Static overlay | High | Already works |
| Recorded-video processing | High | Straightforward OpenCV video IO |
| Solve-once video session | High | Existing solver/session work supports this |
| Moderate-motion overlay on iPhone video | Medium-high | Better input quality should help |
| Look-away/look-back reacquisition | High under controlled video | Easier than continuous fast tracking |
| Template-assisted tracking improvement | Medium | Useful, but not magic |
| Robust live webcam under normal motion | Low | Not the primary target |
| Full SLAM/ARKit-style persistence | Low within 3 weeks | Cut from scope |

### 19.12 Final interpretation

The right portfolio piece is not a perfect AR product.

The right portfolio piece is:

> A markerless video perception system that turns a frozen Sudoku solver into an AR-style overlay demo with solve-once inference, planar homography rendering, confidence-gated tracking, look-away/look-back reacquisition, and clear metrics.

This is the most credible and shippable 3-week plan for an MLE-oriented portfolio project.


---

## 20. Update — Recorded Video Mode and First Optical-Flow Video Success

**Date:** 2026-04-24  
**Current branch:** `markerless-video-demo`

### 20.1 Current strategic direction

The active project direction remains:

> Build a markerless, recorded-iPhone-video Sudoku AR overlay system with confidence-gated tracking and look-away/look-back reacquisition.

This supersedes the earlier ArUco-assisted direction. ArUco remains useful as a diagnostic idea, but it is not part of the final user-facing product path.

The final demo should work on a normal Sudoku puzzle without printed fiducials, QR codes, AprilTags, ArUco markers, or custom board markers.

### 20.2 Recent repo commits

Recent confirmed commits:

- `624c190` — Update README for markerless recorded-video direction
- `648668f` — Pivot roadmap to markerless recorded-video demo
- `f9e25bf` — Add recorded video processing mode
- `98bdea3` — Restore OpenCV dependency after contrib import issue
- `48bd61f` — Add markerless flow tracking prototype and revise roadmap

The `README.md` now reflects the markerless recorded-video direction.

The repo was confirmed clean after the README update:

```text
On branch markerless-video-demo
nothing to commit, working tree clean

