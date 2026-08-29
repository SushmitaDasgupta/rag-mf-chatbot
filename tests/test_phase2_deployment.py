"""Phase 2 deployment config (Vercel frontend — docs/deployment.md)."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = REPO_ROOT / "ui"


def test_phase2_vercel_json() -> None:
    path = UI_DIR / "vercel.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["framework"] == "vite"
    assert data["buildCommand"] == "npm run build"
    assert data["outputDirectory"] == "dist"
    assert data["installCommand"] == "npm install"
    rewrites = data["rewrites"]
    assert any(r.get("destination") == "/index.html" for r in rewrites)


def test_phase2_env_examples() -> None:
    ui_env = (UI_DIR / ".env.example").read_text(encoding="utf-8")
    vercel_env = (REPO_ROOT / "vercel.env.example").read_text(encoding="utf-8")
    assert "VITE_API_BASE_URL" in ui_env
    assert "VITE_API_BASE_URL" in vercel_env
    assert "railway" in vercel_env.lower()


def test_phase2_api_client_uses_vite_env() -> None:
    text = (UI_DIR / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    assert "import.meta.env.VITE_API_BASE_URL" in text
    assert "/api/chat" in text


def test_phase2_build_script_exists() -> None:
    path = REPO_ROOT / "scripts" / "build_ui_production.sh"
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    text = path.read_text(encoding="utf-8")
    assert "VITE_API_BASE_URL" in text
    assert "npm run build" in text


def test_phase2_verify_script_exists() -> None:
    path = REPO_ROOT / "scripts" / "verify_phase2_frontend.sh"
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    text = path.read_text(encoding="utf-8")
    assert 'id="root"' in text


def test_phase2_package_build_script() -> None:
    pkg = json.loads((UI_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["scripts"]["build"] == "tsc -b && vite build"
