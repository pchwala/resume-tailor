"""AI tailoring against the structured JSON contract.

STUB — not yet implemented. See dev/25_06_minimal_req.md (AI tailoring).

Target flow:
  1. Serialize master data (Profile.about + experiences + skill categories + projects).
  2. Call gpt-4.1 with a JSON response format + the tailoring rules (rewrite prose, may
     reorder/drop skills & projects; keep company/period/project.name identical; never add
     a skill/project not in the master).
  3. Validate the response against TailoredResumeSchema (pydantic).
  4. Subset guard: returned companies/periods/project names/skill items must all be subsets
     of the master values; on any violation, fall back to the untailored master.

The tailored JSON shape (the PDF template's only input besides the fixed Profile):
  {
    "about": str,
    "experiences": [{"company": str, "period": str, "desc": str}],
    "skills": [{"category": str, "items": [str]}],
    "projects": [{"name": str, "tech": [str], "desc": str}],
  }
"""
from __future__ import annotations

SYSTEM_PROMPT = "You tailor resumes to a specific job without inventing experience."


def tailor(profile, posting) -> dict:
    """Return validated, guarded tailored-resume JSON for a posting. STUB."""
    raise NotImplementedError(
        "tailor() is not yet implemented — see dev/25_06_minimal_req.md"
    )
