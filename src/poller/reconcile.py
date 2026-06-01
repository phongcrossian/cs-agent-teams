"""
reconcile.py — Reconciliation poller: updated_since scan → enqueue (auto-dedup) + durable checkpoint.

Design: RESOLVE-THEN-ENQUEUE (D-02, fix #4).
  Both webhook receiver and poller call resolve_inbound_and_enqueue() — ONE definition here.
  This means webhook and poller derive the SAME idempotency key from the SAME ticket state,
  so ON CONFLICT DO NOTHING is the sole dedup guard (no read-then-write race).

Poller window durability (fix #3, D-09):
  last_since is persisted to queue.poller_checkpoint (id=1) after every reconcile_once().
  On restart, load_checkpoint() reads it back with a safety overlap (subtract one poller
  window) to cover events that arrived during downtime without losing the window.

Should_suppress: SINGLE SOURCE OF TRUTH (fix #4).
  resolve_latest_inbound_msg_id() calls should_suppress() — never inlines incoming/private
  conditions. This prevents drift between the resolve step and the worker re-check.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from src.freshdesk_io.client import FreshdeskClient
from src.freshdesk_io.models import Conversation
from src.guards.loop_guard import should_suppress
from src.work_queue.enqueue import enqueue_ticket

logger = logging.getLogger(__name__)

# Safety overlap: subtract one poller window on resume to cover events during downtime.
_DEFAULT_SAFETY_WINDOW_SECONDS = 600  # 10 min (matches default poller_interval_seconds)


# ── Checkpoint (durable poller window — fix #3) ───────────────────────────────


async def load_checkpoint(
    conn: asyncpg.Connection,
    safety_overlap_seconds: int = _DEFAULT_SAFETY_WINDOW_SECONDS,
) -> datetime:
    """Load last_since from queue.poller_checkpoint (id=1).

    Returns last_since minus safety_overlap_seconds so that events arriving
    during downtime are not permanently missed (fix #3 — D-09 integrity).

    If no checkpoint row exists, returns NOW() - safety_window as a safe default.
    """
    row = await conn.fetchrow(
        "SELECT last_since FROM queue.poller_checkpoint WHERE id = 1"
    )
    if row is None:
        # First run — start one overlap window back from now
        return datetime.now(timezone.utc) - timedelta(seconds=safety_overlap_seconds)

    last_since: datetime = row["last_since"]
    # Apply safety overlap: resume from (last_since - one window) so we don't miss
    # events that arrived during downtime
    return last_since - timedelta(seconds=safety_overlap_seconds)


async def save_checkpoint(conn: asyncpg.Connection, last_since: datetime) -> None:
    """Persist last_since to queue.poller_checkpoint (UPSERT on id=1).

    Called after every successful reconcile_once() to ensure restart durability (fix #3).
    """
    await conn.execute(
        """
        INSERT INTO queue.poller_checkpoint (id, last_since, updated_at)
        VALUES (1, $1, NOW())
        ON CONFLICT (id) DO UPDATE
            SET last_since = EXCLUDED.last_since,
                updated_at = NOW()
        """,
        last_since,
    )
    logger.info("poller_checkpoint_saved", extra={"last_since": last_since.isoformat()})


# ── Shared resolve helper (SINGLE DEFINITION — used by webhook + poller) ──────


async def resolve_latest_inbound_msg_id(
    client: FreshdeskClient,
    ticket_id: int,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> int | None:
    """Resolve the latest inbound customer message id for a ticket.

    Steps:
      1. GET /api/v2/tickets/{ticket_id}/conversations
      2. For each conversation (latest last), call should_suppress() — SINGLE SOURCE
         OF TRUTH (fix #4). First non-suppressed conversation = the target inbound msg.
      3. Return conv.id (the real inbound_msg_id for the idempotency key).
         Return None if all conversations are suppressed / no inbound customer msg.

    NEVER returns a sentinel (0 or negative). Caller must not enqueue if None.
    """
    convs: list[Conversation] = await client.get_conversations(ticket_id)
    if not convs:
        logger.info(
            "resolve_no_conversations",
            extra={"ticket_id": ticket_id},
        )
        return None

    # Evaluate conversations in reverse order (latest first)
    for conv in reversed(convs):
        suppress, reason = should_suppress(
            conv,
            headers=None,  # API-fetched convs don't expose raw email headers (A4)
            from_email=conv.from_email,
            selless_sync_user_ids=selless_sync_user_ids,
        )
        if not suppress:
            logger.info(
                "resolve_inbound_found",
                extra={"ticket_id": ticket_id, "inbound_msg_id": conv.id},
            )
            return conv.id

    logger.info(
        "resolve_all_suppressed",
        extra={"ticket_id": ticket_id},
    )
    return None


async def resolve_inbound_and_enqueue(
    client: FreshdeskClient,
    conn: asyncpg.Connection,
    ticket_id: int,
    payload: dict,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> bool:
    """Resolve latest inbound message id → compute key → enqueue (dedup via ON CONFLICT).

    Returns True if a new row was inserted; False if suppressed or already queued.

    This is the SHARED helper used by both the webhook receiver and the poller.
    ONE definition here — webhook receiver imports it from this module.
    """
    inbound_msg_id = await resolve_latest_inbound_msg_id(
        client, ticket_id, selless_sync_user_ids
    )
    if inbound_msg_id is None:
        return False

    inserted = await enqueue_ticket(conn, ticket_id, inbound_msg_id, payload)
    if inserted:
        logger.info(
            "ticket_enqueued",
            extra={"ticket_id": ticket_id, "inbound_msg_id": inbound_msg_id},
        )
    else:
        logger.info(
            "ticket_deduped",
            extra={"ticket_id": ticket_id, "inbound_msg_id": inbound_msg_id},
        )
    return inserted


# ── reconcile_once ─────────────────────────────────────────────────────────────


async def reconcile_once(
    client: FreshdeskClient,
    pool: asyncpg.Pool,
    since: datetime,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> tuple[int, datetime]:
    """Scan tickets updated since `since`, resolve + enqueue each, persist checkpoint.

    Args:
        client: FreshdeskClient instance.
        pool: asyncpg pool.
        since: Start of the reconciliation window.
        selless_sync_user_ids: Used by should_suppress (D-07 layer 4).

    Returns:
        (enqueued_count, new_since) where new_since = max(updated_at) seen, or `since`
        if no tickets were found.
    """
    tickets = await client.list_updated_tickets(since)
    logger.info(
        "poller_reconcile_start",
        extra={"since": since.isoformat(), "ticket_count": len(tickets)},
    )

    enqueued = 0
    new_since = since

    async with pool.acquire() as conn:
        for ticket in tickets:
            # Track the furthest updated_at we've seen
            if ticket.updated_at > new_since:
                new_since = ticket.updated_at

            # Minimal payload: just ticket_id (webhook body doesn't have conversation body)
            payload: dict[str, Any] = {"ticket_id": ticket.id}

            inserted = await resolve_inbound_and_enqueue(
                client,
                conn,
                ticket.id,
                payload,
                selless_sync_user_ids,
            )
            if inserted:
                enqueued += 1

        # Persist checkpoint AFTER processing all tickets (fix #3 — D-09 integrity)
        await save_checkpoint(conn, new_since)

    logger.info(
        "poller_reconcile_done",
        extra={
            "enqueued": enqueued,
            "new_since": new_since.isoformat(),
            "ticket_count": len(tickets),
        },
    )
    return enqueued, new_since


# ── poller_loop ────────────────────────────────────────────────────────────────


async def poller_loop(
    client: FreshdeskClient,
    pool: asyncpg.Pool,
    interval_seconds: int = 600,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> None:
    """Run reconcile_once in a loop, resuming from durable checkpoint on startup.

    Cadence: interval_seconds (default 600s = 10 min; band 5–15 min per D-09).
    On startup: load checkpoint from DB (durable resume with safety overlap — fix #3).
    After each reconcile: advance since to new_since; sleep interval_seconds.
    """
    async with pool.acquire() as conn:
        since = await load_checkpoint(conn, safety_overlap_seconds=interval_seconds)

    logger.info(
        "poller_loop_start",
        extra={"since": since.isoformat(), "interval_seconds": interval_seconds},
    )

    while True:
        try:
            _enqueued, since = await reconcile_once(
                client, pool, since, selless_sync_user_ids
            )
        except Exception:
            logger.exception("poller_reconcile_error")

        await asyncio.sleep(interval_seconds)
