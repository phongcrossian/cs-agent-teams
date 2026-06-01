"""Initial queue schema: ticket_queue, dead_letter, dry_run_log, poller_checkpoint.

Revision ID: 0001
Revises:
Create Date: 2026-06-01

Design note (fix review #6 — Phase-3 Postgres co-location):
  All queue tables live in schema `queue` (not `public`).
  Phase 3 (pgvector) will use schema `public` by default.
  Keeping queue tables in a separate schema makes the "one Postgres" decision
  (D-01) an intentional, reversible choice rather than an implicit lock-in.
  Sharing the pool vs. a dedicated pool / separate statement_timeout for pgvector
  is deferred to Phase 3 — schema `queue` keeps those options open.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Schema ────────────────────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS queue")

    # ── queue.ticket_queue ────────────────────────────────────────────────────
    # status domain: pending | claimed | done | suppressed | stale_inbound |
    #                dead_lettered
    #
    # sent_at / freshdesk_reply_id (fix review #1 — exactly-once crash-window):
    #   Worker sets sent_at = NOW() + freshdesk_reply_id = <id> BEFORE calling
    #   Freshdesk POST /reply.  On re-claim, if sent_at IS NOT NULL → SKIP POST,
    #   go straight to finalize_done.  Closes the crash-window between POST 200
    #   and finalize_done.
    op.execute(
        """
        CREATE TABLE queue.ticket_queue (
            id                  BIGSERIAL PRIMARY KEY,
            idempotency_key     TEXT        NOT NULL,
            ticket_id           INTEGER     NOT NULL,
            inbound_msg_id      INTEGER     NOT NULL,
            payload             JSONB       NOT NULL,
            status              TEXT        NOT NULL DEFAULT 'pending',
            claimed_at          TIMESTAMPTZ,
            claimed_by          TEXT,
            claim_token         UUID,
            attempts            INTEGER     NOT NULL DEFAULT 0,
            max_attempts        INTEGER     NOT NULL DEFAULT 5,
            next_attempt_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_error          TEXT,
            last_error_at       TIMESTAMPTZ,
            sent_at             TIMESTAMPTZ,
            freshdesk_reply_id  BIGINT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Dedup at insert — INSERT ON CONFLICT DO NOTHING uses this index (D-02)
    op.execute(
        """
        CREATE UNIQUE INDEX idx_ticket_queue_idempotency
            ON queue.ticket_queue (idempotency_key)
        """
    )

    # Worker scan index — partial index for fast pending-row lookup
    op.execute(
        """
        CREATE INDEX idx_ticket_queue_pending
            ON queue.ticket_queue (status, next_attempt_at)
            WHERE status = 'pending'
        """
    )

    # ── queue.dead_letter ─────────────────────────────────────────────────────
    # Rows moved here after max_attempts exhausted (D-10).
    # alerted flag tracks whether on-call alert has been emitted.
    op.execute(
        """
        CREATE TABLE queue.dead_letter (
            id              BIGSERIAL   PRIMARY KEY,
            idempotency_key TEXT        NOT NULL,
            ticket_id       INTEGER     NOT NULL,
            inbound_msg_id  INTEGER     NOT NULL,
            payload         JSONB       NOT NULL,
            attempts        INTEGER     NOT NULL,
            last_error      TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            alerted         BOOLEAN     NOT NULL DEFAULT FALSE
        )
        """
    )

    # ── queue.dry_run_log ─────────────────────────────────────────────────────
    # Persists would-be Freshdesk actions when send_mode = dry_run (D-05).
    # inbound_msg_id + action always included (02-04 doc-drift note).
    op.execute(
        """
        CREATE TABLE queue.dry_run_log (
            id              BIGSERIAL   PRIMARY KEY,
            ticket_id       INTEGER     NOT NULL,
            inbound_msg_id  INTEGER     NOT NULL,
            action          TEXT        NOT NULL,
            body            TEXT        NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ── queue.poller_checkpoint ───────────────────────────────────────────────
    # Single-row state for the reconciliation poller (fix review #3 — durable
    # last_since).  Poller persists last_since after every reconcile_once; on
    # restart it resumes from last_since − one safety-overlap window to avoid
    # missing events at boundaries.
    #
    # id CHECK (id=1) enforces single-row semantics.
    # Seed row inserted so poller can always UPDATE (never INSERT on first run).
    op.execute(
        """
        CREATE TABLE queue.poller_checkpoint (
            id          INTEGER     PRIMARY KEY CHECK (id = 1),
            last_since  TIMESTAMPTZ NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Seed the single row: start from NOW() - 1 hour as safety overlap
    op.execute(
        """
        INSERT INTO queue.poller_checkpoint (id, last_since, updated_at)
        VALUES (1, NOW() - INTERVAL '1 hour', NOW())
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS queue.poller_checkpoint")
    op.execute("DROP TABLE IF EXISTS queue.dry_run_log")
    op.execute("DROP TABLE IF EXISTS queue.dead_letter")
    op.execute("DROP INDEX IF EXISTS queue.idx_ticket_queue_pending")
    op.execute("DROP INDEX IF EXISTS queue.idx_ticket_queue_idempotency")
    op.execute("DROP TABLE IF EXISTS queue.ticket_queue")
    op.execute("DROP SCHEMA IF EXISTS queue")
