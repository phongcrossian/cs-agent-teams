# Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP) - Research

**Researched:** 2026-06-02
**Domain:** MCP server scaffolding (FastMCP), RAG retrieval (pgvector/Voyage), transactional API wrapping with scope/audit
**Confidence:** MEDIUM-HIGH (stack/scaffolding HIGH; Selless API LOW — undocumented, must defer to user)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Selless MCP — Access & Transport**
- **D-01:** Selless reads go through the Selless **HTTP API** (order, customer, purchase/order history, product, inventory, prior ticket history). Production-correct connection model. **RESEARCH FLAG:** exact endpoints/auth/field shapes NOT confirmed — "built for the platform, not for AI", scattered. Plan a clean client seam; mock/stub for tests until credentials exist.
- **D-02:** Selless MCP language = **Python / FastMCP** (same toolchain as repo + Knowledge MCP). Selless is just an HTTP client — no Node/TS backend worth reusing.
- **D-03:** Tools keyed by `order_id` OR verified `customer email`. Return ONLY records matching that key. **No free-text / cross-customer search.** Email→order resolution is Phase 4's job.

**Selless MCP — Scope, PII & Audit (SEL-04)**
- **D-04:** **Hard field whitelist.** Tools expose only a fixed allow-list (order status, customer name/contact, purchase history, product, inventory, ticket history). Hard-deny: payment/card data, internal cost/margin, other-customer PII. (Return-all-then-filter REJECTED.)
- **D-05:** Prior ticket history (SEL-03) served from **Selless API too** (Selless two-way-syncs tickets w/ Freshdesk). Keep Selless MCP the single transactional surface. Confirm Selless exposes ticket history w/ adequate/stable fields.
- **D-06:** PII passes to the drafter in-context, **redacted at the log/audit boundary** via Presidio (Phase-2 `src/guards/pii.py`).
- **D-07:** Audit log = a **PII-redacted Postgres table**: caller, tool, input ID/key, fields returned (redacted), timestamp, latency, outcome. (Log/metric-only REJECTED.)
- **D-08:** Scope/read-only/rate-limit enforced **at the MCP server boundary**, independent of Freshdesk's limiter. Limits/algorithm = Claude's discretion.

**Knowledge MCP — Storage & Retrieval Shape**
- **D-09:** KB stored in **Postgres (pgvector)** — same instance Phase 2 stood up. No second datastore.
- **D-10:** **Structured-exact** for thresholds (`POLICY-THRESHOLD-INDEX`) & code-map (`CODE-MAP`) → Postgres tables for exact lookup, NEVER chunked into vectors. Prose → semantic chunk+embed. Knowledge MCP exposes BOTH an exact-lookup tool surface AND a semantic-search tool surface.
- **D-11:** Email Templates = a **separate "template library" retrieval type** (fetch reply scaffold by code/scenario), distinct from policy semantic search.
- **D-12:** Authority hierarchy = **WorkFlow (Whimsical) > Email Templates > Confluence**. Stored as a tunable metadata field (not hardcoded).

**Knowledge MCP — Conflict-Aware Grounding**
- **D-13:** On conflicting retrieved passages, return **ALL of them + a `conflict` flag**. MCP does NOT self-arbitrate.
- **D-14:** Resolve the 18 known conflicts via an **override/resolution table** (not pre-ingest curation). Ingest raw now; `policy_resolution` override wins when a ruling exists; else D-13 behavior.
- **D-15:** Stale content is **downranked + recency-flagged**, not deleted.

**Knowledge MCP — Re-sync (KB-04)**
- **D-16:** Re-sync = **manual re-export + an idempotent `re-ingest` command** (versioned). Automated source-watching deferred.

### Claude's Discretion
- Phase 3 demonstrable end-state (MCP-client smoke test: cited semantic query + structured threshold lookup + scoped/audited Selless read against mock-or-sandbox data). Mirror Phase 2's sandbox-demo.
- Rate-limit values/algorithm for the Selless MCP boundary (per-tool/per-minute, token bucket vs fixed window).
- Embedding/index details within locked stack (Voyage `voyage-3-large`, HNSW params, hybrid wiring, optional reranker).
- Chunking strategy for prose (keep thresholds intact — they live in structured tables).
- Exact Postgres schema for KB tables, template library, override table, audit table; MCP module/dir layout under `src/`.
- Selless API client retry/backoff/error taxonomy (reuse httpx + tenacity from Phase 2).

### Deferred Ideas (OUT OF SCOPE)
- Automated source-watching re-sync (Confluence/Google API auto-detect) — needs source-side credentials.
- Pre-ingest canonical policy curation (CS Lead resolving all 18 conflicts before ingest).
- Reranker tuning / hybrid-search weighting — Phase 3 ships baseline; tuning is a follow-up.
- Channel scope vs volume (email = ~30% inbound) — project-level re-check, not a Phase 3 task.
- Classification/extraction/grounding-into-draft/self-critique, orchestrator, guards/escalation — **Phase 4**.
- Offline eval harness — **Phase 5**. Dashboard/kill-switch/routing gate — **Phase 6**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KB-03 | Ingest→normalize→index pipeline builds a centralized RAG store from surveyed sources | §Ingest Pipeline + §RAG Storage; idempotent upsert keyed on content hash over Phase-1 snapshots |
| KB-04 | Knowledge content can be re-synced/re-indexed when policies change | §Ingest Pipeline (D-16 manual re-export + idempotent `re-ingest` CLI; content-hash dedup makes re-runs safe) |
| KB-05 | MCP Knowledge server answers semantic queries + returns source citations | §FastMCP scaffolding + §RAG; Pydantic `Citation` return shape carrying source/recency/authority/conflict/stale metadata |
| SEL-01 | MCP Selless returns order info + status by order ID or customer email | §Selless MCP; `get_order_status` tool keyed by order_id/email |
| SEL-02 | MCP Selless returns customer info + purchase/order history | §Selless MCP; `get_customer_info`, `get_purchase_history` tools |
| SEL-03 | MCP Selless returns prior ticket history | §Selless MCP; `get_ticket_history` tool (D-05 — served via Selless API; field stability flagged as deferred-to-docs) |
| SEL-04 | Scope-enforced read-only permissions, rate limiting, audit logging on every call | §FastMCP scaffolding (readOnlyHint + middleware) + §Audit table + Presidio at log boundary |
</phase_requirements>

## Summary

Phase 3 builds two Python/FastMCP servers over the **same Postgres** Phase 2 stood up. The technical stack is well-established and HIGH-confidence: FastMCP 3.x (current `3.3.1`) gives decorator-based tools with automatic Pydantic-schema structured output, a `readOnlyHint` annotation, and built-in `RateLimitingMiddleware` (token-bucket) plus a custom-middleware `on_call_tool` hook ideal for the SEL-04 audit log. The RAG layer is a textbook pgvector-on-Postgres-16 hybrid-search build: Voyage `voyage-3-large` (1024-dim default) embeddings, HNSW (`vector_cosine_ops`, m=16, ef_construction=64), plus `pg_trgm` + Postgres FTS fused with Reciprocal Rank Fusion (RRF, k=60).

The **one LOW-confidence area is the Selless API itself** (D-01/D-05). It is an internal proprietary platform ("built for the platform, not for AI", scattered) with **no public documentation** — confirmed by web search (only unrelated "Selldone"/"Selly" platforms exist publicly) and by the Phase-1 meeting note. Therefore the planner MUST NOT plan against concrete Selless endpoints. Instead: build a **clean client seam** (an abstract `SellessClient` protocol + a `MockSellessClient` returning fixture data + a `HttpSellessClient` stub mirroring the Phase-2 `httpx + tenacity` pattern with endpoint paths left as TODO config). Everything customer-visible (tool signatures, whitelist, audit, rate-limit, scope) is buildable and testable today against the mock; only the concrete HTTP wiring waits on user-supplied docs/credentials.

The strongest anti-hallucination decisions (D-10 structured-exact tables for the 18 contradictory thresholds; D-13/D-14 conflict-flag + override table) are directly supported by Phase-1 artifacts (`POLICY-THRESHOLD-INDEX.md` has 25 thresholds incl. the HIGH warranty conflict; `CONFLICT-INVENTORY.md` has 5 CONTRA + 5 STALE findings). These ingest as **rows**, not vectors.

**Primary recommendation:** Build vertical slices — (1) Knowledge MCP semantic-query slice (ingest a few Confluence/template chunks → embed → HNSW → cited tool call); (2) Knowledge MCP exact-lookup slice (load `POLICY-THRESHOLD-INDEX` + `CODE-MAP` into structured tables → exact-lookup tool); (3) Selless MCP scoped/audited slice against `MockSellessClient`. Defer all concrete Selless endpoints to a `checkpoint:human-verify` gate fed by user API docs.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Semantic policy search + citations | Knowledge MCP server (Python/FastMCP) | pgvector (Postgres) | RAG retrieval + citation assembly is server logic; vector store is persistence |
| Exact threshold / code-map lookup | Knowledge MCP server | Postgres structured tables | D-10: numbers must come from exact rows, never LLM-read from prose |
| Template-library fetch by code | Knowledge MCP server | Postgres template table | D-11: separate retrieval type; keyed lookup, not semantic |
| Conflict surfacing + override resolution | Knowledge MCP server | Postgres override table | D-13/D-14: server surfaces all + flag; override row decides "resolved" |
| Ingest→normalize→index | Ingest pipeline (CLI/module) | Voyage API + Postgres | Offline batch job over committed snapshots; not in the hot path |
| Order/customer/history lookup | Selless MCP server | `SellessClient` seam → Selless HTTP API | D-01/D-03: keyed lookup-by-ID; client seam isolates undocumented API |
| Scope / read-only / whitelist enforcement | Selless MCP server boundary | — | D-04/D-08: enforced at MCP layer, not downstream |
| Rate limiting | Selless MCP middleware | FastMCP `RateLimitingMiddleware` | D-08: MCP owns its own limiter, independent of Freshdesk's |
| Audit logging (PII-redacted) | Selless MCP `on_call_tool` middleware | Presidio + Postgres audit table | D-06/D-07: redact via `src/guards/pii.py` before persist |
| PII redaction at log boundary | `src/guards/pii.py` (reused) | Presidio | D-06: real PII to drafter; redacted before any log/trace/DB-audit write |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastmcp` | `3.3.1` (current) | Both MCP servers — tool defs, structured output, middleware | [VERIFIED: PyPI] CLAUDE.md mandates "MCP Python SDK v1.x / FastMCP 3.0". FastMCP 3.x is the high-level decorator API; auto-generates JSON schema from type hints + Pydantic models. [CITED: gofastmcp.com/servers/tools] |
| `mcp` | `1.27.2` (current) | Underlying MCP protocol types (`ToolAnnotations`, etc.) | [VERIFIED: PyPI] FastMCP builds on the official SDK; `pip install "mcp[cli]"` for CLI tooling. CLAUDE.md mandates v1.x (v2 pre-alpha — forbidden). |
| `voyageai` | `0.3.7` (latest, 2025-12-16) | `voyage-3-large` embeddings for the Knowledge base | [VERIFIED: PyPI] CLAUDE.md mandate. NOTE: declares `python <3.15`; this repo is **Python 3.14** (compatible). `voyage-3-large` = 1024-dim default (256/512/2048 also available). [CITED: docs.voyageai.com/docs/embeddings] |
| `pgvector` | `0.8.x` ext on Postgres 16 | Vector store + HNSW index | [VERIFIED: local psql 16.14 present] CLAUDE.md mandate. 1024-dim well under the 2000-dim HNSW limit. [CITED: github.com/pgvector/pgvector] |
| `asyncpg` | `0.31.0` (already in repo) | Postgres driver (reuse Phase-2 pool) | [VERIFIED: pyproject.toml] |
| `httpx` + `tenacity` | `0.28.1` / `9.1.4` (already in repo) | Selless API client (mirror `src/freshdesk_io/`) | [VERIFIED: pyproject.toml] D-01/D-08 reuse mandate |
| `presidio-analyzer`/`-anonymizer` | `2.2.359` / `2.2.362` (already in repo) | PII redaction at audit boundary (D-06/D-07) | [VERIFIED: pyproject.toml] reuse `src/guards/pii.py` |
| `pydantic` / `pydantic-settings` | `2.13.4` / `>=2.0` (already in repo) | Tool I/O schemas + config singleton | [VERIFIED: pyproject.toml] |
| `alembic` | `1.18.4` (already in repo) | Migration-per-change for new Phase-3 tables | [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pgvector` Python binding | latest (`pip install pgvector`) | asyncpg/SQLAlchemy `vector` type registration | Needed so asyncpg can encode/decode the `vector` column. Register codec on pool init. [ASSUMED — confirm binding package name `pgvector` at install] |
| `voyageai.Client` rerank (optional) | within `voyageai` 0.3.7 | Reranker over hybrid candidates | Deferred per CONTEXT (baseline hybrid ships first; rerank is a tuning follow-up). Voyage offers rerankers natively. |
| `structlog` | `25.5.0` (already in repo) | Structured logs (redacted) | Reuse Phase-2 logging convention |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pgvector | Qdrant | Only if KB grows >10M vectors (it won't — thousands of chunks). CLAUDE.md rejects for Phase 1. |
| Voyage `voyage-3-large` | OpenAI `text-embedding-3-large` | Only if already on OpenAI billing. CLAUDE.md default is Voyage. |
| FastMCP built-in rate-limit middleware | Hand-rolled token bucket | Reuse Phase-2 `rate_limit.py` style only if FastMCP middleware proves insufficient for per-tool granularity (see Pitfall 3). |
| RRF fusion | Weighted score normalization | RRF avoids normalizing incompatible score distributions; simpler + proven (~62%→~84% precision). |

**Installation:**
```bash
# add to pyproject.toml dependencies
uv add fastmcp voyageai pgvector
# mcp comes transitively with fastmcp; pin to v1.x line if surfaced
```

**Version verification (done this session):**
- `fastmcp` → `3.3.1` latest [VERIFIED: PyPI / `pip index`]
- `mcp` → `1.27.2` latest [VERIFIED: PyPI / `pip index`]
- `voyageai` → `0.3.7` latest, 2025-12-16 [VERIFIED: pypi.org/project/voyageai]. (`pip index` on this machine showed `0.2.4` as "latest compatible" — that is a **Python-3.14 vs declared `<3.15` filtering artifact**, not the true latest. Confirm install resolves 0.3.7; if blocked by the `<3.15` cap, pin `voyageai==0.3.7` and verify it imports under 3.14, or relax via `--ignore-requires-python` only after a manual check.)
- `@modelcontextprotocol/sdk` (TS) → `1.29.0` [VERIFIED: npm] — **not used** (D-02 rejects TS), recorded only to confirm CLAUDE.md's v1.x guidance.

## Package Legitimacy Audit

> slopcheck could not be installed (sandbox denied an undeclared package install for a research-only task). Per the graceful-degradation rule, packages discovered this session that are NOT already in the repo manifest are tagged `[ASSUMED]`; the planner should gate each new install behind a `checkpoint:human-verify` before adding to `pyproject.toml`. Packages already in `pyproject.toml` were vetted in earlier phases.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `fastmcp` | PyPI | mature (1.0→3.3.1) | high | github.com/jlowin/fastmcp (PrefectHQ) | n/a (unavailable) | Approved — well-known, CLAUDE.md-mandated [ASSUMED until human-verify on install] |
| `mcp` | PyPI | mature (official SDK) | high | github.com/modelcontextprotocol/python-sdk | n/a | Approved — official MCP SDK [ASSUMED until human-verify] |
| `voyageai` | PyPI | mature (0.1→0.3.7) | moderate | github.com/voyage-ai/voyageai-python (official) | n/a | Approved — official Voyage lib [ASSUMED until human-verify] |
| `pgvector` (py binding) | PyPI | mature | high | github.com/pgvector/pgvector-python | n/a | Approved — official binding [ASSUMED — confirm exact dist name `pgvector`] |
| in-repo deps (httpx, tenacity, asyncpg, presidio, pydantic, alembic, structlog) | PyPI | — | — | — | vetted prior phases | Approved (already in `pyproject.toml`) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Planner action:** add one `checkpoint:human-verify` task before the install step that adds `fastmcp`, `voyageai`, `pgvector` to `pyproject.toml`.

## Architecture Patterns

### System Architecture Diagram

```
                          PHASE 4 ORCHESTRATOR (future consumer — out of scope)
                                     │  MCP tool calls
            ┌────────────────────────┼─────────────────────────┐
            ▼                                                   ▼
 ┌──────────────────────────┐                    ┌──────────────────────────────┐
 │   KNOWLEDGE MCP (Python)  │                    │     SELLESS MCP (Python)      │
 │  FastMCP server           │                    │  FastMCP server               │
 │                           │                    │                               │
 │  Tools:                   │                    │  Middleware pipeline:         │
 │   • semantic_search ──────┼──hybrid──┐         │   1. RateLimitingMiddleware   │
 │   • lookup_threshold ─────┼─exact─┐  │         │   2. AuditMiddleware          │
 │   • lookup_code ──────────┼─exact─┤  │         │      (on_call_tool)           │
 │   • get_template ─────────┼─keyed─┤  │         │                               │
 │                           │       │  │         │  Tools (readOnlyHint=True,    │
 │  Citation assembly        │       │  │         │   keyed by order_id|email):   │
 │   (source/authority/      │       │  │         │   • get_order_status          │
 │    recency/conflict/stale)│       │  │         │   • get_customer_info         │
 └───────────┬───────────────┘       │  │         │   • get_purchase_history      │
             │                       │  │         │   • get_ticket_history (D-05) │
             ▼                       ▼  ▼         │   • get_product / inventory   │
 ┌─────────────────────────────────────────┐     │           │ field whitelist   │
 │        POSTGRES (single instance)         │     │           ▼ (D-04)            │
 │  schema `queue`  (Phase 2)                │     │  ┌──────────────────────┐    │
 │  schema `knowledge` (Phase 3):            │     │  │  SellessClient (seam) │    │
 │   • kb_chunk (vector, FTS, trgm, meta)    │     │  │   ├ MockSellessClient │◄── fixtures (tests)
 │   • policy_threshold  (exact rows)        │     │  │   └ HttpSellessClient │──► Selless HTTP API
 │   • code_map          (exact rows)        │     │  │      (httpx+tenacity, │    (endpoints = TODO,
 │   • template_library  (keyed rows)        │     │  │       paths=config)   │     deferred to docs)
 │   • policy_resolution (override, D-14)    │     │  └──────────────────────┘    │
 │  schema `audit` (Phase 3):                │◄────┤  writes redacted audit row   │
 │   • selless_audit (PII-redacted, D-07)    │     └──────────────────────────────┘
 └─────────────────────────────────────────┘
             ▲
             │ idempotent upsert (content-hash keyed)
 ┌───────────┴───────────────┐
 │   INGEST PIPELINE (CLI)    │  re-runnable (D-16): re-export snapshots → re-ingest
 │  normalize → chunk → embed │
 │  (Voyage voyage-3-large)   │
 └───────────┬───────────────┘
             │ reads (committed, frozen)
   .planning/phases/01-…/snapshots/  (WorkFlow.svg, *.md templates, Confluence PDFs)
   + POLICY-THRESHOLD-INDEX.md + CODE-MAP.md (→ structured exact tables)
```

Trace the primary use case: an ingest run loads snapshots → normalizes/chunks prose → embeds via Voyage → upserts into `knowledge.kb_chunk`; thresholds/code-map load as exact rows. At query time the orchestrator calls `semantic_search` → hybrid retrieval (vector + FTS + trgm, RRF-fused) → citation assembly with metadata → returns passages + conflict flag. A Selless lookup flows through rate-limit + audit middleware → whitelist-filtered client read → redacted audit row written.

### Recommended Project Structure
```
src/
├── selless_mcp/
│   ├── server.py          # FastMCP() instance, tool defs, middleware wiring
│   ├── client.py          # SellessClient Protocol + Http/Mock impls (httpx+tenacity)
│   ├── models.py          # Pydantic: OrderStatus, CustomerInfo, PurchaseHistory, TicketHistory (whitelisted fields)
│   ├── whitelist.py       # D-04 field allow-list + hard-deny
│   ├── audit.py           # AuditMiddleware (on_call_tool) → redact → audit table
│   └── errors.py          # Selless error taxonomy (mirror freshdesk_io/errors.py)
├── knowledge_mcp/
│   ├── server.py          # FastMCP() instance, tool defs
│   ├── retrieval.py       # hybrid search (vector+FTS+trgm, RRF), citation assembly
│   ├── exact.py           # threshold + code-map exact lookups, template fetch
│   ├── conflict.py        # D-13/D-14 conflict flag + override resolution
│   ├── embeddings.py      # Voyage client wrapper (query vs document input_type)
│   └── models.py          # Pydantic: Citation, ThresholdResult, TemplateResult
├── ingest/
│   ├── pipeline.py        # orchestrates normalize→chunk→embed→upsert (idempotent)
│   ├── sources.py         # snapshot readers (SVG text, .md templates, PDF, threshold/code-map MD)
│   ├── normalize.py       # GLOSSARY-driven jargon expansion, cleaning
│   ├── chunk.py           # prose chunking (keep thresholds intact)
│   └── cli.py             # `python -m src.ingest.cli re-ingest` (D-16)
├── config.py              # EXTEND: selless_api_base_url/key, voyage_api_key, embedding dims
└── guards/pii.py          # REUSE (D-06/D-07)
migrations/versions/
├── 0002_knowledge_schema.py   # kb_chunk, policy_threshold, code_map, template_library, policy_resolution
└── 0003_selless_audit.py      # audit.selless_audit
```

### Pattern 1: FastMCP tool with structured Pydantic output + read-only annotation
```python
# Source: gofastmcp.com/servers/tools
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

mcp = FastMCP(name="SellessMCP", on_duplicate_tools="error")

class OrderStatus(BaseModel):
    order_id: str
    status: str
    # D-04: ONLY whitelisted fields. No payment/card/cost/margin fields.
    placed_at: str
    line_items: list[str]

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def get_order_status(order_id: str) -> OrderStatus:
    """Return current status for a single order by ID (no cross-customer search)."""
    raw = client.fetch_order(order_id)        # SellessClient seam
    return OrderStatus(**whitelist_order(raw))  # D-04 hard filter
```
FastMCP auto-generates the JSON output schema from the Pydantic return type and emits both human-readable + `structuredContent`. `readOnlyHint=True` lets clients skip confirmation prompts.

### Pattern 2: Citation return shape (KB-05) carrying D-12/D-13/D-15 metadata
```python
class Citation(BaseModel):
    text: str
    source: str                 # "WorkFlow.svg" | "Email Templates" | "Confluence" | template code
    source_type: str            # "policy_prose" | "template" | "threshold" | "code_map"
    authority_rank: int         # D-12: WorkFlow=3 > Templates=2 > Confluence=1 (tunable, from metadata)
    recency_flag: str | None    # D-15: "stale" if CONFLICT-INVENTORY marked it
    snapshot_version: str       # ingest run / content hash
    score: float

class SemanticSearchResult(BaseModel):
    citations: list[Citation]
    conflict: bool              # D-13: true if conflicting passages surfaced
    resolved_by_override: bool  # D-14: true if a policy_resolution row applied
```

### Pattern 3: Audit middleware (SEL-04, D-06/D-07)
```python
# Source: gofastmcp.com/servers/middleware
from fastmcp.server.middleware import Middleware, MiddlewareContext
from src.guards.pii import redact_text

class AuditMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool = context.message.name
        key = context.message.arguments  # order_id / email
        t0 = time.monotonic()
        try:
            result = await call_next(context)
            outcome = "ok"
        except Exception:
            outcome = "error"; raise
        finally:
            await write_audit_row(
                tool=tool,
                input_key=redact_text(str(key)),          # D-06 redact before persist
                fields_returned=redact_text(summarize(result)),
                latency_ms=(time.monotonic()-t0)*1000,
                outcome=outcome,
            )
        return result

mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=..., burst_capacity=...))  # D-08
mcp.add_middleware(AuditMiddleware())  # order matters; runs around every tool call
```

### Pattern 4: Hybrid search with RRF (KB-05)
```sql
-- Source: dev.to RRF hybrid-search guide + github.com/pgvector
-- indexes
CREATE INDEX kb_chunk_hnsw ON knowledge.kb_chunk USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX kb_chunk_fts  ON knowledge.kb_chunk USING gin (body_tsv);
CREATE INDEX kb_chunk_trgm ON knowledge.kb_chunk USING gin (body gin_trgm_ops);
-- query: run vector ANN + FTS (+ optional trgm) lists, fuse with RRF (k=60) in app code
```
Over-fetch ~20 candidates per arm, fuse `1/(60+rank)`, then assemble citations. SET `hnsw.ef_search` (≥ requested k) per session.

### Anti-Patterns to Avoid
- **Chunking thresholds into vectors:** D-10 forbids it — numbers go in `policy_threshold` exact rows. An LLM mis-reading "45 days" vs "14 days" is the exact failure mode Phase 1 surfaced (CONTRA-01 HIGH).
- **Return-all-then-filter on Selless:** D-04 rejects it — build the whitelist as the model boundary, not a post-filter.
- **Self-arbitrating conflicts:** D-13 forbids the MCP picking a winner; surface all + flag.
- **Hardcoding endpoint paths against guessed Selless API:** the API is undocumented — leave paths as config TODO behind the seam.
- **Logging raw PII:** CLAUDE.md / D-06 — always `redact_text()` before any audit/log/trace write.
- **One merged MCP:** CLAUDE.md "What NOT to Use" — two separate servers, always.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP tool JSON schema | Manual schema dicts | FastMCP type-hint/Pydantic inference | Auto-generated, validated, kept in sync |
| Rate limiting | Custom limiter from scratch | `fastmcp ...RateLimitingMiddleware` (token bucket) | Built-in, per-server; tune per-tool only if needed |
| PII redaction | Regex PII scrubbing | `src/guards/pii.py` (Presidio) | Already built + vetted in Phase 2 |
| Retry/backoff/error taxonomy | New retry logic | Mirror `src/freshdesk_io/client.py` tenacity pattern | Proven Retry-After + transient/fatal classification |
| Score fusion | Min-max normalization of vector+FTS scores | RRF (`1/(k+rank)`, k=60) | Avoids normalizing incompatible distributions |
| Embeddings | Local model hosting | Voyage `voyage-3-large` API | CLAUDE.md mandate; top retrieval quality |

**Key insight:** Nearly every cross-cutting concern (rate-limit, PII, retry, schema) is either a FastMCP built-in or already exists in the Phase-2 codebase. Phase 3's real work is *wiring*, the two structured-vs-semantic storage split, and the conflict/override mechanism — not infrastructure.

## Runtime State Inventory

> Phase 3 is greenfield-additive (new servers + new schemas), not a rename/refactor. Included for completeness because it touches Postgres state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `knowledge.*` + `audit.*` schemas/tables; Phase-2 `queue.*` untouched | Alembic revisions 0002/0003; pgvector extension `CREATE EXTENSION IF NOT EXISTS vector` |
| Live service config | Selless API base URL/key + Voyage API key — NOT yet in `.env`; Selless creds may not exist yet | Add to `src/config.py` + `.env`; gate live Selless wiring behind human-verify |
| OS-registered state | None — verified by `ls src/` (no OS daemons; servers run as processes) | None |
| Secrets/env vars | New: `selless_api_base_url`, `selless_api_key`, `voyage_api_key`; must follow `__repr__` redaction pattern in `config.py` | Extend `Settings` + redact in `__repr__` |
| Build artifacts | None — new packages only; `uv` reinstall after `pyproject.toml` edit | `uv sync` after adding deps |

## Common Pitfalls

### Pitfall 1: voyageai version resolution under Python 3.14
**What goes wrong:** `voyageai` declares `python <3.15`; this repo is 3.14. `pip index` showed `0.2.4` as latest-compatible (a filtering artifact), hiding the true latest `0.3.7`.
**Why it happens:** Resolver respects `requires-python` upper bounds.
**How to avoid:** Pin `voyageai==0.3.7`, install, and run a smoke `import voyageai; voyageai.Client()`; if blocked, evaluate `--ignore-requires-python` only after manual confirmation it imports under 3.14.
**Warning signs:** Older API surface; missing `base_url`/`output_dimension` kwargs.

### Pitfall 2: pgvector extension + asyncpg vector codec not registered
**What goes wrong:** `vector` column reads/writes fail or return strings.
**Why it happens:** asyncpg needs the `vector` type codec registered on the pool; the DB needs `CREATE EXTENSION vector`.
**How to avoid:** In a migration: `CREATE EXTENSION IF NOT EXISTS vector;`. On pool init register the codec via the `pgvector` python binding (`from pgvector.asyncpg import register_vector`). Reuse Phase-2 pool init but add registration.
**Warning signs:** `operator does not exist` / `type "vector" does not exist`.

### Pitfall 3: FastMCP rate-limit middleware is server-wide, not per-tool by default
**What goes wrong:** D-08 wants per-tool limits; the built-in `RateLimitingMiddleware` applies one bucket per server.
**Why it happens:** Built-in middleware is global.
**How to avoid:** Either (a) accept a single conservative server-wide bucket for MVP, or (b) write a thin custom `on_call_tool` middleware that selects a `TokenBucketRateLimiter` per `context.message.name`. The building blocks (`TokenBucketRateLimiter`, `SlidingWindowRateLimiter`) are exposed. MVP recommendation: server-wide bucket + note the per-tool refinement as discretion.
**Warning signs:** All tools throttled together when only one is hot.

### Pitfall 4: Presidio spaCy model missing
**What goes wrong:** `AnalyzerEngine()` raises `OSError` if `en_core_web_lg` absent (documented in Phase-2 `pii.py`).
**How to avoid:** Ensure `python -m spacy download en_core_web_lg` is in setup (already required by Phase 2). Audit middleware lazily inits the engine — same singleton pattern.

### Pitfall 5: SVG/PDF text extraction quality for ingest
**What goes wrong:** `WorkFlow.svg` is a diagram; Confluence is PDF — naive text extraction loses structure / thresholds.
**Why it happens:** Source formats are export artifacts.
**How to avoid:** D-10 already removes the highest-risk numbers from prose (they live in exact tables sourced from the *already-transcribed* `POLICY-THRESHOLD-INDEX.md` and `CODE-MAP.md` markdown, not from re-parsing the SVG). For prose, extract SVG node text + PDF text best-effort; chunk conservatively; carry `source`/`snapshot_version` metadata. Note `MISS-04` (cf_level_out PDF SRC-04 not text-extracted) and STALE flags as known coverage gaps — ingest what exists, flag the rest.

### Pitfall 6: Selless ticket-history field stability (D-05)
**What goes wrong:** SEL-03 served via Selless API, but whether Selless exposes ticket history with adequate/stable fields is **unconfirmed**.
**How to avoid:** Model `TicketHistory` as a tolerant Pydantic schema behind the seam; `MockSellessClient` returns a representative fixture; flag "confirm ticket-history endpoint + fields" as a human-verify item. Do not assume Freshdesk-shaped fields.

## Code Examples

### Idempotent ingest upsert (KB-03/KB-04, D-16)
```python
# content-hash keyed upsert makes re-ingest safe + idempotent
import hashlib
def content_hash(source: str, body: str) -> str:
    return hashlib.sha256(f"{source}\x00{body}".encode()).hexdigest()

# INSERT ... ON CONFLICT (content_hash) DO UPDATE SET embedding=..., snapshot_version=...
# unchanged chunks are no-ops on re-run; changed prose re-embeds; removed chunks pruned by run-id sweep
```

### Voyage embedding (query vs document input_type)
```python
# Source: docs.voyageai.com/docs/embeddings
import voyageai
vo = voyageai.Client()  # reads VOYAGE_API_KEY
# ingest:
docs = vo.embed(chunks, model="voyage-3-large", input_type="document", output_dimension=1024)
# query time:
q = vo.embed([query], model="voyage-3-large", input_type="query", output_dimension=1024)
```

### Exact threshold lookup (D-10, anti-hallucination)
```python
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def lookup_threshold(threshold_id: str) -> ThresholdResult:
    """Exact numeric/temporal threshold by ID (e.g. THR-03). Never LLM-inferred."""
    row = await db.fetchrow("SELECT * FROM knowledge.policy_threshold WHERE threshold_id=$1", threshold_id)
    return ThresholdResult(**row)  # value, source, conflict_id, override_resolution if any
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastMCP 1.0 standalone | Folded into official `mcp` SDK; FastMCP 3.x is the high-level layer | 2024→2026 | Install `fastmcp` (3.3.1) which depends on `mcp` (1.27.2) |
| Pure vector search | Hybrid (vector + FTS + trgm) fused with RRF | 2025-2026 standard | ~62%→~84% retrieval precision per published benchmarks |
| IVFFlat | HNSW default for pgvector | pgvector 0.5+ | Better speed-recall; use `vector_cosine_ops` |
| `voyageai` 0.2.x | 0.3.7 adds `base_url`, `output_dimension`, rerankers | 2025-12-16 | Use 0.3.7 |

**Deprecated/outdated:**
- MCP SDK **v2** (TS or Python): pre-alpha — CLAUDE.md forbids. Stay v1.x.
- Merged Selless+Knowledge MCP: violates locked architecture.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Selless exposes order/customer/history/product/inventory via an HTTP API with auth | Selless MCP | HIGH — entire Selless slice's live wiring depends on it; mitigated by client seam + mock so build proceeds regardless |
| A2 | Selless exposes prior ticket history with adequate/stable fields (D-05) | Selless MCP | MEDIUM — SEL-03 may need a fallback source if Selless can't serve it; flag for human-verify |
| A3 | `pgvector` is the correct PyPI dist name for the asyncpg codec binding | Stack | LOW — confirm at install; alternative is manual codec registration |
| A4 | `voyageai==0.3.7` imports/runs under Python 3.14 despite `requires-python <3.15` | Stack | MEDIUM — may need pin + manual override; blocks embeddings if truly incompatible |
| A5 | FastMCP per-tool rate limiting needs a thin custom middleware (built-in is server-wide) | Pitfall 3 | LOW — MVP can ship server-wide bucket |
| A6 | Snapshot prose (SVG/PDF) is extractable to usable text for chunking | Ingest | LOW-MEDIUM — thresholds already de-risked via D-10 structured tables |

## Open Questions

1. **Selless API surface (endpoints/auth/field shapes) — THE #1 risk (D-01/D-05).**
   - What we know: internal proprietary platform, "built for the platform not for AI", scattered; no public docs (web search found only unrelated Selldone/Selly).
   - What's unclear: base URL, auth model (key? OAuth? session?), endpoint paths, response shapes, whether ticket history is exposed, rate limits, pagination.
   - Recommendation: **Defer all concrete endpoint wiring to user-supplied API docs.** Build `SellessClient` Protocol + `MockSellessClient` (fixtures) now; `HttpSellessClient` with paths as `# TODO from docs` config. Plan a `checkpoint:human-verify` task that ingests user docs and fills the seam. Everything testable (tools, whitelist, scope, audit, rate-limit) is built against the mock.

2. **Voyage API key + cost at ingest scale.**
   - What we know: KB is small (thousands of chunks) — one-time/occasional embed cost is negligible.
   - Recommendation: add `voyage_api_key` to config; ingest is offline/batch so no hot-path latency concern.

3. **Per-tool vs server-wide rate limits (D-08, discretion).**
   - Recommendation: MVP server-wide token bucket; note per-tool refinement as a follow-up.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | pgvector store, exact tables, audit | ✓ (local) | 16.14 (Homebrew) | — |
| pgvector extension | Vector column + HNSW | ✗ (not confirmed installed in ext) | — | `CREATE EXTENSION` in migration; install ext binary if missing |
| Python | Both servers, ingest | ✓ | 3.14.5 | — (watch voyageai `<3.15` cap, Pitfall 1) |
| pip / uv | Packaging | ✓ | pip 26.1.1 | — |
| Docker | Local stack (compose) | ✗ | — | Run Postgres via Homebrew (already present); compose optional for parity |
| Selless API creds | Live Selless reads | ✗ | — | **MockSellessClient** for all dev/test; live wiring deferred to user docs |
| Voyage API key | Embeddings | ✗ (not in env) | — | None for live embed; required before ingest can run against Voyage |

**Missing dependencies with no fallback (block live, not build):**
- Selless API docs/creds — blocks LIVE Selless reads only (build proceeds on mock).
- Voyage API key — blocks actual embedding (schema/pipeline build proceeds; can unit-test with a stub embedder).

**Missing dependencies with fallback:**
- pgvector extension → install + `CREATE EXTENSION` in Alembic 0002.
- Docker → use existing Homebrew Postgres.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio (auto mode) + respx 0.23.1 (HTTP mock) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (asyncio_mode=auto, function-scope loop) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/` |
| Real-dependency marker | `@pytest.mark.sandbox` (skipped in CI) — extend for live Selless/Voyage smoke |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KB-03 | Ingest builds chunks + exact tables from snapshots | integration | `pytest tests/ingest/test_pipeline.py -x` | ❌ Wave 0 |
| KB-04 | Re-ingest is idempotent (re-run = no dup, changed re-embeds) | integration | `pytest tests/ingest/test_idempotent.py -x` | ❌ Wave 0 |
| KB-05 | semantic_search returns citations w/ source/authority/recency/conflict | integration | `pytest tests/knowledge_mcp/test_semantic.py -x` | ❌ Wave 0 |
| KB-05 | lookup_threshold returns exact value (D-10) | unit | `pytest tests/knowledge_mcp/test_exact.py -x` | ❌ Wave 0 |
| D-13 | conflicting passages → all + conflict flag | unit | `pytest tests/knowledge_mcp/test_conflict.py -x` | ❌ Wave 0 |
| D-14 | override row resolves a conflict | unit | `pytest tests/knowledge_mcp/test_override.py -x` | ❌ Wave 0 |
| SEL-01/02/03 | keyed tools return whitelisted fields (mock) | unit | `pytest tests/selless_mcp/test_tools.py -x` | ❌ Wave 0 |
| D-04 | whitelist hard-denies payment/cost/other-customer fields | unit | `pytest tests/selless_mcp/test_whitelist.py -x` | ❌ Wave 0 |
| D-03 | no free-text/cross-customer search possible | unit | `pytest tests/selless_mcp/test_scope.py -x` | ❌ Wave 0 |
| SEL-04 | every call writes a PII-redacted audit row | integration | `pytest tests/selless_mcp/test_audit.py -x` | ❌ Wave 0 |
| SEL-04 | rate limit enforced at MCP boundary | unit | `pytest tests/selless_mcp/test_rate_limit.py -x` | ❌ Wave 0 |

### Standalone Demonstrable End-State (Claude's-discretion smoke test — mirror Phase 2 sandbox-demo)
A single script (`tests/smoke/test_grounding_demo.py`, `@pytest.mark.sandbox`) acting as an **MCP client** that:
1. Calls Knowledge MCP `semantic_search("warranty window")` → asserts ≥1 `Citation` with source + authority_rank + `conflict=True` (warranty CONTRA-01 is a known HIGH conflict — perfect demo case).
2. Calls Knowledge MCP `lookup_threshold("THR-03")` → asserts exact `45 days from purchase` (proves D-10 exact path).
3. Calls Knowledge MCP `get_template("C1")` → asserts a template scaffold returned (D-11).
4. Calls Selless MCP `get_order_status(order_id=...)` against `MockSellessClient` → asserts whitelisted fields only, then asserts a redacted `audit.selless_audit` row was written (SEL-04) and that a rate-limit kicks in past the bucket.

This proves all four success criteria standalone with no Phase-4 orchestrator. The live variant (real Selless/Voyage) runs under the `sandbox` marker once creds exist.

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (mock-backed, fast)
- **Per wave merge:** `pytest tests/` (full mock suite)
- **Phase gate:** full suite green + the standalone smoke demo (mock) passing before `/gsd:verify-work`; live `sandbox` smoke once Selless/Voyage creds supplied.

### Wave 0 Gaps
- [ ] `tests/ingest/test_pipeline.py` + `test_idempotent.py` — KB-03/KB-04
- [ ] `tests/knowledge_mcp/test_semantic.py`, `test_exact.py`, `test_conflict.py`, `test_override.py` — KB-05/D-13/D-14
- [ ] `tests/selless_mcp/test_tools.py`, `test_whitelist.py`, `test_scope.py`, `test_audit.py`, `test_rate_limit.py` — SEL-01..04
- [ ] `tests/smoke/test_grounding_demo.py` — standalone end-state (sandbox marker)
- [ ] `tests/conftest.py` additions — db_pool w/ pgvector codec, MockSellessClient fixtures, stub embedder (avoid Voyage calls in unit tests)
- [ ] Framework install: `uv add fastmcp voyageai pgvector` (behind human-verify) + `CREATE EXTENSION vector`

## Security Domain

> `security_enforcement` not set to false → included.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (Selless API auth + Voyage key) | API keys in env, never logged (`Settings.__repr__` redaction) |
| V3 Session Management | no | MCP servers are stateless tool surfaces |
| V4 Access Control | yes | D-04 field whitelist + D-03 keyed-only access; readOnlyHint; no cross-customer search |
| V5 Input Validation | yes | Pydantic tool-arg schemas; `strict_input_validation` option; order_id/email validated |
| V6 Cryptography | no (no new crypto) | Reuse TLS via httpx; no hand-rolled crypto |
| V7 Logging | yes | Presidio redaction before any audit/log write (D-06/D-07); audit table is the trail |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII leak into logs/traces | Information Disclosure | `redact_text()` (Presidio) before persist (D-06) |
| Cross-customer data access via free-text query | Elevation / Info Disclosure | D-03 keyed-only tools; no search endpoint; whitelist (D-04) |
| Over-exposure of sensitive fields (payment/cost) | Information Disclosure | D-04 hard-deny list as the model boundary |
| SQL injection in retrieval | Tampering | asyncpg parameterized queries ($1) — never string-format |
| Prompt-injection via retrieved KB content (downstream) | Tampering | Out of Phase-3 scope (Phase-4 guards); Phase 3 returns cited+flagged passages so Phase-4 can react |
| API abuse / runaway calls | DoS | MCP-boundary rate limit (D-08) independent of Freshdesk limiter |
| Slopsquat on new deps | Supply chain | human-verify checkpoint before install (slopcheck unavailable this session) |

## Project Constraints (from CLAUDE.md)
- **Two separate MCPs** — never merged (Selless transactional + Knowledge RAG).
- **No reading raw Confluence/Sheets per reply** — centralized ingest→normalize→index into pgvector with citations.
- **MCP SDK v1.x only** — v2 pre-alpha forbidden.
- **Locked stack:** pgvector 0.8.x on Postgres 16/17 (HNSW), Voyage `voyage-3-large`, FastMCP 3.x / MCP Python SDK v1.x, hybrid search (`pg_trgm`/FTS + vector), optional reranker (Cohere/Voyage), Presidio PII redaction, httpx + tenacity.
- **Never log raw ticket text / PII** — Presidio redaction before any sink.
- **GSD workflow enforcement** — edits go through a GSD command.
- **Postgres-as-single-datastore** (Phase-2 D-01) — no second datastore; `queue` schema isolated; Phase 3 uses new schemas.

## Sources

### Primary (HIGH confidence)
- gofastmcp.com/servers/tools — tool defs, structured output, `readOnlyHint`, validation modes
- gofastmcp.com/servers/middleware — `on_call_tool`, `add_middleware`, audit pattern
- gofastmcp.com/python-sdk/fastmcp-server-middleware-rate_limiting — TokenBucket/SlidingWindow limiters
- docs.voyageai.com/docs/embeddings — `voyage-3-large` dims (1024 default), `input_type` query/document, batch limits
- pypi.org/project/voyageai — 0.3.7 latest (2025-12-16)
- github.com/pgvector/pgvector — HNSW syntax, 2000-dim limit, `vector_cosine_ops`
- Local probes — psql 16.14, Python 3.14.5, npm `@modelcontextprotocol/sdk` 1.29.0, pip index versions
- Phase-1 artifacts — POLICY-THRESHOLD-INDEX.md (25 thresholds), CONFLICT-INVENTORY.md (5 CONTRA/5 STALE/8 MISS), CODE-MAP.md
- Phase-2 code — src/freshdesk_io/client.py, src/config.py, src/guards/pii.py, migrations/0001

### Secondary (MEDIUM confidence)
- dev.to (lpossamai) — hybrid search + RRF (k=60); ~62%→~84% precision
- Neon / Crunchy / Google Cloud / AWS blogs — HNSW params (m=16, ef_construction=64) cross-corroborated
- jlowin.dev / apigene / mcpcat — FastMCP 3.x feature confirmation

### Tertiary (LOW confidence — needs validation)
- Selless API: NO authoritative source found (web search returned only unrelated Selldone/Selly). **All Selless endpoint/auth/field claims are deferred to user-supplied docs.**

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified on PyPI/npm/local; CLAUDE.md-mandated
- FastMCP scaffolding: HIGH — official docs
- RAG storage/retrieval: HIGH — official pgvector/Voyage docs + corroborated hybrid pattern
- Ingest pipeline: MEDIUM — pattern clear; SVG/PDF extraction quality unverified (de-risked by D-10)
- Selless API: LOW — undocumented; mitigated entirely by client-seam + mock strategy
- Phase-2 reuse: HIGH — read actual source files

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (stack stable; re-confirm voyageai/fastmcp versions at install)
