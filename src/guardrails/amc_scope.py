"""Detect queries about AMCs outside the locked Kotak corpus."""

from __future__ import annotations

import re

OUT_OF_CORPUS_AMC_MARKERS = (
    "hdfc",
    "icici",
    "sbi fund",
    "sbi mutual",
    "axis fund",
    "axis mutual",
    "nippon",
    "uti fund",
    "dsp fund",
    "mirae",
    "parag parikh",
    "ppfas",
    "franklin",
    "invesco",
    "aditya birla",
    "birla sun",
    "tata mutual",
    "idfc",
    "bandhan",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def is_out_of_corpus_amc(query: str) -> bool:
    """True when the query names another AMC and is not clearly about Kotak."""
    norm = _normalize(query)
    if "kotak" in norm:
        return False
    return any(marker in norm for marker in OUT_OF_CORPUS_AMC_MARKERS)
