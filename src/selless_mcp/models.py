"""
D-04 whitelisted Pydantic models for the Selless MCP layer.

SECURITY CONTRACT: these models ARE the whitelist boundary.
No field for any DENY-listed key (payment.*, total_product_cost, supplier_*,
contract_id, is_fake_contract, fulfillment_version_id/name, handling_fee,
note, payload, agent, agent_id) may appear here — ever.

See 03-SELLESS-API.md §4 for the full allow / deny list.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Address (shipping / billing)
# ---------------------------------------------------------------------------

class Address(BaseModel):
    """Allow-listed address fields (D-04). No internal ops fields."""

    first_name: str
    last_name: str
    email: str
    phone: str
    address1: str
    address2: Optional[str] = None
    city: str
    state: str
    country: str
    postal_code: str


# ---------------------------------------------------------------------------
# Product (embedded inside OrderDetail)
# ---------------------------------------------------------------------------

class ProductInfo(BaseModel):
    """Allow-listed product identification fields (D-04).

    ALLOW: id, name, code, line, family.
    No inventory, cost, or supplier data.
    """

    id: str
    name: str
    code: Optional[str] = None
    line: Optional[str] = None
    family: Optional[str] = None


# ---------------------------------------------------------------------------
# Delivery Order / fulfillment status
# ---------------------------------------------------------------------------

class DoStatus(BaseModel):
    """Allow-listed delivery order (DO) fields (D-04).

    DENY: supplier_id, supplier_code, supplier_name, contract_id,
    is_fake_contract, fulfillment_version_id, fulfillment_version_name.
    """

    id: str
    code: str
    status: str
    odo_status: str
    status_date_processing: Optional[str] = None
    status_date_delivered: Optional[str] = None
    trackings: list[str] = Field(default_factory=list)
    failed_reason: Optional[str] = None
    product_label: Optional[str] = None
    urgent: bool = False


# ---------------------------------------------------------------------------
# Order (main SEL-01 response)
# ---------------------------------------------------------------------------

class OrderDetail(BaseModel):
    """Whitelisted view of PoViewModel (D-04).

    DENY: payment.*, total_product_cost, handling_fee, note,
    supplier_*, contract_id, is_fake_contract, fulfillment_version_*.
    ALLOW: id, code, status, created, amount, items_amount, tax_amount,
    discount, shipping, shipping_address, billing_address,
    product (id/name/code/line/family), delivery_orders.
    """

    id: str
    code: str
    status: str
    created: str
    amount: float
    items_amount: float
    tax_amount: float
    discount: float
    shipping: float
    closed_reason: Optional[str] = None
    shipping_address: Optional[Address] = None
    billing_address: Optional[Address] = None
    product: Optional[ProductInfo] = None
    delivery_orders: list[DoStatus] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Customer (SEL-02)
# ---------------------------------------------------------------------------

class CustomerInfo(BaseModel):
    """Whitelisted view of CustomerViewModel (D-04).

    ALLOW: id, first_name, last_name, full_name, email, phone,
    email_status, phone_status.
    """

    id: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    email_status: Optional[str] = None
    phone_status: Optional[str] = None


# ---------------------------------------------------------------------------
# Resolved order (D-03 constrained search result)
# ---------------------------------------------------------------------------

class ResolvedOrder(BaseModel):
    """Result of resolve_order — single exact-key identity only (D-03).

    Never a fuzzy/browse list.  Wraps /po/search with take=1 + exact match.
    """

    id: str
    code: str
    customer_id: str
    customer_email: str


# ---------------------------------------------------------------------------
# Purchase history (SEL-02 order list for a customer)
# ---------------------------------------------------------------------------

class PurchaseHistory(BaseModel):
    """Whitelisted summary of a customer's purchase history.

    Only allow-listed order fields; no payment/cost/supplier data.
    """

    orders: list[OrderDetail] = Field(default_factory=list)
    total_count: int = 0


# ---------------------------------------------------------------------------
# Ticket mapping (SEL-03 join key — Selless ticket-do endpoint)
# ---------------------------------------------------------------------------

class TicketMapping(BaseModel):
    """Result of GET /{fd_ticket_id}/ticket-do — order ↔ Freshdesk-ticket mapping.

    This is the JOIN KEY for SEL-03: fd_ticket_id → do_ids.
    Ticket CONTENT is fetched via the Phase-2 Freshdesk client, not Selless.
    """

    fd_ticket_id: int
    do_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ticket history (SEL-03 composed response, D-04/D-05)
# ---------------------------------------------------------------------------

class TicketHistory(BaseModel):
    """Whitelisted prior-ticket content (D-04 / D-05).

    Source: Phase-2 Freshdesk client (via ticket-do mapping as join key).
    ALLOW: rootcause, customer_feedback, customer_request, status, source, created.
    DENY: agent, agent_id (internal CS fields — must never reach the drafter).
    """

    rootcause: Optional[str] = None
    customer_feedback: Optional[str] = None
    customer_request: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    created: Optional[str] = None
