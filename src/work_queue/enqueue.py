"""
enqueue.py — Idempotent enqueue into queue.ticket_queue (D-01, D-02).

Dedup guarantee: INSERT ON CONFLICT (idempotency_key) DO NOTHING.
The unique index on idempotency_key (created in migration 0001) is the single
dedup guard — no read-then-write race possible.

PII contract: caller MUST pass a pre-redacted payload. Full PII-redaction wiring
(Presidio) is done in plan 04; this module only persists whatever payload it receives.

Sentinel contract: caller MUST resolve inbound_msg_id to the REAL conversation id
before calling enqueue_ticket. Sentinel values (0, -1, etc.) are rejected.
"""

import json

import asyncpg

from src.work_queue.idempotency import compute_idempotency_key


async def enqueue_ticket(
    conn: asyncpg.Connection,
    ticket_id: int,
    inbound_msg_id: int,
    redacted_payload: dict,
) -> bool:
    """Insert a ticket into queue.ticket_queue, deduplicating at insert time.

    Uses INSERT ... ON CONFLICT (idempotency_key) DO NOTHING so that a duplicate
    inbound (same ticket_id + inbound_msg_id from both webhook and poller paths)
    results in exactly one row — satisfying REP-05 crit #2 (exactly-once).

    Args:
        conn: asyncpg Connection (caller owns transaction/lifecycle).
        ticket_id: Freshdesk ticket ID.
        inbound_msg_id: Freshdesk conversation ID of the latest incoming customer
            message. Must be the REAL id resolved by the caller ("resolve-then-enqueue"
            contract). Sentinel values are rejected (ValueError).
        redacted_payload: Ticket payload already redacted for PII by the caller.
            Persisted as-is into the JSONB payload column.

    Returns:
        True  — row was inserted (new ticket enqueued).
        False — row already existed (duplicate; ON CONFLICT DO NOTHING fired).

    Raises:
        ValueError: If inbound_msg_id is a sentinel value (<= 0).
    """
    if inbound_msg_id <= 0:
        raise ValueError(
            f"enqueue_ticket: inbound_msg_id must be a real conversation id (got {inbound_msg_id!r}). "
            "Resolve the latest incoming conversation BEFORE calling enqueue_ticket (D-02)."
        )

    key = compute_idempotency_key(ticket_id, inbound_msg_id)

    # asyncpg requires JSONB values to be passed as JSON strings
    payload_json = json.dumps(redacted_payload)

    result = await conn.execute(
        """
        INSERT INTO queue.ticket_queue
            (idempotency_key, ticket_id, inbound_msg_id, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        key,
        ticket_id,
        inbound_msg_id,
        payload_json,
    )
    # asyncpg returns "INSERT 0 1" when one row was inserted, "INSERT 0 0" on DO NOTHING
    return result == "INSERT 0 1"
