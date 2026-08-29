#!/usr/bin/env bash
# Phase 2.4 — verify Vercel frontend deployment (docs/deployment.md).
# Usage: bash scripts/verify_phase2_frontend.sh https://your-app.vercel.app [railway-api-url]
set -euo pipefail

VERCEL_URL="${1:?Usage: $0 <vercel-production-url> [railway-api-url]}"
RAILWAY_URL="${2:-}"
PAGE_URL="${VERCEL_URL%/}/"

echo "=== Phase 2 verification | ${PAGE_URL} ==="
HTML="$(curl -sfS --max-time 60 -L "${PAGE_URL}")"

if ! grep -q 'id="root"' <<< "${HTML}"; then
  echo "ERROR: Vercel page missing React root element (#root)." >&2
  exit 1
fi

if ! grep -qiE '<script[^>]+type="module"[^>]+src="/assets/' <<< "${HTML}"; then
  echo "WARN: Could not confirm Vite asset bundle in HTML (layout may still be valid)."
fi

if [ -n "${RAILWAY_URL}" ]; then
  echo "Checking Phase 1 backend at ${RAILWAY_URL} ..."
  bash "$(dirname "$0")/verify_phase1_backend.sh" "${RAILWAY_URL}"
fi

echo "Phase 2 verification OK | UI reachable at ${VERCEL_URL}"
echo "Manual check: open the URL, ask a scheme question, confirm POST goes to Railway /api/chat (not localhost)."
