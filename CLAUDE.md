# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Status: project not yet scaffolded. This file currently records working preferences and
> conventions. Commands and detailed architecture will be filled in during implementation
> (see the approved plan in `dev/`).

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
