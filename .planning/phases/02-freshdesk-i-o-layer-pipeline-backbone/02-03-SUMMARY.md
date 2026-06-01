---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "03"
subsystem: queue-core
tags: [postgres, skip-locked, idempotency, exactly-once, queue, wave-1]
dependency_graph:
  requires:
    - "02-01 (schema queue.ticket_queue, queue.dead_letter, queue.poller_checkpoint)"
    - "02-01 (conftest.py db_pool + clean_db fixtures)"
  provides:
    - "compute_idempotency_key(ticket_id, inbound_msg_id) -> str (D-02)"
    - "enqueue_ticket: INSERT ON CONFLICT (idempotency_key) DO NOTHING → bool"
    - "claim_one: FOR UPDATE SKIP LOCKED, ORDER BY next_attempt_at ASC, id ASC"
    - "finalize_done: token-checked done (stale worker protection)"
    - "finalize_retry: attempts++, backoff next_attempt_at, redacted last_error"
    - "recover_stale_claims: claimed > lease_minutes → pending (D-11)"
  affects:
    - "02-04 (Wave 2): worker uses enqueue_ticket + claim_one + finalize_* in the loop"
    - "02-05 (Wave 3): webhook + poller call enqueue_ticket with resolved inbound_msg_id"
    - "02-06 (Wave 4): dead-letter sweeper builds on claim/finalize primitives"
tech_stack:
  added: []
  patterns:
    - "INSERT ON CONFLICT (idempotency_key) DO NOTHING — dedup at insert, no read-then-write race"
    - "CTE + FOR UPDATE SKIP LOCKED — atomic claim, multi-worker safe"
    - "claim_token UUID — stale worker finalization guard"
    - "pytest-asyncio 1.4 function scope — asyncio_default_fixture_loop_scope=function"
    - "asyncpg JSONB — json.dumps() before $4::jsonb cast"
key_files:
  created:
    - src/work_queue/idempotency.py
    - src/work_queue/enqueue.py
    - src/work_queue/claim.py
  modified:
    - src/work_queue/__init__.py
    - tests/test_queue.py
    - tests/conftest.py
    - pyproject.toml
decisions:
  - "asyncio_default_fixture_loop_scope=function (not session) — pytest-asyncio 1.4 requires consistent loop scope between fixture and test; session pool attached to session loop crashed when test ran in function loop"
  - "enqueue_ticket rejects inbound_msg_id <= 0 (ValueError) — enforces resolve-then-enqueue contract (D-02); sentinels would break exactly-once guarantee"
  - "json.dumps() + $4::jsonb cast — asyncpg does not auto-serialize dict to JSONB; explicit string→jsonb required"
  - "db_pool fixture changed to function scope — avoids session/function loop mismatch; overhead is <5ms per test (small pool, local DB)"
metrics:
  duration_minutes: ~30
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_created: 3
  files_modified: 4
---

# Phase 02 Plan 03: Idempotent Postgres Queue Core (Wave 1)

Exactly-once queue core: idempotency key computation (D-02), dedup-at-insert via ON CONFLICT, SKIP LOCKED claim with deterministic ORDER BY (fix #8), token-checked finalization, and stale claim recovery (D-11).

## What Was Built

**Task 1 — Idempotency key + enqueue with dedup-at-insert**

- `src/work_queue/idempotency.py`: `compute_idempotency_key(ticket_id, inbound_msg_id) -> str`
  - Returns `f"{ticket_id}:{inbound_msg_id}"` — deterministic, same input = same output
  - Both webhook path and reconciliation poller derive the same key from the same ticket state (D-02 contract)
  - Docstring explicitly states: NOT webhook delivery ID, NOT content hash, NOT ticket ID alone
- `src/work_queue/enqueue.py`: `async enqueue_ticket(conn, ticket_id, inbound_msg_id, redacted_payload) -> bool`
  - `INSERT INTO queue.ticket_queue ... ON CONFLICT (idempotency_key) DO NOTHING`
  - Returns `True` (inserted) / `False` (duplicate — ON CONFLICT fired)
  - Sentinel guard: raises `ValueError` if `inbound_msg_id <= 0` (resolve-then-enqueue contract)
  - PII contract: persists whatever payload it receives — full Presidio wiring in plan 04
- `src/work_queue/__init__.py`: exports full public API + legacy `enqueue`/`claim` aliases for backward compatibility
- `tests/test_queue.py` (Task 1 tests turned GREEN):
  - `test_enqueue_dedup`: 2 enqueues with same key → 1 row, second returns False
  - `test_idempotency`: webhook path + poller path with same inbound_msg_id → 1 row (exactly-once REP-05 crit #2)

**Task 2 — SKIP LOCKED claim + finalize (done/retry) + stale claim recovery**

- `src/work_queue/claim.py`:
  - `claim_one(conn, worker_id)`: CTE + `FOR UPDATE SKIP LOCKED`, `ORDER BY next_attempt_at ASC, id ASC` (deterministic FIFO tiebreaker — fix review #8)
  - `finalize_done(conn, row_id, claim_token)`: token-checked (`WHERE claim_token=$2::uuid`) → `status='done'`; returns `False` on stale token (stale worker protection, T-02-08)
  - `finalize_retry(conn, row_id, claim_token, redacted_error, backoff_seconds)`: `attempts+1`, `next_attempt_at=NOW()+backoff`, stores redacted error (T-02-09 — no PII in last_error)
  - `recover_stale_claims(conn, lease_minutes=10)`: sweeps `status='claimed' AND claimed_at < NOW() - N minutes` → `'pending'`; returns recovered row count (D-11 / T-02-10)
- `tests/test_queue.py` (Task 2 tests turned GREEN):
  - `test_skip_locked_claim`: 2 concurrent workers claim different rows (asyncio.gather)
  - `test_finalize_done`: correct token → done; wrong token → False
  - `test_finalize_retry`: attempts+1, next_attempt_at future, last_error stored
  - `test_stale_claim_recovery`: stale row (15 min ago) → pending; active row (2 min ago) → stays claimed

## Verification Results

| Check | Result |
|-------|--------|
| `pytest test_enqueue_dedup test_idempotency` | 2 PASSED |
| `pytest test_skip_locked_claim test_finalize_done test_finalize_retry test_stale_claim_recovery` | 4 PASSED |
| `pytest tests/test_queue.py` (full file) | 6 PASSED, 5 FAILED (Wave 2/4 RED scaffolds — expected) |
| Wave 2/4 RED tests still fail with `pytest.fail()` | Confirmed — not regressed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest-asyncio 1.4 session/function loop scope mismatch**
- **Found during:** Task 1 (first test run)
- **Issue:** `db_pool` fixture was `scope="session"`, creating the asyncpg pool on the session event loop. Tests run with `asyncio_default_test_loop_scope=function` (per-test loop). asyncpg protocol futures attached to the session loop crashed when used from function loop: `RuntimeError: got Future attached to a different loop`.
- **Fix:** Changed `db_pool` fixture to function scope (no `scope=` argument) + set `asyncio_default_fixture_loop_scope = "function"` in `pyproject.toml`. This aligns all async fixtures with the per-test loop.
- **Impact:** Tiny overhead (~5ms per test, local DB, small pool). Acceptable for a test suite.
- **Files modified:** `tests/conftest.py`, `pyproject.toml`

**2. [Rule 1 - Bug] asyncpg JSONB requires json.dumps(), not raw dict**
- **Found during:** Task 1 (`test_enqueue_dedup` first run after loop fix)
- **Issue:** asyncpg raises `DataError: invalid input for query argument $4: {'subject': 'test'} (expected str, got dict)` when passing a Python dict for a JSONB column.
- **Fix:** Added `import json` + `payload_json = json.dumps(redacted_payload)` in `enqueue_ticket`; cast in SQL as `$4::jsonb`.
- **Files modified:** `src/work_queue/enqueue.py`

## Known Stubs

No stubs introduced. All functions are fully implemented. Wave 2/4 tests remain as intentional `pytest.fail()` scaffolds (not stubs in the implementation sense):

| File | Stub | Resolved in |
|------|------|-------------|
| `tests/test_queue.py` | `test_dead_letter_on_exhaustion` | 02-06 (Wave 4) |
| `tests/test_queue.py` | `test_worker_crash_after_post_does_not_resend` | 02-04 (Wave 2) |
| `tests/test_queue.py` | `test_loop_guard_throttle` | 02-04 (Wave 2) |
| `tests/test_queue.py` | `test_sweep_exhausted_unlettered` | 02-06 (Wave 4) |
| `tests/test_queue.py` | `test_worker_recheck_routes_stale_inbound` | 02-04 (Wave 2) |

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. All threat model mitigations from the plan are implemented:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-07 Tampering (duplicate-send) | UNIQUE index + ON CONFLICT DO NOTHING | Implemented in enqueue.py |
| T-02-08 Elevation/Race | FOR UPDATE SKIP LOCKED + claim_token guard | Implemented in claim.py |
| T-02-09 Information Disclosure (last_error PII) | finalize_retry accepts only pre-redacted string; docstring enforces contract | Implemented + test verifies |
| T-02-10 DoS (stuck queue) | recover_stale_claims + attempts < max_attempts | Implemented in claim.py |

## Self-Check

### Created files exist

- src/work_queue/idempotency.py: found
- src/work_queue/enqueue.py: found
- src/work_queue/claim.py: found

### Commits exist

- bd5ef5c: feat(02-03): idempotency key + enqueue with dedup-at-insert (Task 1)
- 1ee229c: feat(02-03): SKIP LOCKED claim + token finalization + stale recovery (Task 2)

## Self-Check: PASSED
