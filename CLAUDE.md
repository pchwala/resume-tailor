# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Status: **v1 implemented — no stubs remain.** Done: models, admin, env-driven settings,
> templates, deployment files, `signatures.py`, `scraping.py` (Playwright + JSON-LD/meta),
> `seed_resume`, PDF rendering (`tailoring/pdf.py` + self-contained `pdf_template.html`),
> **AI tailoring** (`tailoring/ai.py`), and the **TAILOR flow + 3-tab UI** (`tracker/views.py`
> + templates). The approved plan is `dev/25_06_minimal_req.md`; the reference resume design
> is `printable_resume/`. Deferred (plan follow-ups): background scrape queue, periodic
> re-scrape / "never closes" detection, inline Applied-tab status/notes editing, multiple
> templates, swapping the Tailwind Play CDN for a built asset.

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
  extraction). Owns the 3-tab UI + actions in `views.py`: `tailor` (scrape → dedup →
  `ai.tailor` → save `TailoredResume`, all inline/blocking), `mark_applied`, `pdf_download`,
  and `tracker/templates/tracker/pdf_template.html` (the self-contained PDF layout).
- **`tailoring/`** — `ResumeTemplate`, `TailoredResume` (`content` is JSON); `ai.py`
  (`tailor()` → gpt-4.1 via OpenAI **Structured Outputs** + pydantic → master-subset guard;
  guard violations fall back to `master_content()`, hard errors raise `TailoringError`) and
  `pdf.py` (Chromium `page.pdf()`; `master_content()` projects the master `Profile` into the
  tailored JSON shape and is the subset-guard fallback).

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
  model/migration change, run `pytest --create-db` once to rebuild it. Tests never make live
  OpenAI/Playwright calls — monkeypatch the seams: `tailoring.ai._complete` (the OpenAI call),
  and `tracker.views.scrape` / `tracker.views.tailor_resume` (imported at module level so
  patches take effect).
- Docker: `docker build -t resume-tailor .` then run with env vars / `--env-file .env`.

Settings are env-driven (`django-environ`): `SECRET_KEY`, `DEBUG`, `DATABASE_URL` (Neon
pooled; **required, no SQLite fallback** — fails fast if unset), `OPENAI_API_KEY`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`. Cloud Run: `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`
default to `.run.app` / `https://*.run.app` and `SECURE_PROXY_SSL_HEADER` is set (TLS is
terminated at the proxy). The Neon **pooled** endpoint (PgBouncer transaction mode) requires
`OPTIONS={"prepare_threshold": None}` + `DISABLE_SERVER_SIDE_CURSORS=True` (set in
`settings.py`) — `migrate` works without them but pooled runtime queries 500.
