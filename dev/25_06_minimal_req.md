# Resume Tailor — Initial Build Plan

> Saved 2026-06-25. Updated 2026-06-25 to match the URL→Tailor→PDF workflow.
> Updated 2026-06-26 to templaterize the existing `printable_resume/` design: structured
> **JSON** tailoring contract, normalized master-data models (incl. a new `Project` model
> and an expanded `Profile`), and `TailoredResume.content` as JSON. See
> `printable_resume/index.html` + `resume.css` for the reference design.
> Status: **approved, not yet implemented.**

## Context

A personal tool to (1) track which job postings you've applied to across different job
boards, (2) recognize the *same* job when it appears on multiple boards (via a content
signature) so you can spot roles whose recruitment never closes, and (3) auto-tailor your
resume to each posting with an AI model and export it as a PDF.

You have FastAPI + React experience but consider that overkill here and want a single
all-in-one solution plus a database, deployable to Cloud Run. This plan scaffolds that
app from an empty directory.

**Core workflow (the user's mental model):**
1. **TAILOR** — paste a job URL. The app scrapes the page, tailors the resume with the
   model, and saves the tailored data to the DB. You can then **generate a PDF** from the
   saved data + a provided template (one template in v1).
2. The posted URL + scraped job offer + signature are persisted.
3. Minimal UI: three tabs — **Dashboard**, **Applied/History**, **Tailored**.

**Stack (decided):**
- **Django** (server-rendered, all-in-one) + **HTMX** + **Tailwind** for a custom UI,
  with the built-in **Django admin** as a power-user backend.
- **PostgreSQL on Neon** (managed, serverless), reached over TLS via a plain
  `DATABASE_URL` (Neon pooled endpoint). App on **Cloud Run** (stateless — SQLite would
  not persist there).
- **Playwright (headless Chromium)** for scraping every offer page (handles JS-rendered
  boards like LinkedIn/Greenhouse) **and** for rendering the resume PDF (`page.pdf()`).
- **Deterministic dedup**: a normalized hash of company + title (+ location).
- **OpenAI API** (`gpt-4.1`, Python SDK) for resume tailoring.

## Project layout

```
resume-tailor/
├─ manage.py
├─ pyproject.toml            # deps via pip/uv; or requirements.txt
├─ Dockerfile               # Playwright python base image (Chromium: scrape + PDF)
├─ .env.example             # OPENAI_API_KEY, DATABASE_URL, SECRET_KEY, DEBUG
├─ config/                  # Django project (settings/urls/wsgi/asgi)
│  ├─ settings.py           # env-driven via django-environ
│  └─ urls.py
├─ tracker/                 # offers, postings, applications, scraping, dedup
│  ├─ models.py
│  ├─ signatures.py         # normalize + hash
│  ├─ scraping.py           # Playwright fetch + per-board extraction
│  ├─ views.py              # HTMX dashboard / applied / tailored
│  ├─ admin.py
│  └─ templates/tracker/
│     └─ pdf_template.html  # v1 resume layout (ported from printable_resume/), filled
│                           # from Profile (fixed) + tailored JSON, rendered to PDF
├─ profiles/                # your master resume data + templates
│  ├─ models.py             # Profile, SkillCategory, Skill, Experience, Project
│  ├─ management/commands/
│  │  └─ seed_resume.py     # seed master data from printable_resume/index.html
│  └─ admin.py
├─ tailoring/               # AI tailoring + PDF export
│  ├─ ai.py                 # OpenAI client + prompt assembly
│  ├─ pdf.py                # render TailoredResume -> PDF bytes via Chromium
│  ├─ models.py             # TailoredResume
│  └─ views.py
├─ templates/base.html      # Tailwind + HTMX includes, 3-tab nav
└─ tests/
```

## Data model (`tracker/models.py`, `profiles/models.py`, `tailoring/models.py`)

- **`CanonicalJob`** — `signature` (unique, indexed), `company`, `title`, `location`,
  `first_seen`, `last_seen`. Groups postings that are the same job. (The long-span "never
  closes" surfacing is deferred; the signature/grouping is built now.)
- **`JobPosting`** — FK→`CanonicalJob`, `url` (unique), `source_board`, `raw_html`,
  `description`, `status` (open/closed/unknown), `scraped_at`, `first_seen`, `last_seen`.
- **`Application`** — FK→`JobPosting`, `applied_at`, FK→`TailoredResume` (nullable),
  `status` (applied/interview/offer/rejected), `notes`.
- **`Profile`** — singleton-ish master data, all **fixed** (never tailored): `name`,
  `subtitle` (headline), `location`, `website_url`, `github_url`, `email`, `linkedin_url`,
  master `about` text, `gdpr_text`. Rendered straight into the header/footer.
- **`SkillCategory`** — FK→`Profile`; `name` (e.g. "Frameworks"), `order`.
- **`Skill`** — FK→`SkillCategory`; `name` (the chip text), `order`.
- **`Experience`** — FK→`Profile`; `company`, `period`, `description` (master prose),
  `order`. Company + period are fixed facts; description is the AI's starting point.
- **`Project`** (resume "Key Projects" section) — FK→`Profile`; `name`, `tech` (JSON list
  of chip strings), `description` (master prose), `order`. Name + tech are fixed facts;
  description is tailorable.
- **`ResumeTemplate`** — `name`, `is_default`, `pdf_template_name` (defaults to
  `tracker/pdf_template.html`). v1 ships **one** default; the model is kept so more layouts
  can be added later. The tailored **structure** is driven by the JSON schema + master data
  (below), not by a Markdown body — there is no `content` field. The PDF layout lives in
  `pdf_template.html`.
- **`TailoredResume`** — FK→`JobPosting`, FK→`ResumeTemplate`, `content` (**JSONField**
  holding the validated tailored JSON), `model_used`, `created_at`. PDF is generated on
  demand (not stored as a file in v1).

## The TAILOR action (single flow)

`POST` paste-URL (HTMX, from Dashboard):
1. `detect_board(url)` + Playwright fetch → `raw_html` + extracted
   title/company/location/description.
2. `signature(company, title, location)` → `get_or_create(CanonicalJob)`. If the
   `CanonicalJob` already had postings, set a **"seen before"** flag for the response.
3. Create/update `JobPosting` (FK→CanonicalJob, `url` unique, board, html, description,
   status, timestamps).
4. Tailor: assemble prompt from the structured master data
   (`Profile`/`SkillCategory`/`Skill`/`Experience`/`Project`) + posting fields → OpenAI
   `gpt-4.1` (JSON response) → validate against the schema + master-subset guard → persist
   the tailored JSON on a `TailoredResume`.
5. HTMX returns the new Tailored row + any "you've seen this job before" notice.

## Signature / dedup (`tracker/signatures.py`)

`signature(company, title, location)`:
- normalize each field (lowercase, strip punctuation/extra whitespace, drop common
  suffixes like "Inc"/"Ltd", collapse seniority synonyms minimally),
- `sha256("company|title|location")` → hex.
On scrape, compute the signature, `get_or_create` the `CanonicalJob` by it, then attach
the `JobPosting`. Same signature across two boards ⇒ one `CanonicalJob`, two postings ⇒
"seen before" notice. (Filtered "never closes" analytics view is deferred — see below.)

## Scraping (`tracker/scraping.py`)

- Sync Playwright (`sync_playwright`) launching headless Chromium; run scrapes off the
  request thread (Django management command / a queued task) so page loads don't block
  the web worker.
- `detect_board(url)` by domain → per-board extractor (selectors for title/company/
  location/description) with a generic `<meta>`/JSON-LD `JobPosting` fallback.
- Store `raw_html` so extraction can be re-run/improved without re-fetching.

## AI tailoring (`tailoring/ai.py`)

Use the official OpenAI Python SDK (`pip install openai`).

**Tailoring contract — the JSON schema.** The AI returns (and we validate) exactly this
shape; it is the template's only input besides the fixed `Profile`:

```json
{
  "about": "tailored summary paragraph",
  "experiences": [
    {"company": "ZM Holding Sp. z o.o.", "period": "2022 — Present", "desc": "..."}
  ],
  "skills": [
    {"category": "Frameworks", "items": ["FastAPI", "React", "Flask"]}
  ],
  "projects": [
    {"name": "QuizMinds", "tech": ["React 19", "TypeScript"], "desc": "..."}
  ]
}
```

- `client = OpenAI()` (reads `OPENAI_API_KEY` from env).
- Model `gpt-4.1` with a **JSON / structured-output response format** so the model is forced
  to the schema (replaces the earlier loose-Markdown idea). Generous `max_tokens`.
- **Tailor scope = rewrite prose + select/reorder.** The AI may rewrite About / experience
  / project descriptions and may filter & reorder skills and projects. It must **keep every
  `company`, `period`, and `project.name` identical to the master, and never add a skill or
  project that isn't in the master.**
- System prompt: "You tailor resumes to a specific job without inventing experience."
  User content: the master data (About + experiences + skill categories + projects
  serialized as JSON) + the posting's `title`/`company`/`description` + the rules above.
- **Anti-hallucination guard:** after parsing, validate with pydantic and assert that the
  returned companies, periods, project names, and skill items are all subsets of the master
  DB values; on any violation, fall back to the untailored master.
- Persist the validated JSON on a `TailoredResume` with `model_used`.

```python
from openai import OpenAI
client = OpenAI()
resp = client.chat.completions.create(
    model="gpt-4.1",
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},  # master data JSON + posting + rules
    ],
)
tailored = validate_and_guard(resp.choices[0].message.content, master)  # pydantic + subset
```

## PDF export (`tailoring/pdf.py`)

On demand, from a `TailoredResume`:
- Render `tracker/templates/tracker/pdf_template.html` (ported from
  `printable_resume/index.html`, with `resume.css` inlined and the Inter font bundled) —
  header/contact-row/GDPR footer from the fixed `Profile`; About / Experience / Skills /
  Projects from `{% for %}` loops over the tailored `content` JSON. Produces a
  self-contained HTML string (no external CSS/icon/font paths for headless Chromium).
- `page.set_content(html)` then `page.pdf(format="A4", print_background=True)`; return the
  PDF bytes. Reuse the same `sync_playwright` plumbing as `tracker/scraping.py` (no new
  system deps — Chromium is already installed for scraping).
- `render_pdf(tailored_resume) -> bytes`; a view returns it as a file download.

## UI (HTMX + Tailwind + admin)

**Design principle: simple and robust. No animations, no flashy colors, no "AI
fireworks."** Plain, legible, functional layouts; neutral palette; standard form
controls. HTMX is used for partial updates — not for visual flourish.

Three tabs in `base.html`:
- **Dashboard** — the primary paste-URL form (the TAILOR entry point) that HTMX-posts and
  renders the result inline; below it, a short list of recent tailorings/applications and
  any "you've seen this job before" notices.
- **Applied / History** — the `Application` tracker: postings you've applied to, status,
  notes; a mark-as-applied action linking a posting (and its tailored resume).
- **Tailored** — list of `TailoredResume`s with view + a **"Generate PDF"** download
  action per row.

`base.html` loads Tailwind (Play CDN to start; swap to the standalone CLI build before
deploy) and HTMX from static. Django admin registers all models for quick data entry/
inspection of your profile, skill categories/skills, experience, projects, the default
template, and applications.

## Config & deployment

- `config/settings.py` driven by `django-environ`: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`
  (**Neon pooled connection string**, `sslmode=require`), `OPENAI_API_KEY`,
  `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`. Neon is just a URL via `environ.Env.db()` /
  `dj-database-url` — **no Cloud SQL connector, unix socket, or Secret-Manager DB
  plumbing**.
- WhiteNoise for static files; Gunicorn as the WSGI server.
- **Dockerfile** based on `mcr.microsoft.com/playwright/python` (Chromium preinstalled,
  used for both scraping and PDF); `collectstatic` + `migrate` at startup;
  `gunicorn config.wsgi`.
- **Cloud Run + Neon**: app on Cloud Run; `OPENAI_API_KEY` + `SECRET_KEY` from Secret
  Manager (or env); `DATABASE_URL` points at Neon's pooled endpoint. Mind Cloud Run's
  request-scoped lifecycle when configuring psycopg connections.
- Local dev: `DATABASE_URL` to Neon (or a local Postgres); `.env` from `.env.example`.

## Deliverables checklist

1. `pyproject.toml`/requirements (`django`, `psycopg[binary]`, `django-environ`,
   `playwright`, `openai`, `gunicorn`, `whitenoise`, `pytest-django`).
2. Django project + three apps with the models above (incl. `SkillCategory`/`Skill`,
   `Project`, expanded `Profile`) and migrations.
3. `signatures.py`, `scraping.py`, `tailoring/ai.py` (JSON schema + pydantic validation +
   master-subset guard), `tailoring/pdf.py`.
4. `tracker/templates/tracker/pdf_template.html` ported from `printable_resume/` (CSS
   inlined, Inter bundled, icons inlined) + HTMX/Tailwind app templates (3-tab nav) +
   admin registrations with inlines (simple/robust styling per the UI note).
5. `profiles/management/commands/seed_resume.py` — seeds master data from the current
   `printable_resume/index.html` content (keep `printable_resume/` as the reference design).
6. `Dockerfile`, `.env.example`, settings wired to env (Neon `DATABASE_URL`).
7. `CLAUDE.md` documenting commands (runserver, migrate, seed_resume, test, scrape command,
   PDF, Docker build/deploy) and the architecture above (satisfies the original `/init`).
8. Tests: signature normalization/dedup, scraping extraction (against a saved HTML
   fixture), tailoring schema validation + master-subset guard (OpenAI client mocked),
   `pdf_template.html` renders for both untailored master and tailored data, PDF render
   produces bytes.

## Verification (end-to-end)

1. `python manage.py migrate && python manage.py seed_resume` → master data populated;
   `python manage.py runserver` against Neon.
2. In admin, confirm `Profile`, skill categories/skills, experiences, and projects mirror
   the current resume (plus a default `ResumeTemplate`).
3. Render the **untailored master** to PDF (shell call to `render_pdf` or a debug view) and
   diff it visually against `printable_resume/index.html` — layout, chips, columns, and the
   GDPR footer should match the original design.
4. On the Dashboard, paste a real job-posting URL → confirm Playwright scrapes it, a
   `CanonicalJob` + `JobPosting` are created, fields are extracted, and a `TailoredResume`
   is generated in the one TAILOR action. Inspect the stored `content` JSON: About/
   descriptions rewritten, skills/projects reordered, **companies/periods/project names
   unchanged**.
5. Feed a deliberately bad AI response (mock) with an invented company/skill → confirm the
   subset guard rejects it and falls back to the master.
6. Paste a second board's URL for the *same* role → confirm it attaches to the **same**
   `CanonicalJob` and a "seen before" notice shows (dedup works).
7. On the Tailored tab, click **Generate PDF** → confirm a rendered PDF downloads and keeps
   the exact design.
8. `pytest` green.
9. `docker build` succeeds; smoke-run the container locally before any Cloud Run deploy.

## Open follow-ups (later, not this build)

- Background task queue for scraping (Cloud Tasks / a worker) instead of inline runs.
- Periodic re-scrape to update posting `status` and **automatic "never closes"** detection
  + its filtered analytics view.
- Optional AI/embedding semantic dedup layered on top of the hash signature.
- Caching/storing rendered PDFs; multiple resume templates.
