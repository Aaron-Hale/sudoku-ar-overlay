# Known-Good Checkpoint — Single Solution Texture, No Inset

Created: 20260428_203901

Working path:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> Sudoku solution JSON
  -> one transparent board-sized SCNPlane solution texture
```

Notes:
- Better visual coherence than per-digit AR planes.
- Inset calibration was tested and made alignment worse.
- Current remaining issue is board/corner/pose alignment, not texture inset.

Restore:

```bash
cp "docs/checkpoints/known_good_single_solution_texture_no_inset_20260428_203901/ContentView.swift" ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```
