"""Render a resume PDF from the shell — the offline verification path.

    python manage.py render_resume_pdf --out resume.pdf            # untailored master
    python manage.py render_resume_pdf --out r.pdf --tailored 3    # a TailoredResume

Needs Chromium (`playwright install chromium`) and a seeded Profile
(`python manage.py seed_resume`).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from profiles.models import Profile
from tailoring.models import TailoredResume
from tailoring.pdf import render_master_pdf, render_pdf


class Command(BaseCommand):
    help = "Render the master (or a TailoredResume) to a PDF file."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Output PDF path.")
        parser.add_argument(
            "--tailored", type=int, default=None,
            help="TailoredResume pk to render; omit to render the untailored master.",
        )

    def handle(self, *args, **options):
        if options["tailored"] is not None:
            try:
                tailored = TailoredResume.objects.get(pk=options["tailored"])
            except TailoredResume.DoesNotExist:
                raise CommandError(f"TailoredResume {options['tailored']} not found.")
            pdf_bytes = render_pdf(tailored)
            source = f"TailoredResume {tailored.pk}"
        else:
            profile = Profile.objects.first()
            if profile is None:
                raise CommandError("No Profile — run `python manage.py seed_resume` first.")
            pdf_bytes = render_master_pdf(profile)
            source = f"master profile {profile.name!r}"

        with open(options["out"], "wb") as fh:
            fh.write(pdf_bytes)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rendered {source} -> {options['out']} ({len(pdf_bytes)} bytes)."
            )
        )
