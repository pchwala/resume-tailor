import types

import pytest
from openai import OpenAIError

from tailoring import ai
from tailoring.ai import (
    TailoredResumeSchema,
    TailoringError,
    _guard_violation,
    _subset_guard,
    tailor,
)
from tailoring.pdf import master_content


def _build_profile():
    from profiles.models import Experience, Profile, Project, Skill, SkillCategory

    profile = Profile.objects.create(
        name="Przemysław Chwała",
        subtitle="Software Developer & Problem Solver",
        location="Warsaw, Poland",
        about="Master about paragraph.",
        gdpr_text="I agree to the processing of personal data.",
    )
    Experience.objects.create(
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
    return profile


def _build_posting():
    from tracker.models import CanonicalJob, JobPosting

    canonical = CanonicalJob.objects.create(
        signature="sig", company="Acme", title="Backend Developer", location="Warsaw",
    )
    return JobPosting.objects.create(
        canonical_job=canonical, url="https://example.com/job/1",
        description="We need a Python/FastAPI backend developer.",
    )


def _valid_schema(**overrides) -> TailoredResumeSchema:
    """A schema instance faithful to the master (rewritten prose, reordered skills)."""
    data = {
        "about": "TAILORED summary for this role.",
        "experiences": [
            {"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present",
             "desc": "TAILORED experience desc."}
        ],
        "skills": [{"category": "Frameworks", "items": ["React", "FastAPI"]}],  # reordered
        "projects": [{"name": "QuizMinds", "tech": ["FastAPI"], "desc": "TAILORED project."}],
    }
    data.update(overrides)
    return TailoredResumeSchema(**data)


# --- schema ---------------------------------------------------------------------------------

@pytest.mark.django_db
def test_schema_round_trips_master_content():
    profile = _build_profile()
    master = master_content(profile)
    assert TailoredResumeSchema(**master).model_dump() == master


# --- tailor() happy path --------------------------------------------------------------------

@pytest.mark.django_db
def test_tailor_returns_guarded_output_keeping_fixed_facts(monkeypatch):
    profile = _build_profile()
    posting = _build_posting()
    monkeypatch.setattr(ai, "_complete", lambda messages: _valid_schema())

    result = tailor(profile, posting)

    assert result["about"] == "TAILORED summary for this role."
    # fixed facts unchanged vs master
    assert result["experiences"][0]["company"] == "ZM Holding Sp. z o.o."
    assert result["experiences"][0]["period"] == "2022 — Present"
    assert result["projects"][0]["name"] == "QuizMinds"
    assert result["skills"][0]["items"] == ["React", "FastAPI"]  # reorder allowed


# --- subset guard fallback ------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("bad", [
    {"experiences": [{"company": "Invented Corp", "period": "2022 — Present", "desc": "x"}]},
    {"skills": [{"category": "Frameworks", "items": ["FastAPI", "Django"]}]},  # Django invented
    {"projects": [{"name": "Invented Project", "tech": [], "desc": "x"}]},
])
def test_tailor_falls_back_to_master_on_guard_violation(monkeypatch, bad):
    profile = _build_profile()
    posting = _build_posting()
    monkeypatch.setattr(ai, "_complete", lambda messages: _valid_schema(**bad))

    assert tailor(profile, posting) == master_content(profile)


# --- hard errors raise ----------------------------------------------------------------------

@pytest.mark.django_db
def test_tailor_wraps_openai_error_as_tailoring_error(monkeypatch):
    profile = _build_profile()
    posting = _build_posting()

    def boom(messages):
        raise OpenAIError("connection failed")

    monkeypatch.setattr(ai, "_complete", boom)
    with pytest.raises(TailoringError):
        tailor(profile, posting)


@pytest.mark.django_db
def test_complete_raises_on_refusal(monkeypatch):
    """_complete surfaces a model refusal as TailoringError (via the real code path)."""
    profile = _build_profile()
    posting = _build_posting()

    message = types.SimpleNamespace(refusal="I can't help with that.", parsed=None)
    response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(parse=lambda **kwargs: response)
        )
    )
    monkeypatch.setattr(ai, "OpenAI", lambda: fake_client, raising=False)

    with pytest.raises(TailoringError):
        tailor(profile, posting)


# --- guard unit tests (no DB, no network) ---------------------------------------------------

_MASTER = {
    "about": "a",
    "experiences": [{"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present", "desc": "d"}],
    "skills": [{"category": "Frameworks", "items": ["FastAPI", "React"]}],
    "projects": [{"name": "QuizMinds", "tech": ["React 19", "FastAPI"], "desc": "d"}],
}


def test_guard_passes_for_reordered_subset():
    tailored = {
        "about": "rewritten",
        "experiences": [{"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present", "desc": "x"}],
        "skills": [{"category": "Frameworks", "items": ["React"]}],  # dropped FastAPI, allowed
        "projects": [{"name": "QuizMinds", "tech": ["FastAPI"], "desc": "x"}],
    }
    assert _guard_violation(tailored, _MASTER) is None
    assert _subset_guard(tailored, _MASTER) is tailored


@pytest.mark.parametrize("field, bad", [
    ("experiences", [{"company": "X", "period": "2022 — Present", "desc": "d"}]),
    ("experiences", [{"company": "ZM Holding Sp. z o.o.", "period": "1999", "desc": "d"}]),
    ("skills", [{"category": "Unknown", "items": ["FastAPI"]}]),
    ("skills", [{"category": "Frameworks", "items": ["Django"]}]),
    ("projects", [{"name": "Ghost", "tech": [], "desc": "d"}]),
    ("projects", [{"name": "QuizMinds", "tech": ["Rust"], "desc": "d"}]),
])
def test_guard_flags_invented_facts(field, bad):
    tailored = {**_MASTER, field: bad}
    assert _guard_violation(tailored, _MASTER) is not None
    assert _subset_guard(tailored, _MASTER) is _MASTER
