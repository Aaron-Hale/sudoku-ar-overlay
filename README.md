# sudoku-ar-overlay

A markerless, video-based planar AR overlay for Sudoku solving.

This project extends [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) from a static ML/CV inference pipeline into a video perception system. It detects a normal physical Sudoku puzzle, solves it once, projects missing answers onto the board plane, hides the overlay when tracking confidence is low, and reacquires the solved overlay when the board returns to view.

## Current status

Local development only. Not yet published.

Current working branch:

```text
markerless-video-demo
```

Completed so far:

- static image overlay
- real solver bridge to `sudoku-image-solver`
- webcam mode
- freeze-frame solve usability
- segmentation-only tracking prototype
- optical-flow homography tracking prototype
- rendered OpenCV output recording
- roadmap pivot away from ArUco, SLAM, and ARKit

Next major implementation target:

```text
recorded iPhone video mode
```

## Demo goal

The final demo should process a recorded iPhone video of a normal Sudoku puzzle:

```text
raw iPhone video
  -> board detection
  -> solve once
  -> cache solved board state
  -> project missing digits onto the board
  -> track while confidence is high
  -> hide overlay when tracking confidence drops
  -> reacquire when the board returns
  -> write annotated MP4 and metrics
```

Target command after video mode is implemented:

```bash
PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_lookaway.mp4 \
  --out assets/demo/processed_lookaway_overlay.mp4 \
  --debug
```

## What this project demonstrates

- Frozen ML vision model reuse
- Recorded-video ingestion and output
- Sudoku board detection and solving
- Solve-once / render-many session state
- Homography-based planar overlay
- Markerless tracking from board appearance
- Confidence-gated rendering
- Tracking-loss handling
- Look-away / look-back reacquisition
- Latency, FPS, tracking, and reacquisition metrics
- Practical failure-mode documentation

## Product constraint

The final user-facing demo must work with a normal Sudoku puzzle.

It must not require:

- ArUco markers
- AprilTags
- QR codes
- added stickers or fiducials
- custom board markers
- ARKit / ARCore
- ORB-SLAM or full SLAM

## Relationship to `sudoku-image-solver`

The existing model repo owns:

- board detection
- grid warping
- occupancy inference
- digit inference
- Sudoku solving

This repo owns:

- video application logic
- AR-style overlay rendering
- session state
- markerless tracking
- confidence scoring
- tracking-loss handling
- reacquisition
- demo packaging
- metrics documentation

## Current working commands

### Static image overlay

```bash
PYTHONPATH=src python app.py \
  --mode image \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --image "$HOME/Desktop/sudoku_solver/data/raw/core_test/cte_0022.jpg" \
  --out assets/demo/app_static_real_overlay.jpg

open assets/demo/app_static_real_overlay.jpg
```

### Webcam mode

```bash
PYTHONPATH=src python app.py \
  --mode webcam \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver"
```

Useful controls:

```text
s      solve current/frozen frame
f      freeze/unfreeze frame
space  freeze/unfreeze frame
a      toggle auto-solve
r      reset
q      quit
```

Webcam mode is experimental. The primary demo path is recorded iPhone video.

## Architecture

```text
Recorded iPhone video
  -> frame reader
  -> board detection / reacquisition
  -> frozen Sudoku solver
  -> board session state
  -> markerless tracking
  -> homography overlay renderer
  -> confidence gate
  -> annotated output video + metrics
```

Core design:

```text
solve once
render many times
hide when uncertain
reacquire when visible again
```

## Tracking states

```text
NO_BOARD
BOARD_DETECTED
SOLVED_TRACKING
TRACKING_LOST
REACQUIRED
```

Expected behavior:

```text
Board visible
  -> detect board
  -> solve once
  -> render overlay

Tracking confidence high
  -> show overlay

Tracking confidence low
  -> hide overlay
  -> enter TRACKING_LOST

Board returns
  -> reacquire board
  -> reuse cached solution
  -> enter REACQUIRED
```

## Why not SLAM?

This project does not use SLAM because the primary task is board-plane anchoring, not global camera localization.

SLAM could help estimate camera motion in a world map, but it would not remove the need for board detection, board identity, homography rendering, confidence gating, tracking-loss behavior, and board reacquisition.

For a three-week MLE portfolio build, markerless planar video tracking gives a better reliability-to-complexity tradeoff than integrating ORB-SLAM, RTAB-Map, pySLAM, ARKit, or ARCore.

## Why no ArUco / fiducial markers?

Fiducial markers are useful for debugging planar AR, but they violate the product constraint.

The final demo should work from a normal Sudoku puzzle without printed codes, markers, stickers, or extra visual aids.

## Success definition

The project is successful when it can:

1. Process a recorded iPhone video of a normal Sudoku puzzle.
2. Detect the Sudoku board.
3. Solve it once.
4. Overlay only the originally missing digits.
5. Keep the overlay attached during controlled, moderate camera movement.
6. Hide the overlay when tracking confidence drops.
7. Enter `TRACKING_LOST` when the board leaves view.
8. Reacquire the board when it returns.
9. Redraw the cached solved overlay.
10. Report useful latency, FPS, tracking uptime, loss, and reacquisition metrics.

The project does not need to track through fast motion. It needs to handle fast motion professionally by failing closed and reacquiring.

## Planned metrics

| Metric | Purpose |
|---|---|
| Solve latency | Cost of frozen Sudoku inference |
| Render FPS | Output-video processing speed |
| Tracking uptime | Percent of frames with confident overlay |
| Tracking loss count | How often tracking failed closed |
| Reacquisition time | Time to reattach after board return |
| Failure reasons | Blur, low contrast, partial board, fast motion, etc. |

## Known limitations

Expected limitations:

- works best on printed Sudoku puzzles
- assumes one board at a time
- assumes the puzzle is approximately planar
- works best with good lighting and moderate camera movement
- fast motion can cause tracking loss
- faint gridlines, glare, blur, or partial occlusion may reduce tracking confidence
- significant paper bending violates the planar homography assumption
- live webcam mode is less robust than recorded iPhone video

## Future work

Possible extensions:

- faster board-corner detector
- stronger template-assisted matching
- learned feature matching such as SuperPoint / LightGlue
- better board fingerprinting
- approximate `solvePnP` pose visualization
- mobile AR/VIO integration
- multi-clip evaluation harness
