"""Groq LLM rate limiting for openai/gpt-oss-120b (local sliding-window guard)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.config import get_settings


@dataclass(frozen=True)
class GroqLimitConfig:
    requests_per_minute: int = 30
    requests_per_day: int = 1000
    tokens_per_minute: int = 8000
    tokens_per_day: int = 200_000


@dataclass(frozen=True)
class GroqLimitSnapshot:
    model: str
    requests_last_minute: int
    requests_last_day: int
    tokens_last_minute: int
    tokens_last_day: int
    requests_per_minute_limit: int
    requests_per_day_limit: int
    tokens_per_minute_limit: int
    tokens_per_day_limit: int

    @property
    def requests_minute_remaining(self) -> int:
        return max(0, self.requests_per_minute_limit - self.requests_last_minute)

    @property
    def requests_day_remaining(self) -> int:
        return max(0, self.requests_per_day_limit - self.requests_last_day)

    @property
    def tokens_minute_remaining(self) -> int:
        return max(0, self.tokens_per_minute_limit - self.tokens_last_minute)

    @property
    def tokens_day_remaining(self) -> int:
        return max(0, self.tokens_per_day_limit - self.tokens_last_day)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "usage": {
                "requests_last_minute": self.requests_last_minute,
                "requests_last_day": self.requests_last_day,
                "tokens_last_minute": self.tokens_last_minute,
                "tokens_last_day": self.tokens_last_day,
            },
            "limits": {
                "requests_per_minute": self.requests_per_minute_limit,
                "requests_per_day": self.requests_per_day_limit,
                "tokens_per_minute": self.tokens_per_minute_limit,
                "tokens_per_day": self.tokens_per_day_limit,
            },
            "remaining": {
                "requests_minute": self.requests_minute_remaining,
                "requests_day": self.requests_day_remaining,
                "tokens_minute": self.tokens_minute_remaining,
                "tokens_day": self.tokens_day_remaining,
            },
        }


class GroqRateLimitError(Exception):
    """Raised when a Groq call would exceed configured local rate limits."""

    def __init__(self, message: str, *, retry_after_seconds: float, snapshot: GroqLimitSnapshot):
        super().__init__(message)
        self.retry_after_seconds = max(1.0, retry_after_seconds)
        self.snapshot = snapshot


def estimate_tokens_for_messages(messages: list[dict[str, str]], *, max_output_tokens: int = 256) -> int:
    """Rough pre-flight token estimate (chars/4 heuristic + reserved completion budget)."""
    text = "\n".join(str(m.get("content", "")) for m in messages)
    return max(1, len(text) // 4) + max_output_tokens


class GroqRateLimiter:
    """In-process sliding-window limiter (MVP single-instance demo guard)."""

    def __init__(self, config: GroqLimitConfig, *, model: str) -> None:
        self._config = config
        self._model = model
        self._lock = threading.Lock()
        self._minute_requests: deque[float] = deque()
        self._day_requests: deque[float] = deque()
        self._minute_tokens: deque[tuple[float, int]] = deque()
        self._day_tokens: deque[tuple[float, int]] = deque()
        self._last_reserved_tokens: int = 0

    def snapshot(self) -> GroqLimitSnapshot:
        with self._lock:
            now = time.time()
            self._prune(now)
            return self._build_snapshot()

    def acquire(self, estimated_tokens: int) -> None:
        with self._lock:
            now = time.time()
            self._prune(now)
            snap = self._build_snapshot()

            if snap.requests_last_minute >= self._config.requests_per_minute:
                retry = 60.0 - (now - self._minute_requests[0]) if self._minute_requests else 60.0
                raise GroqRateLimitError(
                    "Groq request limit reached (30 requests/minute). Please wait and try again.",
                    retry_after_seconds=retry,
                    snapshot=snap,
                )

            if snap.requests_last_day >= self._config.requests_per_day:
                retry = 86_400.0 - (now - self._day_requests[0]) if self._day_requests else 86_400.0
                raise GroqRateLimitError(
                    "Groq daily request limit reached (1,000 requests/day). Please try again later.",
                    retry_after_seconds=retry,
                    snapshot=snap,
                )

            minute_tokens = snap.tokens_last_minute + estimated_tokens
            if minute_tokens > self._config.tokens_per_minute:
                retry = 60.0 - (now - self._minute_tokens[0][0]) if self._minute_tokens else 60.0
                raise GroqRateLimitError(
                    "Groq token limit reached (8,000 tokens/minute). Please wait and try again.",
                    retry_after_seconds=retry,
                    snapshot=snap,
                )

            day_tokens = snap.tokens_last_day + estimated_tokens
            if day_tokens > self._config.tokens_per_day:
                retry = 86_400.0 - (now - self._day_tokens[0][0]) if self._day_tokens else 86_400.0
                raise GroqRateLimitError(
                    "Groq daily token limit reached (200,000 tokens/day). Please try again later.",
                    retry_after_seconds=retry,
                    snapshot=snap,
                )

            self._minute_requests.append(now)
            self._day_requests.append(now)
            self._minute_tokens.append((now, estimated_tokens))
            self._day_tokens.append((now, estimated_tokens))
            self._last_reserved_tokens = estimated_tokens

    def reconcile_usage(self, actual_tokens: int) -> None:
        """Adjust the last reservation when Groq returns actual usage."""
        if actual_tokens <= 0:
            return
        with self._lock:
            delta = actual_tokens - self._last_reserved_tokens
            if delta == 0:
                return
            now = time.time()
            if self._minute_tokens:
                ts, amount = self._minute_tokens.pop()
                self._minute_tokens.append((ts, max(0, amount + delta)))
            else:
                self._minute_tokens.append((now, actual_tokens))
            if self._day_tokens:
                ts, amount = self._day_tokens.pop()
                self._day_tokens.append((ts, max(0, amount + delta)))
            else:
                self._day_tokens.append((now, actual_tokens))
            self._last_reserved_tokens = actual_tokens

    def _prune(self, now: float) -> None:
        minute_cutoff = now - 60.0
        day_cutoff = now - 86_400.0

        while self._minute_requests and self._minute_requests[0] < minute_cutoff:
            self._minute_requests.popleft()
        while self._day_requests and self._day_requests[0] < day_cutoff:
            self._day_requests.popleft()
        while self._minute_tokens and self._minute_tokens[0][0] < minute_cutoff:
            self._minute_tokens.popleft()
        while self._day_tokens and self._day_tokens[0][0] < day_cutoff:
            self._day_tokens.popleft()

    def _build_snapshot(self) -> GroqLimitSnapshot:
        return GroqLimitSnapshot(
            model=self._model,
            requests_last_minute=len(self._minute_requests),
            requests_last_day=len(self._day_requests),
            tokens_last_minute=sum(amount for _, amount in self._minute_tokens),
            tokens_last_day=sum(amount for _, amount in self._day_tokens),
            requests_per_minute_limit=self._config.requests_per_minute,
            requests_per_day_limit=self._config.requests_per_day,
            tokens_per_minute_limit=self._config.tokens_per_minute,
            tokens_per_day_limit=self._config.tokens_per_day,
        )


@lru_cache(maxsize=1)
def get_groq_rate_limiter() -> GroqRateLimiter:
    settings = get_settings()
    config = GroqLimitConfig(
        requests_per_minute=settings.groq_rpm_limit,
        requests_per_day=settings.groq_rpd_limit,
        tokens_per_minute=settings.groq_tpm_limit,
        tokens_per_day=settings.groq_tpd_limit,
    )
    return GroqRateLimiter(config, model=settings.groq_model)


def reset_groq_rate_limiter_for_tests() -> None:
    get_groq_rate_limiter.cache_clear()
