"""
Loop/auto-reply guard — D-06 four-signal layer.

SINGLE SOURCE OF TRUTH (fix #4):
  Both the resolve step (02-05) and the worker (02-04) call should_suppress().
  No inline incoming/private conditions exist elsewhere — only here.

Signal layers (applied in order; first match wins):
  Layer 1 — RFC 3834 email headers (Auto-Submitted, Precedence, List-*, etc.)
             Degrades gracefully when headers=None (A4 assumption).
  Layer 2 — Sender regex patterns (noreply@, mailer-daemon@, etc.)
  Layer 3 — Freshdesk source/actor: incoming=False → agent/AI/system;
             private=True → private note.  Only customer public replies pass.
  Layer 4 — Selless-sync user_id whitelist (D-07 primary path).
             is_selless_sync() is factored out so a marker/tag fallback
             can replace it if the sandbox checkpoint (Task 3) reveals
             that user_id is not distinguishable (deferred CONTEXT idea).

Per-ticket throttle (fix #4 — loop-breaker independent of header/sender classification):
  should_throttle_ticket(conn, ticket_id, n, window_minutes) — returns True if
  >= n sent replies for the same ticket exist within the window.  This fires even
  when RFC 3834 headers are inert (A4 scenario), providing a hard backstop for
  criterion #4.
"""

from __future__ import annotations

import re
from typing import Any

from src.freshdesk_io.models import Conversation

# ── Layer 1: RFC 3834 / auto-reply headers ────────────────────────────────────

_AUTO_SUBMITTED_SUPPRESS = frozenset(
    # Suppress unless value is exactly "no" (RFC 3834 §3.1.7)
    # We check != "no" in the validator below
)

_PRECEDENCE_SUPPRESS = frozenset({"bulk", "list", "junk", "auto_reply"})

_X_AUTO_RESPONSE_SUPPRESS_TOKENS = frozenset({"DR", "AUTOREPLY", "ALL"})

# Any List-* header signals a mailing list → never reply
_LIST_HEADER_PREFIXES = ("List-Id", "List-Unsubscribe", "List-Post", "List-Owner", "List-Archive")


def is_auto_reply_by_headers(headers: dict[str, str]) -> bool:
    """Return True if any RFC 3834 / mailing-list header indicates auto-reply.

    Called only when headers is not None (graceful degradation — A4).
    Header name matching is case-insensitive.
    """
    normalized = {k.lower(): v for k, v in headers.items()}

    # Auto-Submitted: anything except "no" indicates auto-generated
    auto_submitted = normalized.get("auto-submitted", "")
    if auto_submitted and auto_submitted.lower() != "no":
        return True

    # Precedence: bulk / list / junk / auto_reply
    precedence = normalized.get("precedence", "")
    if precedence.lower() in _PRECEDENCE_SUPPRESS:
        return True

    # X-Auto-Response-Suppress: contains DR, AUTOREPLY, or ALL
    xars = normalized.get("x-auto-response-suppress", "")
    if xars:
        upper = xars.upper()
        if any(tok in upper for tok in _X_AUTO_RESPONSE_SUPPRESS_TOKENS):
            return True

    # X-Loop, X-Autoreply — presence alone is enough
    if "x-loop" in normalized or "x-autoreply" in normalized:
        return True

    # List-* headers (mailing list signals)
    for prefix in _LIST_HEADER_PREFIXES:
        if prefix.lower() in normalized:
            return True

    # Empty Return-Path → bounce / system envelope
    return_path = normalized.get("return-path", "NOT_PRESENT")
    if return_path != "NOT_PRESENT" and return_path.strip() in ("", "<>"):
        return True

    return False


# ── Layer 2: Sender regex ─────────────────────────────────────────────────────

_NO_REPLY_PATTERN = re.compile(
    r"^(no[._-]?reply|noreply|mailer-daemon|postmaster|bounce[+-]|"
    r"do-not-reply|do_not_reply|return-path|auto-confirm|auto-notify)@",
    re.IGNORECASE,
)


def is_auto_reply_by_sender(from_email: str) -> bool:
    """Return True if the sender email matches known auto-reply / no-reply patterns."""
    return bool(_NO_REPLY_PATTERN.match(from_email.strip()))


# ── Layer 3: Freshdesk source/actor ──────────────────────────────────────────

def is_agent_or_system_message(conv: Conversation) -> bool:
    """Return True if conversation is NOT a customer public reply.

    incoming=False → agent/AI/system reply (Pitfall 3 scope: Phase 2 only processes
    incoming=True conversations; this is the strict correct scope per RESEARCH).
    private=True → private note (never visible to customer, not a reply trigger).
    """
    if not conv.incoming:
        return True  # agent reply, AI reply, system note
    if conv.private:
        return True  # private note
    return False


# ── Layer 4: Selless-sync user_id (D-07 primary path) ────────────────────────

def is_selless_sync(conv: Conversation, selless_sync_user_ids: frozenset[int]) -> bool:
    """Return True if conversation was created by a known Selless-sync integration user.

    D-07 primary path: user_id whitelist (LOW confidence — A2; verified at Task 3 checkpoint).

    This function is factored out (not inlined) so that a marker/tag fallback
    can replace it if the sandbox checkpoint confirms user_id is not distinguishable.
    The fallback (deferred CONTEXT idea) stamps a private marker on outbound replies
    and checks for it in layer 4 — no other code changes needed.
    """
    return conv.user_id in selless_sync_user_ids


# ── Unified entry point — SINGLE SOURCE OF TRUTH ─────────────────────────────

def should_suppress(
    conv: Conversation,
    headers: dict[str, str] | None = None,
    from_email: str | None = None,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> tuple[bool, str]:
    """Decide whether to suppress sending a reply to this conversation.

    Returns (suppress: bool, reason: str).
    reason is empty string when suppress=False.

    THIS IS THE SINGLE SOURCE OF TRUTH (fix #4):
    - resolve step (02-05) calls this before enqueue
    - worker (02-04) re-checks this after claim
    Neither duplicates incoming/private conditions inline.

    Layers applied in order; first suppression reason wins.
    """
    # Layer 1: RFC 3834 headers (only when headers provided — A4 graceful degrade)
    if headers is not None:
        if is_auto_reply_by_headers(headers):
            return True, "layer1:auto_reply_header"

    # Layer 2: Sender pattern
    email = from_email or conv.from_email
    if email and is_auto_reply_by_sender(email):
        return True, "layer2:noreply_sender"

    # Layer 3: source/actor (incoming=False or private=True)
    if is_agent_or_system_message(conv):
        return True, "layer3:agent_or_system"

    # Layer 4: Selless sync user_id whitelist (D-07 primary path)
    if selless_sync_user_ids and is_selless_sync(conv, frozenset(selless_sync_user_ids)):
        return True, "layer4:selless_sync"

    return False, ""


# ── Per-ticket reply throttle (fix #4 — independent loop-breaker) ─────────────

async def should_throttle_ticket(
    conn: Any,
    ticket_id: int,
    n: int,
    window_minutes: int,
) -> bool:
    """Return True if >= n sent replies exist for ticket_id within the last window_minutes.

    This is a loop-breaker INDEPENDENT of sender classification (fix #4).
    It protects criterion #4 even when RFC 3834 header layer is inert (A4 scenario).

    Uses queue.ticket_queue.sent_at column (02-01 schema) to count actual sends.
    """
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM queue.ticket_queue
        WHERE ticket_id = $1
          AND sent_at IS NOT NULL
          AND sent_at >= NOW() - ($2 || ' minutes')::interval
        """,
        ticket_id,
        str(window_minutes),
    )
    return (count or 0) >= n
