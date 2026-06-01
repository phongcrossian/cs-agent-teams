---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "01"
subsystem: bootstrap
tags: [bootstrap, postgres, alembic, queue-schema, test-scaffolding, presidio, pydantic-settings]
dependency_graph:
  requires: []
  provides:
    - pyproject.toml with pinned deps + pytest config
    - schema `queue` with 4 tables (ticket_queue, dead_letter, dry_run_log, poller_checkpoint)
    - src/config.py Settings (SendMode, throttle config)
    - 7 RED test file scaffolds (29 tests collected)
    - src module stubs (freshdesk_io, work_queue, webhook, poller, guards)
  affects:
    - All Phase 2 plans (Wave 1+) import from src/* stubs
    - 02-02/02-03 (Wave 1): turn test_client + test_queue RED → GREEN
    - 02-04 (Wave 2): turn test_queue + test_loop_guard RED → GREEN
    - 02-05 (Wave 3): turn test_webhook + test_poller RED → GREEN
    - 02-06 (Wave 4): turn remaining test_queue + test_e2e_sandbox RED → GREEN
tech_stack:
  added:
    - fastapi==0.136.3
    - uvicorn==0.48.0
    - httpx==0.28.1
    - tenacity==9.1.4
    - asyncpg==0.31.0
    - sqlalchemy==2.0.50
    - alembic==1.18.4
    - pydantic==2.13.4
    - pydantic-settings>=2.0.0
    - presidio-analyzer==2.2.359 + presidio-anonymizer==2.2.362
    - python-dotenv==1.2.2
    - structlog==25.5.0
    - pytest==9.0.3 + pytest-asyncio + respx==0.23.1
    - spaCy en_core_web_lg (Presidio NER backend)
  patterns:
    - Postgres SKIP LOCKED queue pattern (schema `queue` isolated from `public`)
    - Alembic raw-SQL migration (no ORM declarative — queue patterns need raw SQL)
    - pydantic-settings Settings with secret redaction in __repr__
    - RED-on-purpose test scaffolding (pytest.fail not pytest.skip)
    - Single-source-of-truth should_suppress (guards module stub)
key_files:
  created:
    - pyproject.toml
    - .python-version
    - .env.example
    - README.md
    - src/__init__.py
    - src/config.py
    - src/freshdesk_io/__init__.py
    - src/work_queue/__init__.py
    - src/webhook/__init__.py
    - src/poller/__init__.py
    - src/guards/__init__.py
    - docker-compose.yml
    - alembic.ini
    - migrations/env.py
    - migrations/versions/0001_initial_queue_schema.py
    - tests/conftest.py
    - tests/test_client.py
    - tests/test_queue.py
    - tests/test_webhook.py
    - tests/test_poller.py
    - tests/test_loop_guard.py
    - tests/test_e2e_sandbox.py
    - tests/__init__.py
  modified:
    - .gitignore
decisions:
  - "schema `queue` isolates queue tables from `public` (Phase 3 pgvector) — intentional co-location choice per D-01"
  - "src/work_queue/ NOT src/queue/ — avoids shadowing stdlib queue module (fix review #10)"
  - "pip+venv fallback used (uv not in PATH on dev machine — per RESEARCH Environment Availability)"
  - "spaCy en_core_web_lg downloaded and verified (Presidio PII backend D-12)"
  - "SendMode.DRY_RUN as default — nothing posts to Freshdesk unless SEND_MODE=live (D-05)"
metrics:
  duration_minutes: ~25
  completed_date: "2026-06-01"
  tasks_completed: 3
  files_created: 23
---

# Phase 02 Plan 01: Bootstrap — Project Scaffold, Queue Schema, Test Scaffolding

Python greenfield project initialized with Postgres-backed queue schema and RED test scaffolds for all Phase 2 plans.

## What Was Built

**Task 1 — uv project scaffold + dependency declarations + pytest config**

- `pyproject.toml` declaring 13 runtime deps (fastapi, httpx, tenacity, asyncpg, sqlalchemy, alembic, pydantic, presidio-analyzer, presidio-anonymizer, python-dotenv, structlog, uvicorn, pydantic-settings) + 3 dev deps (pytest, pytest-asyncio, respx) at RESEARCH-verified versions
- `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `markers = ["sandbox: ..."]`
- `.python-version` = 3.14, `.env.example` with all required keys (incl. PER_TICKET_REPLY_THROTTLE_N + WINDOW), `README.md` with setup instructions
- `src/__init__.py` package root
- pip+venv fallback (uv not in PATH per RESEARCH § Environment Availability); spaCy `en_core_web_lg` downloaded and installed successfully

**Task 2 — docker-compose Postgres 16 + Alembic schema**

- `docker-compose.yml`: `pgvector/pgvector:pg16` with `pg_isready` healthcheck + named volume (Phase 3 pgvector-ready)
- `src/config.py`: `Settings` (pydantic-settings) with `SendMode` Enum (`DRY_RUN` default per D-05), `selless_sync_user_ids` CSV parser, `per_ticket_reply_throttle_n/window`; api_key + webhook_secret excluded from `__repr__` (CLAUDE.md secret rule)
- `migrations/env.py`: reads `DATABASE_URL` from `Settings` — no hardcode
- `migrations/versions/0001_initial_queue_schema.py`:
  - `CREATE SCHEMA queue` (fix review #6 — Phase 3 pgvector uses `public`)
  - `queue.ticket_queue` with `sent_at TIMESTAMPTZ` + `freshdesk_reply_id BIGINT` (fix #1 — exactly-once crash-window), `UNIQUE INDEX` on `idempotency_key` (D-02), partial index for pending scan
  - `queue.dead_letter` with `alerted BOOLEAN`
  - `queue.dry_run_log` with `inbound_msg_id + action` (D-05, 02-04 doc-drift note)
  - `queue.poller_checkpoint` single-row `id=1` seeded with `NOW() - 1 hour` (fix #3 — durable last_since)

**Task 3 — Test scaffolding (RED-on-purpose)**

- `tests/conftest.py`: asyncpg `db_pool` (session scope), `clean_db` (truncates + resets `poller_checkpoint`), `respx_mock` (Freshdesk base URL); `pytest_collection_modifyitems` skips `sandbox` unless `RUN_SANDBOX=1`
- 7 test file scaffolds (29 tests total, 0 import errors, 0 collection errors):
  - `test_client.py` (5 tests): incl. `test_list_updated_tickets` (fix #2 MANDATORY)
  - `test_queue.py` (9 tests): incl. `test_worker_crash_after_post_does_not_resend` (fix #1 MANDATORY), `test_loop_guard_throttle` (fix #4), `test_sweep_exhausted_unlettered` (fix #9), `test_worker_recheck_routes_stale_inbound`
  - `test_webhook.py` (3 tests): HMAC verify + enqueue flow
  - `test_poller.py` (4 tests): incl. `test_poller_window_persists_across_restart` (fix #3 MANDATORY)
  - `test_loop_guard.py` (6 tests): incl. `test_resolve_uses_should_suppress` (fix #4)
  - `test_e2e_sandbox.py` (2 tests): `@pytest.mark.sandbox` smoke tests
- Module stubs (all importable): `src/freshdesk_io/`, `src/work_queue/` (NOT `src/queue/` — fix #10), `src/webhook/`, `src/poller/`, `src/guards/`

## Verification Results

| Check | Result |
|-------|--------|
| `python -c "import tomllib; ..."` pyproject parse | OK |
| `migration file` — ticket_queue + dead_letter + dry_run_log + poller_checkpoint + sent_at + freshdesk_reply_id + schema queue | OK |
| `pytest --collect-only` — 29 tests, 0 errors | OK |
| `test_list_updated_tickets` present | OK |
| `test_worker_crash_after_post_does_not_resend` present | OK |
| `test_poller_window_persists_across_restart` present | OK |
| `spacy download en_core_web_lg` | OK (3.8.0) |

## Deviations from Plan

### Auto-applied Adjustments

**1. [Rule 3 - Blocking] pip+venv used instead of uv**
- **Found during:** Task 1
- **Issue:** `uv` not found in PATH (per RESEARCH § Environment Availability)
- **Fix:** Created `.venv` with `python3 -m venv .venv && pip install -e ".[dev]"`. Documented in README with uv install command for future use.
- **Files modified:** README.md (documented both uv and pip fallback)

**2. [Plan clarification] tests/__init__.py added**
- **Found during:** Task 3
- **Issue:** Without `tests/__init__.py`, pytest module discovery can conflict with `src/` in some configurations.
- **Fix:** Added empty `tests/__init__.py`

None — plan executed with only the two minor adjustments above.

## Known Stubs

All stubs are intentional Wave 0 scaffolds. Each raises `NotImplementedError` (not silent empty implementations):

| File | Stub | Resolved in |
|------|------|-------------|
| `src/freshdesk_io/__init__.py` | `FreshdeskClient.post_reply/post_note/list_updated_tickets` | 02-02 (Wave 1) |
| `src/work_queue/__init__.py` | `enqueue`, `claim` | 02-03 (Wave 1) |
| `src/webhook/__init__.py` | `verify_signature` | 02-05 (Wave 3) |
| `src/poller/__init__.py` | `reconcile_once`, `load_checkpoint`, `save_checkpoint` | 02-05 (Wave 3) |
| `src/guards/__init__.py` | `should_suppress` | 02-04 (Wave 2) |

## Self-Check

### Created files exist

- pyproject.toml: found
- src/config.py: found
- migrations/versions/0001_initial_queue_schema.py: found
- tests/conftest.py: found
- tests/test_client.py: found
- tests/test_queue.py: found
- tests/test_webhook.py: found
- tests/test_poller.py: found
- tests/test_loop_guard.py: found
- tests/test_e2e_sandbox.py: found

### Commits exist

- 12695e1: chore(02-01): uv project scaffold + dependency declarations + pytest config
- 1a7a984: feat(02-01): Postgres 16 docker-compose + Alembic schema (queue: 4 tables)
- 1d332d1: test(02-01): test scaffolding — conftest + 7 RED test files + module stubs

## Self-Check: PASSED
