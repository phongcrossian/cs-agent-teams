"""
ReplyMCP — the SINGLE customer-draft chokepoint (design §4a).

Architecture boundary:
  submit_reply(body, citations) is the ONLY tool allowed to emit a customer-facing
  draft. By routing all draft emission through this single MCP tool, the
  PreToolUse hook chain (grounding_check → pre_send_guard → escalation_gate) acts
  as a non-bypassable hard gate. The lead/subagents cannot route around it.

DRY_RUN mode (default):
  Mirrors src/work_queue/send.py _dry_run pattern: body is passed through
  redact_text() then persisted to queue.dry_run_log with action="reply".
  Nothing is posted to Freshdesk.

LIVE mode (future):
  Set SEND_MODE=live — reserved for Phase-2 integration bridge.

Launch: uv run python -m src.reply_mcp.server
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from fastmcp import FastMCP

from src.config import SendMode, settings
from src.guards.pii import redact_text

logger = logging.getLogger(__name__)

mcp = FastMCP(name="ReplyMCP", on_duplicate="error")


@mcp.tool()
async def submit_reply(body: str, citations: list[dict]) -> dict[str, Any]:
    """Submit a customer-facing reply draft (the ONLY path to emit a draft — §4a chokepoint).

    Args:
        body: The draft reply body text. Will be PII-redacted before persistence.
        citations: List of citation dicts (each with an "id" key, e.g. [{"id": "KB-1", ...}]).
                   Must be non-empty for grounding_check.py to pass.

    Returns:
        {"submitted": True, "dry_run": True}  in DRY_RUN mode
        {"submitted": True, "dry_run": False} in LIVE mode (future)

    Security: This tool is the SOLE draft-emission path. PreToolUse hooks
    (grounding_check → pre_send_guard → escalation_gate) run before every call;
    any hook returning non-zero blocks the tool and forces an escalate verdict (D-10).
    """
    is_dry_run = settings.dry_run or settings.send_mode == SendMode.DRY_RUN

    if is_dry_run:
        return await _dry_run(body, citations)
    else:
        # Live path: reserved for Phase-2 integration bridge.
        # For now, fall back to dry_run to avoid accidental Freshdesk posts.
        logger.warning("submit_reply: LIVE mode not yet implemented — falling back to DRY_RUN")
        return await _dry_run(body, citations)


async def _dry_run(body: str, citations: list[dict]) -> dict[str, Any]:
    """Persist would-be reply to queue.dry_run_log; never calls Freshdesk.

    Mirrors src/work_queue/send.py _dry_run (lines 93-121):
      redact_text() enforced at the persistence boundary (D-04 / §4a threat T-04-00-02).
    """
    redacted_body = redact_text(body)

    # Lazy DB import — avoid mandatory asyncpg dependency at import time (PoC).
    # In production the pool is injected via the Phase-2 queue infrastructure.
    try:
        import asyncpg  # noqa: F401

        db_url = settings.database_url
        conn = await asyncpg.connect(db_url)
        try:
            await conn.execute(
                """
                INSERT INTO queue.dry_run_log (ticket_id, inbound_msg_id, action, body)
                VALUES ($1, $2, $3, $4)
                """,
                0,         # ticket_id: 0 = agent-team PoC (no live ticket context yet)
                0,         # inbound_msg_id: 0 = same
                "reply",
                redacted_body,
            )
            logger.info("submit_reply_dry_run", extra={"body_len": len(redacted_body), "citations": len(citations)})
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001
        # In PoC / CI without DB, log and proceed — dry_run is best-effort persistence.
        logger.warning("submit_reply_dry_run: DB persist skipped (%s)", exc)

    return {"submitted": True, "dry_run": True}


def run() -> None:
    """Entry point for `uv run python -m src.reply_mcp.server`."""
    mcp.run()


if __name__ == "__main__":
    run()
