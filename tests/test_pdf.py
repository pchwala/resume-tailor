import shutil
from pathlib import Path

import pytest
from django.template.loader import render_to_string

from tailoring.pdf import _load_fonts, master_content, render_master_pdf


def _build_profile():
    from profiles.models import Experience, Profile, Project, Skill, SkillCategory

    profile = Profile.objects.create(
        name="Przemysław Chwała",
        subtitle="Software Developer & Problem Solver",
        location="Warsaw, Poland",
        website_url="https://pchwala.dev/",
        github_url="https://github.com/pchwala",
        email="info@pchwala.dev",
        linkedin_url="https://linkedin.com/in/przemyslaw-chwala",
        about="Master about paragraph.",
        gdpr_text="I agree to the processing of personal data.",
    )
    exp = Experience.objects.create(
        profile=profile, company="ZM Holding Sp. z o.o.", period="2022 — Present",
        description="Master experience prose.", order=0,
    )
    cat = SkillCategory.objects.create(profile=profile, name="Frameworks", order=0)
    Skill.objects.create(category=cat, name="FastAPI", order=0)
    Skill.objects.create(category=cat, name="React", order=1)
    Project.objects.create(
        profile=profile, name="QuizMinds", tech=["React 19", "FastAPI"],
        description="Master project prose.", order=0,
    )
    return profile, exp


@pytest.mark.django_db
def test_master_content_shape():
    profile, _ = _build_profile()
    content = master_content(profile)

    assert content["about"] == "Master about paragraph."
    assert content["experiences"] == [
        {"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present",
         "desc": "Master experience prose."}
    ]
    assert content["skills"] == [{"category": "Frameworks", "items": ["FastAPI", "React"]}]
    assert content["projects"] == [
        {"name": "QuizMinds", "tech": ["React 19", "FastAPI"], "desc": "Master project prose."}
    ]


@pytest.mark.django_db
def test_pdf_template_renders_master_self_contained():
    profile, _ = _build_profile()
    html = render_to_string(
        "tracker/pdf_template.html",
        {"profile": profile, "tailored": master_content(profile), "fonts": _load_fonts()},
    )

    # content present
    assert "Przemysław Chwała" in html
    assert "ZM Holding Sp. z o.o." in html
    assert "FastAPI" in html  # a chip
    assert "I agree to the processing of personal data." in html
    # self-contained: fonts embedded, no external http font/stylesheet/icon refs
    assert "@font-face" in html
    assert "data:font/woff2;base64," in html
    assert "https://fonts.googleapis.com" not in html
    assert 'href="resume.css"' not in html


@pytest.mark.django_db
def test_pdf_template_renders_tailored_content():
    """Design lives in the template; swapping the data swaps the output."""
    profile, _ = _build_profile()
    tailored = {
        "about": "TAILORED summary for this role.",
        "experiences": [{"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present",
                         "desc": "TAILORED experience desc."}],
        "skills": [{"category": "Frameworks", "items": ["React", "FastAPI"]}],  # reordered
        "projects": [{"name": "QuizMinds", "tech": ["FastAPI"], "desc": "TAILORED project."}],
    }
    html = render_to_string(
        "tracker/pdf_template.html",
        {"profile": profile, "tailored": tailored, "fonts": _load_fonts()},
    )
    assert "TAILORED summary for this role." in html
    assert "TAILORED experience desc." in html
    assert "TAILORED project." in html


def _chromium_available() -> bool:
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:
        return False


@pytest.mark.django_db
@pytest.mark.skipif(not _chromium_available(), reason="Chromium not installed")
def test_render_master_pdf_produces_pdf():
    profile, _ = _build_profile()
    pdf = render_master_pdf(profile)
    assert isinstance(pdf, (bytes, bytearray))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000  # a real, non-trivial document
