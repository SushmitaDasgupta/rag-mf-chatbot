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


def test_daily_ingest_workflow_runs_full_pipeline() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "python -u -m src.ingest.run" in text
    assert "--fetch-fallback-cached" in text
    assert "python -u scripts/retrieval_probe.py" in text
    assert "GROQ_API_KEY" not in text


def test_daily_ingest_workflow_rebases_before_push() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "sync_to_origin_main" in text
    assert "push_with_retry" in text
    assert "git push origin main" in text


def test_vectorstore_not_gitignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/vectorstore/" not in gitignore.splitlines()
