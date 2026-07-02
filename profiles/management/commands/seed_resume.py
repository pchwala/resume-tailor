"""Seed master resume data from the current printable_resume/index.html content.

Content mirrors printable_resume/index.html (kept as the reference design). Safe to
re-run: the Profile is get_or_create'd by name and its fixed fields are refreshed, and
all child rows (skill categories/skills, experiences, projects) are replaced from the
lists below on every run.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from profiles.models import Experience, Profile, Project, Skill, SkillCategory

PROFILE_DATA = {
    "name": "Przemysław Chwała",
    "subtitle": "Software Developer & Problem Solver",
    "location": "Warsaw, Poland",
    "website_url": "https://pchwala.dev/",
    "github_url": "https://github.com/pchwala",
    "email": "info@pchwala.dev",
    "linkedin_url": "https://linkedin.com/in/przemyslaw-chwala",
    "about": (
        "Software developer with 5+ years of experience building production systems for "
        "real businesses. I specialize in backend development and automation — APIs, "
        "integrations, and full-stack solutions with FastAPI, Node.js, and React. My "
        "approach is pragmatic: I understand the business process first, then build "
        "something that can be maintained, extended, and handed over. I'm equally "
        "comfortable in the terminal — Linux is my primary environment for development, "
        "deployment, and system-level tooling."
    ),
    "gdpr_text": (
        "I agree to the processing of personal data provided in this document for "
        "realising the recruitment process pursuant to the Personal Data Protection Act "
        "of 10 May 2018 (Journal of Laws 2018, item 1000) and in agreement with "
        "Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 "
        "April 2016 on the protection of natural persons with regard to the processing "
        "of personal data and on the free movement of such data, and repealing "
        "Directive 95/46/EC (General Data Protection Regulation)."
    ),
}

SKILL_CATEGORIES = [
    {"name": "Programming Languages", "skills": ["Python", "TypeScript", "C++"]},
    {"name": "Frameworks", "skills": ["FastAPI", "React", "Flask", "Material UI"]},
    {
        "name": "Linux & Systems",
        "skills": ["Linux", "Bash / Shell", "Docker", "SSH", "systemd"],
    },
    {
        "name": "Tools & Misc",
        "skills": [
            "Git",
            "GCP",
            "SQL",
            "Firebase",
            "REST API",
            "Pandas",
            "Tkinter",
            "PySide6",
            "HTML/CSS",
        ],
    },
    {
        "name": "AI & Automation",
        "skills": [
            "OpenAI API",
            "LLM Integration",
            "Process Automation",
            "Data Pipelines",
            "Webhooks",
        ],
    },
]

EXPERIENCES = [
    {
        "company": "ZM Holding Sp. z o.o.",
        "period": "2022 — Present",
        "description": (
            "Responsible for developing, deploying, and maintaining custom software "
            "solutions including an automated hardware testing application and "
            "e-commerce integration systems. Currently, besides maintaining existing "
            "solutions and implementing new tools, I am also taking on a project "
            "manager role — leading two external developers and coordinating ongoing "
            "delivery. This includes acting as the primary point of contact between "
            "the development team and internal business stakeholders, translating "
            "requirements into technical tasks."
        ),
    },
    {
        "company": "Freelancer",
        "period": "2021 — Present",
        "description": (
            "Creating custom software solutions for various clients, focusing on "
            "integrations and process automation. Highest priority is to deliver "
            "high-quality, maintainable code that meets client needs. Focus on system "
            "reliability, performance optimization, and user experience."
        ),
    },
]

PROJECTS = [
    {
        "name": "QuizMinds",
        "tech": ["React 19", "TypeScript", "FastAPI", "Capacitor", "Firebase", "Python"],
        "description": (
            "Polish-language spaced-repetition training platform for competitive quiz "
            "players. Local-first SPA with an on-device SM-2 engine backed by SQLite "
            "(wasm on web, native on Android via Capacitor), cross-device sync via "
            "FastAPI + PostgreSQL, anonymous-first Firebase auth, and a 4,500-question "
            "bank built through an AI-assisted translation and triage pipeline."
        ),
    },
    {
        "name": "Trade-Ins Manager",
        "tech": ["FastAPI", "React", "MUI", "OpenAI API", "Docker"],
        "description": (
            "Full-stack solution integrating a major marketplace with a local "
            "e-commerce platform. Handles management and synchronization of orders, "
            "trade-ins, and returns, automating customer contact via the OpenAI API "
            "and updating prices and auction listings in real-time."
        ),
    },
    {
        "name": "Marketplace Integration",
        "tech": ["Flask", "REST APIs", "GCP", "Python"],
        "description": (
            "Backend solution with a lightweight frontend UI integrating Refurbed with "
            "IdoSell. Manages inventory synchronization, automates order creation and "
            "processing, and handles parcel tracking — deployed on Google Cloud "
            "Platform."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed master resume data from printable_resume/index.html content."

    @transaction.atomic
    def handle(self, *args, **options):
        profile, created = Profile.objects.update_or_create(
            name=PROFILE_DATA["name"], defaults=PROFILE_DATA
        )

        profile.skill_categories.all().delete()
        profile.experiences.all().delete()
        profile.projects.all().delete()

        for cat_order, cat_data in enumerate(SKILL_CATEGORIES):
            category = SkillCategory.objects.create(
                profile=profile, name=cat_data["name"], order=cat_order
            )
            Skill.objects.bulk_create(
                Skill(category=category, name=skill_name, order=skill_order)
                for skill_order, skill_name in enumerate(cat_data["skills"])
            )

        Experience.objects.bulk_create(
            Experience(
                profile=profile,
                company=exp["company"],
                period=exp["period"],
                description=exp["description"],
                order=order,
            )
            for order, exp in enumerate(EXPERIENCES)
        )

        Project.objects.bulk_create(
            Project(
                profile=profile,
                name=proj["name"],
                tech=proj["tech"],
                description=proj["description"],
                order=order,
            )
            for order, proj in enumerate(PROJECTS)
        )

        skill_count = Skill.objects.filter(category__profile=profile).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} profile {profile.name!r} — "
                f"{profile.skill_categories.count()} skill categories "
                f"({skill_count} skills), {profile.experiences.count()} experiences, "
                f"{profile.projects.count()} projects."
            )
        )
