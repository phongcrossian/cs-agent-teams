"""RED stub — D-03: resolve_order enforces exact-key constraint (no cross-customer search).

Contract: resolve_order(param) accepts only an exact order code (e.g. "25044-67") or a
verified customer email. It wraps /po/search with skip=0&take=1 and returns a single
identity match only. It NEVER returns a fuzzy/browse list. A non-matching param raises.
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 03 creates src/selless_mcp/server.py
from src.selless_mcp.server import resolve_order  # noqa: F401
from src.selless_mcp.models import ResolvedOrder  # noqa: F401


@pytest.mark.asyncio
async def test_resolve_order_returns_single_identity(mock_selless_client):
    """D-03: resolve_order returns exactly one ResolvedOrder for a valid order code."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-03)")


@pytest.mark.asyncio
async def test_resolve_order_no_cross_customer_search(mock_selless_client):
    """D-03: resolve_order does not accept free-text / browse queries."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-03)")
