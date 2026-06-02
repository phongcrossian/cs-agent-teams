"""
AuditMiddleware — SEL-04 / D-06 / D-07.

Every Selless MCP tool call writes a PII-redacted audit row to audit.selless_audit.
Real PII passes to the drafter in the tool result; redaction happens only before
any log or DB write (D-06 Presidio redaction).

Schema (migration 0003):
  id, tool, input_key (redacted), fields_returned (redacted),
  latency_ms, outcome, caller, created_at.

Security:
  - input_key and fields_returned are always passed through redact_text() before INSERT
  - INSERT uses asyncpg $N parameterized query — NEVER f-string SQL (T-03-SQLI)
  - Pool reference is a lazy singleton (not recreated per call)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from src.guards.pii import redact_text  # D-06: reuse existing Presidio wrapper

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy pool singleton (set once from server.py startup or test injection)
# ---------------------------------------------------------------------------

_pool: "asyncpg.Pool | None" = None


def set_audit_pool(pool: "asyncpg.Pool") -> None:
    """Inject the asyncpg pool for audit writes.

    Called from server startup or test fixtures.
    """
    global _pool
    _pool = pool


def get_audit_pool() -> "asyncpg.Pool | None":
    """Return the current audit pool (None if not yet set)."""
    return _pool


# ---------------------------------------------------------------------------
# Result summarizer (fields_returned — redacted before persist)
# ---------------------------------------------------------------------------


def _summarize_result(result: Any) -> str:
    """Build a short summary of tool result field names for the audit row.

    Only field NAMES are recorded (not values), to minimize PII surface before
    Presidio redaction.  Values that could contain PII are not included.
    """
    if result is None:
        return ""
    if hasattr(result, "model_fields"):
        # Pydantic model — record field names only
        return f"fields:{','.join(result.model_fields.keys())}"
    if isinstance(result, dict):
        return f"keys:{','.join(str(k) for k in result.keys())}"
    return f"type:{type(result).__name__}"


# ---------------------------------------------------------------------------
# Parameterized audit row insert (no f-string SQL — T-03-SQLI)
# ---------------------------------------------------------------------------


async def _write_audit_row(
    *,
    tool: str,
    input_key: str,
    fields_returned: str,
    latency_ms: float,
    outcome: str,
    caller: str | None = None,
) -> None:
    """Insert a PII-redacted audit row into audit.selless_audit.

    Uses asyncpg $N parameterized query — NEVER f-string or .format() SQL.
    Silently skips if pool is not configured (test isolation without DB).
    """
    pool = get_audit_pool()
    if pool is None:
        logger.debug(
            "audit_pool_not_configured — skipping audit write for tool=%s", tool
        )
        return

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit.selless_audit
                    (tool, input_key, fields_returned, latency_ms, outcome, caller)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                tool,
                input_key,       # already redact_text()'d by caller
                fields_returned, # already redact_text()'d by caller
                latency_ms,
                outcome,
                caller,
            )
    except Exception:
        # Audit failures must never break the tool call itself
        logger.exception("audit_write_failed tool=%s outcome=%s", tool, outcome)


# ---------------------------------------------------------------------------
# AuditMiddleware
# ---------------------------------------------------------------------------


class AuditMiddleware(Middleware):
    """FastMCP middleware — writes a PII-redacted row to audit.selless_audit per tool call.

    Timing wraps the entire tool execution (including call_next).
    Outcome is "ok" on success, "error" on any exception.
    The audit write happens in the `finally` block so errors are also logged.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next,
    ) -> Any:
        tool = context.message.name
        raw_key = str(context.message.arguments or {})

        t0 = time.monotonic()
        outcome = "error"
        result = None

        try:
            result = await call_next(context)
            outcome = "ok"
            return result
        except Exception:
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000

            # D-06: redact PII before any DB write
            redacted_key = redact_text(raw_key)
            redacted_fields = redact_text(_summarize_result(result))

            await _write_audit_row(
                tool=tool,
                input_key=redacted_key,
                fields_returned=redacted_fields,
                latency_ms=latency_ms,
                outcome=outcome,
            )
