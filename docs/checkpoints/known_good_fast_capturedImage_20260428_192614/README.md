# Known-Good Checkpoint — Fast capturedImage AR Solve

Created: 20260428_192614

## Status

This is the current known-good iOS + Python integration state.

## What works

- iPhone app opens AR camera.
- Backend is reachable from iPhone over local network.
- App sends raw AR camera frame using `frame.capturedImage`.
- Python FastAPI `/solve` receives the frame.
- Solver returns Sudoku solution.
- App renders blue flat SCNPlane digit textures.
- No `sceneView.snapshot()` path.
- No `SCNText` 3D mesh digits.
- No yellow ARKit feature-point debug dots.

## Important implementation notes

The current working path is:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> corners + givens + solution
  -> ARKit raycast placement
  -> flat blue SCNPlane digit overlays
```

Do not replace this with `sceneView.snapshot()` unless intentionally experimenting. The snapshot path became slower and less reliable.

## Restore command

From project root:

```bash
cp "docs/checkpoints/known_good_fast_capturedImage_20260428_192614/ContentView.swift" ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```
