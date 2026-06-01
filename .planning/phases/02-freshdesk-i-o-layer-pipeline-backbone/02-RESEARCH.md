# Phase 2: Freshdesk I/O Layer & Pipeline Backbone — Research

**Nghiên cứu hoàn thành:** 2026-06-01
**Domain:** Freshdesk REST API v2, Postgres-backed queue, httpx+tenacity, FastAPI webhook, Presidio PII
**Confidence tổng thể:** MEDIUM-HIGH (stack đã xác minh; một số chi tiết Freshdesk conversation field cần xác nhận trực tiếp qua sandbox)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Postgres-backed queue + state. Dùng một Postgres duy nhất làm cả work queue (claim via `SELECT ... FOR UPDATE SKIP LOCKED`) và store cho idempotency keys / dedup / dead-letter. Reuse Postgres Phase 3 sẽ dùng cho pgvector → một datastore, transactional idempotency.
- **D-02:** Idempotency key = `ticket_id + inbound_message_id`. Cả webhook path và safety-net poller đều tính cùng key từ cùng ticket state → exactly-once. KHÔNG dùng webhook delivery ID hay content hash.
- **D-03:** Demo posts canned reply vào Freshdesk sandbox account (không phải real customer), chứng minh criterion #2 (post + retry-does-not-double-send).
- **D-04:** Client expose cả reply (public) và note (private) ngay từ đầu.
- **D-05:** Config-driven send-mode switch, default = dry-run. Là seed của Phase 6 kill-switch và Phase 7 staged-rollout control.
- **D-06:** Bốn signal layer loop-guard: (1) RFC 3834 headers, (2) sender patterns, (3) Freshdesk source/actor, (4) Selless-sync origin.
- **D-07:** Sync-echo detection dùng Freshdesk source/actor field. Research flag: verify Freshdesk có stamp distinguishable source/actor cho Selless-sync-originated updates không; nếu không → fallback marker/tag.
- **D-08:** Suppression action = skip + log/metric (KHÔNG dead-letter).
- **D-09:** Webhook primary + periodic reconciliation poller (~5–15 min cadence, `updated_since` scan).
- **D-10:** Bounded backoff + jitter, honor Retry-After on 429 → Postgres dead-letter on exhaustion + alert.
- **D-11:** Single sequential worker Phase 2; SKIP LOCKED design để sau scale lên N workers.
- **D-12:** PII redaction (Presidio) wired từ Phase 2; tracing minimal (structured logs + metrics).

### Claude's Discretion

- Error classification taxonomy cho D-10 (transient vs fatal HTTP errors).
- Exact Postgres table/schema design cho queue, processed/idempotency, và dead-letter.
- Webhook receiver framework (FastAPI) và deployment shape.
- Poller exact cadence; backoff base/cap/jitter values.
- Directory/module layout cho I/O client và worker.

### Deferred Ideas (OUT OF SCOPE)

- Scale-out worker model (N workers + per-ticket lock).
- Full Langfuse tracing / observability dashboard (Phase 4/5/6).
- Marker/tag-based sync-echo detection fallback (chỉ build nếu research D-07 fail).
- Transient-vs-fatal error refinement phức tạp hơn.
- Channel scope re-check (Email 30% vs Contact Form 60%).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REP-05 | AI posts approved reply into correct existing Freshdesk ticket via API, idempotently (no duplicate sends) | Freshdesk POST /api/v2/tickets/{id}/reply verified; Postgres SKIP LOCKED idempotency pattern documented; exactly-once token pattern documented |
</phase_requirements>

---

## Summary

Phase 2 xây dựng "đường ray" (rails) cho toàn bộ pipeline: webhook receiver → Postgres queue → sequential worker → Freshdesk reply/note client. Đây là phase code đầu tiên; repo hiện tại chỉ có planning docs. Mọi phase sau (3, 4, 5, 6, 7) đều chạy qua lớp I/O này.

Stack đã được xác minh hoàn toàn trên PyPI: FastAPI 0.136, httpx 0.28, tenacity 9.1, asyncpg 0.31, SQLAlchemy 2.0, Alembic 1.18, Presidio 2.2, uvicorn 0.48, pytest 9.0, respx 0.23. Tất cả 10 package cốt lõi qua slopcheck [OK]. Docker chưa có trong PATH trên máy dev hiện tại — cần cài để chạy Postgres local (xem Environment Availability).

Điểm quan trọng nhất cần xác nhận qua sandbox trước khi code D-07: Freshdesk conversation API trả về field `incoming` (true/false) để phân biệt customer reply vs agent/system reply — **đây là signal layer 3 chính**. Tuy nhiên, API v2 không expose explicit "actor type" field; cần kết hợp `incoming=false` + `user_id` lookup để phân biệt AI's own reply với agent reply. Source/actor trên Selless-sync updates cần xác nhận trực tiếp qua sandbox.

**Primary recommendation:** Implement Postgres queue với SKIP LOCKED + atomic CTE claim pattern. Dùng FastAPI webhook receiver với HMAC-SHA256 verification. httpx + tenacity với `wait_exponential_jitter` + custom `Retry-After` wait. Presidio redact trước khi persist bất kỳ text nào vào log/DB.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Freshdesk inbound event reception | API / Backend (webhook receiver) | — | Webhook endpoint là entry point duy nhất từ Freshdesk |
| Work queue + state management | Database / Storage (Postgres) | — | D-01: single Postgres datastore, transactional idempotency |
| Loop/auto-reply guard | API / Backend (worker) | — | Decision logic trước khi enqueue, không phải tại edge |
| Freshdesk reply/note posting | API / Backend (I/O client) | — | Centralized module duy nhất được phép gọi Freshdesk API |
| Rate limit + retry/backoff | API / Backend (I/O client) | — | httpx + tenacity wraps mọi outbound Freshdesk call |
| PII redaction | API / Backend (worker, trước persist) | — | Presidio chạy trước bất kỳ log/DB write nào |
| Reconciliation poller | API / Backend (background scheduler) | — | Reads Freshdesk `updated_since`, feeds vào same queue |
| Dead-letter + alerting | Database / Storage (Postgres) | API/Backend (log/metric emit) | Postgres dead-letter table + structured log alert |

---

## Standard Stack

### Core

| Library | Version (verified PyPI) | Purpose | Why Standard |
|---------|------------------------|---------|--------------|
| `fastapi` | 0.136.3 | Webhook receiver HTTP server | ASGI, async-native, Pydantic v2 integration, nhanh và production-ready |
| `uvicorn` | 0.48.0 | ASGI server cho FastAPI | Standard pair với FastAPI; hỗ trợ graceful shutdown |
| `httpx` | 0.28.1 | HTTP client gọi Freshdesk API | Async-first, hỗ trợ retry hooks, CLAUDE.md-mandated |
| `tenacity` | 9.1.4 | Retry/backoff/jitter decorator | CLAUDE.md-mandated; `wait_exponential_jitter` + custom `Retry-After` wait |
| `asyncpg` | 0.31.0 | Async Postgres driver | Hiệu năng cao nhất cho Python async; dùng trực tiếp với raw SQL cho queue |
| `sqlalchemy` | 2.0.50 | ORM/Core cho schema definition + migrations | SQLAlchemy 2.0 async mode; dùng Core (không ORM) cho queue queries nhạy cảm |
| `alembic` | 1.18.4 | Database migrations | Pair chuẩn với SQLAlchemy; Phase 3 pgvector extension cũng dùng |
| `pydantic` | 2.13.4 | Data validation cho webhook payload, models | CLAUDE.md stack; type-safe input parsing |
| `presidio-analyzer` | 2.2.359 | PII detection trong ticket text | D-12: redact trước log/persist; CLAUDE.md-mandated |
| `presidio-anonymizer` | 2.2.362 | PII replacement/redaction | Companion package; replaces PII với entity type tags |
| `python-dotenv` | 1.2.2 | Config/env loading | Standard Python env management |
| `structlog` | 25.5.0 | Structured JSON logging | D-12: structured logs + metrics; JSON output cho log aggregation |

### Supporting (Dev/Test)

| Library | Version (verified PyPI) | Purpose | When to Use |
|---------|------------------------|---------|-------------|
| `pytest` | 9.0.3 | Test framework | Tất cả unit + integration tests |
| `respx` | 0.23.1 | httpx mock cho tests | Mock Freshdesk API calls trong CI (không cần network) |
| `pytest-asyncio` | latest | Async test support | Cần cho FastAPI + asyncpg tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncpg` raw SQL | SQLAlchemy ORM | ORM adds abstraction overhead; raw SQL tốt hơn cho queue patterns nhạy cảm với locking |
| `fastapi` | `starlette` bare | FastAPI thêm validation và docs; starlette nếu cần minimal footprint |
| `structlog` | `logging` stdlib | structlog xuất JSON natively, tốt hơn cho log aggregation; stdlib nếu muốn zero deps |

**Installation (uv):**
```bash
uv add fastapi uvicorn httpx tenacity asyncpg sqlalchemy alembic pydantic \
       presidio-analyzer presidio-anonymizer python-dotenv structlog

# Dev/test
uv add --dev pytest pytest-asyncio respx
```

---

## Package Legitimacy Audit

> Chạy slopcheck 0.6.1. Tất cả 10 package cốt lõi đều qua.

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| fastapi | PyPI | [OK] | Approved |
| httpx | PyPI | [OK] | Approved |
| tenacity | PyPI | [OK] | Approved |
| presidio-analyzer | PyPI | [OK] | Approved |
| presidio-anonymizer | PyPI | [OK] | Approved |
| asyncpg | PyPI | [OK] | Approved |
| sqlalchemy | PyPI | [OK] | Approved |
| alembic | PyPI | [OK] | Approved |
| pydantic | PyPI | [OK] | Approved |
| uvicorn | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Freshdesk
  │
  │  (1) Webhook POST (automation rule fires on ticket create/update)
  ▼
FastAPI Webhook Receiver
  │  verify HMAC-SHA256 sig, extract ticket_id
  │  return HTTP 200 immediately
  │
  ▼
Loop-Guard Pre-Check (in receiver or worker)
  │  RFC3834 headers? sender pattern? source/actor?
  ├─ YES (auto-reply) → mark processed, skip, log metric
  │
  ▼
Postgres Queue Table
  (ticket_id, inbound_msg_id, idempotency_key, status, attempts, ...)
  │  INSERT ON CONFLICT DO NOTHING  ← dedup at insert
  │
  ▼
Sequential Worker (single, D-11)
  │  SELECT ... FOR UPDATE SKIP LOCKED  ← claim one row
  │  Presidio redact ticket body before any persist/log
  │
  ├─ Phase 2: stub processing (canned reply content)
  ├─ Phase 4+: classify → extract → ground → draft
  │
  ▼
send_mode switch (D-05)
  ├─ dry-run → persist would-be action, do NOT call Freshdesk
  │
  └─ live-send →
        Freshdesk I/O Client (httpx + tenacity)
          POST /api/v2/tickets/{id}/reply  (public)
          POST /api/v2/tickets/{id}/notes  (private)
          │  honor X-RateLimit-*, Retry-After on 429
          │  retry 5× with exponential backoff + jitter
          ├─ success → mark row processed (idempotency_key)
          └─ exhausted → push to dead_letter table + emit alert

Reconciliation Poller (background, ~5–15 min)
  GET /api/v2/tickets?updated_since=...
  │  compute same idempotency_key per ticket
  └─ INSERT ON CONFLICT DO NOTHING → same queue (auto-dedup)
```

### Recommended Project Structure

```
src/
├── freshdesk_io/              # Module duy nhất được phép gọi Freshdesk API
│   ├── __init__.py
│   ├── client.py              # FreshdeskClient (httpx + tenacity)
│   ├── models.py              # Pydantic models: Ticket, Conversation, Reply, Note
│   └── rate_limit.py          # X-RateLimit-* header parsing, Retry-After wait
├── queue/
│   ├── __init__.py
│   ├── schema.sql             # hoặc Alembic migrations
│   ├── enqueue.py             # INSERT ON CONFLICT DO NOTHING
│   ├── worker.py              # SKIP LOCKED claim loop
│   └── dead_letter.py         # move exhausted rows to dead_letter table
├── webhook/
│   ├── __init__.py
│   ├── receiver.py            # FastAPI app, HMAC verify, enqueue
│   └── signature.py           # HMAC-SHA256 verification
├── poller/
│   ├── __init__.py
│   └── reconcile.py           # updated_since scan → enqueue
├── guards/
│   ├── __init__.py
│   ├── loop_guard.py          # RFC3834, sender patterns, source/actor check
│   └── pii.py                 # Presidio redaction wrapper
├── config.py                  # Settings (send_mode, DB URL, API key, ...)
└── main.py                    # Entry point: start webhook server + poller + worker
tests/
├── conftest.py                # asyncpg pool fixtures, respx mocks
├── test_client.py             # FreshdeskClient unit tests (respx)
├── test_queue.py              # SKIP LOCKED, dedup, dead-letter
├── test_webhook.py            # HMAC verify, enqueue flow
├── test_loop_guard.py         # RFC3834 headers, sender patterns
└── test_e2e_sandbox.py        # Smoke test vs real Freshdesk sandbox (skipped in CI)
docker-compose.yml             # Postgres 16 + pgvector (Phase 3 ready)
pyproject.toml
```

---

## Freshdesk REST API v2 — Chi tiết quan trọng

### Authentication
[VERIFIED: developers.freshdesk.com/api/]

Basic Auth: API key là username, bất kỳ string nào (thường là `X`) là password.

```python
# httpx
client = httpx.AsyncClient(
    auth=(FRESHDESK_API_KEY, "X"),
    base_url=f"https://{FRESHDESK_DOMAIN}.freshdesk.com"
)
```

### Endpoints chính

[VERIFIED: developers.freshdesk.com/api/]

| Operation | Endpoint | Content-Type |
|-----------|----------|--------------|
| Post public reply | `POST /api/v2/tickets/{id}/reply` | `application/json` (no attachments) hoặc `multipart/form-data` (có attachments) |
| Post private note | `POST /api/v2/tickets/{id}/notes` | `application/json` |
| Get conversations | `GET /api/v2/tickets/{id}/conversations` | — |
| Get ticket | `GET /api/v2/tickets/{id}` | — |
| List tickets (updated) | `GET /api/v2/tickets?updated_since=...` | — |

**Reply request body (JSON):**
```json
{
  "body": "<p>Reply content in HTML</p>",
  "from_email": "support@example.com",
  "cc_emails": ["cc@example.com"],
  "bcc_emails": []
}
```

**Note request body (JSON):**
```json
{
  "body": "<p>Internal note</p>",
  "private": true
}
```

### Rate Limits

[VERIFIED: developers.freshdesk.com/api/ + support.freshdesk.com/solutions/articles/225439]

| Plan | Calls/minute |
|------|-------------|
| Growth | 200 |
| Pro | 400 |
| Enterprise | 700 |
| Trial | 50 |

**Chú ý:** Có per-endpoint sub-limits. Ví dụ Growth plan's Ticket List endpoint capped ở ~20 calls/min, không phải full 200. Cần test trực tiếp để biết sub-limit cho reply endpoint.

**Rate limit headers trong mọi response:**
- `X-RateLimit-Total` — tổng calls được phép
- `X-RateLimit-Remaining` — còn lại trong window
- `X-RateLimit-Used-CurrentRequest` — calls consumed bởi request này
- `Retry-After` — seconds phải chờ khi bị rate-limited (429)

**HTTP status 429** khi vượt limit.

### Conversation Object Fields — Phân biệt nguồn message

[CITED: community.freshworks.dev/t/how-to-determine-if-conversation-is-from-agent-or-customer/2125]

| Field | Type | Ý nghĩa |
|-------|------|---------|
| `incoming` | boolean | `true` = customer reply (bao gồm cả từ portal); `false` = agent reply / AI reply / system |
| `private` | boolean | `true` = private note (không visible với customer); `false` = public |
| `user_id` | integer | ID của người tạo conversation entry (agent ID hoặc contact ID) |
| `from_email` | string | Email address của sender |
| `body` | string | Nội dung HTML |
| `body_text` | string | Nội dung plain text |
| `source` | integer | Numeric source code (email=1, portal=2, phone=3, chat=7, v.v.) |

**Logic phân biệt loại message:**

```
incoming=true  → customer reply (cần process)
incoming=false, private=false → agent/AI sent reply (bỏ qua)
incoming=false, private=true  → private note (bỏ qua)
```

**Hạn chế quan trọng [ASSUMED]:** Freshdesk v2 API không trả về explicit "actor_type" field (agent vs contact vs automation). Để biết AI reply vs human agent reply, phải: (a) giữ record AI đã send với conversation ID trong Postgres, hoặc (b) so sánh `user_id` với agent ID list. Cách (a) là chuẩn và không tốn thêm API calls.

**D-07 — Sync-echo detection [ASSUMED — cần verify qua sandbox]:**
Freshdesk source/actor field cho Selless-sync-originated updates chưa được xác nhận từ official docs. Community docs không đề cập. Cần gọi `GET /api/v2/tickets/{id}/conversations` sau khi Selless tạo một update để xem `user_id` và `from_email` thực tế. Nếu sync user có user_id cố định → dùng user_id whitelist/blacklist. Nếu không distinguish được → activate marker/tag fallback (deferred D-CONTEXT).

### Webhook Configuration

[CITED: support.freshdesk.com/support/solutions/articles/132589]

Freshdesk webhooks được config qua **Admin > Workflows > Automations** (không phải qua API). Hai event types:
- **Ticket Creation** — fires khi ticket mới được tạo
- **Ticket Updates** — fires khi ticket được update (bao gồm khi customer reply)

**Payload:** Freshdesk webhook payloads được config bởi admin — không có pre-defined fixed JSON schema. Admin chọn fields muốn include (Simple mode) hoặc viết custom template (Advanced mode). Do đó:

- **Không có HMAC signature native** trong Freshdesk webhook — authentication qua custom secret header (`X-Freshdesk-Secret` hoặc tương tự) hoặc shared token trong URL/header.
- Webhook payload nên include ít nhất: `ticket.id`, `ticket.status`, `ticket.updated_at`
- Để lấy conversation content, cần gọi `GET /api/v2/tickets/{id}/conversations` sau khi nhận webhook (webhook payload không tự động include conversation body)

**Webhook limitations:**
- 1000 calls/hour limit cho webhook trigger
- Failures retry mỗi 30 phút, tối đa 48 lần
- Webhook payload **không chứa custom ticket fields** — cần separate API call nếu cần

**Implication cho thiết kế:** Webhook receiver chỉ extract `ticket_id` từ payload, enqueue ngay, return 200. Worker sau đó gọi `GET /api/v2/tickets/{id}/conversations` để lấy conversation details — đây là "thin webhook + fat worker" pattern.

**Poller fallback (D-09):**
`GET /api/v2/tickets?updated_since={iso_timestamp}&per_page=100` — scan mọi tickets updated sau window. Cùng idempotency key → auto-dedup với webhook path.

---

## Postgres Queue Pattern — Chi tiết implementation

### Schema thiết kế (Claude's Discretion)

```sql
-- Queue chính
CREATE TABLE ticket_queue (
    id              BIGSERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL,          -- ticket_id + ':' + inbound_msg_id
    ticket_id       INTEGER NOT NULL,
    inbound_msg_id  INTEGER NOT NULL,       -- Freshdesk conversation ID
    payload         JSONB NOT NULL,         -- redacted ticket snapshot
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|claimed|done|suppressed
    claimed_at      TIMESTAMPTZ,
    claimed_by      TEXT,                   -- worker instance ID
    claim_token     UUID,                   -- prevents stale worker finalization
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error      TEXT,
    last_error_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dedup constraint: cùng inbound → chỉ một row
CREATE UNIQUE INDEX idx_ticket_queue_idempotency
    ON ticket_queue (idempotency_key);

-- Worker scan index
CREATE INDEX idx_ticket_queue_pending
    ON ticket_queue (status, next_attempt_at)
    WHERE status = 'pending';

-- Dead-letter (exhausted)
CREATE TABLE dead_letter (
    id              BIGSERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    ticket_id       INTEGER NOT NULL,
    inbound_msg_id  INTEGER NOT NULL,
    payload         JSONB NOT NULL,
    attempts        INTEGER NOT NULL,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alerted         BOOLEAN NOT NULL DEFAULT FALSE
);
```

### Atomic SKIP LOCKED claim

[CITED: dev.to/daniel_romitelli_44e77dc6 — SKIP LOCKED pattern]

```sql
-- Worker claim (trong một transaction)
WITH to_claim AS (
    SELECT id FROM ticket_queue
    WHERE status = 'pending'
      AND next_attempt_at <= NOW()
      AND attempts < max_attempts
    ORDER BY next_attempt_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE ticket_queue
SET status      = 'claimed',
    claimed_at  = NOW(),
    claimed_by  = $1,          -- worker instance ID
    claim_token = gen_random_uuid(),
    updated_at  = NOW()
FROM to_claim
WHERE ticket_queue.id = to_claim.id
RETURNING ticket_queue.*;
```

### Enqueue (INSERT ON CONFLICT DO NOTHING — dedup tại insert)

```sql
INSERT INTO ticket_queue
    (idempotency_key, ticket_id, inbound_msg_id, payload)
VALUES ($1, $2, $3, $4)
ON CONFLICT (idempotency_key) DO NOTHING;
-- Returns 0 rows affected nếu duplicate → bỏ qua silently
```

### Finalization (token-checked)

```sql
-- Success
UPDATE ticket_queue
SET status = 'done', claim_token = NULL, updated_at = NOW()
WHERE id = $1 AND claim_token = $2;
-- Nếu 0 rows → stale worker, bỏ qua

-- Failure + schedule retry với backoff
UPDATE ticket_queue
SET status          = 'pending',
    claimed_at      = NULL,
    claim_token     = NULL,
    attempts        = attempts + 1,
    last_error      = $2,
    last_error_at   = NOW(),
    next_attempt_at = NOW() + ($3::int || ' seconds')::interval,
    updated_at      = NOW()
WHERE id = $1 AND claim_token = $4;

-- Exhaustion → dead-letter
INSERT INTO dead_letter (idempotency_key, ticket_id, inbound_msg_id, payload, attempts, last_error)
SELECT idempotency_key, ticket_id, inbound_msg_id, payload, attempts, last_error
FROM ticket_queue WHERE id = $1;

UPDATE ticket_queue SET status = 'dead_lettered', updated_at = NOW() WHERE id = $1;
```

### Stale claim recovery

```sql
-- Chạy định kỳ (e.g., mỗi 10 phút) để recover stale claims
UPDATE ticket_queue
SET status      = 'pending',
    claimed_at  = NULL,
    claimed_by  = NULL,
    claim_token = NULL,
    last_error  = COALESCE(last_error, 'stale claim recovered'),
    last_error_at = NOW(),
    updated_at  = NOW()
WHERE status = 'claimed'
  AND claimed_at < NOW() - INTERVAL '10 minutes';
```

---

## httpx + tenacity — Retry Pattern

### Error Classification (Claude's Discretion)

| HTTP Status | Classification | Action |
|-------------|---------------|--------|
| 429 | Transient | Retry, honor `Retry-After` header |
| 500, 502, 503, 504 | Transient | Retry với exponential backoff |
| Timeout / ConnectionError | Transient | Retry |
| 401, 403 | Fatal | Straight to dead-letter (config error) |
| 404 | Fatal | Straight to dead-letter (ticket không tồn tại) |
| 400 | Fatal | Straight to dead-letter (bad request — code bug) |
| 409 | Context-dependent | Check response body; thường là idempotency conflict |

### Tenacity pattern với Retry-After

[CITED: tenacity.readthedocs.io, callsphere.ai/blog/retry-strategies-llm-api-calls]

```python
import asyncio
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    RetryError,
)

class FreshdeskRateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after

class FreshdeskFatalError(Exception):
    """404, 403, 400 — không retry"""

def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, FreshdeskRateLimitError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False

def freshdesk_wait(retry_state):
    """Honor Retry-After nếu có, otherwise exponential backoff với jitter."""
    exc = retry_state.outcome.exception()
    if isinstance(exc, FreshdeskRateLimitError):
        return exc.retry_after
    # exponential: base=1s, cap=60s, jitter=±1s
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    import random
    return base + random.uniform(-1, 1)

@retry(
    stop=stop_after_attempt(5),
    wait=freshdesk_wait,
    retry=retry_if_exception_type((FreshdeskRateLimitError, httpx.HTTPStatusError, httpx.TransportError)),
    reraise=True,
)
async def post_reply(client: httpx.AsyncClient, ticket_id: int, body: str) -> dict:
    response = await client.post(
        f"/api/v2/tickets/{ticket_id}/reply",
        json={"body": body},
        timeout=30.0,
    )
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise FreshdeskRateLimitError(retry_after)
    if response.status_code in (401, 403, 404, 400):
        raise FreshdeskFatalError(f"HTTP {response.status_code}: {response.text}")
    response.raise_for_status()
    return response.json()
```

---

## Loop/Auto-Reply Guard — D-06

### Signal Layer 1: RFC 3834 Email Headers

[CITED: arp242.net/autoreply.html, datatracker.ietf.org/doc/html/rfc3834]

```python
AUTO_REPLY_HEADERS = {
    "Auto-Submitted": lambda v: v.lower() != "no",
    "Precedence": lambda v: v.lower() in ("bulk", "list", "junk", "auto_reply"),
    "X-Auto-Response-Suppress": lambda v: any(
        x in v.upper() for x in ("DR", "AUTOREPLY", "ALL")
    ),
    "X-Loop": lambda _: True,
    "X-Autoreply": lambda _: True,
    "X-MSFBL": lambda _: True,
    "Feedback-ID": lambda _: True,
}
LIST_HEADERS = ["List-Id", "List-Unsubscribe", "List-Post", "List-Owner", "List-Archive"]

def is_auto_reply_by_headers(headers: dict) -> bool:
    for header, check in AUTO_REPLY_HEADERS.items():
        if header in headers and check(headers[header]):
            return True
    for lh in LIST_HEADERS:
        if lh in headers:
            return True
    # Empty Return-Path → bounce/system
    if "Return-Path" in headers and headers["Return-Path"].strip() in ("", "<>"):
        return True
    return False
```

**Chú ý:** Freshdesk lưu email headers của inbound emails — nhưng cần kiểm tra xem GET /api/v2/tickets/{id} có trả về raw email headers hay không. Nếu không có → dựa vào layer 2-4.

### Signal Layer 2: Sender Patterns

```python
import re

NO_REPLY_PATTERN = re.compile(
    r"^(no[._-]?reply|noreply|mailer-daemon|postmaster|bounce[+-]|"
    r"return-path|auto-confirm|do-not-reply)@",
    re.IGNORECASE
)

def is_auto_reply_by_sender(from_email: str) -> bool:
    return bool(NO_REPLY_PATTERN.match(from_email))
```

### Signal Layer 3: Freshdesk Source/Actor

[CITED: community.freshworks.dev — incoming field]

```python
def is_real_customer_conversation(conv: dict) -> bool:
    """
    True nếu đây là customer reply cần process.
    False nếu là agent reply, AI reply, system message.
    """
    # incoming=True: customer reply (kể cả từ portal)
    if not conv.get("incoming", False):
        return False  # agent reply, AI reply, hoặc system note
    # Thêm check: không phải private note
    if conv.get("private", False):
        return False
    return True
```

### Signal Layer 4: Selless-Sync Origin [ASSUMED]

Phương pháp chính (D-07): So sánh `user_id` của conversation với Selless sync integration user ID (cấu hình trong config). Nếu match → đây là sync-originated update → skip.

```python
SELLESS_SYNC_USER_IDS: set[int] = set(config.selless_sync_user_ids)  # từ config

def is_selless_sync(conv: dict) -> bool:
    return conv.get("user_id") in SELLESS_SYNC_USER_IDS
```

**[ASSUMED]:** User ID cụ thể của Selless sync integration trên Freshdesk account cần xác nhận qua sandbox.

---

## FastAPI Webhook Receiver Pattern

[CITED: neon.com/guides/fastapi-webhooks]

```python
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, Header
from typing import Optional

app = FastAPI()

SECRET = config.webhook_secret.encode()

def verify_freshdesk_signature(body: bytes, signature: str) -> bool:
    """
    Freshdesk không có native HMAC. Dùng shared secret trong custom header.
    Recommendation: dùng HMAC-SHA256 với secret token trong X-Freshdesk-Signature.
    """
    expected = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.post("/webhook/freshdesk")
async def freshdesk_webhook(
    request: Request,
    x_freshdesk_signature: Optional[str] = Header(None),
):
    body = await request.body()
    
    # 1. Verify signature (nếu configured)
    if config.webhook_secret and not verify_freshdesk_signature(body, x_freshdesk_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 2. Parse payload — chỉ cần ticket_id
    payload = await request.json()
    ticket_id = payload.get("ticket", {}).get("id") or payload.get("ticket_id")
    
    if not ticket_id:
        return {"status": "ignored", "reason": "no ticket_id"}
    
    # 3. Enqueue (idempotency key computed later by worker after fetching conversations)
    # Lưu ý: webhook payload không include inbound_msg_id → worker fetch rồi compute key
    await enqueue_ticket_for_fetch(ticket_id=ticket_id)
    
    # 4. Return 200 ngay lập tức
    return {"status": "queued"}
```

**Hai-bước approach cho idempotency key:**
1. Webhook chỉ biết `ticket_id` → enqueue "fetch ticket conversations" task
2. Worker fetch conversations → tìm latest `incoming=True` conversation → compute `idempotency_key = f"{ticket_id}:{conv_id}"` → insert với ON CONFLICT DO NOTHING

---

## PII Redaction với Presidio

[CITED: microsoft.github.io/presidio]

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

REDACT_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "US_PASSPORT", "LOCATION", "IP_ADDRESS", "URL",
]

def redact_text(text: str) -> str:
    """
    Redact PII trước khi persist vào DB hay log.
    Returns text với PII replaced bởi entity type tags, e.g. <EMAIL_ADDRESS>.
    """
    if not text:
        return text
    results = analyzer.analyze(text=text, entities=REDACT_ENTITIES, language="en")
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text

# Usage: Gọi trước bất kỳ DB insert hay log statement nào chứa ticket content
redacted_body = redact_text(ticket.body_text)
logger.info("processing_ticket", ticket_id=ticket_id, body_preview=redacted_body[:100])
```

**Lưu ý quan trọng:** Presidio dùng spaCy NER model — cần `python -m spacy download en_core_web_lg` (hoặc `en_core_web_sm` để nhẹ hơn). Cần include trong setup script.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry/backoff/jitter | Custom retry decorator | `tenacity` | Edge cases: Retry-After parsing, jitter math, async compatibility |
| PII detection | Regex-based PII scanner | `presidio-analyzer` | NER + regex hybrid; 30+ entity types; tốt hơn regex đơn giản cho email |
| Queue concurrency | Advisory locks / application-level locking | `SELECT ... FOR UPDATE SKIP LOCKED` | PostgreSQL-native, deadlock-free, tested ở scale |
| HMAC verification | Custom comparison | `hmac.compare_digest` | Prevents timing attacks; bắt buộc cho security |
| Async HTTP | `requests` với threading | `httpx` | Native async; tương thích event loop |
| DB migrations | Manual SQL scripts | `alembic` | Phase 3 cũng cần add pgvector; consistent migration history |
| Structured logging | `print()` / stdlib logging | `structlog` | JSON-native; processors pipeline; không cần change log calls khi thay format |

**Key insight:** Postgres queue pattern (SKIP LOCKED) đủ mạnh cho 900–3000 emails/day mà không cần Redis, Celery, hay SQS. Giữ một datastore.

---

## Common Pitfalls

### Pitfall 1: Webhook Payload Không Có Conversation Body
**What goes wrong:** Code assume webhook payload chứa full ticket/conversation content → KeyError hoặc empty body khi process.
**Why it happens:** Freshdesk webhook payload là customizable template; conversation body không tự động included; phải gọi API separate để lấy.
**How to avoid:** Worker luôn gọi `GET /api/v2/tickets/{id}/conversations` sau khi claim queue row, không dùng webhook payload cho content.
**Warning signs:** `body` field trống trong log sau khi nhận webhook.

### Pitfall 2: Idempotency Key Race — Webhook và Poller Đồng Thời
**What goes wrong:** Webhook và poller đều enqueue cùng ticket_id trước khi conversation fetch xong → có thể tạo ra hai `inbound_msg_id` khác nhau nếu conversations đã thay đổi.
**Why it happens:** Thứ tự fetch conversations không deterministic nếu có nhiều inbound messages.
**How to avoid:** Idempotency key phải dựa trên `conv.id` của **latest incoming conversation**, không phải ticket-level. Worker fetch conversations sau claim, pick latest incoming, compute key, check processed table trước khi post.
**Warning signs:** Duplicate replies trong Freshdesk ticket history.

### Pitfall 3: Freshdesk `incoming=False` Nhưng Không Phải AI Reply
**What goes wrong:** Code bỏ qua mọi `incoming=False` → agent reply bị skip đúng, nhưng cũng bỏ qua cases cần quan tâm (e.g., agent forward, system escalation note).
**Why it happens:** Binary `incoming` field không phân biệt mọi actor types.
**How to avoid:** Phase 2 chỉ process `incoming=True` conversations; đây là đủ cho "reply to customer message" use case. Track AI reply bằng cách lưu reply conversation ID vào processed table.
**Warning signs:** Không applicable cho Phase 2 scope.

### Pitfall 4: Stale Claim Worker Crash
**What goes wrong:** Worker claim row, crash trước khi finalize → row bị stuck ở status='claimed' mãi mãi.
**Why it happens:** Không có lease timeout mechanism.
**How to avoid:** Stale claim recovery query chạy định kỳ (xem schema pattern). Claim token ensures chỉ owner hiện tại mới finalize.
**Warning signs:** Rows stuck ở `claimed` status > 10 phút.

### Pitfall 5: Presidio spaCy Model Không Được Install
**What goes wrong:** `AnalyzerEngine()` fail lúc startup với model not found error.
**Why it happens:** `presidio-analyzer` package cần spaCy English model riêng.
**How to avoid:** Thêm vào setup: `python -m spacy download en_core_web_lg`. Include trong Dockerfile và setup docs.
**Warning signs:** `OSError: [E050] Can't find model 'en_core_web_lg'` at startup.

### Pitfall 6: Freshdesk Rate Limit Không Honor Retry-After
**What goes wrong:** Code retry ngay sau 429 → tiếp tục bị 429 → queue bị stuck.
**Why it happens:** Tenacity mặc định dùng exponential backoff, không đọc `Retry-After` header.
**How to avoid:** Custom `wait` function trong tenacity check `Retry-After` header, dùng `max(retry_after, calculated_backoff)`.
**Warning signs:** Log thấy nhiều 429 liên tiếp trong thời gian ngắn.

### Pitfall 7: Webhook Payload Template Không Được Configure
**What goes wrong:** Freshdesk gửi webhook nhưng payload rỗng hoặc không có `ticket.id` field.
**Why it happens:** Freshdesk webhook payload là template do admin configure — mặc định có thể không có fields cần thiết.
**How to avoid:** Document rõ webhook payload config cần thiết (minimum: ticket ID). Include trong sandbox setup checklist.
**Warning signs:** `ticket_id` = None trong webhook receiver log.

---

## Code Examples

### Pattern 1: Enqueue với Dedup

```python
# Source: Postgres SKIP LOCKED pattern (verified via official Postgres docs + community)
async def enqueue_ticket(
    conn: asyncpg.Connection,
    ticket_id: int,
    inbound_msg_id: int,
    redacted_payload: dict,
) -> bool:
    """Returns True nếu enqueued, False nếu duplicate (already exists)."""
    idempotency_key = f"{ticket_id}:{inbound_msg_id}"
    result = await conn.execute(
        """
        INSERT INTO ticket_queue
            (idempotency_key, ticket_id, inbound_msg_id, payload)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        idempotency_key, ticket_id, inbound_msg_id, redacted_payload
    )
    return result == "INSERT 0 1"
```

### Pattern 2: Worker Claim Loop (Sequential, D-11)

```python
import asyncio
import uuid

async def worker_loop(pool: asyncpg.Pool, worker_id: str):
    while True:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    WITH to_claim AS (
                        SELECT id FROM ticket_queue
                        WHERE status = 'pending'
                          AND next_attempt_at <= NOW()
                          AND attempts < max_attempts
                        ORDER BY next_attempt_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE ticket_queue
                    SET status      = 'claimed',
                        claimed_at  = NOW(),
                        claimed_by  = $1,
                        claim_token = $2,
                        updated_at  = NOW()
                    FROM to_claim
                    WHERE ticket_queue.id = to_claim.id
                    RETURNING ticket_queue.*
                    """,
                    worker_id, str(uuid.uuid4())
                )
        
        if row is None:
            await asyncio.sleep(5)  # idle sleep
            continue
        
        await process_queue_row(pool, row)
```

### Pattern 3: Send Mode Switch (D-05)

```python
from enum import Enum

class SendMode(str, Enum):
    DRY_RUN = "dry_run"
    LIVE = "live"

async def send_reply(
    client: FreshdeskClient,
    conn: asyncpg.Connection,
    ticket_id: int,
    body: str,
    mode: SendMode,
) -> dict:
    if mode == SendMode.DRY_RUN:
        # Persist would-be action, do NOT call Freshdesk
        await conn.execute(
            "INSERT INTO dry_run_log (ticket_id, body, created_at) VALUES ($1, $2, NOW())",
            ticket_id, body
        )
        return {"dry_run": True, "ticket_id": ticket_id}
    
    # live-send
    return await client.post_reply(ticket_id=ticket_id, body=body)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Redis queue (Celery/RQ) | Postgres SKIP LOCKED | Một datastore; transactional idempotency; Phase 3 extension tự nhiên |
| `requests` với `urllib3` Retry | `httpx` async + `tenacity` | Async-native; custom wait strategies; Retry-After support |
| Manual migration SQL | Alembic | Phase 3 pgvector cũng dùng Alembic; consistent history |
| Regex-only PII | Presidio (NER + regex hybrid) | 30+ entity types; context-aware detection |
| Webhook-only (no reconciliation) | Webhook primary + poller reconciliation | Không mất events nếu webhook missed |

**Deprecated/outdated:**
- `requests` library: sync-only, không fit async worker pattern
- `celery` với Redis: overkill cho ~900 emails/day; adds Redis operational cost

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Freshdesk conversation `incoming=True` là đủ để identify customer reply | Architecture Patterns, Loop Guard | Nếu sai: AI có thể reply vào system messages hoặc agent notes |
| A2 | Selless sync user có unique Freshdesk `user_id` có thể whitelist | D-07 sync detection | Nếu sai: cần implement marker/tag fallback (deferred, extra work) |
| A3 | Freshdesk không có native HMAC webhook signature | Webhook receiver | Nếu có: bỏ qua custom header approach, dùng built-in |
| A4 | Freshdesk raw email headers (Auto-Submitted, Precedence) exposed qua API | Loop guard layer 1 | Nếu không exposed: layer 1 không hoạt động, chỉ dùng layer 2-4 |
| A5 | spaCy `en_core_web_lg` model đủ accurate cho PII detection trong support emails | PII redaction | Nếu không đủ: upgrade model hoặc thêm custom recognizers |

---

## Open Questions

1. **D-07: Freshdesk source/actor cho Selless-sync updates**
   - What we know: `incoming=False` filter sẽ bỏ qua agent/AI replies; nhưng Selless sync có thể tạo `incoming=True` fake customer replies
   - What's unclear: User ID của Selless sync integration agent trên Freshdesk sandbox account cụ thể
   - Recommendation: Kiểm tra qua sandbox ngay đầu Phase 2 — gọi GET /conversations sau khi Selless sync tạo update, log `user_id` và `from_email`
   - **(RESOLVED: handled by 02-04 Task 3 `checkpoint:human-verify`. Loop-guard layer 4 (`is_selless_sync`) ships với source/actor user_id-whitelist làm default code path; checkpoint chỉ CONFIRM trên sandbox. Nếu source/actor không phân biệt được → marker/tag fallback (deferred CONTEXT idea) kích hoạt như follow-up, KHÔNG block Wave 3 — xem 02-04 Task 3 wave note.)**

2. **Freshdesk raw email headers qua API**
   - What we know: Freshdesk lưu inbound email headers nội bộ
   - What's unclear: API v2 có expose raw email headers (Auto-Submitted, Precedence, List-*) trong conversation/ticket response không
   - Recommendation: Kiểm tra GET /api/v2/tickets/{id} response để xem có `email_config_id` hay raw headers field
   - **(RESOLVED: loop-guard layer 1 (`is_auto_reply_by_headers` trong 02-04 Task 1) degrade gracefully khi headers=None — per Assumption A4. Nếu API không expose raw headers, layers 2–4 (sender pattern + incoming/private + Selless-sync) vẫn chặn auto-reply. Khả năng expose headers được xác nhận tại resolve-step của 02-05 khi gọi GET /conversations.)**

3. **Webhook payload template cụ thể cần config**
   - What we know: Freshdesk webhook payload là configurable template
   - What's unclear: Minimum fields cần include; có include conversation data không
   - Recommendation: Document sandbox webhook config exact template trong Wave 0 setup task
   - **(RESOLVED: minimum payload field = `ticket.id` only — webhook KHÔNG cần conversation body vì 02-05 resolve-step fetch `GET /conversations` để lấy latest inbound message id trước khi enqueue (Pitfall 1). Webhook payload template được document trong 02-01 README/setup + xác nhận tại 02-06 Task 3 sandbox demo.)**

4. **Per-endpoint sub-limits cho reply endpoint**
   - What we know: Enterprise plan = 700/min global; nhưng có per-endpoint sub-limits
   - What's unclear: Exact sub-limit cho POST /reply endpoint
   - Recommendation: Test bằng cách gửi rapid requests vào sandbox; hoặc contact Freshdesk support
   - **(RESOLVED: handled by generic Retry-After/backoff path trong 02-02 (`parse_retry_after` + tenacity wait honor `Retry-After`) và 02-06 Task 1 (`test_retry_after_honored`). Bất kể sub-limit cụ thể, 429 trả `Retry-After` được honor; exact sub-limit verify trên sandbox tại 02-06 Task 3 — không phải blocker vì backoff path là endpoint-agnostic.)**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All code | ✓ | 3.14.5 | — |
| uv | Package management | ✗ (not found in PATH) | — | pip + venv |
| Docker | Local Postgres via docker-compose | ✗ (not in PATH) | — | Install Docker Desktop; hoặc dùng local Postgres |
| PostgreSQL | Queue + state | ✗ (pg_isready not found) | — | Cần Docker hoặc install Postgres locally |
| Freshdesk sandbox account | D-03 demo, D-07 verify | ✓ (confirmed available per CONTEXT) | — | — |
| Freshdesk API key | All Freshdesk calls | ✓ (confirmed available per CONTEXT) | — | — |
| Freshdesk webhook config access | D-09 webhook setup | ✓ (confirmed available per CONTEXT) | — | — |

**Missing dependencies với no fallback:** PostgreSQL cần được cài (via Docker hoặc local). Docker là cách đơn giản nhất — planner cần include Wave 0 task để setup Docker + docker-compose.

**Missing dependencies với fallback:**
- `uv`: Có thể dùng `pip + venv` nếu uv chưa install; nhưng nên install uv trước (CLAUDE.md mandated).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` (Wave 0 — chưa tồn tại) |
| Quick run command | `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REP-05 | Post reply vào đúng ticket, idempotent (no duplicate) | integration | `pytest tests/test_client.py tests/test_queue.py -x` | ❌ Wave 0 |
| REP-05 | Retry does not double-send | integration | `pytest tests/test_queue.py::test_idempotency -x` | ❌ Wave 0 |
| REP-05 | Rate limit honored, Retry-After respected | unit | `pytest tests/test_client.py::test_retry_after -x` | ❌ Wave 0 |
| D-06/D-07 | Loop guard detects auto-reply headers | unit | `pytest tests/test_loop_guard.py -x` | ❌ Wave 0 |
| D-03 | Sandbox smoke: real POST to Freshdesk | smoke (manual/optional) | `pytest tests/test_e2e_sandbox.py -m sandbox` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q`
- **Per wave merge:** full suite
- **Phase gate:** Full suite green + sandbox smoke test pass trước `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — asyncpg pool fixtures, respx mocks, test DB setup
- [ ] `tests/test_client.py` — FreshdeskClient unit tests (respx mock)
- [ ] `tests/test_queue.py` — SKIP LOCKED dedup, idempotency, dead-letter, stale recovery
- [ ] `tests/test_webhook.py` — HMAC verify, enqueue flow
- [ ] `tests/test_loop_guard.py` — RFC3834 headers, sender patterns, source/actor
- [ ] `tests/test_e2e_sandbox.py` — Real Freshdesk sandbox smoke tests
- [ ] `pyproject.toml` — pytest config, dependency declarations (uv)
- [ ] `docker-compose.yml` — Postgres 16 (pgvector-ready) + local dev setup
- [ ] spaCy model install: `python -m spacy download en_core_web_lg`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (Freshdesk API) | API key via Basic Auth over HTTPS only |
| V3 Session Management | no | Stateless worker |
| V4 Access Control | yes | Webhook signature verification; read-only Freshdesk access except reply/note endpoints |
| V5 Input Validation | yes | Pydantic models cho webhook payload; Presidio redact trước persist |
| V6 Cryptography | yes | HMAC-SHA256 với `hmac.compare_digest` (constant-time) cho webhook |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Webhook spoofing (fake Freshdesk events) | Spoofing | HMAC-SHA256 verification với shared secret |
| Reply injection qua ticket body | Tampering | Treat ticket body as data (không eval/execute); Presidio strip PII |
| Rate limit exhaustion / runaway loop | Denial of Service | Bounded retries (D-10); loop guard (D-06); dead-letter on exhaustion |
| PII leak vào logs | Information Disclosure | Presidio redact trước bất kỳ log/persist; CLAUDE.md rule |
| Stale API key exposure | Information Disclosure | API key chỉ trong env vars / secrets; không commit vào git |
| Duplicate reply spam | Tampering | Idempotency key (D-02) + ON CONFLICT DO NOTHING; dry-run default (D-05) |

---

## Sources

### Primary (HIGH confidence)
- `developers.freshdesk.com/api/` — Reply endpoint, Note endpoint, rate limit headers, auth mechanism, conversation fields
- `support.freshdesk.com/solutions/articles/225439` — Rate limits per plan (200/400/700/min)
- `support.freshdesk.com/solutions/articles/132589` — Webhook automation configuration
- PyPI registry — Tất cả package versions verified trực tiếp (pip index versions)
- `datatracker.ietf.org/doc/html/rfc3834` — Auto-Submitted header spec
- `arp242.net/autoreply.html` — Comprehensive auto-reply header detection guide

### Secondary (MEDIUM confidence)
- `community.freshworks.dev/t/how-to-determine-if-conversation-is-from-agent-or-customer/2125` — `incoming` field semantics
- `dev.to/daniel_romitelli...` — SKIP LOCKED table design + claim/unclaim patterns
- `tenacity.readthedocs.io` — Tenacity retry API
- `neon.com/guides/fastapi-webhooks` — FastAPI webhook + asyncpg pattern
- `truto.one/blog/how-to-integrate-with-the-freshdesk-api-2026-engineering-guide/` — Rate limit per-endpoint sub-limits

### Tertiary (LOW confidence — cần verify qua sandbox)
- D-07: Selless sync user_id trong Freshdesk conversation — không tìm thấy official docs; cần sandbox verification
- Freshdesk webhook native HMAC signature — không confirmed từ official docs; assumed không có
- Raw email headers trong API response — không confirmed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tất cả packages verified trên PyPI, slopcheck OK
- Freshdesk API endpoints: HIGH — verified từ official docs
- Freshdesk rate limits: HIGH — verified từ official support article
- Conversation field semantics (`incoming`): MEDIUM — từ community forum, chưa verified qua sandbox
- Webhook signature mechanism: MEDIUM — pattern documented nhưng Freshdesk-specific mechanism chưa confirmed
- D-07 sync-echo detection: LOW — cần sandbox test

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (Freshdesk API stable; packages stable)
