# MAI MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP for `mai.tarko.su`: daily Gosuslugi MAI import, precomputed admission metrics, public search dashboard, permanent search logs, rate limiting, and VPS deployment templates.

**Architecture:** FastAPI serves API and static frontend locally; PostgreSQL is production storage with SQLite allowed for local development/tests. A worker command imports Gosuslugi data and precomputes metrics; public search only reads stored data.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, requests, pytest, vanilla HTML/CSS/JS, nginx/systemd templates.

---

### Task 1: Project Skeleton

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/main.py`
- Create: `backend/__init__.py`
- Create: `tests/conftest.py`

- [ ] Add dependencies: FastAPI, uvicorn, SQLAlchemy, requests, psycopg, pytest.
- [ ] Add settings loaded from environment with safe local defaults.
- [ ] Add SQLAlchemy engine/session helpers.
- [ ] Add FastAPI app factory and schema creation.
- [ ] Write pytest fixtures for isolated SQLite DB.
- [ ] Run `pytest` and confirm empty baseline works.

### Task 2: Models And Metrics

**Files:**
- Create: `backend/models.py`
- Create: `backend/services/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] Write tests for deferred-acceptance cascade.
- [ ] Write tests for consent rank and real competitor rank.
- [ ] Implement ORM tables from the design spec.
- [ ] Implement metric computation for one snapshot.
- [ ] Run metric tests.

### Task 3: Gosuslugi Import Worker

**Files:**
- Create: `backend/services/gosuslugi.py`
- Create: `backend/services/importer.py`
- Create: `backend/worker.py`
- Create: `tests/test_gosuslugi.py`
- Create: `tests/test_importer.py`

- [ ] Write tests for selecting full-time budget MAI groups.
- [ ] Write tests for applicant row normalization.
- [ ] Implement Gosuslugi client using public 2026 endpoints.
- [ ] Implement importer that stores compressed raw JSON outside git, normalizes rows, computes metrics, and records snapshot status.
- [ ] Add CLI entrypoint `python -m backend.worker import`.
- [ ] Run importer tests.

### Task 4: Public API, Logs, Rate Limits

**Files:**
- Create: `backend/services/search.py`
- Modify: `backend/main.py`
- Create: `tests/test_api.py`

- [ ] Write tests for successful search.
- [ ] Write tests for not-found search logging.
- [ ] Write tests for distinct-number rate limiting.
- [ ] Implement `POST /api/search`, `GET /api/status`, `GET /api/health`, `GET /api/ready`.
- [ ] Store permanent search logs.
- [ ] Run API tests.

### Task 5: Frontend Dashboard

**Files:**
- Create: `site/index.html`
- Create: `site/app.js`
- Create: `site/styles.css`

- [ ] Build first-screen search, not a landing page.
- [ ] Render main answer, directions, deadline-aware forecast block, history, and error/rate-limit states.
- [ ] Avoid internal terms and the word `пока` in UI copy.
- [ ] Use `POST /api/search`; never put application number in URL.
- [ ] Add optional Yandex Metrika hook without a hardcoded counter id.

### Task 6: Deployment Templates

**Files:**
- Create: `deploy/nginx/mai-tarko.conf`
- Create: `deploy/systemd/mai-backend.service`
- Create: `deploy/systemd/mai-worker.service`
- Create: `deploy/systemd/mai-worker.timer`
- Create: `.env.example`
- Create: `README.md`

- [ ] Add nginx config with `limit_conn`, `limit_req`, proxy timeouts, and separate logs.
- [ ] Add systemd backend service template.
- [ ] Add systemd worker/timer templates.
- [ ] Add `.env.example` without secrets.
- [ ] Add README with local run and VPS notes.

### Task 7: Verification

**Files:**
- Modify as needed only for fixes.

- [ ] Run `pytest`.
- [ ] Run a local API smoke test with synthetic data.
- [ ] Start local server.
- [ ] Confirm frontend loads from local URL.
- [ ] Run secret scan with `rg`.
- [ ] Commit working MVP.
