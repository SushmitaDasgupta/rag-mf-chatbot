#!/usr/bin/env bash
# P1.3 — Build section-aware chunks in data/processed/chunks/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/_common.sh
source "${SCRIPT_DIR}/_common.sh"

build_scheme_args

phase_banner "P1.3 CHUNK" "START"
ingest_python src.ingest.chunk
phase_banner "P1.3 CHUNK" "END"
