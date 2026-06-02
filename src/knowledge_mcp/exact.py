"""
Exact-lookup tools for the Knowledge MCP (D-10 anti-hallucination path).

These functions query exact tables (policy_threshold, code_map, template_library)
by primary key — no vector search, no LLM interpretation. This is the D-10
compliance layer: numeric and temporal thresholds are NEVER derived from prose
retrieval or LLM inference; they come from deterministic DB rows.

Pool injection: call set_pool(pool) before use (done by server.py on startup,
or by tests via the db_pool fixture).

Security: all SQL uses asyncpg $N parameterized queries (T-03-02-T).
"""

from __future__ import annotations

import logging

from src.knowledge_mcp.models import ThresholdResult, TemplateResult

logger = logging.getLogger(__name__)

# Module-level pool — set via set_pool() or passed directly
_pool = None


def set_pool(pool) -> None:
    """Set the asyncpg pool for exact-lookup queries.

    Called by tests via the db_pool fixture and by the server on startup.
    """
    global _pool
    _pool = pool


def _get_pool():
    """Return the current pool. Raises RuntimeError if not set."""
    if _pool is None:
        raise RuntimeError(
            "exact._pool is not set. Call set_pool(pool) before using exact lookups."
        )
    return _pool


async def lookup_threshold_row(threshold_id: str, pool=None) -> ThresholdResult:
    """Exact lookup of a numeric/temporal threshold by threshold_id.

    D-10: returns the exact stored string value — never LLM-derived.
    Raises KeyError if the threshold_id is not found.

    Args:
        threshold_id: e.g. "THR-03" (45-day warranty window).
        pool: optional asyncpg pool override (for testing; uses module _pool if None).

    Returns:
        ThresholdResult with value, source, conflict_id, override_resolution.

    Raises:
        KeyError: if threshold_id does not exist in knowledge.policy_threshold.
    """
    p = pool if pool is not None else _get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                threshold_id,
                label,
                value,
                source,
                authority_rank,
                conflict_id,
                snapshot_version
            FROM knowledge.policy_threshold
            WHERE threshold_id = $1
            """,
            threshold_id,
        )

    if row is None:
        raise KeyError(f"threshold_id not found: {threshold_id!r}")

    # Check for an override resolution for this threshold's conflict_id
    override_resolution: str | None = None
    if row["conflict_id"]:
        override_resolution = await _fetch_override_resolution(row["conflict_id"], pool=p)

    return ThresholdResult(
        threshold_id=row["threshold_id"],
        value=row["value"],
        source=row["source"],
        conflict_id=row["conflict_id"],
        override_resolution=override_resolution,
    )


async def _fetch_override_resolution(conflict_id: str, pool=None) -> str | None:
    """Return the resolved_value from policy_resolution for a given conflict_id, or None."""
    p = pool if pool is not None else _get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT resolved_value
            FROM knowledge.policy_resolution
            WHERE conflict_id = $1
            """,
            conflict_id,
        )
    return row["resolved_value"] if row else None


async def lookup_code_row(code: str, pool=None) -> dict:
    """Exact lookup of a workflow code -> action mapping.

    D-10: returns the exact stored action and template_code — no LLM.
    Raises KeyError if the code is not found.

    Args:
        code: e.g. "C1" (workflow step code from CODE-MAP.md).
        pool: optional asyncpg pool override (for testing; uses module _pool if None).

    Returns:
        dict with keys: code, action, template_code, source, snapshot_version.

    Raises:
        KeyError: if code does not exist in knowledge.code_map.
    """
    p = pool if pool is not None else _get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                code,
                action,
                template_code,
                source,
                snapshot_version
            FROM knowledge.code_map
            WHERE code = $1
            """,
            code,
        )

    if row is None:
        raise KeyError(f"code not found: {code!r}")

    return dict(row)


async def fetch_template_row(code: str, pool=None) -> TemplateResult:
    """Exact lookup of a reply template scaffold by code.

    D-11: keyed retrieval only — this is NOT a semantic search.
    Raises KeyError if the code is not found.

    Args:
        code: template code/scenario identifier (e.g. "B8").
        pool: optional asyncpg pool override (for testing; uses module _pool if None).

    Returns:
        TemplateResult with subject_template, body_template, source, authority_rank.

    Raises:
        KeyError: if code does not exist in knowledge.template_library.
    """
    p = pool if pool is not None else _get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                code,
                scenario,
                subject_template,
                body_template,
                source,
                authority_rank,
                snapshot_version
            FROM knowledge.template_library
            WHERE code = $1
            """,
            code,
        )

    if row is None:
        raise KeyError(f"template code not found: {code!r}")

    return TemplateResult(
        code=row["code"],
        scenario=row["scenario"],
        subject_template=row["subject_template"],
        body_template=row["body_template"],
        source=row["source"],
        authority_rank=int(row["authority_rank"]),
    )
