"""D-04: field whitelist hard-denies payment/cost/other internal fields.

Contract: apply_order_whitelist(raw_dict) maps PoViewModel raw dict to OrderDetail,
silently dropping all non-allow-listed fields. If a hard-DENY field is present in
raw (e.g. "payment", "total_product_cost", "handling_fee"), the whitelist must not
expose it in the returned model. DENY fields must not appear as attributes on result.
"""

from __future__ import annotations

import pytest

from src.selless_mcp.whitelist import (
    apply_order_whitelist,
    apply_customer_whitelist,
    apply_ticket_history_whitelist,
    _DENY_FIELDS,
)
from src.selless_mcp.client import FIXTURE_ORDER, FIXTURE_CUSTOMER
from src.selless_mcp.models import OrderDetail, CustomerInfo, TicketHistory


# ---------------------------------------------------------------------------
# D-04: order whitelist strips DENY fields
# ---------------------------------------------------------------------------

def test_whitelist_drops_payment_field():
    """D-04: payment field from raw PoViewModel must not appear in OrderDetail."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert isinstance(result, OrderDetail)
    assert not hasattr(result, "payment"), "payment must be DENY-listed from OrderDetail"
    # Confirm the raw fixture actually contains the deny field
    assert "payment" in FIXTURE_ORDER, "Fixture must include payment to prove it is stripped"


def test_whitelist_drops_total_product_cost():
    """D-04: total_product_cost (internal margin) must be hard-denied."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert not hasattr(result, "total_product_cost")
    assert "total_product_cost" in FIXTURE_ORDER, "Fixture must include total_product_cost"


def test_whitelist_drops_handling_fee():
    """D-04: handling_fee must be hard-denied (financial sensitivity)."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert not hasattr(result, "handling_fee")
    assert "handling_fee" in FIXTURE_ORDER, "Fixture must include handling_fee"


def test_whitelist_drops_note():
    """D-04: note (internal ops memo) must be hard-denied from OrderDetail."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert not hasattr(result, "note")
    assert "note" in FIXTURE_ORDER, "Fixture must include note to prove it is stripped"


def test_whitelist_preserves_allowed_fields():
    """D-04: status, code, created, amount, shipping_address are ALLOW-listed."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert result.status == "ACTIVE"
    assert result.code == "25044-67"
    assert result.id == "14sv5kq2iec4to48u4nbcllai"
    assert result.created == "2026-05-01T08:00:00Z"
    assert result.amount == 99.99
    assert result.shipping_address is not None
    assert result.shipping_address.email == "jane.doe@example.com"


def test_whitelist_preserves_product_fields():
    """D-04: product.{id,name,code,line,family} are ALLOW-listed inside OrderDetail."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert result.product is not None
    assert result.product.id == "prod-001"
    assert result.product.name == "Premium Widget"
    assert result.product.code == "PWG-001"
    assert result.product.line == "Widgets"
    assert result.product.family == "Premium"


def test_whitelist_strips_do_supplier_fields():
    """D-04: DoStatus inside delivery_orders must not expose supplier_id/code/name."""
    result = apply_order_whitelist(FIXTURE_ORDER)
    assert len(result.delivery_orders) == 1
    do = result.delivery_orders[0]
    assert not hasattr(do, "supplier_id")
    assert not hasattr(do, "supplier_code")
    assert not hasattr(do, "supplier_name")
    assert not hasattr(do, "contract_id")
    assert not hasattr(do, "is_fake_contract")
    assert not hasattr(do, "fulfillment_version_id")
    assert not hasattr(do, "fulfillment_version_name")
    # ALLOW: tracking and status
    assert do.trackings == ["1Z999AA10123456784"]
    assert do.status == "DELIVERED"


# ---------------------------------------------------------------------------
# D-04: customer whitelist
# ---------------------------------------------------------------------------

def test_customer_whitelist_preserves_allowed_fields():
    """D-04: CustomerInfo gets id, name, email, phone, statuses."""
    result = apply_customer_whitelist(FIXTURE_CUSTOMER)
    assert isinstance(result, CustomerInfo)
    assert result.id == "cust-abc123"
    assert result.email == "jane.doe@example.com"
    assert result.phone == "+1-555-0100"
    assert result.email_status == "verified"


# ---------------------------------------------------------------------------
# D-04: ticket history whitelist (SEL-03 / D-05)
# ---------------------------------------------------------------------------

FIXTURE_TICKET_WITH_DENY = {
    "rootcause": "Item arrived damaged",
    "customer_feedback": "Very unhappy",
    "customer_request": "Full refund",
    "status": "resolved",
    "source": "email",
    "created": "2026-04-15T10:00:00Z",
    # DENY fields — must be stripped
    "agent": "John Agent",
    "agent_id": "agent-001",
    "level_in": "L1",
    "level_out": "L2",
    "id": "ticket-internal-001",
    "fd_ticket_id": 368108,
    "updated": "2026-04-16T12:00:00Z",
}


def test_ticket_history_whitelist_allow_fields():
    """D-04/D-05: TicketHistory gets rootcause, customer_feedback, customer_request, status, source, created."""
    result = apply_ticket_history_whitelist(FIXTURE_TICKET_WITH_DENY)
    assert isinstance(result, TicketHistory)
    assert result.rootcause == "Item arrived damaged"
    assert result.customer_feedback == "Very unhappy"
    assert result.customer_request == "Full refund"
    assert result.status == "resolved"
    assert result.source == "email"
    assert result.created == "2026-04-15T10:00:00Z"


def test_ticket_history_whitelist_denies_agent():
    """D-04/D-05: agent and agent_id must be DENIED from TicketHistory."""
    result = apply_ticket_history_whitelist(FIXTURE_TICKET_WITH_DENY)
    assert not hasattr(result, "agent"), "agent must be denied (internal CS field)"
    assert not hasattr(result, "agent_id"), "agent_id must be denied (internal CS field)"


def test_ticket_history_model_no_agent_field():
    """D-04 source assertion: TicketHistory model has no agent or agent_id field."""
    fields = TicketHistory.model_fields
    assert "agent" not in fields
    assert "agent_id" not in fields


# ---------------------------------------------------------------------------
# D-04: deny-list completeness check
# ---------------------------------------------------------------------------

def test_deny_list_contains_critical_fields():
    """D-04: _DENY_FIELDS must contain all documented critical deny entries."""
    assert "payment" in _DENY_FIELDS
    assert "total_product_cost" in _DENY_FIELDS
    assert "supplier_id" in _DENY_FIELDS
    assert "supplier_name" in _DENY_FIELDS
    assert "handling_fee" in _DENY_FIELDS
    assert "note" in _DENY_FIELDS
    assert "agent" in _DENY_FIELDS
    assert "agent_id" in _DENY_FIELDS
    assert "payload" in _DENY_FIELDS


def test_order_detail_model_fields_no_deny_keys():
    """D-04: OrderDetail Pydantic model has NO field for any DENY-listed key."""
    for deny_key in _DENY_FIELDS:
        assert deny_key not in OrderDetail.model_fields, (
            f"OrderDetail must not have field '{deny_key}' (DENY-listed D-04)"
        )
