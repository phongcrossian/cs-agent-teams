# Grounding Layer — Run Guide (Phase 3)

This document explains how to run the grounding layer components: the ingest CLI,
the Knowledge RAG MCP server, the Selless MCP server, and the smoke demo tests.

---

## Prerequisites

```bash
# Start the Docker stack (Postgres + pgvector + Langfuse)
docker compose up -d

# Activate the Python virtual environment
source .venv/bin/activate

# Apply database migrations (schema for knowledge.*, audit.*, queue.*)
alembic upgrade head
```

Set the required environment variables in `.env`:

```
DATABASE_URL=postgresql+asyncpg://csbot:csbot@localhost:5432/csbot
VOYAGE_API_KEY=<your Voyage API key>          # needed for live ingest + sandbox tests
SELLESS_API_BASE_URL=https://api.selless.dev/admin/csm/order/public/tickets
SELLESS_API_GATEWAY_KEY=<key if VPN/gateway required>   # optional; leave blank if open
```

---

## 1. Ingest CLI

Builds the Knowledge RAG store from the frozen Phase-1 snapshots
(WorkFlow.svg, email template .md files, Confluence PDFs in
`.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/`).

```bash
python -m src.ingest.cli re-ingest
```

What it does:

- Normalises and chunks prose sources into `knowledge.kb_chunk` (with Voyage embeddings).
- Upserts exact thresholds into `knowledge.policy_threshold` (D-10 — never embedded).
- Upserts workflow codes into `knowledge.code_map` (D-10 exact).
- Upserts reply template scaffolds into `knowledge.template_library` (D-11 exact).

Re-running is idempotent: unchanged content hashes produce no-ops (`ON CONFLICT DO UPDATE`
only refreshes `embedding + snapshot_version`).

---

## 2. Knowledge RAG MCP Server

Provides semantic search + exact lookup over the ingested knowledge store.

```bash
python -m src.knowledge_mcp.server
```

Tools exposed (read-only, all carry `readOnlyHint=True`):

| Tool | Description |
|------|-------------|
| `semantic_search(query, top_k=5)` | Hybrid RRF vector+FTS search; returns `SemanticSearchResult` with citations, `conflict` flag (D-13), and `resolved_by_override` (D-14). |
| `lookup_threshold(threshold_id)` | Exact threshold by ID (e.g. `THR-03`). Never LLM-inferred (D-10). |
| `lookup_code(code)` | Exact workflow code → action (e.g. `C1`). Never LLM-inferred (D-10). |
| `get_template(code)` | Exact template scaffold by code (e.g. `C1`). Keyed, not semantic (D-11). |

---

## 3. Selless Transactional MCP Server

Provides scoped, audited, rate-limited read access to the Selless order API.
This is the ONLY module that may call the Selless API (CLAUDE.md architecture constraint).

```bash
python -m src.selless_mcp.server
```

Tools exposed (read-only, `openWorldHint=False`):

| Tool | Description |
|------|-------------|
| `get_order_status(order_id)` | Whitelisted order detail (D-04 allow-list). No payment/supplier data. |
| `get_customer_info(customer_id)` | Whitelisted customer info. |
| `get_purchase_history(customer_id)` | Whitelisted purchase history. |
| `get_ticket_history(order_id)` | SEL-03/D-05 composition: Selless ticket-do mapping → Freshdesk ticket content. |
| `resolve_order(param)` | Exact order code or email → single order identity (D-03). |

Every tool call writes a PII-redacted row to `audit.selless_audit` (D-06/SEL-04).
Rate limit: token-bucket (D-08), configurable via `selless_rate_limit_rps` / `selless_rate_limit_burst` in settings.

---

## 4. Smoke Demo Tests

### Mock-backed (CI — no live API calls)

Proves all four Phase-3 success criteria without Voyage or Selless credentials.
Uses `stub_embedder` (zero vectors) for Knowledge MCP and `MockSellessClient` for Selless MCP.

```bash
pytest tests/smoke/test_grounding_demo.py -x -q
```

Four assertions:

1. `semantic_search("warranty")` returns `>=1` Citation with `source`, `authority_rank`,
   and `conflict=True` (CONTRA-01 stale-vs-current warranty conflict — D-13/D-15).
2. `lookup_threshold("THR-03")` returns exact `"Within 45 days of purchase date"` (D-10).
3. `get_template("C1")` returns a scaffold with `subject_template` + `body_template` (D-11).
4. `get_order_status(order_id)` returns whitelisted fields only (no `payment`/`supplier_id`),
   a redacted `audit.selless_audit` row is written (SEL-04/D-06), and the token-bucket
   rate-limiter rejects calls past burst capacity (D-08).

### Live sandbox (requires RUN_SANDBOX=1 + credentials)

Exercises the real `HttpSellessClient` against the live Selless gateway, and live
Voyage `voyage-3-large` embeddings. Skipped in CI automatically.

```bash
RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q
```

Prerequisites:

1. `VOYAGE_API_KEY` set in `.env`.
2. `SELLESS_API_BASE_URL` reachable from the run environment (gateway-trust model; set
   `SELLESS_API_GATEWAY_KEY` if a VPN or gateway header is required).
3. Run `python -m src.ingest.cli re-ingest` at least once so `knowledge.kb_chunk` is populated.

The live test asserts:

- Live `semantic_search` returns at least one cited passage.
- Live `get_order_status` returns whitelisted shape (no `payment`/`supplier_id` leakage).
- Live `audit.selless_audit` row written after the Selless call.
- Field-shape drift check (T-03-04-DRIFT): live `OrderDetail` fields must match the mock
  fixture shape; any missing fields fail with a descriptive message.

---

## 5. D-05 Freshdesk Composition Note

The Selless MCP provides the **order side** of the support context:
`get_ticket_history(order_id)` calls `fetch_ticket_mapping(order_id)` to get
`fd_ticket_id`, then delegates to the **Phase-2 `FreshdeskClient`** for actual ticket
content (subject, conversations, customer message).

This split is intentional (D-05 Option B, CLAUDE.md architecture constraint):

- **Selless MCP** — transactional/keyed (order status, delivery, customer identity).
  Real-time, lookup-by-ID, scoped permission, audit-logged.
- **Knowledge MCP** — semantic RAG (policy prose, thresholds, templates).
  Batch-ingested, centralized, cited.
- **FreshdeskClient (Phase 2)** — conversation store (ticket history, prior replies).
  Freshdesk is the system of record for email conversations; fetching ticket content
  from Selless would duplicate and diverge from it.

The **Phase-4 orchestrator** merges these three sources into the drafter context.
Do NOT merge the two MCPs into one server (CLAUDE.md: locked architectural decision).

---

## 6. Running the Full Test Suite

```bash
pytest tests/ -q
```

Expected: all unit + integration tests pass; sandbox tests (4) skipped unless `RUN_SANDBOX=1`.
