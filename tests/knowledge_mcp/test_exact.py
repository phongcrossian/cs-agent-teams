"""KB-05/D-10: exact-lookup tools return stored values, never LLM-derived.

Tests:
  - lookup_threshold("THR-03") returns ThresholdResult with value containing "45 days"
  - lookup_threshold with unknown id raises KeyError
  - lookup_code("C1") returns dict with action field
"""

from __future__ import annotations

import pytest

from src.knowledge_mcp import exact as exact_mod
from src.knowledge_mcp.exact import lookup_threshold_row, lookup_code_row
from src.knowledge_mcp.models import ThresholdResult


# ── helpers ───────────────────────────────────────────────────────────────────

async def _seed_threshold(conn, threshold_id: str, value: str,
                           source: str = "WorkFlow.svg",
                           authority_rank: int = 3,
                           conflict_id=None,
                           snapshot_version: str = "snap-001"):
    await conn.execute(
        """
        INSERT INTO knowledge.policy_threshold
            (threshold_id, label, value, source, authority_rank, conflict_id, snapshot_version)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (threshold_id) DO UPDATE
            SET value = EXCLUDED.value,
                snapshot_version = EXCLUDED.snapshot_version
        """,
        threshold_id,
        f"Label for {threshold_id}",
        value,
        source,
        authority_rank,
        conflict_id,
        snapshot_version,
    )


async def _seed_code(conn, code: str, action: str,
                      template_code=None, source: str = "CODE-MAP.md",
                      snapshot_version: str = "snap-001"):
    await conn.execute(
        """
        INSERT INTO knowledge.code_map
            (code, action, template_code, source, snapshot_version)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (code) DO UPDATE
            SET action = EXCLUDED.action,
                snapshot_version = EXCLUDED.snapshot_version
        """,
        code, action, template_code, source, snapshot_version,
    )


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lookup_threshold_exact_value(db_pool, clean_knowledge_db):
    """D-10: lookup_threshold returns exact string value from DB row, not LLM-derived."""
    exact_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_threshold(
            conn,
            threshold_id="THR-03",
            value="45 days from purchase date",
            source="WorkFlow.svg",
            authority_rank=3,
            conflict_id="CONTRA-01",
            snapshot_version="snap-thr-001",
        )

    result = await lookup_threshold_row("THR-03", pool=db_pool)

    assert isinstance(result, ThresholdResult)
    assert result.threshold_id == "THR-03"
    assert "45 days" in result.value, f"Expected '45 days' in value, got: {result.value!r}"
    assert result.source == "WorkFlow.svg"
    assert result.conflict_id == "CONTRA-01"


@pytest.mark.asyncio
async def test_lookup_threshold_not_found_raises(db_pool, clean_knowledge_db):
    """D-10: lookup_threshold raises KeyError for unknown threshold_id."""
    exact_mod.set_pool(db_pool)

    with pytest.raises(KeyError, match="THR-UNKNOWN"):
        await lookup_threshold_row("THR-UNKNOWN", pool=db_pool)


@pytest.mark.asyncio
async def test_lookup_code_returns_action(db_pool, clean_knowledge_db):
    """D-10: lookup_code returns action + template_code for a known workflow code."""
    exact_mod.set_pool(db_pool)

    async with db_pool.acquire() as conn:
        await _seed_code(
            conn,
            code="C1",
            action="Issue standard warranty replacement",
            template_code="B8",
            source="CODE-MAP.md",
            snapshot_version="snap-code-001",
        )

    result = await lookup_code_row("C1", pool=db_pool)

    assert isinstance(result, dict)
    assert result["code"] == "C1"
    assert result["action"] == "Issue standard warranty replacement"
    assert result["template_code"] == "B8"


@pytest.mark.asyncio
async def test_lookup_code_not_found_raises(db_pool, clean_knowledge_db):
    """D-10: lookup_code raises KeyError for unknown code."""
    exact_mod.set_pool(db_pool)

    with pytest.raises(KeyError, match="UNKNOWN-CODE"):
        await lookup_code_row("UNKNOWN-CODE", pool=db_pool)
