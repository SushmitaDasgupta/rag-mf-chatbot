#!/usr/bin/env bash
# Phase 2 — production UI build (docs/deployment.md Phase 2.2).
# Usage: VITE_API_BASE_URL=https://your-api.up.railway.app bash scripts/build_ui_production.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${VITE_API_BASE_URL:-}"

if [ -z "${API_URL}" ]; then
  echo "ERROR: VITE_API_BASE_URL is required (Railway API URL, no trailing slash)." >&2
  echo "Example: VITE_API_BASE_URL=https://your-api.up.railway.app bash scripts/build_ui_production.sh" >&2
  exit 1
fi

case "${API_URL}" in
  */) echo "ERROR: VITE_API_BASE_URL must not end with a trailing slash." >&2; exit 1 ;;
  http://127.0.0.1:*|http://localhost:*)
    echo "WARN: Building with local API URL — use Railway URL for Vercel production." >&2
    ;;
esac

echo "=== UI PRODUCTION BUILD | api=${API_URL} | $(date -u -Iseconds) ==="
cd "${ROOT_DIR}/ui"
npm run build
echo "=== UI PRODUCTION BUILD OK | output=ui/dist ==="
