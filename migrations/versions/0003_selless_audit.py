"""Selless audit schema: audit.selless_audit.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-02

SEL-04 / D-07: every Selless MCP tool call is recorded here with PII-redacted fields.
Real PII passes to the drafter in-context; only the redacted form reaches this table
(via src/guards/pii.py Presidio wrapper — D-06).

Schema `audit` is separate from `queue` and `knowledge` for clear access-control
and to keep audit trail isolated from operational data.

`caller` field is reserved for future MCP client identity (e.g. Phase-4 orchestrator ID).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Schema ────────────────────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    # ── audit.selless_audit ───────────────────────────────────────────────────
    # PII-redacted audit log for every Selless MCP tool call (SEL-04 / D-07).
    #
    # input_key: PII-redacted order_id / customer email passed to the tool.
    # fields_returned: PII-redacted summary of which fields were in the response.
    # outcome: "ok" | "error" (error rows still logged for full audit trail).
    # caller: future field for Phase-4 orchestrator client identity.
    op.execute(
        """
        CREATE TABLE audit.selless_audit (
            id               BIGSERIAL   PRIMARY KEY,
            tool             TEXT        NOT NULL,
            input_key        TEXT        NOT NULL,
            fields_returned  TEXT        NOT NULL,
            latency_ms       FLOAT       NOT NULL,
            outcome          TEXT        NOT NULL,
            caller           TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Index for per-tool and time-range queries (audit trail queries)
    op.execute(
        "CREATE INDEX idx_selless_audit_tool ON audit.selless_audit (tool, created_at)"
    )


def downgrade() -> None:
    # Drop in reverse creation order
    op.execute("DROP INDEX IF EXISTS audit.idx_selless_audit_tool")
    op.execute("DROP TABLE IF EXISTS audit.selless_audit")
    op.execute("DROP SCHEMA IF EXISTS audit")
