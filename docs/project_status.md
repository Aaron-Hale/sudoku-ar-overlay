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
