#!/usr/bin/env bash
# Phase 1.5 — verify Railway backend health (docs/deployment.md).
# Usage: bash scripts/verify_phase1_backend.sh https://your-service.up.railway.app
set -euo pipefail

BASE_URL="${1:?Usage: $0 <railway-api-base-url>}"
HEALTH_URL="${BASE_URL%/}/api/health"

echo "=== Phase 1 verification | ${HEALTH_URL} ==="
BODY="$(curl -sfS --max-time 120 "${HEALTH_URL}")"
echo "${BODY}"

python3 -c "
import json
import sys

data = json.loads(sys.argv[1])
errors = []
if data.get('status') != 'ok':
    errors.append(f\"status={data.get('status')!r} (expected 'ok')\")
if int(data.get('vector_count') or 0) <= 0:
    errors.append(f\"vector_count={data.get('vector_count')!r} (expected > 0)\")
if not data.get('groq_configured'):
    errors.append('groq_configured=false (set GROQ_API_KEY on Railway)')
if errors:
    print('Phase 1 verification FAILED:', file=sys.stderr)
    for err in errors:
        print(f'  - {err}', file=sys.stderr)
    sys.exit(1)
print(
    'Phase 1 verification OK | '
    f\"vectors={data['vector_count']} | \"
    f\"schemes={data.get('schemes_locked')} | \"
    f\"model={data.get('groq_model')}\"
)
" "${BODY}"
