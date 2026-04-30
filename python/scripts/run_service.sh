#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHONPATH=. python -m uvicorn python.service.app:app --host 0.0.0.0 --port 8000
