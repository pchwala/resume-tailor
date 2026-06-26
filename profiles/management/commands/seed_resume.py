"""Seed master resume data from the current printable_resume/index.html content.

STUB — not yet implemented. See dev/25_06_minimal_req.md (Deliverables #5). On
implementation this should create one Profile + its SkillCategory/Skill, Experience, and
Project rows mirroring printable_resume/index.html so the app is usable right after migrate.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed master resume data from printable_resume/index.html content."

    def handle(self, *args, **options):
        raise NotImplementedError(
            "seed_resume is not yet implemented — see dev/25_06_minimal_req.md"
        )
