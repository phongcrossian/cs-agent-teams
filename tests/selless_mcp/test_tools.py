"""SEL-01/02/03: keyed MCP tools return whitelisted fields (mock-backed).

Contract: get_order_status(order_id), get_customer_info(customer_id),
get_purchase_history(customer_id) all:
- Return only D-04 allow-listed fields (no payment/cost/supplier)
- Accept keyed lookup only (order_id or verified customer email / id)
- Work against MockSellessClient in tests (no live HTTP)
"""

from __future__ import annotations

import pytest

from src.selless_mcp.server import (
    _impl_get_order_status,
    _impl_get_customer_info,
    _impl_get_purchase_history,
)
from src.selless_mcp.models import OrderDetail, CustomerInfo, PurchaseHistory


@pytest.mark.asyncio
async def test_get_order_status_returns_order_detail(mock_selless_client):
    """SEL-01: get_order_status returns an OrderDetail with whitelisted fields."""
    result = await _impl_get_order_status("14sv5kq2iec4to48u4nbcllai", client=mock_selless_client)
    assert isinstance(result, OrderDetail)
    assert result.status == "ACTIVE"
    assert result.code == "25044-67"


@pytest.mark.asyncio
async def test_get_order_status_no_payment_field(mock_selless_client):
    """D-04: get_order_status result must not expose payment field."""
    result = await _impl_get_order_status("14sv5kq2iec4to48u4nbcllai", client=mock_selless_client)
    assert not hasattr(result, "payment")
    assert not hasattr(result, "total_product_cost")
    assert not hasattr(result, "handling_fee")
    assert not hasattr(result, "note")


@pytest.mark.asyncio
async def test_get_order_status_has_product(mock_selless_client):
    """SEL-01: get_order_status includes product info (id, name, code, line, family)."""
    result = await _impl_get_order_status("14sv5kq2iec4to48u4nbcllai", client=mock_selless_client)
    assert result.product is not None
    assert result.product.id == "prod-001"
    assert result.product.name == "Premium Widget"


@pytest.mark.asyncio
async def test_get_customer_info_returns_customer_info(mock_selless_client):
    """SEL-02: get_customer_info returns CustomerInfo with whitelisted fields."""
    result = await _impl_get_customer_info("cust-abc123", client=mock_selless_client)
    assert isinstance(result, CustomerInfo)
    assert result.id == "cust-abc123"
    assert result.email == "jane.doe@example.com"
    assert result.phone == "+1-555-0100"


@pytest.mark.asyncio
async def test_get_customer_info_no_deny_fields(mock_selless_client):
    """D-04: get_customer_info result must not expose any DENY-listed fields."""
    result = await _impl_get_customer_info("cust-abc123", client=mock_selless_client)
    assert not hasattr(result, "payment")
    assert not hasattr(result, "handling_fee")
    assert not hasattr(result, "supplier_name")


@pytest.mark.asyncio
async def test_get_purchase_history_returns_history(mock_selless_client):
    """SEL-02: get_purchase_history returns PurchaseHistory (keyed by customer_id)."""
    result = await _impl_get_purchase_history("cust-abc123", client=mock_selless_client)
    assert isinstance(result, PurchaseHistory)


def test_mcp_server_has_no_write_tool():
    """D-08: the MCP server must NOT register any write/mutation tool."""
    from src.selless_mcp.server import mcp
    # list_tools() is synchronous in FastMCP 3.x for locally-registered tools
    import asyncio

    async def _get_tools():
        return await mcp.list_tools()

    tools = asyncio.run(_get_tools())
    tool_names = [t.name for t in tools]

    # Must not contain any write tool
    for name in tool_names:
        assert "create" not in name.lower(), f"Write tool found: {name}"
        assert "post" not in name.lower(), f"Write tool found: {name}"
        assert "write" not in name.lower(), f"Write tool found: {name}"
        assert "ticket_do" not in name.lower(), f"Write tool found: {name}"

    # Must contain the expected read-only tools
    assert "get_order_status" in tool_names
    assert "get_customer_info" in tool_names
    assert "get_purchase_history" in tool_names
    assert "get_ticket_history" in tool_names
    assert "resolve_order" in tool_names


def test_all_tools_readonly_hint():
    """D-08: all registered MCP tools must have readOnlyHint=True."""
    from src.selless_mcp.server import mcp
    import asyncio

    async def _get_tools():
        return await mcp.list_tools()

    tools = asyncio.run(_get_tools())
    for tool in tools:
        annotations = tool.annotations
        if annotations is not None:
            assert annotations.readOnlyHint is True, (
                f"Tool {tool.name!r} must have readOnlyHint=True (D-08)"
            )
