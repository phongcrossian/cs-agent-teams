"""RED stub — D-13: conflicting passages surface all + conflict flag (MCP never self-arbitrates).

Contract: when semantic_search retrieves passages from conflicting sources (e.g. warranty
window CONTRA-01: 45d purchase-date vs 14d delivery-date), it returns ALL passages and
sets conflict=True. It does NOT pick a winner. The Phase-4 orchestrator reacts to conflict=True.
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 02 creates src/knowledge_mcp/server.py + conflict.py
from src.knowledge_mcp.server import semantic_search  # noqa: F401
from src.knowledge_mcp.conflict import apply_conflict_flag  # noqa: F401


@pytest.mark.asyncio
async def test_conflicting_passages_sets_conflict_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-13: when passages from conflicting sources retrieved, conflict=True in result."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-13)")


@pytest.mark.asyncio
async def test_no_conflict_when_single_source(db_pool, stub_embedder, clean_knowledge_db):
    """D-13: conflict=False when all passages from the same (non-conflicting) source."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-13)")


def test_apply_conflict_flag_detects_stale():
    """D-13/D-15: apply_conflict_flag returns has_conflict=True when any citation is stale."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-13/D-15)")
