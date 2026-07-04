"""Three-tab UI + the TAILOR / PDF actions.

The tab views render skeleton templates. The `tailor` and `pdf_download` actions are
stubbed — they wire together scraping, signatures, AI tailoring, and PDF rendering, all of
which are themselves stubs. See dev/25_06_minimal_req.md (The TAILOR action, PDF export).
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render


def dashboard(request):
    return render(request, "tracker/dashboard.html")


def applied(request):
    return render(request, "tracker/applied.html")


def tailored(request):
    return render(request, "tracker/tailored.html")


def tailor(request):
    # TODO: scrape(url) -> signature -> get_or_create CanonicalJob -> JobPosting ->
    #       tailoring.ai.tailor(...) -> persist TailoredResume -> return HTMX partial.
    raise NotImplementedError(
        "TAILOR flow is not yet implemented — see dev/25_06_minimal_req.md"
    )


def pdf_download(request, pk):
    from tailoring.models import TailoredResume
    from tailoring.pdf import render_pdf

    tailored = get_object_or_404(TailoredResume, pk=pk)
    pdf_bytes = render_pdf(tailored)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="resume-{pk}.pdf"'
    return response
