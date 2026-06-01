"""
test_webhook.py — Webhook receiver tests (Wave 3 — 02-05).

Covers:
  - HMAC-SHA256 signature verify (valid + invalid + missing)
  - POST /webhook/freshdesk: resolve-then-enqueue flow
  - Non-customer update → skip enqueue (should_suppress single source of truth)
  - Missing secret → 401 rejection
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
import pytest_asyncio
import asyncpg
import respx as respx_lib
import httpx

from src.webhook import verify_signature


# ── Signature tests (no DB needed) ────────────────────────────────────────────


def test_hmac_verify_valid():
    """verify_signature returns True for a correctly signed webhook payload."""
    secret = b"my-secret-key"
    body = b'{"ticket":{"id":123}}'
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True


def test_hmac_verify_rejects_bad_sig():
    """verify_signature returns False for a tampered payload or wrong sig."""
    secret = b"my-secret-key"
    body = b'{"ticket":{"id":123}}'
    # Wrong signature
    assert verify_signature(body, "deadbeef", secret) is False
    # None signature
    assert verify_signature(body, None, secret) is False
    # Empty string signature
    assert verify_signature(body, "", secret) is False


def test_hmac_verify_malformed_returns_false_not_raises():
    """A non-ASCII / malformed signature header must yield False, never raise (BL-03).

    compare_digest raises TypeError on non-ASCII str operands; verify_signature
    must catch this and return False so the receiver returns 401, not 500.
    """
    secret = b"my-secret-key"
    body = b'{"ticket":{"id":123}}'
    # Non-ASCII header value — would crash hmac.compare_digest if unguarded
    assert verify_signature(body, "déadbéef ", secret) is False
    # Odd-length / non-hex garbage
    assert verify_signature(body, "zzz", secret) is False


@pytest.mark.asyncio
async def test_enqueue_on_webhook(clean_db, db_pool, respx_mock):
    """POST /webhook/freshdesk with valid sig → resolve → enqueue with real key "123:456"."""
    from httpx import AsyncClient
    from src.webhook.receiver import app

    secret = b"test-secret"
    payload = {"ticket": {"id": 123}}
    body = json.dumps(payload).encode()
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()

    # Mock Freshdesk GET /conversations → inbound customer message id=456
    respx_mock.get("/api/v2/tickets/123/conversations").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 456,
                    "incoming": True,
                    "private": False,
                    "user_id": 999,
                    "from_email": "customer@example.com",
                    "source": 1,
                    "body_text": "I need help",
                }
            ],
        )
    )

    import os
    os.environ["WEBHOOK_SECRET"] = "test-secret"
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    # Patch db_pool into app state
    from src.webhook import receiver as recv_module
    recv_module._test_pool = db_pool

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/webhook/freshdesk",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Freshdesk-Signature": sig,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"

    # Verify the row exists in DB with correct idempotency key
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT idempotency_key, ticket_id, inbound_msg_id FROM queue.ticket_queue WHERE ticket_id = 123"
        )
    assert row is not None
    assert row["idempotency_key"] == "123:456"
    assert row["ticket_id"] == 123
    assert row["inbound_msg_id"] == 456


@pytest.mark.asyncio
async def test_webhook_no_inbound_skips_enqueue(clean_db, db_pool, respx_mock):
    """get_conversations with only non-customer messages → should_suppress → no enqueue, 200 ignored."""
    from httpx import AsyncClient
    from src.webhook.receiver import app

    secret = b"test-secret"
    payload = {"ticket": {"id": 789}}
    body = json.dumps(payload).encode()
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()

    # Mock GET /conversations → only agent reply (incoming=False)
    respx_mock.get("/api/v2/tickets/789/conversations").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 500,
                    "incoming": False,
                    "private": False,
                    "user_id": 1,
                    "from_email": "agent@company.com",
                    "source": 1,
                    "body_text": "Agent reply here",
                }
            ],
        )
    )

    import os
    os.environ["WEBHOOK_SECRET"] = "test-secret"
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    from src.webhook import receiver as recv_module
    recv_module._test_pool = db_pool

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/webhook/freshdesk",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Freshdesk-Signature": sig,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

    # No rows enqueued
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM queue.ticket_queue WHERE ticket_id = 789")
    assert count == 0


@pytest.mark.asyncio
async def test_webhook_rejects_unsigned(clean_db, db_pool):
    """Webhook with no signature header → 401 (verify before any I/O)."""
    from httpx import AsyncClient
    from src.webhook.receiver import app

    import os
    os.environ["WEBHOOK_SECRET"] = "test-secret"
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    payload = {"ticket": {"id": 111}}
    body = json.dumps(payload).encode()

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/webhook/freshdesk",
            content=body,
            headers={"Content-Type": "application/json"},
            # No X-Freshdesk-Signature header
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_malformed_signature_returns_401_not_500(clean_db, db_pool):
    """Malformed signature header → 401, never an unhandled 500 (BL-03).

    Before the fix, hmac.compare_digest raised TypeError on a non-ASCII signature
    operand, propagating out of verify_signature into the endpoint as a 500. The
    contract (T-02-15) requires a bad/malformed signature to be rejected with 401.

    Note: a genuinely non-ASCII header value is rejected by the HTTP client/wire
    layer before it ever reaches the app, so the over-the-wire malformed-signature
    case is an ASCII-but-invalid digest (wrong length / non-hex garbage). The
    direct non-ASCII guard on verify_signature is proven by
    test_hmac_verify_malformed_returns_false_not_raises.
    """
    from httpx import AsyncClient
    from src.webhook.receiver import app

    import os
    os.environ["WEBHOOK_SECRET"] = "test-secret"
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    payload = {"ticket": {"id": 222}}
    body = json.dumps(payload).encode()

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/webhook/freshdesk",
            content=body,
            headers={
                "Content-Type": "application/json",
                # Malformed (non-hex, odd-length) signature — must not 500
                "X-Freshdesk-Signature": "not-a-valid-hex-digest!!",
            },
        )

    assert resp.status_code == 401, (
        f"Malformed signature must yield 401, not {resp.status_code} (BL-03)"
    )
