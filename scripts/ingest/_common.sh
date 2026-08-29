#!/usr/bin/env bash
# Shared helpers for ingest phase scripts (GitHub Actions and local runs).

phase_banner() {
  local phase="$1"
  local action="$2"
  local sha
  sha="$(git rev-parse --short HEAD 2>/dev/null || echo local)"
  echo "=== ${phase} ${action} | sha=${sha} | $(date -u -Iseconds) ==="
}

# Prints --scheme-id <id> when INGEST_SCHEME_ID is set (workflow_dispatch input).
ingest_scheme_cli_args() {
  if [ -n "${INGEST_SCHEME_ID:-}" ]; then
    printf '%s\n' --scheme-id "$INGEST_SCHEME_ID"
  fi
}

# Populates INGEST_SCHEME_ARGS for bash 3.2+ (macOS) and GitHub Actions runners.
build_scheme_args() {
  INGEST_SCHEME_ARGS=()
  if [ -n "${INGEST_SCHEME_ID:-}" ]; then
    INGEST_SCHEME_ARGS=(--scheme-id "$INGEST_SCHEME_ID")
  fi
}
