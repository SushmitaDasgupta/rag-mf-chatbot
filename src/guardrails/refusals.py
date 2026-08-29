"""P3.3 — On-policy refusal templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.rag.validate import DISCLAIMER

RefusalKind = Literal["pii", "advisory", "performance"]


@dataclass
class RefusalPayload:
    kind: RefusalKind
    text: str
    disclaimer: str = DISCLAIMER


def pii_refusal() -> RefusalPayload:
    return RefusalPayload(
        kind="pii",
        text=(
            "I cannot process messages that contain personal or sensitive identifiers "
            "(such as PAN, Aadhaar, account numbers, OTPs, email, or phone). "
            "Please remove that information and ask your factual scheme question again."
        ),
    )


def advisory_refusal() -> RefusalPayload:
    return RefusalPayload(
        kind="advisory",
        text=(
            "I can only answer objective, source-backed facts about supported Kotak schemes. "
            "I cannot provide investment advice, recommendations, or fund comparisons."
        ),
    )


def performance_refusal() -> RefusalPayload:
    return RefusalPayload(
        kind="performance",
        text=(
            "I cannot provide past performance figures, return calculations, or return comparisons. "
            "Please refer to the scheme reference page for official disclosures."
        ),
    )


def unsupported_scheme_message(*, scheme_lines: list[str] | None = None) -> str:
    if scheme_lines:
        listing = "\n".join(f"- {name}" for name in scheme_lines)
    else:
        from src.config import get_settings
        from src.ingest.fetch import load_manifest_schemes

        schemes = load_manifest_schemes(get_settings().manifest_path)
        listing = "\n".join(f"- {s['display_name']}" for s in schemes)

    return (
        "I can only answer factual questions about these Kotak schemes from the locked corpus:\n"
        f"{listing}"
    )
