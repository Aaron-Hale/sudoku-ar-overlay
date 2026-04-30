#!/usr/bin/env python3
"""
Benchmark the local FastAPI /solve endpoint using a fixed image.

Purpose:
- isolate backend + solver latency from iPhone/AR/network UI effects
- distinguish cold/warm backend behavior
- write repeatable CSV metrics to assets/metrics/

Example:
  python python/scripts/benchmark_solve_endpoint.py \
    --image assets/demo/test_image.jpg \
    --trials 20 \
    --warmup 3
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None

    values_sorted = sorted(values)
    if len(values_sorted) == 1:
        return values_sorted[0]

    rank = (len(values_sorted) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(values_sorted) - 1)
    weight = rank - low

    return values_sorted[low] * (1 - weight) + values_sorted[high] * weight


def fmt_ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f} ms"


def post_solve(base_url: str, image_path: Path, timeout_s: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/solve"

    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    metadata_json = '{"source":"backend_solve_benchmark"}'

    started = time.perf_counter()

    with image_path.open("rb") as f:
        response = requests.post(
            url,
            files={"image": (image_path.name, f, mime_type)},
            data={"metadata_json": metadata_json},
            timeout=timeout_s,
        )

    ended = time.perf_counter()
    wall_ms = (ended - started) * 1000.0

    row: dict[str, Any] = {
        "created_at": now_iso(),
        "trial_id": str(uuid.uuid4()),
        "image_path": str(image_path),
        "status_code": response.status_code,
        "client_wall_ms": round(wall_ms, 3),
    }

    try:
        payload = response.json()
    except Exception:
        row.update(
            {
                "status": "non_json_response",
                "message": response.text[:500],
                "backend_latency_ms": "",
                "givens_count": "",
                "image_width": "",
                "image_height": "",
            }
        )
        return row

    row.update(
        {
            "status": payload.get("status", ""),
            "message": payload.get("message", ""),
            "backend_latency_ms": payload.get("latency_ms", ""),
            "givens_count": payload.get("givens_count", ""),
            "image_width": payload.get("image_width", ""),
            "image_height": payload.get("image_height", ""),
        }
    )

    return row


def write_rows(output_path: Path, rows: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "created_at",
        "trial_id",
        "image_path",
        "status_code",
        "status",
        "message",
        "client_wall_ms",
        "backend_latency_ms",
        "givens_count",
        "image_width",
        "image_height",
    ]

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def summarize(rows: list[dict[str, Any]]) -> None:
    wall_values: list[float] = []
    backend_values: list[float] = []
    solved = 0

    for row in rows:
        if row.get("status") == "solved":
            solved += 1

        try:
            wall_values.append(float(row["client_wall_ms"]))
        except Exception:
            pass

        try:
            backend_values.append(float(row["backend_latency_ms"]))
        except Exception:
            pass

    total = len(rows)

    print()
    print("Backend /solve benchmark summary")
    print("--------------------------------")
    print(f"Trials: {total}")
    print(f"Solved: {solved}/{total}")

    if wall_values:
        print()
        print("Client wall-clock latency:")
        print(f"  mean: {fmt_ms(statistics.mean(wall_values))}")
        print(f"  p50:  {fmt_ms(percentile(wall_values, 50))}")
        print(f"  p90:  {fmt_ms(percentile(wall_values, 90))}")
        print(f"  p95:  {fmt_ms(percentile(wall_values, 95))}")
        print(f"  min:  {fmt_ms(min(wall_values))}")
        print(f"  max:  {fmt_ms(max(wall_values))}")

    if backend_values:
        print()
        print("Backend-reported solver latency:")
        print(f"  mean: {fmt_ms(statistics.mean(backend_values))}")
        print(f"  p50:  {fmt_ms(percentile(backend_values, 50))}")
        print(f"  p90:  {fmt_ms(percentile(backend_values, 90))}")
        print(f"  p95:  {fmt_ms(percentile(backend_values, 95))}")
        print(f"  min:  {fmt_ms(min(backend_values))}")
        print(f"  max:  {fmt_ms(max(backend_values))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument(
        "--output",
        default="assets/metrics/backend_solve_benchmark.csv",
    )

    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    output_path = Path(args.output)

    print(f"Base URL: {args.base_url}")
    print(f"Image: {image_path}")
    print(f"Warmup trials: {args.warmup}")
    print(f"Measured trials: {args.trials}")
    print(f"Output: {output_path}")

    for i in range(args.warmup):
        print(f"Warmup {i + 1}/{args.warmup}...", flush=True)
        row = post_solve(args.base_url, image_path, args.timeout_s)
        print(
            f"  status={row.get('status')} "
            f"wall_ms={row.get('client_wall_ms')} "
            f"backend_ms={row.get('backend_latency_ms')}"
        )

    rows: list[dict[str, Any]] = []
    for i in range(args.trials):
        print(f"Trial {i + 1}/{args.trials}...", flush=True)
        row = post_solve(args.base_url, image_path, args.timeout_s)
        rows.append(row)
        print(
            f"  status={row.get('status')} "
            f"wall_ms={row.get('client_wall_ms')} "
            f"backend_ms={row.get('backend_latency_ms')} "
            f"givens={row.get('givens_count')}"
        )

    write_rows(output_path, rows)
    summarize(rows)
    print()
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
