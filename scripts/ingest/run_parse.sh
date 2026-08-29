#!/usr/bin/env bash
# P1.2 — Extract text/tables from raw HTML into data/processed/parsed/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/_common.sh
source "${SCRIPT_DIR}/_common.sh"

build_scheme_args

phase_banner "P1.2 PARSE" "START"
stdbuf -oL -eL python -u -m src.ingest.parse "${INGEST_SCHEME_ARGS[@]}"
phase_banner "P1.2 PARSE" "END"
