"""
test_poller.py — Reconciliation poller tests (Wave 3 — 02-05).

Covers:
  - reconcile_once enqueues updated tickets with real key
  - Dedup with webhook path (same idempotency key → ON CONFLICT DO NOTHING)
  - Window advancement to max(updated_at) after reconcile
  - Durable checkpoint: persists last_since; restart resumes with safety overlap (fix #3)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.poller import reconcile_once, load_checkpoint, save_checkpoint


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ticket_resp(ticket_id: int, updated_at: datetime) -> dict:
    return {"id": ticket_id, "updated_at": updated_at.isoformat()}


def _make_conv_resp(conv_id: int, incoming: bool = True) -> dict:
    return {
        "id": conv_id,
        "incoming": incoming,
        "private": False,
        "user_id": 999,
        "from_email": "customer@example.com",
        "source": 1,
        "body_text": "Help needed",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_poller_enqueues_updated(clean_db, db_pool, respx_mock):
    """reconcile_once fetches 2 updated tickets and enqueues both with real keys."""
    import os
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    now = datetime.now(timezone.utc)
    t1_updated = now - timedelta(minutes=5)
    t2_updated = now - timedelta(minutes=3)

    # Mock list_updated_tickets (GET /api/v2/tickets?updated_since=...)
    # list_updated_tickets paginates: page 1 returns data, page 2 returns [] to stop.
    tickets_page_responses = [
        httpx.Response(
            200,
            json=[
                _make_ticket_resp(101, t1_updated),
                _make_ticket_resp(102, t2_updated),
            ],
        ),
        httpx.Response(200, json=[]),  # empty page stops pagination
    ]
    respx_mock.get("/api/v2/tickets").mock(side_effect=tickets_page_responses)

    # Mock GET /conversations for ticket 101 → inbound conv id=201
    respx_mock.get("/api/v2/tickets/101/conversations").mock(
        return_value=httpx.Response(200, json=[_make_conv_resp(201)])
    )
    # Mock GET /conversations for ticket 102 → inbound conv id=202
    respx_mock.get("/api/v2/tickets/102/conversations").mock(
        return_value=httpx.Response(200, json=[_make_conv_resp(202)])
    )

    from src.freshdesk_io.client import FreshdeskClient

    http_client = httpx.AsyncClient(
        auth=("test-api-key", "X"),
        base_url="https://testdomain.freshdesk.com",
        timeout=30.0,
    )
    client = FreshdeskClient(domain="testdomain", api_key="test-api-key", _http_client=http_client)

    since = now - timedelta(hours=1)
    enqueued, new_since = await reconcile_once(client, db_pool, since)

    assert enqueued == 2

    # Verify rows in DB
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT idempotency_key, ticket_id, inbound_msg_id FROM queue.ticket_queue ORDER BY ticket_id"
        )
    assert len(rows) == 2
    assert rows[0]["idempotency_key"] == "101:201"
    assert rows[1]["idempotency_key"] == "102:202"


@pytest.mark.asyncio
async def test_poller_dedup_with_webhook(clean_db, db_pool, respx_mock):
    """Poller derives same key "123:456" as webhook → ON CONFLICT → exactly one row."""
    import os
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    now = datetime.now(timezone.utc)

    # Pre-enqueue the same ticket via "webhook path" (direct DB insert with same key)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO queue.ticket_queue (idempotency_key, ticket_id, inbound_msg_id, payload)
            VALUES ('123:456', 123, 456, '{"ticket_id": 123}'::jsonb)
            ON CONFLICT (idempotency_key) DO NOTHING
            """
        )

    # Poller sees ticket 123 updated; page 2 empty stops pagination
    respx_mock.get("/api/v2/tickets").mock(
        side_effect=[
            httpx.Response(200, json=[_make_ticket_resp(123, now - timedelta(minutes=2))]),
            httpx.Response(200, json=[]),
        ]
    )
    # Poller resolves same conv id=456 → same key "123:456"
    respx_mock.get("/api/v2/tickets/123/conversations").mock(
        return_value=httpx.Response(200, json=[_make_conv_resp(456)])
    )

    from src.freshdesk_io.client import FreshdeskClient

    http_client = httpx.AsyncClient(
        auth=("test-api-key", "X"),
        base_url="https://testdomain.freshdesk.com",
        timeout=30.0,
    )
    client = FreshdeskClient(domain="testdomain", api_key="test-api-key", _http_client=http_client)

    since = now - timedelta(hours=1)
    enqueued, _ = await reconcile_once(client, db_pool, since)

    # ON CONFLICT DO NOTHING → poller finds existing row, reports 0 new enqueued
    assert enqueued == 0

    # Exactly one row in DB
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM queue.ticket_queue WHERE idempotency_key = '123:456'"
        )
    assert count == 1


@pytest.mark.asyncio
async def test_poller_advances_window(clean_db, db_pool, respx_mock):
    """reconcile_once advances new_since to max(updated_at) of processed tickets."""
    import os
    os.environ["FRESHDESK_DOMAIN"] = "testdomain"
    os.environ["FRESHDESK_API_KEY"] = "test-api-key"

    now = datetime.now(timezone.utc)
    t1_updated = now - timedelta(minutes=10)
    t2_updated = now - timedelta(minutes=2)  # more recent

    respx_mock.get("/api/v2/tickets").mock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    _make_ticket_resp(201, t1_updated),
                    _make_ticket_resp(202, t2_updated),
                ],
            ),
            httpx.Response(200, json=[]),  # empty page stops pagination
        ]
    )
    respx_mock.get("/api/v2/tickets/201/conversations").mock(
        return_value=httpx.Response(200, json=[_make_conv_resp(301)])
    )
    respx_mock.get("/api/v2/tickets/202/conversations").mock(
        return_value=httpx.Response(200, json=[_make_conv_resp(302)])
    )

    from src.freshdesk_io.client import FreshdeskClient

    http_client = httpx.AsyncClient(
        auth=("test-api-key", "X"),
        base_url="https://testdomain.freshdesk.com",
        timeout=30.0,
    )
    client = FreshdeskClient(domain="testdomain", api_key="test-api-key", _http_client=http_client)

    since = now - timedelta(hours=1)
    _, new_since = await reconcile_once(client, db_pool, since)

    # new_since should be t2_updated (max of the two)
    # Compare with 2-second tolerance for timezone rounding
    assert abs((new_since - t2_updated).total_seconds()) < 2


@pytest.mark.asyncio
async def test_poller_window_persists_across_restart(clean_db, db_pool):
    """MANDATORY fix #3: last_since is persisted; restart resumes with safety overlap.

    Simulates:
      1. save_checkpoint(conn, last_since) → persists to queue.poller_checkpoint
      2. Simulated restart: load_checkpoint(conn) reads from DB
      3. Loaded value = last_since - safety_overlap (not epoch, not NOW() from scratch)
    """
    now = datetime.now(timezone.utc)
    saved_since = now - timedelta(minutes=5)
    safety_overlap = 600  # seconds (default poller_interval_seconds)

    async with db_pool.acquire() as conn:
        # Persist the checkpoint
        await save_checkpoint(conn, saved_since)

        # Simulate restart: load checkpoint fresh from DB
        resumed_since = await load_checkpoint(conn, safety_overlap_seconds=safety_overlap)

    # resumed_since must be approx saved_since - safety_overlap
    expected = saved_since - timedelta(seconds=safety_overlap)
    diff = abs((resumed_since - expected).total_seconds())

    # Must not be epoch (0), not NOW() from scratch, must be near expected
    assert diff < 5, (
        f"Restart did not resume from checkpoint with safety overlap. "
        f"Expected ~{expected.isoformat()}, got {resumed_since.isoformat()}"
    )

    # Verify data was actually persisted to DB (not just in-memory)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_since FROM queue.poller_checkpoint WHERE id = 1"
        )
    assert row is not None
    db_last_since: datetime = row["last_since"]
    assert abs((db_last_since - saved_since).total_seconds()) < 2, (
        f"DB checkpoint {db_last_since.isoformat()} differs from saved {saved_since.isoformat()}"
    )
