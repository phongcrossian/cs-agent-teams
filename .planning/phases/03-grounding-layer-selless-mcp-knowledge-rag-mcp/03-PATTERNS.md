# Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP) — Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 20 new/modified files
**Analogs found:** 18 / 20 (2 greenfield — FastMCP server scaffold and hybrid-search RRF have no codebase analog; use RESEARCH.md patterns)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/selless_mcp/server.py` | service (MCP server) | request-response | `src/freshdesk_io/client.py` | role-match (HTTP boundary, auth, scope) |
| `src/selless_mcp/client.py` | service (HTTP client) | request-response | `src/freshdesk_io/client.py` | **exact** (httpx+tenacity, retry/backoff, error taxonomy) |
| `src/selless_mcp/models.py` | model | transform | `src/freshdesk_io/client.py` lines 44-45 (imports models) | role-match |
| `src/selless_mcp/whitelist.py` | utility | transform | `src/guards/pii.py` (boundary filter) | role-match |
| `src/selless_mcp/audit.py` | middleware | event-driven | `src/guards/pii.py` + migration 0001 pattern | role-match |
| `src/selless_mcp/errors.py` | utility | request-response | `src/freshdesk_io/errors.py` | **exact** |
| `src/knowledge_mcp/server.py` | service (MCP server) | request-response | `src/freshdesk_io/client.py` (boundary pattern) | partial-match |
| `src/knowledge_mcp/retrieval.py` | service | request-response | `src/freshdesk_io/client.py` (async DB pattern) | partial-match |
| `src/knowledge_mcp/exact.py` | service | CRUD | `src/freshdesk_io/client.py` (async query pattern) | partial-match |
| `src/knowledge_mcp/conflict.py` | utility | transform | *(no analog)* | no-analog |
| `src/knowledge_mcp/embeddings.py` | service | request-response | `src/freshdesk_io/client.py` (external API client) | role-match |
| `src/knowledge_mcp/models.py` | model | transform | `src/freshdesk_io/client.py` models import pattern | role-match |
| `src/ingest/pipeline.py` | service | batch | `src/freshdesk_io/client.py` (async, idempotent) | partial-match |
| `src/ingest/sources.py` | utility | file-I/O | *(no strong analog)* | no-analog |
| `src/ingest/normalize.py` | utility | transform | `src/guards/pii.py` (text transform pattern) | role-match |
| `src/ingest/chunk.py` | utility | transform | `src/guards/pii.py` (text processing) | partial-match |
| `src/ingest/cli.py` | utility | batch | *(CLI, no analog)* | no-analog |
| `src/config.py` | config | — | `src/config.py` | **exact** (extend in-place) |
| `migrations/versions/0002_knowledge_schema.py` | migration | — | `migrations/versions/0001_initial_queue_schema.py` | **exact** |
| `migrations/versions/0003_selless_audit.py` | migration | — | `migrations/versions/0001_initial_queue_schema.py` | **exact** |

---

## Pattern Assignments

### `src/selless_mcp/client.py` (service, request-response)

**Analog:** `src/freshdesk_io/client.py`

**Imports pattern** (lines 24–46):
```python
from __future__ import annotations

import random
import logging
from typing import Any, Protocol, runtime_checkable

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    RetryCallState,
)

from src.selless_mcp.errors import (
    SelessFatalError,
    SellessRateLimitError,
    SellessTransientError,
)
from src.selless_mcp.models import OrderDetail, CustomerInfo, PurchaseHistory
```

**Wait strategy pattern** (lines 53–61 of analog — copy verbatim, swap error types):
```python
def _selless_wait(retry_state: RetryCallState) -> float:
    """Honor Retry-After on rate-limit, else exp+jitter."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, SellessRateLimitError):
        return float(exc.retry_after)
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    return base + random.uniform(-1.0, 1.0)
```

**Client seam — Protocol + Http + Mock** (new pattern, no direct analog):
```python
@runtime_checkable
class SellessClient(Protocol):
    """Seam isolating the undocumented Selless API from MCP tools.

    MockSellessClient for tests; HttpSellessClient for prod.
    Base URL: https://api.selless.dev/admin/csm/order/public/tickets
    (confirmed 2026-06-02, gateway-trust auth model — no token needed).
    """
    async def fetch_order(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_customer(self, customer_id: str) -> dict[str, Any]: ...
    async def resolve_order(self, param: str) -> dict[str, Any]: ...
    async def fetch_dispute(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_refunds(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_ticket_mapping(self, fd_ticket_id: str) -> dict[str, Any]: ...


class HttpSellessClient:
    """Production httpx+tenacity impl. Mirror FreshdeskClient.__init__ exactly."""
    def __init__(
        self,
        base_url: str,           # from settings.selless_api_base_url
        max_attempts: int = 5,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None: ...

    def _client(self) -> httpx.AsyncClient:
        # Mirror analog lines 127-134: lazy build, no auth header needed
        # (gateway-trust model; add auth header config hook for prod VPN/gateway)
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
            )
        return self._http_client

    def _make_retry_decorator(self):
        # Copy analog lines 136-145 verbatim, swap error types
        return retry(
            stop=stop_after_attempt(self._max_attempts),
            wait=_selless_wait,
            retry=retry_if_exception_type(
                (SellessRateLimitError, SellessTransientError, httpx.TransportError)
            ),
            reraise=True,
        )

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        # Endpoint: GET /po/{id}  (internal id, not human code)
        retry_dec = self._make_retry_decorator()
        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/po/{order_id}")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()
        return await _call()

    async def resolve_order(self, param: str) -> dict[str, Any]:
        # Constrained resolve_order (D-03): wraps /po/search with exact-key only.
        # param = exact order code (e.g. "25044-67") OR verified customer email.
        # NEVER returns a fuzzy/browse list — only exact single-identity match.
        # Endpoint: GET /po/search?param={param}&skip=0&take=1
        ...


class MockSellessClient:
    """Test double — returns fixture dicts. No HTTP calls."""
    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        return FIXTURE_ORDER  # define fixture at module level
```

**Status → error classification** (mirror `src/freshdesk_io/rate_limit.py` lines 34–51):
```python
def _raise_for_selless_status(response: httpx.Response) -> None:
    status = response.status_code
    if status == 429:
        retry_after = parse_retry_after(dict(response.headers))
        raise SellessRateLimitError(retry_after=retry_after)
    classification = classify_status(status)   # reuse rate_limit.classify_status
    if classification == "fatal":
        raise SelessFatalError(f"HTTP {status}")
    if classification == "transient":
        raise SellessTransientError(f"HTTP {status}")
```

---

### `src/selless_mcp/errors.py` (utility, request-response)

**Analog:** `src/freshdesk_io/errors.py` — **copy exactly, rename prefix**

```python
# src/selless_mcp/errors.py — mirror freshdesk_io/errors.py 1:1

class SellessRateLimitError(Exception):
    """HTTP 429. Carries retry_after seconds."""
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")

class SellessTransientError(Exception):
    """5xx / transport timeout. Safe to retry."""
    def __init__(self, message: str = "") -> None:
        super().__init__(message)

class SelessFatalError(Exception):
    """400/401/403/404/409. Dead-letter immediately."""
    def __init__(self, message: str = "") -> None:
        super().__init__(message)
```

---

### `src/selless_mcp/models.py` (model, transform)

**Analog:** `src/freshdesk_io/client.py` line 44 (imports Pydantic models); Phase-2 `src/freshdesk_io/models.py` (not read but pattern is Pydantic BaseModel with explicit fields)

**Core pattern — D-04 whitelist as the model boundary:**
```python
from pydantic import BaseModel, Field
from typing import Optional

# ALLOW-listed fields only (D-04, 03-SELLESS-API.md §4)
# NEVER add payment.*, total_product_cost, supplier_*, payload fields.

class Address(BaseModel):
    first_name: str; last_name: str; email: str; phone: str
    address1: str; address2: Optional[str] = None
    city: str; state: str; country: str; postal_code: str

class DoStatus(BaseModel):
    id: str; code: str; status: str; odo_status: str
    status_date_processing: Optional[str] = None
    status_date_delivered: Optional[str] = None
    trackings: list[str] = Field(default_factory=list)
    failed_reason: Optional[str] = None

class OrderDetail(BaseModel):
    """Whitelisted view of PoViewModel. No payment/cost/supplier fields."""
    id: str; code: str; status: str; created: str
    amount: float; items_amount: float; tax_amount: float
    discount: float; shipping: float
    shipping_address: Address
    billing_address: Address
    delivery_orders: list[DoStatus] = Field(default_factory=list)

class CustomerInfo(BaseModel):
    """Whitelisted view of CustomerViewModel."""
    id: str; first_name: str; last_name: str; full_name: str
    email: str; phone: str
    email_status: Optional[str] = None
    phone_status: Optional[str] = None

class ResolvedOrder(BaseModel):
    """Result of resolve_order: single identity match only (D-03)."""
    id: str; code: str; customer_id: str; customer_email: str
```

---

### `src/selless_mcp/server.py` (service/MCP server, request-response)

**Analog:** `src/freshdesk_io/client.py` (architecture boundary docstring pattern); FastMCP patterns from RESEARCH.md §Pattern 1 and §Pattern 3

**Imports + server init pattern:**
```python
"""
SellessMCP — the ONLY module permitted to call the Selless API.

Architecture boundary: no other module may call Selless directly (D-08).
All tools are read-only (readOnlyHint=True). Every call is rate-limited,
scope-enforced, field-whitelisted (D-04), and audit-logged (D-07).
"""
from __future__ import annotations

import time
import logging
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.selless_mcp.client import SellessClient, HttpSellessClient
from src.selless_mcp.models import OrderDetail, CustomerInfo, ResolvedOrder
from src.selless_mcp.whitelist import apply_order_whitelist, apply_customer_whitelist
from src.selless_mcp.audit import AuditMiddleware
from src.config import settings

logger = logging.getLogger(__name__)

mcp = FastMCP(name="SellessMCP", on_duplicate_tools="error")
```

**Tool definition pattern** (RESEARCH.md §Pattern 1):
```python
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_order_status(order_id: str) -> OrderDetail:
    """Return whitelisted order status for a single order by internal ID.

    Keyed lookup only — no cross-customer search (D-03).
    Returns only D-04 allow-listed fields.
    """
    raw = await _client().fetch_order(order_id)
    return apply_order_whitelist(raw)  # D-04 hard filter via whitelist.py

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def resolve_order(param: str) -> ResolvedOrder:
    """Resolve an exact order code OR verified customer email to a single order identity.

    Wraps /po/search with exact-key constraint (D-03 amendment 2026-06-02).
    NEVER returns a fuzzy/browse list.
    """
    raw = await _client().resolve_order(param)
    return ResolvedOrder(**raw)
```

**Middleware wiring** (RESEARCH.md §Pattern 3):
```python
from fastmcp.server.middleware import RateLimitingMiddleware
# D-08: MCP boundary owns rate-limit independent of Freshdesk limiter
# MVP: server-wide token bucket (60 req/min, burst 10)
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=1, burst_capacity=10))
mcp.add_middleware(AuditMiddleware())   # runs around every tool call; writes redacted audit row
```

---

### `src/selless_mcp/audit.py` (middleware, event-driven)

**Analog:** `src/guards/pii.py` (Presidio singleton pattern) + `migrations/0001` audit table pattern + RESEARCH.md §Pattern 3

**Core middleware pattern:**
```python
"""
AuditMiddleware — SEL-04 / D-06 / D-07.

Every Selless tool call writes a PII-redacted audit row to audit.selless_audit.
Real PII passes to the drafter; redacted before any log/DB write (D-06).
"""
from __future__ import annotations
import time
import logging
from fastmcp.server.middleware import Middleware, MiddlewareContext
from src.guards.pii import redact_text          # D-06: REUSE existing Presidio wrapper

logger = logging.getLogger(__name__)

class AuditMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool = context.message.name
        raw_key = str(context.message.arguments or {})
        t0 = time.monotonic()
        outcome = "error"
        result = None
        try:
            result = await call_next(context)
            outcome = "ok"
            return result
        except Exception:
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000
            await _write_audit_row(
                tool=tool,
                input_key=redact_text(raw_key),                        # D-06
                fields_returned=redact_text(_summarize_result(result)), # D-06
                latency_ms=latency_ms,
                outcome=outcome,
            )

async def _write_audit_row(
    tool: str, input_key: str, fields_returned: str,
    latency_ms: float, outcome: str,
) -> None:
    """Insert into audit.selless_audit (schema from migration 0003)."""
    # Use the shared asyncpg pool; parameterized query ($1…) — no string format
    ...
```

**PII singleton reuse** (from `src/guards/pii.py` lines 39–53):
```python
# DO NOT re-implement Presidio. Import from src.guards.pii:
from src.guards.pii import redact_text
# redact_text() is safe to call on empty strings (no-op) — see pii.py lines 71-73
```

---

### `src/selless_mcp/whitelist.py` (utility, transform)

**Analog:** `src/guards/pii.py` (boundary filter with explicit entity list — same structural role)

**Pattern:**
```python
"""
D-04 field whitelist — the ONLY place that maps raw Selless API dicts
to safe Pydantic models. Never call pass-through; always map-and-whitelist.

DENY list (hard — raise if present in raw): payment.*, total_product_cost,
supplier_id/code/name, contract_id, is_fake_contract,
fulfillment_version_id/name, DisputeViewModel.payload,
HistoryViewModel.payload, handling_fee.
See 03-SELLESS-API.md §4 for the full list.
"""
from src.selless_mcp.models import OrderDetail, CustomerInfo

_DENY_FIELDS = frozenset({
    "payment", "total_product_cost", "supplier_id", "supplier_code",
    "supplier_name", "contract_id", "is_fake_contract",
    "fulfillment_version_id", "fulfillment_version_name",
    "handling_fee",
})

def apply_order_whitelist(raw: dict) -> OrderDetail:
    """Map raw PoViewModel dict → OrderDetail (allow-listed fields only)."""
    # Explicit field extraction — never **raw spread
    return OrderDetail(
        id=raw["id"],
        code=raw["code"],
        status=raw["status"],
        # ... map only ALLOW-listed fields; silently drop everything else
    )
```

---

### `src/knowledge_mcp/server.py` (service/MCP server, request-response)

**Analog:** `src/freshdesk_io/client.py` (boundary docstring + module-level singleton pattern); FastMCP patterns from RESEARCH.md §Pattern 1 and §Pattern 2

**Imports + server init:**
```python
"""
KnowledgeMCP — semantic RAG + exact-lookup grounding surface (KB-03..KB-05).

Architecture boundary: Phase-4 orchestrator calls these tools; never reads
raw Confluence/Sheets directly (CLAUDE.md constraint).
"""
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from src.knowledge_mcp.models import SemanticSearchResult, ThresholdResult, TemplateResult
from src.knowledge_mcp.retrieval import hybrid_search, assemble_citations
from src.knowledge_mcp.exact import lookup_threshold_row, lookup_code_row, fetch_template_row
from src.knowledge_mcp.conflict import apply_conflict_flag, apply_override

mcp = FastMCP(name="KnowledgeMCP", on_duplicate_tools="error")
```

**Tool definitions** (RESEARCH.md §Pattern 1 + §Pattern 2):
```python
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def semantic_search(query: str, top_k: int = 5) -> SemanticSearchResult:
    """Hybrid semantic search over policy prose. Returns cited passages + conflict flag.

    D-13: if conflicting passages retrieved, returns ALL + conflict=True.
    D-14: if override row exists, resolved_by_override=True and winning passage first.
    D-15: stale passages carry recency_flag="stale" in Citation metadata.
    """
    candidates = await hybrid_search(query, top_k=top_k)
    citations = assemble_citations(candidates)
    citations = apply_override(citations)   # D-14: override table wins if present
    conflict = apply_conflict_flag(citations)  # D-13: flag if conflicting sources
    return SemanticSearchResult(citations=citations, conflict=conflict.has_conflict,
                                resolved_by_override=conflict.resolved)

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def lookup_threshold(threshold_id: str) -> ThresholdResult:
    """Exact numeric/temporal threshold by ID (e.g. THR-03). D-10: never LLM-inferred."""
    return await lookup_threshold_row(threshold_id)

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def lookup_code(code: str) -> dict:
    """Exact workflow code → action mapping (D-10). e.g. 'C1' → action + template ref."""
    return await lookup_code_row(code)

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_template(code: str) -> TemplateResult:
    """Fetch reply template scaffold by code/scenario (D-11). Keyed lookup, not semantic."""
    return await fetch_template_row(code)
```

---

### `src/knowledge_mcp/models.py` (model, transform)

**Analog:** RESEARCH.md §Pattern 2 (Citation shape); `src/freshdesk_io/client.py` Pydantic model import pattern

```python
from pydantic import BaseModel, Field
from typing import Optional

class Citation(BaseModel):
    text: str
    source: str             # "WorkFlow.svg" | "Email Templates/{name}" | "Confluence/{slug}"
    source_type: str        # "policy_prose" | "template" | "threshold" | "code_map"
    authority_rank: int     # D-12: WorkFlow=3 > Templates=2 > Confluence=1 (stored in metadata)
    recency_flag: Optional[str] = None  # D-15: "stale" if CONFLICT-INVENTORY flagged
    snapshot_version: str   # content hash from ingest run
    score: float            # RRF fused score

class SemanticSearchResult(BaseModel):
    citations: list[Citation]
    conflict: bool              # D-13: True if conflicting passages retrieved
    resolved_by_override: bool  # D-14: True if policy_resolution row applied

class ThresholdResult(BaseModel):
    threshold_id: str           # e.g. "THR-03"
    value: str                  # e.g. "45 days from purchase"
    source: str
    conflict_id: Optional[str] = None   # e.g. "CONTRA-01" if in CONFLICT-INVENTORY
    override_resolution: Optional[str] = None

class TemplateResult(BaseModel):
    code: str
    scenario: str
    subject_template: str
    body_template: str
    source: str
    authority_rank: int
```

---

### `src/knowledge_mcp/retrieval.py` (service, request-response)

**Analog:** `src/freshdesk_io/client.py` (async method + parameterized asyncpg query pattern, lines 211–228); hybrid search pattern from RESEARCH.md §Pattern 4

**Async DB query pattern** (mirror client.py lines 211–228):
```python
async def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """RRF-fused hybrid: vector ANN + FTS + trgm. Returns over-fetched candidates."""
    pool = get_db_pool()   # reuse Phase-2 pool; add pgvector codec on init (Pitfall 2)
    async with pool.acquire() as conn:
        # 1. embed query (Voyage voyage-3-large, input_type="query")
        q_vec = await embed_query(query)
        # 2. vector ANN (top 20)
        vec_rows = await conn.fetch(
            """
            SELECT id, body, metadata, embedding <=> $1::vector AS vec_dist
            FROM knowledge.kb_chunk
            ORDER BY vec_dist LIMIT 20
            """,
            q_vec,   # asyncpg parameterized — never f-string
        )
        # 3. FTS (top 20)
        fts_rows = await conn.fetch(
            """
            SELECT id, body, metadata,
                   ts_rank(body_tsv, plainto_tsquery('english', $1)) AS fts_rank
            FROM knowledge.kb_chunk
            WHERE body_tsv @@ plainto_tsquery('english', $1)
            ORDER BY fts_rank DESC LIMIT 20
            """,
            query,
        )
        # 4. RRF fusion (k=60) in Python — 1/(60+rank)
        return _rrf_fuse(vec_rows, fts_rows, top_k=top_k)
```

---

### `src/knowledge_mcp/exact.py` (service, CRUD)

**Analog:** `src/freshdesk_io/client.py` (async single-row fetch pattern, lines 234–249); RESEARCH.md §Code Examples exact threshold lookup

```python
async def lookup_threshold_row(threshold_id: str) -> ThresholdResult:
    """D-10: exact row from knowledge.policy_threshold. No LLM interpretation."""
    pool = get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM knowledge.policy_threshold WHERE threshold_id = $1",
            threshold_id,   # parameterized — never string-format (security note)
        )
    if row is None:
        raise KeyError(f"threshold_id not found: {threshold_id}")
    return ThresholdResult(**dict(row))
```

---

### `src/knowledge_mcp/embeddings.py` (service, request-response)

**Analog:** `src/freshdesk_io/client.py` (external API client with lazy-init singleton pattern, lines 127–134)

```python
"""Voyage voyage-3-large embeddings wrapper (CLAUDE.md mandate)."""
import voyageai
from functools import lru_cache

@lru_cache(maxsize=1)
def _vo_client() -> voyageai.Client:
    """Lazy singleton — reads VOYAGE_API_KEY from env. Mirror pii.py _get_engines()."""
    return voyageai.Client()  # reads VOYAGE_API_KEY from environment

async def embed_query(text: str) -> list[float]:
    """Embed a single query string. input_type='query' (Voyage distinction)."""
    result = _vo_client().embed([text], model="voyage-3-large",
                                input_type="query", output_dimension=1024)
    return result.embeddings[0]

async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for ingest. input_type='document'."""
    result = _vo_client().embed(texts, model="voyage-3-large",
                                input_type="document", output_dimension=1024)
    return result.embeddings
```

---

### `src/knowledge_mcp/conflict.py` (utility, transform)

**Analog:** No codebase analog — greenfield. Use RESEARCH.md D-13/D-14 logic.

```python
"""
D-13: surface all conflicting passages + conflict flag.
D-14: check policy_resolution override table; winning row resolves the conflict.
MCP NEVER self-arbitrates. Returns all + flag; Phase-4 escalation reacts.
"""
from dataclasses import dataclass

@dataclass
class ConflictResult:
    has_conflict: bool
    resolved: bool   # True if a policy_resolution row applied

def apply_conflict_flag(citations: list[Citation]) -> ConflictResult:
    """D-13: detect conflicting passages by source_type + conflict_id metadata."""
    conflict_ids = [c for c in citations if c.recency_flag == "stale"
                    or _has_known_conflict(c)]
    return ConflictResult(has_conflict=bool(conflict_ids), resolved=False)

async def apply_override(citations: list[Citation]) -> list[Citation]:
    """D-14: if policy_resolution row exists for a conflict_id, put winner first."""
    # SELECT from knowledge.policy_resolution WHERE conflict_id IN (...)
    # parameterized asyncpg query
    ...
```

---

### `src/ingest/pipeline.py` (service, batch)

**Analog:** `src/freshdesk_io/client.py` (idempotent async flow + parameterized upsert pattern); RESEARCH.md §Code Examples idempotent upsert

**Core idempotent upsert pattern** (RESEARCH.md §Code Examples):
```python
import hashlib

def content_hash(source: str, body: str) -> str:
    """Keyed dedup — makes re-ingest idempotent (KB-04 / D-16)."""
    return hashlib.sha256(f"{source}\x00{body}".encode()).hexdigest()

async def upsert_chunk(conn, source: str, body: str, embedding: list[float],
                       metadata: dict, run_id: str) -> None:
    """INSERT ... ON CONFLICT (content_hash) DO UPDATE.

    Unchanged chunks: no-op on re-run.
    Changed prose: re-embeds (new hash → new row or update embedding).
    Uses parameterized query — never f-string (security rule from client.py).
    """
    ch = content_hash(source, body)
    await conn.execute(
        """
        INSERT INTO knowledge.kb_chunk
            (content_hash, source, body, embedding, metadata, snapshot_version)
        VALUES ($1, $2, $3, $4::vector, $5, $6)
        ON CONFLICT (content_hash) DO UPDATE
            SET embedding = EXCLUDED.embedding,
                snapshot_version = EXCLUDED.snapshot_version,
                updated_at = NOW()
        """,
        ch, source, body, embedding, metadata, run_id,
    )
```

---

### `src/ingest/normalize.py` (utility, transform)

**Analog:** `src/guards/pii.py` (text-processing function with no side-effects, entity-list pattern)

```python
"""
GLOSSARY-driven jargon expansion and text normalization.
Reads GLOSSARY.md mappings; replaces internal jargon with plain English
so embeddings don't fragment on CEE/SCE/DNR/RTS/OOS etc.
"""
_JARGON_MAP: dict[str, str] = {
    "CEE": "Customer Experience Excellence",
    "SCE": "Standard Customer Experience",
    "DNR": "Did Not Receive",
    "RTS": "Return To Sender",
    "OOS": "Out Of Stock",
    # ... load from GLOSSARY.md at init
}

def normalize_text(text: str) -> str:
    """Expand jargon, strip internal-only headers, clean whitespace."""
    for term, expansion in _JARGON_MAP.items():
        text = text.replace(term, expansion)
    return text.strip()
```

---

### `src/config.py` (config — extend in-place)

**Analog:** `src/config.py` itself — **extend in-place**, do NOT create a new file

**Extension pattern** (add to `Settings` class, lines 28–116, following existing field pattern):
```python
# === Phase 3 additions — add after existing Freshdesk fields ===

# Selless API (D-01, gateway-trust model confirmed 2026-06-02)
selless_api_base_url: str = Field(
    default="https://api.selless.dev/admin/csm/order/public/tickets",
    description="Selless API base URL (public/tickets prefix). No auth token needed "
                "— access gated at network/gateway layer.",
)
# Reserve field for future gateway auth header if prod VPN requires it
selless_api_gateway_key: str = Field(
    default="",
    description="Optional gateway auth header value — NEVER log this value",
)

# Voyage embeddings (KB-05, CLAUDE.md mandate)
voyage_api_key: str = Field(
    default="",
    description="Voyage AI API key for voyage-3-large embeddings — NEVER log",
)
voyage_model: str = Field(
    default="voyage-3-large",
    description="Voyage embedding model name",
)
voyage_output_dimension: int = Field(
    default=1024,
    description="Embedding dimension (voyage-3-large default: 1024)",
)

# Selless MCP rate limit (D-08, Claude's discretion)
selless_rate_limit_rps: float = Field(
    default=1.0,
    description="Selless MCP server-wide token bucket: requests/second",
)
selless_rate_limit_burst: int = Field(
    default=10,
    description="Selless MCP token bucket burst capacity",
)
```

**`__repr__` extension** (lines 102–109 — add new secrets to the redaction):
```python
def __repr__(self) -> str:
    """Never expose api_key, webhook_secret, selless_api_gateway_key, or voyage_api_key."""
    return (
        f"Settings(send_mode={self.send_mode!r}, "
        f"freshdesk_domain={self.freshdesk_domain!r}, "
        f"database_url={self.database_url!r}, "
        f"selless_api_base_url={self.selless_api_base_url!r}, "
        f"freshdesk_api_key=<REDACTED>, webhook_secret=<REDACTED>, "
        f"selless_api_gateway_key=<REDACTED>, voyage_api_key=<REDACTED>)"
    )
```

---

### `migrations/versions/0002_knowledge_schema.py` (migration)

**Analog:** `migrations/versions/0001_initial_queue_schema.py` — **copy structure exactly**

**Header + schema pattern** (lines 1–28 of analog):
```python
"""Knowledge schema: kb_chunk, policy_threshold, code_map, template_library, policy_resolution.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-02

Design note: knowledge tables live in schema `knowledge` (not `public` or `queue`).
Phase-2 design note (0001 line 9): Phase 3 uses schema `public` by default — OVERRIDE:
use `knowledge` schema to keep separation with `queue`. pgvector extension in `public`.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")          # pgvector (Pitfall 2)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")         # hybrid search

    # kb_chunk: prose chunks (vector + FTS + trgm)
    op.execute("""
        CREATE TABLE knowledge.kb_chunk (
            id               BIGSERIAL PRIMARY KEY,
            content_hash     TEXT        NOT NULL,      -- idempotent upsert key (KB-04)
            source           TEXT        NOT NULL,      -- "WorkFlow.svg" | "Email Templates/..." | "Confluence/..."
            source_type      TEXT        NOT NULL,      -- "policy_prose" | "template" | ...
            authority_rank   INTEGER     NOT NULL,      -- D-12: 3=WorkFlow 2=Templates 1=Confluence
            recency_flag     TEXT,                      -- D-15: "stale" | NULL
            body             TEXT        NOT NULL,
            body_tsv         TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
            embedding        VECTOR(1024),              -- voyage-3-large, 1024-dim
            metadata         JSONB       NOT NULL DEFAULT '{}',
            snapshot_version TEXT        NOT NULL,      -- ingest run id / content hash
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # UNIQUE on content_hash for idempotent upsert (KB-04)
    op.execute("CREATE UNIQUE INDEX idx_kb_chunk_hash ON knowledge.kb_chunk (content_hash)")
    # HNSW index for ANN (D-09, CLAUDE.md mandate: m=16, ef_construction=64)
    op.execute("""
        CREATE INDEX idx_kb_chunk_hnsw ON knowledge.kb_chunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    # FTS + trgm indexes for hybrid search
    op.execute("CREATE INDEX idx_kb_chunk_fts  ON knowledge.kb_chunk USING gin (body_tsv)")
    op.execute("CREATE INDEX idx_kb_chunk_trgm ON knowledge.kb_chunk USING gin (body gin_trgm_ops)")

    # policy_threshold: D-10 exact numeric/temporal thresholds (never vectorized)
    op.execute("""
        CREATE TABLE knowledge.policy_threshold (
            threshold_id         TEXT PRIMARY KEY,   -- e.g. "THR-03"
            label                TEXT NOT NULL,
            value                TEXT NOT NULL,      -- e.g. "45 days from purchase"
            source               TEXT NOT NULL,
            authority_rank       INTEGER NOT NULL,
            conflict_id          TEXT,               -- e.g. "CONTRA-01" from CONFLICT-INVENTORY
            snapshot_version     TEXT NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # code_map: D-10 workflow code → action → template ref (never vectorized)
    op.execute("""
        CREATE TABLE knowledge.code_map (
            code             TEXT PRIMARY KEY,       -- e.g. "C1"
            action           TEXT NOT NULL,
            template_code    TEXT,                   -- FK to template_library.code
            source           TEXT NOT NULL,
            snapshot_version TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # template_library: D-11 separate retrieval type (keyed by code)
    op.execute("""
        CREATE TABLE knowledge.template_library (
            code             TEXT PRIMARY KEY,
            scenario         TEXT NOT NULL,
            subject_template TEXT NOT NULL,
            body_template    TEXT NOT NULL,
            source           TEXT NOT NULL,
            authority_rank   INTEGER NOT NULL DEFAULT 2,  -- D-12: Templates=2
            snapshot_version TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # policy_resolution: D-14 override table for known conflicts
    op.execute("""
        CREATE TABLE knowledge.policy_resolution (
            conflict_id      TEXT PRIMARY KEY,       -- e.g. "CONTRA-01"
            winning_source   TEXT NOT NULL,
            resolved_value   TEXT NOT NULL,
            resolved_by      TEXT,                   -- CS Lead name / "auto"
            resolved_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes            TEXT
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge.policy_resolution")
    op.execute("DROP TABLE IF EXISTS knowledge.template_library")
    op.execute("DROP TABLE IF EXISTS knowledge.code_map")
    op.execute("DROP TABLE IF EXISTS knowledge.policy_threshold")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_trgm")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_fts")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_hnsw")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_hash")
    op.execute("DROP TABLE IF EXISTS knowledge.kb_chunk")
    op.execute("DROP SCHEMA IF EXISTS knowledge")
```

---

### `migrations/versions/0003_selless_audit.py` (migration)

**Analog:** `migrations/versions/0001_initial_queue_schema.py` — **copy structure exactly**

```python
"""Selless audit schema: audit.selless_audit.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-02

SEL-04 / D-07: every Selless MCP call is recorded here with PII-redacted fields.
Schema `audit` is separate from `queue` and `knowledge` for clear access-control.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("""
        CREATE TABLE audit.selless_audit (
            id               BIGSERIAL   PRIMARY KEY,
            tool             TEXT        NOT NULL,       -- tool name (e.g. "get_order_status")
            input_key        TEXT        NOT NULL,       -- PII-redacted order_id / email (D-06)
            fields_returned  TEXT        NOT NULL,       -- PII-redacted summary of returned fields
            latency_ms       FLOAT       NOT NULL,
            outcome          TEXT        NOT NULL,       -- "ok" | "error"
            caller           TEXT,                       -- future: MCP client identity
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # index for per-tool and time-range queries (audit trail queries per customer/order)
    op.execute("CREATE INDEX idx_selless_audit_tool ON audit.selless_audit (tool, created_at)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit.idx_selless_audit_tool")
    op.execute("DROP TABLE IF EXISTS audit.selless_audit")
    op.execute("DROP SCHEMA IF EXISTS audit")
```

---

### `tests/conftest.py` (extend in-place) + `tests/selless_mcp/`, `tests/knowledge_mcp/`, `tests/ingest/`, `tests/smoke/`

**Analog:** `tests/conftest.py` (lines 1–90) + `tests/test_client.py` (lines 1–80)

**New conftest additions** (add to existing `tests/conftest.py` — same structure as existing fixtures):
```python
# ── Phase 3 fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_selless_client():
    """MockSellessClient returning fixture data. No HTTP calls (D-01 seam)."""
    from src.selless_mcp.client import MockSellessClient
    return MockSellessClient()

@pytest.fixture
def stub_embedder(monkeypatch):
    """Replace embed_query / embed_documents with fixed-dim zeros (avoid Voyage calls)."""
    import src.knowledge_mcp.embeddings as emb
    monkeypatch.setattr(emb, "embed_query",
                        lambda text: [0.0] * 1024)
    monkeypatch.setattr(emb, "embed_documents",
                        lambda texts: [[0.0] * 1024 for _ in texts])

@pytest.fixture
async def clean_knowledge_db(db_pool):
    """Truncate knowledge.* + audit.* tables between tests."""
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE knowledge.kb_chunk RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.policy_threshold RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.template_library RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.policy_resolution RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE audit.selless_audit RESTART IDENTITY CASCADE")
    yield

@pytest.fixture
def selless_respx_mock():
    """respx mock for Selless httpx calls. Mirror existing respx_mock fixture."""
    with respx_lib.mock(base_url="https://api.selless.dev") as mock:
        yield mock
```

**Test file pattern** (mirror `tests/test_client.py` lines 1–80):
```python
# tests/selless_mcp/test_tools.py
from __future__ import annotations
import pytest
from src.selless_mcp.server import get_order_status
from src.selless_mcp.models import OrderDetail

@pytest.mark.asyncio
async def test_get_order_status_whitelisted_fields(mock_selless_client):
    """SEL-01: get_order_status returns only D-04 allow-listed fields."""
    result = await get_order_status("test-order-id")
    assert isinstance(result, OrderDetail)
    assert not hasattr(result, "payment")      # DENY: payment.*
    assert not hasattr(result, "handling_fee") # DENY: handling_fee
    assert result.status is not None           # ALLOW: status
```

---

## Shared Patterns

### Boundary Docstring (Architecture Contract)
**Source:** `src/freshdesk_io/client.py` lines 1–22
**Apply to:** `src/selless_mcp/server.py`, `src/knowledge_mcp/server.py`
```python
"""
[ModuleName] — the ONLY module permitted to call [external system].

Architecture boundary: no other module in this codebase may call [system] directly.
"""
```

### httpx + tenacity Retry Pattern
**Source:** `src/freshdesk_io/client.py` lines 53–145
**Apply to:** `src/selless_mcp/client.py` (HttpSellessClient), `src/knowledge_mcp/embeddings.py`

Key elements to copy verbatim (swap class names):
- `_freshdesk_wait` → `_selless_wait` (lines 53–61): custom wait honoring `Retry-After` header
- `_make_retry_decorator` (lines 136–145): `stop_after_attempt` + `retry_if_exception_type`
- Lazy `_http_client` init (lines 127–134): inject for testing, build on first call

### Error Taxonomy (3-class pattern)
**Source:** `src/freshdesk_io/errors.py` (all 35 lines)
**Apply to:** `src/selless_mcp/errors.py`

Exact pattern: `RateLimitError(retry_after: int)` / `TransientError(message)` / `FatalError(message)`

### Status → Error Classification
**Source:** `src/freshdesk_io/rate_limit.py` lines 19–51
**Apply to:** `src/selless_mcp/client.py` (`_raise_for_selless_status`)

Reuse `parse_retry_after()` and `classify_status()` directly from `freshdesk_io.rate_limit` — do not duplicate.

### PII Redaction (before any log/audit/DB write)
**Source:** `src/guards/pii.py` lines 56–82
**Apply to:** `src/selless_mcp/audit.py` (AuditMiddleware), `src/ingest/pipeline.py` (if logging raw text)

```python
# RULE: always call before any log statement, DB persist, or trace containing customer content
from src.guards.pii import redact_text
safe_text = redact_text(raw_text)
# redact_text("") returns "" — safe to call on empty/None-coerced strings (pii.py line 71-73)
```

### Secrets Never Logged (`__repr__` redaction)
**Source:** `src/config.py` lines 102–109
**Apply to:** `src/config.py` extension (add `selless_api_gateway_key`, `voyage_api_key` to REDACTED list)

### Parameterized DB Queries (no string formatting)
**Source:** `src/freshdesk_io/client.py` lines 283–298 (asyncpg `$1`, `$2`...)
**Apply to:** `src/knowledge_mcp/retrieval.py`, `src/knowledge_mcp/exact.py`, `src/selless_mcp/audit.py`, `src/ingest/pipeline.py`

Security rule: NEVER use f-strings or `.format()` in SQL queries — always asyncpg `$N` parameters.

### Alembic Migration Structure
**Source:** `migrations/versions/0001_initial_queue_schema.py` (all 151 lines)
**Apply to:** `migrations/versions/0002_knowledge_schema.py`, `migrations/versions/0003_selless_audit.py`

Key structural elements:
- Header docstring with design note (lines 1–14)
- `revision`, `down_revision`, `branch_labels`, `depends_on` (lines 19–22)
- `op.execute("CREATE SCHEMA IF NOT EXISTS ...")` as first statement
- Matching `downgrade()` with `DROP ... IF EXISTS` in reverse order (lines 143–151)

### pytest-asyncio Test Pattern
**Source:** `tests/test_client.py` lines 40–57; `tests/conftest.py` lines 33–89
**Apply to:** All `tests/selless_mcp/`, `tests/knowledge_mcp/`, `tests/ingest/`, `tests/smoke/`

Key elements:
- `@pytest.mark.asyncio` on each async test (or `asyncio_mode=auto` from pyproject.toml)
- `@pytest.mark.sandbox` for any test requiring real Voyage/Selless creds (auto-skipped in CI)
- `respx_lib.mock(base_url=...)` pattern for HTTP mocking (apply selless_respx_mock fixture)
- Function-scope fixtures to avoid event-loop-scope mismatch (conftest.py line 34 note)

### Lazy Singleton Init
**Source:** `src/guards/pii.py` lines 39–53 (Presidio engines)
**Apply to:** `src/knowledge_mcp/embeddings.py` (Voyage client), `src/selless_mcp/audit.py` (AuditMiddleware DB pool ref)

```python
# Pattern: global None → init on first call → cache
_singleton: "Type | None" = None
def _get_singleton() -> "Type":
    global _singleton
    if _singleton is None:
        _singleton = Type(...)
    return _singleton
```

---

## No Analog Found

Files with no close codebase match (planner uses RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/knowledge_mcp/conflict.py` | utility | transform | No conflict-flag or override-resolution logic exists anywhere in the codebase; greenfield per D-13/D-14 |
| `src/ingest/sources.py` | utility | file-I/O | No SVG/PDF/Markdown snapshot reader exists; reads from `.planning/phases/01-*/snapshots/` which Phase 2 never touched |
| `src/ingest/cli.py` | utility | batch | No CLI entry point exists in the repo; use `python -m src.ingest.cli re-ingest` pattern; standard `argparse`/`click` |

**For these files:** planner should use RESEARCH.md §Pattern 4 (RRF hybrid), §Code Examples (idempotent upsert, Voyage API), and the D-13/D-14 conflict posture description as the implementation reference.

---

## Metadata

**Analog search scope:** `src/freshdesk_io/`, `src/guards/`, `src/config.py`, `migrations/versions/`, `tests/`
**Files scanned:** 9 source files read directly; codebase structure verified via `ls src/` and `find tests/`
**Pattern extraction date:** 2026-06-02
**Key risk:** `src/selless_mcp/client.py` → `HttpSellessClient` endpoint paths are confirmed from `03-SELLESS-API.md` (live GET returned 200 with no auth). The `/public/tickets` prefix and specific endpoints (`/po/{id}`, `/customer/{id}`, `/po/search`) are now concrete — mock fixtures should use these exact shapes.
