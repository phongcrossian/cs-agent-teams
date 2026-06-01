"""
test_loop_guard.py — Loop/auto-reply guard tests (Wave 0 scaffold — RED-on-purpose).

Covers: RFC 3834 headers, sender noreply pattern, source/actor incoming=false,
Selless sync user ID (D-06/D-07), unified should_suppress (fix #4),
and stale_inbound re-check seam (fix #4).

All tests import successfully but fail with pytest.fail() until Wave 2 (02-04).
"""

import pytest
from src.guards import should_suppress


def test_rfc3834_headers():
    """should_suppress returns True for conversation with Auto-Submitted header."""
    pytest.fail("Wave 2 (02-04): implement RFC 3834 header detection in should_suppress")


def test_sender_pattern_noreply():
    """should_suppress returns True for noreply@/mailer-daemon@ sender patterns."""
    pytest.fail("Wave 2 (02-04): implement sender pattern check in should_suppress")


def test_source_actor_incoming_false():
    """should_suppress returns True when conversation incoming=False (agent/AI reply)."""
    pytest.fail("Wave 2 (02-04): implement incoming=False suppression in should_suppress")


def test_selless_sync_user_id():
    """should_suppress returns True when user_id matches SELLESS_SYNC_USER_IDS config (D-06/D-07)."""
    pytest.fail("Wave 2 (02-04): implement Selless sync user_id check in should_suppress")


def test_resolve_uses_should_suppress():
    """Resolve step calls the SAME should_suppress function — single source of truth (fix #4).

    Neither webhook resolver nor poller resolver duplicates suppression logic.
    Turns GREEN in 02-04 T1.
    """
    pytest.fail(
        "Wave 2 (02-04): verify resolve step uses should_suppress as single source of truth"
    )


def test_worker_recheck_routes_stale_inbound():
    """Worker re-check on claimed row: if should_suppress now True → status='stale_inbound' (fix #4).

    Must NOT silently suppress — must be observable as stale_inbound + alert.
    Turns GREEN in 02-04 T2.
    """
    pytest.fail(
        "Wave 2 (02-04): implement worker re-check — stale_inbound status (not silent suppressed)"
    )
