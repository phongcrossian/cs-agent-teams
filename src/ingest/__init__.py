"""
src.ingest — snapshot ingest pipeline (KB-03 / KB-04).

This package reads the frozen Phase-1 snapshots, normalizes + chunks prose,
embeds via Voyage, and upserts into knowledge.* tables idempotently.

Public entrypoints:
  - src.ingest.pipeline.IngestPipeline  — orchestration class
  - src.ingest.cli                       — `python -m src.ingest.cli re-ingest`
"""
