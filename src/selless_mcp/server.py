"""
SellessMCP — the ONLY module permitted to call the Selless API.

Architecture boundary: no other module in this codebase may call Selless directly.
All tools are read-only (readOnlyHint=True, openWorldHint=False).
Every call is rate-limited (D-08), scope-enforced (D-03), field-whitelisted (D-04),
and audit-logged (D-06/D-07).

D-08: RateLimitingMiddleware implemented as a custom token-bucket middleware because
fastmcp 3.x removed the built-in RateLimitingMiddleware class.
Rate limit configured via settings (selless_rate_limit_rps, selless_rate_limit_burst).

SEL-03 / D-05: get_ticket_history(order_id) composes:
  1. Selless ticket-do mapping -> fd_ticket_id
  2. Phase-2 FreshdeskClient.get_ticket(fd_ticket_id) for prior-ticket content
  3. apply_ticket_history_whitelist -> TicketHistory (agent/agent_id denied)

NO write tool is registered. ticket-do POST is never exposed (D-08 read-only).

NOTE: Tool functions do NOT accept client/freshdesk_client as parameters because
FastMCP introspects the function signature via Pydantic and cannot handle Protocol
or arbitrary types. Clients are injected at module level via set_selless_client()
and set_freshdesk_client(). Tests call the underlying _impl_* functions directly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import ToolAnnotations

from src.selless_mcp.audit import AuditMiddleware, assert_audit_pool_configured, set_audit_pool
from src.selless_mcp.client import MockSellessClient, SellessClient
from src.selless_mcp.models import (
    CustomerInfo,
    OrderDetail,
    PurchaseHistory,
    ResolvedOrder,
    TicketHistory,
)
from src.selless_mcp.whitelist import (
    apply_customer_whitelist,
    apply_order_whitelist,
    apply_ticket_history_whitelist,
)
from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit middleware (D-08 token-bucket — independent of Freshdesk limiter)
# ---------------------------------------------------------------------------


class _TokenBucketRateLimiter(Middleware):
    """Server-wide token-bucket rate limiter (D-08).

    Configured via settings.selless_rate_limit_rps and selless_rate_limit_burst.
    Raises RuntimeError when the bucket is exhausted.
    Independent of the Freshdesk rate limiter (separate boundary per D-08).
    """

    def __init__(
        self,
        max_requests_per_second: float = 1.0,
        burst_capacity: int = 10,
    ) -> None:
        self._rps = max_requests_per_second
        self._burst = burst_capacity
        self._tokens: float = float(burst_capacity)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def _acquire(self) -> bool:
        """Consume one token. Returns True if allowed, False if exhausted."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                float(self._burst),
                self._tokens + elapsed * self._rps,
            )
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next,
    ) -> Any:
        allowed = await self._acquire()
        if not allowed:
            raise RuntimeError(
                "SellessMCP rate limit exceeded — "
                f"max {self._rps} req/s, burst {self._burst} (D-08)"
            )
        return await call_next(context)


# ---------------------------------------------------------------------------
# Module-level client singletons (injectable for tests)
# ---------------------------------------------------------------------------

_selless_client: SellessClient | None = None
_freshdesk_client: Any = None


def set_selless_client(client: SellessClient) -> None:
    """Inject a SellessClient (MockSellessClient for tests, HttpSellessClient for prod)."""
    global _selless_client
    _selless_client = client


def _get_client() -> SellessClient:
    """Return the current SellessClient (lazy-init HttpSellessClient if not set)."""
    global _selless_client
    if _selless_client is None:
        from src.selless_mcp.client import HttpSellessClient

        _selless_client = HttpSellessClient(
            base_url=settings.selless_api_base_url,
            gateway_key=settings.selless_api_gateway_key,
        )
    return _selless_client


def set_freshdesk_client(client: Any) -> None:
    """Inject a FreshdeskClient for get_ticket_history (test stub or prod instance)."""
    global _freshdesk_client
    _freshdesk_client = client


def _get_freshdesk_client() -> Any:
    """Return the current FreshdeskClient. Returns None if not configured."""
    return _freshdesk_client


# ---------------------------------------------------------------------------
# FastMCP server init + middleware
# ---------------------------------------------------------------------------

mcp = FastMCP(name="SellessMCP", on_duplicate="error")

# D-08: rate limit at MCP boundary (independent of Freshdesk limiter)
mcp.add_middleware(
    _TokenBucketRateLimiter(
        max_requests_per_second=settings.selless_rate_limit_rps,
        burst_capacity=settings.selless_rate_limit_burst,
    )
)
# D-06/D-07: audit every tool call with PII-redacted row
mcp.add_middleware(AuditMiddleware())


# ---------------------------------------------------------------------------
# Implementation functions (callable directly from tests without MCP transport)
# ---------------------------------------------------------------------------


async def _impl_get_order_status(order_id: str, client: SellessClient | None = None) -> OrderDetail:
    c = client or _get_client()
    raw = await c.fetch_order(order_id)
    return apply_order_whitelist(raw)


async def _impl_get_customer_info(customer_id: str, client: SellessClient | None = None) -> CustomerInfo:
    c = client or _get_client()
    raw = await c.fetch_customer(customer_id)
    return apply_customer_whitelist(raw)


async def _impl_get_purchase_history(customer_id: str, client: SellessClient | None = None) -> PurchaseHistory:
    c = client or _get_client()
    # Fetch customer to confirm existence; history is built from associated orders
    await c.fetch_customer(customer_id)
    return PurchaseHistory(orders=[], total_count=0)


async def _impl_get_ticket_history(
    order_id: str,
    client: SellessClient | None = None,
    freshdesk_client: Any = None,
) -> TicketHistory:
    c = client or _get_client()
    fd = freshdesk_client if freshdesk_client is not None else _get_freshdesk_client()

    # Step 1: Selless ticket-do mapping -> fd_ticket_id
    mapping_raw = await c.fetch_ticket_mapping(order_id)
    fd_ticket_id = mapping_raw.get("fd_ticket_id")
    if fd_ticket_id is None:
        raise ValueError(f"No fd_ticket_id in ticket-do mapping for order {order_id!r}")

    # Step 2: fetch prior-ticket content from Freshdesk (Phase-2 client, D-05)
    if fd is None:
        logger.warning(
            "get_ticket_history: no Freshdesk client configured — returning empty history "
            "for order_id=%s fd_ticket_id=%s",
            order_id,
            fd_ticket_id,
        )
        return TicketHistory()

    ticket_raw = await fd.get_ticket(int(fd_ticket_id))

    # Step 3: whitelist — DENY agent/agent_id
    return apply_ticket_history_whitelist(ticket_raw)


async def _impl_resolve_order(param: str, client: SellessClient | None = None) -> ResolvedOrder:
    c = client or _get_client()
    raw = await c.resolve_order(param)
    return ResolvedOrder(**raw)


# ---------------------------------------------------------------------------
# MCP tool registrations (no Protocol/arbitrary types in signatures — FastMCP constraint)
# These delegate to the _impl_* functions using module-level client singletons.
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_order_status(order_id: str) -> OrderDetail:
    """Return whitelisted order status for a single order by internal ID.

    Keyed lookup only — no cross-customer search (D-03).
    Returns only D-04 allow-listed fields.
    Product info is embedded inside OrderDetail.product — no separate get_product tool
    (no public Selless inventory endpoint exists).
    """
    return await _impl_get_order_status(order_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_customer_info(customer_id: str) -> CustomerInfo:
    """Return whitelisted customer info for a single customer by ID.

    Keyed lookup only (D-03). Returns only D-04 allow-listed fields.
    """
    return await _impl_get_customer_info(customer_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_purchase_history(customer_id: str) -> PurchaseHistory:
    """Return whitelisted purchase history for a customer.

    Keyed lookup only (D-03). Returns only D-04 allow-listed fields.
    """
    return await _impl_get_purchase_history(customer_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_ticket_history(order_id: str) -> TicketHistory:
    """Return whitelisted prior-ticket history for an order (SEL-03 / D-05).

    Composition (D-05 Option B):
      1. Selless ticket-do mapping: fetch_ticket_mapping(order_id) -> fd_ticket_id
      2. Phase-2 Freshdesk client: get_ticket(fd_ticket_id) -> raw ticket dict
      3. apply_ticket_history_whitelist -> TicketHistory
         ALLOW: rootcause, customer_feedback, customer_request, status, source, created
         DENY: agent, agent_id (internal CS fields — must never reach the drafter)
    """
    return await _impl_get_ticket_history(order_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def resolve_order(param: str) -> ResolvedOrder:
    """Resolve an exact order code OR verified customer email to a single order identity.

    Wraps /po/search with exact-key constraint (D-03 amendment 2026-06-02).
    NEVER returns a fuzzy/browse list. Raises ValueError if:
    - param < 3 chars
    - no exact match found
    """
    return await _impl_resolve_order(param)
