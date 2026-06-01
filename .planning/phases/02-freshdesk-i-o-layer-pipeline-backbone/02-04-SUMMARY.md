---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "04"
subsystem: queue
tags: [loop-guard, pii, presidio, worker, send-mode, dead-letter, exactly-once, freshdesk]

requires:
  - phase: 02-02
    provides: FreshdeskClient (post_reply, get_conversations, list_updated_tickets, models)
  - phase: 02-03
    provides: claim_one, finalize_done, finalize_retry, enqueue_ticket (queue.ticket_queue schema)

provides:
  - "src/guards/loop_guard.py — should_suppress() 4-layer single source of truth + should_throttle_ticket()"
  - "src/guards/pii.py — redact_text() via Presidio (D-12)"
  - "src/work_queue/send.py — send_reply() mode-aware (DRY_RUN/LIVE) + send-intent transactional + pre-send guard (fix #1)"
  - "src/work_queue/dead_letter_sink.py — DeadLetterSink Protocol + RetryOnlyDeadLetterSink (fix #7)"
  - "src/work_queue/worker.py — process_queue_row() + worker_loop() sequential (D-11)"
  - "D-07 sandbox-verified: incoming=false + stable user_id is correct Selless-sync signal; config follow-up flagged"

affects:
  - 02-05-resolve-then-enqueue
  - 02-06-sandbox-demo
  - phase-04-draft-engine
  - phase-06-kill-switch-routing

tech-stack:
  added:
    - presidio-analyzer / presidio-anonymizer (PII redaction, en_core_web_lg)
  patterns:
    - "Single source of truth: should_suppress() called identically by resolve (02-05) and worker — no inline incoming/private drift (fix #4)"
    - "Send-intent transactional: sent_at + freshdesk_reply_id persisted immediately after POST 200; re-claim skips post (exactly-once across crash — fix #1, REP-05)"
    - "Pre-send guard: scan conversations for system marker before live POST — closes residual crash window (fix #1)"
    - "DeadLetterSink injected as dependency (not stringly-typed hook) — fatal path has typed destination from Wave 2 (fix #7)"
    - "Per-ticket throttle: independent loop-breaker counting sent_at rows within window — protects criterion #4 even when RFC 3834 headers are inert (A4)"
    - "D-07 whitelist config-driven: SELLESS_SYNC_USER_IDS env var (set[int]); is_selless_sync() factored out for marker/tag fallback swap"

key-files:
  created:
    - src/guards/__init__.py
    - src/guards/loop_guard.py
    - src/guards/pii.py
    - src/work_queue/send.py
    - src/work_queue/dead_letter_sink.py
    - src/work_queue/worker.py
  modified:
    - tests/test_loop_guard.py
    - tests/test_queue.py

key-decisions:
  - "should_suppress() is single source of truth for D-06/D-07 — both resolve (02-05) and worker call identical function; no inline conditions elsewhere (fix #4)"
  - "D-07 primary path CONFIRMED on sandbox (shophelp-dev, ticket 368108): API-originated conversations carry stable user_id (incoming=false); whitelist mechanism is sound"
  - "SELLESS_SYNC_USER_IDS is config-driven (env var) — specific Selless service account user_id must be captured from a real sync event and added to .env (data follow-up, not code gate)"
  - "raw_headers_exposed=False confirmed: GET /api/v2/conversations does NOT expose RFC 3834 email headers; Layer 1 only available from webhook payload — worker/resolve paths do not depend on API-fetched headers (matches A4 conservative-safe assumption)"
  - "409 remains FreshdeskFatalError (dead-letter) until 02-06 sandbox demo reproduces and characterizes the semantic"
  - "send_reply() is the Phase 6 kill-switch / Phase 7 rollout seam — documented with explicit comment, not a temporary dev flag"
  - "stale_inbound is observable status distinct from suppressed: worker re-check suppress on valid row → status=stale_inbound + emit_alert, never silent drop (fix #4)"

patterns-established:
  - "Guard single source of truth: consolidate all classification logic in one function called uniformly — prevents drift between pipeline stages"
  - "Send-intent dual-write: persist sent_at immediately after POST 200 so crash-recovery skips re-send without coordinator"
  - "Dependency-injected sink: fatal error destinations typed via Protocol, injected at construction — no magic string dispatch"

requirements-completed: [REP-05]

duration: ~90min (Tasks 1-2 implementation + Task 3 sandbox checkpoint + findings recording)
completed: "2026-06-01"
---

# Phase 02 Plan 04: Worker + Guards + Send-Mode Integration Summary

**4-layer loop-guard (single source of truth), Presidio PII redaction, mode-aware send_reply with exactly-once send-intent transactional, DeadLetterSink Protocol, and a complete process_queue_row worker — with D-07 Selless-sync primary path confirmed on the shophelp-dev Freshdesk sandbox.**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-06-01T~13:00Z
- **Completed:** 2026-06-01T15:13Z
- **Tasks:** 3 (Tasks 1-2 implementation + TDD; Task 3 sandbox checkpoint + findings)
- **Files modified:** 8

## Accomplishments

- `should_suppress()` unifies all 4 D-06 loop-guard signal layers (RFC 3834 headers, sender regex, incoming/private actor, Selless-sync user_id) as a single source of truth called identically by both the resolve step (02-05) and the worker — eliminating any drift risk between pipeline stages (fix #4).
- Per-ticket throttle (`should_throttle_ticket`) provides an independent loop-breaker counting `sent_at` rows within a rolling window — criterion #4 holds even when RFC 3834 headers are inert from the API (A4 confirmed on sandbox).
- `send_reply()` implements true exactly-once across crash: persist `sent_at + freshdesk_reply_id` transactionally immediately after POST 200; re-claim of a row with `sent_at IS NOT NULL` skips the post entirely and goes straight to `finalize_done` (fix #1, REP-05).
- D-07 sandbox verification confirmed: API-originated conversations carry a stable, populated `user_id` with `incoming=false` — the whitelist mechanism is sound. Config follow-up flagged (capture real Selless service account user_id and add to `SELLESS_SYNC_USER_IDS` env var).
- RFC 3834 header availability confirmed NOT via API conversations endpoint — Layer 1 is only usable from webhook payload; all conservative-safe assumptions already coded correctly (A4).

## Task Commits

1. **Task 1: Loop-guard 4-layer + PII redaction + per-ticket throttle** — `930af83` (feat)
2. **Task 2: send_reply + DeadLetterSink + process_queue_row worker** — `69b0209` (feat)
3. **Task 3: D-07 sandbox findings recorded in loop_guard comment** — `8ce5a23` (docs)

## Files Created/Modified

- `src/guards/__init__.py` — guards package init
- `src/guards/loop_guard.py` — `should_suppress()` 4-layer + `should_throttle_ticket()` + D-07 sandbox findings comment
- `src/guards/pii.py` — `redact_text()` via Presidio (lazy singleton, en_core_web_lg)
- `src/work_queue/send.py` — `send_reply()` DRY_RUN/LIVE + pre-send guard + send-intent transactional (fix #1)
- `src/work_queue/dead_letter_sink.py` — `DeadLetterSink` Protocol + `RetryOnlyDeadLetterSink` (fix #7)
- `src/work_queue/worker.py` — `process_queue_row()` + `worker_loop()` sequential (D-11)
- `tests/test_loop_guard.py` — 8 TDD tests (4 layer suppression + resolve-uses-should-suppress + throttle + redact_pii)
- `tests/test_queue.py` — 6 worker/send TDD tests (dry_run, live, suppressed, stale_inbound, happy-path exactly-once, crash-after-post no-resend)

## Decisions Made

- `should_suppress()` is the single source of truth (fix #4): no inline `incoming/private` conditions exist in worker or resolve step — both import and call this function.
- D-07 primary path mechanism confirmed sound on sandbox; specific Selless service account `user_id` is a config/data follow-up (not a code gate).
- `send_reply()` is explicitly documented as the Phase 6 kill-switch / Phase 7 rollout seam — not a temporary dev flag.
- `stale_inbound` is a distinct observable status (not silent-suppressed) when worker re-check finds a previously-valid-enqueued row now suppressed — emits alert for dropped-reply visibility (fix #4).
- `DeadLetterSink` injected as typed Protocol dependency — fatal-404 path has a typed destination from Wave 2 onward; Plan 06 will inject the real `PostgresDeadLetterSink`.

## Deviations from Plan

None — plan executed exactly as written. Task 3 checkpoint was resolved by human sandbox verification and findings were recorded as a comment update in `loop_guard.py` and documented here, as directed by the checkpoint resolution.

## D-07 Sandbox Verification Findings (Task 3)

**Checkpoint type:** `human-verify` — performed against real Freshdesk sandbox (shophelp-dev).

| Finding | Result | Action |
|---------|--------|--------|
| D-07 primary path (user_id whitelist mechanism) | CONFIRMED SOUND — API agent user carried stable `user_id=60006429889`, `incoming=false` | Config follow-up: capture real Selless service account user_id and add to `SELLESS_SYNC_USER_IDS` |
| `raw_headers_exposed` (RFC 3834 via GET /conversations) | NOT EXPOSED — `email_headers`/`Auto-Submitted`/`Precedence`/`List-*` absent from API response | Layer 1 only available from webhook payload; worker/resolve must not depend on API-fetched headers — already coded correctly (A4) |
| 409 semantic | Not reproduced in sandbox | Remains `FreshdeskFatalError` (dead-letter) until 02-06 sandbox demo |

**Config follow-up (not a code gate):** Add the real Selless integration service account `user_id` (obtained from a live Selless→Freshdesk sync event) to `.env` as `SELLESS_SYNC_USER_IDS=<id>`. Do NOT use `60006429889` — that is the sandbox API agent user, not the Selless service account.

## Issues Encountered

None.

## User Setup Required

**Config follow-up flagged (D-07):** After a real Selless→Freshdesk sync event occurs, capture the `user_id` from the resulting conversation entry (via `GET /api/v2/tickets/{id}/conversations`) and set:

```
SELLESS_SYNC_USER_IDS=<selless_service_account_user_id>
```

in `.env`. The whitelist is already config-driven (`set[int]` parsed from CSV env var in `Settings`). This is a data/ops step, not a code change.

## Next Phase Readiness

- **02-05 (resolve-then-enqueue):** Fully unblocked. `should_suppress()` is ready for import as the single source of truth at the resolve stage. `enqueue_ticket()` interface from 02-03 is in place.
- **02-06 (sandbox demo):** Can proceed. Will reproduce and characterize 409 semantic to confirm or update `FreshdeskFatalError` classification.
- **Phase 04 (draft engine):** Worker seam (`canned_body = placeholder reply`) is explicitly marked for replacement by the real draft. The `process_queue_row()` function signature is stable.
- **Phase 06 (kill-switch/routing):** `send_reply()` is documented as the kill-switch seam. `DeadLetterSink` Protocol ready for `PostgresDeadLetterSink` injection.

---
*Phase: 02-freshdesk-i-o-layer-pipeline-backbone*
*Completed: 2026-06-01*
