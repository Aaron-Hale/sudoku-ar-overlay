# Known-Good Checkpoint — Dynamic Image Anchor Larger Crop

Created: 20260429_120645

Current best branch:

```text
ARFrame.capturedImage
  -> JPEG
  -> FastAPI /solve
  -> single transparent solution texture
  -> dynamic ARImageAnchor with larger reference crop
```

Known limitations:
- Good visual alignment when image anchor is tracked.
- Fast movement / looking away can make overlay disappear.
- Old puzzle answer can appear over new puzzle unless state is reset carefully.

Restore:

```bash
cp "docs/checkpoints/known_good_dynamic_image_anchor_larger_crop_20260429_120645/ContentView.swift" ios/SudokuAROverlay/SudokuAROverlay/ContentView.swift
cp "docs/checkpoints/known_good_dynamic_image_anchor_larger_crop_20260429_120645/app.py" python/service/app.py
```
