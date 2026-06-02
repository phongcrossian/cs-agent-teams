"""
AuditMiddleware — SEL-04 / D-06 / D-07.

Every Selless MCP tool call writes a PII-redacted audit row to audit.selless_audit.
Real PII passes to the drafter in the tool result; redaction happens only before
any log or DB write (D-06 Presidio redaction).

Fail-closed contract (D-07):
  If the audit pool IS configured and the INSERT fails, _write_audit_row raises
  SellessFatalError — the tool call does NOT return unaudited customer data.
  If the audit pool is NOT configured AND _audit_test_bypass is False (the default),
  _write_audit_row raises RuntimeError at startup time (pool must always be set
  in production — see assert_audit_pool_configured()).
  The _audit_test_bypass flag is set ONLY by test fixtures (set_audit_pool(None)
  with bypass=True) so test code that does not need DB audit writes can still call
  _impl_* functions.  Production server startup MUST call set_audit_pool(pool) with
  a real pool — assert_audit_pool_configured() is called from server startup to
  enforce this.

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
from src.selless_mcp.errors import SellessFatalError

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy pool singleton (set once from server.py startup or test injection)
# ---------------------------------------------------------------------------

_pool: "asyncpg.Pool | None" = None

# Test-only bypass flag: when True, a None pool silently skips audit writes
# instead of raising.  NEVER set to True in production code.
_audit_test_bypass: bool = False


def set_audit_pool(pool: "asyncpg.Pool | None", *, _test_bypass: bool = False) -> None:
    """Inject the asyncpg pool for audit writes.

    Args:
        pool: asyncpg connection pool.  Pass None only in tests that need
              to disable DB audit writes (also pass _test_bypass=True).
        _test_bypass: set True ONLY in test fixtures.  In production this
                      must always be False (default).

    Called from server startup (production) or test fixtures.
    Production startup must call set_audit_pool(real_pool) — audit writes
    are fail-closed when the pool is configured (D-07).
    """
    global _pool, _audit_test_bypass
    _pool = pool
    _audit_test_bypass = _test_bypass


def get_audit_pool() -> "asyncpg.Pool | None":
    """Return the current audit pool (None if not yet set)."""
    return _pool


def assert_audit_pool_configured() -> None:
    """Assert the audit pool is set.  Call from server startup.

    Raises RuntimeError if the pool is None and _audit_test_bypass is False,
    preventing production startup without a wired audit pool (D-07 contract).
    """
    if _pool is None and not _audit_test_bypass:
        raise RuntimeError(
            "Selless MCP audit pool is not configured — refusing to start. "
            "Call set_audit_pool(pool) from server startup before serving requests. "
            "(D-07: every tool call must write a durable audit row)"
        )


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

    Fail-closed contract (D-07):
      - If pool is None AND _audit_test_bypass=True: skip silently (test isolation only).
      - If pool is None AND _audit_test_bypass=False: raise RuntimeError — production
        misconfiguration; refusing to serve unaudited data is the correct behavior.
      - If pool is set but INSERT fails: raise SellessFatalError — the caller (tool
        handler) must NOT return unaudited customer data.

    Uses asyncpg $N parameterized query — NEVER f-string or .format() SQL.
    """
    pool = get_audit_pool()
    if pool is None:
        if _audit_test_bypass:
            logger.debug(
                "audit_pool_not_configured (test bypass active) — "
                "skipping audit write for tool=%s", tool
            )
            return
        # Production path: pool must always be set.  Raise loudly.
        raise RuntimeError(
            f"audit pool not configured — refusing to serve Selless data unaudited "
            f"(D-07). tool={tool!r}. "
            "Call set_audit_pool(pool) from server startup."
        )

    # Pool is set — INSERT must succeed.  Any failure is fatal (fail-closed).
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
        # INSERT succeeded — no exception means the audit row is durable.


# ---------------------------------------------------------------------------
# AuditMiddleware
# ---------------------------------------------------------------------------


class AuditMiddleware(Middleware):
    """FastMCP middleware — writes a PII-redacted row to audit.selless_audit per tool call.

    Timing wraps the entire tool execution (including call_next).
    Outcome is "ok" on success, "error" on any exception.
    The audit write happens in the `finally` block so errors are also audited.

    Fail-closed (D-07): if _write_audit_row raises (pool misconfigured OR INSERT
    failure), the exception propagates — the tool response is NOT returned to the
    caller without a durable audit row.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next,
    ) -> Any:
        tool = context.message.name
        raw_key = str(context.message.arguments or {})

        # WR-01: extract caller identity from MCP context if available.
        # In Phase 3 the transport metadata may not carry a client identity;
        # record None for now and let Phase 4 wire it when the orchestrator
        # client is known.  The column is nullable and reserved for forensic use.
        caller: str | None = None
        try:
            # FastMCP MiddlewareContext may expose client_id in future versions.
            # Access it defensively so this does not break on SDK upgrades.
            caller = getattr(context, "client_id", None)
        except Exception:
            pass

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

            # Fail-closed: if _write_audit_row raises, the exception propagates
            # out of the finally block, overriding the original result/exception.
            # This is intentional — an unaudited tool response must not be served.
            await _write_audit_row(
                tool=tool,
                input_key=redacted_key,
                fields_returned=redacted_fields,
                latency_ms=latency_ms,
                outcome=outcome,
                caller=caller,
            )
