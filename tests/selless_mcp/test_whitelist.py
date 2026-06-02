"""RED stub — D-04: field whitelist hard-denies payment/cost/other-customer fields.

Contract: apply_order_whitelist(raw_dict) maps PoViewModel raw dict to OrderDetail,
silently dropping all non-allow-listed fields. If a hard-DENY field is present in
raw (e.g. "payment", "total_product_cost", "handling_fee"), the whitelist must not
expose it in the returned model. DENY fields must not appear as attributes on result.
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 03 creates src/selless_mcp/whitelist.py
from src.selless_mcp.whitelist import apply_order_whitelist  # noqa: F401


def test_whitelist_drops_payment_field():
    """D-04: payment field from raw PoViewModel must not appear in OrderDetail."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-04)")


def test_whitelist_drops_total_product_cost():
    """D-04: total_product_cost (internal margin) must be hard-denied."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-04)")


def test_whitelist_drops_handling_fee():
    """D-04: handling_fee must be hard-denied (financial sensitivity)."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-04)")


def test_whitelist_preserves_allowed_fields():
    """D-04: status, code, created, amount, shipping_address are ALLOW-listed."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-04)")
