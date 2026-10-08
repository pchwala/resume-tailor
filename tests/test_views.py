import pytest
from django.urls import reverse

from tailoring.ai import TailoringError
from tracker import views
from tracker.models import Application, CanonicalJob, JobPosting
from tracker.scraping import ScrapedJob
from tracker.signatures import signature


@pytest.fixture
def profile(db):
    from profiles.models import Profile

    return Profile.objects.create(name="Przemysław Chwała", about="Master about.")


def _scraped(company="Acme", title="Backend Developer", location="Warsaw"):
    return ScrapedJob(
        title=title, company=company, location=location,
        description="We need a FastAPI backend developer.",
        raw_html="<html></html>", source_board="generic",
    )


def _fake_scrape(**kw):
    return lambda url: _scraped(**kw)


def _fake_tailor(content=None):
    content = content or {"about": "tailored", "experiences": [], "skills": [], "projects": []}
    return lambda profile, posting: content


def _make_tailored():
    from tailoring.models import TailoredResume

    canonical = CanonicalJob.objects.create(
        signature="sig", company="Acme", title="Backend Developer", location="Warsaw",
    )
    posting = JobPosting.objects.create(
        canonical_job=canonical, url="https://example.com/job/1", description="d",
    )
    return TailoredResume.objects.create(posting=posting, content={"about": "x"})


# --- tabs render ----------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("name", ["dashboard", "applied", "tailored"])
def test_tabs_render(admin_client, name):
    assert admin_client.get(reverse(name)).status_code == 200


# --- tailor flow ----------------------------------------------------------------------------

@pytest.mark.django_db
def test_tailor_happy_path(admin_client, profile, monkeypatch):
    from tailoring.models import TailoredResume

    monkeypatch.setattr(views, "scrape", _fake_scrape())
    monkeypatch.setattr(views, "tailor_resume", _fake_tailor())

    resp = admin_client.post(reverse("tailor"), {"url": "https://example.com/job/1"})

    assert resp.status_code == 200
    assert b"Backend Developer" in resp.content
    assert CanonicalJob.objects.count() == 1
    assert JobPosting.objects.count() == 1
    tr = TailoredResume.objects.get()
    assert tr.content["about"] == "tailored"
    assert tr.model_used  # MODEL recorded


@pytest.mark.django_db
def test_tailor_seen_before_notice(admin_client, profile, monkeypatch):
    monkeypatch.setattr(views, "scrape", _fake_scrape())
    monkeypatch.setattr(views, "tailor_resume", _fake_tailor())
    # Pre-existing canonical job with the same signature the scrape will produce.
    CanonicalJob.objects.create(
        signature=signature("Acme", "Backend Developer", "Warsaw"),
        company="Acme", title="Backend Developer", location="Warsaw",
    )

    resp = admin_client.post(reverse("tailor"), {"url": "https://example.com/job/1"})

    assert b"seen this job before" in resp.content
    assert CanonicalJob.objects.count() == 1  # no duplicate group


@pytest.mark.django_db
def test_tailor_dedups_across_urls(admin_client, profile, monkeypatch):
    monkeypatch.setattr(views, "scrape", _fake_scrape())
    monkeypatch.setattr(views, "tailor_resume", _fake_tailor())

    admin_client.post(reverse("tailor"), {"url": "https://a.example.com/job"})
    admin_client.post(reverse("tailor"), {"url": "https://b.example.com/job"})

    assert CanonicalJob.objects.count() == 1
    assert JobPosting.objects.count() == 2


@pytest.mark.django_db
def test_tailor_tailoring_error_shows_message_and_saves_no_resume(admin_client, profile, monkeypatch):
    from tailoring.models import TailoredResume

    def boom(profile, posting):
        raise TailoringError("model refused")

    monkeypatch.setattr(views, "scrape", _fake_scrape())
    monkeypatch.setattr(views, "tailor_resume", boom)

    resp = admin_client.post(reverse("tailor"), {"url": "https://example.com/job/1"})

    assert b"Tailoring failed" in resp.content
    assert TailoredResume.objects.count() == 0
    assert JobPosting.objects.count() == 1  # posting persisted before tailoring


@pytest.mark.django_db
def test_tailor_missing_url(admin_client, profile):
    resp = admin_client.post(reverse("tailor"), {"url": ""})
    assert b"paste a job-posting URL" in resp.content


# --- mark_applied ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mark_applied_is_idempotent(admin_client):
    tr = _make_tailored()

    resp = admin_client.post(reverse("mark_applied", args=[tr.pk]))
    assert resp.status_code == 200
    assert b"Applied" in resp.content
    app = Application.objects.get()
    assert app.posting == tr.posting
    assert app.tailored_resume == tr

    admin_client.post(reverse("mark_applied", args=[tr.pk]))
    assert Application.objects.count() == 1  # no duplicate


# --- auth + method guards -------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("name", ["dashboard", "applied", "tailored"])
def test_tabs_require_login(client, name):
    url = reverse(name)
    resp = client.get(url)
    assert resp.status_code == 302
    assert resp["Location"] == f"{reverse('admin:login')}?next={url}"


@pytest.mark.django_db
def test_pdf_download_requires_login(client):
    tr = _make_tailored()
    resp = client.get(reverse("pdf_download", args=[tr.pk]))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_tailor_requires_login(client, monkeypatch):
    monkeypatch.setattr(views, "scrape", _fake_scrape())
    resp = client.post(reverse("tailor"), {"url": "https://example.com/job/1"})
    assert resp.status_code == 302
    assert JobPosting.objects.count() == 0


@pytest.mark.django_db
def test_actions_reject_get(admin_client):
    tr = _make_tailored()
    assert admin_client.get(reverse("tailor")).status_code == 405
    assert admin_client.get(reverse("mark_applied", args=[tr.pk])).status_code == 405
    assert Application.objects.count() == 0
