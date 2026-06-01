---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "06"
subsystem: queue
tags: [postgres, asyncpg, freshdesk, dead-letter, retry, exactly-once, observability, structlog]

requires:
  - phase: 02-freshdesk-i-o-layer-pipeline-backbone/02-01
    provides: queue schema (queue.ticket_queue, queue.dead_letter, queue.dry_run_log), DB migrations
  - phase: 02-freshdesk-i-o-layer-pipeline-backbone/02-02
    provides: FreshdeskClient (post_reply, get_conversations), error hierarchy (FreshdeskFatalError/TransientError/RateLimitError)
  - phase: 02-freshdesk-i-o-layer-pipeline-backbone/02-03
    provides: enqueue_ticket, claim_one, finalize_done, recover_stale_claims, claim/finalize protocol
  - phase: 02-freshdesk-i-o-layer-pipeline-backbone/02-04
    provides: process_queue_row, worker_loop, DeadLetterSink protocol, loop-guard, per-ticket throttle, send-intent (sent_at/freshdesk_reply_id)
  - phase: 02-freshdesk-i-o-layer-pipeline-backbone/02-05
    provides: poller_loop, durable checkpoint, resolve_inbound_and_enqueue, webhook receiver

provides:
  - PostgresDeadLetterSink (DeadLetterSink impl) — classifies fatal/transient errors, persists queue.dead_letter, emits alert
  - sweep_exhausted — catches pending-but-exhausted rows that bypass the normal dead-letter path (fix #9)
  - Bounded retry with Retry-After honor + exponential backoff+jitter (D-10, crit #3)
  - observability.py — structlog JSON renderer + in-memory metric counters (processed, suppressed, stale_inbound, dead_lettered, retries)
  - main.py — single process entry point: uvicorn webhook + poller_loop + worker_loop + stale-recovery + exhausted-sweeper concurrent
  - D-03 sandbox e2e demo — live proof of real post + exactly-once + crash-after-post-no-resend on shophelp-dev

affects:
  - Phase 3 (MCP/RAG): full pipeline backbone now running; Phase 3 adds AI classification + knowledge retrieval
  - Phase 5 (Eval): dead_letter + observability provide the error-rate signal for the eval harness
  - Phase 6 (Monitoring/kill-switch): main.py send_mode seam (D-05) is the Phase 6 kill-switch integration point
  - Phase 7 (Staged rollout): send_mode + worker_loop seam is the rollout-percentage integration point

tech-stack:
  added:
    - structlog (JSON structured logging, D-12)
    - PostgresDeadLetterSink (in-project impl of DeadLetterSink protocol)
  patterns:
    - Dead-letter sink protocol (inject at worker level; swap impl without touching worker logic)
    - sweep_exhausted as safety net for rows exhausted without being lettered (fix #9)
    - Retry-After honor: RateLimitError.retry_after → finalize_retry backoff_seconds (Pitfall 6)
    - main.py as single asyncio.gather entry point for webhook + poller + worker + schedulers
    - Observability-via-structlog: no PII in logs; metric counters as in-memory dict

key-files:
  created:
    - src/work_queue/dead_letter.py
    - src/observability.py
    - src/main.py
  modified:
    - src/work_queue/worker.py (inject PostgresDeadLetterSink, retry/DLQ wiring)
    - tests/test_queue.py (5 new dead-letter/retry/sweep tests + main wiring smoke)
    - tests/test_e2e_sandbox.py (aligned to marker-free verification via freshdesk_reply_id)

key-decisions:
  - "PostgresDeadLetterSink injected into worker via DeadLetterSink protocol (fix #7) — replaces RetryOnlyDeadLetterSink default from 02-04"
  - "409 stays FreshdeskFatalError → dead-letter immediately (fix #5); semantic reclassify deferred pending sandbox evidence"
  - "Freshdesk strips HTML comments from reply bodies (D-03 live finding, ticket 368108) — HTML-comment marker pre-send guard removed (commit 7fd7fab); exactly-once rests on idempotency key + skip-if-sent + token-checked write"
  - "Residual window (POST 200 but process dies before sent_at write commits) accepted as documented Phase-2 limitation — not mitigated further; Phase 6 kill-switch is the next control point"
  - "SELLESS_SYNC_USER_IDS carry-forward: must be populated with real Selless integration user_id from a live Selless→Freshdesk sync (config/data follow-up, not a code gate)"
  - "NoDecode on SELLESS_SYNC_USER_IDS .env parse — empty/CSV string handled without JSON decode error (commit 3327550)"
  - "Freshdesk domain normalization: .env had full domain with subdomain; double-append of .freshdesk.com caused SSL errors — client now strips trailing domain suffix (commit c7f6922)"

patterns-established:
  - "Dead-letter protocol: fatal error (401/403/404/400/409) → dead-letter immediately; transient (429/5xx/timeout) → retry with backoff; exhaustion → dead-letter + alert"
  - "sweep_exhausted: scheduled alongside recover_stale_claims (~10 min cadence) — catches rows exhausted without being dead-lettered"
  - "Observability no-PII: structlog events carry ticket_id/inbound_msg_id; raw ticket body/PII never logged (D-12)"
  - "Sandbox e2e verification: use freshdesk_reply_id (c.id == freshdesk_reply_id) not body content (Freshdesk strips HTML comments)"

requirements-completed: [REP-05]

duration: ~120min (Tasks 1-2 execution + D-03 live sandbox demo)
completed: "2026-06-01"
---

# Phase 02 Plan 06: Dead-Letter Hardening + main.py Entry Point + D-03 Sandbox E2E Demo Summary

**Bounded retry/dead-letter (PostgresDeadLetterSink), exhausted-row sweeper, structlog observability, single-process entry point (main.py), and live proof of exactly-once across crash on the Freshdesk sandbox (shophelp-dev, ticket 368108)**

## Performance

- **Duration:** ~120 min
- **Started:** 2026-06-01T~07:00Z
- **Completed:** 2026-06-01T09:25Z
- **Tasks:** 3 (Tasks 1-2 automated; Task 3 resolved by orchestrator via live sandbox demo)
- **Files modified:** 7

## Accomplishments

- PostgresDeadLetterSink + sweep_exhausted ship the final hardening for crit #3 (no silent drops): fatal errors dead-letter immediately; transient errors retry up to max_attempts with Retry-After honor then dead-letter; exhausted-but-pending rows swept by a scheduler every 10 min (fix #7, #9).
- main.py wires webhook (uvicorn) + poller_loop + worker_loop + recover_stale_claims + sweep_exhausted into a single async process (D-09, D-11); send_mode logged at startup, no secrets logged.
- D-03 live sandbox demo on shophelp-dev ticket 368108 confirmed all three exactly-once scenarios: real POST, duplicate-inbound rejection (ON CONFLICT DO NOTHING), and crash-after-post skip-if-sent path — all PASS.

## Task Commits

1. **Task 1: PostgresDeadLetterSink + sweep_exhausted + retry wiring** — `4b38098` (feat)
2. **Task 2: main.py entry point** — `eedebbf` (feat)
3. **Fix (NoDecode SELLESS_SYNC_USER_IDS)** — `3327550` (fix, found post-wave gate)
4. **Fix (Freshdesk domain double-append SSL)** — `c7f6922` (fix, found during D-03)
5. **Fix (remove HTML-comment marker pre-send guard)** — `7fd7fab` (fix, found during D-03)
6. **Task 3 / test alignment (marker-free sandbox tests)** — *(this commit)*

## Files Created/Modified

- `src/work_queue/dead_letter.py` — PostgresDeadLetterSink, should_dead_letter, sweep_exhausted
- `src/observability.py` — structlog JSON renderer, metric counters (processed/suppressed/stale_inbound/dead_lettered/retries), emit_alert
- `src/main.py` — single async entry point: uvicorn webhook + poller_loop + worker_loop + stale-recovery + exhausted-sweeper scheduler
- `src/work_queue/worker.py` — PostgresDeadLetterSink injected; fatal/transient/rate-limit routing; metric counter increments
- `src/work_queue/send.py` — HTML-comment marker pre-send guard removed (commit 7fd7fab); D-03 finding documented in module docstring
- `tests/test_queue.py` — 5 dead-letter/retry/sweep tests + test_main_wires_components smoke
- `tests/test_e2e_sandbox.py` — aligned to marker-free verification (freshdesk_reply_id-based)

## D-03 Live Sandbox Demo — Evidence

Run against shophelp-dev sandbox, ticket 368108. All three scenarios PASS:

**[A] Real reply posted:**
- DB row: status=done, sent_at IS NOT NULL, freshdesk_reply_id matched POST result
- GET /conversations confirmed the reply appeared in conversation history
- Proves: AI can post an approved reply into the correct existing ticket via Freshdesk API

**[B] Duplicate inbound — exactly-once:**
- Second enqueue_ticket with same inbound_msg_id returned False (ON CONFLICT DO NOTHING)
- No second reply posted; conversation count stable
- Proves: REP-05 crit #2 exactly-once at the enqueue layer

**[C] Crash-after-post — skip-if-sent:**
- send_reply called (real POST 200); finalize_done NOT called (crash simulated)
- claimed_at forced stale → recover_stale_claims=1
- Second worker claimed row; process_queue_row saw sent_at IS NOT NULL → SKIPPED POST → status=done
- Exactly 1 reply in Freshdesk (not 2)
- Proves: fix #1 (send-intent transactional write + process_queue_row skip-if-sent) works across crash

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] NoDecode on SELLESS_SYNC_USER_IDS env parse**
- **Found during:** Post-wave gate (after Task 2 commit)
- **Issue:** Empty or CSV string in .env caused JSON decode error on startup
- **Fix:** Applied NoDecode validator so Settings accepts raw string; parse to set manually
- **Files modified:** `src/config.py`
- **Committed in:** `3327550`

**2. [Rule 1 - Bug] Freshdesk domain double-append SSL error**
- **Found during:** D-03 sandbox demo setup
- **Issue:** .env FRESHDESK_DOMAIN contained full subdomain (e.g., `shophelp-dev.freshdesk.com`); FreshdeskClient appended `.freshdesk.com` again → SSL handshake failure on wrong hostname
- **Fix:** Client normalizes domain by stripping `.freshdesk.com` suffix before constructing base URL
- **Files modified:** `src/freshdesk_io/client.py`
- **Committed in:** `c7f6922`

**3. [Rule 1 - Bug] HTML-comment marker pre-send guard removed**
- **Found during:** D-03 live sandbox demo (probe on ticket 368108)
- **Issue:** Earlier design embedded `<!-- csbot:sent:{inbound_msg_id} -->` in reply body and scanned conversations for it as a pre-send guard. Live probe confirmed Freshdesk STRIPS HTML comments from reply bodies — the marker never persists in `body` or `body_text`. The guard was therefore dead weight that could never work.
- **Fix:** Removed marker injection from send_reply; removed marker scan from test assertions; documented D-03 finding in send.py module docstring. Exactly-once now rests on: (1) UNIQUE idempotency key, (2) process_queue_row skip-if-sent, (3) token-checked sent_at write.
- **Files modified:** `src/work_queue/send.py`, `tests/test_e2e_sandbox.py`
- **Committed in:** `7fd7fab` (send.py removal); test alignment committed in this plan's final commit

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 bugs)
**Impact on plan:** All three fixes were necessary for correctness and the sandbox demo to run. The marker removal is a design clarification, not scope creep — it removes unreliable behavior and makes the verification model cleaner.

## Known Limitations / Residual Window

**Documented Phase-2 limitation — POST-to-sent_at residual window:**
There exists a narrow window where the Freshdesk POST succeeds (HTTP 200/201) but the process dies before the `sent_at` UPDATE commits. In that case:
- The row stays `claimed` → `recover_stale_claims` → re-pending → re-claimed
- `process_queue_row` checks `row["sent_at"]` which is NULL (the write never committed)
- The worker will POST again → a genuine duplicate

This window is narrow (milliseconds between POST response and UPDATE commit) and self-healing on the next poll. The HTML-comment marker approach was designed to close this window but was invalidated by the D-03 finding (Freshdesk strips comments). Accepted as a Phase-2 limitation. Phase 6 kill-switch is the next control point. A future mitigation could use a Freshdesk-side idempotency key if the API exposes one.

**Decision (user-approved):** Accept the documented residual window for Phase 2; do not add a customer-visible marker.

## Carry-Forward: SELLESS_SYNC_USER_IDS

`SELLESS_SYNC_USER_IDS` in `.env` must be populated with the real Selless integration user_id(s) — the Freshdesk agent account ID(s) used by the Selless→Freshdesk sync. This ID is needed for the loop-guard (suppress AI replies to Selless-agent messages). Currently the value is empty/placeholder.

**Action required:** Run a live Selless→Freshdesk sync on the sandbox, inspect the resulting Freshdesk conversations for `user_id`, add that value to `.env` and production config. This is a config/data follow-up, not a code gate — the code already reads and applies the setting correctly.

## Issues Encountered

- D-03 sandbox: Freshdesk API does not allow injecting a synthetic "incoming customer" conversation via the API — only UI or real email inbound creates `incoming=True` conversations. Workaround: used existing real inbound conversations on ticket 368108 as test inputs; demo replies were deleted (HTTP 204) post-run to keep sandbox clean.
- pytest-asyncio 1.4 function-scope pool fixture required to avoid session/function event loop mismatch (established in 02-03; maintained here).

## Next Phase Readiness

Phase 02 backbone is complete:
- Freshdesk I/O (read conversations, post replies) — operational
- Queue (enqueue, claim, finalize, dead-letter, recover-stale, sweep-exhausted) — hardened
- Worker (process_queue_row with retry/DLQ + loop-guard + throttle) — operational
- Poller + webhook (durable checkpoint, resolve-then-enqueue, idempotency) — operational
- Observability (structlog JSON, metric counters) — minimal but present
- main.py single entry point — runnable

**Ready for Phase 3:** AI classification + Knowledge RAG MCP integration. The pipeline now has a queue consumer that can call `process_queue_row`; Phase 3 replaces the canned-reply body with the AI-drafted reply.

**Pre-Phase 3 blockers (from Phase 1):**
- P0 policy conflicts (CONTRA-01/02) must be resolved before RAG ingests conflicting content
- SELLESS_SYNC_USER_IDS must be set before live loop-guard is accurate

---
*Phase: 02-freshdesk-i-o-layer-pipeline-backbone*
*Completed: 2026-06-01*
