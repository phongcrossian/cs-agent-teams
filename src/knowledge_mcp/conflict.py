"""
D-13 conflict detection + D-14 override resolution for the Knowledge MCP.

Architecture rule: MCP NEVER self-arbitrates conflicts. It surfaces ALL
conflicting passages with conflict=True, and only reorders when a human-
populated policy_resolution row exists (D-14). Phase-4 escalation reacts.

Anti-pattern (per 03-RESEARCH.md): do NOT drop passages or pick a winner
without an explicit policy_resolution row.

Pool injection: call set_pool(pool) before use (done by server.py on startup,
or by tests via the db_pool fixture).

Security: override query uses asyncpg $N parameterized query (T-03-02-T,
T-03-02-ARB).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.knowledge_mcp.models import Citation

logger = logging.getLogger(__name__)

# Module-level pool — set via set_pool() or passed directly to apply_override()
_pool = None


def set_pool(pool) -> None:
    """Set the asyncpg pool for conflict/override queries.

    Called by tests via the db_pool fixture and by the server on startup.
    """
    global _pool
    _pool = pool


def _get_pool():
    """Return the current pool. Raises RuntimeError if not set."""
    if _pool is None:
        raise RuntimeError(
            "conflict._pool is not set. Call set_pool(pool) before using apply_override."
        )
    return _pool


@dataclass
class ConflictResult:
    """Result of conflict detection on a set of citations.

    has_conflict: True if any conflicting passages were detected.
    resolved: True if a policy_resolution override row was applied (D-14).
    """

    has_conflict: bool
    resolved: bool  # True only when apply_override() found a matching row


def _extract_conflict_ids(citations: list[Citation]) -> list[str]:
    """Extract conflict_ids from Citation.conflict_id fields.

    Citation.conflict_id is populated by assemble_citations() from
    kb_chunk.metadata["conflict_id"], which the ingest pipeline writes
    for prose chunks tied to a CONFLICT-INVENTORY CONTRA entry.

    snapshot_version is the ingest run_id only — conflict_ids are NEVER
    encoded there (that was dead code: the ingest pipeline never wrote the
    "conflict:<ID>:<run_id>" prefix that the old implementation expected).

    Returns list of unique conflict_ids found (may be empty).
    """
    conflict_ids = []
    seen: set[str] = set()
    for c in citations:
        cid = c.conflict_id
        if cid and cid not in seen:
            conflict_ids.append(cid)
            seen.add(cid)
    return conflict_ids


def _sources_conflict(citations: list[Citation]) -> bool:
    """Detect conflict by recency_flag and conflict_id metadata.

    Two citations conflict if:
    - At least one is stale AND at least one is current (stale vs. current).
    - Citations carry known conflict_ids from ingest metadata (Citation.conflict_id).
    """
    stale = [c for c in citations if c.recency_flag == "stale"]
    current = [c for c in citations if c.recency_flag != "stale"]

    # Stale alongside current = conflict (D-15 flagging + D-13 surfacing)
    if stale and current:
        return True

    # Known conflict_ids from ingest metadata (D-14)
    if _extract_conflict_ids(citations):
        return True

    return False


def apply_conflict_flag(citations: list[Citation]) -> ConflictResult:
    """D-13: detect conflicts in a citation set and return a ConflictResult.

    Conflict is signaled if:
    - Any citation has recency_flag="stale" alongside non-stale citations.
    - Citations carry known conflict_ids (CONTRA-*) in their snapshot_version.

    MCP NEVER drops citations. All are returned; the flag tells Phase-4 to escalate.

    Args:
        citations: list of Citation objects from assemble_citations().

    Returns:
        ConflictResult(has_conflict, resolved=False).
        resolved is always False here — apply_override() sets it to True.
    """
    if not citations:
        return ConflictResult(has_conflict=False, resolved=False)

    has_conflict = _sources_conflict(citations)
    return ConflictResult(has_conflict=has_conflict, resolved=False)


async def apply_override(
    citations: list[Citation], pool=None
) -> tuple[list[Citation], bool]:
    """D-14: reorder citations if a policy_resolution override row exists.

    Queries knowledge.policy_resolution for any conflict_ids present in the
    citation set. If a winning_source row is found, puts the citation from that
    source first. Does NOT drop any citations (D-13 surface-all rule).

    Args:
        citations: list of Citation objects (as assembled by assemble_citations).
        pool: optional asyncpg pool override (for testing; uses module _pool if None).

    Returns:
        Tuple of (reordered_citations, resolved_by_override).
        resolved_by_override=True only when a policy_resolution row applied.
    """
    if not citations:
        return citations, False

    # Collect conflict_ids from snapshot_version convention
    conflict_ids = _extract_conflict_ids(citations)

    if not conflict_ids:
        # No conflict IDs to look up — no override possible via this path
        # (stale-vs-current conflicts are flagged but not overridable without conflict_id)
        return citations, False

    try:
        p = pool if pool is not None else _get_pool()
        async with p.acquire() as conn:
            # Parameterized ANY($1::text[]) — safe against injection (T-03-02-T)
            rows = await conn.fetch(
                """
                SELECT conflict_id, winning_source, resolved_value
                FROM knowledge.policy_resolution
                WHERE conflict_id = ANY($1::text[])
                """,
                conflict_ids,
            )
    except Exception:
        logger.exception("Failed to query policy_resolution; returning unmodified citations")
        return citations, False

    if not rows:
        return citations, False

    # Take the first matching override row
    override_row = rows[0]
    winning_source = override_row["winning_source"]

    # Reorder: winning_source citations first, preserve relative order of rest
    # D-13: never drop any citation — all are surfaced
    winners = [c for c in citations if c.source == winning_source]
    others = [c for c in citations if c.source != winning_source]
    reordered = winners + others

    return reordered, True
