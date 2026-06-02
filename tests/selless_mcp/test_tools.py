"""RED stub — SEL-01/02/03: keyed MCP tools return whitelisted fields (mock-backed).

Contract: get_order_status(order_id), get_customer_info(customer_id),
get_purchase_history(customer_id), get_ticket_mapping(fd_ticket_id) all:
- Return only D-04 allow-listed fields (no payment/cost/supplier)
- Accept keyed lookup only (order_id or verified customer email / id)
- Work against MockSellessClient in tests (no live HTTP)
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 03 creates src/selless_mcp/server.py
from src.selless_mcp.server import get_order_status  # noqa: F401
from src.selless_mcp.models import OrderDetail  # noqa: F401


@pytest.mark.asyncio
async def test_get_order_status_returns_order_detail(mock_selless_client):
    """SEL-01: get_order_status returns an OrderDetail with whitelisted fields."""
    raise NotImplementedError("RED stub — implement in Plan 03 (SEL-01)")


@pytest.mark.asyncio
async def test_get_customer_info_returns_customer(mock_selless_client):
    """SEL-02: get_customer_info returns CustomerInfo with whitelisted fields."""
    raise NotImplementedError("RED stub — implement in Plan 03 (SEL-02)")


@pytest.mark.asyncio
async def test_get_ticket_mapping_returns_mapping(mock_selless_client):
    """SEL-03: get_ticket_mapping returns ticket-to-order mapping via Selless."""
    raise NotImplementedError("RED stub — implement in Plan 03 (SEL-03)")
