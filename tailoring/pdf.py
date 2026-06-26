"""Render a TailoredResume to PDF bytes via headless Chromium.

STUB — not yet implemented. See dev/25_06_minimal_req.md (PDF export).

Target: render the resume template (Profile fixed header/footer + tailored JSON loops) to a
self-contained HTML string, then page.set_content(html) + page.pdf(format="A4",
print_background=True) using the same sync_playwright plumbing as tracker/scraping.py.
"""
from __future__ import annotations


def render_pdf(tailored_resume) -> bytes:
    raise NotImplementedError(
        "render_pdf() is not yet implemented — see dev/25_06_minimal_req.md"
    )
