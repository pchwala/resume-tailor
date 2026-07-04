from pathlib import Path

import pytest

from tracker.scraping import ScrapedJob, detect_board, extract

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.linkedin.com/jobs/view/123", "linkedin"),
        ("https://boards.greenhouse.io/acme/jobs/456", "greenhouse"),
        ("https://jobs.lever.co/acme/789", "lever"),
        ("https://justjoin.it/offers/abc", "justjoin"),
        ("https://nofluffjobs.com/job/xyz", "nofluffjobs"),
        ("https://www.pracuj.pl/praca/dev,oferta,1", "pracuj"),
        ("https://careers.some-unknown-company.com/job/1", "generic"),
    ],
)
def test_detect_board(url, expected):
    assert detect_board(url) == expected


def test_extract_jsonld():
    url = "https://boards.greenhouse.io/acme/jobs/456"
    job = extract(_fixture("jobposting_jsonld.html"), url)

    assert isinstance(job, ScrapedJob)
    assert job.title == "Senior Backend Engineer"
    # company suffix is preserved here; normalization happens in signatures.py
    assert job.company == "Acme Sp. z o.o."
    assert job.location == "Warsaw"
    # description HTML is flattened to plain text
    assert "backend engineer" in job.description
    assert "FastAPI" in job.description
    assert "<strong>" not in job.description
    assert job.source_board == "greenhouse"
    assert job.raw_html  # raw HTML retained for re-extraction


def test_extract_meta_fallback():
    url = "https://careers.some-unknown-company.com/job/1"
    job = extract(_fixture("meta_only.html"), url)

    assert job.title == "Fallback Job Title — Some Board"
    assert "only via meta tags" in job.description
    # no structured company/location available -> left blank, no crash
    assert job.company == ""
    assert job.location == ""
    assert job.source_board == "generic"


def test_extract_handles_malformed_jsonld():
    html = """
    <html><head>
      <title>Broken Board</title>
      <script type="application/ld+json">{ this is not valid json ]</script>
      <script type="application/ld+json">
        {"@type": "JobPosting", "title": "Recovered Title",
         "hiringOrganization": "Plain Co"}
      </script>
    </head><body></body></html>
    """
    job = extract(html, "https://example.com/job")

    # malformed block is skipped, the valid one is still used
    assert job.title == "Recovered Title"
    # hiringOrganization given as a bare string, not a dict
    assert job.company == "Plain Co"
