"""
Hybrid semantic retrieval for the Knowledge RAG MCP (KB-05).

Implements Reciprocal Rank Fusion (RRF, k=60) over:
  1. Vector ANN search (pgvector HNSW, cosine distance)
  2. Full-text search (Postgres FTS via body_tsv)

Pool injection: call set_pool(pool) before use (done by server.py on startup,
or by tests via the db_pool fixture). The module-level _pool is used by default.

Security: all SQL uses asyncpg $N parameterized queries — NEVER f-string SQL (T-03-02-T).

D-12: authority_rank carried from kb_chunk row into Citation metadata.
D-15: recency_flag carried from kb_chunk row into Citation metadata.
"""

from __future__ import annotations

import logging
from typing import Any

import src.knowledge_mcp.embeddings as _embeddings_mod
from src.knowledge_mcp.models import Citation

logger = logging.getLogger(__name__)

# RRF constant — standard value from the Cormack/Clarke paper
_RRF_K = 60

# Module-level pool — set via set_pool() or injected in function calls
_pool = None


def set_pool(pool) -> None:
    """Set the asyncpg pool for retrieval queries.

    Called by tests via the db_pool fixture and by the server on startup.
    """
    global _pool
    _pool = pool


def _get_pool():
    """Return the current pool. Raises RuntimeError if not set."""
    if _pool is None:
        raise RuntimeError(
            "retrieval._pool is not set. Call set_pool(pool) before using hybrid_search."
        )
    return _pool


def _rrf_score(rank: int) -> float:
    """Reciprocal Rank Fusion score: 1 / (k + rank). Rank is 1-based."""
    return 1.0 / (_RRF_K + rank)


def _rrf_fuse(
    vec_rows: list[Any],
    fts_rows: list[Any],
    top_k: int,
) -> list[dict]:
    """Fuse vector ANN and FTS result lists using Reciprocal Rank Fusion.

    Each row contributes 1/(60+rank) to its chunk's total score.
    Returns top_k unique chunks ordered by descending fused score,
    carrying all metadata needed for Citation assembly.

    Args:
        vec_rows: asyncpg Records from the vector ANN query (ordered by distance).
        fts_rows: asyncpg Records from the FTS query (ordered by ts_rank DESC).
        top_k: number of candidates to return.

    Returns:
        list of dicts, each representing a kb_chunk row with a 'rrf_score' key.
    """
    scores: dict[int, float] = {}
    rows_by_id: dict[int, dict] = {}

    for rank, row in enumerate(vec_rows, start=1):
        chunk_id = row["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank)
        if chunk_id not in rows_by_id:
            rows_by_id[chunk_id] = dict(row)

    for rank, row in enumerate(fts_rows, start=1):
        chunk_id = row["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank)
        if chunk_id not in rows_by_id:
            rows_by_id[chunk_id] = dict(row)

    # Sort by fused score descending, take top_k
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    result = []
    for chunk_id, score in ranked:
        row = dict(rows_by_id[chunk_id])
        row["rrf_score"] = score
        result.append(row)
    return result


async def hybrid_search(query: str, top_k: int = 5, pool=None) -> list[dict]:
    """RRF-fused hybrid search: vector ANN (cosine) + FTS (plainto_tsquery).

    Steps:
      1. Embed query via embed_query() (Voyage voyage-3-large, input_type='query').
      2. Run vector ANN: ORDER BY embedding <=> $1::vector LIMIT 20.
      3. Run FTS: ts_rank(body_tsv, plainto_tsquery('english', $1)) LIMIT 20.
      4. Fuse with RRF(k=60) in Python; return top_k candidates.

    Security: parameterized queries only — no f-string SQL (T-03-02-T).

    Args:
        query: free-text query string from the Phase-4 caller.
        top_k: number of passages to return (default 5).
        pool: optional asyncpg pool override (for testing; uses module _pool if None).

    Returns:
        list of dicts with kb_chunk fields + 'rrf_score'.
    """
    p = pool if pool is not None else _get_pool()

    # Call embed_query via module reference so monkeypatch (stub_embedder fixture)
    # can replace it at test time. inspect.isawaitable bridges sync stub vs async
    # Voyage production path — mirrors the pattern in src/ingest/pipeline.py.
    import inspect
    _embed_result = _embeddings_mod.embed_query(query)
    q_vec = await _embed_result if inspect.isawaitable(_embed_result) else _embed_result

    async with p.acquire() as conn:
        # Set HNSW ef_search for better recall at query time
        await conn.execute("SET LOCAL hnsw.ef_search = 100")

        # 1. Vector ANN — cosine distance via pgvector <=> operator
        vec_rows = await conn.fetch(
            """
            SELECT
                id,
                content_hash,
                source,
                source_type,
                authority_rank,
                recency_flag,
                body,
                metadata,
                snapshot_version,
                embedding <=> $1::vector AS vec_dist
            FROM knowledge.kb_chunk
            ORDER BY vec_dist
            LIMIT 20
            """,
            q_vec,
        )

        # 2. FTS — plainto_tsquery to avoid injection via user query (T-03-02-T)
        fts_rows = await conn.fetch(
            """
            SELECT
                id,
                content_hash,
                source,
                source_type,
                authority_rank,
                recency_flag,
                body,
                metadata,
                snapshot_version,
                ts_rank(body_tsv, plainto_tsquery('english', $1)) AS fts_rank
            FROM knowledge.kb_chunk
            WHERE body_tsv @@ plainto_tsquery('english', $1)
            ORDER BY fts_rank DESC
            LIMIT 20
            """,
            query,
        )

    return _rrf_fuse(list(vec_rows), list(fts_rows), top_k=top_k)


def assemble_citations(rows: list[dict]) -> list[Citation]:
    """Convert raw kb_chunk rows (with rrf_score) into Citation objects.

    Carries D-12 authority_rank and D-15 recency_flag from the DB row into
    each Citation so Phase-4 can apply its own policy (e.g., downrank stale).

    Args:
        rows: list of dicts as returned by hybrid_search() (must have rrf_score).

    Returns:
        list[Citation] in the same order as input rows.
    """
    citations = []
    for row in rows:
        citation = Citation(
            text=row["body"],
            source=row["source"],
            source_type=row.get("source_type", "policy_prose"),
            authority_rank=int(row["authority_rank"]),
            recency_flag=row.get("recency_flag"),  # None if not stale
            snapshot_version=row["snapshot_version"],
            score=float(row.get("rrf_score", 0.0)),
        )
        citations.append(citation)
    return citations
