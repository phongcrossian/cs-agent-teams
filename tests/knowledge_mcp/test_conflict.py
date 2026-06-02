"""D-13: conflicting passages surface all + conflict flag (MCP never self-arbitrates).

Tests:
  - When passages from conflicting sources retrieved (stale + current), conflict=True
  - ALL conflicting citations are present — none dropped
  - When single non-conflicting source, conflict=False
  - apply_conflict_flag detects stale citations (D-13/D-15)
"""

from __future__ import annotations

import json
import hashlib
import pytest

from src.knowledge_mcp import retrieval as retrieval_mod
from src.knowledge_mcp import conflict as conflict_mod
from src.knowledge_mcp.retrieval import hybrid_search, assemble_citations
from src.knowledge_mcp.conflict import apply_conflict_flag, ConflictResult
from src.knowledge_mcp.models import Citation


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_citation(source: str, recency_flag=None, authority_rank: int = 2,
                   snapshot_version: str = "snap-001") -> Citation:
    return Citation(
        text=f"Policy text from {source}",
        source=source,
        source_type="policy_prose",
        authority_rank=authority_rank,
        recency_flag=recency_flag,
        snapshot_version=snapshot_version,
        score=0.5,
    )


async def _seed_chunk(conn, *, source: str, source_type: str = "policy_prose",
                      authority_rank: int = 3, recency_flag=None,
                      body: str, snapshot_version: str = "snap-001"):
    content_hash = hashlib.sha256(f"{source}\x00{body}".encode()).hexdigest()
    await conn.execute(
        """
        INSERT INTO knowledge.kb_chunk
            (content_hash, source, source_type, authority_rank, recency_flag,
             body, embedding, metadata, snapshot_version)
        VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9)
        ON CONFLICT (content_hash) DO NOTHING
        """,
        content_hash, source, source_type, authority_rank, recency_flag,
        body, [0.0] * 1024, json.dumps({}), snapshot_version,
    )


# ── unit tests (no DB needed) ─────────────────────────────────────────────────

def test_apply_conflict_flag_detects_stale():
    """D-13/D-15: apply_conflict_flag returns has_conflict=True when any citation is stale
    alongside non-stale citations."""
    stale = _make_citation("billing-template.md", recency_flag="stale")
    current = _make_citation("WorkFlow.svg", recency_flag=None, authority_rank=3)

    result = apply_conflict_flag([stale, current])

    assert isinstance(result, ConflictResult)
    assert result.has_conflict is True
    assert result.resolved is False  # D-13: no self-arbitration


def test_apply_conflict_flag_no_conflict_single_source():
    """D-13: conflict=False when all citations are from non-conflicting, non-stale sources."""
    c1 = _make_citation("WorkFlow.svg", recency_flag=None, authority_rank=3)
    c2 = _make_citation("WorkFlow.svg", recency_flag=None, authority_rank=3,
                         snapshot_version="snap-002")

    result = apply_conflict_flag([c1, c2])

    assert result.has_conflict is False
    assert result.resolved is False


def test_apply_conflict_flag_empty_returns_no_conflict():
    """apply_conflict_flag on empty list returns has_conflict=False."""
    result = apply_conflict_flag([])
    assert result.has_conflict is False
    assert result.resolved is False


def test_apply_conflict_flag_all_stale_no_conflict():
    """D-13: if ALL citations are stale (no current-state ones), no conflict to flag."""
    s1 = _make_citation("billing-template.md", recency_flag="stale")
    s2 = _make_citation("old-template.md", recency_flag="stale")

    result = apply_conflict_flag([s1, s2])

    # Only stale, no current counterpart — no conflict detected (stale vs stale is not a conflict)
    assert result.has_conflict is False


# ── integration tests (DB-backed via hybrid_search) ──────────────────────────

@pytest.mark.asyncio
async def test_conflicting_passages_sets_conflict_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-13: when stale and current passages retrieved, conflict=True in result."""
    retrieval_mod.set_pool(db_pool)
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        # Current policy passage
        await _seed_chunk(
            conn,
            source="WorkFlow.svg",
            source_type="policy_prose",
            authority_rank=3,
            recency_flag=None,
            body="warranty policy: 45 days from purchase date for returns",
            snapshot_version="snap-current",
        )
        # Stale conflicting passage
        await _seed_chunk(
            conn,
            source="billing-template.md",
            source_type="template",
            authority_rank=2,
            recency_flag="stale",
            body="warranty policy: 14 days from delivery date for returns",
            snapshot_version="snap-stale",
        )

    candidates = await hybrid_search("warranty days return", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    # Must surface BOTH passages (D-13 surface-all)
    assert len(citations) >= 2, f"Expected >=2 citations, got {len(citations)}"

    # Apply conflict detection
    conflict_result = apply_conflict_flag(citations)
    assert conflict_result.has_conflict is True, "Expected conflict=True for stale+current mix"
    assert conflict_result.resolved is False, "D-13: no self-arbitration — resolved must be False"


@pytest.mark.asyncio
async def test_no_conflict_when_single_source(db_pool, stub_embedder, clean_knowledge_db):
    """D-13: conflict=False when all passages from the same non-conflicting source."""
    retrieval_mod.set_pool(db_pool)
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_chunk(
            conn,
            source="WorkFlow.svg",
            source_type="policy_prose",
            authority_rank=3,
            recency_flag=None,
            body="standard return process for domestic orders step one",
            snapshot_version="snap-a",
        )
        await _seed_chunk(
            conn,
            source="WorkFlow.svg",
            source_type="policy_prose",
            authority_rank=3,
            recency_flag=None,
            body="standard return process for domestic orders step two",
            snapshot_version="snap-b",
        )

    candidates = await hybrid_search("standard return domestic", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    conflict_result = apply_conflict_flag(citations)
    assert conflict_result.has_conflict is False
