---
phase: 2
slug: freshdesk-i-o-layer-pipeline-backbone
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-01
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (uv-managed) |
| **Config file** | `pyproject.toml` — created in Wave 0 (02-01 Task 1) |
| **Quick run command** | `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds (mocked HTTP via respx; no network) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green + Freshdesk sandbox smoke test passes
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 02-01 | 0 | REP-05 | T-02-SC | Deps declared + pinned (slopcheck [OK]); secrets only via env | scaffold | `python -c "import tomllib; ..."` (pyproject parse) | ✅ W0 | ⬜ pending |
| 02-01-T2 | 02-01 | 0 | REP-05 | T-02-02 | UNIQUE idempotency index at DB level; SendMode default dry_run | scaffold | `python -c "...migration tables..."` (schema+config OK) | ✅ W0 | ⬜ pending |
| 02-01-T3 | 02-01 | 0 | REP-05 | — | 7 test files collect (no ImportError); RED-on-purpose | scaffold | `pytest tests/ --collect-only -q` | ✅ W0 | ⬜ pending |
| 02-02-T1 | 02-02 | 1 | REP-05 | — | Error taxonomy: transient vs fatal classification | unit | `pytest tests/test_client.py -x` | ✅ W0 | ⬜ pending |
| 02-02-T2 | 02-02 | 1 | REP-05 (crit #3) | T-02-19 | Reply/note into correct ticket; 429 honors Retry-After; fatal no-retry | integration | `pytest tests/test_client.py::test_retry_after tests/test_client.py::test_fatal_404_no_retry -x` | ✅ W0 | ⬜ pending |
| 02-03-T1 | 02-03 | 1 | REP-05 (crit #2) | T-02-07 | Resolve-then-enqueue: webhook + poller derive same key → dedup at insert | integration | `pytest tests/test_queue.py::test_enqueue_dedup tests/test_queue.py::test_idempotency -x` | ✅ W0 | ⬜ pending |
| 02-03-T2 | 02-03 | 1 | REP-05 | T-02-08, T-02-10 | SKIP LOCKED claim no double-claim; token finalize; stale recovery | integration | `pytest tests/test_queue.py::test_skip_locked_claim tests/test_queue.py::test_stale_claim_recovery -x` | ✅ W0 | ⬜ pending |
| 02-04-T1 | 02-04 | 2 | REP-05 (crit #4) | T-02-11, T-02-12 | Auto-reply / no-reply / sync-echo never triggers send; PII redacted before persist | unit | `pytest tests/test_loop_guard.py -x` | ✅ W0 | ⬜ pending |
| 02-04-T2 | 02-04 | 2 | REP-05 (crit #2) | T-02-12 | Worker uses real key (no re-key); dry-run no Freshdesk call; happy path exactly-once | integration | `pytest tests/test_queue.py::test_worker_happy_path_exactly_once tests/test_queue.py::test_send_dry_run -x` | ✅ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 2 | REP-05 (crit #4) | T-02-13 | D-07 sync-echo distinguishable on sandbox (source/actor default ships; checkpoint confirms) | smoke (manual) | `RUN_SANDBOX=1 python -c "...get_conversations..."` | ✅ W0 | ⬜ pending |
| 02-05-T1 | 02-05 | 2 | REP-05 (crit #1) | T-02-15 | Webhook HMAC verify before I/O; resolve real inbound id then enqueue | integration | `pytest tests/test_webhook.py -x` | ✅ W0 | ⬜ pending |
| 02-05-T2 | 02-05 | 2 | REP-05 (crit #1) | T-02-16 | Poller resolves SAME key as webhook → ON CONFLICT auto-dedup | integration | `pytest tests/test_poller.py -x` | ✅ W0 | ⬜ pending |
| 02-06-T1 | 02-06 | 3 | REP-05 (crit #3) | T-02-19, T-02-22 | Transient retry bounded → dead-letter + alert; fatal straight to DLQ; Retry-After honored; suppressed never DLQ | integration | `pytest tests/test_queue.py::test_transient_retries_then_dead_letter tests/test_queue.py::test_fatal_straight_to_dead_letter tests/test_queue.py::test_retry_after_honored -x` | ✅ W0 | ⬜ pending |
| 02-06-T2 | 02-06 | 3 | REP-05 | — | Entry point wires webhook + poller + worker + stale-recovery; no secret in startup log | smoke | `pytest tests/test_queue.py::test_main_wires_components -x` | ✅ W0 | ⬜ pending |
| 02-06-T3 | 02-06 | 3 | REP-05 (crit #2) | T-02-20, T-02-21 | Real `POST /reply` on sandbox (D-03); re-run (webhook+poller same resolved key) → no second send | smoke (manual) | `RUN_SANDBOX=1 pytest tests/test_e2e_sandbox.py -m sandbox -x` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. File Exists = scaffolded in Wave 0 (02-01 Task 3).*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — pytest config + dependency declarations (uv) — 02-01 T1
- [ ] `docker-compose.yml` — Postgres 16 (pgvector-ready) for local dev/test — 02-01 T2
- [ ] Alembic migration `0001` — `ticket_queue` (UNIQUE `idempotency_key`), `dead_letter`, `dry_run_log` — 02-01 T2
- [ ] `tests/conftest.py` — asyncpg pool fixtures, respx HTTP mocks, test DB setup, skip-sandbox-unless-RUN_SANDBOX — 02-01 T3
- [ ] `tests/test_client.py` — FreshdeskClient unit tests (respx mock) for REP-05
- [ ] `tests/test_queue.py` — resolve-then-enqueue dedup, idempotency, SKIP LOCKED, dead-letter, stale recovery, worker, send-mode
- [ ] `tests/test_webhook.py` — webhook HMAC verify + resolve + enqueue flow
- [ ] `tests/test_poller.py` — reconciliation poller: resolve same key as webhook, dedup, window advance (D-09)
- [ ] `tests/test_loop_guard.py` — RFC 3834 headers, sender patterns, source/actor + Selless-sync (D-06/D-07)
- [ ] `tests/test_e2e_sandbox.py` — real Freshdesk sandbox smoke tests (marked `sandbox`)
- [ ] spaCy model install: `python -m spacy download en_core_web_lg` (Presidio backend)

*All 7 test files (`test_client`, `test_queue`, `test_webhook`, `test_poller`, `test_loop_guard`, `test_e2e_sandbox`, + `conftest`) are scaffolded in 02-01 Task 3. Every `<automated>` verify across all plans references one of these files — no MISSING references remain.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real reply posts into a live sandbox ticket (D-03) | REP-05 (crit #2) | Requires a real Freshdesk sandbox account + live API key with reply scope; cannot run in CI | Flip send-mode to `live`, run `RUN_SANDBOX=1 pytest -m sandbox`, confirm reply appears on the target ticket and a re-run (webhook + poller resolve same key) does NOT post a second reply — 02-06 T3 |
| D-07 sync-echo distinguishability | REP-05 (crit #4) | Needs a real Selless→Freshdesk sync update to inspect `user_id`/`from_email` actually stamped | Trigger a Selless sync, `GET /tickets/{id}/conversations`, record whether source/actor distinguishes sync-origin; source/actor default already ships in code — if not distinguishable, activate marker/tag fallback (follow-up, does not block Wave 3) — 02-04 T3 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (every auto task maps to a scaffolded test file; 2 manual checkpoints documented above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only 02-04 T3 and 02-06 T3 are manual; each is preceded/followed by automated-verify tasks)
- [x] Wave 0 covers all MISSING references (all 7 test files scaffolded in 02-01 T3, including `test_poller.py`)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (~15s mocked suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready (planner-filled; awaiting execution)
