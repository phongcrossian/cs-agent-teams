---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "05"
subsystem: webhook-poller-intake
tags: [webhook, poller, hmac, fastapi, dedup, checkpoint, resolve-then-enqueue]
dependency_graph:
  requires: ["02-02", "02-03", "02-04"]
  provides: ["src/webhook/signature.py", "src/webhook/receiver.py", "src/poller/reconcile.py"]
  affects: ["queue.ticket_queue", "queue.poller_checkpoint"]
tech_stack:
  added: [fastapi, python-hmac-sha256]
  patterns: [resolve-then-enqueue-D02, durable-checkpoint-fix3, should_suppress-SSOT-fix4, on-conflict-do-nothing-dedup]
key_files:
  created:
    - src/webhook/signature.py
    - src/webhook/receiver.py
    - src/poller/reconcile.py
  modified:
    - src/webhook/__init__.py
    - src/poller/__init__.py
    - tests/test_webhook.py
    - tests/test_poller.py
decisions:
  - "resolve_inbound_and_enqueue single definition in src/poller/reconcile.py — webhook receiver imports from there (no code duplication)"
  - "respx pagination fix: list_updated_tickets paginates until empty page — tests mock side_effect=[data_page, empty_page] to stop loop"
  - "load_checkpoint applies safety overlap (last_since - interval) on resume to cover events during downtime (fix #3)"
metrics:
  duration: "~25 min"
  completed_date: "2026-06-01"
  tasks: 2
  files: 7
---

# Phase 02 Plan 05: Webhook + Reconciliation Poller Summary

## One-Liner

HMAC-SHA256 webhook receiver (FastAPI) + reconciliation poller with durable checkpoint, both feeding queue via shared resolve-then-enqueue helper using should_suppress as single source of truth.

## What Was Built

### Task 1: HMAC-SHA256 Signature Verify + FastAPI Webhook Receiver

**src/webhook/signature.py** — `verify_signature(body, signature, secret)`:
- Uses `hmac.new(secret, body, hashlib.sha256).hexdigest()` + `hmac.compare_digest` (constant-time, T-02-15)
- Returns False for None/empty signature (missing header case)

**src/webhook/receiver.py** — FastAPI `app` with `POST /webhook/freshdesk`:
1. Read raw body (NEVER logged — T-02-17)
2. Verify HMAC-SHA256 signature BEFORE any I/O → 401 on failure (T-02-15 spoofing prevention)
3. Extract `ticket_id` as int from `payload["ticket"]["id"]` (T-02-18: only int extracted)
4. Call `resolve_inbound_and_enqueue()` from reconcile module (shared helper — D-02)
5. Return `{"status": "queued"}` or `{"status": "ignored"}`

**src/webhook/__init__.py** — exports `verify_signature` from signature module.

**tests/test_webhook.py** — 5 tests GREEN:
- `test_hmac_verify_valid`: correct sig → True
- `test_hmac_verify_rejects_bad_sig`: wrong sig / None / empty → False
- `test_enqueue_on_webhook`: valid sig → resolve conv id=456 → key "123:456" in DB
- `test_webhook_no_inbound_skips_enqueue`: only agent reply → should_suppress → 200 ignored, 0 DB rows
- `test_webhook_rejects_unsigned`: no header + secret configured → 401

### Task 2: Reconciliation Poller + Durable Checkpoint

**src/poller/reconcile.py** — shared helpers + poller:

**Shared resolve helpers** (single definition — both webhook + poller import):
- `resolve_latest_inbound_msg_id(client, ticket_id, selless_sync_user_ids) -> int | None`:
  Calls `get_conversations()`, iterates reversed (latest first), calls `should_suppress()` (SSOT fix #4). Returns real conv.id or None.
- `resolve_inbound_and_enqueue(client, conn, ticket_id, payload, selless_sync_user_ids) -> bool`:
  Resolve → compute key → `enqueue_ticket()` (ON CONFLICT DO NOTHING auto-dedup D-02).

**Durable checkpoint** (fix #3, D-09):
- `load_checkpoint(conn, safety_overlap_seconds) -> datetime`:
  Reads `queue.poller_checkpoint id=1`; applies `last_since - safety_overlap` on resume.
  If no row: returns `NOW() - safety_window` as safe default.
- `save_checkpoint(conn, last_since) -> None`:
  UPSERT on `id=1`; called after every `reconcile_once()`.

**reconcile_once(client, pool, since, selless_sync_user_ids) -> (enqueued, new_since)**:
  1. `list_updated_tickets(since)` → paginated ticket list
  2. Per-ticket: `resolve_inbound_and_enqueue()` → auto-dedup via ON CONFLICT
  3. `new_since = max(ticket.updated_at)`; `save_checkpoint(new_since)`
  4. Returns `(enqueued_count, new_since)`

**poller_loop(client, pool, interval_seconds, selless_sync_user_ids)**:
  On startup: `load_checkpoint()` for durable resume. Loops `reconcile_once()` with `asyncio.sleep(interval_seconds)`.

**src/poller/__init__.py** — exports all public symbols.

**tests/test_poller.py** — 4 tests GREEN:
- `test_poller_enqueues_updated`: 2 tickets → 2 DB rows with real keys
- `test_poller_dedup_with_webhook`: pre-enqueued row with key "123:456" → poller ON CONFLICT → still 1 row
- `test_poller_advances_window`: new_since = max(updated_at) of processed tickets
- `test_poller_window_persists_across_restart` (MANDATORY): save → load → resumed with safety overlap, not epoch/NOW()

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] respx pagination hang: mocked single page caused infinite loop**
- **Found during:** Task 2 (test_poller_enqueues_updated hung indefinitely)
- **Issue:** `list_updated_tickets` paginates until empty page. Test mocked only page 1 response; page 2 had no mock → respx either blocked or test hung waiting for network.
- **Fix:** Changed all 3 mock sites to use `side_effect=[data_response, empty_response]` so pagination terminates naturally.
- **Files modified:** tests/test_poller.py
- **Commit:** d598664

## Self-Check

- [x] src/webhook/signature.py exists
- [x] src/webhook/receiver.py exists
- [x] src/poller/reconcile.py exists
- [x] tests/test_webhook.py 5 tests GREEN
- [x] tests/test_poller.py 4 tests GREEN (incl. test_poller_window_persists_across_restart)
- [x] Task 1 commit: 16e9cb5
- [x] Task 2 commit: d598664

## Threat Surface Scan

All threats from plan threat_model were mitigated:

| Threat ID | Mitigation |
|-----------|-----------|
| T-02-15 | verify_signature with hmac.compare_digest; 401 on fail before any I/O |
| T-02-16 | ON CONFLICT DO NOTHING on idempotency_key — replay/duplicate → 0 extra rows |
| T-02-17 | Raw body never logged; only ticket_id + status in logs |
| T-02-18 | Only ticket_id (int-cast) extracted from payload; no field used as URL/command |
| T-02-25 | save_checkpoint after every reconcile_once; load_checkpoint with safety overlap on restart |

No new threat surface introduced beyond plan scope.

## Self-Check: PASSED
