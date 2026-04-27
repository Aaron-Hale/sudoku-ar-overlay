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


---


## 21. Update — Fail-Closed Tracking, Grid-First Discovery, Reacquisition Debugging, and Next Architecture Decision

**Date:** 2026-04-24  
**Current branch:** `markerless-video-demo`

### 21.1 Summary of where we are now

Since the last update, the project moved from “can we track at all?” to a more precise perception-system problem:

> The app can solve a clean starting frame, track the board well under moderate motion, and fail closed when the board leaves frame. The remaining hard problem is robust reacquisition: finding the returned Sudoku board quickly, validating whether it is the same puzzle or a new puzzle, and fitting the overlay accurately before rendering.

Confirmed improvements:

- recorded-video mode works
- initial solve works quickly on clean starting frames
- optical-flow tracking works well while the board is visible
- moderate motion is handled much better than webcam / segmentation-only tracking
- the overlay now hides when tracking becomes implausible
- rug/carpet false positives can be rejected with grid validation
- the codebase now has a path toward grid-first discovery and identity-aware reacquisition

Current remaining gaps:

- reacquisition is still too slow
- reacquired overlay fit can be skewed
- returned moving / side-entering puzzles can produce rough or premature corners
- same-puzzle versus new-puzzle policy still needs to be implemented cleanly
- several local changes are uncommitted and should be reviewed before committing

### 21.2 Important confirmed behavior from the latest video tests

The latest iPhone video test showed:

```text
Initial board visible:
  solves quickly and accurately

Board in motion:
  optical-flow tracking is good under moderate movement

Camera/board moves away:
  overlay cuts off / hides correctly

Board returns:
  system finds something Sudoku-like, but reacquisition is slow
  the overlay returns with a slightly skewed / poor fit
```

Interpretation:

> The tracker is no longer the main blocker. The main blocker is reacquisition quality: finding the correct returned board, waiting until it is stable enough, refining its grid corners, and deciding whether to reuse the cached solution or solve fresh.

### 21.3 Fail-closed behavior improved

Earlier versions had a bad failure mode:

```text
board leaves frame
→ optical flow keeps attaching the old overlay to random background
```

This was improved by adding motion / geometry plausibility checks:

- board area change checks
- corner jump checks
- flow inlier checks
- minimum board area checks
- corner quality checks
- tracking-loss state handling

Current desired behavior:

```text
if flow result becomes implausible:
  hide overlay immediately
  stop rendering stale geometry
  enter discovery/reacquisition mode
```

This is now mostly working and is an important product-quality milestone.

### 21.4 Full-solve reacquisition was tested and found unsafe by itself

We tested the idea:

```text
tracking lost
→ run full solver again when a puzzle-like candidate appears
→ if solve succeeds, initialize a new session
```

This is product-safe in theory because it avoids projecting an old solution onto a new puzzle.

But the first implementation had serious issues:

1. It could repeatedly call the full solver on bad/no-board frames.
2. It could hang for many minutes.
3. It was too brittle when candidate frames were transitional, blurred, moving, or misdetected.

A safety patch was added:

```text
--reacquire-with-solve default=False
```

Later, bounded solving was added:

```text
--solve-timeout-sec
--discover-solve-cooldown-frames
--discover-max-solve-attempts
```

This prevented indefinite hangs, but it did not solve the underlying reacquisition-quality issue.

### 21.5 The Sudoku solver hang was diagnosed and improved

A major diagnostic finding:

> Some failed reacquisition frames were not slow because segmentation or OCR was slow. They were slow because OCR produced an invalid givens grid, and the naive Sudoku backtracker spent too long trying to prove the grid unsolvable.

The stack trace showed repeated recursion inside:

```text
solve_sudoku(grid)
```

A fail-fast MRV Sudoku solver was added in:

```text
src/sudoku_ar_overlay/solver_adapter.py
```

The MRV solver now:

- checks for duplicate nonzero givens in rows, columns, and boxes
- selects the empty cell with the fewest legal candidates
- fails quickly on contradictory OCR output

Result:

```text
bad OCR givens now fail quickly instead of hanging
```

This should stay in the project.

### 21.6 Side-by-side frame debugging proved the issue was upstream of OCR/solve

We compared two frames from the same iPhone video:

```text
frame 0010
frame 0670
```

Frame `0010` solved cleanly:

```text
filled givens: 39
duplicate issues: none
MRV solve_sudoku result: True
```

Frame `0670` produced nonsense predicted givens:

```text
filled givens: 20
mostly 2s and 5s
duplicate issues in multiple rows, columns, and boxes
MRV solve_sudoku result: False
```

At first this looked like OCR failure, but image diagnostics showed the deeper issue:

> For frame `0670`, the detector was not finding the Sudoku board. It was warping a rug/carpet region and passing that into OCR.

That explained why OCR predicted garbage digits.

Conclusion:

```text
The solver was not failing on the puzzle.
The detector/discovery path was selecting the wrong rectangle.
```

### 21.7 Grid validation was added and successfully rejected the rug false positive

A new module was added:

```text
src/sudoku_ar_overlay/grid_validation.py
```

It includes:

```text
validate_sudoku_grid_candidate(...)
warp_candidate(...)
evaluate_sudoku_grid_fit(...)
```

The validator checks whether a warped candidate actually looks like a Sudoku grid by looking for repeated horizontal and vertical grid-line evidence.

Diagnostic result:

```text
frame_0010 True  grid ok: score=0.160 v_peak=0.141 h_peak=0.179 v_lines=7 h_lines=10
frame_0670 False grid rejected: score=-0.007 v_peak=-0.012 h_peak=-0.003 v_lines=1 h_lines=3
```

This was a major breakthrough.

Interpretation:

> The validator correctly accepts the real Sudoku board and rejects the rug false positive.

This should remain in the project.

### 21.8 Grid-first discovery was added

A new module was added:

```text
src/sudoku_ar_overlay/grid_discovery.py
```

Purpose:

> Find Sudoku-like grid candidates directly from line/contour structure instead of blindly trusting the segmentation detector.

This was added because segmentation can return a plausible-looking rectangle that is not the Sudoku board.

The intended discovery order is now:

```text
1. Try grid-first discovery.
2. Validate candidate looks like a Sudoku grid.
3. If grid discovery fails, optionally fall back to segmentation candidate.
4. Reject anything that does not pass grid validation.
```

This is the right direction. It prevents false positives like carpet/rug candidates from reaching OCR or overlay rendering.

### 21.9 Grid-fit validation was added but reacquired overlay fit is still imperfect

A fit validator was added to check whether candidate corners align with expected Sudoku grid lines:

```text
evaluate_sudoku_grid_fit(...)
```

Purpose:

```text
candidate corners
→ warp candidate
→ compare expected grid-line positions to detected line peaks
→ reject candidates whose projected grid is poorly aligned
```

This is meant to prevent skewed overlays.

However, the latest output still shows:

```text
reacquired overlay appears slightly skewed
```

Current interpretation:

> Grid-first discovery can find a Sudoku-like candidate, but the corners are still rough. The overlay needs refined grid-corner alignment before rendering.

### 21.10 Pose-aware reacquisition policy was explored

We discussed and started implementing a better policy using last known board pose.

Store when tracking is lost:

```text
last_good_corners
last_good_center
last_good_area
last_good_board_template/fingerprint later
```

For each new candidate:

```text
candidate_center
candidate_area
candidate_corners
candidate_grid_fit
```

Use pose continuity:

```text
center movement from last known pose
area ratio from last known pose
candidate grid quality
candidate fit quality
```

Policy:

```text
near last pose + good grid fit:
  likely same puzzle
  cached solution may be reused provisionally

far from last pose + low similarity:
  likely new puzzle
  fresh solve required

uncertain:
  show nothing
```

This is the right high-level policy, but it is not fully stable yet.

### 21.11 We decided cached reacquisition alone is unsafe

There was a brief idea to reacquire using the cached solution instead of fresh solving.

This was rejected as the default product behavior.

Reason:

```text
A different puzzle could enter the frame.
Reusing the old solution on a new puzzle would be a serious product failure.
```

The better policy is:

```text
same puzzle likely:
  reuse cache provisionally for speed

new puzzle likely:
  require fresh solve

uncertain:
  show nothing
```

This led to the current recommended architecture:

> Cached overlay can be used for fast known-puzzle reacquisition only if there is identity evidence, not merely because a Sudoku-like board appeared.

### 21.12 Best architecture decision from this round

The most robust/scalable answer is now:

```text
separate tracking, detection, identity, and solving
```

Roles:

| Module | Responsibility |
|---|---|
| Tracker | Track current board frame-to-frame with optical flow/homography |
| Detector | Find Sudoku-grid candidates when tracking is lost |
| Grid validator | Reject false positives like carpet/rug/table texture |
| Grid refiner | Improve rough detected corners to overlay-quality grid corners |
| Identity verifier | Decide whether candidate is same puzzle or new puzzle |
| Solver | Solve only when needed for a new puzzle or initial puzzle |

This avoids the earlier mistake of letting one component do too much.

### 21.13 Current recommended state machine

Recommended final behavior:

```text
DISCOVERY
  find stable Sudoku-grid candidate
  solve fresh
  cache solution + board fingerprint
  initialize tracker
  -> SOLVED_TRACKING

SOLVED_TRACKING
  optical flow updates corners every frame
  render only while tracking quality is high
  if motion/geometry implausible:
    hide overlay
    preserve last good pose + identity fingerprint
    -> TRACKING_LOST

TRACKING_LOST
  show nothing
  search for Sudoku-grid candidates
  if candidate found:
    -> CANDIDATE_REACQUIRED

CANDIDATE_REACQUIRED
  evaluate:
    grid validity
    grid fit
    pose continuity
    board fingerprint/template similarity

  if likely same board:
    optionally show cached overlay quickly/provisionally
    validate in background
    -> SOLVED_TRACKING

  if likely new board:
    hide overlay
    fresh solve required
    -> DISCOVERY / NEW_PUZZLE_SOLVING

  if uncertain:
    show nothing
    collect more frames
```

### 21.14 Key insight: reacquisition is happening too early while the board is moving

The latest video showed that the board returns from the side of the frame while moving.

This creates a different condition than the initial solve:

```text
Initial solve:
  board centered
  board still
  full puzzle visible
  clean corners
  accurate solve

Reacquisition:
  board entering from side
  board moving
  corners changing
  partial/edge-frame views
  rough/skewed candidate corners
```

Conclusion:

> The system is reacquiring too early on a moving/transitioning object.

Correct fix:

```text
candidate appears
→ do not render immediately
→ collect a short candidate buffer
→ wait until candidate is stable for a few frames
→ refine grid corners
→ then render / solve / initialize flow
```

At 30 FPS, this does not need to be slow:

```text
3–5 stable frames = ~0.1–0.17 sec
10 stable frames = ~0.33 sec
```

This is much better than showing a skewed overlay.

### 21.15 Known-puzzle fast reacquisition idea

For speed when the same known puzzle leaves and returns:

```text
solve initial board
cache canonical board fingerprint/template
when board returns:
  detect candidate grid
  warp candidate to canonical view
  compare to cached fingerprint
  if high similarity:
    reuse cached solution quickly
  if low similarity:
    fresh solve required
```

This gives the best user experience:

```text
same puzzle returns:
  overlay returns fast

different puzzle appears:
  old overlay is blocked
  fresh solve required
```

This requires adding a board fingerprint/template module.

Suggested cached data:

```text
cached solution
cached givens
canonical board crop/template
edge-map template
last good corners
last good center
last good area
last exit side
```

Suggested same-board evidence:

```text
template similarity
givens/grid layout similarity
pose continuity
scale continuity
time since loss
entry/exit side consistency
```

### 21.16 Entry/exit side should be used, but not alone

We discussed whether the system should use where the puzzle left and where it returned.

Decision:

> Yes, use last pose / exit side / new candidate location as a signal, but not as the only decision rule.

Example:

```text
board exits left and returns near left:
  stronger same-puzzle evidence

board exits left and candidate appears far right:
  weaker same-puzzle evidence
  likely new puzzle
```

But this should be combined with template similarity and grid fit because the same puzzle could re-enter elsewhere.

Practical score components:

```text
same_board_score =
  visual_template_similarity
+ givens/grid_layout_similarity
+ pose_continuity_score
+ scale_continuity_score
+ entry/exit side score
```

### 21.17 `app.py` got messy and was repaired

The pose-aware/grid-fit patch created indentation errors in `app.py`.

Observed errors:

```text
IndentationError: unexpected indent
SyntaxError: expected 'except' or 'finally' block
```

Root cause:

> Large text-substitution patches inserted `last_good_center_px` at incorrect indentation levels in multiple branches.

Resolution:

- full `app.py` was uploaded
- a corrected `app_fixed.py` was generated
- local `app.py` was replaced from the downloaded fixed file
- `python -m py_compile app.py` passed

This restored syntactic correctness.

Important lesson:

> Stop applying giant text replacements directly to `app.py`. Move reacquisition/identity logic into smaller modules before continuing.

Recommended next structure:

```text
src/sudoku_ar_overlay/reacquisition.py
src/sudoku_ar_overlay/board_identity.py
src/sudoku_ar_overlay/grid_refinement.py
```

### 21.18 Current uncommitted local state

After replacing `app.py`, the repo showed:

```text
 M app.py
 M src/sudoku_ar_overlay/grid_validation.py
?? app.py.before_full_file_fix
?? app.py.broken_pose_patch_backup
?? app.py.broken_reacq_patch
?? assets/
?? src/sudoku_ar_overlay/grid_discovery.py
```

`app.py` compiles.

Do not commit backup files:

```text
app.py.before_full_file_fix
app.py.broken_pose_patch_backup
app.py.broken_reacq_patch
```

Do not commit large generated video/image assets yet unless choosing a final demo asset deliberately.

Recommended cleanup before commit:

```bash
rm -f app.py.before_full_file_fix app.py.broken_pose_patch_backup app.py.broken_reacq_patch
```

Recommended staged commit once behavior is acceptable:

```bash
git add app.py \
  src/sudoku_ar_overlay/grid_validation.py \
  src/sudoku_ar_overlay/grid_discovery.py \
  src/sudoku_ar_overlay/solver_adapter.py

git commit -m "Add grid-first discovery and fail-closed video tracking"
```

But only commit after verifying the current behavior is not worse than the previous checkpoint.

### 21.19 Current behavior assessment

Current behavior:

| Capability | Status |
|---|---|
| Initial static/image solve | Works |
| Initial video solve | Works |
| Optical-flow tracking while visible | Good |
| Moderate motion handling | Good |
| Hide overlay when board leaves | Much improved |
| Reject carpet/rug false positives | Grid validator works |
| Fresh solve on returned/moving frames | Unreliable |
| Reacquisition speed | Still too slow |
| Reacquired overlay fit | Still skewed |
| Same-vs-new puzzle identity | Design chosen, not fully implemented |
| Grid-corner refinement | Needed next |
| Candidate stability buffer | Needed next |
| Board fingerprint/template matching | Needed next |

### 21.20 Recommended next technical step

Do not keep tuning `app.py`.

Next build should be modular:

1. Add `grid_refinement.py`
   - input: rough Sudoku candidate corners
   - output: refined overlay-quality grid corners
   - purpose: fix skewed reacquired overlay

2. Add `reacquisition.py`
   - input: candidate history buffer
   - output: stable candidate only after motion settles
   - purpose: avoid initializing overlay on moving/partial boards

3. Add `board_identity.py`
   - cache canonical board template at initial solve
   - compare reacquired candidate to cached template
   - purpose: fast same-puzzle reacquisition without blindly reusing old solution

4. Update `app.py` only after the modules are tested independently.

The next immediate diagnostic should be:

```text
take a returned-frame candidate
run grid discovery
run grid refinement
draw rough vs refined corners
verify refined corners hug the printed Sudoku grid
```

Only after that works should it be integrated into video mode.

### 21.21 Current project interpretation

The project has crossed an important threshold.

Earlier question:

> Can we turn the static Sudoku solver into a video AR overlay?

Current answer:

> Yes, for initial solve and moderate motion. The main remaining challenge is robust reacquisition.

The hard part is now a real perception-system design problem:

```text
when the board disappears and returns, decide:
  is this the same board?
  is this a new board?
  are the corners accurate enough to render?
  is the board stable enough to solve/render?
```

This is actually a strong portfolio direction because it demonstrates applied judgment beyond simply drawing an overlay.

The next portfolio-quality milestone is:

> A known Sudoku board leaves frame, returns, is recognized as the same board via template/pose/grid evidence, waits briefly for stable geometry, refines its grid corners, and reattaches the cached overlay without skew.

After that:

> A different puzzle enters frame, cached overlay is blocked, and the system requires a fresh solve before rendering.


# `sudoku-ar-overlay` Status Update — Stable Reacquisition Milestone

**Date:** 2026-04-24  
**Recommended section:** Append as `## 22` in `docs/project_status.md`  
**Current branch:** `markerless-video-demo`  
**Purpose:** Preserve the current working milestone before pushing further on aggressive/new-puzzle reacquisition.

---

## 22. Update — Stable Refined Reacquisition Works; Aggressive New-Puzzle Stress Test Exposes Remaining Gap

### 22.1 Executive summary

The project has reached a meaningful working milestone.

The latest markerless recorded-video pipeline now produces a credible demo:

```text
clean initial solve
→ optical-flow tracking during moderate motion
→ fail-closed overlay hiding when tracking becomes implausible
→ grid-first discovery when the board returns
→ grid-corner refinement
→ stability-buffered reacquisition
→ overlay reappears with acceptable fit
```

This is the best version so far and should be treated as the current baseline.

The system is now strong enough to package as an MLE portfolio demo if framed correctly:

> A markerless planar AR-style video perception system that turns a frozen Sudoku image solver into a video overlay application with solve-once inference, optical-flow tracking, confidence-gated rendering, grid-first reacquisition, corner refinement, and safe failure behavior.

The remaining gap is not basic tracking. The remaining gap is robust **new-puzzle acquisition under aggressive motion**, especially when a second/different puzzle enters the frame and must be solved fresh rather than reusing the cached solution.

---

### 22.2 Current repo/checkpoint status

Recent confirmed commits:

```text
b4f5fa1 Add grid refinement and reacquisition stability diagnostics
7a13a98 Add grid-first discovery and fail-fast video tracking diagnostics
2a44725 Add fail-fast solver timeout and grid candidate validation
eea7901 Disable solve-based reacquisition by default
b0ad123 Update status after first optical-flow video success
8aafd3d Use optical flow tracking in video mode
```

Important note:

The most recent `app.py` integration that uses stable refined grid candidates may or may not be committed yet, depending on whether the commit was created after copying in:

```text
app_stability_integrated.py
```

Before continuing, verify:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

git status --short
git log --oneline -8
python -m py_compile app.py
```

If `app.py` is modified and the stable reacquisition behavior is the current best version, preserve it with:

```bash
git add app.py
git commit -m "Use stable refined grid candidates for video reacquisition"
```

Do not commit generated demo videos/images under `assets/` unless intentionally selecting a small final artifact.

---

### 22.3 Files/modules now added or materially changed

The project now includes several important modules beyond the original static overlay pipeline.

#### Core video/tracking app

```text
app.py
```

Current role:

- video mode
- initial solve frame
- optical-flow tracking
- fail-closed tracking loss
- grid-first discovery
- stable refined reacquisition
- debug overlays / state text
- MP4 output

#### Optical-flow tracker

```text
src/sudoku_ar_overlay/flow_tracker.py
```

Purpose:

- track board points frame-to-frame
- estimate homography with RANSAC
- update board corners quickly without rerunning full segmentation/OCR every frame

#### Grid validation

```text
src/sudoku_ar_overlay/grid_validation.py
```

Important functions:

```text
validate_sudoku_grid_candidate(...)
warp_candidate(...)
evaluate_sudoku_grid_fit(...)
```

Purpose:

- reject false positives such as carpet/rug/table texture
- check whether a candidate actually contains Sudoku-like grid-line evidence
- check whether candidate corners align with expected Sudoku grid-line locations

#### Grid-first discovery

```text
src/sudoku_ar_overlay/grid_discovery.py
```

Purpose:

- search for Sudoku-like grid candidates directly from line/contour structure
- avoid blindly trusting the segmentation model during reacquisition
- prevent false positive candidate regions from reaching OCR/rendering

#### Grid refinement

```text
src/sudoku_ar_overlay/grid_refinement.py
```

Purpose:

- take rough candidate corners
- warp to canonical view
- find actual Sudoku grid-line peaks
- refine outer corners to better match the printed Sudoku grid
- reduce skew in reacquired overlays

#### Reacquisition stability buffer

```text
src/sudoku_ar_overlay/reacquisition.py
```

Important classes:

```text
ReacquisitionCandidate
StabilityResult
CandidateStabilityBuffer
```

Purpose:

- collect candidate detections over multiple frames
- reject candidates while the board is still entering the frame or moving too much
- release only stable refined candidates for overlay initialization or fresh solving

#### Debug scripts

```text
scripts/debug_grid_refinement.py
scripts/debug_reacquisition_stability.py
```

Purpose:

- inspect rough vs refined corners on specific frames
- evaluate return-sequence stability
- produce diagnostic overlays, warps, CSVs, and montages

These scripts were essential in proving that single-frame refinement works and that the prior skew came from reacquiring too early during motion.

---

### 22.4 Major technical finding: the reacquisition problem was not one bug

The project uncovered several distinct failure modes that initially looked like one issue.

#### Failure mode 1 — optical flow attaches to random background

Earlier behavior:

```text
board leaves frame
→ optical flow tries to keep fitting old overlay somewhere
→ overlay sticks to random background
```

Current fix:

- motion/geometry plausibility gates
- area-jump checks
- corner-jump checks
- inlier-ratio checks
- minimum board-area checks
- confidence-gated render policy
- immediate hide on tracking loss

Current status:

```text
Mostly fixed.
The overlay now fails closed instead of confidently sticking to random objects.
```

#### Failure mode 2 — full solve can hang on invalid OCR givens

Earlier behavior:

```text
bad candidate frame
→ OCR predicts invalid givens
→ naive Sudoku backtracker spends a long time proving unsolvable
→ app appears hung
```

Current fix:

- fail-fast MRV Sudoku solver
- duplicate-givens validation before search
- timeout wrapper around solve calls

Current status:

```text
Fixed enough for demo safety.
Bad givens now fail quickly instead of hanging for many minutes.
```

#### Failure mode 3 — detector selects a rug/carpet, not the Sudoku board

Diagnostic result:

```text
frame_0010: real Sudoku board accepted
frame_0670: rug/carpet false positive rejected
```

The grid validator distinguished them:

```text
frame_0010 True  grid ok: score=0.160 v_peak=0.141 h_peak=0.179 v_lines=7 h_lines=10
frame_0670 False grid rejected: score=-0.007 v_peak=-0.012 h_peak=-0.003 v_lines=1 h_lines=3
```

Current fix:

- grid validation
- grid-first discovery
- reject non-grid candidates before solve/render

Current status:

```text
Major improvement.
False positives like carpet/rug candidates are now rejectable.
```

#### Failure mode 4 — rough reacquisition corners cause skewed overlay

Earlier behavior:

```text
board returns
→ rough candidate found
→ overlay initializes immediately
→ overlay is skewed / poorly fit
```

Current fix:

- grid-corner refinement
- evaluate grid fit
- candidate stability buffer
- delay overlay until candidate is stable

Current status:

```text
Substantially improved.
The latest stable/fast reacquisition videos are the best so far.
```

#### Failure mode 5 — second/new puzzle may be missed in aggressive video

Current behavior on aggressive stress clip:

```text
first known puzzle:
  performs relatively well

second/different puzzle:
  can be missed or fail to acquire
```

Current interpretation:

```text
The first puzzle has an advantage because it was solved from a clean upfront frame and may use the known-session path.

The second puzzle must go through the harder new-puzzle path:
  discover grid
  refine corners
  wait for stability
  run fresh solve on candidate
  initialize flow
```

This is the next gap, but it is a narrower problem than before.

---

### 22.5 Commands that produced the best current demo behavior

The stable candidate version worked well enough to be considered a decent demo:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_demo2_1080p30.mp4 \
  --out assets/demo/processed_iphone_demo2_stable_reacq.mp4 \
  --solve-frame 10 \
  --flow-max-corners 600 \
  --flow-min-points 30 \
  --flow-min-inlier-ratio 0.60 \
  --flow-ransac-reproj-threshold 4.0 \
  --flow-refresh-points-every 5 \
  --discover-every-n-frames 5 \
  --enable-discovery-solve \
  --solve-timeout-sec 6 \
  --discover-solve-cooldown-frames 90 \
  --discover-max-solve-attempts 4 \
  --reacquire-min-board-area-frac 0.025 \
  --reacquire-max-candidate-shift-frac 0.18 \
  --video-min-area-change-ratio 0.65 \
  --video-max-area-change-ratio 1.60 \
  --video-max-corner-jump-frac 0.20 \
  --same-pose-center-frac 0.35 \
  --same-pose-min-area-ratio 0.45 \
  --same-pose-max-area-ratio 2.25 \
  --fit-max-mean-error-px 14 \
  --fit-min-found-lines 7 \
  --refine-max-mean-error-px 18 \
  --refine-min-found-lines 7 \
  --reacq-stable-min-frames 4 \
  --reacq-stable-max-center-motion-frac 0.025 \
  --reacq-stable-max-area-ratio 1.18 \
  --reacq-stable-max-corner-motion-frac 0.035 \
  --debug
```

A faster version improved pickup speed and still looked good:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_demo2_1080p30.mp4 \
  --out assets/demo/processed_iphone_demo2_stable_reacq_fast.mp4 \
  --solve-frame 10 \
  --flow-max-corners 600 \
  --flow-min-points 30 \
  --flow-min-inlier-ratio 0.60 \
  --flow-ransac-reproj-threshold 4.0 \
  --flow-refresh-points-every 5 \
  --discover-every-n-frames 3 \
  --enable-discovery-solve \
  --solve-timeout-sec 6 \
  --discover-solve-cooldown-frames 60 \
  --discover-max-solve-attempts 4 \
  --reacquire-min-board-area-frac 0.025 \
  --reacquire-max-candidate-shift-frac 0.18 \
  --video-min-area-change-ratio 0.65 \
  --video-max-area-change-ratio 1.60 \
  --video-max-corner-jump-frac 0.20 \
  --same-pose-center-frac 0.35 \
  --same-pose-min-area-ratio 0.45 \
  --same-pose-max-area-ratio 2.25 \
  --fit-max-mean-error-px 14 \
  --fit-min-found-lines 7 \
  --refine-max-mean-error-px 18 \
  --refine-min-found-lines 7 \
  --reacq-stable-min-frames 3 \
  --reacq-stable-max-center-motion-frac 0.030 \
  --reacq-stable-max-area-ratio 1.22 \
  --reacq-stable-max-corner-motion-frac 0.040 \
  --debug
```

An even faster/ultrafast version was tested:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_demo2_1080p30.mp4 \
  --out assets/demo/processed_iphone_demo2_stable_reacq_ultrafast.mp4 \
  --solve-frame 10 \
  --flow-max-corners 600 \
  --flow-min-points 30 \
  --flow-min-inlier-ratio 0.60 \
  --flow-ransac-reproj-threshold 4.0 \
  --flow-refresh-points-every 5 \
  --discover-every-n-frames 2 \
  --enable-discovery-solve \
  --solve-timeout-sec 6 \
  --discover-solve-cooldown-frames 45 \
  --discover-max-solve-attempts 4 \
  --reacquire-min-board-area-frac 0.025 \
  --reacquire-max-candidate-shift-frac 0.20 \
  --video-min-area-change-ratio 0.65 \
  --video-max-area-change-ratio 1.60 \
  --video-max-corner-jump-frac 0.20 \
  --same-pose-center-frac 0.40 \
  --same-pose-min-area-ratio 0.40 \
  --same-pose-max-area-ratio 2.50 \
  --fit-max-mean-error-px 16 \
  --fit-min-found-lines 7 \
  --refine-max-mean-error-px 20 \
  --refine-min-found-lines 7 \
  --reacq-stable-min-frames 2 \
  --reacq-stable-max-center-motion-frac 0.040 \
  --reacq-stable-max-area-ratio 1.30 \
  --reacq-stable-max-corner-motion-frac 0.050 \
  --debug
```

User assessment:

```text
The faster versions are better.
This is now a decent demo.
The remaining drawback is that reacquisition could still be faster.
```

Recommended baseline:

```text
Use the fast or ultrafast run as the current demo baseline, depending on which visually preserves better overlay alignment.
Do not regress to earlier non-stability-buffered reacquisition.
```

---

### 22.6 Standalone diagnostics that proved the stability/refinement approach

#### Grid refinement diagnostic

Script:

```text
scripts/debug_grid_refinement.py
```

Output files inspected:

```text
rough_overlay.jpg
refined_overlay.jpg
rough_warp.jpg
refined_warp.jpg
```

Finding:

```text
Rough and refined corners both looked solid on the still frame.
This suggested that grid refinement can work.
The skew seen in video was likely caused by attaching too early while the board was moving, not by an impossible corner-refinement problem.
```

#### Reacquisition stability diagnostic

Script:

```text
scripts/debug_reacquisition_stability.py
```

Output files inspected:

```text
first_stable_overlay.jpg
first_stable_warp.jpg
reacq_stability_montage.jpg
reacq_stability.csv
```

Key finding:

```text
The board starts returning around frame ~580.
Grid discovery does not produce a valid candidate until around frame ~620.
The stability buffer releases the first stable candidate around frame ~635.
```

With the diagnostic settings:

```text
620 pending 1/4
625 pending 2/4
630 pending 3/4
635 stable
```

This means:

```text
0.5 sec after first partial appearance
~0.13 sec after first valid candidate
```

The fit error was low:

```text
frame 635 stable: fit approximately 2.8 px
frame 670 stable: fit approximately 1.8 px
```

Conclusion:

```text
Candidate stability buffering is the correct fix for the skewed reacquisition problem.
```

---

### 22.7 Aggressive stress-test video result

A more aggressive iPhone video was recorded and processed.

Representative command:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_aggressive_1080p30.mp4 \
  --out assets/demo/processed_iphone_aggressive_ultrafast_debug.mp4 \
  --solve-frame 10 \
  --flow-max-corners 600 \
  --flow-min-points 30 \
  --flow-min-inlier-ratio 0.60 \
  --flow-ransac-reproj-threshold 4.0 \
  --flow-refresh-points-every 5 \
  --discover-every-n-frames 2 \
  --enable-discovery-solve \
  --solve-timeout-sec 6 \
  --discover-solve-cooldown-frames 45 \
  --discover-max-solve-attempts 6 \
  --reacquire-min-board-area-frac 0.025 \
  --reacquire-max-candidate-shift-frac 0.20 \
  --video-min-area-change-ratio 0.65 \
  --video-max-area-change-ratio 1.60 \
  --video-max-corner-jump-frac 0.20 \
  --same-pose-center-frac 0.40 \
  --same-pose-min-area-ratio 0.40 \
  --same-pose-max-area-ratio 2.50 \
  --fit-max-mean-error-px 16 \
  --fit-min-found-lines 7 \
  --refine-max-mean-error-px 20 \
  --refine-min-found-lines 7 \
  --reacq-stable-min-frames 2 \
  --reacq-stable-max-center-motion-frac 0.040 \
  --reacq-stable-max-area-ratio 1.30 \
  --reacq-stable-max-corner-motion-frac 0.050 \
  --debug
```

Observed behavior:

```text
First puzzle:
  system performs reasonably well

Second/different puzzle:
  system misses or fails to acquire reliably
```

Current interpretation:

```text
The first puzzle benefits from clean initial solve and/or known-session state.
The second puzzle must go through the fresh new-puzzle acquisition path.
The new-puzzle path is currently weaker.
```

This is not a reason to discard the current demo. It identifies the next targeted improvement.

---

### 22.8 Why the second puzzle is missed

Likely causes:

```text
1. Stability buffer rejects the second puzzle while it is moving.
2. Discovery finds candidates, but not long enough / stable enough to trigger solve.
3. Full-solve attempts may be spent on poor early candidates.
4. Global discover-max-solve-attempts may be burned before the best second-puzzle frame appears.
5. Fresh candidate crop solving is more brittle than the cached known-puzzle path.
6. The second puzzle may be present for too few stable frames under the aggressive motion.
```

Most important distinction:

```text
Known puzzle path:
  can reuse cached state if same-pose/same-identity evidence is strong

New puzzle path:
  must fresh-solve before any overlay appears
```

The miss is acceptable as a stress-test failure if the system fails safely:

```text
Good failure:
  no overlay appears on the second puzzle

Bad failure:
  old overlay appears on the wrong puzzle
```

Current behavior appears closer to the good failure mode.

---

### 22.9 Recommended next improvement if we keep pushing

Do not rework the tracker. The next improvement should target new-puzzle acquisition.

Recommended next module/feature:

```text
CandidateCluster / best-frame fresh solve
```

New-puzzle acquisition should work like this:

```text
candidate appears
→ refine corners
→ track candidate cluster over ~0.5–1.0 sec
→ score candidate frames by:
    grid fit error
    sharpness
    board size
    stability
    grid discovery score
→ attempt fresh solve on the best 1–3 frames
→ accept first valid solve
→ initialize flow from that candidate’s refined corners
→ if all fail, show nothing and keep searching
```

This is better than the current approach:

```text
first stable candidate
→ attempt solve
→ cooldown / max attempts
```

The current global solve-attempt policy should eventually be replaced.

Bad current-ish policy:

```text
max solve attempts per video
```

Better policy:

```text
max solve attempts per candidate cluster
```

Why:

```text
The app may burn solve attempts on early bad frames.
Then when the second puzzle becomes clean/stable, the app may refuse or delay solving.
```

This is probably the best next technical fix for the aggressive-video second-puzzle miss.

---

### 22.10 Portfolio decision

Current recommendation:

> Package the current stable/fast reacquisition version as the main demo baseline. Do not chase full 3D world AR / SLAM / ARKit right now.

Why:

```text
Sudoku is a planar object.
Homography-based planar AR is the right abstraction.
The current system demonstrates practical applied perception engineering.
Full 3D world anchoring is a different project and likely a time sink.
```

The demo now shows the important MLE/product engineering skills:

```text
model reuse
video inference wrapper
solve-once state management
optical-flow tracking
homography rendering
confidence-gated display
fail-closed behavior
false-positive rejection
grid-based discovery
corner refinement
stability-buffered reacquisition
bounded solve attempts
diagnostic tooling
honest limitations
```

This is strong enough to use as a portfolio artifact if presented honestly.

Suggested README framing:

> This is not a full ARKit/SLAM system. It is a markerless planar AR-style video overlay for a flat Sudoku puzzle. It uses a frozen Sudoku solver for initial inference, optical-flow homography tracking for frame-to-frame motion, and confidence-gated grid-first reacquisition to avoid rendering when pose or board identity is uncertain.

---

### 22.11 Current known working baseline

Recommended “known good” behavior to preserve:

```text
Input:
  controlled iPhone video
  puzzle starts fully visible and still
  puzzle later moves moderately
  puzzle leaves frame
  puzzle returns

Expected:
  initial solve succeeds quickly
  overlay tracks during moderate motion
  overlay hides when tracking becomes implausible
  returned board is rediscovered
  grid corners are refined
  candidate must be stable before overlay appears
  overlay reappears with acceptable fit
```

Known limitations:

```text
fast/aggressive motion can break tracking
new/different puzzle acquisition is not yet reliable
second puzzle in aggressive stress test can be missed
reacquisition is slightly slower than ideal
overlay fit depends on stable returned frames
not a true world-anchored 3D AR system
not a live production mobile app
```

---

### 22.12 Recommended immediate preservation steps

Before experimenting further, preserve the working state.

Run:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

python -m py_compile app.py
python -m py_compile src/sudoku_ar_overlay/solver_adapter.py
python -m py_compile src/sudoku_ar_overlay/grid_validation.py
python -m py_compile src/sudoku_ar_overlay/grid_discovery.py
python -m py_compile src/sudoku_ar_overlay/grid_refinement.py
python -m py_compile src/sudoku_ar_overlay/reacquisition.py

git status --short
git log --oneline -8
```

If `app.py` contains the stable integrated reacquisition behavior and is not committed yet:

```bash
git add app.py
git commit -m "Use stable refined grid candidates for video reacquisition"
```

Then, optionally tag or branch the milestone:

```bash
git tag stable-reacq-demo-v1
```

or:

```bash
git switch -c stable-reacq-demo-v1
```

Do not commit all of `assets/` by accident.

---

### 22.13 Recommended next step after preservation

After preserving this baseline, choose one of two paths.

#### Option A — Package demo now

Recommended if time is tight.

Tasks:

```text
select best demo video
create clean no-debug output
create debug output
write README demo section
write docs/metrics.md
write limitations honestly
```

This is enough for a portfolio artifact.

#### Option B — One more technical improvement

Recommended if we want to improve aggressive/new-puzzle behavior.

Build:

```text
CandidateCluster / best-frame fresh solve
```

Purpose:

```text
fix second-puzzle misses in aggressive video
avoid burning solve attempts on bad early frames
attempt fresh solve on best candidate frames only
```

This should be implemented as another standalone module or debug script first, not by heavily patching `app.py`.

Recommended future module:

```text
src/sudoku_ar_overlay/candidate_cluster.py
```

Then integrate only after diagnostics show it picks better second-puzzle frames.

---

### 22.14 Bottom-line assessment

This is now a real portfolio demo.

It is not perfect. It is not production AR. It is not SLAM.

But it does show a strong applied MLE/perception story:

> I took a frozen computer-vision model and built a markerless video overlay system around it. I separated slow model inference from fast tracking, added confidence-gated rendering, made tracking fail closed, rejected false positives with grid validation, refined reacquired board corners, and used stability buffering to avoid drawing overlays on moving/partial boards.

Current maturity:

```text
static overlay:
  strong

controlled recorded-video demo:
  good

moderate motion:
  good enough

look-away/look-back same-puzzle reacquisition:
  decent and now demonstrable

aggressive motion:
  partially robust, fails closed in important cases

new-puzzle reacquisition:
  not reliable yet
```

Recommended preservation point:

> Treat the current stable/fast reacquisition demo as `stable-reacq-demo-v1`.

Recommended next work only if continuing:

> Add candidate-cluster best-frame solving for new-puzzle acquisition.

Otherwise:

> Freeze this as the core demo and move to README / metrics / video polish.


# `sudoku-ar-overlay` Status Update — Known-Board Identity Caching / Core Demo Freeze Candidate

**Date:** 2026-04-24  
**Recommended section:** Append as `## 23` in `docs/project_status.md`  
**Current branch:** `markerless-video-demo`  
**Purpose:** Preserve the current working state after adding known-board identity caching and deciding the core demo is ready to freeze/package rather than keep chasing deeper AR/SLAM behavior.

---

## 23. Update — Known-Board Identity Caching Added; Core Markerless Video Demo Is Ready to Package

### 23.1 Executive summary

The project has reached a strong core-demo checkpoint.

The latest implementation adds **known-board identity caching**, allowing the app to distinguish a previously solved Sudoku board from a new/different board candidate during reacquisition. This matters because the system should **reuse the clean original solution for a known board** instead of re-running OCR/Sudoku solve on later degraded frames.

Current best demo behavior:

```text
clean initial frame
→ real solver solves puzzle once
→ solved board is registered as a known board
→ optical-flow homography tracks the overlay while visible
→ overlay hides when tracking becomes implausible
→ discovery/reacquisition searches for returning board
→ known-board identity check can reattach cached solution
→ app avoids blindly re-solving the known board from worse later frames
```

This is now a legitimate MLE/perception portfolio demo.

The project should move from core algorithm work into **packaging, README polish, metrics documentation, and final demo asset creation**.

---

### 23.2 Current repo status and important commit

The known-board identity work was committed successfully:

```text
ddb0c8e Add known-board identity caching for safer reacquisition
```

This commit added/updated:

```text
app.py
src/sudoku_ar_overlay/board_identity.py
```

The terminal confirmed:

```text
[markerless-video-demo ddb0c8e] Add known-board identity caching for safer reacquisition
 2 files changed, 298 insertions(+), 1 deletion(-)
 create mode 100644 src/sudoku_ar_overlay/board_identity.py
```

This is now the key current implementation checkpoint.

---

### 23.3 Latest successful known-board identity run

Command context:

```text
input:  assets/demo/raw_iphone_aggressive_1080p30.mp4
output: assets/demo/processed_iphone_aggressive_known_board_identity.mp4
```

The latest run completed end-to-end.

Terminal output:

```text
Reading video: assets/demo/raw_iphone_aggressive_1080p30.mp4
Writing video: assets/demo/processed_iphone_aggressive_known_board_identity.mp4
Input FPS: 30.00
Total frames: 1568
Solve frame: 10

Solving frame 10 with solver=real...
Solved frame 10
Solver status: real_solved
Solve latency: 306.70 ms
Latency breakdown:
  segmentation_ms: 269.77 ms
  warp_crop_ms: 1.81 ms
  ocr_ms: 33.08 ms
  sudoku_solve_ms: 2.04 ms
  pipeline_ms: 306.70 ms

Registered known board id=1 label=initial solve

Wrote output video: assets/demo/processed_iphone_aggressive_known_board_identity.mp4
Processed frames: 1568
Wall time: 98.89 sec
Processing FPS: 15.86
Final state: SOLVED_TRACKING
Solve latency ms: 306.70
Tracking uptime: 0.706
Tracking loss events: 3
Reacquisition events: 3
```

Important numbers to preserve:

| Metric | Value |
|---|---:|
| Input FPS | 30.00 |
| Total frames | 1568 |
| Solve frame | 10 |
| Initial solve latency | 306.70 ms |
| Segmentation latency | 269.77 ms |
| OCR latency | 33.08 ms |
| Sudoku solve latency | 2.04 ms |
| Processing FPS | 15.86 |
| Tracking uptime | 0.706 |
| Tracking loss events | 3 |
| Reacquisition events | 3 |
| Final state | `SOLVED_TRACKING` |

Interpretation:

> The system processed the aggressive recorded-video test fully, solved the first puzzle, registered it as a known board, recovered from multiple loss/reacquisition events, and ended in a solved-tracking state.

---

### 23.4 What known-board identity caching fixed

Before this change, the system had a risky behavior:

```text
known puzzle returns late in video
→ app may treat it as a generic/new candidate
→ app may fresh-solve from a worse motion-blurred/angled frame
→ OCR can produce wrong givens
→ solver returns a valid but wrong solution
→ overlay appears confidently wrong
```

The known-board identity path addresses this by changing the rule:

```text
if candidate visually matches a known solved board:
  reuse cached givens/solution
  initialize overlay/tracker from current refined corners
  do not re-run OCR/Sudoku solve for that known board
```

This is the correct product behavior.

A known board should not be re-solved from a worse frame when a cleaner solution already exists in session memory.

---

### 23.5 New module: `board_identity.py`

New file:

```text
src/sudoku_ar_overlay/board_identity.py
```

Role:

```text
create visual fingerprint/template for a solved board
compare reacquired candidates against known board fingerprints
decide whether a candidate is likely the same known board
support fast/safe cached reacquisition
```

Conceptual behavior:

```text
initial solve:
  warp board to canonical view
  create normalized fingerprint/template
  store known board record with givens/solution

candidate during reacquisition:
  warp candidate to canonical view
  compute similarity to known board fingerprints
  if score exceeds threshold:
    treat as known board
    reuse cached solution
  otherwise:
    treat as unknown/new puzzle candidate
```

Current known-board parameters used in the latest run:

```text
--known-board-match-threshold 0.78
--known-board-fingerprint-size 450
```

Tuning guidance:

```text
if known board is not recognized:
  lower threshold slightly, e.g. 0.74

if a new/different board is incorrectly treated as known:
  raise threshold, e.g. 0.84
```

---

### 23.6 Current best architecture after known-board identity

The current architecture is now:

```text
Initial solve:
  real frozen sudoku-image-solver pipeline
  segmentation + OCR + Sudoku solve
  cache givens/solution/missing cells
  register known-board fingerprint

Visible tracking:
  optical flow tracks board features
  RANSAC homography updates board corners
  overlay renders by warping solved digits onto the current board plane

Tracking failure:
  motion/geometry gates reject implausible flow
  overlay hides immediately
  session retains known board state

Reacquisition:
  grid-first discovery and/or segmentation fallback finds candidates
  candidates are grid-validated
  corners are refined against Sudoku grid lines
  stability buffer waits for stable geometry
  known-board matcher checks whether this candidate is already solved
  if known: reuse cached solution
  if unknown: require fresh solve path
```

This is a clean and defensible perception-system design.

---

### 23.7 Current tracking method clarification

The project is **not** using visual odometry.

Current tracking method:

```text
optical flow + homography
```

More specifically:

```text
board solved / detected once
→ select image features on/near the board
→ track 2D feature movement frame-to-frame using optical flow
→ estimate homography with RANSAC
→ project Sudoku board corners through the homography
→ render the solved digit overlay onto the updated board plane
```

This is:

```text
2D planar object tracking
```

not:

```text
3D camera/world motion estimation
visual odometry
SLAM
VIO
ARKit/ARCore world anchoring
```

Correct README phrasing:

> Homography-based planar tracking using optical flow, not visual odometry or SLAM.

This is technically honest and appropriate because Sudoku is a flat planar target.

---

### 23.8 Why this is good enough for an MLE portfolio demo

This project now demonstrates the right skills for a hands-on MLE/applied perception portfolio artifact:

```text
reuse a frozen ML/CV model in a new application
build an inference adapter around another repo
wrap static inference in a video perception system
separate solve, track, reacquire, and render responsibilities
use confidence gates and fail-closed behavior
debug real video failure modes
add grid validation and corner refinement
use optical flow/homography for planar tracking
add known-object identity caching
measure latency, tracking uptime, loss events, and reacquisition events
document limitations honestly
```

This is much stronger than a basic static overlay.

The project does **not** need to become a full 3D AR/SLAM app to be portfolio-worthy.

Recommended framing:

> A markerless recorded-video planar AR overlay that turns a frozen Sudoku image solver into a video perception system with solve-once inference, optical-flow homography tracking, fail-closed confidence gates, stable grid reacquisition, and known-board identity caching.

---

### 23.9 Current recommendation: freeze core algorithm work

Recommendation:

```text
ship/freeze the core demo implementation
stop chasing additional tracking/reacquisition improvements for now
move to packaging
```

Reason:

The remaining improvements are now incremental and time-expensive:

```text
multi-frame solve consensus
better new-puzzle acquisition
more robust OCR voting
pose/entry-side identity scoring
cleaner configuration management
```

These are valuable, but they are not necessary for the main portfolio signal.

The main demo story is already strong.

---

### 23.10 Hero demo vs stress-test demo decision

Do **not** use the most aggressive multi-puzzle stress clip as the primary hero demo if it has any visibly wrong solution.

Recommended split:

```text
Hero demo:
  one puzzle
  clean initial solve
  moderate movement
  look away / board leaves frame
  board returns
  cached overlay reacquires correctly
  no wrong solution

Stress-test/debug demo:
  aggressive movement
  second/different puzzle
  debug overlay text
  shows limitations and failure-safe behavior
```

Why:

```text
A wrong confident overlay is worse than a delayed/missed overlay.
The hero video should be clean, reliable, and short.
The aggressive video is better as engineering evidence / limitations discussion.
```

This is the professional product/portfolio choice.

---

### 23.11 Current known limitations to document

Current limitations should be stated honestly:

```text
This is planar AR-style tracking, not full 3D AR.
No persistent world anchoring when the board is fully out of view.
Aggressive fast motion can delay or break reacquisition.
New/different puzzle acquisition is harder than known-board reacquisition.
A single bad OCR frame can still produce a wrong but valid Sudoku solution.
Multi-frame solve agreement is future work.
Live webcam mode is secondary/experimental.
Recorded iPhone video is the primary polished demo path.
```

The key limitation:

> New-puzzle acquisition still needs multi-frame solve confirmation before it is safe under aggressive motion.

Recommended future work:

```text
multi-frame OCR/solve agreement
best-candidate solve ranking
known/new board identity scoring using both visual template and givens pattern
pose/entry-side scoring
cleaner config profiles for hero/stress modes
optional mobile ARKit/ARCore implementation
```

---

### 23.12 Current best command/profile to preserve

The latest known-board identity run used this profile:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_aggressive_1080p30.mp4 \
  --out assets/demo/processed_iphone_aggressive_known_board_identity.mp4 \
  --solve-frame 10 \
  --flow-max-corners 600 \
  --flow-min-points 30 \
  --flow-min-inlier-ratio 0.60 \
  --flow-ransac-reproj-threshold 4.0 \
  --flow-refresh-points-every 5 \
  --discover-every-n-frames 2 \
  --enable-discovery-solve \
  --solve-timeout-sec 6 \
  --discover-solve-cooldown-frames 20 \
  --discover-max-solve-attempts 20 \
  --reacquire-min-board-area-frac 0.020 \
  --reacquire-max-candidate-shift-frac 0.25 \
  --grid-min-peak 0.015 \
  --grid-min-strong-lines 5 \
  --video-min-area-change-ratio 0.65 \
  --video-max-area-change-ratio 1.60 \
  --video-max-corner-jump-frac 0.20 \
  --same-pose-center-frac 0.35 \
  --same-pose-min-area-ratio 0.45 \
  --same-pose-max-area-ratio 2.25 \
  --fit-max-mean-error-px 12 \
  --fit-min-found-lines 8 \
  --refine-max-mean-error-px 14 \
  --refine-min-found-lines 8 \
  --reacq-stable-min-frames 8 \
  --reacq-stable-max-center-motion-frac 0.025 \
  --reacq-stable-max-area-ratio 1.15 \
  --reacq-stable-max-corner-motion-frac 0.030 \
  --known-board-match-threshold 0.78 \
  --known-board-fingerprint-size 450 \
  --debug
```

Recommended action:

Save this as:

```text
scripts/demo_runs/run_aggressive_known_board_identity.sh
```

and commit it.

---

### 23.13 Immediate cleanup commands

Remove local backup file:

```bash
cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

rm -f app.py.before_known_board_identity
```

Check state:

```bash
git status --short
git log --oneline -8
```

Expected remaining untracked item:

```text
?? assets/
```

That is okay.

Do not commit large generated video/image assets unless intentionally selecting a final small demo artifact.

---

### 23.14 Recommended next packaging steps

Next work should be packaging, not core algorithm work.

Suggested order:

1. Save current best run command as a script.

```bash
mkdir -p scripts/demo_runs
# create scripts/demo_runs/run_aggressive_known_board_identity.sh
git add scripts/demo_runs/run_aggressive_known_board_identity.sh
git commit -m "Save known-board aggressive demo run configuration"
```

2. Add/update docs:

```text
docs/metrics.md
README.md
docs/ROADMAP_CONTRACT.md if needed
docs/project_status.md
```

3. Create final demo assets:

```text
assets/demo/final_hero_demo.mp4      # likely not committed if too large
assets/demo/final_debug_demo.mp4     # likely not committed if too large
docs/images/demo_frame.jpg           # small screenshot likely okay
```

4. Update README with:

```text
project overview
architecture diagram
demo video/GIF or screenshot
quickstart commands
pipeline explanation
metrics table
known limitations
future work
```

5. Decide whether to push branch or merge to main.

---

### 23.15 Suggested README positioning

Recommended README headline:

> Markerless planar AR Sudoku overlay from recorded video.

Recommended summary:

> This project extends a frozen Sudoku image solver into a markerless recorded-video AR-style overlay system. It solves a clean frame once, tracks the puzzle using optical-flow homography, renders missing digits onto the board plane, hides overlays when confidence drops, and reacquires known boards using grid validation, corner refinement, stability gating, and visual identity caching.

Recommended architecture bullets:

```text
Frozen ML solver integration
Solve-once session state
Optical-flow homography tracking
Fail-closed confidence gates
Grid-first and segmentation fallback discovery
Grid-corner refinement
Candidate stability buffer
Known-board identity caching
Recorded MP4 processing
```

Recommended limitation wording:

> This is not full SLAM, visual odometry, or ARKit-style world anchoring. It is a planar AR-style overlay for a flat target. That is intentional: a Sudoku board is planar, so homography tracking is the appropriate bounded geometry.

---

### 23.16 Current project interpretation

The project has reached the intended portfolio signal.

It now shows:

```text
ML model reuse
video inference engineering
tracking and geometry
confidence gating
debugging real-world failure modes
safe reacquisition policy
known-object identity caching
practical scope control
```

The correct next move is:

```text
freeze core implementation
polish README/docs
create final hero video
add metrics
push repo
move to the next portfolio project
```

Do not let this turn into an open-ended AR research project.

The project is now good enough to present as:

> A bounded but credible markerless video perception system built around a frozen Sudoku solver, using optical-flow planar tracking and identity-aware reacquisition.


