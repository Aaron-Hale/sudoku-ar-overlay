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
2. **Model / perception runtime** — the solver repo's frozen hot-path benchmark.
3. **API / service-boundary overhead** — the measurable cost of using a local FastAPI backend instead of an edge/on-device deployment.

## Measurement setup

- Device path: physical iPhone running the AR app
- Backend: local Mac-hosted FastAPI service
- Network: same local Wi-Fi
- Trial type: warm local-backend validation run
- Number of measured scans: 20
- Result: 20 / 20 scans returned a solved board and placed an overlay

These are prototype integration metrics, not a full multi-condition AR benchmark.

## Top-line readout

| Category | Metric | Result | What it means |
|---|---|---:|---|
| **FastAPI demo** | Scan-to-overlay success | **20 / 20** | Current app path successfully solved and rendered overlay in all measured warm runs |
| **FastAPI demo** | p50 scan-to-overlay latency | **756.9 ms** | Tap **Scan** to AR overlay placed |
| **FastAPI demo** | p95 scan-to-overlay latency | **917.2 ms** | Tail latency for the current local-backend demo |
| **Backend `/solve`** | p50 backend-reported latency | **501.0 ms** | Backend-reported solve time in the AR service path |
| **Backend `/solve`** | p95 backend-reported latency | **551.1 ms** | Backend-reported solve tail latency in the AR service path |
| **Solver repo** | Frozen hot-path runtime | **233.2 ms mean / 239.6 ms p95** | Published solver-repo benchmark; owned by `sudoku-image-solver`, not this AR repo |
| **API / app overhead** | Implied p50 overhead | **~255.9 ms** | p50 scan-to-overlay minus p50 backend-reported latency |
| **API / app overhead** | Implied p95 overhead | **~366.1 ms** | p95 scan-to-overlay minus p95 backend-reported latency |

## Full measured breakdown

| Metric | Mean | p50 | p90 | p95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| Capture + JPEG encode | 22.4 ms | 23.0 ms | 25.4 ms | 25.9 ms | 17.3 ms | 27.1 ms |
| Request round trip | 725.9 ms | 712.5 ms | 838.7 ms | 874.6 ms | 616.6 ms | 901.6 ms |
| Overlay placement | 18.4 ms | 18.1 ms | 20.2 ms | 20.6 ms | 15.7 ms | 23.1 ms |
| Total scan-to-overlay | 771.4 ms | 756.9 ms | 885.1 ms | 917.2 ms | 664.8 ms | 947.7 ms |
| Backend-reported solver latency | 506.0 ms | 501.0 ms | 515.1 ms | 551.1 ms | 488.3 ms | 553.6 ms |

## How to interpret the latency

The current demo is intentionally **not** an edge deployment. It is a local FastAPI prototype that uses a Mac-hosted Python solver over Wi-Fi. That is useful for development because the solver can stay in Python, but it adds a service boundary that a production iOS app should not need.

The measured p50 scan-to-overlay latency is **756.9 ms**, but that does not mean the model itself is taking 756.9 ms. The measured p50 backend-reported solve latency is **501.0 ms**, and the companion solver repo reports a frozen hot-path runtime of **233.2 ms mean / 239.6 ms p95**.

The measured local API/app overhead is:

```text
p50 overhead = 756.9 ms - 501.0 ms = 255.9 ms
p95 overhead = 917.2 ms - 551.1 ms = 366.1 ms
```

This overhead includes local Wi-Fi upload, FastAPI request handling, multipart parsing, JSON response handling, and app-side overlay update.

## Prototype vs. edge deployment

A production iOS deployment should move the perception stack on-device with Core ML or a similar edge/mobile runtime.

The expected benefit is not a made-up final latency number. The defensible claim is narrower:

> An edge/on-device implementation is expected to remove the local Wi-Fi and FastAPI service-boundary dependency. In this prototype, that measured service-boundary/app overhead is approximately **256 ms p50 / 366 ms p95**.

An optimized edge implementation may also reduce the gap between the AR service's backend-reported latency and the companion solver repo's frozen hot-path runtime, but that should be treated as a benchmark target, not a claimed result. Final on-device latency should be reported only after converting the perception stack and measuring it on an actual iPhone.

## External deployment rationale

Apple's Core ML documentation states that Core ML runs predictions on a person's device, optimizes on-device performance by leveraging CPU, GPU, and Neural Engine, and removes the need for a network connection when a model runs strictly on-device. AWS's edge-computing documentation similarly frames edge deployment as moving compute closer to users/devices to improve application performance, reduce bandwidth needs, and provide faster real-time behavior.

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
