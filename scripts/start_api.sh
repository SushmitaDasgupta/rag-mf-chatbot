#!/usr/bin/env bash
# Production API entrypoint (Railway Phase 1.2).
# Uses $PORT from the platform; defaults to 8000 for local runs.
set -euo pipefail

HOST="${API_HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "=== API START | host=${HOST} port=${PORT} | $(date -u -Iseconds) ==="
exec uvicorn src.api.main:app --host "${HOST}" --port "${PORT}"
