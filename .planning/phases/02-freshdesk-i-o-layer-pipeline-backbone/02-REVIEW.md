---
phase: 02-freshdesk-i-o-layer-pipeline-backbone
reviewed: 2026-06-01T09:45:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - src/config.py
  - src/freshdesk_io/client.py
  - src/freshdesk_io/errors.py
  - src/freshdesk_io/models.py
  - src/freshdesk_io/rate_limit.py
  - src/guards/loop_guard.py
  - src/guards/pii.py
  - src/work_queue/enqueue.py
  - src/work_queue/claim.py
  - src/work_queue/idempotency.py
  - src/work_queue/worker.py
  - src/work_queue/send.py
  - src/work_queue/dead_letter.py
  - src/work_queue/dead_letter_sink.py
  - src/webhook/receiver.py
  - src/webhook/signature.py
  - src/poller/reconcile.py
  - src/observability.py
  - src/main.py
  - migrations/versions/0001_initial_queue_schema.py
findings:
  blocker: 4
  warning: 8
  info: 5
  total: 17
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-01T09:45:00Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Reviewed the Freshdesk I/O layer and pipeline backbone for Phase 2. The exactly-once design is largely sound: the idempotency-key unique index, `SKIP LOCKED` claim, token-checked finalization, and skip-if-sent path are correctly wired and the residual POST-200-before-`sent_at`-commit crash window is a documented, accepted limitation (not re-reported here).

However, adversarial review surfaced four blocker-class defects that undermine the exactly-once and PII guarantees in practice:

1. **`send_reply` LIVE path and `finalize_done` run as separate auto-committed statements** — the skip-if-sent guard relies on `sent_at` being written, but if the worker crashes between the POST and the `sent_at` write, the row is re-claimed and re-POSTed, producing a duplicate customer reply. This is the documented residual window, BUT the implementation widens it beyond what is documented because `process_queue_row` never opens an explicit transaction, so even non-crash paths leave windows.
2. **`throttle` and skip-if-sent ordering allows a duplicate send to bypass the throttle** under stale-claim recovery.
3. **HMAC signature comparison can throw and 500 instead of 401** on a malformed (odd-length / non-hex) signature, and the signature scheme has no replay/timestamp protection.
4. **PII redaction is not actually invoked on the webhook/poller persist path** — `enqueue_ticket` persists `payload` verbatim and the contract is delegated to callers who pass only `{"ticket_id": ...}`, but `dry_run_log.body` and several log sites depend on redaction wiring that is partially bypassed.

Plus eight warnings (status-domain has no DB constraint, unbounded pagination, `0.0.0.0` bind, per-request pool/client creation leak, backoff overflow on high attempt counts, etc.) and several info items.

## Blocker Issues

### BL-01: Worker pipeline is not transactional — widens the duplicate-send window beyond the documented limitation

**File:** `src/work_queue/worker.py:105-218`, `src/work_queue/send.py:130-147`
**Issue:** `process_queue_row` acquires a connection via `async with pool.acquire() as conn:` but never opens `conn.transaction()`. Every `conn.execute` (the `sent_at` send-intent write in `_live_send`, and `finalize_done`) auto-commits independently. The documented/accepted limitation is the narrow window between Freshdesk returning 200 and the `sent_at` write committing. But because there is no surrounding transaction, the design also exposes a second, *avoidable* gap: after `_live_send` commits `sent_at` but before `finalize_done` commits, a crash leaves the row in `claimed` with `sent_at` set. Stale-claim recovery resets it to `pending`, it is re-claimed, and skip-if-sent correctly short-circuits — so this particular sub-window is covered. The real exposure is that the POST in `client.post_reply` itself contains a tenacity retry loop that can POST more than once on a transient-then-success sequence (e.g. a 502 then 200) where the first POST actually succeeded server-side but the client saw a transport error. There is no server-side idempotency key sent to Freshdesk, so a retried reply is a duplicate customer-visible message. This is broader than the documented single crash window.
**Fix:** Send a client-generated idempotency token to Freshdesk if/when the API supports it; until then, do not let `post_reply` retry on `httpx.TransportError` after the request body has been transmitted (only retry on pre-send connect errors). At minimum, narrow the tenacity `retry_if_exception_type` for `post_reply`/`post_note` (mutating calls) to exclude post-send transport errors:
```python
# In FreshdeskClient, use a non-retrying decorator for mutating POSTs,
# or retry only on httpx.ConnectError (pre-send), not httpx.TransportError (post-send).
retry=retry_if_exception_type((FreshdeskRateLimitError, FreshdeskTransientError, httpx.ConnectError))
```

### BL-02: Per-ticket throttle can be bypassed, allowing a duplicate reply within the throttle window

**File:** `src/work_queue/worker.py:177-191`, `src/guards/loop_guard.py:198-222`
**Issue:** `should_throttle_ticket` counts rows where `sent_at IS NOT NULL` within the window and returns True when `count >= n` (default n=1). The throttle is checked in step 4, *before* the send in step 7. Two distinct queue rows for the same ticket (e.g. one enqueued by the webhook, one by the poller with a *different* `inbound_msg_id` because a new customer reply arrived) can both pass the throttle check concurrently in the single-worker model only sequentially — but the count is read at the start of processing and `sent_at` for the row currently being processed is written later. If row A is processed and sent (sent_at written) and row B was claimed/read before A's `sent_at` committed, B's throttle check saw count=0 and proceeds to send a second reply inside the window. In the strictly-sequential D-11 worker this is mitigated, but the moment N>1 workers are enabled (explicitly advertised as "no code changes required" at `worker.py:368-369`) the throttle check and the send are not atomic, so the loop-breaker silently fails. The throttle is the only backstop for criterion #4 when RFC 3834 headers are inert.
**Fix:** Make the throttle check-and-record atomic, or perform the throttle count inside the same transaction as the `sent_at` write with `SELECT ... FOR UPDATE` on the ticket, or add a partial unique index enforcing at most `n` sent rows per ticket per window. Do not advertise N-worker safety until the throttle is concurrency-safe.

### BL-03: Webhook signature verification raises (HTTP 500) on malformed signature and has no replay protection

**File:** `src/webhook/signature.py:34-39`, `src/webhook/receiver.py:80-84`
**Issue:** `hmac.compare_digest(expected, signature)` compares a hex `str` (`expected`) against the attacker-controlled header value `signature`. `compare_digest` raises `TypeError` if the two arguments are of different types or if a `str` contains non-ASCII characters. An attacker sending a signature header containing a non-ASCII byte (or, in some Python configurations, mismatched types) causes `compare_digest` to raise, which propagates out of `verify_signature` into `webhook_freshdesk`, producing an unhandled `500` rather than the intended `401`. A 500 vs 401 difference is an information-disclosure / availability oracle and breaks the "bad/missing signature -> 401" security contract (T-02-15). Additionally, the HMAC scheme has no timestamp/nonce, so a captured valid request can be replayed indefinitely to re-enqueue tickets.
**Fix:** Guard the comparison and treat any exception as verification failure; add replay protection:
```python
def verify_signature(body, signature, secret) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False
```
Consider signing a `timestamp` header into the HMAC and rejecting requests older than a few minutes to mitigate replay. (The replay surface is partly mitigated by ON CONFLICT dedup, but a replay with a new inbound message still re-triggers a send.)

### BL-04: PII redaction contract is delegated but never enforced; raw body reaches `dry_run_log` and is trusted to be pre-redacted

**File:** `src/work_queue/worker.py:193-215`, `src/work_queue/send.py:88-104`, `src/work_queue/enqueue.py:6-9`
**Issue:** CLAUDE.md / D-12 mandate redaction before any DB persist of customer content. In the worker, `redact_text(raw_body)` is called (line 195) but the *result* (`redacted_body`) is then discarded — the body actually sent to `send_reply` is `canned_body` (line 200-203, 211), so for Phase 2 the redacted body is never persisted. That is fine for the canned placeholder, BUT the `dry_run_log` persists whatever `body` it receives (`send.py:97-104`) with a comment claiming "caller must have already called redact_text()", and the worker passes `canned_body` (safe) — so today this is latent. The real defect is the `enqueue_ticket` contract (`enqueue.py:6-9`): it persists `redacted_payload` verbatim into the JSONB `payload` column and documents "Full PII-redaction wiring (Presidio) is done in plan 04; this module only persists whatever payload it receives." Both the webhook (`receiver.py:131`) and poller (`reconcile.py:204`) pass `{"ticket_id": ticket_id}` — safe today — but the column is the persisted seam future code will fill, and there is no guard preventing an unredacted payload from being stored. A contract enforced only by comment is a latent PII leak. The `redact_text` call in the worker is dead weight that creates a false sense of compliance.
**Fix:** Either remove the misleading `redact_text` call in the worker (since its output is unused) or wire it to the actual persisted/logged value. For `enqueue_ticket`, add an assertion or schema that rejects known PII-bearing keys, or centralize redaction inside `enqueue_ticket` rather than trusting callers. Add a test that fails if an unredacted email/body string reaches `payload` or `dry_run_log.body`.

## Warnings

### WR-01: `status` column has no CHECK constraint or enum — typos silently corrupt state

**File:** `migrations/versions/0001_initial_queue_schema.py:41-62`, `src/work_queue/worker.py:169-189`
**Issue:** `status` is a free `TEXT` column. The code writes the string literals `'pending'`, `'claimed'`, `'done'`, `'suppressed'`, `'stale_inbound'`, `'dead_lettered'` from multiple modules (`_mark_status`, `finalize_done`, `claim_one`, dead-letter sink). A typo (e.g. `'supressed'`) would not be caught and a row could become un-claimable and un-swept (the `claim_one` filter is `status = 'pending'` and `sweep_exhausted` filters `status = 'pending'`). Silent stuck rows violate the "no silent drop" invariant.
**Fix:** Add `CHECK (status IN ('pending','claimed','done','suppressed','stale_inbound','dead_lettered'))` to the column, or use a Postgres enum type.

### WR-02: `list_updated_tickets` pagination is unbounded — can loop and accumulate unbounded memory

**File:** `src/freshdesk_io/client.py:256-300`
**Issue:** The `while True` loop fetches pages until an empty page is returned. Freshdesk's list endpoint caps at page 10 / 300 results historically and returns the same data or a 400 past the cap rather than an empty list. If the API never returns an empty page (or returns a non-empty final page repeatedly), the loop never terminates. There is also no max-page guard and `results` grows without bound for a very active window. The poller runs this on a cadence; a stuck call blocks the poller loop.
**Fix:** Add a hard page cap (e.g. `MAX_PAGES = 50`) and break with a warning if exceeded; rely on `updated_since` advancing the window rather than deep pagination.

### WR-03: Webhook binds to `0.0.0.0` with no auth beyond optional HMAC

**File:** `src/main.py:108-113`, `src/webhook/receiver.py:77-78`
**Issue:** uvicorn binds `host="0.0.0.0"` (all interfaces). The HMAC check is *skipped entirely* when `WEBHOOK_SECRET` is empty (`receiver.py:78` — `if webhook_secret_str:`). In any deployment where the secret env var is unset or blank, the endpoint accepts unauthenticated enqueue requests from anywhere reachable. Fail-open on a missing secret is dangerous for a system that posts customer-visible replies.
**Fix:** Fail closed: if `WEBHOOK_SECRET` is not configured, reject all webhook requests with 401 (or refuse to start). Bind to a specific interface / require a reverse proxy.

### WR-04: Webhook creates a new asyncpg pool and httpx client per request — connection/socket leak

**File:** `src/webhook/receiver.py:39-47, 113-128`
**Issue:** `_get_pool()` calls `asyncpg.create_pool(...)` on every request when `_test_pool` is None (no caching), and `webhook_freshdesk` constructs a fresh `httpx.AsyncClient` and `FreshdeskClient` per request and never closes either. Under load this leaks pools, DB connections, and sockets until exhaustion. (Out-of-scope perf is excluded, but resource exhaustion is a correctness/availability defect — the endpoint will start failing.)
**Fix:** Create the pool and HTTP client once at app startup (FastAPI lifespan / `app.state`) and reuse; close on shutdown.

### WR-05: `instantiates `Settings()` per webhook request and reads env directly — config drift

**File:** `src/webhook/receiver.py:107-111`, `src/main.py:97`
**Issue:** The webhook reads `WEBHOOK_SECRET`, `FRESHDESK_DOMAIN`, `FRESHDESK_API_KEY`, `DATABASE_URL` directly from `os.environ` AND also constructs `Settings()` — two independent config sources that can diverge (e.g. `.env` loaded by pydantic-settings vs raw env). `main.py` separately constructs `Settings()`. The signature check uses raw env `WEBHOOK_SECRET` while the rest uses `Settings`. Inconsistent config resolution is a latent security/behavior bug (e.g. secret set in `.env` but not exported → signature check silently disabled).
**Fix:** Resolve config once through `Settings` and inject it; do not mix `os.environ.get` and `Settings`.

### WR-06: Backoff exponent overflows / saturates at high attempt counts in client wait

**File:** `src/freshdesk_io/client.py:53-61`
**Issue:** `_freshdesk_wait` computes `base = min(2 ** attempt, 60)` where `attempt = retry_state.attempt_number`. With large `max_attempts` this is fine due to the cap, but `2 ** attempt` is computed before the cap so for pathological configs it does unnecessary big-int work; more importantly `base + random.uniform(-1.0, 1.0)` can return a negative wait when `base` is small relative to jitter only if base<1 (not possible here since min attempt gives 2**1=2). Minor. The real issue: the worker's `_compute_backoff` (`worker.py:71`) uses `math.pow(2, attempts)` which returns a float and for `attempts` ~1000+ yields `inf`, and `min(inf, cap)` = cap so it is safe, but `int(capped + jitter)` is fine. Net: defensive but the two backoff implementations (client vs worker) diverge in base/cap/jitter, which is an inconsistency.
**Fix:** Unify the two backoff strategies into one helper; clamp attempt before exponentiation (`min(attempt, 16)`).

### WR-07: `parse_retry_after` ignores HTTP-date form of Retry-After

**File:** `src/freshdesk_io/rate_limit.py:19-31`
**Issue:** `Retry-After` may be either delta-seconds *or* an HTTP-date (RFC 7231). The parser only handles the integer form and silently returns 60 for the date form. If Freshdesk ever sends a date, the client waits a fixed 60s that may be far shorter than the server-requested backoff, causing repeated 429s and faster exhaustion toward dead-letter.
**Fix:** Parse the HTTP-date form (`email.utils.parsedate_to_datetime`) and compute the delta; fall back to 60 only if truly unparseable.

### WR-08: `recover_stale_claims` does not preserve `sent_at`/attempts semantics for in-flight sends

**File:** `src/work_queue/claim.py:149-182`
**Issue:** The stale-claim sweeper resets `claimed`→`pending` for rows older than the lease, but does not consider whether `sent_at IS NOT NULL`. A row that was sent but crashed before `finalize_done` is reset to `pending` and re-claimed; skip-if-sent then finalizes it — correct. But the sweeper also resets rows where the worker is *legitimately still processing* a slow Freshdesk call that exceeds the 10-minute lease (the client timeout is 30s but tenacity retries with backoff can exceed 10 min on sustained 429s). The original worker is still holding the row logically (not via DB lock, since the claim transaction already committed), so two workers can process the same row; for a LIVE send this risks a duplicate POST before either writes `sent_at`.
**Fix:** Set the lease window safely larger than the worst-case `max_attempts * max_backoff`, or have the worker heartbeat `claimed_at` during long retries, or only recover rows where `sent_at IS NULL`.

## Info

### IN-01: Two divergent backoff implementations

**File:** `src/freshdesk_io/client.py:53-61`, `src/work_queue/worker.py:62-75`
**Issue:** Client uses `2**attempt` cap 60 ±1s; worker uses `base*2^attempts` cap 60 ±25%. Divergent behavior for the same conceptual retry.
**Fix:** Extract a single shared backoff helper.

### IN-02: `_AUTO_SUBMITTED_SUPPRESS` is a dead empty frozenset

**File:** `src/guards/loop_guard.py:35-38`
**Issue:** Declared but never used; the actual check is inline at line 57-59. Dead code with a misleading name.
**Fix:** Remove it.

### IN-03: `should_dead_letter` is imported into worker but never called on the actual decision path

**File:** `src/work_queue/worker.py:51, 225-234`
**Issue:** The comment at 227-228 says "call it explicitly for documentation clarity" but it is not actually called — the fatal branch dead-letters unconditionally. The import and helper are effectively unused in the worker.
**Fix:** Either call `should_dead_letter(exc)` to gate the branch or drop the import.

### IN-04: `database_url` scheme rewrite only handles one alias

**File:** `src/main.py:97`
**Issue:** `.replace("postgresql+asyncpg://", "postgresql://")` handles only that one driver prefix; a `postgres://` or `postgresql+psycopg://` URL would pass through and may fail in asyncpg. Minor robustness gap.
**Fix:** Normalize known SQLAlchemy-style prefixes explicitly.

### IN-05: `freshdesk_reply_id` typed BIGINT but `ReplyResult.id` / `inbound_msg_id` are INTEGER

**File:** `migrations/versions/0001_initial_queue_schema.py:45, 57, 89`
**Issue:** `ticket_id` and `inbound_msg_id` are `INTEGER` (max ~2.1B) while `freshdesk_reply_id` is `BIGINT`. Freshdesk conversation/ticket IDs already exceed 2^31 in some accounts (the sandbox note in `loop_guard.py:130` shows `user_id=60006429889`, ~6e10, far beyond INTEGER range). Storing such an ID in an `INTEGER` column raises a numeric-overflow error at insert time, which would fail enqueue for those tickets.
**Fix:** Change `ticket_id`, `inbound_msg_id`, and any stored Freshdesk-origin IDs to `BIGINT` for consistency and to avoid overflow.

---

_Reviewed: 2026-06-01T09:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
