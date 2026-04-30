from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import Body, FastAPI, File, Form, UploadFile

from .sudoku_solver_client import DEFAULT_SOLVER_REPO, solve_frame_for_ar, to_py


app = FastAPI(title="Sudoku AR Overlay Solver Service")


METRICS_DIR = Path("assets/metrics")
AR_TRIALS_CSV = METRICS_DIR / "ar_trials.csv"

AR_TRIAL_FIELDNAMES = [
    "created_at",
    "trial_id",
    "event_source",
    "puzzle_id",
    "condition",
    "backend_url",
    "status",
    "solve_status",
    "overlay_placed",
    "user_visible_success",
    "failure_stage",
    "givens_count",
    "image_width",
    "image_height",
    "capture_encode_ms",
    "request_roundtrip_ms",
    "response_decode_ms",
    "overlay_place_ms",
    "total_scan_to_overlay_ms",
    "total_scan_attempt_ms",
    "backend_latency_ms",
    "tracking_window_s",
    "tracking_lost_count",
    "overlay_remained_visible",
    "overlay_remained_usable",
    "reacquisition_attempted",
    "reacquisition_success",
    "reacquisition_time_ms",
    "false_attach_observed",
    "visual_alignment_rating",
    "notes",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flatten_metric_payload(payload: dict[str, Any]) -> dict[str, Any]:
    row = {key: "" for key in AR_TRIAL_FIELDNAMES}
    row["created_at"] = payload.get("created_at") or utc_now_iso()

    for key in AR_TRIAL_FIELDNAMES:
        if key in payload and payload[key] is not None:
            row[key] = payload[key]

    return row


def append_ar_trial_metric(payload: dict[str, Any]) -> Path:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = AR_TRIALS_CSV.exists()

    row = _flatten_metric_payload(payload)

    with AR_TRIALS_CSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AR_TRIAL_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    return AR_TRIALS_CSV


# REQUEST_START_LOGGING_MIDDLEWARE
@app.middleware("http")
async def request_start_logging(request, call_next):
    import time
    import uuid

    rid = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    print(f"[{rid}] REQUEST START {request.method} {request.url.path}", flush=True)

    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(
            f"[{rid}] REQUEST END {request.method} {request.url.path} "
            f"status={response.status_code} elapsed_ms={elapsed_ms:.1f}",
            flush=True,
        )
        return response
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(
            f"[{rid}] REQUEST ERROR {request.method} {request.url.path} "
            f"elapsed_ms={elapsed_ms:.1f} error={type(e).__name__}: {e}",
            flush=True,
        )
        raise



@app.get("/health")
def health():
    solver_repo = os.environ.get("SUDOKU_SOLVER_REPO", DEFAULT_SOLVER_REPO)
    return {
        "status": "ok",
        "solver_repo": solver_repo,
        "solver_repo_exists": Path(solver_repo).expanduser().exists(),
    }


@app.post("/metrics")
async def metrics(payload: dict[str, Any] = Body(...)):
    """Append AR/mobile prototype metrics to a local CSV.

    This endpoint is intentionally simple:
    - no database
    - no authentication
    - local-development use only
    - generated CSV stays under assets/metrics/ and is ignored by git

    Curated metrics can later be copied into docs/metrics/ after review.
    """
    path = append_ar_trial_metric(payload)
    return {
        "status": "ok",
        "metrics_path": str(path),
    }


@app.post("/solve")
async def solve(
    image: UploadFile = File(...),
    metadata_json: str | None = Form(default=None),
):
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            metadata = {"metadata_parse_error": metadata_json}

    raw = await image.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if frame is None:
        return {
            "status": "failed",
            "message": "Could not decode uploaded image.",
            "latency_ms": 0.0,
            "confidence": 0.0,
            "image_width": None,
            "image_height": None,
            "corners_px": None,
            "givens": None,
            "solution": None,
            "givens_count": 0,
            "debug": {
                "metadata": metadata,
            },
        }

    solver_repo = os.environ.get("SUDOKU_SOLVER_REPO", DEFAULT_SOLVER_REPO)

    result = solve_frame_for_ar(
        frame,
        repo_root=solver_repo,
        debug_dir="assets/debug",
    )

    response = to_py(result.__dict__)
    response["debug"]["metadata"] = metadata
    return response


@app.post("/detect")
async def detect(
    image: UploadFile = File(...),
    metadata_json: str | None = Form(default=None),
):
    """Experimental board reacquisition endpoint.

    For now this reuses the existing solver pipeline so it can return:
    - status
    - corners_px
    - givens
    - solution
    - givens_count

    Later, this should become a cheaper detect-only path.
    """
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            metadata = {"metadata_parse_error": metadata_json}

    raw = await image.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if frame is None:
        return {
            "status": "failed",
            "message": "Could not decode uploaded image.",
            "latency_ms": 0.0,
            "confidence": 0.0,
            "image_width": None,
            "image_height": None,
            "corners_px": None,
            "givens": None,
            "solution": None,
            "givens_count": 0,
            "debug": {
                "metadata": metadata,
                "mode": "detect",
            },
        }

    solver_repo = os.environ.get("SUDOKU_SOLVER_REPO", DEFAULT_SOLVER_REPO)

    result = solve_frame_for_ar(
        frame,
        repo_root=solver_repo,
        debug_dir="assets/debug",
    )

    response = to_py(result.__dict__)
    response["debug"]["metadata"] = metadata
    response["debug"]["mode"] = "detect_reacquisition"
    return response

