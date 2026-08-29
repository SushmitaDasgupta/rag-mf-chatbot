#!/usr/bin/env bash
# P1.1 — Download allowlisted scheme HTML into data/raw/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/_common.sh
source "${SCRIPT_DIR}/_common.sh"

build_scheme_args

phase_banner "P1.1 FETCH" "START"
stdbuf -oL -eL python -u -m src.ingest.fetch --fetch-fallback-cached "${INGEST_SCHEME_ARGS[@]}"
phase_banner "P1.1 FETCH" "END"
