from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile

from .sudoku_solver_client import DEFAULT_SOLVER_REPO, solve_frame_for_ar, to_py


app = FastAPI(title="Sudoku AR Overlay Solver Service")


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
