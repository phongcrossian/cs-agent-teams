---
phase: 2
slug: freshdesk-i-o-layer-pipeline-backbone
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-01
revised: 2026-06-01  # cross-AI review revision (REVIEWS.md): exactly-once crash-window, poller checkpoint, list_updated_tickets, unified loop-guard
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` § Validation Architecture.
> Revised to fold in `02-REVIEWS.md` consensus: 3 mandatory new RED tests + 4 recommended RED tests.

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

## Wave Structure (revised)

Adding the unified `should_suppress` single-source-of-truth (review fix #4) makes the poller resolve step depend on the loop-guard built in 02-04. The DAG stays acyclic; the phase is now 5 waves (0–4):

| Wave | Plans | Note |
|------|-------|------|
| 0 | 02-01 | Bootstrap + schema (+sent_at/freshdesk_reply_id, poller_checkpoint, `queue` schema) + test scaffolds |
| 1 | 02-02, 02-03 | Client (+list_updated_tickets/Ticket) ‖ queue core (parallel, no file overlap) |
| 2 | 02-04 | Worker + loop-guard (should_suppress) + send-intent + DeadLetterSink protocol |
| 3 | 02-05 | Webhook + poller (resolve uses should_suppress; durable checkpoint) — depends 02-04 |
| 4 | 02-06 | Retry/dead-letter (PostgresDeadLetterSink) + sweeper + main.py + sandbox e2e |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 02-01 | 0 | REP-05 | T-02-SC | Deps declared + pinned (slopcheck [OK]); secrets only via env | scaffold | `python -c "import tomllib; ..."` (pyproject parse) | ✅ W0 | ⬜ pending |
| 02-01-T2 | 02-01 | 0 | REP-05 | T-02-02 | UNIQUE idempotency index; sent_at/freshdesk_reply_id; poller_checkpoint; `queue` schema; SendMode default dry_run | scaffold | `python -c "...migration tables+columns+schema..."` | ✅ W0 | ⬜ pending |
| 02-01-T3 | 02-01 | 0 | REP-05 | — | 7 test files collect (no ImportError); RED-on-purpose incl. 3 new mandatory RED tests | scaffold | `pytest tests/ --collect-only -q` (grep crash-after-post / poller-window / list_updated) | ✅ W0 | ⬜ pending |
| 02-02-T1 | 02-02 | 1 | REP-05 | — | Error taxonomy: 409→fatal (fix #5); Ticket model (fix #2) | unit | `pytest tests/test_client.py -x` | ✅ W0 | ⬜ pending |
| 02-02-T2 | 02-02 | 1 | REP-05 (crit #3) | T-02-19 | Reply/note correct ticket; 429 Retry-After; fatal(incl 409) no-retry; list_updated_tickets+pagination | integration | `pytest tests/test_client.py::test_retry_after tests/test_client.py::test_fatal_404_no_retry tests/test_client.py::test_list_updated_tickets -x` | ✅ W0 | ⬜ pending |
| 02-03-T1 | 02-03 | 1 | REP-05 (crit #2) | T-02-07 | Resolve-then-enqueue: same key → dedup at insert | integration | `pytest tests/test_queue.py::test_enqueue_dedup tests/test_queue.py::test_idempotency -x` | ✅ W0 | ⬜ pending |
| 02-03-T2 | 02-03 | 1 | REP-05 | T-02-08, T-02-10 | SKIP LOCKED claim (ORDER BY id ASC tiebreaker, fix #8); token finalize; stale recovery | integration | `pytest tests/test_queue.py::test_skip_locked_claim tests/test_queue.py::test_stale_claim_recovery -x` | ✅ W0 | ⬜ pending |
| 02-04-T1 | 02-04 | 2 | REP-05 (crit #4) | T-02-11, T-02-12 | should_suppress single source of truth + per-ticket throttle (fix #4); PII redacted before persist | unit | `pytest tests/test_loop_guard.py -x` | ✅ W0 | ⬜ pending |
| 02-04-T2 | 02-04 | 2 | REP-05 (crit #2) | T-02-12, T-02-23, T-02-24 | send-intent (sent_at) + pre-send guard → crash-after-post no resend (fix #1); stale_inbound observable (fix #4); dry-run no Freshdesk; happy path exactly-once | integration | `pytest tests/test_queue.py::test_worker_happy_path_exactly_once tests/test_queue.py::test_send_dry_run tests/test_queue.py::test_worker_crash_after_post_does_not_resend tests/test_queue.py::test_worker_recheck_routes_stale_inbound -x` | ✅ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 2 | REP-05 (crit #4) | T-02-13 | D-07 sync-echo + raw-header (A4) + 409 semantic verified on sandbox (default ships; checkpoint confirms) | smoke (manual) | `RUN_SANDBOX=1 python -c "...get_conversations..."` | ✅ W0 | ⬜ pending |
| 02-05-T1 | 02-05 | 3 | REP-05 (crit #1) | T-02-15 | Webhook HMAC verify before I/O; resolve real inbound id (via should_suppress) then enqueue | integration | `pytest tests/test_webhook.py -x` | ✅ W0 | ⬜ pending |
| 02-05-T2 | 02-05 | 3 | REP-05 (crit #1) | T-02-16, T-02-25 | Poller resolves SAME key (should_suppress) → ON CONFLICT dedup; durable checkpoint survives restart (fix #3) | integration | `pytest tests/test_poller.py -x` | ✅ W0 | ⬜ pending |
| 02-06-T1 | 02-06 | 4 | REP-05 (crit #3) | T-02-19, T-02-22 | Transient retry bounded → DLQ (PostgresDeadLetterSink fix #7); fatal(incl 409) straight to DLQ; Retry-After honored; suppressed/stale_inbound never DLQ; sweep exhausted (fix #9) | integration | `pytest tests/test_queue.py::test_transient_retries_then_dead_letter tests/test_queue.py::test_fatal_straight_to_dead_letter tests/test_queue.py::test_retry_after_honored tests/test_queue.py::test_sweep_exhausted_unlettered -x` | ✅ W0 | ⬜ pending |
| 02-06-T2 | 02-06 | 4 | REP-05 | — | Entry point wires webhook + poller + worker + stale-recovery + exhausted-sweeper; no secret in startup log | smoke | `pytest tests/test_queue.py::test_main_wires_components -x` | ✅ W0 | ⬜ pending |
| 02-06-T3 | 02-06 | 4 | REP-05 (crit #2) | T-02-20, T-02-21 | Real `POST /reply` on sandbox (D-03); re-run no second send; crash-after-post no resend (fix #1) | smoke (manual) | `RUN_SANDBOX=1 pytest tests/test_e2e_sandbox.py -m sandbox -x` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. File Exists = scaffolded in Wave 0 (02-01 Task 3).*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — pytest config + dependency declarations (uv) + per-ticket throttle config — 02-01 T1
- [ ] `docker-compose.yml` — Postgres 16 (pgvector-ready) for local dev/test — 02-01 T2
- [ ] Alembic migration `0001` — schema `queue`: `ticket_queue` (UNIQUE `idempotency_key`, **+sent_at TIMESTAMPTZ, +freshdesk_reply_id BIGINT**), `dead_letter`, `dry_run_log`, **`poller_checkpoint`** — 02-01 T2
- [ ] `tests/conftest.py` — asyncpg pool fixtures, respx HTTP mocks, test DB setup (truncate + reset poller_checkpoint), skip-sandbox-unless-RUN_SANDBOX — 02-01 T3
- [ ] `tests/test_client.py` — FreshdeskClient unit tests (respx) incl. **test_list_updated_tickets** (fix #2)
- [ ] `tests/test_queue.py` — dedup, idempotency, SKIP LOCKED, dead-letter, stale recovery, worker, send-mode, **test_worker_crash_after_post_does_not_resend** (fix #1), **test_loop_guard_throttle** (fix #4), **test_sweep_exhausted_unlettered** (fix #9), test_worker_recheck_routes_stale_inbound (fix #4)
- [ ] `tests/test_webhook.py` — webhook HMAC verify + resolve (should_suppress) + enqueue flow
- [ ] `tests/test_poller.py` — reconciliation poller: resolve same key, dedup, window advance, **test_poller_window_persists_across_restart** (fix #3)
- [ ] `tests/test_loop_guard.py` — RFC 3834 headers, sender patterns, source/actor + Selless-sync (D-06/D-07), **test_resolve_uses_should_suppress** (fix #4), test_worker_recheck stale_inbound seam
- [ ] `tests/test_e2e_sandbox.py` — real Freshdesk sandbox smoke tests (marked `sandbox`): real reply, retry-no-double-send, **crash-after-post-no-resend** (fix #1)
- [ ] spaCy model install: `python -m spacy download en_core_web_lg` (Presidio backend)

*All 7 test files (`test_client`, `test_queue`, `test_webhook`, `test_poller`, `test_loop_guard`, `test_e2e_sandbox`, + `conftest`) are scaffolded in 02-01 Task 3. Every `<automated>` verify across all plans references one of these files — no MISSING references remain.*

### New RED tests mandated by this revision (must be scaffolded RED in Wave 0)

| Test | File | Fix | Plan that turns it GREEN |
|------|------|-----|--------------------------|
| `test_worker_crash_after_post_does_not_resend` | test_queue.py | #1 (MANDATORY) | 02-04 T2 |
| `test_poller_window_persists_across_restart` | test_poller.py | #3 (MANDATORY) | 02-05 T2 |
| `test_list_updated_tickets` | test_client.py | #2 (MANDATORY) | 02-02 T2 |
| `test_resolve_uses_should_suppress` | test_loop_guard.py | #4 | 02-04 T1 |
| `test_worker_recheck_routes_stale_inbound` | test_queue.py / test_loop_guard.py | #4 | 02-04 T2 |
| `test_loop_guard_throttle` | test_queue.py | #4 | 02-04 T1 |
| `test_sweep_exhausted_unlettered` | test_queue.py | #9 | 02-06 T1 |

*Module note (fix #10): queue code lives in `src/work_queue/` (NOT `src/queue/`) to avoid shadowing the stdlib `queue` module.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real reply posts into a live sandbox ticket (D-03) | REP-05 (crit #2) | Requires real Freshdesk sandbox + live API key; cannot run in CI | Flip send-mode to `live`, run `RUN_SANDBOX=1 pytest -m sandbox`, confirm reply appears and re-run does NOT post a second reply — 02-06 T3 |
| Crash-after-post does not resend on real Freshdesk (fix #1) | REP-05 (crit #2) | Requires real sandbox to prove send-intent + pre-send guard hold the dual-write boundary | Simulate worker crash between POST 200 and finalize_done (row claimed + sent_at set), recover_stale_claims → re-claim → assert conversation count does NOT increase — 02-06 T3 |
| D-07 sync-echo distinguishability + raw-header (A4) + 409 semantic | REP-05 (crit #4) | Needs real Selless→Freshdesk sync + sandbox 409 to inspect actual fields | Trigger Selless sync, `GET /conversations`, record user_id/source + raw-header exposure + any 409 body; source/actor default + throttle already ship — if not distinguishable, activate marker/tag fallback (follow-up, does not block Wave 4) — 02-04 T3 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (every auto task maps to a scaffolded test file; 2 manual checkpoints documented above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only 02-04 T3 and 02-06 T3 are manual; each is preceded/followed by automated-verify tasks)
- [x] Wave 0 covers all MISSING references (all 7 test files scaffolded in 02-01 T3, including 3 mandatory + 4 recommended new RED tests)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (~15s mocked suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready (planner-filled; revised for REVIEWS.md; awaiting execution)
