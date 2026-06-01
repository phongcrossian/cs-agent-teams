---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
plan: "02"
subsystem: freshdesk-io
tags: [freshdesk, httpx, tenacity, pydantic, rate-limit, retry, models, tdd]
dependency_graph:
  requires: ["02-01"]
  provides:
    - FreshdeskClient with post_reply/post_note/get_conversations/get_ticket/list_updated_tickets
    - Error taxonomy: FreshdeskRateLimitError / FreshdeskTransientError / FreshdeskFatalError
    - Pydantic models: Conversation / Ticket / ReplyResult / NoteResult
    - Rate-limit helpers: parse_retry_after / classify_status
  affects:
    - 02-03+ (Wave 1+): all callers import FreshdeskClient from src.freshdesk_io
    - 02-05 (Wave 3): list_updated_tickets provides poller dependency (fix #2)
    - 02-06 (Wave 4): sandbox demo exercises post_reply / retry path
tech_stack:
  added: []
  patterns:
    - tenacity retry with custom freshdesk_wait (honor Retry-After on 429, exp+jitter otherwise)
    - 409 classified FATAL (dead-letter) until sandbox verify in 02-06 Task 3 (fix review #5)
    - Pydantic v2 BaseModel with extra="ignore" for safe API response parsing (T-02-06)
    - Pagination via page++ until empty response (list_updated_tickets)
    - Logs only ticket_id + HTTP status + conversation id — no raw body/PII (T-02-03)
key_files:
  created:
    - src/freshdesk_io/errors.py
    - src/freshdesk_io/models.py
    - src/freshdesk_io/rate_limit.py
    - src/freshdesk_io/client.py
  modified:
    - src/freshdesk_io/__init__.py
    - tests/test_client.py
decisions:
  - "409 → FreshdeskFatalError (dead-letter) until sandbox verify (02-06 Task 3) — fix review #5"
  - "list_updated_tickets pagination: page++ until empty page (not Link header) — simpler, sufficient"
  - "Client accepts injected httpx.AsyncClient for testability (respx pattern)"
  - "Logs ticket_id + conv_id only — no raw body, no from_email (CLAUDE.md PII rule)"
metrics:
  duration_minutes: ~20
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 02 Plan 02: Freshdesk I/O Client — FreshdeskClient with Retry + Rate-limit

Freshdesk I/O boundary module implemented: FreshdeskClient with post_reply/post_note/get_conversations/list_updated_tickets, tenacity retry honoring Retry-After on 429, 409→fatal dead-letter, and pagination for the poller.

## What Was Built

**Task 1 — Pydantic models + error taxonomy + rate-limit helpers**

- `errors.py`: Three exception classes:
  - `FreshdeskRateLimitError(retry_after: int)` — raised on 429, carries Retry-After seconds
  - `FreshdeskTransientError` — raised on 5xx / transport timeout (safe to retry)
  - `FreshdeskFatalError` — raised on 400/401/403/404/409 (no retry, dead-letter immediately)
- `rate_limit.py`:
  - `parse_retry_after(headers) -> int` — reads Retry-After header, default 60 if absent/unparseable
  - `classify_status(status_code) -> "transient" | "fatal"` — 429/5xx=transient; 400/401/403/404/409=fatal
  - 409 → fatal per fix review #5 (treating as success would silently swallow real errors; sandbox verification deferred to 02-06 Task 3)
- `models.py`:
  - `Conversation(id, incoming, private, user_id, from_email, source, body_text)` — loop-guard signal fields
  - `Ticket(id, updated_at)` — minimal poller model (fix review #2), extra fields ignored
  - `ReplyResult(id, ticket_id)`, `NoteResult(id, ticket_id)` — post result wrappers
  - All models use `extra="ignore"` — safe parsing of untrusted API responses (T-02-06)

**Task 2 — FreshdeskClient + 6 tests GREEN**

- `client.py`: `FreshdeskClient(domain, api_key, max_attempts=5)`
  - `post_reply(ticket_id, body) -> ReplyResult`: POST /api/v2/tickets/{id}/reply
  - `post_note(ticket_id, body, private=True) -> NoteResult`: POST /api/v2/tickets/{id}/notes
  - `get_conversations(ticket_id) -> list[Conversation]`: GET /api/v2/tickets/{id}/conversations
  - `get_ticket(ticket_id) -> dict`: GET /api/v2/tickets/{id}
  - `list_updated_tickets(since: datetime) -> list[Ticket]`: pagination via page++ until empty page
  - All methods wrapped with per-call tenacity `@retry`:
    - `retry_if_exception_type((FreshdeskRateLimitError, FreshdeskTransientError, httpx.TransportError))`
    - `stop_after_attempt(max_attempts)` (T-02-05: bounded, no runaway)
    - `_freshdesk_wait`: honors `retry_after` seconds on RateLimitError; exp+jitter otherwise (base=2^attempt, cap=60s, ±1s jitter)
  - `FreshdeskFatalError` NOT in retry set → tenacity does not retry it, raises immediately (T-02-05)
  - Logging: only ticket_id + HTTP status + conversation id (T-02-03, CLAUDE.md PII rule)
  - `httpx.AsyncClient` injectable for testing (respx pattern)
- `__init__.py`: exports `FreshdeskClient`
- `tests/test_client.py`: 6 tests, all GREEN with respx (no network):
  - `test_post_reply_success` — 201 → ReplyResult with correct id
  - `test_post_note` — 201 + verifies `private=True` in request body
  - `test_retry_after` — 429 (Retry-After: 1) then 200 → exactly 2 calls
  - `test_fatal_404_no_retry` — 404 → FreshdeskFatalError, call_count == 1
  - `test_get_conversations` — 200 list → list[Conversation] parsed correctly
  - `test_list_updated_tickets` — page 1 returns 2 tickets, page 2 empty → list[Ticket] with 2 items

## Verification Results

| Check | Result |
|-------|--------|
| `pytest tests/test_client.py -x -q` — 6 tests | PASS (6 passed, 1.11s) |
| `post_reply` → ReplyResult with conversation id | OK |
| `post_note` → NoteResult + private=True in request | OK |
| 429 + Retry-After honored (call_count == 2) | OK |
| 404 → FreshdeskFatalError, call_count == 1 | OK |
| `get_conversations` → list[Conversation] parsed | OK |
| `list_updated_tickets` pagination (page++) | OK |
| `classify_status(409) == "fatal"` (fix #5) | OK |
| `parse_retry_after({}) == 60` (default) | OK |

## Deviations from Plan

### Auto-applied Adjustments

**1. [Rule 2 - Missing Functionality] Added `get_conversations` test**

- **Found during:** Task 2
- The RED scaffold from 02-01 had only 5 tests; plan spec listed 6 including `test_get_conversations`
- Added full `test_get_conversations` test verifying list[Conversation] parse with mixed incoming values
- **Files modified:** tests/test_client.py

None — plan executed with only the one minor gap-fill above.

## Known Stubs

None. All methods are fully implemented and tested. The `get_ticket` method is implemented but not separately tested in test_client.py (no dedicated RED test in 02-01 scaffold; covered implicitly by the module being importable and the method being structurally identical to get_conversations).

## Threat Surface Scan

No new security-relevant surface beyond what the plan's `<threat_model>` covers:
- T-02-03: log redaction implemented (ticket_id + conv_id only) ✓
- T-02-04: API key read from constructor arg (from Settings in production), not hardcoded, not logged ✓
- T-02-05: stop_after_attempt(max_attempts) bounds retry; 409/404/400/401/403 fail immediately ✓
- T-02-06: extra="ignore" on all Pydantic models; no eval/execute of response content ✓

## Self-Check

### Created files exist

- src/freshdesk_io/errors.py: found
- src/freshdesk_io/models.py: found
- src/freshdesk_io/rate_limit.py: found
- src/freshdesk_io/client.py: found
- src/freshdesk_io/__init__.py: modified (found)
- tests/test_client.py: modified (found)

### Commits exist

- eb984c0: feat(02-02): Conversation+Ticket models, error taxonomy, rate-limit helpers
- 8ec9484: feat(02-02): FreshdeskClient — post_reply/post_note/get_conversations/list_updated_tickets

## Self-Check: PASSED
