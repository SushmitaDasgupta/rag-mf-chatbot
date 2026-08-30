#!/usr/bin/env bash
# P1.4 — Embed chunks and upsert into Chroma (probes run in a separate step).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/_common.sh
source "${SCRIPT_DIR}/_common.sh"

build_scheme_args

phase_banner "P1.4 INDEX" "START"
ingest_python src.ingest.index --skip-probes
phase_banner "P1.4 INDEX" "END"
