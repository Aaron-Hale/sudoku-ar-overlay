# Metrics

## Primary demo

Primary clean demo output:

```text
assets/demo/final_demo_clean.mp4
```

Debug/stress demo output:

```text
assets/demo/processed_iphone_aggressive_known_board_identity.mp4
```

Clean demo run script:

```text
scripts/demo_runs/run_aggressive_known_board_identity_clean.sh
```

Debug/stress run script:

```text
scripts/demo_runs/run_aggressive_known_board_identity.sh
```

## Latest clean demo run

| Metric | Value |
|---|---:|
| Input FPS | 30.00 |
| Total frames | 1,568 |
| Initial solve frame | 10 |
| Initial solve latency | 318.66 ms |
| Segmentation latency | 278.01 ms |
| Warp/crop latency | 1.23 ms |
| OCR latency | 37.20 ms |
| Sudoku solve latency | 2.22 ms |
| Offline processing FPS | 15.31 |
| Tracking uptime | 0.706 |
| Tracking loss events | 3 |
| Reacquisition events | 3 |
| Final state | SOLVED_TRACKING |

## Latest debug/stress run

| Metric | Value |
|---|---:|
| Input FPS | 30.00 |
| Total frames | 1,568 |
| Initial solve frame | 10 |
| Initial solve latency | 388.34 ms |
| Segmentation latency | 347.26 ms |
| Warp/crop latency | 1.26 ms |
| OCR latency | 38.22 ms |
| Sudoku solve latency | 1.59 ms |
| Offline processing FPS | 15.41 |
| Tracking uptime | 0.706 |
| Tracking loss events | 3 |
| Reacquisition events | 3 |
| Final state | SOLVED_TRACKING |

## Interpretation

This is a markerless planar video overlay demo. It uses optical-flow homography tracking and confidence-gated reacquisition, not visual odometry, SLAM, ARKit, or ARCore.

The system is designed to:

1. solve a clean frame once,
2. render solved digits while tracking confidence is high,
3. hide the overlay when tracking becomes unreliable,
4. reacquire the board when it returns,
5. avoid confidently rendering onto random background regions.

The reported processing FPS is offline video-processing throughput, not real-time camera FPS. The demo input is a recorded 30 FPS iPhone video.

## Known limitations

- Works best on printed Sudoku boards with good lighting and moderate motion.
- Fast/aggressive motion can trigger tracking loss.
- New-puzzle acquisition is harder than known-board reacquisition.
- Single-frame OCR errors can produce wrong Sudoku solutions if a new board is solved from a poor crop.
- Known-board identity caching improves reacquisition for a previously solved board but is not a full object-recognition system.
- The system uses planar optical-flow/homography tracking, not full 3D world anchoring.
- Webcam mode remains experimental; recorded iPhone video is the primary demo path.
