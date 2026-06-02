"""RED stub — standalone grounding demo (Phase 3 demonstrable end-state, sandbox marker).

This smoke test acts as an MCP client and proves all four Phase-3 success criteria:
1. Knowledge MCP semantic_search("warranty window") -> >= 1 Citation, conflict=True
   (warranty CONTRA-01 is a known HIGH conflict — perfect demo case).
2. Knowledge MCP lookup_threshold("THR-03") -> exact "45 days from purchase" (D-10).
3. Knowledge MCP get_template("C1") -> template scaffold returned (D-11).
4. Selless MCP get_order_status() against MockSellessClient -> whitelisted fields only,
   then assert redacted audit.selless_audit row was written (SEL-04).

Requires: RUN_SANDBOX=1 + VOYAGE_API_KEY (or stub_embedder fixture) to run.
Skipped in CI automatically (sandbox marker).
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plans 01-03 create the modules
from src.knowledge_mcp.server import semantic_search, lookup_threshold, get_template  # noqa: F401
from src.selless_mcp.server import get_order_status  # noqa: F401


@pytest.mark.sandbox
@pytest.mark.asyncio
async def test_grounding_demo_semantic_warranty_conflict(db_pool, stub_embedder, clean_knowledge_db):
    """KB-05/D-13: semantic_search('warranty window') returns citations with conflict=True (CONTRA-01)."""
    raise NotImplementedError("RED stub — implement after Plans 01-03 (Phase-3 smoke demo)")


@pytest.mark.sandbox
@pytest.mark.asyncio
async def test_grounding_demo_exact_threshold(db_pool, clean_knowledge_db):
    """D-10: lookup_threshold('THR-03') returns exact '45 days from purchase'."""
    raise NotImplementedError("RED stub — implement after Plans 01-03 (Phase-3 smoke demo)")


@pytest.mark.sandbox
@pytest.mark.asyncio
async def test_grounding_demo_template_fetch(db_pool, clean_knowledge_db):
    """D-11: get_template('C1') returns a template scaffold with subject + body templates."""
    raise NotImplementedError("RED stub — implement after Plans 01-03 (Phase-3 smoke demo)")


@pytest.mark.sandbox
@pytest.mark.asyncio
async def test_grounding_demo_selless_whitelist_and_audit(db_pool, mock_selless_client, clean_knowledge_db):
    """SEL-01/SEL-04: get_order_status returns whitelisted fields + audit row written."""
    raise NotImplementedError("RED stub — implement after Plans 01-03 (Phase-3 smoke demo)")
