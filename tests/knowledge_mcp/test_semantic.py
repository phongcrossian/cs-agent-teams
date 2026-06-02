"""RED stub — KB-05: semantic_search returns citations with source/authority/recency/conflict.

Contract: calling semantic_search(query) returns a SemanticSearchResult with:
- citations: list[Citation] each having text, source, source_type, authority_rank,
  recency_flag, snapshot_version, score
- conflict=True when passages from conflicting sources are retrieved (D-13)
- resolved_by_override=True if a policy_resolution row applied (D-14)
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 02 creates src/knowledge_mcp/server.py
from src.knowledge_mcp.server import semantic_search  # noqa: F401
from src.knowledge_mcp.models import SemanticSearchResult, Citation  # noqa: F401


@pytest.mark.asyncio
async def test_semantic_search_returns_citations(db_pool, stub_embedder, clean_knowledge_db):
    """KB-05: semantic_search returns at least 1 citation with required metadata."""
    raise NotImplementedError("RED stub — implement in Plan 02 (KB-05)")


@pytest.mark.asyncio
async def test_semantic_search_authority_rank_present(db_pool, stub_embedder, clean_knowledge_db):
    """KB-05/D-12: citations carry authority_rank (WorkFlow=3 > Templates=2 > Confluence=1)."""
    raise NotImplementedError("RED stub — implement in Plan 02 (KB-05/D-12)")
