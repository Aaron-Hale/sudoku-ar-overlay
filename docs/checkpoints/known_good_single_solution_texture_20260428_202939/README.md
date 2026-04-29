# Known-Good Checkpoint — Single Solution Texture Overlay

Created: 20260428_202939

This checkpoint keeps the fast capturedImage solve path and uses one transparent board-sized solution texture on a single SCNPlane.

Observed:
- Solves successfully.
- Display feels more natural and less floaty than per-digit AR nodes.
- Remaining issue: solved numbers sometimes do not align exactly with printed grid cells.

Restore:

```bash
cp "docs/checkpoints/known_good_single_solution_texture_20260428_202939/ContentView.swift" ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```
