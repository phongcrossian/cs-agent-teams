# Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP) - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the **two separate grounding surfaces** the drafter relies on so the orchestrator never reads source systems directly:

1. **Knowledge MCP (semantic RAG)** — answers semantic queries over an ingested, conflict-aware RAG store and returns passages with **source citations carrying source/recency/authority metadata** (KB-05). Includes the **ingest → normalize → index pipeline** that builds the centralized store from the Phase 1 surveyed sources (KB-03), re-syncable/re-indexable when policies change (KB-04).
2. **Selless MCP (transactional)** — scoped **lookup-by-ID** reads: order status, customer info, purchase/order history, product, inventory, and prior ticket history, keyed to a verified customer/order ID — **no free-text cross-customer search** (SEL-01, SEL-02, SEL-03). Every call is **read-only, scope-enforced, rate-limited, and audit-logged** (SEL-04).

Maps to requirements **KB-03, KB-04, KB-05, SEL-01, SEL-02, SEL-03, SEL-04**.

**In scope:**
- Knowledge MCP server (FastMCP/Python) with cited semantic search + structured exact lookups
- KB ingest/normalize/index pipeline from Phase 1 artifacts into Postgres/pgvector, idempotent + re-runnable
- Conflict-aware retrieval (conflict flag + override table) and recency/authority metadata
- Selless MCP server (FastMCP/Python) wrapping the Selless **API** with a hard field whitelist
- Scope enforcement, rate-limiting, PII redaction at log/audit boundary, and an audit table
- A standalone verification that both MCPs answer real tool calls (no Phase 4 orchestrator required)

**Out of scope (defer):**
- Classification / extraction / grounding-into-draft / self-critique — **Phase 4** (the consumer of these MCPs)
- The reply pipeline orchestrator and safety guards/escalation logic — **Phase 4**
- Offline eval harness — **Phase 5**
- Live dashboard / kill-switch / routing gate — **Phase 6**
- Operational actions (refund/replace/order changes) — out of the Phase-1 milestone entirely
- Authoring/curating new KB content or resolving the 18 conflicts authoritatively — CS-team responsibility (Phase 3 builds the *mechanism*, not the rulings)

</domain>

<decisions>
## Implementation Decisions

### Selless MCP — Access & Transport
- **D-01: Selless reads go through the Selless API.** The MCP wraps Selless's HTTP API to fetch order info, customer info, purchase/order history, product, inventory, and prior ticket history. This is the production-correct connection model (must connect this way on deploy). **RESEARCH FLAG:** the exact endpoints/auth/field shapes are **not yet confirmed** — Selless API is "built for the platform, not for AI" and scattered. Researcher must survey the API and the user will supply API documentation/credentials. Plan a clean client seam so endpoints can be filled in once known; mock/stub for tests until credentials exist.
  - **API-CONFIRMED (2026-06-02 — see `03-SELLESS-API.md`):** Base URL `https://api.selless.dev/admin/csm/order`; surface is the `/public/tickets` controller (`Selless.CSM.Order.Admin` .NET). Swagger declares **NO auth** (`security: []`) and a live GET returned HTTP 200 with no credentials → access is gated at the **network/gateway** layer, not by token. **Consequence: the Selless API enforces no auth/scope/rate-limit/audit — our MCP layer is the sole security boundary** (reinforces D-08). Keyed GET endpoints confirmed: `po/{id}` (OrderDetail), `customer/{id}` (CustomerViewModel), `po/{id}/dispute|refunds|irreplaceable`, `{id}/ticket-do` (mapping). The `POST {id}/ticket-do` write endpoint is ⛔ never exposed (read-only).
- **D-02: Selless MCP language = Python / FastMCP.** Same toolchain as the existing repo (uv, `src/`, Postgres) and the Knowledge MCP — one language, one ops surface. Selless is just an HTTP client, so there is no Node/TS backend worth reusing (TS SDK rejected for this reason).
- **D-03: Tools are keyed by `order_id` OR verified `customer email`.** Each Selless tool accepts an order ID or a verified customer email and returns only records matching that key. **No free-text / cross-customer search** (enforces success criterion #3). Email→order resolution at the message level is Phase 4's extraction job; Phase 3 just exposes the keyed lookups.
  - **API-CONFIRMED amendment (2026-06-02):** The Selless `po/search` endpoint IS free-text cross-customer (Elasticsearch over id/code/tracking/name/email/phone) — exposing it raw would violate this decision. **Resolution (user-confirmed):** the MCP exposes a constrained **`resolve_order`** tool that accepts an **exact order code OR a verified customer email** and returns **only exact-key matches (a single customer identity)** — never a fuzzy/browse list. This honors the "keyed lookup, no cross-customer browsing" intent while still letting Phase-4 turn a human order code (e.g. `25044-67`) into the internal order `id` needed by `get_order(id)`. The raw free-text `po/search` is an internal client implementation detail of `resolve_order`, not an exposed MCP tool.

### Selless MCP — Scope, PII & Audit (SEL-04)
- **D-04: Hard field whitelist.** Tools expose only a fixed allow-list of fields needed to answer a reply (order status, customer name/contact, purchase history, product, inventory, ticket history). Hard-deny sensitive fields: payment/card data, internal cost/margin, and any other-customer PII. (Return-all-then-filter rejected as leak-prone.)
  - **API-CONFIRMED amendment (2026-06-02 — conservative posture, user-confirmed; concrete fields in `03-SELLESS-API.md` §4):** **DENY** `payment.*` (card_first4/last4/brand, gateway_id, transaction_id, merchant_name/email, provider), `*.total_product_cost` (cost/margin), `DoViewModel.{supplier_id, supplier_code, contract_id, is_fake_contract, fulfillment_version_id/name}` + `*.supplier_name`, `DisputeViewModel.payload`, `HistoryViewModel.payload`, **and the borderline-internal fields** `PoViewModel.note`, `PoViewModel.handling_fee`, `TicketViewModel.agent`/`agent_id`. **ALLOW** order `{id, code, status, created, amounts, addresses, product, line_items(minus cost)}`, DO `{status, odo_status, status_date_*, trackings, failed_reason}`, customer `{names, email, phone, *_status}`, refund/dispute/irreplaceable (minus payload). Implement allow-list as explicit Pydantic response models (map-and-whitelist), never pass-through.
- **D-05: Prior ticket history (SEL-03) is served from the Selless API too.** Keep the Selless MCP as the single transactional surface; ticket history comes via Selless (it two-way-syncs tickets with Freshdesk) rather than splitting reads across the Phase-2 Freshdesk client. Researcher to confirm the Selless API exposes ticket history with adequate fields/stability.
  - **API-CONFIRMED amendment (2026-06-02 — REVERSES the original "via Selless" choice, user-confirmed):** The Selless `/public/tickets` surface exposes only the `{id}/ticket-do` **mapping** (order ↔ `fd_ticket_id` ↔ `do_ids`); full ticket **content** (`TicketViewModel`: rootcause/customer_feedback/customer_request/agent) lives only on a **non-public** endpoint (`po/{id}/tickets`). **Resolution (user-confirmed 2026-06-02): Phase 3 ships a FULL `get_ticket_history(order_id)` tool on the Selless MCP that internally (1) calls Selless `ticket-do` to resolve `fd_ticket_id`, (2) fetches prior-ticket CONTENT via the existing Phase-2 Freshdesk client, and (3) returns whitelisted ticket-history fields.** SEL-03 is **fully satisfied within Phase 3** (NOT deferred to Phase 4), reusing the in-repo Freshdesk client. Source of ticket content = Freshdesk (the Selless mapping is just the join key); the composition lives inside the Selless MCP tool so the orchestrator sees one clean transactional tool. The raw `ticket-do` GET mapping may also be exposed as a low-level tool, but `get_ticket_history` is the SEL-03 deliverable.
- **D-06: PII passes to the drafter, redacted at the log/audit boundary.** Real PII (name, address, email, phone) is returned in-context to the drafter (needed to address the customer / confirm the order), but **Presidio (wired since Phase 2, D-12) redacts before any log/audit/trace write**. Upholds the CLAUDE.md "never log raw ticket text" rule.
- **D-07: Audit log = a PII-redacted Postgres table.** Every Selless call is recorded in an audit table in the same Postgres: caller, tool, input ID/key, fields returned (redacted), timestamp, latency, outcome. One datastore, queryable per customer/order. (Log/metric-only rejected — not queryable as an audit trail.)
- **D-08: Scope/read-only/rate-limit enforced at the MCP server boundary.** The MCP layer owns its own per-tool rate limiter and read-only guarantee, independent of the Freshdesk client's limiter. (Exact limits/algorithm = Claude's discretion.)

### Knowledge MCP — Storage & Retrieval Shape
- **D-09: KB stored in Postgres (pgvector).** Policy/workflow/template knowledge lives in the existing Postgres + pgvector — the same instance Phase 2 stood up — because production deploy must connect this way. No second datastore.
- **D-10: Structured-exact for thresholds & code-map; semantic for prose.** `POLICY-THRESHOLD-INDEX` (numeric/temporal thresholds: 45d, 20%, 1h, …) and `CODE-MAP` (workflow code → action → template) are stored as **structured Postgres tables for exact lookup** — never chunked into vectors — to prevent the LLM mis-reading a number. Prose (Confluence guides, WorkFlow narrative) goes through semantic chunk+embed. The Knowledge MCP therefore exposes **both** an exact-lookup tool surface and a semantic-search tool surface.
- **D-11: Email Templates = a separate "template library" retrieval type.** Operational reply templates are their own retrieval surface (drafter fetches a reply scaffold by code/scenario), distinct from policy semantic search. Distinguished from policy content in the store (separate type/metadata).
- **D-12: Authority hierarchy = WorkFlow (Whimsical) > Email Templates > Confluence.** Used for ranking and citation metadata. WorkFlow.svg (the operational process source) is most authoritative, Email Templates next (what agents actually send), Confluence lowest (mostly guidance/sizing root-cause material). Store authority as a metadata field (not hardcoded) so it can be tuned.

### Knowledge MCP — Conflict-Aware Grounding
- **D-13: On conflicting retrieved passages, return ALL of them + a `conflict` flag.** The Knowledge MCP does **not** self-arbitrate; it surfaces every conflicting passage with its metadata and a conflict flag so the Phase-4 safety/escalation layer can force a human handoff. Most conservative / anti-hallucination posture.
- **D-14: Resolve the 18 known conflicts via an override/resolution table (not pre-ingest curation).** Ingest the raw surveyed content now (don't block on CS-team triage). Maintain a `policy_resolution`/override table: when an authoritative ruling exists for a conflict, that record wins; until then, D-13 conflict-flag behavior applies. CS Lead populates rulings over time. (Pre-ingest canonical curation rejected — blocks the phase on CS-team work; query-time-only flag rejected — provides no path to a resolved answer.)
- **D-15: Stale content is downranked + recency-flagged, not deleted.** Content the Phase-1 CONFLICT-INVENTORY marks stale stays retrievable but is downranked and carries a `stale`/recency flag in metadata so the drafter/guard can react. (Hard-exclude rejected for now — keep auditability.)

### Knowledge MCP — Re-sync (KB-04)
- **D-16: Re-sync = manual re-export + an idempotent `re-ingest` command.** Because Phase-1 source access is manual viewer-only (no source API), the operator refreshes the committed snapshots and runs a versioned, idempotent re-ingest/re-index command. Automated source-watching (Confluence/Google API) is deferred (needs source-side credentials that may not exist).

### Claude's Discretion
- **Phase 3 demonstrable end-state** — how to prove both MCPs work standalone before Phase 4 exists (e.g., an MCP-client smoke test issuing real tool calls: a cited semantic query + a structured threshold lookup + a scoped/audited Selless read against mock-or-sandbox data). Planner to design; mirror Phase 2's sandbox-demo pattern.
- **Rate-limit values/algorithm** for the Selless MCP boundary (per-tool/per-minute, token bucket vs fixed window).
- Embedding/index details within the locked stack: Voyage `voyage-3-large`, HNSW index params, hybrid search wiring (`pg_trgm`/FTS + vector), optional reranker — all per CLAUDE.md, researcher/planner decide.
- Chunking strategy for prose (keep thresholds intact — they live in the structured tables anyway).
- Exact Postgres schema for KB tables, template library, override table, and the audit table; MCP module/directory layout under `src/`.
- Selless API client retry/backoff/error taxonomy (reuse the httpx + tenacity pattern established in Phase 2).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before planning or implementing.**

### Project-Level (locked)
- `.planning/PROJECT.md` — two-MCP architecture (NEVER merged), Selless-via-scoped-MCP constraint, knowledge-readiness (survey-before-RAG) constraint, "answers customers only" boundary
- `.planning/REQUIREMENTS.md` — **KB-03, KB-04, KB-05** (ingest/re-sync/cited semantic search) and **SEL-01..04** (transactional reads + scope/RL/audit) map to this phase
- `.planning/ROADMAP.md` §"Phase 3" — goal + the 4 success criteria this phase must make TRUE; depends on Phase 1 (survey gates ingest) and Phase 2 (foundation)
- `CLAUDE.md` — locked stack: **pgvector 0.8.x on Postgres 16/17** (HNSW), **Voyage `voyage-3-large`** embeddings, **MCP Python SDK v1.x / FastMCP 3.0**, hybrid search (`pg_trgm`/FTS + vector), optional reranker (Cohere/Voyage), **Presidio** PII redaction, **httpx + tenacity**; "What NOT to Use": no merged MCP, no reading raw Confluence/Sheets per-reply, no MCP SDK v2

### Phase 1 KB artifacts (ingest INPUTS — the foundation this RAG is built on)
- `.planning/phases/01-knowledge-survey-conflict-inventory/SURVEY.md` — master source inventory + coverage findings
- `.planning/phases/01-knowledge-survey-conflict-inventory/SURVEY-confluence.md` — Confluence SCE guides survey
- `.planning/phases/01-knowledge-survey-conflict-inventory/SURVEY-email-templates.md` — Email Templates survey
- `.planning/phases/01-knowledge-survey-conflict-inventory/CONFLICT-INVENTORY.md` — 18 HIGH/MEDIUM conflicts + threshold cross-source axis + stale flags (drives D-13/D-14/D-15)
- `.planning/phases/01-knowledge-survey-conflict-inventory/POLICY-THRESHOLD-INDEX.md` — every numeric/temporal threshold w/ source → **structured-exact table** (D-10)
- `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` + `CODE-MAP-templates.md` — workflow code → action → email template → **structured-exact table** (D-10) + template library (D-11)
- `.planning/phases/01-knowledge-survey-conflict-inventory/GLOSSARY.md` — internal jargon → plain English (CEE/SCE/DNR/RTS/OOS…), needed for normalization
- `.planning/phases/01-knowledge-survey-conflict-inventory/COVERAGE-MAP.csv` — KB↔ticket-type coverage
- `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/` — frozen source content: `WorkFlow.svg`, Email Templates `*.md`, Confluence PDFs, `confluence/` — the raw ingest material; re-export target for D-16

### Phase 2 foundation (build on, don't duplicate)
- `.planning/phases/02-freshdesk-i-o-layer-pipeline-backbone/02-CONTEXT.md` — Postgres-as-single-datastore decision (D-01 there), schema/connection seam left for pgvector, Presidio PII wiring (D-12 there)
- `src/config.py` — pydantic-settings pattern; add Selless/Knowledge config here (`database_url` already present)
- `migrations/` (Alembic, `0001_initial_queue_schema.py`) — add Phase-3 tables (KB chunks, threshold/code-map exact tables, template library, override table, Selless audit) as new revisions; pattern established
- `src/guards/pii.py` — existing Presidio redaction to reuse at the Selless log/audit boundary (D-06/D-07)
- `src/freshdesk_io/client.py`, `rate_limit.py`, `errors.py` — httpx + tenacity + rate-limit + error-taxonomy patterns to mirror for the Selless API client (D-01/D-08)

### Selless API (CONFIRMED 2026-06-02)
- `.planning/phases/03-grounding-layer-selless-mcp-knowledge-rag-mcp/03-SELLESS-API.md` — **confirmed Selless surface**: base URL, no-auth/gateway-trust model, the `/public/tickets` keyed GET endpoints, the concrete DTO schemas, the D-04 field whitelist/deny-list, and the resolved D-03/D-05 decisions. **Planner MUST read this for the Selless client seam + tool definitions.**
- Live OpenAPI: `https://api.selless.dev/admin/csm/order/swagger.json` (OpenAPI 3.0.1, `Selless.CSM.Order.Admin` v1.7.54.0)
- Source code (read-only reference, .NET/C#): `/Users/admin/work/crossian/csm/csm-order-admin` — `Controllers/TicketController.cs`, `Services/{Order,Po,Ticket,Customer,Dispute,Refund}Service.cs`, `Models/ViewModel/`

### External (to be confirmed during research)
- Voyage embeddings + pgvector HNSW docs — index/build params
- MCP Python SDK / FastMCP 3.0 docs — server scaffolding, tool definitions, citation/structured-output shape

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Postgres + Alembic + asyncpg stack** (`src/config.py`, `migrations/`, `docker-compose.yml`): the same Postgres hosts pgvector and the new Phase-3 tables — no new datastore (D-09).
- **Presidio redaction** (`src/guards/pii.py`): reuse directly at the Selless audit/log boundary (D-06/D-07).
- **httpx + tenacity client pattern** (`src/freshdesk_io/`): the Selless API client mirrors this (retry/backoff/Retry-After, error taxonomy, rate-limit module) (D-01/D-08).
- **pydantic-settings config singleton** (`src/config.py`): extend for Selless API base URL/key + Knowledge/embedding config (secrets excluded from `__repr__`).

### Established Patterns
- Python toolchain (uv), `src/<module>/` package layout, Alembic migration-per-change, structured-logs + metrics (Langfuse tracing still deferred until LLM calls exist in Phase 4/5).
- Secrets never logged (`Settings.__repr__` redaction) — extend to Selless API key.

### Integration Points
- **Downstream (Phase 4):** the two MCPs are the grounding tools the classify→extract→ground→draft orchestrator consumes via MCP. Keep tool signatures clean and citation/metadata-rich; the conflict flag (D-13) is the hook the Phase-4 escalation logic reads.
- **Within Postgres:** Phase-3 tables (vector chunks, exact threshold/code-map tables, template library, override table, Selless audit) live alongside Phase-2's `queue` schema — use a separate schema/namespace to keep concerns clean.
- **External:** Selless API (read-only), and the committed Phase-1 snapshots as ingest source (re-export → re-ingest for D-16).

</code_context>

<specifics>
## Specific Ideas

- User's framing (verbatim): *"Selless Access sẽ qua API để lấy thông tin đơn hàng, khách hàng, product, inventory. Còn knowledge base (policy, workflow....) thì sử dụng db postgres để lưu trữ, vì sau này deploy trên production cũng phải connect kiểu này."* → production-correct connection models are a hard requirement, not a dev shortcut (drives D-01, D-09).
- Authority ordering is deliberately **WorkFlow > Templates > Confluence** (D-12) — counter to the usual "official docs win"; here the operational workflow diagram is the source of truth and Confluence is mostly guidance.
- Conflict posture is intentionally conservative: the MCP never picks a winner among conflicting policies on its own (D-13); resolution only comes from the human-populated override table (D-14).
- Structured-exact storage for numbers is a non-negotiable anti-hallucination measure given Phase-1 found contradictory thresholds (e.g., warranty 45d-purchase vs 14d-delivery) (D-10).

</specifics>

<deferred>
## Deferred Ideas

- **Automated source-watching for re-sync** — connecting Confluence/Google APIs to auto-detect KB changes and re-index (D-16 fallback). Deferred: needs source-side API credentials that may not exist; manual re-export + re-ingest is the v1 mechanism.
- **Pre-ingest canonical policy curation** — CS Lead resolving all 18 conflicts into a single clean "canonical policy" set before ingest. Deferred in favor of the override-table approach (D-14) to avoid blocking the phase on CS-team work; could become the long-term ideal once rulings accumulate.
- **Reranker tuning / hybrid-search weighting** — if retrieval quality is the bottleneck, add/tune a reranker (Cohere/Voyage) before changing the LLM (per CLAUDE.md guidance). Phase 3 ships baseline hybrid search; tuning is a follow-up.
- **Channel scope vs volume** (carried from Phase 1 & 2) — Email is only ~30% of inbound; Contact Form (60%) already syncs into Freshdesk. Project-level re-check for `/gsd:complete-milestone`, not a Phase 3 task.

</deferred>

---

*Phase: 3-grounding-layer-selless-mcp-knowledge-rag-mcp*
*Context gathered: 2026-06-02*
