"""Deterministic dedup signature for grouping the same role across boards.

See dev/25_06_minimal_req.md (Signature / dedup). Normalizes each field (lowercase,
strip punctuation/whitespace, drop common company suffixes like "Inc"/"Ltd", collapse
seniority synonyms in the title), then sha256("company|title|location") -> hex.
"""
from __future__ import annotations

import hashlib
import re

_COMPANY_SUFFIXES = [
    "sp z o o",
    "s a",
    "gmbh",
    "inc",
    "ltd",
    "llc",
    "llp",
    "co",
    "corp",
    "corporation",
    "company",
    "limited",
    "plc",
]

_SENIORITY_SYNONYMS = {
    "sr": "senior",
    "jr": "junior",
}


def _clean(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_company_suffix(cleaned: str) -> str:
    words = cleaned.split()
    changed = True
    while changed:
        changed = False
        for suffix in _COMPANY_SUFFIXES:
            suffix_words = suffix.split()
            n = len(suffix_words)
            if n and words[-n:] == suffix_words:
                words = words[:-n]
                changed = True
    return " ".join(words).strip()


def _normalize_title(text: str) -> str:
    cleaned = _clean(text)
    words = [_SENIORITY_SYNONYMS.get(word, word) for word in cleaned.split()]
    return " ".join(words)


def signature(company: str, title: str, location: str = "") -> str:
    norm_company = _strip_company_suffix(_clean(company))
    norm_title = _normalize_title(title)
    norm_location = _clean(location)
    raw = f"{norm_company}|{norm_title}|{norm_location}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
