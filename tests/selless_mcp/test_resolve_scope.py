"""D-03: resolve_order enforces exact-key constraint (no cross-customer search).

Contract: resolve_order(param) accepts only an exact order code (e.g. "25044-67") or a
verified customer email. It wraps /po/search with skip=0&take=1 and returns a single
identity match only. It NEVER returns a fuzzy/browse list. A non-matching param raises.
"""

from __future__ import annotations

import pytest

from src.selless_mcp.server import _impl_resolve_order, resolve_order
from src.selless_mcp.models import ResolvedOrder
from src.selless_mcp.client import MockSellessClient


@pytest.mark.asyncio
async def test_resolve_order_returns_single_identity(mock_selless_client):
    """D-03: resolve_order returns exactly one ResolvedOrder for a valid order code."""
    result = await _impl_resolve_order("25044-67", client=mock_selless_client)
    assert isinstance(result, ResolvedOrder)
    assert result.id == "14sv5kq2iec4to48u4nbcllai"
    assert result.code == "25044-67"
    assert result.customer_id == "cust-abc123"
    assert result.customer_email == "jane.doe@example.com"


@pytest.mark.asyncio
async def test_resolve_order_param_too_short_raises(mock_selless_client):
    """D-03: resolve_order rejects param shorter than 3 chars."""
    with pytest.raises(ValueError, match="too short"):
        await _impl_resolve_order("ab", client=mock_selless_client)


@pytest.mark.asyncio
async def test_resolve_order_no_match_raises(mock_selless_client):
    """D-03: resolve_order raises when param does not exactly match any order."""
    with pytest.raises(ValueError, match="no exact match"):
        await _impl_resolve_order("99999-XX", client=mock_selless_client)


@pytest.mark.asyncio
async def test_resolve_order_no_cross_customer_search(mock_selless_client):
    """D-03: resolve_order does not expose free-text / browse list behavior.

    The mock enforces exact match only; any non-matching input raises ValueError.
    This verifies that the tool NEVER returns a list of multiple customers.
    """
    # Only exact code or email should work — partial match should raise
    with pytest.raises(ValueError):
        await _impl_resolve_order("jane", client=mock_selless_client)


def test_resolved_order_model_has_no_browse_list_field():
    """D-03 source assertion: ResolvedOrder is a single-identity model (no list field)."""
    fields = ResolvedOrder.model_fields
    # Must have single-identity fields
    assert "id" in fields
    assert "code" in fields
    assert "customer_id" in fields
    assert "customer_email" in fields
    # Must NOT have a list/results field (would indicate browse behavior)
    assert "results" not in fields
    assert "items" not in fields
    assert "orders" not in fields


def test_selless_client_is_runtime_checkable_protocol():
    """SellessClient is a runtime_checkable Protocol; MockSellessClient satisfies it."""
    from src.selless_mcp.client import SellessClient, MockSellessClient
    mock = MockSellessClient()
    assert isinstance(mock, SellessClient)


def test_no_write_method_on_clients():
    """D-08: no write method exists on MockSellessClient or HttpSellessClient."""
    from src.selless_mcp.client import MockSellessClient, HttpSellessClient
    for cls in (MockSellessClient, HttpSellessClient):
        assert not hasattr(cls, "create_ticket_mapping"), (
            f"{cls.__name__} must not have write method create_ticket_mapping (D-08)"
        )
        assert not hasattr(cls, "post_ticket_do"), (
            f"{cls.__name__} must not have write method post_ticket_do (D-08)"
        )
        assert not hasattr(cls, "write_ticket_mapping"), (
            f"{cls.__name__} must not have write method write_ticket_mapping (D-08)"
        )


def test_order_detail_model_no_deny_fields():
    """D-04 source assertion: OrderDetail has no payment, total_product_cost, supplier_name, handling_fee field."""
    from src.selless_mcp.models import OrderDetail
    fields = OrderDetail.model_fields
    assert "payment" not in fields
    assert "total_product_cost" not in fields
    assert "supplier_name" not in fields
    assert "handling_fee" not in fields
    assert "note" not in fields


def test_customer_info_model_no_deny_fields():
    """D-04 source assertion: CustomerInfo has no payment, handling_fee, supplier_name field."""
    from src.selless_mcp.models import CustomerInfo
    fields = CustomerInfo.model_fields
    assert "payment" not in fields
    assert "handling_fee" not in fields
    assert "supplier_name" not in fields
