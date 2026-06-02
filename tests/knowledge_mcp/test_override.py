"""D-14: override row in policy_resolution table resolves a known conflict.

Tests:
  - With a policy_resolution row, resolved_by_override=True and winning citation first
  - Without a resolution row, resolved_by_override=False while conflict=True (D-13)
  - apply_override does NOT drop any citations (D-13 surface-all rule)
"""

from __future__ import annotations

import json
import hashlib
import pytest

from src.knowledge_mcp import conflict as conflict_mod
from src.knowledge_mcp.conflict import apply_override, apply_conflict_flag
from src.knowledge_mcp.models import Citation


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_citation(source: str, recency_flag=None, authority_rank: int = 2,
                   snapshot_version: str = "snap-001", text: str = "policy text") -> Citation:
    return Citation(
        text=text,
        source=source,
        source_type="policy_prose",
        authority_rank=authority_rank,
        recency_flag=recency_flag,
        snapshot_version=snapshot_version,
        score=0.5,
    )


def _make_conflicting_citation(source: str, conflict_id: str,
                                recency_flag=None, authority_rank: int = 2) -> Citation:
    """Create a citation with a conflict_id embedded in snapshot_version."""
    return Citation(
        text=f"Policy text from {source} re: {conflict_id}",
        source=source,
        source_type="policy_prose",
        authority_rank=authority_rank,
        recency_flag=recency_flag,
        snapshot_version=f"conflict:{conflict_id}:snap-001",
        score=0.5,
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


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_override_row_resolves_conflict(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: when policy_resolution row exists, resolved_by_override=True and winner first."""
    conflict_mod.set_pool(db_pool)

    # Seed a policy_resolution override for CONTRA-01
    async with db_pool.acquire() as conn:
        await _seed_policy_resolution(
            conn,
            conflict_id="CONTRA-01",
            winning_source="WorkFlow.svg",
            resolved_value="45 days from purchase date",
            resolved_by="CS Lead",
        )

    # Two conflicting citations — "WorkFlow.svg" is the winner per override row
    citations = [
        _make_conflicting_citation(
            source="billing-template.md",
            conflict_id="CONTRA-01",
            recency_flag="stale",
            authority_rank=2,
        ),
        _make_conflicting_citation(
            source="WorkFlow.svg",
            conflict_id="CONTRA-01",
            recency_flag=None,
            authority_rank=3,
        ),
    ]

    reordered, resolved = await apply_override(citations, pool=db_pool)

    # D-14: override applied
    assert resolved is True, "resolved_by_override must be True when policy_resolution row exists"
    # D-14: winning_source citation is first
    assert reordered[0].source == "WorkFlow.svg", (
        f"Expected WorkFlow.svg first (winning source), got {reordered[0].source!r}"
    )
    # D-13: all citations still present — none dropped
    assert len(reordered) == len(citations), "D-13: no citations may be dropped"


@pytest.mark.asyncio
async def test_no_override_falls_back_to_conflict_flag(db_pool, stub_embedder, clean_knowledge_db):
    """D-14: without resolution row, conflict=True + resolved_by_override=False (D-13 behavior)."""
    conflict_mod.set_pool(db_pool)

    # No policy_resolution row seeded — table is empty (clean_knowledge_db truncates it)
    citations = [
        _make_conflicting_citation(
            source="billing-template.md",
            conflict_id="CONTRA-01",
            recency_flag="stale",
        ),
        _make_conflicting_citation(
            source="WorkFlow.svg",
            conflict_id="CONTRA-01",
            recency_flag=None,
            authority_rank=3,
        ),
    ]

    reordered, resolved = await apply_override(citations, pool=db_pool)

    # D-14: no override row → not resolved
    assert resolved is False, "resolved_by_override must be False when no policy_resolution row"
    # D-13: all citations still present
    assert len(reordered) == len(citations)

    # D-13: conflict flag still raised
    conflict_result = apply_conflict_flag(reordered)
    assert conflict_result.has_conflict is True
    assert conflict_result.resolved is False


@pytest.mark.asyncio
async def test_override_does_not_drop_citations(db_pool, clean_knowledge_db):
    """D-13 + D-14: even with an override, ALL citations are returned (none dropped)."""
    conflict_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_policy_resolution(
            conn,
            conflict_id="CONTRA-02",
            winning_source="WorkFlow.svg",
            resolved_value="20% discount cap",
            resolved_by="CS Lead",
        )

    # Three citations — one winner, two others
    citations = [
        _make_conflicting_citation("Confluence/discount-policy", "CONTRA-02", authority_rank=1),
        _make_conflicting_citation("Email Templates/discount.md", "CONTRA-02", authority_rank=2),
        _make_conflicting_citation("WorkFlow.svg", "CONTRA-02", authority_rank=3),
    ]

    reordered, resolved = await apply_override(citations, pool=db_pool)

    assert resolved is True
    assert reordered[0].source == "WorkFlow.svg"
    # All 3 citations present
    assert len(reordered) == 3, f"Expected 3 citations, got {len(reordered)}"
