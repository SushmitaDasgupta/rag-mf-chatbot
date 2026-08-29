"""Groq rate limiter unit tests."""

from __future__ import annotations

import pytest

from src.guardrails.groq_limits import (
    GroqLimitConfig,
    GroqRateLimiter,
    estimate_tokens_for_messages,
    reset_groq_rate_limiter_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_groq_rate_limiter_for_tests()
    yield
    reset_groq_rate_limiter_for_tests()


def test_estimate_tokens_for_messages() -> None:
    messages = [{"role": "user", "content": "a" * 400}]
    assert estimate_tokens_for_messages(messages, max_output_tokens=256) >= 356


def test_acquire_within_limits() -> None:
    limiter = GroqRateLimiter(GroqLimitConfig(), model="openai/gpt-oss-120b")
    limiter.acquire(100)
    snap = limiter.snapshot()
    assert snap.requests_last_minute == 1
    assert snap.tokens_last_minute == 100


def test_blocks_when_minute_requests_exceeded() -> None:
    limiter = GroqRateLimiter(
        GroqLimitConfig(requests_per_minute=2, tokens_per_minute=100_000),
        model="openai/gpt-oss-120b",
    )
    limiter.acquire(10)
    limiter.acquire(10)
    with pytest.raises(Exception, match="requests/minute"):
        limiter.acquire(10)


def test_blocks_when_minute_tokens_exceeded() -> None:
    limiter = GroqRateLimiter(
        GroqLimitConfig(requests_per_minute=100, tokens_per_minute=100),
        model="openai/gpt-oss-120b",
    )
    with pytest.raises(Exception, match="tokens/minute"):
        limiter.acquire(150)
