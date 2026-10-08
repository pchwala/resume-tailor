# Resume Tailor — Architecture & Reference

How the app is built, as of 2026-10-08. For setup and commands see the
[README](../README.md); for status, known gaps and the roadmap see the active plan
[`dev/25_06_minimal_req.md`](../dev/25_06_minimal_req.md).

## Overview

A single-user Django app. You paste a job-posting URL. The app scrapes it, groups it with
the same role seen on other boards, asks `gpt-4.1` to tailor your master resume to it, and
stores the result. You can then download a PDF built from one HTML template.

```
URL ──► scrape (Playwright) ──► signature ──► CanonicalJob / JobPosting
                                                   │
                     Profile (master resume) ──► tailor (OpenAI + subset guard)
                                                   │
                                             TailoredResume.content (JSON)
                                                   │
                         pdf_template.html ──► Chromium page.pdf() ──► download
```

Everything runs in the request. Scraping, OpenAI and PDF rendering all block the web
worker; there is no task queue yet.

## Apps

| App | Owns |
|---|---|
| `config/` | Settings (env-driven), root URLs, WSGI/ASGI |
| `profiles/` | Master resume data + `seed_resume` command |
| `tracker/` | Jobs, postings, applications; dedup, scraping; **all UI views and templates**, including the PDF template |
| `tailoring/` | `ResumeTemplate`, `TailoredResume`; AI tailoring (`ai.py`), PDF rendering (`pdf.py`), `render_resume_pdf` command |

## Data model

```
Profile ─┬─< SkillCategory ─< Skill
         ├─< Experience
         └─< Project

CanonicalJob ─< JobPosting ─┬─< TailoredResume >── ResumeTemplate
                            └─< Application ──> TailoredResume (nullable)
```

**Master data (`profiles/models.py`).** `Profile` is treated as a singleton; code uses
`Profile.objects.first()`. Its identity, header and footer fields (name, subtitle,
location, links, email, GDPR text) are **fixed** and never tailored. `about` is the master
summary that the AI rewrites a copy of. `Experience.company`/`period` and
`Project.name`/`tech` are fixed facts. Their `description` fields are the master text the
AI starts from. Every child model has an `order` field.

**Tracking (`tracker/models.py`).**
- `CanonicalJob`: one real-world role, unique by `signature`.
- `JobPosting`: one URL on one board (`url` unique). Stores `raw_html` so extraction can
  be re-run later, plus `description`, `source_board` and `status`
  (open/closed/unknown; currently never updated).
- `Application`: a posting you applied to. Has a status (applied / interview / offer /
  rejected), notes, and an optional link to the `TailoredResume` you used.

**Tailoring (`tailoring/models.py`).**
- `TailoredResume.content` is the validated JSON (see the contract below), plus
  `model_used`.
- `ResumeTemplate` names a Django template for the PDF. None is seeded yet, so rendering
  falls back to `tracker/pdf_template.html`.

## The TAILOR flow (`tracker/views.py:tailor`)

`POST /tailor/` from the Dashboard form (HTMX):

1. Validate that a URL was sent and a `Profile` exists.
2. `scrape(url)`. Any exception becomes an inline error message, not a 500.
3. `signature(company, title, location)` → `CanonicalJob.get_or_create`. If the row
   already existed, the response shows a **"seen before"** notice with the posting count.
4. `JobPosting.update_or_create(url=...)`. Re-pasting a URL refreshes the existing posting.
5. `tailor_resume(profile, posting)`. A `TailoringError` becomes an inline error.
6. Create a `TailoredResume` and return the `_tailor_result.html` partial.

`tailor` and `mark_applied` accept only POST (`@require_POST`); a GET returns 405.

**Auth.** `LoginRequiredMiddleware` protects every view, including PDF download. Logged-out
visitors are redirected to the admin login page (`LOGIN_URL = "admin:login"`); log in as
the superuser. The nav has a Log out button that POSTs to `admin:logout`.

Other routes (`tracker/urls.py`):

| Route | View | Notes |
|---|---|---|
| `/` | `dashboard` | Paste form + 10 most recent tailorings |
| `/applied/` | `applied` | Applications, newest first (read-only list) |
| `/tailored/` | `tailored` | All tailorings, with an `is_applied` flag |
| `/tailored/<pk>/apply/` | `mark_applied` | Idempotently creates an `Application`; returns the row partial |
| `/tailored/<pk>/pdf/` | `pdf_download` | Renders and returns `resume-<pk>.pdf` |
| `/admin/` | Django admin | All models registered |

`scrape` and `tailor_resume` are imported into `tracker.views` at module level so tests can
monkeypatch them there.

## Dedup signature (`tracker/signatures.py`)

`signature(company, title, location="")`:
1. Lowercase each field, replace punctuation with spaces, and collapse whitespace.
2. Company: repeatedly strip trailing legal suffixes (`inc`, `ltd`, `llc`, `gmbh`,
   `sp z o o`, `s a`, `corp`, …).
3. Title: map `sr` → `senior` and `jr` → `junior`.
4. Return `sha256("company|title|location")` as hex.

The match is exact on the normalized text, with no fuzzy or semantic matching. Two boards
that format the location differently (for example "Warsaw" vs "Warsaw, Poland") produce
different signatures.

## Scraping (`tracker/scraping.py`)

`scrape(url) = extract(fetch_html(url), url)`.

- **`fetch_html`** is the only network code. It uses sync Playwright with headless
  Chromium, a desktop Chrome user agent, `wait_until="domcontentloaded"` and a 30 s
  timeout.
- **`extract`** is pure and tested against fixtures in `tests/fixtures/`.
  1. It walks every `application/ld+json` block (flattening lists and `@graph`) to find a
     `JobPosting` node, and reads `title`, `hiringOrganization.name`,
     `jobLocation.address` and `description` (HTML is converted to plain text).
  2. Fallbacks: `og:title` or `<title>` for the title, and `meta description` or
     `og:description` for the description. Company and location have no fallback.
- **`detect_board`** maps a host to a slug: linkedin, greenhouse, lever, justjoin,
  nofluffjobs, pracuj, otherwise `generic`. The slug is a label only; there are no
  per-board selectors yet.

## AI tailoring (`tailoring/ai.py`)

**Contract.** This is the PDF template's only input besides the fixed `Profile`:

```json
{
  "about": "…",
  "experiences": [{"company": "…", "period": "…", "desc": "…"}],
  "skills":      [{"category": "…", "items": ["…"]}],
  "projects":    [{"name": "…", "tech": ["…"], "desc": "…"}]
}
```

The pydantic model `TailoredResumeSchema` mirrors this shape exactly.
`tailoring.pdf.master_content(profile)` projects the master data into the same shape.

**Call.** `_complete()` calls `client.chat.completions.parse(model="gpt-4.1",
response_format=TailoredResumeSchema)` using OpenAI Structured Outputs, so the schema is
enforced by the API. The user message contains the master JSON, the posting's title,
company and description, and the rules. The model may rewrite prose and filter or reorder
skills and projects, but must not change or invent any fact.

**Errors and fallback.**
- *Hard failures* raise `TailoringError`: an OpenAI or network error, a pydantic
  `ValidationError`, a refusal, or no parsed output. The view shows the error message.
- The **subset guard** (`_guard_violation`) rejects the output if:
  - any `(company, period)` pair is not in the master,
  - a skill category is unknown, or a category contains an item not in the master,
  - a project name is unknown, or a project lists tech the master doesn't have for it.

  On a violation the guard logs a warning and returns the **untailored master** instead.

## PDF rendering (`tailoring/pdf.py`)

- `pdf_template.html` is a port of `printable_resume/` and is fully self-contained: CSS,
  icons and the Inter font are inlined. The font comes from
  `tracker/static/resume/fonts/*.woff2`, base64-encoded and cached. Chromium therefore
  needs no network access. The fixed header and footer come from `Profile`; the About,
  Experience, Skills and Projects sections loop over `content`.
- `_html_to_pdf` renders in five steps:
  1. `set_content`.
  2. Emulate `print` media.
  3. Set the viewport to the A4 width (794 px).
  4. Measure `scrollHeight`.
  5. Call `page.pdf(format="A4", margin=0, scale=s)`.
- **Auto-shrink:** `s = clamp(2 pages × 1122.5px × 0.92 / height, 0.75, 1.0)`. Short
  resumes render at 100%. Long ones shrink to fit 2 pages but never below 75%; past that
  point they spill onto a third page.
- Entry points: `render_pdf(tailored_resume)`, `render_master_pdf(profile)`, and the CLI
  command `render_resume_pdf --out f.pdf [--tailored <pk>]`.

## Configuration (`config/settings.py`)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | **required** | Neon pooled URL. Startup fails fast if it is unset; there is deliberately no SQLite fallback. |
| `SECRET_KEY` | insecure dev value | Always set it in production. |
| `DEBUG` | `False` | |
| `OPENAI_API_KEY` | `""` | Read by the OpenAI SDK from the environment. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,.run.app` | |
| `CSRF_TRUSTED_ORIGINS` | `https://*.run.app` | |

Two settings are hard-coded:
- **Neon pooler.** PgBouncer runs in transaction mode, so the settings disable psycopg3
  prepared statements (`OPTIONS.prepare_threshold=None`) and set
  `DISABLE_SERVER_SIDE_CURSORS=True`. Without these, `migrate` works but pooled runtime
  queries return 500.
- **Cloud Run.** `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto` so that CSRF origin
  checks pass behind the TLS proxy.

Static files are served by WhiteNoise (`CompressedManifestStaticFilesStorage`). The
frontend loads Tailwind from the Play CDN and HTMX 2.0 from unpkg. HTMX sends the CSRF
token through `hx-headers` on `<body>`.

## Testing

- `pytest` with `pytest-django`. View tests use the `admin_client` fixture (a logged-in
  superuser); `client` is used to check that logged-out requests are redirected. Tests run against the **Neon** test DB with `--reuse-db`.
  After any model change, run `pytest --create-db` once.
- Tests never call OpenAI or the network. Monkeypatch `tailoring.ai._complete`,
  `tracker.views.scrape` and `tracker.views.tailor_resume`.
- `tests/test_pdf.py` covers template rendering and the scaling math. The two tests that
  produce real PDF bytes are skipped unless Chromium can launch (it needs
  `playwright install chromium` plus the system libraries from `playwright install-deps`).

## Deployment

The `Dockerfile` builds on `mcr.microsoft.com/playwright/python:v1.63.0-noble`, which has
Chromium preinstalled for both scraping and PDFs. On start the container runs `migrate`,
then `collectstatic`, then `gunicorn config.wsgi` on `$PORT` (8080). It is meant to run on
Cloud Run with `DATABASE_URL`, `SECRET_KEY` and `OPENAI_API_KEY` supplied as env vars or
from Secret Manager.

The image tag must match the `playwright==` pin in `requirements.txt`. If they differ, the
package looks for a Chromium build the image doesn't have. Bump both together.

Before deploying, read the "Known gaps" section of the active plan.
