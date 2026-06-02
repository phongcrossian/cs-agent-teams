"""RED stub — KB-04: re-ingest is idempotent (re-run = no duplicates, changed re-embeds).

Contract: running the ingest pipeline twice on the same content produces identical
kb_chunk rows (keyed by content_hash). Changed content produces updated embedding.
Unchanged content is a no-op (no new row created).
"""

from __future__ import annotations

import pytest

# RED: this import fails until Plan 01 creates src/ingest/pipeline.py
from src.ingest.pipeline import IngestPipeline  # noqa: F401


@pytest.mark.asyncio
async def test_reingest_no_duplicates(db_pool, stub_embedder, clean_knowledge_db):
    """KB-04: running ingest twice on same content produces same row count."""
    raise NotImplementedError("RED stub — implement in Plan 01 (KB-04)")


@pytest.mark.asyncio
async def test_reingest_changed_content_updates_embedding(db_pool, stub_embedder, clean_knowledge_db):
    """KB-04: changing body text updates embedding and snapshot_version, same content_hash key."""
    raise NotImplementedError("RED stub — implement in Plan 01 (KB-04)")
