"""Deterministic dedup signature for grouping the same role across boards.

STUB — not yet implemented. See dev/25_06_minimal_req.md (Signature / dedup).
Target: normalize each field (lowercase, strip punctuation/whitespace, drop suffixes like
"Inc"/"Ltd", collapse seniority synonyms), then sha256("company|title|location") -> hex.
"""
from __future__ import annotations


def signature(company: str, title: str, location: str = "") -> str:
    raise NotImplementedError(
        "signature() is not yet implemented — see dev/25_06_minimal_req.md"
    )
