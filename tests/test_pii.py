"""P3.1 — PII gate unit tests (synthetic patterns only)."""

from __future__ import annotations

from src.guardrails.pii import check_pii


def test_detects_synthetic_pan() -> None:
    result = check_pii("My PAN is ABCDE1234F. What is the exit load?")
    assert result.detected
    assert "pan" in result.kinds


def test_detects_synthetic_email() -> None:
    result = check_pii("Contact investor@example.com about Kotak Liquid Fund fees.")
    assert result.detected
    assert "email" in result.kinds


def test_detects_folio_number() -> None:
    result = check_pii("Folio number 987654321098 for Kotak Gold Fund query.")
    assert result.detected
    assert "account" in result.kinds


def test_detects_otp() -> None:
    result = check_pii("OTP is 483920 for login. What is the benchmark?")
    assert result.detected
    assert "otp" in result.kinds


def test_detects_phone_with_context() -> None:
    result = check_pii("Call me at +91 9876543210 about Kotak Midcap Fund.")
    assert result.detected
    assert "phone" in result.kinds


def test_plain_factual_query_is_clean() -> None:
    result = check_pii("What is the expense ratio of Kotak Large Cap Fund?")
    assert not result.detected
    assert result.kinds == []


def test_random_ten_digits_without_context_not_pii() -> None:
    result = check_pii("The scheme code 1234567890 is mentioned in docs.")
    assert not result.detected
