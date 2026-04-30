# Sudoku AR Overlay — Prototype Metrics Summary

## Scope

These metrics describe the live AR/mobile integration layer in `sudoku-ar-overlay`.

Formal OCR/model accuracy lives in the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo. This summary measures the local-backend AR prototype path:

```text
iPhone Scan tap
  -> ARFrame.capturedImage
  -> JPEG encode
  -> local FastAPI /solve request
  -> companion solver backend
  -> JSON response
  -> AR overlay placement
```

## Measurement setup

- Device path: physical iPhone running the AR app
- Backend: local Mac-hosted FastAPI service
- Network: same local Wi-Fi
- Trial type: warm local-backend validation run
- Number of measured scans: 20
- Result: 20 / 20 scans returned a solved board and placed an overlay

These are prototype integration metrics, not a full multi-condition AR benchmark.

## Results

| Metric | Mean | p50 | p90 | p95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| Capture + JPEG encode | 22.4 ms | 23.0 ms | 25.4 ms | 25.9 ms | 17.3 ms | 27.1 ms |
| Request round trip | 725.9 ms | 712.5 ms | 838.7 ms | 874.6 ms | 616.6 ms | 901.6 ms |
| Overlay placement | 18.4 ms | 18.1 ms | 20.2 ms | 20.6 ms | 15.7 ms | 23.1 ms |
| Total scan-to-overlay | 771.4 ms | 756.9 ms | 885.1 ms | 917.2 ms | 664.8 ms | 947.7 ms |
| Backend-reported solver latency | 506.0 ms | 501.0 ms | 515.1 ms | 551.1 ms | 488.3 ms | 553.6 ms |

## Top-line prototype result

| Metric | Result |
|---|---:|
| Scan-to-overlay success | 20 / 20 |
| p50 scan-to-overlay latency | 756.9 ms |
| p95 scan-to-overlay latency | 917.2 ms |
| p50 backend-reported latency | 501.0 ms |
| p95 backend-reported latency | 551.1 ms |

## Interpretation

The measured warm path is dominated by backend request/solver time. Capture/JPEG encoding and overlay placement are relatively small contributors.

The difference between backend-reported solver latency and total scan-to-overlay latency mostly reflects local network request overhead, HTTP/multipart handling, JSON response handling, and app-side UI/overlay update time.

This supports the production roadmap: moving perception on-device with Core ML or a similar edge deployment path should remove the local Wi-Fi/backend dependency and reduce network overhead, though final on-device latency would need to be measured separately after conversion.

## Limitations

This was a warm local-backend validation run, not a full benchmark across lighting, viewing angle, puzzle type, and tracking/reacquisition conditions.

Not yet measured here:

- Pixel-level AR registration error
- Overlay jitter while stationary
- Tracking usability across a timed movement protocol
- Reacquisition success after looking away
- False-attach rate on different puzzles

Those should be measured before claiming production-level AR robustness.
