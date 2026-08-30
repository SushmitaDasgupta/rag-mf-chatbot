"""Application settings loaded from environment / `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    # Groq openai/gpt-oss-120b free-tier limits (local guard; override in .env if tier changes)
    groq_rpm_limit: int = 30
    groq_rpd_limit: int = 1000
    groq_tpm_limit: int = 8000
    groq_tpd_limit: int = 200_000

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    vector_store_path: str = "data/vectorstore"
    chroma_collection: str = "mutual_fund_chunks"

    manifest_path: str = "data/manifest.yaml"
    parsed_dir: str = "data/processed/parsed"
    chunks_dir: str = "data/processed/chunks"
    structured_facts_path: str = "data/processed/structured_facts.yaml"
    raw_dir: str = "data/raw"
    fetch_log_path: str = "data/raw/fetch_log.yaml"
    fetch_timeout_seconds: float = 30.0

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://127.0.0.1:8000"
    ui_min_seconds_between_requests: float = 2.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    fetch_fallback_cached: bool = False
    fetch_fail_on_cached_fallback: bool = False
    fetch_retry_count: int = 3
    fetch_inter_scheme_delay_seconds: float = 1.0

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
