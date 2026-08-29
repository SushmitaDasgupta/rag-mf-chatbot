"""Phase 1 deployment config (Railway backend — docs/deployment.md)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAILWAY_TOML = REPO_ROOT / "railway.toml"


def test_phase1_procfile_exists() -> None:
    text = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
    assert "scripts/start_api.sh" in text


def test_phase1_start_api_script() -> None:
    path = REPO_ROOT / "scripts" / "start_api.sh"
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    text = path.read_text(encoding="utf-8")
    assert "uvicorn src.api.main:app" in text
    assert 'PORT="${PORT:-8000}"' in text


def test_phase1_railway_toml() -> None:
    text = RAILWAY_TOML.read_text(encoding="utf-8")
    assert 'startCommand = "bash scripts/start_api.sh"' in text
    assert 'healthcheckPath = "/api/health"' in text
    assert "healthcheckTimeout = 300" in text
    assert 'NIXPACKS_PYTHON_VERSION = "3.11"' in text


def test_phase1_verify_script_exists() -> None:
    path = REPO_ROOT / "scripts" / "verify_phase1_backend.sh"
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    text = path.read_text(encoding="utf-8")
    assert "/api/health" in text
    assert "groq_configured" in text


def test_phase1_python_version() -> None:
    assert (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11"


def test_phase1_railway_env_example_documents_secrets() -> None:
    text = (REPO_ROOT / "railway.env.example").read_text(encoding="utf-8")
    assert "GROQ_API_KEY" in text
    assert "CORS_ORIGINS" in text
