# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Status: **scaffolded; key features stubbed.** The Django project, three apps, models,
> admin, env-driven settings, base templates, and deployment files exist. Behavioral
> modules — scraping, signatures, AI tailoring, PDF rendering, the TAILOR/PDF views, and
> `seed_resume` — raise `NotImplementedError` with TODOs pointing at the plan. The approved
> plan is `dev/25_06_minimal_req.md`; the reference resume design is `printable_resume/`.

## Project

Resume Tailor — a personal Django app to track job applications across boards, dedupe the
same job seen on different boards (via a normalized signature), and AI-tailor resumes to
each posting.

**Stack:** Django + HTMX + Tailwind (server-rendered, all-in-one) · PostgreSQL on Neon
(serverless, via `DATABASE_URL`) · Cloud Run · Playwright (headless Chromium) for scraping
**and** resume-PDF rendering (`page.pdf()`) · OpenAI API (`gpt-4.1`) for tailoring.

**Core workflow:** paste a job URL → scrape → AI-tailor the resume → save to DB → generate
a PDF on demand from a single v1 template. UI is three tabs: Dashboard, Applied/History,
Tailored.

## UI preferences

- Keep the UI **simple and robust**. Prioritize legibility and function.
- **No fancy animations, no flashy colors, no "AI fireworks."** Use a neutral palette and
  standard form controls. HTMX is for partial page updates, not visual flourish.

## Working conventions

- All plans and handoffs are saved in the **`dev/`** directory for future reference.
- Naming format: **`date_name.md`** (e.g. `25_06_minimal_req.md`).
- The current/active plan is `dev/25_06_minimal_req.md`.

## Architecture

Django project `config/`; three apps:
- **`profiles/`** — master resume data the AI tailors from: `Profile` (fixed identity +
  header/footer), `SkillCategory`/`Skill`, `Experience`, `Project`. `seed_resume`
  management command (stub) seeds these from `printable_resume/index.html`.
- **`tracker/`** — `CanonicalJob` (dedup group), `JobPosting`, `Application`; plus
  `signatures.py` (dedup hash) and `scraping.py` (Playwright) — both stubs. Owns the 3-tab
  UI views and `tracker/templates/tracker/pdf_template.html` (the PDF layout).
- **`tailoring/`** — `ResumeTemplate`, `TailoredResume` (`content` is JSON); `ai.py`
  (gpt-4.1 → validated tailored JSON + master-subset guard) and `pdf.py` (Chromium
  `page.pdf()`) — both stubs.

Tailoring contract: the AI returns JSON `{about, experiences[], skills[], projects[]}`
that the PDF template loops over; fixed facts (contact, company/period, project names) come
straight from `Profile`. Design lives in the template, content in the data — never fused.

## Commands

- Setup: `pip install -r requirements.txt` · `playwright install chromium` · copy
  `.env.example` → `.env`.
- Dev: `python manage.py migrate` · `python manage.py seed_resume` (stub) ·
  `python manage.py runserver` · `python manage.py createsuperuser` (for `/admin/`).
- Migrations: `python manage.py makemigrations` (none committed yet — generate after the
  first model review).
- Test: `pytest`.
- Docker: `docker build -t resume-tailor .` then run with env vars / `--env-file .env`.

Settings are env-driven (`django-environ`): `SECRET_KEY`, `DEBUG`, `DATABASE_URL` (Neon
pooled; falls back to local SQLite when unset), `OPENAI_API_KEY`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`.
