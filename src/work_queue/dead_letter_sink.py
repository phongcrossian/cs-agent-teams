"""
DeadLetterSink protocol + default implementations (fix review #7).

Worker receives a DeadLetterSink via dependency injection — no stringly-typed
hook, no "if attribute exists" check.  Plan 06 (Wave 4) injects a real
PostgresDeadLetterSink.  Wave 2 uses RetryOnlyDeadLetterSink (no-op on fatal)
so fatal errors surface via finalize_retry until the real sink is wired.

Protocol:
    async def to_dead_letter(conn, row, error: str) -> None

Implementations shipped here:
  RetryOnlyDeadLetterSink — no-op (row stays in retry cycle until plan 06)
  RaisingDeadLetterSink   — raises; use in tests to assert fatal path is NOT hit
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DeadLetterSink(Protocol):
    """Protocol for dead-letter routing.

    Implementations must be async-callable with (conn, row, error).
    Plan 06 injects PostgresDeadLetterSink which inserts into queue.dead_letter.
    """

    async def to_dead_letter(
        self,
        conn: Any,
        row: Any,
        error: str,
    ) -> None:
        """Route a fatally-failed queue row to dead-letter storage.

        Parameters
        ----------
        conn:  asyncpg connection (already acquired by caller)
        row:   asyncpg Record — the queue.ticket_queue row that failed fatally
        error: pre-redacted error description (no PII — D-12)
        """
        ...  # pragma: no cover


class RetryOnlyDeadLetterSink:
    """Default Wave 2 dead-letter sink: no-op.

    Fatally-failed rows stay in the retry cycle (finalize_retry) until
    plan 06 (Wave 4) wires in PostgresDeadLetterSink.

    A warning log is emitted so the fatal path is observable even in Wave 2.
    """

    async def to_dead_letter(
        self,
        conn: Any,
        row: Any,
        error: str,
    ) -> None:
        """Log the fatal failure and return without moving the row.

        Plan 06 replaces this with an INSERT INTO queue.dead_letter.
        """
        ticket_id = row["ticket_id"] if hasattr(row, "__getitem__") else getattr(row, "ticket_id", "?")
        row_id = row["id"] if hasattr(row, "__getitem__") else getattr(row, "id", "?")
        logger.warning(
            "dead_letter_no_sink_wave2",
            extra={
                "row_id": row_id,
                "ticket_id": ticket_id,
                "error": error,
                "note": "RetryOnlyDeadLetterSink — wire PostgresDeadLetterSink in plan 06",
            },
        )


class RaisingDeadLetterSink:
    """Test-utility sink: raises AssertionError if dead-letter path is hit.

    Use in tests to assert that a code path must NOT reach dead-letter.

    Example:
        sink = RaisingDeadLetterSink()
        await process_queue_row(..., dead_letter_sink=sink)
        # If to_dead_letter() is called, the test fails with a clear message.
    """

    async def to_dead_letter(
        self,
        conn: Any,
        row: Any,
        error: str,
    ) -> None:
        row_id = row["id"] if hasattr(row, "__getitem__") else getattr(row, "id", "?")
        raise AssertionError(
            f"RaisingDeadLetterSink: unexpected dead-letter call for row_id={row_id!r}, error={error!r}"
        )
