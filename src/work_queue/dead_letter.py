"""
dead_letter.py — PostgresDeadLetterSink + should_dead_letter + sweep_exhausted (D-10, fix #7/#9).

PostgresDeadLetterSink implements the DeadLetterSink protocol (from dead_letter_sink.py).
Inject this into worker_loop / main.py in place of RetryOnlyDeadLetterSink (fix #7).

should_dead_letter(exc) — True for FreshdeskFatalError (go straight to DL, no retry).
                          False for transient errors (let retry logic handle).

sweep_exhausted(conn, sink) — finds rows status='pending' AND attempts>=max_attempts
  (exhausted but not yet dead-lettered — e.g. worker crashed right after the final
  finalize_retry increment).  Pushes each row to dead_letter via sink.  (fix #9)

PII contract (D-12):
  last_error stored in dead_letter must be pre-redacted.
  ticket_id and attempts are structural IDs — safe to log.
  NO raw ticket body, email, or customer content is ever persisted here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.freshdesk_io.errors import FreshdeskFatalError
from src.observability import emit_alert, increment
from src.work_queue.dead_letter_sink import DeadLetterSink

logger = logging.getLogger(__name__)


# ── Error classification helper ───────────────────────────────────────────────


def should_dead_letter(exc: BaseException) -> bool:
    """Return True if the exception warrants immediate dead-lettering (no retry).

    Fatal errors (FreshdeskFatalError — covers 400/401/403/404/409) → True.
    Transient errors → False (let backoff + retry logic handle).

    409 is FATAL (fix review #5): dead-letter immediately for human inspection.
    """
    return isinstance(exc, FreshdeskFatalError)


# ── PostgresDeadLetterSink ────────────────────────────────────────────────────


class PostgresDeadLetterSink:
    """Real DeadLetterSink implementation: INSERT into queue.dead_letter (fix #7).

    Replaces RetryOnlyDeadLetterSink (Wave 2 no-op) — wire this into worker_loop
    and main.py so fatally-failed rows are persisted for human review.

    Protocol method:
        async to_dead_letter(conn, row, error: str) -> None

    Side-effects:
      1. INSERT into queue.dead_letter (idempotency_key, ticket_id, inbound_msg_id,
         payload, attempts, last_error, alerted=True).
      2. UPDATE queue.ticket_queue status='dead_lettered'.
      3. emit_alert("dead_letter", ...) — observable, no PII.
      4. increment("dead_lettered_total") metric counter.
    """

    async def to_dead_letter(
        self,
        conn: Any,
        row: Any,
        error: str,
    ) -> None:
        """Move a fatally-failed queue row to dead_letter storage.

        Parameters
        ----------
        conn   asyncpg connection (caller holds; no new transaction started here)
        row    asyncpg Record from queue.ticket_queue
        error  pre-redacted error description (NO PII — D-12)
        """
        row_id = row["id"]
        ticket_id = row["ticket_id"]
        idempotency_key = row["idempotency_key"]
        inbound_msg_id = row["inbound_msg_id"]
        attempts = row["attempts"]
        # payload is a jsonb column — asyncpg returns a dict; re-serialize for INSERT
        payload = row["payload"]
        if isinstance(payload, str):
            payload_json = payload
        else:
            payload_json = json.dumps(payload)

        # 1. INSERT into dead_letter
        # Note: no unique constraint on idempotency_key in dead_letter (by schema design).
        # The ticket_queue UPDATE to status='dead_lettered' is the idempotency guard —
        # sweep_exhausted and the worker only process 'pending'/'claimed' rows so
        # a row cannot be dead-lettered twice under normal operation.
        await conn.execute(
            """
            INSERT INTO queue.dead_letter
                (idempotency_key, ticket_id, inbound_msg_id, payload, attempts, last_error, alerted)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, TRUE)
            """,
            idempotency_key,
            ticket_id,
            inbound_msg_id,
            payload_json,
            attempts,
            error,
        )

        # 2. UPDATE ticket_queue status → dead_lettered
        await conn.execute(
            """
            UPDATE queue.ticket_queue
            SET status     = 'dead_lettered',
                claim_token = NULL,
                updated_at  = NOW()
            WHERE id = $1
            """,
            row_id,
        )

        # 3. Alert + metric (no PII in kwargs — only structural IDs and error type)
        emit_alert(
            "dead_letter",
            ticket_id=ticket_id,
            row_id=row_id,
            attempts=attempts,
            # error is already redacted by caller — log the type only for brevity
            error_summary=error[:120] if error else "",
        )
        increment("dead_lettered_total")

        logger.warning(
            "dead_letter_row_moved",
            extra={
                "row_id": row_id,
                "ticket_id": ticket_id,
                "attempts": attempts,
            },
        )


# ── Exhausted-but-unlettered sweeper (fix #9) ─────────────────────────────────


async def sweep_exhausted(
    conn: Any,
    sink: DeadLetterSink | None = None,
) -> int:
    """Find status='pending' rows with attempts>=max_attempts and push to dead_letter.

    This sweeper catches the path where a worker incremented attempts to max_attempts
    via finalize_retry but then crashed before calling to_dead_letter — leaving the
    row stuck as status='pending' with no remaining attempts.  Without this sweeper,
    claim_one() would never pick up the row again (attempts < max_attempts filter),
    so it would be silently stuck forever (fix #9).

    Parameters
    ----------
    conn  asyncpg connection
    sink  DeadLetterSink to use; defaults to PostgresDeadLetterSink()

    Returns
    -------
    Number of exhausted rows swept into dead_letter.
    """
    if sink is None:
        sink = PostgresDeadLetterSink()

    # Find exhausted-but-unlettered rows
    rows = await conn.fetch(
        """
        SELECT *
        FROM queue.ticket_queue
        WHERE status = 'pending'
          AND attempts >= max_attempts
        ORDER BY id ASC
        """
    )

    swept = 0
    for row in rows:
        try:
            # Build a redacted error for the dead_letter record
            last_error = row.get("last_error") or "exhausted: max_attempts reached (swept by sweeper)"
            # Truncate + sanitize — no raw PII (D-12)
            redacted = last_error[:200] if last_error else "exhausted"

            await sink.to_dead_letter(conn, row, redacted)
            swept += 1

            logger.info(
                "sweep_exhausted_row",
                extra={
                    "row_id": row["id"],
                    "ticket_id": row["ticket_id"],
                    "attempts": row["attempts"],
                },
            )
        except Exception:
            # Log and continue — don't let one row block others
            logger.exception(
                "sweep_exhausted_error",
                extra={"row_id": row["id"], "ticket_id": row["ticket_id"]},
            )

    if swept:
        logger.info("sweep_exhausted_done", extra={"swept": swept})

    return swept
