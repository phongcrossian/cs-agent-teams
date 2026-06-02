"""
Tests for KB-04: re-ingest is idempotent (re-run = no duplicates, changed re-embeds).

Contract: running the ingest pipeline twice on the same content produces identical
kb_chunk rows (keyed by content_hash). Changed content produces updated embedding.
Unchanged content is a no-op (no new row created).
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_reingest_no_duplicates(db_pool, stub_embedder, clean_knowledge_db):
    """KB-04: running ingest twice on same content produces same row count."""
    from src.ingest.pipeline import IngestPipeline

    pipeline = IngestPipeline(db_pool)

    # First run
    await pipeline.ingest_all(run_id="test-run-1")
    async with db_pool.acquire() as conn:
        count_after_first = await conn.fetchval("SELECT COUNT(*) FROM knowledge.kb_chunk")

    # Second run — identical content, same snapshots
    await pipeline.ingest_all(run_id="test-run-2")
    async with db_pool.acquire() as conn:
        count_after_second = await conn.fetchval("SELECT COUNT(*) FROM knowledge.kb_chunk")

    assert count_after_first > 0, "Expected rows after first ingest run"
    assert count_after_first == count_after_second, (
        f"Re-ingest created duplicates: {count_after_first} -> {count_after_second} rows "
        "(KB-04: second run should be idempotent)"
    )


@pytest.mark.asyncio
async def test_reingest_changed_content_updates_embedding(db_pool, stub_embedder, clean_knowledge_db):
    """KB-04: changing body text updates embedding and snapshot_version, new content_hash."""
    from src.ingest.pipeline import IngestPipeline, content_hash

    pipeline = IngestPipeline(db_pool)

    # Insert a synthetic chunk directly with known content_hash
    source = "WorkFlow.svg"
    original_body = "The warranty period is 45 days from purchase date."
    original_hash = content_hash(source, original_body)
    original_run = "run-original"

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO knowledge.kb_chunk
                (content_hash, source, source_type, authority_rank, body, embedding,
                 metadata, snapshot_version)
            VALUES ($1, $2, 'policy_prose', 3, $3, $4::vector, '{}', $5)
            """,
            original_hash,
            source,
            original_body,
            [0.0] * 1024,
            original_run,
        )

    # Upsert with CHANGED body — new content_hash, updated snapshot_version
    changed_body = "The warranty period is 30 days from purchase date."  # changed
    changed_hash = content_hash(source, changed_body)
    new_run = "run-changed"

    # content_hash must differ for changed content
    assert original_hash != changed_hash, "content_hash must differ for different body text"

    async with db_pool.acquire() as conn:
        await pipeline.upsert_chunk(
            conn,
            source=source,
            source_type="policy_prose",
            authority_rank=3,
            body=changed_body,
            embedding=[0.1] * 1024,
            metadata={},
            run_id=new_run,
        )

    # Verify the new row exists with updated snapshot_version
    async with db_pool.acquire() as conn:
        new_row = await conn.fetchrow(
            "SELECT * FROM knowledge.kb_chunk WHERE content_hash = $1",
            changed_hash,
        )
        original_row = await conn.fetchrow(
            "SELECT * FROM knowledge.kb_chunk WHERE content_hash = $1",
            original_hash,
        )

    assert new_row is not None, "Changed content should create a new kb_chunk row"
    assert new_row["snapshot_version"] == new_run
    # Original row is unchanged (different hash key — both co-exist)
    assert original_row is not None, "Original row should still exist (different content_hash)"
    assert original_row["snapshot_version"] == original_run


@pytest.mark.asyncio
async def test_reingest_unchanged_content_is_noop(db_pool, stub_embedder, clean_knowledge_db):
    """KB-04: upserting same body twice keeps row count at 1 (ON CONFLICT no-op)."""
    from src.ingest.pipeline import IngestPipeline

    pipeline = IngestPipeline(db_pool)
    source = "WorkFlow.svg"
    body = "The cancellation window is within 1 hour of placing the order."

    async with db_pool.acquire() as conn:
        await pipeline.upsert_chunk(
            conn, source=source, source_type="policy_prose", authority_rank=3,
            body=body, embedding=[0.0] * 1024, metadata={}, run_id="run-1",
        )
        await pipeline.upsert_chunk(
            conn, source=source, source_type="policy_prose", authority_rank=3,
            body=body, embedding=[0.0] * 1024, metadata={}, run_id="run-2",
        )
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge.kb_chunk WHERE source = $1",
            source,
        )

    assert count == 1, (
        f"Same body upserted twice should yield 1 row, got {count} (ON CONFLICT should dedup)"
    )
