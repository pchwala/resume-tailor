"""Three-tab UI + the TAILOR / PDF actions.

The tab views render skeleton templates. The `tailor` and `pdf_download` actions are
stubbed — they wire together scraping, signatures, AI tailoring, and PDF rendering, all of
which are themselves stubs. See dev/25_06_minimal_req.md (The TAILOR action, PDF export).
"""
from django.shortcuts import render


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
    # TODO: load TailoredResume(pk) -> tailoring.pdf.render_pdf(...) -> FileResponse.
    raise NotImplementedError(
        "pdf_download is not yet implemented — see dev/25_06_minimal_req.md"
    )
