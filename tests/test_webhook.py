"""
test_webhook.py — Webhook receiver tests (Wave 0 scaffold — RED-on-purpose).

Covers: HMAC signature verify (valid + invalid), enqueue on webhook receipt.

All tests import successfully but fail with pytest.fail() until Wave 3 (02-05).
"""

import pytest
from src.webhook import verify_signature


def test_hmac_verify_valid():
    """verify_signature returns True for a correctly signed webhook payload."""
    pytest.fail("Wave 3 (02-05): implement verify_signature (HMAC-SHA256)")


def test_hmac_verify_rejects_bad_sig():
    """verify_signature returns False (or raises) for a tampered payload."""
    pytest.fail("Wave 3 (02-05): implement verify_signature rejection of bad signature")


def test_enqueue_on_webhook(clean_db, db_pool, respx_mock):
    """POST /webhook/freshdesk with valid sig → ticket enqueued in queue.ticket_queue."""
    pytest.fail("Wave 3 (02-05): implement webhook receiver → enqueue flow")
