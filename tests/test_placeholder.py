"""Scaffold placeholder.

Real tests to add during implementation (see dev/25_06_minimal_req.md, Deliverables #8):
  - signature normalization / dedup
  - scraping extraction against a saved HTML fixture
  - tailoring schema validation + master-subset guard (OpenAI client mocked)
  - pdf_template.html renders for both untailored master and tailored data
  - render_pdf() returns non-empty bytes
"""


def test_scaffold_imports():
    import config.settings  # noqa: F401
    import profiles.models  # noqa: F401
    import tailoring.models  # noqa: F401
    import tracker.models  # noqa: F401
