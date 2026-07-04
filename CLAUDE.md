# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Status: **partially implemented.** Done: models, admin, env-driven settings, base
> templates, deployment files, `signatures.py`, `seed_resume`, `scraping.py` (Playwright +
> JSON-LD/meta extraction), and PDF rendering (`tailoring/pdf.py` + the self-contained
> `pdf_template.html` with Inter bundled). Still stubbed (raise `NotImplementedError`): AI
> tailoring (`tailoring/ai.py`) and the TAILOR flow + 3-tab UI (`tracker/views.py`'s
> `tailor` view and the dashboard/applied/tailored templates). The approved plan is
> `dev/25_06_minimal_req.md`; the reference resume design is `printable_resume/`.

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
  management command seeds these from `printable_resume/index.html`.
- **`tracker/`** — `CanonicalJob` (dedup group), `JobPosting`, `Application`; plus
  `signatures.py` (dedup hash) and `scraping.py` (Playwright fetch + JSON-LD/meta
  extraction) — both implemented. Owns the 3-tab UI views (`tailor` still a stub) and
  `tracker/templates/tracker/pdf_template.html` (the self-contained PDF layout).
- **`tailoring/`** — `ResumeTemplate`, `TailoredResume` (`content` is JSON); `ai.py`
  (gpt-4.1 → validated tailored JSON + master-subset guard, **stub**) and `pdf.py`
  (Chromium `page.pdf()`; `master_content()` projects the master `Profile` into the
  tailored JSON shape and is the AI's future fallback) — `pdf.py` implemented.

Tailoring contract: the AI returns JSON `{about, experiences[], skills[], projects[]}`
that the PDF template loops over; fixed facts (contact, company/period, project names) come
straight from `Profile`. Design lives in the template, content in the data — never fused.

## Commands

- Setup: `pip install -r requirements.txt` · `playwright install chromium` · copy
  `.env.example` → `.env`.
- Dev: `python manage.py migrate` · `python manage.py seed_resume` ·
  `python manage.py runserver` · `python manage.py createsuperuser` (for `/admin/`).
- PDF: `python manage.py render_resume_pdf --out resume.pdf [--tailored <pk>]` — renders the
  untailored master (or a `TailoredResume`) to a PDF file; needs `playwright install chromium`.
- Migrations: `python manage.py makemigrations` (none committed yet — generate after the
  first model review).
- Test: `pytest`. Tests run against the **Neon** DB, so `pytest.ini` sets `--reuse-db` (the
  remote test DB is expensive to recreate and can deadlock on a lingering session). After a
  model/migration change, run `pytest --create-db` once to rebuild it.
- Docker: `docker build -t resume-tailor .` then run with env vars / `--env-file .env`.

Settings are env-driven (`django-environ`): `SECRET_KEY`, `DEBUG`, `DATABASE_URL` (Neon
pooled; **required, no SQLite fallback** — fails fast if unset), `OPENAI_API_KEY`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
