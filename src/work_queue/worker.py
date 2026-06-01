"""
Worker — process_queue_row + worker_loop (D-11 single sequential worker).

process_queue_row pipeline:
  1. SKIP-IF-SENT (fix #1):    row.sent_at IS NOT NULL → POST already succeeded;
                                skip straight to finalize_done (exactly-once across crash).
  2. Fetch conversations:       GET /conversations to get body + re-check loop-guard.
  3. Re-check should_suppress: SAME function as resolve step (single source of truth, fix #4).
                                If suppress → branch on context:
                                  - original enqueue was valid → status='stale_inbound' + alert (fix #4).
                                  - non-customer slipped through → status='suppressed' (D-08).
  4. Per-ticket throttle:       should_throttle_ticket → loop-breaker (fix #4).
  5. PII redact:                redact_text() on body BEFORE any log/persist (D-12).
  6. Canned reply body:         Phase 2 placeholder — Phase 4 replaces with real draft seam.
  7. send_reply:                mode-aware (D-05); send-intent persist (fix #1).
  8. finalize_done.

Error handling:
  - Transient (FreshdeskTransientError, httpx.TransportError) → finalize_retry with backoff.
  - Fatal (FreshdeskFatalError) → dead_letter_sink.to_dead_letter() (injected — fix #7).

Sequential loop (D-11):
  worker_loop(pool, client, settings, dead_letter_sink):
    claim_one → process_queue_row → sleep when idle.
    SKIP LOCKED design allows safe upgrade to N workers in a later phase.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.config import SendMode
from src.freshdesk_io.client import FreshdeskClient
from src.freshdesk_io.errors import FreshdeskFatalError, FreshdeskTransientError
from src.guards.loop_guard import should_suppress, should_throttle_ticket
from src.guards.pii import redact_text
from src.work_queue.claim import claim_one, finalize_done, finalize_retry
from src.work_queue.dead_letter_sink import DeadLetterSink, RetryOnlyDeadLetterSink
from src.work_queue.send import send_reply

logger = logging.getLogger(__name__)

# Backoff seconds for transient errors (simple fixed value for Wave 2; plan 06 can tune)
_TRANSIENT_BACKOFF_SECONDS = 60

# ── Stale-inbound alert helper ────────────────────────────────────────────────

def _emit_alert(event: str, **kwargs: Any) -> None:
    """Emit a structured alert log. Phase 6 wires this to a metric/alert sink."""
    logger.warning(event, extra=kwargs)


# ── Core row processor ────────────────────────────────────────────────────────

async def process_queue_row(
    pool: Any,
    client: FreshdeskClient,
    row: Any,
    settings: Any,
    dead_letter_sink: DeadLetterSink,
) -> None:
    """Process a single claimed queue row through the full post-path pipeline.

    Parameters
    ----------
    pool            asyncpg Pool (used for DB ops inside this function)
    client          FreshdeskClient (injected — testable with respx)
    row             asyncpg Record from claim_one — queue.ticket_queue row
    settings        Settings-like object with send_mode, selless_sync_user_ids,
                    per_ticket_reply_throttle_n, per_ticket_reply_throttle_window_minutes
    dead_letter_sink DeadLetterSink implementation (injected — fix #7)
    """
    row_id = row["id"]
    ticket_id = row["ticket_id"]
    inbound_msg_id = row["inbound_msg_id"]
    claim_token = str(row["claim_token"])

    async with pool.acquire() as conn:
        try:
            # ── Step 1: SKIP-IF-SENT (fix #1 — exactly-once across crash) ────────
            # If sent_at IS NOT NULL, a previous attempt already POSTed successfully
            # but crashed before finalize_done.  Skip the POST entirely.
            if row["sent_at"] is not None:
                logger.info(
                    "worker_skip_already_sent",
                    extra={"row_id": row_id, "ticket_id": ticket_id},
                )
                await finalize_done(conn, row_id=row_id, claim_token=claim_token)
                return

            # ── Step 2: Fetch conversations ───────────────────────────────────────
            # Always fetch from API — webhook payload does not contain conv body (Pitfall 1).
            conversations = await client.get_conversations(ticket_id)

            # Find the conversation matching inbound_msg_id (or latest incoming as fallback)
            target_conv = None
            for c in conversations:
                if c.id == inbound_msg_id:
                    target_conv = c
                    break
            if target_conv is None:
                # Fallback: pick latest incoming=True conversation
                incoming = [c for c in conversations if c.incoming and not c.private]
                target_conv = incoming[-1] if incoming else (conversations[-1] if conversations else None)

            # ── Step 3: Re-check should_suppress (SINGLE SOURCE OF TRUTH — fix #4) ─
            # Both resolve step (02-05) and worker call this same function.
            # No inline incoming/private conditions here — only should_suppress().
            selless_sync_ids = frozenset(getattr(settings, "selless_sync_user_ids", set()))

            if target_conv is not None:
                suppress, reason = should_suppress(
                    target_conv,
                    headers=None,  # raw headers not available at worker stage (A4)
                    from_email=target_conv.from_email,
                    selless_sync_user_ids=selless_sync_ids,
                )
            else:
                suppress, reason = False, ""

            if suppress:
                # Row was enqueued as valid inbound but state changed post-enqueue
                # (e.g. selless_sync_user_ids config updated, or rare resolve race) →
                # status='stale_inbound' + alert (observable — fix #4).
                # D-08 distinction: stale_inbound ≠ suppressed ≠ dead_letter.
                # Note: if a truly non-customer message slipped through resolve (not
                # supposed to happen per D-02 contract), we STILL use stale_inbound
                # so it is observable.  The key invariant is: NO SILENT DROP.
                _emit_alert(
                    "stale_inbound_dropped",
                    row_id=row_id,
                    ticket_id=ticket_id,
                    reason=reason,
                )
                # Determine: was this enqueued as genuinely valid (incoming=True customer)?
                # A message that is suppressed at worker time but was originally a
                # real incoming customer conv → stale_inbound (fix #4 observable).
                # A message that appears to be a system/agent conv → suppressed (D-08).
                if target_conv is not None and not target_conv.incoming:
                    # Non-customer conv: standard suppressed path (D-08)
                    await _mark_status(conn, row_id, "suppressed")
                else:
                    # Valid-looking conv now suppressed → stale_inbound (fix #4)
                    await _mark_status(conn, row_id, "stale_inbound")
                return

            # ── Step 4: Per-ticket throttle (fix #4 — loop-breaker independent) ───
            throttle_n = getattr(settings, "per_ticket_reply_throttle_n", 1)
            throttle_window = getattr(settings, "per_ticket_reply_throttle_window_minutes", 30)
            if await should_throttle_ticket(conn, ticket_id, throttle_n, throttle_window):
                _emit_alert(
                    "worker_throttled",
                    row_id=row_id,
                    ticket_id=ticket_id,
                    n=throttle_n,
                    window_minutes=throttle_window,
                )
                # Throttle: suppress send, mark stale_inbound (observable — fix #4)
                await _mark_status(conn, row_id, "stale_inbound")
                return

            # ── Step 5: PII redaction (D-12) — BEFORE any log or persist ─────────
            raw_body = target_conv.body_text if target_conv else ""
            redacted_body = redact_text(raw_body)

            # ── Step 6: Canned reply body (Phase 2 placeholder) ──────────────────
            # SEAM: Phase 4 replaces this with classify → retrieve → draft pipeline.
            # The variable name 'canned_body' signals this is intentional scaffolding.
            canned_body = (
                "<p>Thank you for contacting support. "
                "We have received your message and will respond shortly.</p>"
            )

            # ── Step 7: Send reply (mode-aware D-05 + send-intent fix #1) ────────
            await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body=canned_body,
                mode=settings.send_mode,
                row_id=row_id,
                claim_token=claim_token,
            )

            # ── Step 8: Finalize done ─────────────────────────────────────────────
            await finalize_done(conn, row_id=row_id, claim_token=claim_token)
            logger.info(
                "worker_row_done",
                extra={"row_id": row_id, "ticket_id": ticket_id},
            )

        except (FreshdeskFatalError,) as exc:
            # Fatal errors (404, 401, 403, 400, 409): no retry → dead-letter (fix #7)
            redacted_error = f"fatal: {type(exc).__name__} (no ticket/auth details logged)"
            logger.error(
                "worker_fatal_error",
                extra={"row_id": row_id, "ticket_id": ticket_id, "error_type": type(exc).__name__},
            )
            await dead_letter_sink.to_dead_letter(conn, row, redacted_error)
            # After sink (which may move the row), also finalize_retry so the row
            # doesn't stay 'claimed' if the sink is a no-op (RetryOnlyDeadLetterSink).
            await finalize_retry(
                conn,
                row_id=row_id,
                claim_token=claim_token,
                redacted_error=redacted_error,
                backoff_seconds=_TRANSIENT_BACKOFF_SECONDS,
            )

        except (FreshdeskTransientError, httpx.TransportError, Exception) as exc:
            # Transient / unexpected errors: schedule retry with backoff
            redacted_error = f"transient: {type(exc).__name__} (details redacted — D-12)"
            logger.warning(
                "worker_transient_error",
                extra={"row_id": row_id, "ticket_id": ticket_id, "error_type": type(exc).__name__},
            )
            await finalize_retry(
                conn,
                row_id=row_id,
                claim_token=claim_token,
                redacted_error=redacted_error,
                backoff_seconds=_TRANSIENT_BACKOFF_SECONDS,
            )


# ── Status helper ─────────────────────────────────────────────────────────────

async def _mark_status(conn: Any, row_id: int, status: str) -> None:
    """Update row status (suppressed / stale_inbound) and clear claim fields."""
    await conn.execute(
        """
        UPDATE queue.ticket_queue
        SET status     = $1,
            claim_token = NULL,
            claimed_at  = NULL,
            updated_at  = NOW()
        WHERE id = $2
        """,
        status,
        row_id,
    )


# ── Sequential worker loop (D-11) ─────────────────────────────────────────────

async def worker_loop(
    pool: Any,
    client: FreshdeskClient,
    settings: Any,
    dead_letter_sink: DeadLetterSink | None = None,
    idle_sleep_seconds: float = 5.0,
) -> None:
    """Sequential worker loop (D-11).

    Claims one row at a time, processes it, sleeps when queue is idle.
    SKIP LOCKED design is multi-worker safe — scale by launching N copies
    of this coroutine when needed (no code changes required).

    Parameters
    ----------
    pool                asyncpg Pool
    client              FreshdeskClient
    settings            Settings object (send_mode, selless_sync_user_ids, throttle config)
    dead_letter_sink    DeadLetterSink implementation (defaults to RetryOnlyDeadLetterSink)
    idle_sleep_seconds  Seconds to sleep when queue is empty (default 5s)
    """
    if dead_letter_sink is None:
        dead_letter_sink = RetryOnlyDeadLetterSink()

    worker_id = f"worker-{id(pool)}"

    while True:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await claim_one(conn, worker_id=worker_id)

        if row is None:
            await asyncio.sleep(idle_sleep_seconds)
            continue

        await process_queue_row(
            pool=pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=dead_letter_sink,
        )
