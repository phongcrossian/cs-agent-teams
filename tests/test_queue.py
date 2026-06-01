"""
test_queue.py — Queue core tests (Wave 0 scaffold — RED-on-purpose).

Covers: enqueue dedup, idempotency, SKIP LOCKED claim, dead-letter exhaustion,
stale claim recovery, worker crash-after-post exactly-once (fix #1),
per-ticket throttle (fix #4), sweep exhausted unlettered (fix #9),
stale_inbound observable (fix #4).

All tests import successfully but fail with pytest.fail() until Wave 1/2 (02-03/02-04).
"""

import pytest
from src.work_queue import enqueue, claim


def test_enqueue_dedup(clean_db, db_pool):
    """Enqueueing same idempotency_key twice → second insert is silently ignored (ON CONFLICT DO NOTHING)."""
    pytest.fail("Wave 1 (02-03): implement enqueue with ON CONFLICT DO NOTHING dedup")


def test_idempotency(clean_db, db_pool, respx_mock):
    """Worker processing same ticket twice does NOT send two Freshdesk replies (REP-05 crit #2)."""
    pytest.fail("Wave 1 (02-03): implement idempotency — retry does not double-send")


def test_skip_locked_claim(clean_db, db_pool):
    """Two concurrent workers claim different rows (SKIP LOCKED — no collision)."""
    pytest.fail("Wave 1 (02-03): implement SKIP LOCKED claim")


def test_dead_letter_on_exhaustion(clean_db, db_pool):
    """Row with attempts >= max_attempts is moved to queue.dead_letter on next failure."""
    pytest.fail("Wave 1 (02-03): implement dead-letter on exhaustion")


def test_stale_claim_recovery(clean_db, db_pool):
    """Rows stuck in 'claimed' status > timeout are recovered back to 'pending'."""
    pytest.fail("Wave 1 (02-03): implement stale claim recovery")


def test_worker_crash_after_post_does_not_resend(clean_db, db_pool, respx_mock):
    """MANDATORY RED (fix #1): Worker crashes between POST 200 and finalize_done.

    Re-claim of the same row must NOT post a second reply to Freshdesk.
    respx POST call count must equal exactly 1 after recovery + re-claim.

    Turns GREEN in 02-04 T2 (send-intent: sent_at IS NOT NULL → skip POST).
    """
    pytest.fail(
        "Wave 2 (02-04): implement send-intent (sent_at) — crash-after-post no resend"
    )


def test_loop_guard_throttle(clean_db, db_pool):
    """Per-ticket reply throttle: must not send more than N replies to same ticket in T minutes (fix #4)."""
    pytest.fail("Wave 2 (02-04): implement per-ticket reply throttle in loop-guard")


def test_sweep_exhausted_unlettered(clean_db, db_pool):
    """Sweeper moves rows with status='pending' AND attempts>=max_attempts to dead_letter (fix #9)."""
    pytest.fail("Wave 4 (02-06): implement sweeper for exhausted unlettered rows")


def test_worker_recheck_routes_stale_inbound(clean_db, db_pool):
    """Worker re-checks should_suppress on claimed row; if now suppressed → status='stale_inbound' + alert (fix #4)."""
    pytest.fail(
        "Wave 2 (02-04): implement worker re-check → stale_inbound status, NOT silent suppressed"
    )
