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

LIVE (fix #1 — send-intent transactional write):
  1. POST /api/v2/tickets/{id}/reply with body.
  2. Immediately after POST 200/201: UPDATE ticket_queue SET sent_at=NOW(),
     freshdesk_reply_id=result.id WHERE id=row_id AND claim_token=claim_token.
     This is the send-intent transactional write (REP-05).

Exactly-once is enforced by three layers (NOT by a Freshdesk-side body marker):
  - DB idempotency key (UNIQUE) — a duplicate inbound never enqueues twice (D-02);
  - process_queue_row skip-if-sent — row.sent_at IS NOT NULL ⇒ no POST (fix #1, the
    crash-after-post path proven on the D-03 sandbox demo);
  - the token-checked sent_at write below — a stale worker writes nothing.

D-03 FINDING (why there is no marker-scan pre-send guard):
  An earlier design embedded an HTML-comment marker (<!-- csbot:sent:{id} -->) in the
  reply body and scanned conversations for it to close the residual window between POST
  200 and the sent_at write. The D-03 live sandbox demo proved Freshdesk STRIPS HTML
  comments from reply bodies, so the marker never persists and the scan is dead weight.
  It was removed. The residual window (POST succeeds but the process dies before the
  sent_at write commits) is a documented, narrow Phase-2 limitation — see 02-06-SUMMARY.md.

PII contract (D-12 — enforced structurally, not by caller convention):
  The dry_run_log persistence boundary (_dry_run) ALWAYS passes body through
  redact_text() before the INSERT, so no raw customer-derived text can reach
  the dry_run_log.body column regardless of what the caller passed. This makes
  redaction a property of the persistence seam rather than a caller promise
  (BL-04). redact_text() is idempotent on already-redacted / canned text, so
  double-redaction is safe.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import SendMode
from src.freshdesk_io.client import FreshdeskClient
from src.freshdesk_io.models import ReplyResult
from src.guards.pii import redact_text

logger = logging.getLogger(__name__)


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
    dict {"dry_run": True}  — in DRY_RUN mode
    ReplyResult             — in LIVE mode, after successful post
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
    """Persist would-be reply to dry_run_log, no Freshdesk call.

    Redaction is enforced HERE at the persistence boundary (D-12 / BL-04):
    body is passed through redact_text() unconditionally so no raw customer
    PII can land in dry_run_log.body even if a future caller forgets to
    pre-redact. Idempotent on canned / already-redacted text.
    """
    redacted_body = redact_text(body)
    await conn.execute(
        """
        INSERT INTO queue.dry_run_log (ticket_id, inbound_msg_id, action, body)
        VALUES ($1, $2, $3, $4)
        """,
        ticket_id,
        inbound_msg_id,
        "reply",
        redacted_body,
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
    """Live send: post_reply → persist sent_at + freshdesk_reply_id (fix #1).

    No Freshdesk-side pre-send marker scan (D-03: Freshdesk strips HTML comments).
    Exactly-once relies on the idempotency key, process_queue_row's skip-if-sent,
    and the token-checked send-intent write below.
    """

    result: ReplyResult = await client.post_reply(ticket_id, body)

    # ── SEND-INTENT: persist sent_at + freshdesk_reply_id immediately (fix #1) ─
    # Token-checked UPDATE: only updates if claim_token still matches.
    # If a stale worker race were to occur, this silently writes nothing.
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
