#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/Desktop/sudoku-ar-overlay"
source .venv/bin/activate

PYTHONPATH=src python app.py \
  --mode webcam \
  --solver real \
  --repo-root "$HOME/projects/sudoku-image-solver" \
  --track-board \
  --track-every-n-frames 30 \
  --debug
