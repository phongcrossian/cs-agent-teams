"""RED stub — SEL-04/D-08: rate limit enforced at MCP boundary, independent of Freshdesk limiter.

Contract: the Selless MCP server applies a server-wide token bucket at the MCP boundary.
Burst capacity is respected (first N calls allowed immediately). Past burst, calls are
rate-limited (429-equivalent error or sleep). Rate limit is configured via settings:
selless_rate_limit_rps (default 1.0) and selless_rate_limit_burst (default 10).
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 03 creates src/selless_mcp/server.py
from src.selless_mcp.server import mcp  # noqa: F401


@pytest.mark.asyncio
async def test_rate_limit_allows_burst(mock_selless_client):
    """D-08: first burst_capacity calls succeed immediately (no throttle)."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-08)")


@pytest.mark.asyncio
async def test_rate_limit_throttles_past_burst(mock_selless_client):
    """D-08: calls past burst_capacity are rate-limited by MCP server token bucket."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-08)")
