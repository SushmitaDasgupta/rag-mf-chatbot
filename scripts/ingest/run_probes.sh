#!/usr/bin/env bash
# P1.5 — Post-index retrieval smoke probes (quality gate before corpus commit).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/_common.sh
source "${SCRIPT_DIR}/_common.sh"

phase_banner "P1.5 RETRIEVAL PROBES" "START"
stdbuf -oL -eL python -u scripts/retrieval_probe.py
phase_banner "P1.5 RETRIEVAL PROBES" "END"
