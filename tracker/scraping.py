"""Job-posting scraping via Playwright (headless Chromium).

STUB — not yet implemented. See dev/25_06_minimal_req.md (Scraping). Target: sync
Playwright launch, detect_board(url) -> per-board extractor for title/company/location/
description with a <meta>/JSON-LD JobPosting fallback; store raw_html for re-extraction.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrapedJob:
    title: str
    company: str
    location: str
    description: str
    raw_html: str
    source_board: str


def detect_board(url: str) -> str:
    raise NotImplementedError(
        "detect_board() is not yet implemented — see dev/25_06_minimal_req.md"
    )


def scrape(url: str) -> ScrapedJob:
    raise NotImplementedError(
        "scrape() is not yet implemented — see dev/25_06_minimal_req.md"
    )
