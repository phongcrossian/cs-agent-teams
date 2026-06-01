# Phase 2: Freshdesk I/O Layer & Pipeline Backbone - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the **only module allowed to talk to Freshdesk** plus the queued, stateless intake it feeds. This phase centralizes: rate-limit handling, the **reply (public) vs note (private)** distinction, and the **idempotency / loop guards** that prevent duplicate or runaway sends. Maps to requirement **REP-05** (post the approved reply into the correct existing Freshdesk ticket via API, idempotently — no duplicate sends).

This is the **first implementation/code phase** — the repo is currently greenfield (only planning docs). Phase 2 builds the **rails (plumbing)**: `inbound event → queue → worker → post capability`. Real reply content (classification/extraction/drafting) arrives in **Phase 4**; the two MCPs (Selless + Knowledge RAG) arrive in **Phase 3**.

**In scope:**
- Isolated, rate-limit-aware Freshdesk REST API v2 client (read tickets/conversations; post reply + note)
- Queued intake: webhook receiver (primary) + reconciliation poller (backup)
- Idempotency / dedup / loop-guard / dead-letter state
- A config-driven send-mode switch (dry-run ↔ live-send)
- PII redaction before any logging/persistence
- Sandbox-based end-to-end demo proving the post path + exactly-once

**Out of scope (defer):**
- Classification / extraction / grounding / drafting — Phase 4
- Selless MCP & Knowledge RAG MCP — Phase 3
- Live quality dashboard + kill-switch **UI** — Phase 6 (Phase 2 only seeds the send-mode config mechanism)
- Staged rollout % bucketing — Phase 7
- Operational actions (refund/replace/order changes) — out of Phase-1 milestone entirely

</domain>

<decisions>
## Implementation Decisions

### Queue & State Backend
- **D-01: Postgres-backed queue + state.** Use a single Postgres as both the work queue (claim rows via `SELECT ... FOR UPDATE SKIP LOCKED`) and the store for idempotency keys / dedup / dead-letter. Rationale: reuse the exact Postgres that Phase 3 needs for pgvector → one datastore, simpler ops, transactional idempotency. Sufficient for current volume (~900 email/day Phase-1 scope; ~3k/day all-channel ceiling). Avoids standing up Redis/SQS as a second datastore.

### Idempotency
- **D-02: Idempotency key = `ticket_id + inbound message id`.** The unit of "an inbound" is the latest customer message that needs a reply, keyed by Freshdesk ticket id + that conversation/message id. Both the webhook path and the safety-net poller compute the key off the **same ticket state**, so they derive the **same key** → exactly-once. (Deliberately NOT the webhook delivery/event id, which would not dedup a poller-picked duplicate; NOT a content hash, which is fragile to normalization differences.)

### Phase 2 Demonstrable End-State
- **D-03: Demo posts a canned reply into a Freshdesk sandbox.** The end-to-end Phase 2 demo exercises the real `POST /tickets/{id}/reply` path with placeholder/canned content against an **isolated sandbox account** (no real customers), proving criterion #2 (post + retry-does-not-double-send) on real Freshdesk.
- **D-04: Client exposes BOTH reply (public) and note (private) from the start.** Even though the demo posts a public reply, the I/O client implements both surfaces (note is needed for later escalation/observability flows).
- **D-05: Config-driven send-mode switch, default = dry-run.** A single config flag controls `dry-run` (compute + persist the would-be action, do NOT call Freshdesk) ↔ `live-send`. Default is **dry-run** (the sandbox demo flips it on). This is the **seed of the Phase 6 kill-switch and Phase 7 staged-rollout control**, and prevents accidental live sends during development.

### Loop / Auto-Reply Guard (criterion #4)
- **D-06: Four combined signal layers** decide "do NOT auto-reply":
  1. **Standard email headers** — `Auto-Submitted` (RFC 3834), `Precedence: bulk/junk/list`, `List-*` headers, `X-Auto-Response-Suppress`, empty `Return-Path`.
  2. **Sender patterns** — `no-reply@`/`noreply@`, `mailer-daemon@`, `postmaster@`, bounce addresses.
  3. **Freshdesk source/actor** — only process messages whose source/actor is a **real incoming customer message**; skip messages created by agent/system/automation and skip replies the AI itself just sent.
  4. **Selless-sync origin** (see D-07).
- **D-07: Sync-echo detection relies on Freshdesk source/actor field** (the simpler approach over marker/tag stamping). Treat updates whose source/actor = the Selless sync integration user as non-customer → never reply. **RESEARCH FLAG:** verify Freshdesk actually stamps a distinguishable source/actor on Selless-sync-originated updates; if it does not, fall back to a controlled marker/tag on system-originated outbound. (Selless API/sync behavior is noted as unconfirmed in STATE.md.)
- **D-08: Suppression action = skip + log/metric.** When loop-guard classifies an inbound as "no auto-reply": mark it processed (idempotent, never re-picked), do NOT post, and emit a log + metric to observe the suppression rate. Suppressed inbound does **NOT** go to the dead-letter path (dead-letter is for genuine processing failures, per criterion #3).

### Webhook vs Poller (criterion #1)
- **D-09: Webhook primary + periodic reconciliation poller.** Webhook is the low-latency primary path. A poller runs on a configurable cadence (~5–15 min) scanning tickets `updated_since` a recent window, reconciling against the processed table to catch any events the webhook dropped. Dedup is automatic because both paths share the D-02 idempotency key. (NOT webhook-only — that loses reconciliation and violates criterion #1.)

### Retry / Dead-Letter (criterion #3)
- **D-10: Bounded backoff + alert.** Finite retries (~5, configurable) with exponential backoff + jitter, always honoring the Freshdesk `Retry-After` header on 429. On exhaustion → push to the Postgres dead-letter table + fire an alert (log/metric/notify) for a human. Counts and thresholds are configurable. (NOT infinite retry — risks a stuck/runaway queue on the customer-send path.)

### Worker Concurrency / Ordering
- **D-11: Single sequential worker for Phase 2.** One worker processes the queue sequentially — simplest, no race conditions, sufficient for ~900/day. The Postgres `SKIP LOCKED` design leaves the door open to scale to N workers with a per-ticket lock later, but Phase 2 ships the single-worker model.

### Observability / PII
- **D-12: PII redaction (Presidio) wired from Phase 2; tracing minimal.** Because the worker touches real ticket data immediately, redact PII before any log/persist (PII leaking into logs is hard to claw back). Observability stays minimal in Phase 2 — structured logs + metrics. Full Langfuse tracing is deferred to Phase 4/5 when LLM calls exist. (This upholds the CLAUDE.md rule: never log raw ticket text.)

### Claude's Discretion
- Error classification taxonomy for D-10 (which HTTP errors are transient/retryable vs fatal/straight-to-dead-letter, e.g. 429/5xx/timeout vs 404/403) — planner/executor decide.
- Exact Postgres table/schema design for queue, processed/idempotency, and dead-letter.
- Webhook receiver framework choice (e.g. FastAPI) and deployment shape, consistent with the Python stack in CLAUDE.md.
- Poller exact cadence value within the ~5–15 min band; backoff base/cap/jitter values.
- Directory/module layout for the I/O client and worker.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before planning or implementing.**

### Project-Level (locked)
- `.planning/PROJECT.md` — phase boundary (Phase 1 milestone = email-answering only, no ops actions), two-MCP architecture, Freshdesk-API-into-existing-ticket integration constraint
- `.planning/REQUIREMENTS.md` — **REP-05** (idempotent post into existing ticket) maps to this phase; SEL-*/KB-* are Phase 3, REP-01..04 are Phase 4
- `.planning/ROADMAP.md` §"Phase 2" — goal + the 4 success criteria this phase must make TRUE; depends on Phase 1
- `CLAUDE.md` — recommended stack: **Freshdesk REST API v2** (`POST /tickets/{id}/reply`, `GET /tickets/{id}/conversations`, Basic Auth with API key as username + dummy password, plan-based rate limits ~700/min Enterprise), **httpx + tenacity** (retry/backoff on 429), **Postgres 16/17 + pgvector 0.8.x**, **Microsoft Presidio** (PII redaction), Python toolchain (uv), Docker Compose local stack, Langfuse (deferred to later phase)

### User-Provided (carried from Phase 1)
- `2026-05-28-meeting-note.md` — CS Lead context: channel split (Email 30% / Contact Form 60% / Other 10%), ~3k tickets/day total, Level-In distribution, agent workflow B1–B4
- `.planning/phases/01-knowledge-survey-conflict-inventory/01-CONTEXT.md` — prior decisions; notes Selless two-way sync with Freshdesk (relevant to D-07 sync-echo detection)

### External (to be confirmed during research/planning)
- Freshdesk REST API v2 docs: `developers.freshdesk.com/api/` — reply/note endpoints, conversation source/actor fields (needed for D-06 layer 3 and D-07 sync detection), webhook/automation configuration (D-09), rate-limit + `Retry-After` semantics (D-10)
- Selless ↔ Freshdesk sync behavior — **how source/actor is stamped on sync-originated updates** (D-07 research flag); Selless API/latency noted unconfirmed in STATE.md

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None — greenfield.** Repo contains only planning artifacts (`.planning/`, `CLAUDE.md`, `Plan-discussion.md`, `2026-05-28-meeting-note.md`). Phase 2 creates the first source code.

### Established Patterns
- `.planning/` GSD layout is the only existing convention. No code conventions yet — Phase 2 establishes the initial Python project structure (uv, module layout, Docker Compose for local Postgres).

### Integration Points
- **Downstream (Phase 3):** the Postgres instance stood up here is the same one pgvector will extend; design the schema/connection layer so Phase 3 can add the vector store alongside.
- **Downstream (Phase 4):** the worker's processing step is a stub in Phase 2 — leave a clean seam where the classify→extract→ground→draft pipeline plugs in. The send-mode switch (D-05) is the integration point for Phase 6's kill-switch and Phase 7's rollout %.
- **External:** Freshdesk (webhook in, reply/note out), and later Selless via sync (read-only awareness for loop-guard).

</code_context>

<specifics>
## Specific Ideas

- **Prerequisites confirmed available (no blockers):** Freshdesk **sandbox account**, **API key with reply scope**, **webhook configuration access** on the plan, and **Selless-sync source/actor knowledge** are all available per the user. This unblocks D-03 (sandbox demo), D-09 (webhook), and D-07 (sync detection verification).
- The send-mode switch (D-05) should be deliberately designed as the forward-compatible seam for the Phase 6 kill-switch and Phase 7 staged-rollout control — not a throwaway dev flag.
- Test strategy (D-03 + below): **mock HTTP (respx/httpx mock) in CI** for fast, network-free unit/integration tests; **real verification + smoke test on the Freshdesk sandbox** for the post path.

</specifics>

<deferred>
## Deferred Ideas

- **Scale-out worker model** — N workers + per-ticket lock (Postgres advisory lock / `SKIP LOCKED`). Phase 2 ships a single sequential worker (D-11); revisit when volume or channel scope grows.
- **Full Langfuse tracing / observability dashboard** — deferred to Phase 4/5 (when LLM calls exist) and Phase 6 (dashboard). Phase 2 keeps structured logs + metrics only.
- **Marker/tag-based sync-echo detection** — fallback for D-07 if Freshdesk source/actor proves insufficient; not built unless research shows the source/actor approach fails.
- **Transient-vs-fatal error classification refinement** — a smarter retry policy distinguishing 429/5xx/timeout (retry) from 404/403 (straight to dead-letter); folded into Claude's discretion for now rather than a separate locked decision.
- **Channel scope vs volume** (carried from Phase 1) — Email is only 30% of inbound; Contact Form (60%) is larger and already syncs into Freshdesk. A project-level scope re-check for `/gsd:complete-milestone`, not a Phase 2 task.

</deferred>

---

*Phase: 2-freshdesk-i-o-layer-pipeline-backbone*
*Context gathered: 2026-06-01*
