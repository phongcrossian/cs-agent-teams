"""
test_e2e_sandbox.py — Real Freshdesk sandbox smoke tests.

All tests are marked @pytest.mark.sandbox and are skipped in CI unless
RUN_SANDBOX=1 is set.

These tests require:
  - Real Freshdesk sandbox account (D-03)
  - FRESHDESK_DOMAIN, FRESHDESK_API_KEY env vars
  - SEND_MODE=live
  - Running Postgres (DATABASE_URL)

Turns GREEN in 02-06 T3.
"""

import pytest


@pytest.mark.sandbox
async def test_sandbox_real_reply():
    """Posts a real reply into a Freshdesk sandbox ticket and verifies it appears.

    Proves criterion #2: AI can post approved reply into correct existing ticket via API.
    """
    pytest.fail("Wave 4 (02-06): implement sandbox real reply smoke test (D-03)")


@pytest.mark.sandbox
async def test_sandbox_retry_no_double_send():
    """Re-running the worker on the same ticket does NOT post a second reply.

    Proves exactly-once idempotency (REP-05 crit #2) against a real Freshdesk sandbox.
    """
    pytest.fail(
        "Wave 4 (02-06): implement sandbox retry-no-double-send smoke test (REP-05)"
    )
