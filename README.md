# CareReady AI — Phase 1

CQC Compliance Intelligence for Supported Living — full-stack application.
Powered by Omfys Technologies.

This is the Phase 1 build following the POC concept note architecture:
FastAPI backend · SQL database (SQLite dev / PostgreSQL prod) · REST APIs ·
JWT authentication · AI services (Anthropic or Azure OpenAI) · web frontend.

## What's real in Phase 1 (vs the static beta)

- Real sign-in — JWT auth against seeded user accounts (4 roles)
- Live readiness engine — the 82% and every key-question score are computed
  from the database (evidence currency 40% · staff compliance 25% ·
  incidents 15% · actions 20%, weighted per key question), and recalculate
  instantly when data changes
- Evidence library — 493 seeded items; upload a real document and it is
  stored, auto-classified to a category and CQC key question, and the
  readiness scores move
- Compliance actions — update status from the UI; Well-led recalculates
- Mock CQC Inspection — answers are POSTed to the API; with an AI key set,
  a live LLM inspector assesses each answer; without one, a deterministic
  keyword engine takes over
- Evidence pack — generated server-side as a printable report (print → PDF)
- Per-location scoring, activity trail written on every change, alert
  read-state, role records

## Quick start (local)

    cp .env.example .env          # edit JWT_SECRET; add an AI key if you have one
    ./run-dev.sh                  # installs deps, seeds the DB, serves everything

Open http://localhost:8000 — the API serves the frontend too.

Sign in: kunle.adeyemi@ultrawell.co.uk / demo1234
Other seeded accounts (same password): admin@, compliance@, viewer@ultrawell.co.uk

## Docker

    cp .env.example .env
    docker compose up --build

## Deploying (careready.shajianandan.com)

Phase 1 needs a Python host (the beta's static hosting is no longer enough):

- **Railway / Render / Fly.io** (simplest): point at this repo, it detects the
  Dockerfile. Set env vars from .env.example. Add the custom domain
  careready.shajianandan.com in the platform dashboard + a CNAME in your DNS.
- **A VPS** (Hetzner/DigitalOcean, ~$6/mo): `docker compose up -d` behind
  Caddy or nginx for TLS.
- For production switch DATABASE_URL to PostgreSQL (add `psycopg2-binary`
  to requirements) and set a strong JWT_SECRET.

## Enabling live AI

Set either in .env:

    ANTHROPIC_API_KEY=sk-ant-...          # or
    AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_KEY=...

The mock-inspection card in the app shows which engine is active.
Keys live server-side only — never in the browser.

## Project layout

    backend/app/models.py   SQLAlchemy models (orgs, locations, users, staff,
                            service users, incidents, actions, evidence, trend,
                            activity, alerts)
    backend/app/core.py     Auth (PBKDF2 + JWT) · readiness scoring engine ·
                            AI service (LLM assess + fallback, doc classifier)
    backend/app/seed.py     UltraWell demo dataset (493 evidence items,
                            4 locations, 8 staff, 6 service users, ...)
    backend/app/main.py     API routes + static frontend serving
    frontend/index.html     Single-page app (same UI as the beta, now API-driven)

## Resetting demo data

Delete `backend/careready.db` (or the Docker volume) and restart — the seed
runs automatically on an empty database.
