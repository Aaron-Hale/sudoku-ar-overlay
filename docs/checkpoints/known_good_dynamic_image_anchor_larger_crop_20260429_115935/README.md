# Known-Good Checkpoint — Dynamic Image Anchor Larger Crop

Created: 20260429_115935

Working branch:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> single transparent solution texture
  -> dynamic ARImageAnchor with larger reference crop
```

Notes:
- Better alignment / less floating than table-plane-only version.
- Larger crop uses boardReferenceMarginScale = 1.25.
- Fast movement or moving out of frame can still cause image tracking to disappear/reacquire.
- Failed experiments reverted:
  - persistent hold-last-pose overlay
  - hybrid fallback patch
  - image-pose-to-world-anchor promotion
  - texture inset calibration

Restore:

```bash
cp "docs/checkpoints/known_good_dynamic_image_anchor_larger_crop_20260429_115935/ContentView.swift" ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
```
