"""P3.1 — Detect sensitive identifiers before retrieval or Groq."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

PiiKind = Literal["pan", "aadhaar", "account", "otp", "email", "phone"]

# Synthetic test fixtures only — do not log matched substrings in production paths.
PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_EXPLICIT = re.compile(
    r"aadhaar(?:\s*(?:no|number|card|#))?[\s:]*\d{4}[\s-]?\d{4}[\s-]?\d{4}",
    re.IGNORECASE,
)
AADHAAR_GROUPED = re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b")
ACCOUNT_PATTERN = re.compile(
    r"(?:account|folio|acct)(?:\s*(?:no|number|#))?[\s:]*(?:is\s*)?\d{6,18}",
    re.IGNORECASE,
)
OTP_PATTERN = re.compile(
    r"(?:otp|one[\s-]?time[\s-]?password)[\s:]*(?:is\s*)?\d{4,8}",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
PHONE_EXPLICIT = re.compile(
    r"(?:phone|mobile|contact)(?:\s*(?:no|number|#))?[\s:]*(?:\+91[\s-]?)?[6-9]\d{9}",
    re.IGNORECASE,
)
PHONE_E164 = re.compile(r"(?:\+91[\s-]?)[6-9]\d{9}\b")
PHONE_STANDALONE = re.compile(r"\b[6-9]\d{9}\b")


@dataclass
class PiiCheckResult:
    detected: bool
    kinds: list[PiiKind] = field(default_factory=list)


def _add_kind(result: PiiCheckResult, kind: PiiKind) -> None:
    if kind not in result.kinds:
        result.kinds.append(kind)
    result.detected = True


def check_pii(message: str) -> PiiCheckResult:
    """Return whether the message contains sensitive identifier patterns."""
    result = PiiCheckResult(detected=False)
    if not message or not message.strip():
        return result

    text = message.strip()

    if PAN_PATTERN.search(text):
        _add_kind(result, "pan")

    if AADHAAR_EXPLICIT.search(text) or (
        "aadhaar" in text.lower() and AADHAAR_GROUPED.search(text)
    ):
        _add_kind(result, "aadhaar")

    if ACCOUNT_PATTERN.search(text):
        _add_kind(result, "account")

    if OTP_PATTERN.search(text):
        _add_kind(result, "otp")

    if EMAIL_PATTERN.search(text):
        _add_kind(result, "email")

    if (
        PHONE_EXPLICIT.search(text)
        or PHONE_E164.search(text)
        or (
            PHONE_STANDALONE.search(text)
            and any(w in text.lower() for w in ("call me", "my number", "reach me at"))
        )
    ):
        _add_kind(result, "phone")

    return result
