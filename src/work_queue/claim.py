"""
claim.py — SKIP LOCKED claim, token-checked finalization, stale claim recovery (D-01, D-11).

All SQL references the `queue` schema. All functions accept an asyncpg Connection;
callers own the connection/transaction lifecycle.

Concurrency model:
  - claim_one: FOR UPDATE SKIP LOCKED → two concurrent workers never claim the same row.
  - finalize_done / finalize_retry: token-checked (WHERE claim_token = $2) →
    a stale/crashed worker that wakes up cannot finalize a row already reclaimed.
  - recover_stale_claims: sweeps rows stuck in 'claimed' beyond the lease window
    back to 'pending' so they can be re-claimed (D-11).

PII rule (T-02-09): finalize_retry writes last_error but MUST NOT write raw customer
text. Callers pass a pre-redacted error string.
"""

from __future__ import annotations

from typing import Optional

import asyncpg


async def claim_one(
    conn: asyncpg.Connection,
    worker_id: str,
) -> Optional[asyncpg.Record]:
    """Atomically claim one pending row using FOR UPDATE SKIP LOCKED.

    Selects the earliest eligible row (next_attempt_at ASC, id ASC for deterministic
    FIFO tiebreaking — fix review #8) that is pending, due, and has retries remaining.
    Uses a CTE so the SELECT and UPDATE are a single atomic statement.

    Args:
        conn: asyncpg Connection. Should be inside a transaction for atomicity.
        worker_id: Identifier for the claiming worker (stored in claimed_by column).

    Returns:
        asyncpg.Record of the claimed row, or None if the queue is empty / all rows
        are locked by other workers or not yet due.
    """
    return await conn.fetchrow(
        """
        WITH to_claim AS (
            SELECT id
            FROM queue.ticket_queue
            WHERE status = 'pending'
              AND next_attempt_at <= NOW()
              AND attempts < max_attempts
            ORDER BY next_attempt_at ASC, id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE queue.ticket_queue
        SET
            status      = 'claimed',
            claimed_at  = NOW(),
            claimed_by  = $1,
            claim_token = gen_random_uuid(),
            updated_at  = NOW()
        FROM to_claim
        WHERE queue.ticket_queue.id = to_claim.id
        RETURNING queue.ticket_queue.*
        """,
        worker_id,
    )


async def finalize_done(
    conn: asyncpg.Connection,
    row_id: int,
    claim_token: str,
) -> bool:
    """Mark a claimed row as done, token-checked.

    The WHERE claim_token = $2 guard ensures a stale worker that woke up after
    the lease expired (and the row was reclaimed by another worker) cannot
    accidentally finalize the new worker's claim.

    Args:
        conn: asyncpg Connection.
        row_id: Primary key of the ticket_queue row.
        claim_token: UUID string issued at claim time.

    Returns:
        True  — row updated (token matched; row is now 'done').
        False — 0 rows updated (stale token; another worker owns this row).
    """
    result = await conn.execute(
        """
        UPDATE queue.ticket_queue
        SET
            status      = 'done',
            claim_token = NULL,
            updated_at  = NOW()
        WHERE id = $1
          AND claim_token = $2::uuid
        """,
        row_id,
        claim_token,
    )
    return result == "UPDATE 1"


async def finalize_retry(
    conn: asyncpg.Connection,
    row_id: int,
    claim_token: str,
    redacted_error: str,
    backoff_seconds: int,
) -> None:
    """Put a claimed row back to pending for retry with backoff, token-checked.

    Increments attempts, sets next_attempt_at = NOW() + backoff_seconds, and
    records the (pre-redacted) error string. If token doesn't match (stale worker),
    the UPDATE is a no-op — safe to ignore.

    Args:
        conn: asyncpg Connection.
        row_id: Primary key of the ticket_queue row.
        claim_token: UUID string issued at claim time.
        redacted_error: Error description with PII already removed (T-02-09).
            Caller MUST NOT pass raw customer text or exception tracebacks containing
            customer data.
        backoff_seconds: Seconds to delay before the row becomes eligible again.
    """
    await conn.execute(
        """
        UPDATE queue.ticket_queue
        SET
            status          = 'pending',
            claim_token     = NULL,
            attempts        = attempts + 1,
            next_attempt_at = NOW() + ($3 * INTERVAL '1 second'),
            last_error      = $4,
            last_error_at   = NOW(),
            updated_at      = NOW()
        WHERE id = $1
          AND claim_token = $2::uuid
        """,
        row_id,
        claim_token,
        backoff_seconds,
        redacted_error,
    )


async def recover_stale_claims(
    conn: asyncpg.Connection,
    lease_minutes: int = 10,
) -> int:
    """Return rows stuck in 'claimed' beyond the lease window back to 'pending'.

    A worker that crashes between claim and finalization leaves rows in 'claimed'
    indefinitely. This sweeper resets them so they can be re-claimed (D-11 / T-02-10).

    Args:
        conn: asyncpg Connection.
        lease_minutes: Rows claimed more than this many minutes ago are considered
            stale. Default 10 minutes.

    Returns:
        Number of rows recovered (reset to 'pending').
    """
    result = await conn.execute(
        """
        UPDATE queue.ticket_queue
        SET
            status      = 'pending',
            claim_token = NULL,
            claimed_by  = NULL,
            claimed_at  = NULL,
            updated_at  = NOW()
        WHERE status = 'claimed'
          AND claimed_at < NOW() - ($1 * INTERVAL '1 minute')
        """,
        lease_minutes,
    )
    # result is e.g. "UPDATE 3" — parse the count
    parts = result.split()
    return int(parts[1]) if len(parts) == 2 and parts[0] == "UPDATE" else 0
