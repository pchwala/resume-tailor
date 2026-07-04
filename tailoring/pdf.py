"""Render a resume to PDF bytes via headless Chromium.

The template (`tracker/pdf_template.html`) is self-contained — CSS, the Inter font
(base64), and contact icons are all inlined — so `page.set_content()` needs no network.
Reuses the same sync-Playwright plumbing as `tracker/scraping.py`.

`master_content()` projects the master `Profile` into the tailored-resume JSON contract
`{about, experiences[], skills[], projects[]}`. It renders the *untailored* master now and
is reused later as the AI tailorer's subset-guard fallback. See dev/25_06_minimal_req.md.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from django.template.loader import render_to_string

_FONT_DIR = Path(__file__).resolve().parent.parent / "tracker" / "static" / "resume" / "fonts"
_DEFAULT_TEMPLATE = "tracker/pdf_template.html"

# Auto-shrink-to-fit: scale the rendered page down just enough to keep it within _MAX_PAGES.
_A4_PAGE_PX = 1122.5     # A4 height (297mm) in CSS px at 96dpi; margins are 0 so this is the full sheet
_MAX_PAGES = 2
_SAFETY = 0.97           # absorb whitespace left by `page-break-inside: avoid`
_MIN_SCALE = 0.75        # legibility floor (~12px); below this we allow a spill rather than shrink further


def _scale_for_height(measured_height: float) -> float:
    """Scale factor to fit `measured_height` (CSS px) into _MAX_PAGES, clamped to [_MIN_SCALE, 1.0].

    Never upscales (short resumes render at 1.0); floors at _MIN_SCALE so very long resumes
    spill to another page rather than become unreadable.
    """
    if measured_height <= 0:
        return 1.0
    budget = _A4_PAGE_PX * _MAX_PAGES * _SAFETY
    return max(_MIN_SCALE, min(1.0, budget / measured_height))


def master_content(profile) -> dict:
    """Project the master Profile into the tailored-resume JSON shape (untailored)."""
    return {
        "about": profile.about,
        "experiences": [
            {"company": exp.company, "period": exp.period, "desc": exp.description}
            for exp in profile.experiences.all()
        ],
        "skills": [
            {"category": cat.name, "items": [s.name for s in cat.skills.all()]}
            for cat in profile.skill_categories.all()
        ],
        "projects": [
            {"name": proj.name, "tech": proj.tech, "desc": proj.description}
            for proj in profile.projects.all()
        ],
    }


@lru_cache(maxsize=1)
def _load_fonts() -> dict:
    """Base64-encode the bundled Inter variable-font woff2 subsets for @font-face inlining."""

    def b64(name: str) -> str:
        return base64.b64encode((_FONT_DIR / name).read_bytes()).decode("ascii")

    return {"latin": b64("Inter-latin.woff2"), "latin_ext": b64("Inter-latin-ext.woff2")}


def _render_html(profile, content: dict, template_name: str = _DEFAULT_TEMPLATE) -> str:
    return render_to_string(
        template_name,
        {"profile": profile, "tailored": content, "fonts": _load_fonts()},
    )


def _html_to_pdf(html: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            # Measure under print media (the template's print padding differs) and shrink to fit.
            page.emulate_media(media="print")
            scale = _scale_for_height(page.evaluate("document.documentElement.scrollHeight"))
            return page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                scale=scale,
            )
        finally:
            browser.close()


def render_master_pdf(profile) -> bytes:
    """Render the untailored master resume to PDF bytes (no TailoredResume needed)."""
    return _html_to_pdf(_render_html(profile, master_content(profile)))


def render_pdf(tailored_resume) -> bytes:
    """Render a persisted TailoredResume to PDF bytes."""
    from profiles.models import Profile

    profile = Profile.objects.first()
    if profile is None:
        raise RuntimeError("No Profile found — run `python manage.py seed_resume` first.")

    template = tailored_resume.template
    template_name = template.pdf_template_name if template else _DEFAULT_TEMPLATE
    html = _render_html(profile, tailored_resume.content, template_name)
    return _html_to_pdf(html)
