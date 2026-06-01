"""
test_poller.py — Reconciliation poller tests (Wave 0 scaffold — RED-on-purpose).

Covers: poller enqueues updated tickets, dedup with webhook path,
window advance (D-09), and durable checkpoint across restart (fix #3).

All tests import successfully but fail with pytest.fail() until Wave 3 (02-05).
"""

import pytest
from src.poller import reconcile_once, load_checkpoint, save_checkpoint


def test_poller_enqueues_updated(clean_db, db_pool, respx_mock):
    """reconcile_once fetches updated tickets and enqueues new ones."""
    pytest.fail("Wave 3 (02-05): implement reconcile_once → enqueue updated tickets")


def test_poller_dedup_with_webhook(clean_db, db_pool, respx_mock):
    """Poller and webhook path produce the same idempotency_key → exactly-once enqueue."""
    pytest.fail("Wave 3 (02-05): implement poller dedup — same key as webhook path")


def test_poller_advances_window(clean_db, db_pool, respx_mock):
    """reconcile_once advances the since-window after processing (D-09 reconciliation)."""
    pytest.fail("Wave 3 (02-05): implement window advancement in reconcile_once")


def test_poller_window_persists_across_restart(clean_db, db_pool):
    """MANDATORY RED (fix #3): last_since is persisted to queue.poller_checkpoint.

    After simulated restart (new reconcile_once call), poller resumes from
    saved last_since minus safety overlap — NOT from epoch or NOW().

    Turns GREEN in 02-05 T2 (durable checkpoint).
    """
    pytest.fail(
        "Wave 3 (02-05): implement durable poller checkpoint — persist last_since to queue.poller_checkpoint"
    )
