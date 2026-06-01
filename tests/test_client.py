"""
test_client.py — FreshdeskClient unit tests (Wave 0 scaffold — RED-on-purpose).

All tests import successfully but fail with pytest.fail() until Wave 1 (02-02)
implements FreshdeskClient.
"""

import pytest
from src.freshdesk_io import FreshdeskClient


def test_post_reply_success(respx_mock):
    """FreshdeskClient.post_reply posts to /api/v2/tickets/{id}/reply and returns reply dict."""
    pytest.fail("Wave 1 (02-02): implement FreshdeskClient.post_reply")


def test_post_note(respx_mock):
    """FreshdeskClient.post_note posts to /api/v2/tickets/{id}/notes (private note)."""
    pytest.fail("Wave 1 (02-02): implement FreshdeskClient.post_note")


def test_retry_after(respx_mock):
    """FreshdeskClient honors Retry-After header on 429 before retrying (REP-05 rate limit)."""
    pytest.fail("Wave 1 (02-02): implement Retry-After honored retry logic")


def test_fatal_404_no_retry(respx_mock):
    """FreshdeskClient does NOT retry on 404 — straight to dead-letter path."""
    pytest.fail("Wave 1 (02-02): implement fatal 404 no-retry classification")


def test_list_updated_tickets(respx_mock):
    """FreshdeskClient.list_updated_tickets(since) returns list[Ticket] (fix #2 — poller dependency).

    Mandatory RED test — turns GREEN in 02-02 T2.
    """
    pytest.fail("Wave 1 (02-02): implement list_updated_tickets returning list[Ticket]")
