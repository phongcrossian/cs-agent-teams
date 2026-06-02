"""RED stub — D-14: override row in policy_resolution table resolves a known conflict.

Contract: when a policy_resolution row exists for a conflict_id, semantic_search
puts the winning passage first in citations and sets resolved_by_override=True.
Without a resolution row, D-13 behavior applies (all + conflict=True).
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 02 creates src/knowledge_mcp/server.py + conflict.py
from src.knowledge_mcp.server import semantic_search  # noqa: F401
from src.knowledge_mcp.conflict import apply_override  # noqa: F401


@pytest.mark.asyncio
async def test_override_row_resolves_conflict(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: when policy_resolution row exists, resolved_by_override=True and winner first."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-14)")


@pytest.mark.asyncio
async def test_no_override_falls_back_to_conflict_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: without resolution row, conflict=True + resolved_by_override=False (D-13 behavior)."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-14)")
