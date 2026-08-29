"""Tests for shared logging configuration."""

from __future__ import annotations

import logging

from src.logging_config import get_logger, setup_logging


def test_setup_logging_is_idempotent() -> None:
    setup_logging("INFO")
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.INFO


def test_noisy_loggers_are_quiet() -> None:
    setup_logging("INFO")
    assert logging.getLogger("sentence_transformers").level >= logging.WARNING


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("src.ingest.run")
    assert logger.name == "src.ingest.run"
