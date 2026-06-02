"""
SellessClient — seam isolating the Selless API from MCP tools.

Architecture boundary: use MockSellessClient for tests, HttpSellessClient for prod.
Base URL: https://api.selless.dev/admin/csm/order/public/tickets
(confirmed 2026-06-02, gateway-trust auth model — no token needed).

D-03: resolve_order is the ONLY search entry point; it enforces exact-key single-identity
only and NEVER returns a fuzzy/browse list.
D-08: NO write method exists on any client class (ticket-do POST never exposed).
"""

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
    SellessFatalError,
    SellessRateLimitError,
    SellessTransientError,
)
from src.freshdesk_io.rate_limit import classify_status, parse_retry_after

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tenacity wait strategy (mirror _freshdesk_wait from freshdesk_io/client.py)
# ---------------------------------------------------------------------------

def _selless_wait(retry_state: RetryCallState) -> float:
    """Honor Retry-After on rate-limit, else exp+jitter."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, SellessRateLimitError):
        return float(exc.retry_after)
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    return base + random.uniform(-1.0, 1.0)


# ---------------------------------------------------------------------------
# Response → error classification (reuses rate_limit helpers)
# ---------------------------------------------------------------------------

def _raise_for_selless_status(response: httpx.Response) -> None:
    """Raise appropriate exception based on HTTP status.

    Reuses classify_status / parse_retry_after from freshdesk_io.rate_limit
    (do NOT duplicate).
    """
    status = response.status_code
    if status == 429:
        retry_after = parse_retry_after(dict(response.headers))
        logger.warning("selless_rate_limited", extra={"retry_after": retry_after})
        raise SellessRateLimitError(retry_after=retry_after)

    classification = classify_status(status)
    if classification == "fatal":
        logger.error("selless_fatal_error", extra={"status": status})
        raise SellessFatalError(f"HTTP {status}: fatal — no retry")

    if classification == "transient":
        logger.warning("selless_transient_error", extra={"status": status})
        raise SellessTransientError(f"HTTP {status}: transient — will retry")


# ---------------------------------------------------------------------------
# Protocol (runtime-checkable client seam — D-01)
# ---------------------------------------------------------------------------

@runtime_checkable
class SellessClient(Protocol):
    """Seam isolating the Selless API from MCP tools.

    MockSellessClient satisfies this for tests;
    HttpSellessClient satisfies it for production.

    D-08: NO write method exists. ticket-do POST is never exposed.
    """

    async def fetch_order(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_customer(self, customer_id: str) -> dict[str, Any]: ...
    async def resolve_order(self, param: str) -> dict[str, Any]: ...
    async def fetch_dispute(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_refunds(self, order_id: str) -> dict[str, Any]: ...
    async def fetch_ticket_mapping(self, fd_ticket_id: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Fixture data (derived from 03-SELLESS-API.md live JSON shapes)
# Includes DENY-listed keys so whitelist tests can prove stripping works.
# ---------------------------------------------------------------------------

FIXTURE_ORDER: dict[str, Any] = {
    # ALLOW fields
    "id": "14sv5kq2iec4to48u4nbcllai",
    "code": "25044-67",
    "status": "ACTIVE",
    "created": "2026-05-01T08:00:00Z",
    "amount": 99.99,
    "items_amount": 89.99,
    "tax_amount": 7.00,
    "discount": 5.00,
    "shipping": 8.00,
    "closed_reason": None,
    "shipping_address": {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone": "+1-555-0100",
        "address1": "123 Main St",
        "address2": None,
        "city": "Springfield",
        "state": "IL",
        "country": "US",
        "postal_code": "62701",
    },
    "billing_address": {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone": "+1-555-0100",
        "address1": "123 Main St",
        "address2": None,
        "city": "Springfield",
        "state": "IL",
        "country": "US",
        "postal_code": "62701",
    },
    "product": {
        "id": "prod-001",
        "name": "Premium Widget",
        "code": "PWG-001",
        "line": "Widgets",
        "family": "Premium",
    },
    "delivery_orders": [
        {
            "id": "do-abc123",
            "code": "DO-25044-67-1",
            "status": "DELIVERED",
            "odo_status": "DELIVERED",
            "status_date_processing": "2026-05-02T10:00:00Z",
            "status_date_delivered": "2026-05-05T14:00:00Z",
            "trackings": ["1Z999AA10123456784"],
            "failed_reason": None,
            "product_label": None,
            "urgent": False,
            # DENY fields — whitelist must strip these
            "supplier_id": "sup-secret-001",
            "supplier_code": "SUP001",
            "supplier_name": "Secret Supplier Co",
            "contract_id": "contract-xyz",
            "is_fake_contract": False,
            "fulfillment_version_id": "fv-001",
            "fulfillment_version_name": "v2.3",
        }
    ],
    # DENY fields at order level — whitelist must strip all of these
    "payment": {
        "transaction_id": "txn-secret-001",
        "gateway_id": "gw-001",
        "provider": "stripe",
        "card_first4": "4111",
        "card_last4": "1111",
        "card_brand": "visa",
        "merchant_name": "Acme Corp",
        "merchant_email": "billing@acme.com",
        "paid": True,
    },
    "total_product_cost": 55.00,
    "handling_fee": 3.50,
    "note": "Internal ops memo — never expose",
}

FIXTURE_CUSTOMER: dict[str, Any] = {
    # ALLOW fields
    "id": "cust-abc123",
    "first_name": "Jane",
    "last_name": "Doe",
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+1-555-0100",
    "email_status": "verified",
    "phone_status": "verified",
    # No DENY fields on CustomerViewModel (clean shape)
}

FIXTURE_RESOLVED_ORDER: dict[str, Any] = {
    "id": "14sv5kq2iec4to48u4nbcllai",
    "code": "25044-67",
    "customer_id": "cust-abc123",
    "customer_email": "jane.doe@example.com",
}

FIXTURE_DISPUTE: dict[str, Any] = {
    "id": "disp-001",
    "status": "OPEN",
    "reason": "Item not received",
    # DENY field — whitelist must strip
    "payload": {"internal_notes": "secret data"},
}

FIXTURE_REFUNDS: list[dict[str, Any]] = [
    {
        "amount": 99.99,
        "include_refund_guarantee": True,
    }
]

FIXTURE_TICKET_MAPPING: dict[str, Any] = {
    "fd_ticket_id": 368108,
    "do_ids": ["do-abc123"],
}


# ---------------------------------------------------------------------------
# MockSellessClient (test double — no HTTP calls)
# ---------------------------------------------------------------------------

class MockSellessClient:
    """Test double — returns fixture dicts. No HTTP calls (D-01 seam).

    Satisfies SellessClient Protocol.  All fixture dicts include DENY-listed keys
    so that whitelist tests can prove those keys are stripped.
    D-08: no write method exists.
    """

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        return dict(FIXTURE_ORDER)

    async def fetch_customer(self, customer_id: str) -> dict[str, Any]:
        return dict(FIXTURE_CUSTOMER)

    async def resolve_order(self, param: str) -> dict[str, Any]:
        """D-03: exact-key only. Raises ValueError for < 3 chars or no match."""
        if len(param) < 3:
            raise ValueError(
                f"resolve_order param too short ({len(param)} chars < 3) — "
                "exact order code or email required (D-03)"
            )
        # Exact match: fixture code or email only
        if param not in (FIXTURE_RESOLVED_ORDER["code"], FIXTURE_RESOLVED_ORDER["customer_email"]):
            raise ValueError(
                f"resolve_order: no exact match for {param!r} — "
                "MCP enforces keyed-only access (D-03)"
            )
        return dict(FIXTURE_RESOLVED_ORDER)

    async def fetch_dispute(self, order_id: str) -> dict[str, Any]:
        return dict(FIXTURE_DISPUTE)

    async def fetch_refunds(self, order_id: str) -> dict[str, Any]:
        return list(FIXTURE_REFUNDS)

    async def fetch_ticket_mapping(self, fd_ticket_id: str) -> dict[str, Any]:
        return dict(FIXTURE_TICKET_MAPPING)


# ---------------------------------------------------------------------------
# HttpSellessClient (production — httpx + tenacity, mirror FreshdeskClient)
# ---------------------------------------------------------------------------

class HttpSellessClient:
    """Production Selless API client: httpx + tenacity retry/backoff.

    Mirrors FreshdeskClient.__init__ / _client() / _make_retry_decorator() exactly.
    Gateway-trust auth: no auth header by default; selless_api_gateway_key config hook
    reserved for prod VPN/gateway if needed.
    D-08: NO write method. ticket-do POST is never called.
    """

    def __init__(
        self,
        base_url: str,
        max_attempts: int = 5,
        gateway_key: str = "",
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._max_attempts = max_attempts
        self._gateway_key = gateway_key
        # Allow injection for testing; built lazily on first call otherwise
        self._http_client = _http_client

    def _client(self) -> httpx.AsyncClient:
        """Lazy-build httpx.AsyncClient (mirror FreshdeskClient._client)."""
        if self._http_client is None:
            headers: dict[str, str] = {}
            if self._gateway_key:
                headers["X-Gateway-Key"] = self._gateway_key
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._http_client

    def _make_retry_decorator(self):
        """Build tenacity retry decorator (mirror FreshdeskClient._make_retry_decorator)."""
        return retry(
            stop=stop_after_attempt(self._max_attempts),
            wait=_selless_wait,
            retry=retry_if_exception_type(
                (SellessRateLimitError, SellessTransientError, httpx.TransportError)
            ),
            reraise=True,
        )

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        """GET /po/{id} — internal order id (not human code)."""
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/po/{order_id}")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()

        return await _call()

    async def fetch_customer(self, customer_id: str) -> dict[str, Any]:
        """GET /customer/{id}."""
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/customer/{customer_id}")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()

        return await _call()

    async def resolve_order(self, param: str) -> dict[str, Any]:
        """D-03: constrained exact-key search. GET /po/search?param=&skip=0&take=1.

        Accepts an exact order code (e.g. "25044-67") OR verified customer email.
        NEVER returns a fuzzy/browse list — only exact single-identity match.
        Raises ValueError if param < 3 chars or no exact match found.
        """
        if len(param) < 3:
            raise ValueError(
                f"resolve_order param too short ({len(param)} chars < 3) — "
                "exact order code or email required (D-03)"
            )

        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(
                "/po/search",
                params={"param": param, "skip": 0, "take": 1},
            )
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            data = resp.json()
            # Expect a list with exactly one result (exact-key constraint D-03)
            items = data if isinstance(data, list) else data.get("items", [])
            if not items:
                raise ValueError(
                    f"resolve_order: no exact match for {param!r} — "
                    "MCP enforces keyed-only access (D-03)"
                )
            # Return only the first (and only) result; caller gets ResolvedOrder
            item = items[0]
            return {
                "id": item["id"],
                "code": item["code"],
                "customer_id": item.get("customer_id", ""),
                "customer_email": item.get("customer_email", ""),
            }

        return await _call()

    async def fetch_dispute(self, order_id: str) -> dict[str, Any]:
        """GET /po/{id}/dispute."""
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/po/{order_id}/dispute")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()

        return await _call()

    async def fetch_refunds(self, order_id: str) -> dict[str, Any]:
        """GET /po/{id}/refunds."""
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/po/{order_id}/refunds")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()

        return await _call()

    async def fetch_ticket_mapping(self, fd_ticket_id: str) -> dict[str, Any]:
        """GET /{fd_ticket_id}/ticket-do — returns {fd_ticket_id, do_ids[]}.

        This is the JOIN KEY for SEL-03 (D-05): maps Freshdesk ticket → DO ids.
        Ticket CONTENT is fetched from Freshdesk, not Selless.
        D-08: the POST /{id}/ticket-do write endpoint is NEVER called here.
        """
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/{fd_ticket_id}/ticket-do")
            if resp.status_code != 200:
                _raise_for_selless_status(resp)
            return resp.json()

        return await _call()
