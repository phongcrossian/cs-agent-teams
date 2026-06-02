---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
plan: "00"
subsystem: grounding-bootstrap
tags: [pgvector, fastmcp, voyageai, alembic, migrations, test-scaffolding, config]
dependency_graph:
  requires: [02-06]
  provides: [knowledge-schema, audit-schema, phase3-settings, phase3-test-stubs]
  affects: [03-01, 03-02, 03-03, 03-04]
tech_stack:
  added: [fastmcp==3.3.1, voyageai==0.3.7, pgvector==0.4.2, mcp==1.27.2]
  patterns: [alembic-op-execute, asyncpg-pool-init-codec, pydantic-settings-extend-in-place]
key_files:
  created:
    - migrations/versions/0002_knowledge_schema.py
    - migrations/versions/0003_selless_audit.py
    - tests/ingest/__init__.py
    - tests/ingest/test_pipeline.py
    - tests/ingest/test_idempotent.py
    - tests/knowledge_mcp/__init__.py
    - tests/knowledge_mcp/test_semantic.py
    - tests/knowledge_mcp/test_exact.py
    - tests/knowledge_mcp/test_conflict.py
    - tests/knowledge_mcp/test_override.py
    - tests/selless_mcp/__init__.py
    - tests/selless_mcp/test_tools.py
    - tests/selless_mcp/test_resolve_scope.py
    - tests/selless_mcp/test_whitelist.py
    - tests/selless_mcp/test_audit.py
    - tests/selless_mcp/test_rate_limit.py
    - tests/smoke/__init__.py
    - tests/smoke/test_grounding_demo.py
  modified:
    - pyproject.toml
    - src/config.py
    - tests/conftest.py
decisions:
  - "voyageai==0.3.7 installed with --ignore-requires-python (Python 3.14 > declared <3.14 cap; imports and works correctly)"
  - "Migrations run against the project's intended Docker DB (pgvector/pgvector:pg16, csbot=superuser, pgvector pre-baked) — not a local Homebrew pg where csbot lacks superuser to CREATE the untrusted 'vector' extension"
  - "register_vector wrapped in try/except to avoid Phase-2 regression when vector extension not yet installed"
  - "uv not present in PATH; pip install against .venv used instead; pyproject.toml updated manually"
metrics:
  duration: "~35 minutes"
  completed_date: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 18
  files_modified: 3
---

# Phase 03 Plan 00: Wave 0 Bootstrap Summary

**One-liner:** FastMCP/Voyage/pgvector installed, knowledge+audit schema migrations created, Settings extended with 7 Phase-3 config fields, and 12 RED test stubs scaffolded for Plans 01-04.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 | Supply-chain gate | Pre-approved by orchestrator | — |
| 1 | Install deps + extend Settings | 9608176 | pyproject.toml, src/config.py |
| 2 | Alembic migrations 0002 + 0003 | cfdc845 | migrations/versions/0002_knowledge_schema.py, 0003_selless_audit.py |
| 3 | Test scaffolding — RED stubs + conftest fixtures | c5048c7 | tests/conftest.py + 17 new files |

## What Was Built

### Task 1 — Dependencies + Settings
- `fastmcp==3.3.1`, `mcp==1.27.2` (v1.x, CLAUDE.md-compliant), `pgvector==0.4.2`, `voyageai==0.3.7` installed into `.venv`
- `src/config.py` extended in-place with 7 new fields: `selless_api_base_url` (confirmed gateway-trust URL), `selless_api_gateway_key` (REDACTED), `voyage_api_key` (REDACTED), `voyage_model` ("voyage-3-large"), `voyage_output_dimension` (1024), `selless_rate_limit_rps` (1.0), `selless_rate_limit_burst` (10)
- `__repr__` updated to redact both new secrets (T-03-00-ID mitigation)
- Verification: `python -c "import fastmcp, voyageai, mcp, pgvector; from src.config import settings; ..."` prints OK

### Task 2 — Alembic Migrations
- `migrations/versions/0002_knowledge_schema.py`: revision "0002", down_revision "0001"
  - `CREATE EXTENSION IF NOT EXISTS vector` + `pg_trgm`
  - `knowledge.kb_chunk`: VECTOR(1024), GENERATED TSVECTOR, HNSW (m=16, ef_construction=64), GIN FTS, GIN trgm, UNIQUE on content_hash
  - `knowledge.policy_threshold`, `knowledge.code_map`, `knowledge.template_library`, `knowledge.policy_resolution`
  - `downgrade()` drops all in reverse order
- `migrations/versions/0003_selless_audit.py`: revision "0003", down_revision "0002"
  - `audit.selless_audit`: PII-redacted audit trail (SEL-04/D-07)
  - Index on (tool, created_at)
- **`alembic upgrade head` applied** (chain 0001→0002→0003) against the Docker `pgvector/pgvector:pg16` stack — all 6 tables queryable, `vector`+`pg_trgm` present, vector codec round-trip confirmed. See Resolved Issues below for how the DB-environment blocker was cleared.

### Task 3 — Test Scaffolding
- `tests/conftest.py` extended: `db_pool` now registers pgvector codec via `init=_init_conn` (graceful skip if extension absent); 4 new fixtures: `mock_selless_client`, `stub_embedder`, `clean_knowledge_db`, `selless_respx_mock`
- 4 package `__init__.py` files created
- 12 RED stub test files created (imports not-yet-existing Phase-3 src modules)
- Phase-2 tests (25/25) remain GREEN after conftest edits

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv not in PATH — used pip install against .venv instead**
- **Found during:** Task 1
- **Issue:** `uv` command not found in shell PATH; plan said `uv add fastmcp voyageai pgvector`
- **Fix:** Used `pip install` directly against `.venv/bin/pip` (the project's existing venv at `.venv/`)
- **Files modified:** pyproject.toml updated manually to add deps
- **Commit:** 9608176

**2. [Rule 1 - Bug] voyageai Python cap: `<3.14` blocks version 0.3.7 resolver**
- **Found during:** Task 1
- **Issue:** `voyageai` 0.3.7 declares `requires-python >=3.9,<3.14`; this repo is Python 3.14.5 — resolver returned 0.3.0rc0 as latest compatible
- **Fix:** Installed `voyageai==0.3.7` with `--ignore-requires-python` flag after verifying it imports correctly under Python 3.14 (`import voyageai; voyageai.Client` succeeds)
- **Files modified:** pyproject.toml pinned to `voyageai==0.3.7`
- **Commit:** 9608176

**3. [Rule 1 - Bug] register_vector caused Phase-2 test regression**
- **Found during:** Task 3 verification
- **Issue:** Adding `init=_init_conn` with `register_vector` to db_pool caused `ValueError: unknown type: public.vector` on Phase-2 tests (extension not yet in DB)
- **Fix:** Wrapped `register_vector` in `try/except Exception: pass` — gracefully skips when vector extension absent, works correctly when present
- **Files modified:** tests/conftest.py
- **Commit:** c5048c7

### Resolved Issues

**DB-environment blocker — alembic upgrade head (RESOLVED during Wave 0 orchestration)**

The executor initially reported `alembic upgrade head` as blocked and mis-diagnosed the cause as "Homebrew pgvector 0.8.2 ships no pg16 bottle, must build from source." That diagnosis was wrong.

- **Actual root cause:** The Postgres answering on `localhost:5432` was a *local Homebrew* `postgresql@16` instance, in which `csbot` is an ordinary (non-superuser) application role. `vector` is an **untrusted** extension, so `CREATE EXTENSION vector` requires superuser — hence `InsufficientPrivilegeError: permission denied to create extension "vector"`. pgvector itself was present in `pg_available_extensions`; nothing needed to be built from source. The project's *intended* database is the `pgvector/pgvector:pg16` Docker image declared in `docker-compose.yml` (where `csbot` is the container superuser and pgvector is pre-baked) — that container simply was not running.
- **Resolution (orchestrator, user chose the Docker path):**
  1. Installed a container runtime: `brew install colima docker docker-compose`; `colima start`.
  2. Gracefully stopped the local Homebrew pg via `pg_ctl -D /opt/homebrew/var/postgresql@16 stop -m fast` (data dir preserved — restartable) to free port 5432.
  3. `docker-compose up -d postgres` → `pgvector/pgvector:pg16` healthy.
  4. `alembic upgrade head` → chain 0001→0002→0003 applied cleanly.
- **Verification:** all 6 tables (`knowledge.kb_chunk`, `policy_threshold`, `code_map`, `template_library`, `policy_resolution`, `audit.selless_audit`) queryable; `vector` + `pg_trgm` present in `pg_extension`; `alembic_version = 0003`; a vector round-trip through `knowledge.kb_chunk.embedding` returned a 1024-dim ndarray (pgvector asyncpg codec confirmed working).

**Follow-up (non-blocking, for Plans 01/02):** the conftest `register_vector` wrapper still swallows all exceptions (`except Exception: pass`). Now that pgvector is present this succeeds, but Plans 01/02 (which add vector-dependent tests) should tighten it to fail loudly if codec registration ever fails, so a broken vector fixture can't pass silently.

**Impact:** Plans 01-04 that write/read vector columns require the extension to be installed. Mock-backed unit tests (RED stubs) do not require the extension — they fail RED on import errors (correct for TDD scaffolding), not DB errors.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: supply_chain | .venv/lib/.../voyageai | voyageai 0.3.7 installed with --ignore-requires-python; imports verified OK under Python 3.14 but outside declared support range |

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| All 12 test files | tests/ingest/*, tests/knowledge_mcp/*, tests/selless_mcp/*, tests/smoke/* | Intentional RED stubs — src/ Phase-3 modules created in Plans 01-03 |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| migrations/versions/0002_knowledge_schema.py | FOUND |
| migrations/versions/0003_selless_audit.py | FOUND |
| src/config.py | FOUND |
| tests/conftest.py | FOUND |
| tests/ingest/test_pipeline.py | FOUND |
| tests/knowledge_mcp/test_semantic.py | FOUND |
| tests/selless_mcp/test_tools.py | FOUND |
| tests/smoke/test_grounding_demo.py | FOUND |
| commit 9608176 (Task 1) | FOUND |
| commit cfdc845 (Task 2) | FOUND |
| commit c5048c7 (Task 3) | FOUND |

**Note:** `alembic upgrade head` was applied and fully verified against the Docker `pgvector/pgvector:pg16` stack (chain 0001→0002→0003; all 6 tables queryable; `vector`+`pg_trgm` present; vector codec round-trip confirmed). See Resolved Issues for how the DB-environment blocker was cleared.
