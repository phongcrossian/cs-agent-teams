"""
send_reply — mode-aware send with send-intent transactional + pre-send guard (D-05, fix #1).

SEAM NOTE (D-05):
  This function is the Phase 6 kill-switch / Phase 7 staged-rollout seam.
  SendMode is a config-driven switch — not a development flag.  Phase 6 wires
  the kill-switch here; Phase 7 wraps it with rollout-percentage logic.
  Do NOT collapse the DRY_RUN / LIVE branches or remove the seam.

DRY_RUN (default — D-05):
  Persist the would-be action into queue.dry_run_log (ticket_id, inbound_msg_id,
  action='reply', body=redacted_body).  DOES NOT call Freshdesk.
  Schema: (id, ticket_id, inbound_msg_id, action, body, created_at) — 02-01.

LIVE (fix #1 — send-intent + pre-send guard):
  1. PRE-SEND GUARD: GET /conversations → scan for system marker stamped on prior
     outbound replies for this inbound_msg_id.  If found → SKIP (already sent).
     This closes the residual crash-window between POST 200 and sent_at write (T-02-23).
  2. POST /api/v2/tickets/{id}/reply with body + marker embedded.
  3. Immediately after POST 200/201: UPDATE ticket_queue SET sent_at=NOW(),
     freshdesk_reply_id=result.id WHERE id=row_id AND claim_token=claim_token.
     This is the send-intent transactional write (REP-05).

PII contract (D-12):
  Caller is responsible for redacting body before passing here.
  dry_run_log.body stores the redacted body.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import SendMode
from src.freshdesk_io.client import FreshdeskClient
from src.freshdesk_io.models import ReplyResult

logger = logging.getLogger(__name__)

# ── System marker ─────────────────────────────────────────────────────────────
# Embedded in every outbound reply body so the pre-send guard can detect
# "this inbound_msg_id was already replied to" across crashes.
# Format: <!-- csbot:sent:{inbound_msg_id} -->
# (HTML comment — not visible to end users in most email clients)
_MARKER_TEMPLATE = "<!-- csbot:sent:{inbound_msg_id} -->"


def _make_marker(inbound_msg_id: int) -> str:
    return _MARKER_TEMPLATE.format(inbound_msg_id=inbound_msg_id)


def _has_marker(body: str, inbound_msg_id: int) -> bool:
    """Return True if body contains the system marker for this inbound_msg_id."""
    return _make_marker(inbound_msg_id) in body


async def send_reply(
    client: FreshdeskClient,
    conn: Any,
    ticket_id: int,
    inbound_msg_id: int,
    body: str,
    mode: SendMode,
    row_id: int,
    claim_token: str,
) -> dict[str, Any] | ReplyResult:
    """Send or dry-run a reply for a queue row.

    Parameters
    ----------
    client          FreshdeskClient instance
    conn            asyncpg connection (caller holds; used for dry_run_log + sent_at write)
    ticket_id       Freshdesk ticket ID
    inbound_msg_id  Freshdesk conversation ID of the inbound message being replied to
    body            Reply body (caller must have already called redact_text() — D-12)
    mode            SendMode.DRY_RUN or SendMode.LIVE
    row_id          queue.ticket_queue row id (for send-intent UPDATE)
    claim_token     claim token string (for token-checked send-intent UPDATE — fix #1)

    Returns
    -------
    dict {"dry_run": True}         — in DRY_RUN mode
    dict {"skipped": "already_sent"} — in LIVE mode, pre-send guard fired
    ReplyResult                    — in LIVE mode, after successful post
    """
    if mode == SendMode.DRY_RUN:
        return await _dry_run(conn, ticket_id, inbound_msg_id, body)
    else:
        return await _live_send(client, conn, ticket_id, inbound_msg_id, body, row_id, claim_token)


# ── DRY_RUN path ──────────────────────────────────────────────────────────────

async def _dry_run(
    conn: Any,
    ticket_id: int,
    inbound_msg_id: int,
    body: str,
) -> dict[str, Any]:
    """Persist would-be reply to dry_run_log, no Freshdesk call."""
    await conn.execute(
        """
        INSERT INTO queue.dry_run_log (ticket_id, inbound_msg_id, action, body)
        VALUES ($1, $2, $3, $4)
        """,
        ticket_id,
        inbound_msg_id,
        "reply",
        body,
    )
    logger.info(
        "send_dry_run",
        extra={"ticket_id": ticket_id, "inbound_msg_id": inbound_msg_id},
    )
    return {"dry_run": True}


# ── LIVE path ─────────────────────────────────────────────────────────────────

async def _live_send(
    client: FreshdeskClient,
    conn: Any,
    ticket_id: int,
    inbound_msg_id: int,
    body: str,
    row_id: int,
    claim_token: str,
) -> dict[str, Any] | ReplyResult:
    """Live send: pre-send guard → post_reply → persist sent_at (fix #1)."""

    # ── PRE-SEND GUARD (fix #1 — close residual crash window) ────────────────
    # Scan existing conversations for the system marker of this inbound_msg_id.
    # If found, a previous run already POSTed the reply but crashed before
    # finalize_done.  Skip the POST entirely.
    conversations = await client.get_conversations(ticket_id)
    marker = _make_marker(inbound_msg_id)
    for conv in conversations:
        if not conv.incoming and _has_marker(conv.body_text or "", inbound_msg_id):
            logger.info(
                "pre_send_guard_already_sent",
                extra={"ticket_id": ticket_id, "inbound_msg_id": inbound_msg_id},
            )
            return {"skipped": "already_sent"}

    # ── POST reply (embed marker for future pre-send guard scans) ─────────────
    body_with_marker = body + "\n" + marker
    result: ReplyResult = await client.post_reply(ticket_id, body_with_marker)

    # ── SEND-INTENT: persist sent_at + freshdesk_reply_id immediately (fix #1) ─
    # Token-checked UPDATE: only updates if claim_token still matches.
    # If a stale worker race were to occur, this silently writes nothing —
    # the second worker's pre-send guard would catch the already-posted marker.
    await conn.execute(
        """
        UPDATE queue.ticket_queue
        SET sent_at = NOW(),
            freshdesk_reply_id = $1,
            updated_at = NOW()
        WHERE id = $2
          AND claim_token = $3::uuid
        """,
        result.id,
        row_id,
        claim_token,
    )
    logger.info(
        "send_live_success",
        extra={
            "ticket_id": ticket_id,
            "inbound_msg_id": inbound_msg_id,
            "freshdesk_reply_id": result.id,
        },
    )
    return result
