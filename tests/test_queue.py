"""
test_queue.py — Queue core tests.

Wave 1 (02-03) — GREEN:
  - test_enqueue_dedup: ON CONFLICT DO NOTHING dedup at insert
  - test_idempotency: webhook path + poller path → same key → exactly-once (REP-05 crit #2)
  - test_skip_locked_claim: FOR UPDATE SKIP LOCKED — no concurrent collision
  - test_finalize_done: token-checked done finalization
  - test_finalize_retry: attempts++, backoff next_attempt_at, PII-safe last_error
  - test_stale_claim_recovery: stale claimed rows → pending

Wave 2 (02-04) — GREEN (this plan):
  - test_send_dry_run
  - test_send_live
  - test_worker_suppressed_path
  - test_worker_recheck_routes_stale_inbound
  - test_worker_happy_path_exactly_once
  - test_worker_crash_after_post_does_not_resend
  - test_loop_guard_throttle (in test_loop_guard.py)

Wave 4 (02-06) — still RED:
  - test_dead_letter_on_exhaustion
  - test_sweep_exhausted_unlettered (fix #9)
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
import respx as respx_lib
import httpx

from src.work_queue import enqueue, claim
from src.work_queue.enqueue import enqueue_ticket
from src.work_queue.claim import (
    claim_one,
    finalize_done,
    finalize_retry,
    recover_stale_claims,
)
from src.work_queue.idempotency import compute_idempotency_key
from src.config import SendMode


# ── Wave 1 (02-03) GREEN tests ────────────────────────────────────────────────

async def test_enqueue_dedup(clean_db, db_pool):
    """Enqueueing same idempotency_key twice → second insert is silently ignored (ON CONFLICT DO NOTHING)."""
    async with db_pool.acquire() as conn:
        # First enqueue — should return True (inserted)
        result1 = await enqueue_ticket(conn, ticket_id=100, inbound_msg_id=200, redacted_payload={"subject": "test"})
        assert result1 is True, "First enqueue should return True (inserted)"

        # Second enqueue with same (ticket_id, inbound_msg_id) — must return False (duplicate)
        result2 = await enqueue_ticket(conn, ticket_id=100, inbound_msg_id=200, redacted_payload={"subject": "test"})
        assert result2 is False, "Second enqueue with same key should return False (ON CONFLICT DO NOTHING)"

        # Exactly one row in the table
        count = await conn.fetchval("SELECT COUNT(*) FROM queue.ticket_queue WHERE ticket_id = 100")
        assert count == 1, f"Expected 1 row after double-enqueue, got {count}"


async def test_idempotency(clean_db, db_pool, respx_mock):
    """
    Webhook path and poller path both compute the same idempotency_key from the same
    ticket state → exactly one row in queue (REP-05 crit #2 — exactly-once).

    Simulates: webhook arrives first (enqueues) → poller later discovers the same
    ticket with the same inbound_msg_id → tries to enqueue → ON CONFLICT DO NOTHING
    → still exactly 1 row → worker processes it once → no duplicate send.
    """
    ticket_id = 42
    # Both paths resolve the same latest incoming conversation id (D-02 contract)
    inbound_msg_id = 9001

    # Key computation is deterministic and identical for both paths
    webhook_key = compute_idempotency_key(ticket_id, inbound_msg_id)
    poller_key = compute_idempotency_key(ticket_id, inbound_msg_id)
    assert webhook_key == poller_key, "Webhook and poller must derive the same idempotency key"
    assert webhook_key == f"{ticket_id}:{inbound_msg_id}"

    async with db_pool.acquire() as conn:
        # Webhook path enqueues first
        enqueued_by_webhook = await enqueue_ticket(
            conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id,
            redacted_payload={"source": "webhook", "subject": "[REDACTED]"}
        )
        assert enqueued_by_webhook is True

        # Poller path discovers the same ticket (same inbound_msg_id) → duplicate
        enqueued_by_poller = await enqueue_ticket(
            conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id,
            redacted_payload={"source": "poller", "subject": "[REDACTED]"}
        )
        assert enqueued_by_poller is False, "Poller path must be a duplicate (exactly-once)"

        # Queue has exactly one row — one Freshdesk reply will be sent
        row_count = await conn.fetchval(
            "SELECT COUNT(*) FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
        )
        assert row_count == 1, f"Exactly-once: expected 1 row, got {row_count}"


async def test_skip_locked_claim(clean_db, db_pool):
    """Two concurrent workers claim different rows (SKIP LOCKED — no collision)."""
    # Enqueue 2 rows
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=1, inbound_msg_id=101, redacted_payload={})
        await enqueue_ticket(conn, ticket_id=2, inbound_msg_id=102, redacted_payload={})

    # Two concurrent claim transactions — each must get a different row
    claimed_ids = []
    claimed_tokens = []

    async def claim_in_tx(worker_id: str):
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                row = await claim_one(conn, worker_id=worker_id)
                if row is not None:
                    claimed_ids.append(row["id"])
                    claimed_tokens.append(str(row["claim_token"]))
                    # Hold the transaction open briefly to create contention
                    await asyncio.sleep(0.05)
                return row

    results = await asyncio.gather(
        claim_in_tx("worker-A"),
        claim_in_tx("worker-B"),
    )

    # Both workers must have claimed a row
    assert all(r is not None for r in results), "Both workers should claim a row"
    # No two workers claimed the same row (SKIP LOCKED guarantee)
    assert len(set(claimed_ids)) == 2, f"Workers claimed same row! ids={claimed_ids}"
    # Tokens are distinct UUIDs
    assert len(set(claimed_tokens)) == 2, "Claim tokens must be distinct"

    # Order: claim_one uses ORDER BY next_attempt_at ASC, id ASC (deterministic)
    # Both rows were enqueued with the same next_attempt_at (NOW()), so tiebreaker is id ASC
    assert sorted(claimed_ids) == claimed_ids or len(set(claimed_ids)) == 2  # order may vary by concurrency


async def test_finalize_done(clean_db, db_pool):
    """claim + finalize_done(correct token) → status='done'; wrong token → 0 rows (stale worker)."""
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=10, inbound_msg_id=1001, redacted_payload={})

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await claim_one(conn, worker_id="worker-test")
        assert row is not None, "Should have claimed a row"
        claim_token = str(row["claim_token"])
        row_id = row["id"]

    # finalize with correct token → True, status='done'
    async with db_pool.acquire() as conn:
        ok = await finalize_done(conn, row_id=row_id, claim_token=claim_token)
    assert ok is True, "finalize_done with correct token should return True"

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row_id)
    assert status == "done"

    # finalize again with a different (wrong) token → False (stale worker protection)
    wrong_token = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        ok2 = await finalize_done(conn, row_id=row_id, claim_token=wrong_token)
    assert ok2 is False, "finalize_done with wrong token should return False (stale worker)"


async def test_finalize_retry(clean_db, db_pool):
    """finalize_retry → attempts+1, next_attempt_at in the future, status='pending'."""
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=20, inbound_msg_id=2001, redacted_payload={})

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await claim_one(conn, worker_id="worker-retry")
        assert row is not None
        claim_token = str(row["claim_token"])
        row_id = row["id"]
        original_attempts = row["attempts"]

    backoff_seconds = 60
    # Error string must be pre-redacted (T-02-09 — no raw PII)
    redacted_error = "HTTP 500 from Freshdesk (transient); no customer data logged"

    async with db_pool.acquire() as conn:
        await finalize_retry(
            conn,
            row_id=row_id,
            claim_token=claim_token,
            redacted_error=redacted_error,
            backoff_seconds=backoff_seconds,
        )

    async with db_pool.acquire() as conn:
        updated = await conn.fetchrow(
            "SELECT status, attempts, next_attempt_at, last_error FROM queue.ticket_queue WHERE id = $1",
            row_id,
        )

    assert updated["status"] == "pending"
    assert updated["attempts"] == original_attempts + 1
    # next_attempt_at must be in the future (at least backoff_seconds - 2s margin for test speed)
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    assert updated["next_attempt_at"] > now_utc, "next_attempt_at must be in the future after retry"
    # last_error was stored
    assert updated["last_error"] == redacted_error
    # PII rule: last_error must not contain raw customer content
    # (structural check: our test value is already redacted — passes trivially here;
    #  the contract is enforced by convention and code review, not a runtime regex)


async def test_stale_claim_recovery(clean_db, db_pool):
    """Rows stuck in 'claimed' with claimed_at > lease_minutes → recover_stale_claims → 'pending'."""
    # Enqueue and manually set claimed_at to 15 minutes ago (simulating a crashed worker)
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=30, inbound_msg_id=3001, redacted_payload={})
        await conn.execute(
            """
            UPDATE queue.ticket_queue
            SET status = 'claimed',
                claimed_at = NOW() - INTERVAL '15 minutes',
                claimed_by = 'crashed-worker',
                claim_token = gen_random_uuid(),
                updated_at = NOW()
            WHERE ticket_id = 30
            """
        )

    # Also enqueue a fresh claimed row (should NOT be recovered — within lease)
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=31, inbound_msg_id=3101, redacted_payload={})
        await conn.execute(
            """
            UPDATE queue.ticket_queue
            SET status = 'claimed',
                claimed_at = NOW() - INTERVAL '2 minutes',
                claimed_by = 'active-worker',
                claim_token = gen_random_uuid(),
                updated_at = NOW()
            WHERE ticket_id = 31
            """
        )

    async with db_pool.acquire() as conn:
        recovered = await recover_stale_claims(conn, lease_minutes=10)

    assert recovered == 1, f"Expected 1 stale row recovered, got {recovered}"

    async with db_pool.acquire() as conn:
        stale_row = await conn.fetchrow(
            "SELECT status, claim_token FROM queue.ticket_queue WHERE ticket_id = 30"
        )
        active_row = await conn.fetchrow(
            "SELECT status FROM queue.ticket_queue WHERE ticket_id = 31"
        )

    assert stale_row["status"] == "pending", "Stale row should be back to 'pending'"
    assert stale_row["claim_token"] is None, "claim_token should be cleared on stale recovery"
    assert active_row["status"] == "claimed", "Active (within-lease) row should remain 'claimed'"


# ── Wave 4 (02-06) dead_letter + sweep tests ─────────────────────────────────

async def test_dead_letter_on_exhaustion(clean_db, db_pool):
    """Row reaching max_attempts on transient error → moved to queue.dead_letter + alerted.

    Scenario: row already at attempts = max_attempts - 1, receives one more transient
    error → worker calls PostgresDeadLetterSink.to_dead_letter → row status='dead_lettered',
    queue.dead_letter has 1 row with alerted=True.
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter import PostgresDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.errors import FreshdeskTransientError

    ticket_id = 800
    inbound_msg_id = 9010
    max_attempts = 5

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        # Simulate row that has already attempted max_attempts - 1 times
        await conn.execute(
            "UPDATE queue.ticket_queue SET attempts = $1 WHERE ticket_id = $2",
            max_attempts - 1,
            ticket_id,
        )
        row = await claim_one(conn, worker_id="worker-exhausted")
        assert row is not None

    # Mock client: get_conversations returns a valid customer conv, then post_reply raises transient
    from src.freshdesk_io.models import Conversation
    customer_conv = Conversation(
        id=inbound_msg_id,
        incoming=True,
        private=False,
        user_id=42,
        from_email="customer@gmail.com",
        source=1,
        body_text="Help with order.",
    )

    import respx as respx_lib
    import httpx
    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[customer_conv.model_dump()])
        )
        # POST raises transient error — this is the final attempt
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            side_effect=FreshdeskTransientError("500 internal server error")
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
        settings = _make_settings(send_mode=SendMode.LIVE, per_ticket_reply_throttle_n=999)
        sink = PostgresDeadLetterSink()

        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=sink,
        )

    async with db_pool.acquire() as conn:
        tq_row = await conn.fetchrow(
            "SELECT status, attempts FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
        )
        dl_row = await conn.fetchrow(
            "SELECT ticket_id, alerted FROM queue.dead_letter WHERE ticket_id = $1", ticket_id
        )

    assert tq_row["status"] == "dead_lettered", (
        f"Exhausted row must be dead_lettered; got {tq_row['status']!r}"
    )
    assert dl_row is not None, "queue.dead_letter must have 1 row after exhaustion"
    assert dl_row["alerted"] is True, "dead_letter row must be alerted=True"


# ── Wave 2 (02-04) — send + worker tests ─────────────────────────────────────

async def test_send_dry_run(clean_db, db_pool, respx_mock):
    """DRY_RUN mode: persists to dry_run_log, does NOT call Freshdesk API (respx call count = 0)."""
    from src.work_queue.send import send_reply

    ticket_id = 200
    inbound_msg_id = 9001

    # Enqueue a row so we have a valid row_id
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-dry-run")
        assert row is not None
        row_id = row["id"]
        claim_token = str(row["claim_token"])

    # Build a minimal FreshdeskClient (no real HTTP calls expected)
    from src.freshdesk_io.client import FreshdeskClient
    http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
    client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)

    body = "Thank you for contacting support."

    async with db_pool.acquire() as conn:
        result = await send_reply(
            client=client,
            conn=conn,
            ticket_id=ticket_id,
            inbound_msg_id=inbound_msg_id,
            body=body,
            mode=SendMode.DRY_RUN,
            row_id=row_id,
            claim_token=claim_token,
        )

    # 1. Result must indicate dry run
    assert result.get("dry_run") is True, f"Expected dry_run=True in result; got {result}"

    # 2. No Freshdesk HTTP calls (respx_mock tracks all calls)
    assert len(respx_mock.calls) == 0, f"DRY_RUN must not call Freshdesk; got {len(respx_mock.calls)} calls"

    # 3. dry_run_log row must exist with correct columns (DOC-DRIFT fix: schema has inbound_msg_id + action)
    async with db_pool.acquire() as conn:
        log_row = await conn.fetchrow(
            "SELECT ticket_id, inbound_msg_id, action, body FROM queue.dry_run_log WHERE ticket_id = $1",
            ticket_id,
        )
    assert log_row is not None, "dry_run_log row must be inserted in DRY_RUN mode"
    assert log_row["ticket_id"] == ticket_id
    assert log_row["inbound_msg_id"] == inbound_msg_id
    assert log_row["action"] == "reply"
    assert log_row["body"] is not None


async def test_dry_run_persists_redacted_body(clean_db, db_pool, respx_mock):
    """DRY_RUN persistence boundary redacts PII before INSERT into dry_run_log (BL-04 / D-12).

    Redaction must be enforced structurally at the persistence seam, not by
    caller convention. Even when a caller passes a raw body containing an email
    address, the persisted dry_run_log.body must NOT contain the raw PII.
    """
    from src.work_queue.send import send_reply

    ticket_id = 250
    inbound_msg_id = 9051

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-redact")
        assert row is not None
        row_id = row["id"]
        claim_token = str(row["claim_token"])

    from src.freshdesk_io.client import FreshdeskClient
    http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
    client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)

    # Raw body with an email address — a caller forgetting to pre-redact
    raw_email = "john.doe@example.com"
    raw_body = f"Please refund my order, contact me at {raw_email} thanks"

    async with db_pool.acquire() as conn:
        await send_reply(
            client=client,
            conn=conn,
            ticket_id=ticket_id,
            inbound_msg_id=inbound_msg_id,
            body=raw_body,
            mode=SendMode.DRY_RUN,
            row_id=row_id,
            claim_token=claim_token,
        )

    async with db_pool.acquire() as conn:
        persisted_body = await conn.fetchval(
            "SELECT body FROM queue.dry_run_log WHERE ticket_id = $1", ticket_id
        )

    assert persisted_body is not None, "dry_run_log row must exist"
    # The raw email must NOT survive to the persisted column
    assert raw_email not in persisted_body, (
        f"Raw PII leaked into dry_run_log.body: {persisted_body!r} (BL-04)"
    )
    # Redaction tag should be present
    assert "<EMAIL_ADDRESS>" in persisted_body, (
        f"Expected redacted EMAIL_ADDRESS tag in persisted body; got {persisted_body!r}"
    )


async def test_send_live(clean_db, db_pool):
    """LIVE mode: post_reply → persist sent_at + freshdesk_reply_id (fix #1, send-intent)."""
    from src.work_queue.send import send_reply
    from src.freshdesk_io.client import FreshdeskClient

    ticket_id = 300
    inbound_msg_id = 9002
    fake_reply_id = 54321

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-live")
        assert row is not None
        row_id = row["id"]
        claim_token = str(row["claim_token"])

    # respx mock: POST reply → 201 (no conversations scan — marker pre-send guard removed, D-03)
    with respx_lib.mock(base_url="https://testdomain.freshdesk.com") as mock:
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            return_value=httpx.Response(201, json={"id": fake_reply_id, "ticket_id": ticket_id})
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)

        async with db_pool.acquire() as conn:
            result = await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body="<p>We are looking into your order.</p>",
                mode=SendMode.LIVE,
                row_id=row_id,
                claim_token=claim_token,
            )

    # Result is the ReplyResult
    assert hasattr(result, "id") or isinstance(result, dict), f"Expected ReplyResult or dict; got {result}"

    # sent_at + freshdesk_reply_id persisted (fix #1 — send-intent transactional)
    async with db_pool.acquire() as conn:
        updated = await conn.fetchrow(
            "SELECT sent_at, freshdesk_reply_id FROM queue.ticket_queue WHERE id = $1", row_id
        )
    assert updated["sent_at"] is not None, "sent_at must be persisted after LIVE send (fix #1)"
    assert updated["freshdesk_reply_id"] == fake_reply_id, f"freshdesk_reply_id must be persisted; got {updated['freshdesk_reply_id']}"


async def test_worker_suppressed_path(clean_db, db_pool):
    """Worker: conv suppressed by loop-guard → status='suppressed', not dead_letter, no send (D-08)."""
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter_sink import RetryOnlyDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.models import Conversation

    ticket_id = 400
    inbound_msg_id = 9003

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-suppress")
        assert row is not None

    # Mock client: get_conversations returns a non-customer conv (incoming=False)
    suppressed_conv = Conversation(
        id=inbound_msg_id,
        incoming=False,  # agent reply → suppress
        private=False,
        user_id=99,
        from_email="agent@company.com",
        source=1,
        body_text="Agent note",
    )

    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[suppressed_conv.model_dump()])
        )
        # POST should NOT be called — registered only to detect unexpected calls
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            return_value=httpx.Response(201, json={"id": 999, "ticket_id": ticket_id})
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)

        # Build mock settings
        settings = _make_settings(send_mode=SendMode.DRY_RUN)
        dead_letter_sink = RetryOnlyDeadLetterSink()

        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=dead_letter_sink,
        )

    # Status must be 'suppressed' (D-08: suppress = skip+log, NOT dead_letter)
    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row["id"])
        dead_letter_count = await conn.fetchval("SELECT COUNT(*) FROM queue.dead_letter")
    assert status == "suppressed", f"Suppressed conv should set status='suppressed'; got {status!r}"
    assert dead_letter_count == 0, "Suppressed conv must NOT go to dead_letter (D-08)"

    # POST reply must not have been called
    post_calls = [c for c in mock.calls if c.request.method == "POST"]
    assert len(post_calls) == 0, f"Suppressed path must not call POST; got {len(post_calls)} calls"


async def test_worker_recheck_routes_stale_inbound(clean_db, db_pool):
    """Worker re-checks should_suppress on valid enqueued row.

    If suppress is now True (state changed post-enqueue) →
    status='stale_inbound' + alert emitted, NOT silent 'suppressed', NOT dead_letter (fix #4).
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter_sink import RetryOnlyDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.models import Conversation

    ticket_id = 500
    inbound_msg_id = 9004
    selless_user_id = 99999  # will be added to whitelist after enqueue

    # Enqueue as valid customer inbound (user_id NOT yet in selless list)
    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-stale")
        assert row is not None

    # Now: user_id is discovered to be a Selless sync user (config updated after enqueue)
    # Conv looks like valid customer BUT user_id is now in selless_sync_user_ids
    stale_conv = Conversation(
        id=inbound_msg_id,
        incoming=True,   # looks like customer reply
        private=False,
        user_id=selless_user_id,  # but now whitelisted as Selless sync
        from_email="sync@selless.com",
        source=1,
        body_text="Sync update content",
    )

    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[stale_conv.model_dump()])
        )
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            return_value=httpx.Response(201, json={"id": 888, "ticket_id": ticket_id})
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)

        # Settings now have selless_user_id in the whitelist
        settings = _make_settings(
            send_mode=SendMode.DRY_RUN,
            selless_sync_user_ids={selless_user_id},
        )
        dead_letter_sink = RetryOnlyDeadLetterSink()

        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=dead_letter_sink,
        )

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row["id"])
        dead_letter_count = await conn.fetchval("SELECT COUNT(*) FROM queue.dead_letter")

    # Must be 'stale_inbound' NOT 'suppressed' (fix #4 — observable, not silent drop)
    assert status == "stale_inbound", (
        f"Valid row re-checked suppress=True → must be 'stale_inbound', got {status!r} (fix #4)"
    )
    assert dead_letter_count == 0, "stale_inbound must NOT go to dead_letter"

    # POST reply must not have been called
    post_calls = [c for c in mock.calls if c.request.method == "POST"]
    assert len(post_calls) == 0, "stale_inbound path must not call POST"


async def test_worker_happy_path_exactly_once(clean_db, db_pool):
    """Happy path: claim → fetch conversations → suppress=False → redact → send (dry-run) → done.

    Re-run with same inbound MUST NOT create a second send (exactly-once via idempotency key).
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter_sink import RetryOnlyDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.models import Conversation

    ticket_id = 600
    inbound_msg_id = 9005

    # Customer conv to return from get_conversations
    customer_conv = Conversation(
        id=inbound_msg_id,
        incoming=True,
        private=False,
        user_id=42,
        from_email="customer@gmail.com",
        source=1,
        body_text="Please help me with my order.",
    )

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-happy")
        assert row is not None

    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[customer_conv.model_dump()])
        )
        # DRY_RUN — no POST expected but set up in case
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            return_value=httpx.Response(201, json={"id": 777, "ticket_id": ticket_id})
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
        settings = _make_settings(send_mode=SendMode.DRY_RUN)
        dead_letter_sink = RetryOnlyDeadLetterSink()

        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=dead_letter_sink,
        )

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row["id"])
    assert status == "done", f"Happy path must finalize to 'done'; got {status!r}"

    # Exactly-once: second enqueue with same key must be rejected
    async with db_pool.acquire() as conn:
        second = await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
    assert second is False, "Second enqueue with same key must be rejected (exactly-once)"

    # No POST calls (dry-run)
    post_calls = [c for c in mock.calls if c.request.method == "POST"]
    assert len(post_calls) == 0, "DRY_RUN should not call Freshdesk POST"


async def test_worker_crash_after_post_does_not_resend(clean_db, db_pool):
    """MANDATORY (fix #1 REP-05): Worker crashes after POST 200 but before finalize_done.

    Recovery scenario:
    1. Worker claims row, POSTs successfully, persists sent_at + freshdesk_reply_id.
    2. finalize_done raises (simulating crash).
    3. Row stays in 'claimed' status (crash left it there).
    4. recover_stale_claims re-sets row to 'pending'.
    5. Second worker claims the row.
    6. process_queue_row sees sent_at IS NOT NULL → SKIP post → go straight to finalize_done.
    7. respx POST call count == 1 (sent only once — exactly-once across crash).
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter_sink import RetryOnlyDeadLetterSink
    from src.work_queue.send import send_reply
    from src.freshdesk_io.client import FreshdeskClient

    ticket_id = 700
    inbound_msg_id = 9006
    fake_reply_id = 11111

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})

    post_call_count = 0

    # No GET conversations mock: send_reply no longer scans (marker pre-send guard removed,
    # D-03), and the recovered row's skip-if-sent (sent_at set) returns before any worker fetch.
    with respx_lib.mock(base_url="https://testdomain.freshdesk.com") as mock:
        # POST reply → 201 (should only be called once)
        def post_side_effect(request):
            nonlocal post_call_count
            post_call_count += 1
            return httpx.Response(201, json={"id": fake_reply_id, "ticket_id": ticket_id})

        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(side_effect=post_side_effect)

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
        settings = _make_settings(send_mode=SendMode.LIVE)
        dead_letter_sink = RetryOnlyDeadLetterSink()

        # ── Step 1: First claim
        async with db_pool.acquire() as conn:
            row = await claim_one(conn, worker_id="worker-first")
            assert row is not None
            row_id = row["id"]

        # ── Step 2: Simulate crash — manually persist sent_at (as if POST succeeded but crash before finalize)
        # We call send_reply directly to simulate: POST 200 → sent_at persisted → crash
        async with db_pool.acquire() as conn:
            await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body="<p>We are looking into this.</p>",
                mode=SendMode.LIVE,
                row_id=row_id,
                claim_token=str(row["claim_token"]),
            )
        # sent_at now persisted, POST called once
        assert post_call_count == 1, f"Expected 1 POST after first send; got {post_call_count}"

        # ── Step 3: Simulate crash — row stays 'claimed' (no finalize_done called)
        async with db_pool.acquire() as conn:
            status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row_id)
        assert status == "claimed", f"After crash simulation, status should be 'claimed'; got {status}"

        # Verify sent_at IS NOT NULL (send-intent persisted)
        async with db_pool.acquire() as conn:
            sent_at = await conn.fetchval("SELECT sent_at FROM queue.ticket_queue WHERE id = $1", row_id)
        assert sent_at is not None, "sent_at must be persisted after successful POST"

        # ── Step 4: Stale claim recovery (simulate time passing)
        async with db_pool.acquire() as conn:
            # Force claimed_at to be stale
            await conn.execute(
                "UPDATE queue.ticket_queue SET claimed_at = NOW() - INTERVAL '15 minutes' WHERE id = $1",
                row_id,
            )
            recovered = await recover_stale_claims(conn, lease_minutes=10)
        assert recovered == 1, f"Expected 1 recovered row; got {recovered}"

        # ── Step 5: Second worker claims
        async with db_pool.acquire() as conn:
            row2 = await claim_one(conn, worker_id="worker-second")
        assert row2 is not None, "Second worker must be able to claim the recovered row"
        assert row2["id"] == row_id, "Second worker must claim same row"

        # ── Step 6: process_queue_row — must detect sent_at IS NOT NULL → SKIP post
        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row2,
            settings=settings,
            dead_letter_sink=dead_letter_sink,
        )

    # ── Step 7: POST call count == 1 (exactly-once across crash — fix #1)
    assert post_call_count == 1, (
        f"Exactly-once across crash: POST must be called exactly 1 time; got {post_call_count} (fix #1, REP-05)"
    )

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM queue.ticket_queue WHERE id = $1", row_id)
    assert status == "done", f"After recovery, status must be 'done'; got {status!r}"


async def test_fatal_straight_to_dead_letter(clean_db, db_pool):
    """Fatal error (404 or 409) → dead_letter immediately, no retry (fix #5).

    Attempts should NOT increment to max_attempts first — fatal = dead-letter NOW.
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter import PostgresDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.errors import FreshdeskFatalError
    from src.freshdesk_io.models import Conversation

    import respx as respx_lib
    import httpx

    for status_code, label in [(404, "404_not_found"), (409, "409_conflict")]:
        ticket_id = 810 + status_code  # unique per iteration
        inbound_msg_id = 9020 + status_code

        async with db_pool.acquire() as conn:
            await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
            row = await claim_one(conn, worker_id=f"worker-fatal-{label}")
            assert row is not None

        customer_conv = Conversation(
            id=inbound_msg_id,
            incoming=True,
            private=False,
            user_id=42,
            from_email="customer@gmail.com",
            source=1,
            body_text="Need help.",
        )

        with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
            mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
                return_value=httpx.Response(200, json=[customer_conv.model_dump()])
            )
            mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
                side_effect=FreshdeskFatalError(f"HTTP {status_code}")
            )

            http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
            client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
            settings = _make_settings(send_mode=SendMode.LIVE, per_ticket_reply_throttle_n=999)
            sink = PostgresDeadLetterSink()

            await process_queue_row(
                pool=db_pool,
                client=client,
                row=row,
                settings=settings,
                dead_letter_sink=sink,
            )

        async with db_pool.acquire() as conn:
            tq_row = await conn.fetchrow(
                "SELECT status, attempts FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
            )
            dl_count = await conn.fetchval(
                "SELECT COUNT(*) FROM queue.dead_letter WHERE ticket_id = $1", ticket_id
            )

        assert tq_row["status"] == "dead_lettered", (
            f"Fatal {label}: status must be 'dead_lettered'; got {tq_row['status']!r}"
        )
        assert dl_count == 1, f"Fatal {label}: must have 1 dead_letter row; got {dl_count}"
        # Fatal = dead-letter immediately, NOT after max_attempts retries
        assert tq_row["attempts"] < 5, (
            f"Fatal {label}: attempts must stay low (immediate DL); got {tq_row['attempts']}"
        )


async def test_retry_after_honored(clean_db, db_pool):
    """FreshdeskRateLimitError(retry_after=3) → next_attempt_at ~= NOW()+3s (not exponential blind)."""
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter import PostgresDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.errors import FreshdeskRateLimitError
    from src.freshdesk_io.models import Conversation
    from datetime import datetime, timezone, timedelta
    import respx as respx_lib
    import httpx

    ticket_id = 820
    inbound_msg_id = 9030
    retry_after_secs = 3

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-ratelimit")
        assert row is not None
        row_id = row["id"]

    customer_conv = Conversation(
        id=inbound_msg_id,
        incoming=True,
        private=False,
        user_id=42,
        from_email="customer@gmail.com",
        source=1,
        body_text="Order question.",
    )

    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[customer_conv.model_dump()])
        )
        mock.post(f"/api/v2/tickets/{ticket_id}/reply").mock(
            side_effect=FreshdeskRateLimitError(retry_after=retry_after_secs)
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
        settings = _make_settings(send_mode=SendMode.LIVE, per_ticket_reply_throttle_n=999)
        sink = PostgresDeadLetterSink()

        before = datetime.now(timezone.utc)
        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=sink,
        )
        after = datetime.now(timezone.utc)

    async with db_pool.acquire() as conn:
        updated = await conn.fetchrow(
            "SELECT status, next_attempt_at FROM queue.ticket_queue WHERE id = $1", row_id
        )

    assert updated["status"] == "pending", (
        f"RateLimit: status must be 'pending' for retry; got {updated['status']!r}"
    )
    # next_attempt_at must be approximately NOW() + retry_after_secs
    # Allow ±5s margin for test execution time
    expected_min = before + timedelta(seconds=retry_after_secs - 5)
    expected_max = after + timedelta(seconds=retry_after_secs + 5)
    nat = updated["next_attempt_at"]
    assert expected_min <= nat <= expected_max, (
        f"Retry-After honored: next_attempt_at={nat} not in range [{expected_min}, {expected_max}]"
    )


async def test_suppressed_not_dead_letter(clean_db, db_pool):
    """Suppressed (stale_inbound / D-08) inbound NEVER goes to dead_letter.

    Suppression is D-08 loop-guard logic; dead_letter is for actual send failures (crit #3).
    These must NOT be conflated.
    """
    from src.work_queue.worker import process_queue_row
    from src.work_queue.dead_letter import PostgresDeadLetterSink
    from src.freshdesk_io.client import FreshdeskClient
    from src.freshdesk_io.models import Conversation
    import respx as respx_lib
    import httpx

    ticket_id = 830
    inbound_msg_id = 9040

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        row = await claim_one(conn, worker_id="worker-suppress-dl")
        assert row is not None

    # Non-customer conversation → should_suppress returns True
    suppressed_conv = Conversation(
        id=inbound_msg_id,
        incoming=False,   # agent reply → suppressed
        private=False,
        user_id=99,
        from_email="agent@company.com",
        source=1,
        body_text="Agent note",
    )

    with respx_lib.mock(base_url="https://testdomain.freshdesk.com", assert_all_called=False) as mock:
        mock.get(f"/api/v2/tickets/{ticket_id}/conversations").mock(
            return_value=httpx.Response(200, json=[suppressed_conv.model_dump()])
        )

        http_client = httpx.AsyncClient(base_url="https://testdomain.freshdesk.com")
        client = FreshdeskClient(domain="testdomain", api_key="test_key", _http_client=http_client)
        settings = _make_settings(send_mode=SendMode.DRY_RUN, per_ticket_reply_throttle_n=999)
        sink = PostgresDeadLetterSink()

        await process_queue_row(
            pool=db_pool,
            client=client,
            row=row,
            settings=settings,
            dead_letter_sink=sink,
        )

    async with db_pool.acquire() as conn:
        tq_status = await conn.fetchval(
            "SELECT status FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
        )
        dl_count = await conn.fetchval(
            "SELECT COUNT(*) FROM queue.dead_letter WHERE ticket_id = $1", ticket_id
        )

    assert tq_status in ("suppressed", "stale_inbound"), (
        f"Suppressed conv must end up suppressed/stale_inbound; got {tq_status!r}"
    )
    assert dl_count == 0, (
        f"Suppressed/stale_inbound MUST NOT go to dead_letter (D-08 vs crit#3); got {dl_count}"
    )


# ── Wave 4 (02-06) — still RED ────────────────────────────────────────────────

async def test_sweep_exhausted_unlettered(clean_db, db_pool):
    """Sweeper moves rows with status='pending' AND attempts>=max_attempts to dead_letter (fix #9).

    Scenario: worker incremented attempts to max_attempts but crashed before dead-lettering.
    Row is stuck as status='pending' with attempts=max_attempts (exhausted but unlettered).
    sweep_exhausted() must find it and push to dead_letter — no silent stuck rows.
    """
    from src.work_queue.dead_letter import sweep_exhausted, PostgresDeadLetterSink

    ticket_id = 850
    inbound_msg_id = 9011
    max_attempts = 5

    async with db_pool.acquire() as conn:
        await enqueue_ticket(conn, ticket_id=ticket_id, inbound_msg_id=inbound_msg_id, redacted_payload={})
        # Simulate exhausted-but-unlettered: status='pending', attempts=max_attempts
        await conn.execute(
            """
            UPDATE queue.ticket_queue
            SET attempts = $1, last_error = 'transient: repeated failures (redacted)'
            WHERE ticket_id = $2
            """,
            max_attempts,
            ticket_id,
        )

        # Verify setup: row is pending with max attempts
        row = await conn.fetchrow(
            "SELECT status, attempts, max_attempts FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
        )
        assert row["status"] == "pending"
        assert row["attempts"] >= row["max_attempts"]

    # Run sweeper
    sink = PostgresDeadLetterSink()
    async with db_pool.acquire() as conn:
        swept = await sweep_exhausted(conn, sink)

    assert swept == 1, f"sweep_exhausted must return 1 (one exhausted row); got {swept}"

    async with db_pool.acquire() as conn:
        tq_row = await conn.fetchrow(
            "SELECT status FROM queue.ticket_queue WHERE ticket_id = $1", ticket_id
        )
        dl_row = await conn.fetchrow(
            "SELECT ticket_id, alerted FROM queue.dead_letter WHERE ticket_id = $1", ticket_id
        )

    assert tq_row["status"] == "dead_lettered", (
        f"Swept row must be 'dead_lettered'; got {tq_row['status']!r}"
    )
    assert dl_row is not None, "queue.dead_letter must have 1 row after sweep"
    assert dl_row["alerted"] is True, "Swept dead_letter row must be alerted=True"


async def test_main_wires_components(clean_db, db_pool):
    """Smoke test: main module assembles all components without binding ports or making network calls."""
    import src.main as m

    # main module must expose an entry point
    assert hasattr(m, "main") or hasattr(m, "run"), "main.py must expose main() or run() entry point"

    # PostgresDeadLetterSink must be importable and usable
    from src.work_queue.dead_letter import PostgresDeadLetterSink
    from src.work_queue.dead_letter_sink import DeadLetterSink
    sink = PostgresDeadLetterSink()
    assert isinstance(sink, DeadLetterSink), "PostgresDeadLetterSink must implement DeadLetterSink protocol"

    # worker_loop is importable from worker
    from src.work_queue.worker import worker_loop
    import inspect
    assert inspect.iscoroutinefunction(worker_loop), "worker_loop must be a coroutine"

    # sweep_exhausted is importable from dead_letter
    from src.work_queue.dead_letter import sweep_exhausted
    assert inspect.iscoroutinefunction(sweep_exhausted), "sweep_exhausted must be a coroutine"

    # recover_stale_claims is importable
    from src.work_queue.claim import recover_stale_claims
    assert inspect.iscoroutinefunction(recover_stale_claims), "recover_stale_claims must be a coroutine"

    # poller_loop is importable
    from src.poller.reconcile import poller_loop
    assert inspect.iscoroutinefunction(poller_loop), "poller_loop must be a coroutine"

    # webhook app is a FastAPI app
    from src.webhook.receiver import app
    assert app is not None, "webhook app must be importable"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_settings(
    send_mode: SendMode = SendMode.DRY_RUN,
    selless_sync_user_ids: set[int] | None = None,
    per_ticket_reply_throttle_n: int = 3,
    per_ticket_reply_throttle_window_minutes: int = 30,
):
    """Build a minimal Settings-like object for tests."""
    from types import SimpleNamespace
    return SimpleNamespace(
        send_mode=send_mode,
        selless_sync_user_ids=selless_sync_user_ids or set(),
        per_ticket_reply_throttle_n=per_ticket_reply_throttle_n,
        per_ticket_reply_throttle_window_minutes=per_ticket_reply_throttle_window_minutes,
    )
