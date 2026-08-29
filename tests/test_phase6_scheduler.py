"""Phase 6 checks: daily ingest GitHub Actions workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "daily-ingest.yml"


def test_daily_ingest_workflow_exists() -> None:
    assert WORKFLOW_PATH.is_file(), f"Missing workflow: {WORKFLOW_PATH}"


def test_daily_ingest_workflow_schedule_10am_ist() -> None:
    """10:00 AM IST = 04:30 UTC."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'cron: "30 4 * * *"' in text or "cron: '30 4 * * *'" in text


def test_daily_ingest_workflow_has_manual_dispatch_and_concurrency() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "scheme_id:" in text
    data = yaml.safe_load(text)
    assert data["concurrency"]["group"] == "daily-ingest"
    assert data["concurrency"]["cancel-in-progress"] is False


INGEST_DIR = REPO_ROOT / "scripts" / "ingest"
INGEST_PHASE_SCRIPTS = (
    "run_fetch.sh",
    "run_parse.sh",
    "run_chunk.sh",
    "run_index.sh",
    "run_probes.sh",
)


def test_daily_ingest_workflow_runs_full_pipeline() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    for script in INGEST_PHASE_SCRIPTS:
        assert f"scripts/ingest/{script}" in text
    assert "--fetch-fallback-cached" in (INGEST_DIR / "run_fetch.sh").read_text(encoding="utf-8")
    assert "--skip-probes" in (INGEST_DIR / "run_index.sh").read_text(encoding="utf-8")
    assert "GROQ_API_KEY" not in text


def test_ingest_phase_scripts_exist_and_are_executable() -> None:
    for script in INGEST_PHASE_SCRIPTS:
        path = INGEST_DIR / script
        assert path.is_file(), f"Missing ingest script: {path}"
        assert path.stat().st_mode & 0o111, f"Script not executable: {path}"
    assert (INGEST_DIR / "_common.sh").is_file()


def test_daily_ingest_workflow_rebases_before_push() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "scripts/commit_corpus_refresh.sh" in text
    script = (REPO_ROOT / "scripts" / "commit_corpus_refresh.sh").read_text(encoding="utf-8")
    assert "CORPUS_COMMIT_SCRIPT_VERSION=3" in script
    assert "Corpus push attempt" in script


def test_vectorstore_not_gitignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/vectorstore/" not in gitignore.splitlines()
