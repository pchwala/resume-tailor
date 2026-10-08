# Resume Tailor

A personal Django app that does three things:
- **Tracks job applications** across job boards.
- **Spots duplicate postings.** The same job seen on several boards is matched by a
  normalized signature.
- **Tailors your resume with AI** for each posting, and exports a PDF.

Paste a job URL. The app scrapes the posting, tailors your master resume to it with
`gpt-4.1`, and saves the result. You can then download a PDF at any time.

## Stack

- **Django 5 + HTMX + Tailwind**, server-rendered, with the Django admin as a back office.
- **PostgreSQL on Neon**, using the pooled endpoint via `DATABASE_URL`.
- **Playwright (headless Chromium)** for both scraping and PDF rendering.
- **OpenAI `gpt-4.1`** with Structured Outputs, validated with pydantic.
- **Gunicorn + WhiteNoise**, deployed with Docker on Cloud Run.

## Quick start

Requires Python 3.10+ (developed on 3.14) and a Postgres database (Neon or local). There is
no SQLite fallback.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env        # set DATABASE_URL, OPENAI_API_KEY, SECRET_KEY

python manage.py migrate
python manage.py seed_resume          # load the master resume from printable_resume/
python manage.py createsuperuser      # for /admin/
python manage.py runserver
```

Then open http://localhost:8000. The app has three tabs:
- **Dashboard:** paste a URL to tailor.
- **Applied / History:** your applications.
- **Tailored:** all tailored resumes, with PDF download and mark-as-applied.

## Commands

| Task | Command |
|---|---|
| Run dev server | `python manage.py runserver` |
| Re-seed master resume | `python manage.py seed_resume` (safe to re-run) |
| Render master resume to PDF | `python manage.py render_resume_pdf --out resume.pdf` |
| Render a tailored resume | `python manage.py render_resume_pdf --out r.pdf --tailored <pk>` |
| Tests | `pytest` (add `--create-db` once after model changes) |
| Docker | `docker build -t resume-tailor .` then `docker run --env-file .env -p 8080:8080 resume-tailor` |

Tests use a test database on Neon and keep it between runs (`--reuse-db`). They never call
OpenAI or Playwright, because those calls are monkeypatched.

## Configuration

Settings are read from the environment or `.env`; see `.env.example`.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | Neon **pooled** connection string with `sslmode=require` |
| `OPENAI_API_KEY` | for tailoring | |
| `SECRET_KEY` | in production | Falls back to an insecure dev value |
| `DEBUG` | no | Defaults to `False` |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | no | Default to localhost plus `.run.app` / `https://*.run.app` |

## Project layout

```
config/            settings, urls
profiles/          master resume models (Profile, skills, experience, projects) + seed_resume
tracker/           jobs/postings/applications, signatures.py, scraping.py, views + templates
tailoring/         TailoredResume, ai.py (OpenAI + subset guard), pdf.py, render_resume_pdf
templates/         base.html (3-tab nav)
printable_resume/  reference resume design the PDF template is ported from
tests/             pytest suite + HTML fixtures
doc/               architecture & reference docs
dev/               plans and handoffs (date_name.md)
```

## Documentation

- [`doc/architecture.md`](doc/architecture.md) explains how it works: data model, the
  TAILOR flow, dedup, scraping, the AI contract and guard, PDF rendering, config and
  deployment.
- [`dev/25_06_minimal_req.md`](dev/25_06_minimal_req.md) is the active plan: original
  design, implementation status, known gaps and next steps.

## Status

v1 is feature-complete. **It is not yet ready for public deployment**, because the UI has
no authentication. The active plan lists the known gaps and what to do next.
