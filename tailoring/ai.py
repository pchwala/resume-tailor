"""AI tailoring against the structured JSON contract.

`tailor(profile, posting)` calls gpt-4.1 with OpenAI Structured Outputs (the pydantic schema
below is enforced server-side), then runs an anti-hallucination subset guard: the returned
companies/periods, skill items, and project names/tech must all be subsets of the master
`Profile` data. On a guard violation it falls back to the untailored master
(`master_content`); on a hard failure (API/network/refusal/unparseable) it raises
`TailoringError` so the caller can surface the problem. See dev/25_06_minimal_req.md.

The tailored JSON shape (the PDF template's only input besides the fixed Profile):
  {
    "about": str,
    "experiences": [{"company": str, "period": str, "desc": str}],
    "skills": [{"category": str, "items": [str]}],
    "projects": [{"name": str, "tech": [str], "desc": str}],
  }
"""
from __future__ import annotations

import json
import logging

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from tailoring.pdf import master_content

logger = logging.getLogger(__name__)

MODEL = "gpt-4.1"
SYSTEM_PROMPT = "You tailor resumes to a specific job without inventing experience."

_RULES = (
    "Rules:\n"
    "- Rewrite the About paragraph and the experience/project descriptions to match the job.\n"
    "- You may filter and reorder skills and projects for relevance.\n"
    "- Keep every experience `company` and `period` and every project `name` identical to the"
    " master — do not alter, add, or invent them.\n"
    "- Never add a skill item, skill category, or project that is not present in the master.\n"
    "- Only tech chips already listed under a project in the master may appear for it.\n"
    "- Return the full structure: about, experiences, skills, projects."
)


# --- Tailoring contract (enforced by OpenAI Structured Outputs) -----------------------------

class ExperienceItem(BaseModel):
    company: str
    period: str
    desc: str


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class ProjectItem(BaseModel):
    name: str
    tech: list[str]
    desc: str


class TailoredResumeSchema(BaseModel):
    about: str
    experiences: list[ExperienceItem]
    skills: list[SkillGroup]
    projects: list[ProjectItem]


class TailoringError(Exception):
    """Raised on a hard tailoring failure (API/network error, refusal, or unparseable output)."""


# --- Public entry point ---------------------------------------------------------------------

def tailor(profile, posting) -> dict:
    """Return validated, subset-guarded tailored-resume JSON for a posting.

    Raises TailoringError on a hard failure; falls back to the untailored master when the
    model's output violates the subset guard.
    """
    master = master_content(profile)
    messages = _build_messages(master, posting)

    try:
        parsed = _complete(messages)
    except OpenAIError as exc:  # API / network / SDK errors
        raise TailoringError(f"OpenAI request failed: {exc}") from exc
    except ValidationError as exc:  # output did not satisfy the schema
        raise TailoringError(f"Tailored output failed validation: {exc}") from exc

    return _subset_guard(parsed.model_dump(), master)


# --- Internals ------------------------------------------------------------------------------

def _build_messages(master: dict, posting) -> list[dict]:
    canonical = posting.canonical_job
    user = (
        "Master resume data (JSON):\n"
        f"{json.dumps(master, ensure_ascii=False, indent=2)}\n\n"
        "Job posting:\n"
        f"Title: {canonical.title}\n"
        f"Company: {canonical.company}\n"
        f"Description:\n{posting.description}\n\n"
        f"{_RULES}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _complete(messages: list[dict]) -> TailoredResumeSchema:
    """Isolated network call — parse gpt-4.1's structured output into the schema.

    Tests monkeypatch this so the guard/fallback logic runs without touching the SDK.
    """
    client = OpenAI()  # instantiated lazily so importing this module needs no API key
    resp = client.chat.completions.parse(
        model=MODEL,
        messages=messages,
        response_format=TailoredResumeSchema,
    )
    message = resp.choices[0].message
    if message.refusal:
        raise TailoringError(f"Model refused to tailor: {message.refusal}")
    if message.parsed is None:
        raise TailoringError("Model returned no parsed content.")
    return message.parsed


def _subset_guard(tailored: dict, master: dict) -> dict:
    """Return `tailored` if it only uses master facts, else fall back to `master`."""
    reason = _guard_violation(tailored, master)
    if reason:
        logger.warning("Tailored resume failed subset guard (%s); falling back to master.", reason)
        return master
    return tailored


def _guard_violation(tailored: dict, master: dict) -> str | None:
    """Return a human-readable reason string if `tailored` invents facts, else None."""
    master_pairs = {(e["company"], e["period"]) for e in master["experiences"]}
    master_items = {c["category"]: set(c["items"]) for c in master["skills"]}
    master_tech = {p["name"]: set(p["tech"]) for p in master["projects"]}

    for exp in tailored["experiences"]:
        if (exp["company"], exp["period"]) not in master_pairs:
            return f"unknown experience {exp['company']!r} / {exp['period']!r}"

    for group in tailored["skills"]:
        allowed = master_items.get(group["category"])
        if allowed is None:
            return f"unknown skill category {group['category']!r}"
        invented = set(group["items"]) - allowed
        if invented:
            return f"invented skills {sorted(invented)!r} in {group['category']!r}"

    for proj in tailored["projects"]:
        allowed_tech = master_tech.get(proj["name"])
        if allowed_tech is None:
            return f"unknown project {proj['name']!r}"
        invented = set(proj["tech"]) - allowed_tech
        if invented:
            return f"invented tech {sorted(invented)!r} in {proj['name']!r}"

    return None
