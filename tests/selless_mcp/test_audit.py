"""RED stub — SEL-04/D-07: every Selless MCP call writes a PII-redacted audit row.

Contract: after any tool call through the MCP server (even a failed one), one row is
written to audit.selless_audit with:
- tool: the tool name (e.g. "get_order_status")
- input_key: PII-redacted form of the order_id / email (not raw PII)
- fields_returned: PII-redacted summary of returned field names
- latency_ms: float > 0
- outcome: "ok" or "error"
The raw PII must NOT appear in the audit table (D-06 Presidio redaction).
"""

from __future__ import annotations

import pytest

# RED: these imports fail until Plan 03 creates src/selless_mcp/server.py + audit.py
from src.selless_mcp.server import get_order_status  # noqa: F401
from src.selless_mcp.audit import AuditMiddleware  # noqa: F401


@pytest.mark.asyncio
async def test_tool_call_writes_audit_row(db_pool, mock_selless_client, clean_knowledge_db):
    """SEL-04/D-07: calling get_order_status writes exactly one row to audit.selless_audit."""
    raise NotImplementedError("RED stub — implement in Plan 03 (SEL-04)")


@pytest.mark.asyncio
async def test_audit_row_pii_redacted(db_pool, mock_selless_client, clean_knowledge_db):
    """D-06: raw PII (email, order_id with PII) must not appear in audit table input_key column."""
    raise NotImplementedError("RED stub — implement in Plan 03 (D-06)")


@pytest.mark.asyncio
async def test_error_outcome_still_logged(db_pool, mock_selless_client, clean_knowledge_db):
    """SEL-04: failed tool calls (outcome='error') are still written to audit table."""
    raise NotImplementedError("RED stub — implement in Plan 03 (SEL-04)")
