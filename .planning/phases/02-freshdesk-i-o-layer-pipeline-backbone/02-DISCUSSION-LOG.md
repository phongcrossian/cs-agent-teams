# Phase 2: Freshdesk I/O Layer & Pipeline Backbone - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 2-freshdesk-i-o-layer-pipeline-backbone
**Areas discussed:** Queue & state backend, Phase 2 end-state, Loop/auto-reply guard, Freshdesk test environment, Webhook vs poller, Retry/dead-letter, Worker concurrency/ordering, PII redaction & tracing

---

## Queue & State Backend

| Option | Description | Selected |
|--------|-------------|----------|
| Postgres-backed | Single Postgres as queue (`SKIP LOCKED`) + idempotency/dead-letter store; reuse for pgvector Phase 3 | ✓ |
| Redis + worker lib | Redis broker + Arq/RQ/Celery; second datastore to operate | |
| Cloud-managed (SQS…) | Managed queue + dedup table; vendor lock, overkill for current volume | |

**User's choice:** Postgres-backed.
**Notes:** Chosen for single-datastore simplicity and reuse with Phase 3 pgvector.

### Idempotency key

| Option | Description | Selected |
|--------|-------------|----------|
| ticket_id + inbound message id | Stable across webhook & poller (same ticket state → same key) | ✓ |
| webhook event/delivery id | Only dedups webhook fire; misses poller-picked duplicate | |
| hash(ticket_id + body + time) | Content hash; fragile to normalization differences | |

**User's choice:** ticket_id + inbound message id.

---

## Phase 2 End-State

| Option | Description | Selected |
|--------|-------------|----------|
| Private note into ticket | Post internal note (customer can't see); safest demo | |
| Canned reply in sandbox | Post public reply to isolated Freshdesk sandbox; proves real reply path | ✓ |
| Draft-only, no post | Persist placeholder, never call Freshdesk; doesn't verify criterion #2 on real system | |

**User's choice:** Canned reply in sandbox.
**Notes:** Implies a sandbox account is used (confirmed available later). Reply-public path proven on real Freshdesk.

### Send-mode switch

| Option | Description | Selected |
|--------|-------------|----------|
| Config-driven, default safe | dry-run ↔ live-send flag, default dry-run; seed of Phase 6 kill-switch | ✓ |
| No switch, keep minimal | Always post; only sandbox protects | |
| Switch now, UI in Phase 6 | Build flag mechanism now, dashboard/kill-switch UI in Phase 6 | |

**User's choice:** Config-driven, default = dry-run. Client exposes both reply (public) and note (private).

---

## Loop / Auto-Reply Guard

| Option | Description | Selected |
|--------|-------------|----------|
| Standard email headers | Auto-Submitted, Precedence, List-*, X-Auto-Response-Suppress, empty Return-Path | ✓ |
| Sender patterns | no-reply@, mailer-daemon@, postmaster@, bounce addresses | ✓ |
| Freshdesk source/actor | Only reply to real incoming-customer messages; skip agent/system/AI-own | ✓ |
| Selless-sync origin | Detect sync-originated echo updates | ✓ |

**User's choice:** All four layers (defense-in-depth).

### Sync-echo detection

| Option | Description | Selected |
|--------|-------------|----------|
| Both: allowlist + marker | Customer-origin allowlist + marker stamp on system outbound | |
| Freshdesk source/actor only | Whitelist incoming-from-customer; sync-user treated as non-customer | ✓ |
| Marker/tag only | Self-controlled marker; misses externally-created sync updates | |

**User's choice:** Freshdesk source/actor only.
**Notes:** RESEARCH FLAG — verify Freshdesk stamps a distinguishable source/actor on Selless-sync updates; fall back to marker/tag if not.

### Suppression action

| Option | Description | Selected |
|--------|-------------|----------|
| Skip + log/metric | Mark processed, don't post, emit log+metric; not dead-letter | ✓ |
| Skip + private note | Also post internal note explaining the skip | |
| Skip silently | No record; loses observability/audit | |

**User's choice:** Skip + log/metric.

---

## Freshdesk Test Environment

| Option | Description | Selected |
|--------|-------------|----------|
| Sandbox + mock in CI | Mock HTTP in CI (fast, no network); real verify on isolated sandbox | ✓ |
| Test ticket+group on live | No sandbox; isolated group on live account; higher risk | |
| Mock-only | No sandbox; contradicts sandbox-demo decision | |

**User's choice:** Sandbox + mock HTTP in CI.

### Prerequisites available (no blockers)

| Item | Available |
|------|-----------|
| Freshdesk sandbox account | ✓ |
| API key with reply scope | ✓ |
| Webhook configuration access | ✓ |
| Selless-sync source/actor knowledge | ✓ |

---

## Webhook vs Poller

| Option | Description | Selected |
|--------|-------------|----------|
| Webhook primary + periodic poller | Webhook low-latency; poller reconciles (~5–15 min, configurable) | ✓ |
| Poller primary | Poll only; higher latency, more API load | |
| Webhook only | Low latency but no reconciliation; violates criterion #1 | |

**User's choice:** Webhook primary + periodic reconciliation poller.

---

## Retry / Dead-Letter

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded backoff + alert | ~5 retries, exp backoff + jitter, honor Retry-After; then dead-letter + alert | ✓ |
| Transient vs fatal classification | Smarter: retry 429/5xx/timeout, fatal 4xx straight to dead-letter | |
| Infinite retry + alert | Retry until success; runaway risk | |

**User's choice:** Bounded backoff + alert.
**Notes:** Transient/fatal classification folded into Claude's discretion as a sensible default.

---

## Worker Concurrency / Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| N workers + per-ticket lock | Parallel throughput with per-ticket lock to prevent same-ticket races | |
| Single sequential worker | Simplest, no races, sufficient for ~900/day | ✓ |
| N workers, no ticket lock | Max parallelism, relies on idempotency key only; ordering race risk | |

**User's choice:** Single sequential worker (Phase 2). `SKIP LOCKED` design leaves the door open to scale later.

---

## PII Redaction & Tracing

| Option | Description | Selected |
|--------|-------------|----------|
| Redact PII now, tracing minimal | Presidio before any log/persist; structured logs+metrics; Langfuse deferred | ✓ |
| Wire Presidio + Langfuse now | Full observability stack from Phase 2 | |
| Defer both | Raw logging; violates CLAUDE.md no-raw-ticket-text rule | |

**User's choice:** Redact PII (Presidio) from Phase 2; tracing minimal, Langfuse deferred to Phase 4/5.

---

## Claude's Discretion

- HTTP error classification taxonomy (transient/retryable vs fatal/straight-to-dead-letter)
- Postgres table/schema design for queue, idempotency/processed, dead-letter
- Webhook receiver framework (e.g. FastAPI) + deployment shape
- Poller exact cadence (within ~5–15 min); backoff base/cap/jitter values
- I/O client + worker module/directory layout

## Deferred Ideas

- Scale-out N-worker model with per-ticket lock (revisit on volume growth)
- Full Langfuse tracing / observability dashboard (Phase 4/5 and Phase 6)
- Marker/tag-based sync-echo detection (fallback for D-07)
- Transient-vs-fatal error classification refinement
- Channel scope vs volume project-level re-check (Email 30% vs Contact Form 60%) — for `/gsd:complete-milestone`
