"""RED stub — KB-05/D-10: lookup_threshold returns exact numeric value (never LLM-inferred).

Contract: lookup_threshold("THR-03") returns a ThresholdResult with an exact string value
loaded from knowledge.policy_threshold. No vector search, no LLM interpretation.
lookup_code("C1") returns exact action + template_code from knowledge.code_map.
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 02 creates src/knowledge_mcp/server.py
from src.knowledge_mcp.server import lookup_threshold, lookup_code  # noqa: F401
from src.knowledge_mcp.models import ThresholdResult  # noqa: F401


@pytest.mark.asyncio
async def test_lookup_threshold_exact_value(db_pool, clean_knowledge_db):
    """D-10: lookup_threshold returns exact string value from DB row, not LLM-derived."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-10)")


@pytest.mark.asyncio
async def test_lookup_threshold_not_found_raises(db_pool, clean_knowledge_db):
    """D-10: lookup_threshold raises KeyError for unknown threshold_id."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-10)")


@pytest.mark.asyncio
async def test_lookup_code_returns_action(db_pool, clean_knowledge_db):
    """D-10: lookup_code returns action + template_code for a known workflow code."""
    raise NotImplementedError("RED stub — implement in Plan 02 (D-10)")
