"""D-14: override row in policy_resolution table resolves a known conflict.

Tests:
  - With a policy_resolution row AND real ingested data (pipeline output),
    resolved_by_override=True and winning citation first.
  - Without a resolution row, resolved_by_override=False while conflict=True (D-13).
  - apply_override does NOT drop any citations (D-13 surface-all rule).

IMPORTANT: These tests drive the override through REAL pipeline output — they do NOT
hand-craft citations with a "conflict:<ID>:..." snapshot_version prefix (that prefix
was dead code; the ingest pipeline never wrote it).  Instead:
  1. An IngestPipeline run writes kb_chunk rows with metadata={"conflict_id": "CONTRA-XX"}.
  2. hybrid_search + assemble_citations produce Citation objects with .conflict_id set.
  3. apply_override queries policy_resolution and reorders based on those conflict_ids.
"""

from __future__ import annotations

import json
import hashlib
import pytest

from src.knowledge_mcp import conflict as conflict_mod
from src.knowledge_mcp import retrieval as retrieval_mod
from src.knowledge_mcp.conflict import apply_override, apply_conflict_flag
from src.knowledge_mcp.retrieval import assemble_citations
from src.knowledge_mcp.models import Citation
from src.ingest.pipeline import IngestPipeline


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_citation(source: str, recency_flag=None, authority_rank: int = 2,
                   snapshot_version: str = "snap-001", text: str = "policy text",
                   conflict_id: str | None = None) -> Citation:
    return Citation(
        text=text,
        source=source,
        source_type="policy_prose",
        authority_rank=authority_rank,
        recency_flag=recency_flag,
        snapshot_version=snapshot_version,
        score=0.5,
        conflict_id=conflict_id,
    )


async def _seed_policy_resolution(conn, conflict_id: str, winning_source: str,
                                   resolved_value: str, resolved_by: str = "CS Lead"):
    await conn.execute(
        """
        INSERT INTO knowledge.policy_resolution
            (conflict_id, winning_source, resolved_value, resolved_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (conflict_id) DO UPDATE
            SET winning_source = EXCLUDED.winning_source,
                resolved_value = EXCLUDED.resolved_value
        """,
        conflict_id, winning_source, resolved_value, resolved_by,
    )


async def _seed_kb_chunk(conn, *, source: str, body: str,
                          authority_rank: int = 2, recency_flag=None,
                          conflict_id: str | None = None,
                          snapshot_version: str = "test-run-1"):
    """Insert a kb_chunk row exactly as the real IngestPipeline would produce it.

    metadata carries conflict_id when set — this is the real linkage path (D-14).
    snapshot_version is the ingest run_id, never a "conflict:..." prefix.
    """
    ch = hashlib.sha256(f"{source}\x00{body}".encode()).hexdigest()
    metadata: dict = {"recency_flag": recency_flag}
    if conflict_id:
        metadata["conflict_id"] = conflict_id
    await conn.execute(
        """
        INSERT INTO knowledge.kb_chunk
            (content_hash, source, source_type, authority_rank, recency_flag,
             body, embedding, metadata, snapshot_version)
        VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9)
        ON CONFLICT (content_hash) DO NOTHING
        """,
        ch, source, "policy_prose", authority_rank, recency_flag,
        body, [0.0] * 1024, json.dumps(metadata), snapshot_version,
    )


# ── integration tests via real pipeline-shaped data ───────────────────────────

@pytest.mark.asyncio
async def test_override_applies_on_real_pipeline_output(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: override is applied when conflict_id comes from REAL kb_chunk.metadata.

    Drives the full path: ingest-shaped row -> hybrid_search -> assemble_citations
    -> apply_override.  Citation.conflict_id must be populated from metadata, NOT
    from a hand-crafted snapshot_version prefix.
    """
    conflict_mod.set_pool(db_pool)
    retrieval_mod.set_pool(db_pool)

    # Seed an override ruling for CONTRA-01
    async with db_pool.acquire() as conn:
        await _seed_policy_resolution(
            conn,
            conflict_id="CONTRA-01",
            winning_source="WorkFlow.svg",
            resolved_value="45 days from purchase date",
            resolved_by="CS Lead",
        )

        # Seed two kb_chunk rows as the real ingest pipeline would produce them.
        # Both carry conflict_id="CONTRA-01" in their metadata JSONB.
        # snapshot_version is a plain run_id — NO "conflict:..." prefix.
        await _seed_kb_chunk(
            conn,
            source="billing-template.md",
            body="warranty policy: 14 days from delivery date for returns",
            authority_rank=2,
            recency_flag="stale",
            conflict_id="CONTRA-01",
            snapshot_version="test-run-1",
        )
        await _seed_kb_chunk(
            conn,
            source="WorkFlow.svg",
            body="warranty policy: 45 days from purchase date for returns",
            authority_rank=3,
            recency_flag=None,
            conflict_id="CONTRA-01",
            snapshot_version="test-run-1",
        )

    # Retrieve via real hybrid_search path (uses FTS since embeddings are zero-vectors)
    from src.knowledge_mcp.retrieval import hybrid_search
    candidates = await hybrid_search("warranty days return policy", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    # Verify that assemble_citations carried conflict_id from metadata
    conflict_ids_on_citations = [c.conflict_id for c in citations if c.conflict_id]
    assert conflict_ids_on_citations, (
        "assemble_citations must populate Citation.conflict_id from kb_chunk.metadata. "
        "Got citations with no conflict_id — pipeline-to-citation linkage is broken."
    )
    assert all(cid == "CONTRA-01" for cid in conflict_ids_on_citations), (
        f"Expected conflict_id='CONTRA-01' on all conflict-tagged citations, "
        f"got: {conflict_ids_on_citations}"
    )

    # Now apply override — must resolve because policy_resolution row exists
    reordered, resolved = await apply_override(citations, pool=db_pool)

    assert resolved is True, (
        "resolved_by_override must be True when policy_resolution row exists and "
        "Citation.conflict_id is populated from real pipeline metadata. "
        "If False, the conflict_id is not reaching apply_override."
    )
    assert reordered[0].source == "WorkFlow.svg", (
        f"Expected WorkFlow.svg first (winning source per override row), "
        f"got {reordered[0].source!r}"
    )
    # D-13: all citations still present — none dropped
    assert len(reordered) == len(citations), "D-13: no citations may be dropped by override"


@pytest.mark.asyncio
async def test_no_override_falls_back_to_conflict_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: without resolution row, conflict=True + resolved_by_override=False (D-13 behavior).

    Uses real pipeline-shaped metadata rows — no hand-crafted snapshot_version prefix.
    """
    conflict_mod.set_pool(db_pool)
    retrieval_mod.set_pool(db_pool)

    # No policy_resolution row seeded — table is empty (clean_knowledge_db truncates it)
    async with db_pool.acquire() as conn:
        await _seed_kb_chunk(
            conn,
            source="billing-template.md",
            body="warranty return fourteen delivery stale policy",
            authority_rank=2,
            recency_flag="stale",
            conflict_id="CONTRA-01",
        )
        await _seed_kb_chunk(
            conn,
            source="WorkFlow.svg",
            body="warranty return fortyfive purchase current policy",
            authority_rank=3,
            recency_flag=None,
            conflict_id="CONTRA-01",
        )

    from src.knowledge_mcp.retrieval import hybrid_search
    candidates = await hybrid_search("warranty return policy", top_k=5, pool=db_pool)
    citations = assemble_citations(candidates)

    # Both rows must be retrieved for a meaningful conflict test
    assert len(citations) >= 2, (
        f"Expected >=2 citations (stale + current), got {len(citations)}. "
        "FTS may not have matched the seeded rows — check body text vs query stemming."
    )

    reordered, resolved = await apply_override(citations, pool=db_pool)

    # D-14: no override row → not resolved
    assert resolved is False, "resolved_by_override must be False when no policy_resolution row"
    # D-13: all citations still present
    assert len(reordered) == len(citations)

    # D-13: conflict flag still raised (stale + current citations present)
    conflict_result = apply_conflict_flag(reordered)
    assert conflict_result.has_conflict is True
    assert conflict_result.resolved is False


@pytest.mark.asyncio
async def test_override_does_not_drop_citations(db_pool, stub_embedder, clean_knowledge_db):
    """D-13 + D-14: even with an override, ALL citations are returned (none dropped).

    Uses Citation objects with conflict_id set directly (unit-level test of apply_override logic).
    """
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_policy_resolution(
            conn,
            conflict_id="CONTRA-02",
            winning_source="WorkFlow.svg",
            resolved_value="20% discount cap",
            resolved_by="CS Lead",
        )

    # Three citations with conflict_id set — simulates what assemble_citations produces
    citations = [
        _make_citation("Confluence/discount-policy", "stale", authority_rank=1,
                       conflict_id="CONTRA-02"),
        _make_citation("Email Templates/discount.md", None, authority_rank=2,
                       conflict_id="CONTRA-02"),
        _make_citation("WorkFlow.svg", None, authority_rank=3,
                       conflict_id="CONTRA-02"),
    ]

    reordered, resolved = await apply_override(citations, pool=db_pool)

    assert resolved is True
    assert reordered[0].source == "WorkFlow.svg"
    # All 3 citations present
    assert len(reordered) == 3, f"Expected 3 citations, got {len(reordered)}"


@pytest.mark.asyncio
async def test_citation_without_conflict_id_not_overridden(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: citations with no conflict_id are not touched by apply_override.

    Ensures apply_override returns False (not resolved) when no conflict_id is
    present on any citation — even if a policy_resolution row exists for some
    unrelated conflict.
    """
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_policy_resolution(
            conn,
            conflict_id="CONTRA-01",
            winning_source="WorkFlow.svg",
            resolved_value="45 days from purchase date",
        )

    # Citations with NO conflict_id (as returned by ingest of non-conflicting sources)
    citations = [
        _make_citation("WorkFlow.svg", None, authority_rank=3, conflict_id=None),
        _make_citation("Confluence/returns.pdf", None, authority_rank=1, conflict_id=None),
    ]

    reordered, resolved = await apply_override(citations, pool=db_pool)

    assert resolved is False, (
        "apply_override must return False when no citation carries a conflict_id — "
        "there is nothing to look up in policy_resolution"
    )
    assert reordered == citations  # order unchanged
