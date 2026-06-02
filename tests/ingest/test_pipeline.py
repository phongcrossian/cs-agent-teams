"""RED stub — KB-03: ingest pipeline builds chunks + exact tables from snapshots.

This file imports src.ingest.pipeline which does not exist yet (Plan 01 creates it).
Collection will error RED until Plan 01 implements the module.

Contract: ingest_pipeline(source_dir, db_pool) normalizes+chunks prose sources,
embeds via Voyage, and upserts into knowledge.kb_chunk idempotently. Structured
data (thresholds, codes) loads into exact tables.
"""

from __future__ import annotations

import pytest

# RED: this import fails until Plan 01 creates src/ingest/pipeline.py
from src.ingest.pipeline import IngestPipeline  # noqa: F401


@pytest.mark.asyncio
async def test_pipeline_creates_kb_chunks(db_pool, stub_embedder, clean_knowledge_db):
    """KB-03: running the pipeline against snapshot fixtures creates kb_chunk rows."""
    # Plan 01 will implement IngestPipeline and this test will go GREEN
    raise NotImplementedError("RED stub — implement in Plan 01 (KB-03)")


@pytest.mark.asyncio
async def test_pipeline_loads_exact_tables(db_pool, stub_embedder, clean_knowledge_db):
    """KB-03: policy_threshold and code_map rows loaded from POLICY-THRESHOLD-INDEX + CODE-MAP."""
    raise NotImplementedError("RED stub — implement in Plan 01 (KB-03)")
