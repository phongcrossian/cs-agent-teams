"""
D-04 field whitelist — the ONLY place that maps raw Selless API dicts to safe
Pydantic models. Never call with pass-through (**raw spread); always map-and-whitelist.

DENY list (hard — these fields must NEVER appear in any returned model):
  payment, total_product_cost, supplier_id, supplier_code, supplier_name,
  contract_id, is_fake_contract, fulfillment_version_id, fulfillment_version_name,
  handling_fee, note, payload, agent, agent_id.

See 03-SELLESS-API.md §4 for the full allow / deny list.
"""

from __future__ import annotations

from typing import Any

from src.selless_mcp.models import (
    Address,
    CustomerInfo,
    DoStatus,
    OrderDetail,
    ProductInfo,
    TicketHistory,
)

# ---------------------------------------------------------------------------
# Hard deny-list (D-04)
# Any key in this set must NEVER appear in a returned model.
# The whitelist functions below never reference these keys.
# ---------------------------------------------------------------------------

_DENY_FIELDS = frozenset(
    {
        "payment",
        "total_product_cost",
        "supplier_id",
        "supplier_code",
        "supplier_name",
        "contract_id",
        "is_fake_contract",
        "fulfillment_version_id",
        "fulfillment_version_name",
        "handling_fee",
        "note",
        "payload",
        "agent",
        "agent_id",
    }
)


# ---------------------------------------------------------------------------
# Address helper
# ---------------------------------------------------------------------------


def _map_address(raw: dict[str, Any] | None) -> Address | None:
    """Map raw address dict to Address model. Returns None if input is None."""
    if raw is None:
        return None
    return Address(
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        email=raw.get("email", ""),
        phone=raw.get("phone", ""),
        address1=raw.get("address1", ""),
        address2=raw.get("address2"),
        city=raw.get("city", ""),
        state=raw.get("state", ""),
        country=raw.get("country", ""),
        postal_code=raw.get("postal_code", ""),
    )


# ---------------------------------------------------------------------------
# DoStatus helper — strips supplier/contract/fulfillment fields
# ---------------------------------------------------------------------------


def _map_do_status(raw: dict[str, Any]) -> DoStatus:
    """Map raw DoViewModel dict → DoStatus (DENY fields silently dropped).

    Explicitly extracts only ALLOW-listed fields.
    supplier_id, supplier_code, supplier_name, contract_id, is_fake_contract,
    fulfillment_version_id, fulfillment_version_name are silently ignored.
    """
    trackings_raw = raw.get("trackings") or []
    trackings = [str(t) for t in trackings_raw] if trackings_raw else []
    return DoStatus(
        id=raw.get("id", ""),
        code=raw.get("code", ""),
        status=raw.get("status", ""),
        odo_status=raw.get("odo_status", ""),
        status_date_processing=raw.get("status_date_processing"),
        status_date_delivered=raw.get("status_date_delivered"),
        trackings=trackings,
        failed_reason=raw.get("failed_reason"),
        product_label=raw.get("product_label"),
        urgent=bool(raw.get("urgent", False)),
        # DENY: supplier_id, supplier_code, supplier_name, contract_id,
        # is_fake_contract, fulfillment_version_id, fulfillment_version_name
        # — all silently dropped by explicit field extraction
    )


# ---------------------------------------------------------------------------
# ProductInfo helper
# ---------------------------------------------------------------------------


def _map_product(raw: dict[str, Any] | None) -> ProductInfo | None:
    """Map raw product dict to ProductInfo. Returns None if input is None."""
    if raw is None:
        return None
    return ProductInfo(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        code=raw.get("code"),
        line=raw.get("line"),
        family=raw.get("family"),
    )


# ---------------------------------------------------------------------------
# Order whitelist (D-04 main entry point — SEL-01)
# ---------------------------------------------------------------------------


def apply_order_whitelist(raw: dict[str, Any]) -> OrderDetail:
    """Map raw PoViewModel dict → OrderDetail (allow-listed fields only).

    Explicit field extraction — NEVER **raw spread.
    DENY fields (payment, total_product_cost, handling_fee, note, supplier_*,
    contract_id, is_fake_contract, fulfillment_version_*) are silently dropped.

    This is the ONLY place raw Selless dicts become OrderDetail models (D-04).
    """
    # Map nested DO list — each stripped of supplier/contract/fulfillment fields
    raw_dos = raw.get("delivery_orders") or []
    delivery_orders = [_map_do_status(do) for do in raw_dos]

    return OrderDetail(
        id=raw["id"],
        code=raw["code"],
        status=raw.get("status", ""),
        created=raw.get("created", ""),
        amount=float(raw.get("amount", 0.0)),
        items_amount=float(raw.get("items_amount", 0.0)),
        tax_amount=float(raw.get("tax_amount", 0.0)),
        discount=float(raw.get("discount", 0.0)),
        shipping=float(raw.get("shipping", 0.0)),
        closed_reason=raw.get("closed_reason"),
        shipping_address=_map_address(raw.get("shipping_address")),
        billing_address=_map_address(raw.get("billing_address")),
        product=_map_product(raw.get("product")),
        delivery_orders=delivery_orders,
        # DENY: payment, total_product_cost, handling_fee, note
        # — all silently dropped (not referenced above)
    )


# ---------------------------------------------------------------------------
# Customer whitelist (D-04 — SEL-02)
# ---------------------------------------------------------------------------


def apply_customer_whitelist(raw: dict[str, Any]) -> CustomerInfo:
    """Map raw CustomerViewModel dict → CustomerInfo (allow-listed fields only).

    Explicit field extraction — NEVER **raw spread.
    This is the ONLY place raw Selless customer dicts become CustomerInfo models.
    """
    return CustomerInfo(
        id=raw["id"],
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        full_name=raw.get("full_name", ""),
        email=raw.get("email", ""),
        phone=raw.get("phone", ""),
        email_status=raw.get("email_status"),
        phone_status=raw.get("phone_status"),
    )


# ---------------------------------------------------------------------------
# Ticket history whitelist (D-04 / D-05 — SEL-03)
# ---------------------------------------------------------------------------


def apply_ticket_history_whitelist(raw: dict[str, Any]) -> TicketHistory:
    """Map raw TicketViewModel dict → TicketHistory (allow-listed fields only).

    ALLOW: rootcause, customer_feedback, customer_request, status, source, created.
    DENY: agent, agent_id (internal CS fields — must never reach the drafter).

    Explicit field extraction — NEVER **raw spread.
    """
    return TicketHistory(
        rootcause=raw.get("rootcause"),
        customer_feedback=raw.get("customer_feedback"),
        customer_request=raw.get("customer_request"),
        status=raw.get("status"),
        source=raw.get("source"),
        created=raw.get("created"),
        # DENY: agent, agent_id — silently dropped (not referenced above)
    )
