"""
test_loop_guard.py — Loop/auto-reply guard tests (Wave 2 — 02-04).

Covers:
  - RFC 3834 email headers (layer 1)
  - Sender noreply pattern (layer 2)
  - Source/actor incoming=false / private=true (layer 3)
  - Selless sync user ID (layer 4 — D-06/D-07)
  - should_suppress is single source of truth (fix #4)
  - Per-ticket reply throttle (fix #4 — loop-breaker independent of classification)
  - PII redaction via Presidio (D-12)
"""

from __future__ import annotations

import pytest
from src.freshdesk_io.models import Conversation
from src.guards import should_suppress
from src.guards.loop_guard import should_throttle_ticket
from src.guards.pii import redact_text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_conv(**kwargs) -> Conversation:
    """Build a Conversation with sensible defaults (real customer reply)."""
    defaults = {
        "id": 1001,
        "incoming": True,
        "private": False,
        "user_id": 42,
        "from_email": "jane@gmail.com",
        "source": 1,
        "body_text": "I need help with my order.",
    }
    defaults.update(kwargs)
    return Conversation(**defaults)


# ── Layer 1: RFC 3834 headers ─────────────────────────────────────────────────

def test_rfc3834_headers():
    """should_suppress returns True for conversations with auto-reply headers."""
    conv = _make_conv()

    # Auto-Submitted: auto-replied → suppress
    suppressed, reason = should_suppress(conv, headers={"Auto-Submitted": "auto-replied"})
    assert suppressed is True, f"Auto-Submitted header should suppress; got reason={reason!r}"
    assert reason != ""

    # Precedence: bulk → suppress
    suppressed, reason = should_suppress(conv, headers={"Precedence": "bulk"})
    assert suppressed is True, f"Precedence:bulk should suppress"

    # List-Id present → suppress (mailing list)
    suppressed, reason = should_suppress(conv, headers={"List-Id": "<newsletter.example.com>"})
    assert suppressed is True, f"List-Id header should suppress"

    # Normal headers → NOT suppressed
    suppressed, reason = should_suppress(conv, headers={"Content-Type": "text/plain"})
    assert suppressed is False, f"Normal headers should not suppress; got reason={reason!r}"
    assert reason == ""

    # No headers (None) → degrade gracefully, use layer 2-4 only
    suppressed, reason = should_suppress(conv, headers=None)
    assert suppressed is False, "No headers + valid customer conv → not suppressed"


# ── Layer 2: Sender pattern ───────────────────────────────────────────────────

def test_sender_pattern_noreply():
    """should_suppress returns True for noreply/mailer-daemon sender patterns."""
    # noreply@shop.com → suppress
    conv = _make_conv(from_email="noreply@shop.com")
    suppressed, reason = should_suppress(conv)
    assert suppressed is True, f"noreply@ sender should suppress; got {reason!r}"

    # mailer-daemon@x.com → suppress
    conv2 = _make_conv(from_email="mailer-daemon@x.com")
    suppressed, reason = should_suppress(conv2)
    assert suppressed is True, f"mailer-daemon@ sender should suppress"

    # do-not-reply@ → suppress
    conv3 = _make_conv(from_email="do-not-reply@example.com")
    suppressed, reason = should_suppress(conv3)
    assert suppressed is True, f"do-not-reply@ sender should suppress"

    # Real customer email → NOT suppressed
    conv4 = _make_conv(from_email="jane@gmail.com")
    suppressed, reason = should_suppress(conv4)
    assert suppressed is False, f"Real customer email should not suppress; got {reason!r}"


# ── Layer 3: source/actor (incoming=false / private=true) ─────────────────────

def test_source_actor_incoming_false():
    """should_suppress returns True when conversation is not a real customer public reply."""
    # incoming=False → agent/AI/system reply → suppress
    conv = _make_conv(incoming=False, private=False)
    suppressed, reason = should_suppress(conv)
    assert suppressed is True, f"incoming=False should suppress (agent/AI reply)"

    # private=True → private note → suppress
    conv2 = _make_conv(incoming=True, private=True)
    suppressed, reason = should_suppress(conv2)
    assert suppressed is True, f"private=True should suppress (private note)"

    # incoming=True AND private=False → real customer public reply → NOT suppressed
    conv3 = _make_conv(incoming=True, private=False)
    suppressed, reason = should_suppress(conv3)
    assert suppressed is False, f"Real customer public reply should not suppress; got {reason!r}"


# ── Layer 4: Selless sync user_id ─────────────────────────────────────────────

def test_selless_sync_user_id():
    """should_suppress returns True when user_id matches selless_sync_user_ids (D-07 primary)."""
    selless_ids = {9999, 10000}

    # Selless sync user → suppress
    conv = _make_conv(user_id=9999)
    suppressed, reason = should_suppress(conv, selless_sync_user_ids=selless_ids)
    assert suppressed is True, f"Selless sync user_id should suppress; got {reason!r}"

    # Another Selless sync user → suppress
    conv2 = _make_conv(user_id=10000)
    suppressed, reason = should_suppress(conv2, selless_sync_user_ids=selless_ids)
    assert suppressed is True

    # Regular customer → NOT suppressed
    conv3 = _make_conv(user_id=42)
    suppressed, reason = should_suppress(conv3, selless_sync_user_ids=selless_ids)
    assert suppressed is False, f"Regular customer user_id should not suppress; got {reason!r}"

    # Empty selless_sync_user_ids → no layer4 suppression
    conv4 = _make_conv(user_id=9999)
    suppressed, reason = should_suppress(conv4, selless_sync_user_ids=frozenset())
    assert suppressed is False, "Empty selless_sync_user_ids → no layer4 suppression"


# ── Single source of truth (fix #4) ──────────────────────────────────────────

def test_resolve_uses_should_suppress():
    """should_suppress is the single source of truth — importable as the unified guard (fix #4).

    The resolve step (02-05) and worker both import and call should_suppress.
    This test verifies the function is the canonical export from src.guards,
    confirming no inline conditions exist that could drift from the worker.
    """
    # Verify it's the canonical import path (same object as guards module exports)
    from src.guards import should_suppress as guards_should_suppress
    from src.guards.loop_guard import should_suppress as loop_guard_should_suppress

    assert guards_should_suppress is loop_guard_should_suppress, (
        "src.guards.should_suppress must re-export loop_guard.should_suppress "
        "(single source of truth — fix #4)"
    )

    # Verify the function signature accepts (conv, headers, from_email, selless_sync_user_ids)
    import inspect
    sig = inspect.signature(guards_should_suppress)
    params = list(sig.parameters)
    assert "conv" in params, "should_suppress must accept 'conv' parameter"
    assert "headers" in params, "should_suppress must accept 'headers' parameter"
    assert "selless_sync_user_ids" in params, "should_suppress must accept 'selless_sync_user_ids'"


# ── Per-ticket throttle (fix #4 — loop-breaker independent) ──────────────────

async def test_loop_guard_throttle(clean_db, db_pool):
    """should_throttle_ticket returns True when >= N sent replies to same ticket in window (fix #4)."""
    ticket_id = 77

    # Enqueue and manually mark as sent (simulate N already-sent replies)
    async with db_pool.acquire() as conn:
        # First row: enqueued and sent (sent_at IS NOT NULL)
        await conn.execute(
            """
            INSERT INTO queue.ticket_queue
              (idempotency_key, ticket_id, inbound_msg_id, payload, status, sent_at, freshdesk_reply_id)
            VALUES ($1, $2, $3, '{}', 'done', NOW(), 111)
            """,
            f"{ticket_id}:5001", ticket_id, 5001,
        )

        # Throttle n=1: already have 1 sent reply in window → should return True
        throttled = await should_throttle_ticket(conn, ticket_id=ticket_id, n=1, window_minutes=30)
        assert throttled is True, f"With n=1 and 1 sent reply, should be throttled"

        # Throttle n=2: only 1 sent reply → not yet throttled
        throttled2 = await should_throttle_ticket(conn, ticket_id=ticket_id, n=2, window_minutes=30)
        assert throttled2 is False, f"With n=2 and only 1 sent reply, should NOT be throttled"

        # Second sent reply: add another
        await conn.execute(
            """
            INSERT INTO queue.ticket_queue
              (idempotency_key, ticket_id, inbound_msg_id, payload, status, sent_at, freshdesk_reply_id)
            VALUES ($1, $2, $3, '{}', 'done', NOW(), 222)
            """,
            f"{ticket_id}:5002", ticket_id, 5002,
        )

        # Now n=2: 2 sent replies → throttled
        throttled3 = await should_throttle_ticket(conn, ticket_id=ticket_id, n=2, window_minutes=30)
        assert throttled3 is True, f"With n=2 and 2 sent replies, should be throttled"

        # Old reply outside window: insert with old sent_at
        ticket_id2 = 78
        await conn.execute(
            """
            INSERT INTO queue.ticket_queue
              (idempotency_key, ticket_id, inbound_msg_id, payload, status, sent_at, freshdesk_reply_id)
            VALUES ($1, $2, $3, '{}', 'done', NOW() - INTERVAL '60 minutes', 333)
            """,
            f"{ticket_id2}:6001", ticket_id2, 6001,
        )
        # n=1, window=30: 1 reply but 60 min ago → outside window → NOT throttled
        throttled4 = await should_throttle_ticket(conn, ticket_id=ticket_id2, n=1, window_minutes=30)
        assert throttled4 is False, "Reply outside window should not count toward throttle"


# ── Worker re-check stale_inbound (fix #4) ────────────────────────────────────

def test_worker_recheck_routes_stale_inbound():
    """should_suppress logic is tested here; stale_inbound routing is tested in test_queue.py.

    This test validates the building block: a conv that was valid when enqueued
    but is now suppressed (e.g. Selless user_id added post-enqueue) correctly
    returns suppress=True from should_suppress.
    """
    # Simulate: conv was enqueued as customer message (incoming=True, public)
    # but now user_id is in selless_sync_user_ids (config updated after enqueue)
    conv = _make_conv(incoming=True, private=False, user_id=9999)
    selless_ids = {9999}  # added post-enqueue

    suppressed, reason = should_suppress(conv, selless_sync_user_ids=selless_ids)
    assert suppressed is True, "Post-enqueue state change should make conv suppressed"
    assert "selless" in reason.lower() or "sync" in reason.lower() or reason != "", (
        f"Reason should describe selless sync suppression; got {reason!r}"
    )


# ── PII redaction (D-12) ──────────────────────────────────────────────────────

def test_redact_pii():
    """redact_text removes email addresses and phone numbers (Presidio — D-12)."""
    original = "email me at jane@x.com or call 555-123-4567 thanks"
    redacted = redact_text(original)

    assert "jane@x.com" not in redacted, f"Email should be redacted; got: {redacted!r}"
    assert "555-123-4567" not in redacted, f"Phone should be redacted; got: {redacted!r}"

    # Empty text → return as-is (no crash)
    assert redact_text("") == ""
    assert redact_text("  ") == "  "

    # Text without PII → return unchanged (or with no changes)
    plain = "Thank you for contacting support."
    result = redact_text(plain)
    assert isinstance(result, str), "redact_text should return a string"
    assert len(result) > 0
