#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python app.py \
  --mode video \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --input assets/demo/raw_iphone_aggressive_1080p30.mp4 \
  --out assets/demo/processed_iphone_aggressive_very_strict_new_solve.mp4 \
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
  --debug
