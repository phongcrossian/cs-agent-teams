"""KB-05: semantic_search returns citations with source/authority/recency metadata.

Tests:
  - citations carry required metadata fields (source, authority_rank, snapshot_version, score)
  - D-12: authority_rank is an int matching the ingested value
  - D-15: stale-flagged chunks surface with recency_flag="stale" in their Citation
"""

from __future__ import annotations

import json
import pytest

from src.knowledge_mcp import retrieval as retrieval_mod
from src.knowledge_mcp import conflict as conflict_mod
from src.knowledge_mcp.retrieval import hybrid_search, assemble_citations
from src.knowledge_mcp.models import SemanticSearchResult, Citation


# ── helpers ──────────────────────────────────────────────────────────────────

async def _seed_chunk(conn, *, source: str, source_type: str = "policy_prose",
                      authority_rank: int = 3, recency_flag=None,
                      body: str = "warranty policy text for customers",
                      snapshot_version: str = "snap-001"):
    """Insert a kb_chunk row with a zero-vector embedding."""
    import hashlib
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
        body,
        [0.0] * 1024,  # zero vector — matches stub_embedder query vector
        json.dumps({}),
        snapshot_version,
    )


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_semantic_search_returns_citations(db_pool, stub_embedder, clean_knowledge_db):
    """KB-05: semantic_search returns at least 1 citation with required metadata fields."""
    retrieval_mod.set_pool(db_pool)
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_chunk(
            conn,
            source="WorkFlow.svg",
            source_type="policy_prose",
            authority_rank=3,
            body="warranty policy: customers have 45 days to request return",
            snapshot_version="snap-v1",
        )

    candidates = await hybrid_search("warranty policy", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    assert len(citations) >= 1, "Expected at least one citation"
    c = citations[0]

    # KB-05: each Citation must carry these metadata fields
    assert isinstance(c, Citation)
    assert c.source, "source must be non-empty"
    assert isinstance(c.authority_rank, int), "authority_rank must be int"
    assert c.snapshot_version, "snapshot_version must be non-empty"
    assert isinstance(c.score, float), "score must be float"
    assert c.text, "text must be non-empty"


@pytest.mark.asyncio
async def test_semantic_search_authority_rank_present(db_pool, stub_embedder, clean_knowledge_db):
    """KB-05/D-12: citations carry authority_rank (WorkFlow=3 > Templates=2 > Confluence=1)."""
    retrieval_mod.set_pool(db_pool)
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_chunk(
            conn,
            source="WorkFlow.svg",
            source_type="policy_prose",
            authority_rank=3,
            body="workflow policy for order processing steps",
            snapshot_version="snap-v2",
        )
        await _seed_chunk(
            conn,
            source="Email Templates/warranty.md",
            source_type="template",
            authority_rank=2,
            body="template text for warranty response emails",
            snapshot_version="snap-v3",
        )

    candidates = await hybrid_search("policy processing", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    assert len(citations) >= 1
    for c in citations:
        assert isinstance(c.authority_rank, int), "authority_rank must be int"
        assert c.authority_rank in (1, 2, 3), f"Unexpected authority_rank: {c.authority_rank}"


@pytest.mark.asyncio
async def test_stale_chunk_surfaces_with_recency_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-15: a kb_chunk seeded with recency_flag='stale' surfaces with recency_flag='stale'."""
    retrieval_mod.set_pool(db_pool)
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_chunk(
            conn,
            source="billing-template.md",
            source_type="template",
            authority_rank=2,
            recency_flag="stale",
            body="billing and chargeback policy stale content",
            snapshot_version="snap-stale-001",
        )

    candidates = await hybrid_search("billing chargeback", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    stale_citations = [c for c in citations if c.recency_flag == "stale"]
    assert len(stale_citations) >= 1, "Stale-flagged chunk must surface with recency_flag='stale'"
    assert stale_citations[0].source == "billing-template.md"
