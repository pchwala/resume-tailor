"""Three-tab UI + the TAILOR / PDF / mark-applied actions.

The `tailor` view is the core loop: scrape a pasted URL, dedup it into a CanonicalJob via the
content signature, tailor the master resume to the posting, and persist a TailoredResume — all
inline (Playwright/OpenAI block the worker; a background queue is a plan follow-up). Scraping
and tailoring are imported at module level so tests can monkeypatch them. See
dev/25_06_minimal_req.md (The TAILOR action).
"""
import logging

from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from profiles.models import Profile
from tailoring.ai import MODEL, TailoringError, tailor as tailor_resume
from tailoring.models import ResumeTemplate, TailoredResume
from tracker.models import Application, CanonicalJob, JobPosting
from tracker.scraping import scrape
from tracker.signatures import signature

logger = logging.getLogger(__name__)


def _tailored_qs():
    """TailoredResume rows with the posting joined and an `is_applied` flag annotated."""
    applied = Application.objects.filter(tailored_resume=OuterRef("pk"))
    return (
        TailoredResume.objects.select_related("posting__canonical_job")
        .annotate(is_applied=Exists(applied))
        .order_by("-created_at")
    )


def dashboard(request):
    return render(request, "tracker/dashboard.html", {"recent": _tailored_qs()[:10]})


def applied(request):
    applications = (
        Application.objects.select_related("posting__canonical_job", "tailored_resume")
        .order_by("-applied_at")
    )
    return render(request, "tracker/applied.html", {"applications": applications})


def tailored(request):
    return render(request, "tracker/tailored.html", {"tailored_resumes": _tailored_qs()})


def _error(request, message: str, status: int = 200) -> HttpResponse:
    return render(request, "tracker/_tailor_result.html", {"error": message}, status=status)


@require_POST
def tailor(request):
    """Scrape → dedup → tailor → persist, returning an HTMX result partial."""
    url = (request.POST.get("url") or "").strip()
    if not url:
        return _error(request, "Please paste a job-posting URL.")

    profile = Profile.objects.first()
    if profile is None:
        return _error(request, "No resume profile found — run `python manage.py seed_resume`.")

    try:
        job = scrape(url)
    except Exception as exc:  # Playwright/network failure — surface, don't 500
        logger.warning("Scrape failed for %s: %s", url, exc)
        return _error(request, f"Could not scrape that URL: {exc}")

    sig = signature(job.company, job.title, job.location)
    canonical, created = CanonicalJob.objects.get_or_create(
        signature=sig,
        defaults={"company": job.company, "title": job.title, "location": job.location},
    )
    seen_before = not created

    posting, _ = JobPosting.objects.update_or_create(
        url=url,
        defaults={
            "canonical_job": canonical,
            "source_board": job.source_board,
            "raw_html": job.raw_html,
            "description": job.description,
            "scraped_at": timezone.now(),
        },
    )

    try:
        content = tailor_resume(profile, posting)
    except TailoringError as exc:
        logger.warning("Tailoring failed for %s: %s", url, exc)
        return _error(request, f"Tailoring failed: {exc}")

    template = ResumeTemplate.objects.filter(is_default=True).first()
    tr = TailoredResume.objects.create(
        posting=posting, template=template, content=content, model_used=MODEL
    )
    tr.is_applied = False  # freshly created; drives the row partial's action

    return render(
        request,
        "tracker/_tailor_result.html",
        {"tailored": tr, "seen_before": seen_before, "posting_count": canonical.postings.count()},
    )


@require_POST
def mark_applied(request, pk):
    """Create (idempotently) an Application for a tailored resume's posting."""
    tr = get_object_or_404(TailoredResume, pk=pk)
    Application.objects.get_or_create(
        posting=tr.posting, defaults={"tailored_resume": tr}
    )
    tr.is_applied = True
    return render(request, "tracker/_tailored_row.html", {"tailored": tr})


def pdf_download(request, pk):
    from tailoring.models import TailoredResume
    from tailoring.pdf import render_pdf

    tailored = get_object_or_404(TailoredResume, pk=pk)
    pdf_bytes = render_pdf(tailored)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="resume-{pk}.pdf"'
    return response
