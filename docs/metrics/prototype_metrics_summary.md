# Sudoku AR Overlay — Prototype Metrics Summary

## Scope

These metrics describe the live AR/mobile integration layer in `sudoku-ar-overlay`.

Formal OCR/model accuracy and frozen perception benchmarks live in the companion [`sudoku-image-solver`](https://github.com/Aaron-Hale/sudoku-image-solver) repo. This summary measures the local-backend AR prototype path:

```text
iPhone Scan tap
  -> ARFrame.capturedImage
  -> JPEG encode
  -> local FastAPI /solve request
  -> companion solver backend
  -> JSON response
  -> AR overlay placement
```

The goal is to separate three things that are easy to blur together:

1. **FastAPI demo latency** — the current end-to-end prototype.
2. **Backend service latency** — the local `/solve` service path used by the AR app.
3. **Solver hot-path runtime** — the companion solver repo's frozen perception benchmark.

## Measurement setup

- Device path: physical iPhone running the AR app
- Backend: local Mac-hosted FastAPI service
- Network: same local Wi-Fi
- Trial type: warm local-backend validation run
- Number of measured scans: 20
- Result: 20 / 20 scans returned a solved board and placed an overlay

These are prototype integration metrics, not a full multi-condition AR benchmark.

## FastAPI demo: end-to-end AR path

| Metric | Result | Notes |
|---|---:|---|
| Scan-to-overlay success | **20 / 20** | Successful backend solve and visible AR overlay |
| Mean scan-to-overlay latency | **771.4 ms** | Tap **Scan** → AR overlay placed |
| p50 scan-to-overlay latency | **756.9 ms** | Tap **Scan** → AR overlay placed |
| p90 scan-to-overlay latency | **885.1 ms** | Tap **Scan** → AR overlay placed |
| p95 scan-to-overlay latency | **917.2 ms** | Tap **Scan** → AR overlay placed |
| Min / max scan-to-overlay latency | **664.8 ms / 947.7 ms** | Warm validation run |

## Backend `/solve`: local service path

| Metric | Result | Notes |
|---|---:|---|
| Mean backend-reported latency | **506.0 ms** | Backend `/solve` reported latency |
| p50 backend-reported latency | **501.0 ms** | Backend `/solve` reported latency |
| p90 backend-reported latency | **515.1 ms** | Backend `/solve` reported latency |
| p95 backend-reported latency | **551.1 ms** | Backend `/solve` reported latency |
| Min / max backend-reported latency | **488.3 ms / 553.6 ms** | Warm validation run |

## App-side overhead

| Metric | Mean | p50 | p90 | p95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| Capture + JPEG encode | 22.4 ms | 23.0 ms | 25.4 ms | 25.9 ms | 17.3 ms | 27.1 ms |
| Request round trip | 725.9 ms | 712.5 ms | 838.7 ms | 874.6 ms | 616.6 ms | 901.6 ms |
| Overlay placement | 18.4 ms | 18.1 ms | 20.2 ms | 20.6 ms | 15.7 ms | 23.1 ms |

## Solver hot-path runtime

The companion `sudoku-image-solver` repo reports **233.2 ms mean** hot steady-state latency and **239.6 ms p95** for its frozen solver path. That benchmark belongs to the solver repo because it is the evaluated perception stack.

The AR repo uses that solver through a local FastAPI service, so the end-to-end app latency includes additional service-boundary and mobile integration overhead.

## Prototype vs. edge deployment

The current demo is intentionally **not** an edge deployment. It is a local FastAPI prototype that uses a Mac-hosted Python solver over Wi-Fi. That is useful for development because the solver can stay in Python, but it adds a service boundary that a production iOS app should not need.

The measured p50 scan-to-overlay latency is **756.9 ms**, but that does not mean the model itself is taking 756.9 ms. The measured p50 backend-reported solve latency is **501.0 ms**, and the companion solver repo reports a frozen hot-path runtime of **233.2 ms mean / 239.6 ms p95**.

Measured prototype overhead:

```text
p50 API/app overhead = 756.9 ms - 501.0 ms = 255.9 ms
p95 API/app overhead = 917.2 ms - 551.1 ms = 366.1 ms
```

This overhead includes local Wi-Fi upload, FastAPI request handling, multipart parsing, JSON response handling, and app-side overlay update.

A production edge/on-device implementation is expected to remove the local Wi-Fi and FastAPI service-boundary dependency. Final on-device latency is not claimed here because the perception stack has not yet been converted to Core ML or benchmarked on an actual iPhone.

## External deployment rationale

Apple's Core ML documentation states that Core ML runs predictions on a person's device and optimizes on-device performance by leveraging CPU, GPU, and Neural Engine while removing the need for a network connection when a model runs strictly on-device. AWS's edge-computing documentation similarly frames edge deployment as moving compute closer to users/devices to improve performance, reduce bandwidth needs, and support faster real-time behavior.

References:

- [Apple Core ML documentation](https://developer.apple.com/documentation/coreml)
- [Apple Core ML overview](https://developer.apple.com/machine-learning/core-ml/)
- [AWS: What is Edge Computing?](https://aws.amazon.com/what-is/edge-computing/)

## Limitations

This was a warm local-backend validation run, not a full benchmark across lighting, viewing angle, puzzle type, and tracking/reacquisition conditions.

Not yet measured here:

- Pixel-level AR registration error
- Overlay jitter while stationary
- Tracking usability across a timed movement protocol
- Reacquisition success after looking away
- False-attach rate on different puzzles
- Actual Core ML / on-device latency

Those should be measured before claiming production-level AR robustness or final edge performance.
