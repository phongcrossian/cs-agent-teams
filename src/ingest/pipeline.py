"""
Ingest pipeline — normalize → chunk → embed → content-hash upsert (KB-03 / KB-04).

Orchestrates:
  1. read_prose_sources() → normalize → chunk → embed_documents → upsert_chunk (kb_chunk)
  2. read_threshold_rows() → upsert policy_threshold (D-10 exact — no embeddings)
  3. read_code_map_rows() → upsert code_map (D-10 exact — no embeddings)
  4. read_templates() → upsert template_library (D-11 exact — no embeddings)

Idempotency (KB-04): keyed on content_hash = sha256(source + "\x00" + body).
  Unchanged chunks: ON CONFLICT → no-op (same hash, no re-embed needed).
  Changed prose: new hash → new row (or update existing via ON CONFLICT DO UPDATE).

Security:
  - All SQL uses asyncpg $N parameterized queries — never f-string SQL (T-03-01-T).
  - redact_text() called before any log line containing snapshot text (T-03-01-ID).

Usage:
    pipeline = IngestPipeline(pool)
    result = await pipeline.ingest_all(run_id="2026-06-02")
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def content_hash(source: str, body: str) -> str:
    """Compute idempotent dedup key for a prose chunk (KB-04 / D-16).

    sha256 of 'source\\x00body' — changes if either source path or body changes.
    """
    return hashlib.sha256(f"{source}\x00{body}".encode()).hexdigest()


class IngestPipeline:
    """Orchestrates the full snapshot ingest into knowledge.* tables.

    Args:
        pool: asyncpg connection pool with pgvector codec registered.
    """

    def __init__(self, pool) -> None:
        self._pool = pool

    async def ingest_all(self, run_id: str) -> dict[str, int]:
        """Run the full ingest pipeline.

        Args:
            run_id: Identifies this ingest run (e.g. timestamp or content version).

        Returns:
            Dict with counts: {"kb_chunk": N, "policy_threshold": N, "code_map": N, "template_library": N}
        """
        from src.ingest.sources import (
            read_code_map_rows,
            read_prose_sources,
            read_templates,
            read_threshold_rows,
        )
        from src.ingest.normalize import normalize_text
        from src.ingest.chunk import chunk_prose
        from src.knowledge_mcp.embeddings import embed_documents
        from src.guards.pii import redact_text

        counts: dict[str, int] = {
            "kb_chunk": 0,
            "policy_threshold": 0,
            "code_map": 0,
            "template_library": 0,
        }

        # ── Step 1: Prose → normalize → chunk → embed → upsert kb_chunk ──────

        prose_records = read_prose_sources()
        all_chunks: list[dict[str, Any]] = []

        for record in prose_records:
            normalized = normalize_text(record["body"])
            if not normalized:
                continue
            passages = chunk_prose(normalized, record["source"])
            for passage in passages:
                all_chunks.append(
                    {
                        "source": record["source"],
                        "source_type": record["source_type"],
                        "authority_rank": record["authority_rank"],
                        "recency_flag": record.get("recency_flag"),
                        "conflict_id": record.get("conflict_id"),
                        "body": passage["body"],
                    }
                )

        # Embed in batch (stub_embedder replaces this in tests with a sync lambda)
        if all_chunks:
            bodies = [c["body"] for c in all_chunks]
            logger.debug(
                "Embedding %d prose chunks (run_id=%s)",
                len(bodies),
                run_id,
            )
            import inspect
            result = embed_documents(bodies)
            if inspect.isawaitable(result):
                embeddings = await result
            else:
                embeddings = result

            async with self._pool.acquire() as conn:
                for chunk, embedding in zip(all_chunks, embeddings):
                    # T-03-01-ID: redact before logging
                    safe_preview = redact_text(chunk["body"][:80])
                    logger.debug("upserting chunk source=%s preview=%s", chunk["source"], safe_preview)
                    # D-14: carry conflict_id in metadata so assemble_citations()
                    # can populate Citation.conflict_id for apply_override() lookups.
                    # Never encode in snapshot_version (that field = run_id only).
                    chunk_metadata: dict = {"recency_flag": chunk["recency_flag"]}
                    if chunk.get("conflict_id"):
                        chunk_metadata["conflict_id"] = chunk["conflict_id"]
                    await self.upsert_chunk(
                        conn,
                        source=chunk["source"],
                        source_type=chunk["source_type"],
                        authority_rank=chunk["authority_rank"],
                        body=chunk["body"],
                        embedding=embedding,
                        metadata=chunk_metadata,
                        run_id=run_id,
                        recency_flag=chunk["recency_flag"],
                    )
                    counts["kb_chunk"] += 1

        # ── Step 2: Thresholds → upsert policy_threshold (D-10 exact) ────────

        threshold_rows = read_threshold_rows()
        async with self._pool.acquire() as conn:
            for row in threshold_rows:
                await self.upsert_threshold(conn, row, run_id)
                counts["policy_threshold"] += 1

        # ── Step 3: Code map → upsert code_map (D-10 exact) ──────────────────

        code_rows = read_code_map_rows()
        async with self._pool.acquire() as conn:
            for row in code_rows:
                await self.upsert_code_map(conn, row, run_id)
                counts["code_map"] += 1

        # ── Step 4: Templates → upsert template_library (D-11 exact) ─────────

        template_rows = read_templates()
        async with self._pool.acquire() as conn:
            for row in template_rows:
                await self.upsert_template(conn, row, run_id)
                counts["template_library"] += 1

        logger.info(
            "ingest_all complete run_id=%s kb_chunk=%d policy_threshold=%d "
            "code_map=%d template_library=%d",
            run_id,
            counts["kb_chunk"],
            counts["policy_threshold"],
            counts["code_map"],
            counts["template_library"],
        )
        return counts

    async def upsert_chunk(
        self,
        conn,
        source: str,
        source_type: str,
        authority_rank: int,
        body: str,
        embedding: list[float],
        metadata: dict[str, Any],
        run_id: str,
        recency_flag: str | None = None,
    ) -> None:
        """Idempotent upsert of a prose chunk into knowledge.kb_chunk.

        Keyed on content_hash(source, body).
        ON CONFLICT (content_hash) DO UPDATE updates embedding + snapshot_version.
        Uses $N parameterized query — never f-string SQL (T-03-01-T).
        """
        ch = content_hash(source, body)
        metadata_json = json.dumps(metadata)

        # asyncpg requires explicit ::jsonb cast for JSONB columns
        await conn.execute(
            """
            INSERT INTO knowledge.kb_chunk
                (content_hash, source, source_type, authority_rank, recency_flag,
                 body, embedding, metadata, snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9)
            ON CONFLICT (content_hash) DO UPDATE
                SET embedding         = EXCLUDED.embedding,
                    snapshot_version  = EXCLUDED.snapshot_version,
                    updated_at        = NOW()
            """,
            ch,
            source,
            source_type,
            authority_rank,
            recency_flag,
            body,
            embedding,
            metadata_json,
            run_id,
        )

    async def upsert_threshold(
        self,
        conn,
        row: dict[str, Any],
        run_id: str,
    ) -> None:
        """Upsert a policy threshold row (D-10 exact — never embedded)."""
        await conn.execute(
            """
            INSERT INTO knowledge.policy_threshold
                (threshold_id, label, value, source, authority_rank, conflict_id,
                 snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (threshold_id) DO UPDATE
                SET label            = EXCLUDED.label,
                    value            = EXCLUDED.value,
                    source           = EXCLUDED.source,
                    authority_rank   = EXCLUDED.authority_rank,
                    conflict_id      = EXCLUDED.conflict_id,
                    snapshot_version = EXCLUDED.snapshot_version
            """,
            row["threshold_id"],
            row["label"],
            row["value"],
            row["source"],
            row["authority_rank"],
            row.get("conflict_id"),
            run_id,
        )

    async def upsert_code_map(
        self,
        conn,
        row: dict[str, Any],
        run_id: str,
    ) -> None:
        """Upsert a code map row (D-10 exact — never embedded)."""
        await conn.execute(
            """
            INSERT INTO knowledge.code_map
                (code, action, template_code, source, snapshot_version)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO UPDATE
                SET action           = EXCLUDED.action,
                    template_code    = EXCLUDED.template_code,
                    source           = EXCLUDED.source,
                    snapshot_version = EXCLUDED.snapshot_version
            """,
            row["code"],
            row["action"],
            row.get("template_code"),
            row["source"],
            run_id,
        )

    async def upsert_template(
        self,
        conn,
        row: dict[str, Any],
        run_id: str,
    ) -> None:
        """Upsert a template row (D-11 exact — keyed lookup, never embedded)."""
        await conn.execute(
            """
            INSERT INTO knowledge.template_library
                (code, scenario, subject_template, body_template, source,
                 authority_rank, snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (code) DO UPDATE
                SET scenario          = EXCLUDED.scenario,
                    subject_template  = EXCLUDED.subject_template,
                    body_template     = EXCLUDED.body_template,
                    source            = EXCLUDED.source,
                    authority_rank    = EXCLUDED.authority_rank,
                    snapshot_version  = EXCLUDED.snapshot_version
            """,
            row["code"],
            row["scenario"],
            row["subject_template"],
            row["body_template"],
            row["source"],
            row["authority_rank"],
            run_id,
        )
