# sudoku-ar-overlay

A real-time planar AR overlay for Sudoku solving.

This project extends `sudoku-image-solver` from a static ML/CV inference pipeline into a live AR-style application. The goal is to detect a physical Sudoku board, solve it once, anchor the missing digits to the board plane, stabilize the overlay across video frames, and reacquire the board after temporary tracking loss.

## Project status

Local development only. Not yet published.

## Intended scope

This is not a full SLAM system. The first successful version uses planar tracking because the target object is a flat Sudoku board.

Core concepts demonstrated:

- ML vision model reuse
- real-time camera loop
- homography-based planar overlay
- solve-once session state
- temporal smoothing
- board reacquisition after tracking loss
- latency/FPS reporting
- optional pose estimation with `solvePnP`

## Relationship to `sudoku-image-solver`

The existing model repo owns:

- board detection
- grid warping
- occupancy inference
- digit inference
- Sudoku solving

This repo owns:

- live camera application
- AR-style overlay rendering
- tracking state
- smoothing
- reacquisition
- demo packaging

## Success definition

The project is successful when it can:

1. Detect a Sudoku board in a live camera feed.
2. Solve it once.
3. Overlay only the missing digits.
4. Keep the overlay attached to the board under moderate camera movement.
5. Hide the overlay when the board leaves view.
6. Reacquire the same solved overlay when the board returns.
7. Report useful latency/FPS metrics.
