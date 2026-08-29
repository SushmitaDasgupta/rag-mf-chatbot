#!/usr/bin/env bash
# Idempotent corpus commit for GitHub Actions daily-ingest workflow.
# Always resets to latest origin/main, reapplies ingest patch, then pushes with retry.
set -euo pipefail

CORPUS_COMMIT_SCRIPT_VERSION=3
echo "=== commit_corpus_refresh.sh v${CORPUS_COMMIT_SCRIPT_VERSION} | $(date -u -Iseconds) ==="

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

COMMIT_MSG="chore(ingest): daily corpus refresh $(date -u +%Y-%m-%d)"
PATCH_FILE="$(mktemp)"

cleanup() {
  rm -f "$PATCH_FILE"
}
trap cleanup EXIT

# Snapshot ingest artifacts as a patch (survives branch resets).
git add data/raw data/processed data/vectorstore
if git diff --staged --quiet; then
  echo "No corpus changes to commit."
  exit 0
fi
git diff --staged > "$PATCH_FILE"
echo "Captured corpus patch ($(wc -c < "$PATCH_FILE") bytes)."

reset_to_origin_main() {
  git fetch origin main
  git checkout -B main origin/main
}

apply_corpus_patch() {
  # Clean data paths so apply is repeatable on each attempt.
  git checkout HEAD -- data/raw data/processed data/vectorstore 2>/dev/null || true
  if git apply --3way "$PATCH_FILE"; then
    :
  elif git apply "$PATCH_FILE"; then
    :
  else
    return 1
  fi
  git add data/raw data/processed data/vectorstore
  return 0
}

commit_if_staged() {
  if git diff --staged --quiet; then
    return 1
  fi
  git commit -m "$COMMIT_MSG"
  return 0
}

for attempt in $(seq 1 15); do
  echo "--- Corpus push attempt ${attempt}/15 ---"
  reset_to_origin_main

  if ! apply_corpus_patch; then
    echo "WARN: Could not apply corpus patch on attempt ${attempt}."
    if ! git diff --quiet -- data/raw data/processed data/vectorstore; then
      echo "ERROR: Unresolved data diff after failed patch apply."
      exit 1
    fi
    echo "Remote tree already matches ingest output — idempotent success."
    exit 0
  fi

  if ! commit_if_staged; then
    echo "No staged diff after patch — idempotent success."
    exit 0
  fi

  if git push origin main; then
    echo "Corpus push succeeded on attempt ${attempt}."
    exit 0
  fi

  echo "Push rejected (remote advanced); retrying after sleep..."
  sleep $((attempt * 2))
done

echo "ERROR: Corpus push failed after 15 attempts."
exit 1
