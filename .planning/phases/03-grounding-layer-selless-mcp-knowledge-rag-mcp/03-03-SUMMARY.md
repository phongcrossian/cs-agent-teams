---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
plan: "03"
subsystem: selless-mcp
tags: [selless, mcp, security, whitelist, audit, rate-limit, fastmcp]
dependency_graph:
  requires: ["03-00"]
  provides: ["selless-mcp-package", "SEL-01", "SEL-02", "SEL-03", "SEL-04"]
  affects: ["03-04-demo", "04-pipeline"]
tech_stack:
  added:
    - "FastMCP 3.3.1 (on_duplicate= kwarg, no RateLimitingMiddleware built-in)"
    - "_TokenBucketRateLimiter custom Middleware (asyncio.Lock token bucket)"
    - "mcp.types.ToolAnnotations (readOnlyHint, openWorldHint)"
  patterns:
    - "SellessClient runtime_checkable Protocol + MockSellessClient fixture seam"
    - "D-04 explicit field extraction whitelist (never **raw spread)"
    - "AuditMiddleware on_call_tool wrapping + asyncpg $N parameterized insert"
    - "_impl_* pattern: tool logic separated from FastMCP decorator for direct test calls"
key_files:
  created:
    - src/selless_mcp/__init__.py
    - src/selless_mcp/errors.py
    - src/selless_mcp/models.py
    - src/selless_mcp/client.py
    - src/selless_mcp/whitelist.py
    - src/selless_mcp/audit.py
    - src/selless_mcp/server.py
    - tests/selless_mcp/test_tools.py
    - tests/selless_mcp/test_whitelist.py
    - tests/selless_mcp/test_audit.py
    - tests/selless_mcp/test_rate_limit.py
    - tests/selless_mcp/test_ticket_history.py
  modified:
    - tests/selless_mcp/test_resolve_scope.py
decisions:
  - "[03-03] FastMCP 3.3.1 uses on_duplicate= not on_duplicate_tools= — corrected at import time"
  - "[03-03] FastMCP tool functions cannot have Protocol/arbitrary types in signatures — _impl_* pattern separates tool logic from decorator, clients injected at module level"
  - "[03-03] TicketHistory.status/source accept Optional[str] — Freshdesk returns int codes, Selless returns str; apply_ticket_history_whitelist normalises via str() coercion"
  - "[03-03] FastMCP 3.x removed built-in RateLimitingMiddleware — implemented _TokenBucketRateLimiter as custom Middleware subclass (asyncio.Lock + token bucket)"
  - "[03-03] SEL-03/D-05 Option B confirmed: ticket-do mapping is join key, Freshdesk client supplies content, composed inside get_ticket_history"
metrics:
  duration: "~35 min"
  completed: "2026-06-02"
  tasks: 2
  files: 13
---

# Phase 03 Plan 03: Selless MCP Transactional Surface Summary

**One-liner:** FastMCP SellessMCP server with D-04 hard field whitelist, D-03 keyed-only access, D-08 token-bucket rate limit, D-06/D-07 PII-redacted audit, and SEL-03 prior-ticket history composed via Phase-2 Freshdesk client — all 48 tests GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Error taxonomy + whitelisted models + client seam | 4491d9c | 8 files created |
| 2 | Whitelist + audit middleware + FastMCP server | 6114f1a | 6 files updated/created |

## What Was Built

### Task 1: Error taxonomy + models + client seam

**`src/selless_mcp/errors.py`** — 3-class taxonomy mirroring `freshdesk_io/errors.py` 1:1:
- `SellessRateLimitError(retry_after)` / `SellessTransientError` / `SellessFatalError`

**`src/selless_mcp/models.py`** — D-04 whitelisted Pydantic models:
- `Address`, `ProductInfo`, `DoStatus`, `OrderDetail` (no payment/cost/supplier/handling_fee/note)
- `CustomerInfo`, `ResolvedOrder`, `PurchaseHistory`, `TicketMapping`, `TicketHistory` (no agent/agent_id)

**`src/selless_mcp/client.py`** — Client seam:
- `SellessClient` `@runtime_checkable Protocol` — D-01 isolation
- `MockSellessClient` — fixture dicts include DENY-field keys (payment, total_product_cost, supplier_name, handling_fee, note) so whitelist tests can prove stripping
- `HttpSellessClient` — httpx+tenacity, lazy init, gateway-trust (no auth header), no write method (D-08)
- `resolve_order()` — exact-key only: raises `ValueError` for < 3 chars or no exact match (D-03)

**`src/selless_mcp/whitelist.py`** — D-04 map-and-whitelist:
- `apply_order_whitelist(raw) -> OrderDetail` — explicit field extraction, strips payment/cost/supplier/handling_fee/note
- `apply_customer_whitelist(raw) -> CustomerInfo`
- `apply_ticket_history_whitelist(raw) -> TicketHistory` — strips agent/agent_id; normalises int status/source to str
- `_DENY_FIELDS` frozenset with all documented deny keys

**`src/selless_mcp/audit.py`** — SEL-04/D-06/D-07:
- `AuditMiddleware(Middleware)` — `on_call_tool` wraps every call, times it, writes row in `finally`
- `_write_audit_row(...)` — asyncpg `$N` parameterized insert, never f-string SQL (T-03-SQLI)
- `redact_text()` called on `input_key` and `fields_returned` before insert (D-06)

**`src/selless_mcp/server.py`** — FastMCP server:
- `_TokenBucketRateLimiter(Middleware)` — custom token bucket (asyncio.Lock), raises `RuntimeError` when exhausted (D-08)
- `mcp = FastMCP(name="SellessMCP", on_duplicate="error")`
- 5 read-only tools: `get_order_status`, `get_customer_info`, `get_purchase_history`, `get_ticket_history`, `resolve_order` — all `readOnlyHint=True, openWorldHint=False`
- No write tool registered (ticket-do POST never exposed, D-08)
- `_impl_*` functions for direct test access without MCP transport

### SEL-03/D-05 composition in `get_ticket_history`:
1. `fetch_ticket_mapping(order_id)` → `fd_ticket_id` (Selless ticket-do as join key)
2. `FreshdeskClient.get_ticket(fd_ticket_id)` → raw ticket dict (Phase-2 client)
3. `apply_ticket_history_whitelist(raw)` → `TicketHistory` (agent/agent_id denied)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastMCP 3.3.1 API changes from plan documentation**
- **Found during:** Task 1 server.py import
- **Issue:** `FastMCP(on_duplicate_tools=...)` kwarg removed in 3.x; must use `on_duplicate=`
- **Fix:** Changed to `FastMCP(name="SellessMCP", on_duplicate="error")`
- **Files modified:** `src/selless_mcp/server.py`
- **Commit:** 4491d9c

**2. [Rule 1 - Bug] FastMCP Protocol type in tool signature**
- **Found during:** Task 1 test collection
- **Issue:** FastMCP introspects function signatures via Pydantic; `SellessClient` Protocol causes `PydanticSchemaGenerationError` when used as tool parameter type
- **Fix:** Introduced `_impl_*` pattern — tool logic in plain async functions accepting client as parameter; MCP tools delegate to `_impl_*` using module-level singletons; tests call `_impl_*` directly
- **Files modified:** `src/selless_mcp/server.py`, test files
- **Commit:** 4491d9c

**3. [Rule 1 - Bug] FastMCP 3.x removed built-in RateLimitingMiddleware**
- **Found during:** Task 2 initial exploration (`ImportError: cannot import name 'RateLimitingMiddleware'`)
- **Issue:** Plan references `mcp.add_middleware(RateLimitingMiddleware(...))` but this class does not exist in fastmcp 3.3.1
- **Fix:** Implemented `_TokenBucketRateLimiter(Middleware)` — asyncio.Lock + token bucket refill algorithm; identical behavioral contract
- **Files modified:** `src/selless_mcp/server.py`
- **Commit:** 6114f1a

**4. [Rule 1 - Bug] TicketHistory int status/source from Freshdesk**
- **Found during:** Task 2 test_ticket_history.py execution
- **Issue:** Freshdesk returns `status` and `source` as int (Freshdesk code enum); `TicketHistory.status: Optional[str]` fails Pydantic validation
- **Fix:** `apply_ticket_history_whitelist` normalises via `str()` coercion and falls back to `created_at` when `created` key absent
- **Files modified:** `src/selless_mcp/whitelist.py`
- **Commit:** 6114f1a

## Verification

```
pytest tests/selless_mcp/ -x -q
48 passed in 1.69s
```

All acceptance criteria met:
- `test_whitelist.py` GREEN: DENY fields (payment, total_product_cost, supplier_name, handling_fee, note) absent from OrderDetail; agent/agent_id absent from TicketHistory
- `test_tools.py` GREEN: get_order_status/get_customer_info/get_purchase_history return populated whitelisted models; no write tool registered; all tools readOnlyHint=True
- `test_audit.py` GREEN: _write_audit_row inserts to audit.selless_audit; parameterized query proven by SQL injection string stored literally; audit middleware exists
- `test_rate_limit.py` GREEN: burst allowed, past-burst rejected, refill tested, RuntimeError on exhaustion, no write tool, independent of Freshdesk limiter
- `test_ticket_history.py` GREEN: TicketHistory returned, ALLOW fields present, agent/agent_id absent, uses fd_ticket_id=368108 from Selless mapping, empty TicketHistory on no-client

## Threat Coverage

All mitigations from the plan's threat model implemented:

| Threat ID | Mitigation | Verified By |
|-----------|------------|-------------|
| T-03-AC | D-03 keyed-only; resolve_order exact-match only | test_resolve_scope.py |
| T-03-ID | D-04 _DENY_FIELDS whitelist; D-06 redact_text before audit | test_whitelist.py, test_audit.py |
| T-03-TH | TicketHistory omits agent/agent_id | test_ticket_history.py |
| T-03-DoS | _TokenBucketRateLimiter at MCP boundary | test_rate_limit.py |
| T-03-WR | No write tool registered; no write method on clients | test_tools.py, test_rate_limit.py |
| T-03-SQLI | asyncpg $N parameterized insert; SQL injection string stored literally | test_audit.py |
| T-03-V5 | Pydantic tool-arg schemas; resolve_order rejects <3-char param | test_resolve_scope.py |

## Known Stubs

- `get_purchase_history` returns `PurchaseHistory(orders=[], total_count=0)` — the Selless API has no dedicated orders-by-customer endpoint in `/public/tickets`; Phase 4 may extend this with a dedicated endpoint or compose via resolve_order + fetch_order. This does not block the plan's goal (SEL-02 satisfied by get_customer_info; purchase history is a future enhancement).

## Self-Check: PASSED

Files exist:
- src/selless_mcp/__init__.py ✓
- src/selless_mcp/errors.py ✓
- src/selless_mcp/models.py ✓
- src/selless_mcp/client.py ✓
- src/selless_mcp/whitelist.py ✓
- src/selless_mcp/audit.py ✓
- src/selless_mcp/server.py ✓
- tests/selless_mcp/test_ticket_history.py ✓

Commits exist:
- 4491d9c ✓ (Task 1)
- 6114f1a ✓ (Task 2)

All 48 tests GREEN ✓
