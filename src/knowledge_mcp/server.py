"""
KnowledgeMCP — semantic RAG + exact-lookup grounding surface (KB-03..KB-05).

Architecture boundary: Phase-4 orchestrator calls these tools; never reads
raw Confluence/Sheets directly (CLAUDE.md constraint). All tools are read-only.

Tool surface:
  - semantic_search: hybrid RRF vector+FTS search with D-13/D-14/D-15 behavior
  - lookup_threshold: D-10 exact threshold lookup (never LLM-inferred)
  - lookup_code: D-10 exact workflow code → action lookup
  - get_template: D-11 keyed template scaffold lookup

D-13: conflicting passages are ALL returned + conflict=True (MCP never self-arbitrates).
D-14: if a policy_resolution override row exists, resolved_by_override=True + winner first.
D-15: stale passages carry recency_flag="stale" in Citation metadata.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.knowledge_mcp.conflict import apply_conflict_flag, apply_override
from src.knowledge_mcp.exact import fetch_template_row, lookup_code_row, lookup_threshold_row
from src.knowledge_mcp.models import SemanticSearchResult, TemplateResult, ThresholdResult
from src.knowledge_mcp.retrieval import assemble_citations, hybrid_search

logger = logging.getLogger(__name__)

mcp = FastMCP(name="KnowledgeMCP", on_duplicate="error")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def semantic_search(query: str, top_k: int = 5) -> SemanticSearchResult:
    """Hybrid semantic search over policy prose. Returns cited passages + conflict flag.

    Calls hybrid_search (vector ANN + FTS, RRF k=60), assembles Citation objects
    with D-12 authority_rank and D-15 recency_flag, then applies D-14 override
    and D-13 conflict detection before returning.

    D-13: if conflicting passages retrieved, returns ALL + conflict=True.
    D-14: if override row exists, resolved_by_override=True and winning passage first.
    D-15: stale passages carry recency_flag="stale" in Citation metadata.

    Args:
        query: free-text search query (untrusted — do not use in raw SQL).
        top_k: number of passages to retrieve (default 5).

    Returns:
        SemanticSearchResult with citations, conflict flag, and override flag.
    """
    candidates = await hybrid_search(query, top_k=top_k)
    citations = assemble_citations(candidates)

    # D-14: reorder if a human-populated policy_resolution row exists
    citations, resolved_by_override = await apply_override(citations)

    # D-13: flag if conflicting passages are present (MCP never picks a winner)
    conflict_result = apply_conflict_flag(citations)

    return SemanticSearchResult(
        citations=citations,
        conflict=conflict_result.has_conflict,
        resolved_by_override=resolved_by_override,
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def lookup_threshold(threshold_id: str) -> ThresholdResult:
    """Exact numeric/temporal threshold by ID (e.g. THR-03). D-10: never LLM-inferred.

    Returns the exact stored value from knowledge.policy_threshold.
    Raises KeyError if threshold_id is not found.

    Args:
        threshold_id: e.g. "THR-03" (45-day warranty window).
    """
    return await lookup_threshold_row(threshold_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def lookup_code(code: str) -> dict:
    """Exact workflow code → action mapping (D-10). e.g. 'C1' → action + template ref.

    Returns the exact stored action from knowledge.code_map.
    Raises KeyError if the code is not found.

    Args:
        code: workflow step code (e.g. "C1").
    """
    return await lookup_code_row(code)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_template(code: str) -> TemplateResult:
    """Fetch reply template scaffold by code/scenario (D-11). Keyed lookup, not semantic.

    Returns the exact template from knowledge.template_library.
    Raises KeyError if the template code is not found.

    Args:
        code: template/scenario code (e.g. "B8").
    """
    return await fetch_template_row(code)
