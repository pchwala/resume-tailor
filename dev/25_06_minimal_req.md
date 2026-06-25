# Resume Tailor — Initial Build Plan

> Saved 2026-06-25. Status: **approved, not yet implemented.**

## Context

A personal tool to (1) track which job postings you've applied to across different job
boards, (2) recognize the *same* job when it appears on multiple boards (via a content
signature) so you can spot roles whose recruitment never closes, and (3) auto-tailor your
resume to each posting with an AI model.

You have FastAPI + React experience but consider that overkill here and want a single
all-in-one solution plus a database, deployable to Cloud Run. This plan scaffolds that
app from an empty directory.

**Stack (decided):**
- **Django** (server-rendered, all-in-one) + **HTMX** + **Tailwind** for a custom UI,
  with the built-in **Django admin** as a power-user backend.
- **PostgreSQL** on **Cloud SQL**, app on **Cloud Run** (stateless — SQLite would not
  persist there).
- **Playwright (headless Chromium)** for scraping every offer page (handles JS-rendered
  boards like LinkedIn/Greenhouse).
- **Deterministic dedup**: a normalized hash of company + title (+ location).
- **OpenAI API** (`gpt-4.1`, Python SDK) for resume tailoring.

## Project layout

```
resume-tailor/
├─ manage.py
├─ pyproject.toml            # deps via pip/uv; or requirements.txt
├─ Dockerfile               # Playwright python base image
├─ .env.example             # OPENAI_API_KEY, DATABASE_URL, SECRET_KEY, DEBUG
├─ config/                  # Django project (settings/urls/wsgi/asgi)
│  ├─ settings.py           # env-driven via django-environ
│  └─ urls.py
├─ tracker/                 # offers, postings, applications, scraping, dedup
│  ├─ models.py
│  ├─ signatures.py         # normalize + hash
│  ├─ scraping.py           # Playwright fetch + per-board extraction
│  ├─ views.py              # HTMX list/detail/add-URL
│  ├─ admin.py
│  └─ templates/tracker/
├─ profiles/                # your master resume data + templates
│  ├─ models.py             # Profile, Skill, Experience, ResumeTemplate
│  └─ admin.py
├─ tailoring/               # AI tailoring
│  ├─ ai.py                 # OpenAI client + prompt assembly
│  ├─ models.py             # TailoredResume
│  └─ views.py
├─ templates/base.html      # Tailwind + HTMX includes
└─ tests/
```

## Data model (`tracker/models.py`, `profiles/models.py`, `tailoring/models.py`)

- **`CanonicalJob`** — `signature` (unique, indexed), `company`, `title`, `location`,
  `first_seen`, `last_seen`. Groups postings that are the same job. "Never closes" =
  long span between `first_seen` and `last_seen` while postings stay open → surface as a
  filtered list / admin view.
- **`JobPosting`** — FK→`CanonicalJob`, `url` (unique), `source_board`, `raw_html`,
  `description`, `status` (open/closed/unknown), `scraped_at`, `first_seen`, `last_seen`.
- **`Application`** — FK→`JobPosting`, `applied_at`, FK→`TailoredResume` (nullable),
  `status` (applied/interview/offer/rejected), `notes`.
- **`Profile`** — singleton-ish master data: contact info + free-form summary.
- **`Skill`**, **`Experience`** — FK→`Profile`; structured rows the AI draws from.
- **`ResumeTemplate`** — `name`, `content` (Markdown), `is_default`.
- **`TailoredResume`** — FK→`JobPosting`, FK→`ResumeTemplate`, `content`, `model_used`,
  `created_at`.

## Signature / dedup (`tracker/signatures.py`)

`signature(company, title, location)`:
- normalize each field (lowercase, strip punctuation/extra whitespace, drop common
  suffixes like "Inc"/"Ltd", collapse seniority synonyms minimally),
- `sha256("company|title|location")` → hex.
On scrape, compute the signature, `get_or_create` the `CanonicalJob` by it, then attach
the `JobPosting`. Same signature across two boards ⇒ one `CanonicalJob`, two postings.

## Scraping (`tracker/scraping.py`)

- Sync Playwright (`sync_playwright`) launching headless Chromium; run scrapes off the
  request thread (Django management command / a queued task) so page loads don't block
  the web worker.
- `detect_board(url)` by domain → per-board extractor (selectors for title/company/
  location/description) with a generic `<meta>`/JSON-LD `JobPosting` fallback.
- Store `raw_html` so extraction can be re-run/improved without re-fetching.

## AI tailoring (`tailoring/ai.py`)

Use the official OpenAI Python SDK (`pip install openai`).

- `client = OpenAI()` (reads `OPENAI_API_KEY` from env).
- Model `gpt-4.1`; **stream** the request (tailored resumes can be long — streaming
  avoids HTTP timeouts). Generous `max_tokens` (e.g. 8000–16000).
- System prompt: "You tailor resumes to a specific job without inventing experience."
  User content: the `ResumeTemplate` + structured `Profile`/`Skill`/`Experience` +
  the posting's `title`/`company`/`description`.
- Persist the result as a `TailoredResume` with `model_used`.

```python
from openai import OpenAI
client = OpenAI()
stream = client.chat.completions.create(
    model="gpt-4.1",
    max_tokens=8000,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ],
    stream=True,
)
text = "".join(chunk.choices[0].delta.content or "" for chunk in stream)
```

## UI (HTMX + Tailwind + admin)

**Design principle: simple and robust. No animations, no flashy colors, no "AI
fireworks."** Plain, legible, functional layouts; neutral palette; standard form
controls. HTMX is used for partial updates (add-URL, tailor) — not for visual flourish.

- `base.html` loads Tailwind (Play CDN to start; swap to the standalone CLI build before
  deploy) and HTMX from static.
- Pages: **offers list** (canonical jobs, with "still open / never closes" filter),
  **posting detail** (raw vs extracted, applications, tailored resumes), **add-URL form**
  (HTMX POST → scrape → render the new row), **tailor button** (HTMX POST → stream/poll →
  show the tailored resume).
- Django admin registers all models for quick data entry/inspection of your profile,
  templates, and applications.

## Config & deployment

- `config/settings.py` driven by `django-environ`: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`,
  `OPENAI_API_KEY`, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`.
- WhiteNoise for static files; Gunicorn as the WSGI server.
- **Dockerfile** based on `mcr.microsoft.com/playwright/python` (Chromium preinstalled);
  `collectstatic` + `migrate` at startup; `gunicorn config.wsgi`.
- **Cloud Run + Cloud SQL**: connect via the Cloud SQL connector / unix socket; pull
  `OPENAI_API_KEY`, `SECRET_KEY`, DB creds from **Secret Manager**.
- Local dev: Postgres via Docker (or `DATABASE_URL` to a local instance); `.env` from
  `.env.example`.

## Deliverables checklist

1. `pyproject.toml`/requirements (`django`, `psycopg[binary]`, `django-environ`,
   `playwright`, `openai`, `gunicorn`, `whitenoise`, `pytest-django`).
2. Django project + three apps with the models above and migrations.
3. `signatures.py`, `scraping.py`, `tailoring/ai.py`.
4. HTMX/Tailwind templates + admin registrations (simple/robust styling per the UI note).
5. `Dockerfile`, `.env.example`, settings wired to env.
6. `CLAUDE.md` documenting commands (runserver, migrate, test, scrape command, Docker
   build/deploy) and the architecture above (satisfies the original `/init`).
7. Tests: signature normalization/dedup, scraping extraction (against a saved HTML
   fixture), tailoring with the OpenAI client mocked.

## Verification (end-to-end)

1. `python manage.py migrate && python manage.py runserver` against local Postgres.
2. In admin, create a `Profile` with a couple of `Skill`/`Experience` rows and a default
   `ResumeTemplate`.
3. Add a real job-posting URL via the UI → confirm Playwright scrapes it, a
   `CanonicalJob` + `JobPosting` are created, and fields are extracted.
4. Add a second board's URL for the *same* role → confirm it attaches to the **same**
   `CanonicalJob` (dedup works).
5. Click "tailor" → confirm a `TailoredResume` is generated and rendered.
6. `pytest` green.
7. `docker build` succeeds; smoke-run the container locally before any Cloud Run deploy.

## Open follow-ups (later, not this build)

- Background task queue for scraping (Cloud Tasks / a worker) instead of inline runs.
- Periodic re-scrape to update posting `status` and detect "never closes" automatically.
- Optional AI/embedding semantic dedup layered on top of the hash signature.
