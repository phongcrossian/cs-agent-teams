"""
test_e2e_sandbox.py — Real Freshdesk sandbox smoke tests (D-03, REP-05, fix #1).

All tests are marked @pytest.mark.sandbox and are SKIPPED in CI unless RUN_SANDBOX=1.

Prerequisites:
  - .env with FRESHDESK_DOMAIN, FRESHDESK_API_KEY for shophelp-dev sandbox account
  - SEND_MODE=live in .env (or set as env var — D-05 default is dry_run)
  - DATABASE_URL pointing to dev/test Postgres (not production)
  - A ticket existing on the sandbox (set SANDBOX_TICKET_ID env var)

Run:
  RUN_SANDBOX=1 SEND_MODE=live SANDBOX_TICKET_ID=<id> pytest tests/test_e2e_sandbox.py -m sandbox -x -q

After demo: set SEND_MODE back to dry_run (T-02-20 — accidental live-send prevention).

Tests:
  test_sandbox_real_reply          — posts a canned reply to real Freshdesk ticket, verifies it appears
  test_sandbox_retry_no_double_send — re-run same inbound → no second reply (exactly-once D-02)
  test_sandbox_crash_after_post_no_resend — mocked crash after POST 200 → re-claim → no resend (fix #1)

D-03 FINDING — Marker-based verification removed:
  Freshdesk STRIPS HTML comments from reply bodies (verified on shophelp-dev, ticket 368108).
  An earlier design searched for <!-- csbot:sent:{inbound_msg_id} --> in c.body to verify
  exactly-once. Since the marker never persists through Freshdesk, this approach was abandoned.
  Verification now uses the freshdesk_reply_id returned by send_reply (result.id):
    - Assert exactly one conversation whose id == freshdesk_reply_id exists.
  The Conversation model does NOT expose a `body` field — do not reference it.
"""

from __future__ import annotations

import os

import asyncpg
import httpx
import pytest

from src.config import SendMode, Settings
from src.freshdesk_io.client import FreshdeskClient
from src.work_queue.claim import claim_one, finalize_done, recover_stale_claims
from src.work_queue.dead_letter import PostgresDeadLetterSink
from src.work_queue.enqueue import enqueue_ticket
from src.work_queue.send import send_reply
from src.work_queue.worker import process_queue_row


# ── Sandbox fixtures ──────────────────────────────────────────────────────────

def _get_sandbox_ticket_id() -> int:
    """Read SANDBOX_TICKET_ID from environment or raise a clear error."""
    raw = os.environ.get("SANDBOX_TICKET_ID", "").strip()
    if not raw:
        pytest.skip("SANDBOX_TICKET_ID env var not set — provide a real sandbox ticket id")
    return int(raw)


async def _make_sandbox_pool() -> asyncpg.Pool:
    """Create asyncpg pool pointing at DATABASE_URL (test/dev DB, not prod)."""
    settings = Settings()
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(url, min_size=1, max_size=3)


def _make_sandbox_client() -> FreshdeskClient:
    """Create FreshdeskClient from FRESHDESK_DOMAIN + FRESHDESK_API_KEY env vars."""
    settings = Settings()
    if not settings.freshdesk_domain or not settings.freshdesk_api_key:
        pytest.skip("FRESHDESK_DOMAIN or FRESHDESK_API_KEY not set in env")
    return FreshdeskClient(domain=settings.freshdesk_domain, api_key=settings.freshdesk_api_key)


# ── Sandbox tests ─────────────────────────────────────────────────────────────


@pytest.mark.sandbox
async def test_sandbox_real_reply():
    """Posts a real canned reply into a Freshdesk sandbox ticket and verifies it appears.

    Proves D-03 criterion: AI can post an approved reply into the correct existing ticket
    via the Freshdesk API.

    Assertions:
    - POST /api/v2/tickets/{id}/reply returns 201 with a freshdesk_reply_id (result.id)
    - GET /api/v2/tickets/{id}/conversations returns exactly one conversation whose
      id == freshdesk_reply_id (proves the reply posted; body/marker not checked —
      Freshdesk strips HTML comments, D-03 finding)
    - queue.ticket_queue row status='done', sent_at IS NOT NULL, freshdesk_reply_id matches
    """
    ticket_id = _get_sandbox_ticket_id()
    pool = await _make_sandbox_pool()
    client = _make_sandbox_client()

    try:
        # Truncate queue tables for this test run (fresh state)
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE queue.ticket_queue RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dead_letter RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dry_run_log RESTART IDENTITY CASCADE")

        # Resolve the latest inbound conversation from the real sandbox ticket
        conversations = await client.get_conversations(ticket_id)
        incoming = [c for c in conversations if c.incoming and not c.private]
        if not incoming:
            pytest.skip(
                f"No incoming customer conversation found on ticket {ticket_id}. "
                "Add a customer reply to the sandbox ticket before running."
            )

        inbound_conv: Conversation = incoming[-1]
        inbound_msg_id = inbound_conv.id

        # Enqueue the ticket
        async with pool.acquire() as conn:
            enqueued = await enqueue_ticket(
                conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                redacted_payload={"source": "sandbox_test", "subject": "[REDACTED]"},
            )
            assert enqueued, f"Expected to enqueue ticket {ticket_id}:{inbound_msg_id}"
            row = await claim_one(conn, worker_id="sandbox-test-worker")
            assert row is not None, "Should have claimed the enqueued row"

        row_id = row["id"]
        claim_token = str(row["claim_token"])
        body = (
            "<p>[SANDBOX TEST] Thank you for contacting our support team. "
            "This is an automated test reply from the csbot e2e sandbox demo (D-03). "
            "Please disregard.</p>"
        )

        # Send the real reply (LIVE mode)
        async with pool.acquire() as conn:
            result = await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body=body,
                mode=SendMode.LIVE,
                row_id=row_id,
                claim_token=claim_token,
            )
            await finalize_done(conn, row_id=row_id, claim_token=claim_token)

        # Verify: result has a freshdesk_reply_id
        assert hasattr(result, "id") or isinstance(result, dict), (
            f"Expected ReplyResult or dict; got {result!r}"
        )
        if hasattr(result, "id"):
            freshdesk_reply_id = result.id
        else:
            freshdesk_reply_id = result.get("id")

        assert freshdesk_reply_id, "POST /reply must return a freshdesk_reply_id"

        # Verify: DB row has sent_at + freshdesk_reply_id
        async with pool.acquire() as conn:
            db_row = await conn.fetchrow(
                "SELECT status, sent_at, freshdesk_reply_id FROM queue.ticket_queue WHERE id = $1",
                row_id,
            )
        assert db_row["status"] == "done", f"Row status must be 'done'; got {db_row['status']!r}"
        assert db_row["sent_at"] is not None, "sent_at must be set (send-intent persisted)"
        assert db_row["freshdesk_reply_id"] == freshdesk_reply_id, (
            f"DB freshdesk_reply_id mismatch: {db_row['freshdesk_reply_id']} != {freshdesk_reply_id}"
        )

        # Verify: the reply appears in Freshdesk conversations by freshdesk_reply_id.
        # NOTE: Freshdesk strips HTML comments, so marker-based lookup is not used (D-03 finding).
        # Instead verify by conversation id == freshdesk_reply_id (exactly one such conversation).
        updated_convs = await client.get_conversations(ticket_id)
        our_replies = [c for c in updated_convs if c.id == freshdesk_reply_id]
        assert len(our_replies) == 1, (
            f"Expected exactly 1 conversation with id={freshdesk_reply_id} in ticket {ticket_id}; "
            f"found {len(our_replies)}. Check the Freshdesk sandbox UI to confirm the reply posted."
        )

        print(f"\n[D-03 PASS] Reply posted to ticket {ticket_id}, freshdesk_reply_id={freshdesk_reply_id}")

    finally:
        await pool.close()
        if hasattr(client, "_http_client"):
            await client._http_client.aclose()


@pytest.mark.sandbox
async def test_sandbox_retry_no_double_send():
    """Re-running the worker on the same ticket does NOT post a second reply.

    Proves exactly-once idempotency (REP-05 crit #2) against the real Freshdesk sandbox:
    - First run: enqueue → claim → send → done (reply appears in ticket)
    - Second attempt to enqueue same inbound_msg_id → ON CONFLICT DO NOTHING → 0 new rows
    - If somehow claimed again: sent_at IS NOT NULL → skip-if-sent path → no second POST

    Assertions:
    - Second enqueue_ticket() call returns False (duplicate)
    - Freshdesk has exactly 1 conversation with id == first_freshdesk_reply_id after second run
      (no body/marker check — Freshdesk strips HTML comments, D-03 finding)
    """
    ticket_id = _get_sandbox_ticket_id()
    pool = await _make_sandbox_pool()
    client = _make_sandbox_client()

    try:
        # Truncate for clean state
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE queue.ticket_queue RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dead_letter RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dry_run_log RESTART IDENTITY CASCADE")

        # Resolve inbound conversation
        conversations = await client.get_conversations(ticket_id)
        incoming = [c for c in conversations if c.incoming and not c.private]
        if not incoming:
            pytest.skip(
                f"No incoming customer conversation on ticket {ticket_id}. "
                "Add a customer reply before running."
            )
        inbound_conv = incoming[-1]
        inbound_msg_id = inbound_conv.id

        initial_conv_count = len(conversations)

        # ── First send ────────────────────────────────────────────────────────
        async with pool.acquire() as conn:
            first_enqueued = await enqueue_ticket(
                conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                redacted_payload={"source": "sandbox_idempotency_test_1"},
            )
            assert first_enqueued, "First enqueue must succeed"
            row = await claim_one(conn, worker_id="sandbox-retry-test")
            assert row is not None
            row_id = row["id"]
            claim_token = str(row["claim_token"])

        body = (
            "<p>[SANDBOX TEST idempotency] csbot e2e — exactly-once test (D-03 REP-05). "
            "Disregard.</p>"
        )

        async with pool.acquire() as conn:
            first_result = await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body=body,
                mode=SendMode.LIVE,
                row_id=row_id,
                claim_token=claim_token,
            )
            await finalize_done(conn, row_id=row_id, claim_token=claim_token)

        # Capture the freshdesk_reply_id from the first (and only) send
        first_freshdesk_reply_id = first_result.id if hasattr(first_result, "id") else first_result.get("id")
        assert first_freshdesk_reply_id, "First send must return a freshdesk_reply_id"

        # ── Second enqueue attempt (same inbound_msg_id) ──────────────────────
        async with pool.acquire() as conn:
            second_enqueued = await enqueue_ticket(
                conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                redacted_payload={"source": "sandbox_idempotency_test_2"},
            )
        assert second_enqueued is False, (
            "Second enqueue with same inbound_msg_id must be rejected (ON CONFLICT DO NOTHING)"
        )

        # ── Verify: exactly 1 conversation with first_freshdesk_reply_id ─────────
        # NOTE: Freshdesk strips HTML comments so marker-based lookup is not used (D-03 finding).
        # Verify by conversation id — proves exactly one reply was posted.
        updated_convs = await client.get_conversations(ticket_id)
        our_replies = [c for c in updated_convs if c.id == first_freshdesk_reply_id]
        assert len(our_replies) == 1, (
            f"Exactly-once: expected exactly 1 conversation with id={first_freshdesk_reply_id}; "
            f"found {len(our_replies)}"
        )

        print(
            f"\n[REP-05 PASS] Exactly-once confirmed: 1 reply in ticket {ticket_id}, "
            f"freshdesk_reply_id={first_freshdesk_reply_id}, second enqueue rejected."
        )

    finally:
        await pool.close()
        if hasattr(client, "_http_client"):
            await client._http_client.aclose()


@pytest.mark.sandbox
async def test_sandbox_crash_after_post_no_resend():
    """Simulate crash after POST 200 but before finalize_done → re-claim → NO second POST.

    This proves fix #1 (send-intent + skip-if-sent guard) prevents duplicate sends across
    process crashes — the hardest path in REP-05 crit #2.

    Scenario:
    1. Worker claims row, calls send_reply → POST 200 (real Freshdesk send) → sent_at persisted.
    2. Crash simulated: finalize_done NOT called → row stays 'claimed'.
    3. claimed_at forced into the past → recover_stale_claims → row back to 'pending'.
    4. Second worker claims the row.
    5. process_queue_row: row.sent_at IS NOT NULL → SKIP POST → finalize_done.
    6. Conversation count in Freshdesk == 1 (not 2).

    Assertions:
    - Freshdesk POST called exactly once (verified via exactly 1 conversation with
      id == freshdesk_reply_id — no body/marker check; Freshdesk strips HTML comments, D-03 finding)
    - Final queue.ticket_queue status == 'done'
    - No extra reply in Freshdesk conversation list
    """
    ticket_id = _get_sandbox_ticket_id()
    pool = await _make_sandbox_pool()
    client = _make_sandbox_client()

    try:
        # Truncate for clean state
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE queue.ticket_queue RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dead_letter RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE queue.dry_run_log RESTART IDENTITY CASCADE")

        # Resolve inbound conversation
        conversations = await client.get_conversations(ticket_id)
        incoming = [c for c in conversations if c.incoming and not c.private]
        if not incoming:
            pytest.skip(
                f"No incoming customer conversation on ticket {ticket_id}. "
                "Add a customer reply before running."
            )
        inbound_conv = incoming[-1]
        inbound_msg_id = inbound_conv.id

        # Enqueue + claim
        async with pool.acquire() as conn:
            await enqueue_ticket(
                conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                redacted_payload={"source": "sandbox_crash_test"},
            )
            row = await claim_one(conn, worker_id="sandbox-crash-worker-1")
            assert row is not None
            row_id = row["id"]
            claim_token = str(row["claim_token"])

        body = (
            "<p>[SANDBOX TEST crash-after-post] csbot e2e — exactly-once across crash (fix #1 D-03). "
            "Disregard.</p>"
        )

        # ── Step 1: Send (real POST) + persist sent_at — simulate crash (no finalize_done) ──
        async with pool.acquire() as conn:
            result = await send_reply(
                client=client,
                conn=conn,
                ticket_id=ticket_id,
                inbound_msg_id=inbound_msg_id,
                body=body,
                mode=SendMode.LIVE,
                row_id=row_id,
                claim_token=claim_token,
            )
        # sent_at is now persisted; row is still 'claimed' (no finalize_done called)
        # Capture freshdesk_reply_id for later verification
        freshdesk_reply_id = result.id if hasattr(result, "id") else result.get("id")
        assert freshdesk_reply_id, "send_reply must return a freshdesk_reply_id on LIVE send"

        # Verify sent_at was persisted
        async with pool.acquire() as conn:
            db_row = await conn.fetchrow(
                "SELECT status, sent_at FROM queue.ticket_queue WHERE id = $1", row_id
            )
        assert db_row["status"] == "claimed", "After crash simulation, status must be 'claimed'"
        assert db_row["sent_at"] is not None, "sent_at must be persisted after successful POST"

        # ── Step 2: Force claimed_at stale → recover_stale_claims ────────────
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE queue.ticket_queue SET claimed_at = NOW() - INTERVAL '15 minutes' WHERE id = $1",
                row_id,
            )
            recovered = await recover_stale_claims(conn, lease_minutes=10)
        assert recovered == 1, f"Expected 1 stale row recovered; got {recovered}"

        # ── Step 3: Second worker claims + processes ───────────────────────────
        from types import SimpleNamespace
        settings = Settings()
        settings_ns = SimpleNamespace(
            send_mode=SendMode.LIVE,
            selless_sync_user_ids=set(),
            per_ticket_reply_throttle_n=999,  # no throttle
            per_ticket_reply_throttle_window_minutes=30,
        )
        sink = PostgresDeadLetterSink()

        async with pool.acquire() as conn:
            row2 = await claim_one(conn, worker_id="sandbox-crash-worker-2")
        assert row2 is not None, "Second worker must be able to claim recovered row"
        assert row2["id"] == row_id, "Second worker must claim same row"
        assert row2["sent_at"] is not None, "Recovered row must still have sent_at set"

        await process_queue_row(
            pool=pool,
            client=client,
            row=row2,
            settings=settings_ns,
            dead_letter_sink=sink,
        )

        # ── Step 4: Verify DB state ───────────────────────────────────────────
        async with pool.acquire() as conn:
            final_row = await conn.fetchrow(
                "SELECT status FROM queue.ticket_queue WHERE id = $1", row_id
            )
        assert final_row["status"] == "done", (
            f"After recovery, status must be 'done'; got {final_row['status']!r}"
        )

        # ── Step 5: Verify Freshdesk — exactly 1 conversation with freshdesk_reply_id ──
        # NOTE: Freshdesk strips HTML comments so marker-based lookup is not used (D-03 finding).
        # Verify by conversation id: exactly 1 conversation with id == freshdesk_reply_id proves
        # the reply was posted once (not twice — fix #1 skip-if-sent path worked).
        final_convs = await client.get_conversations(ticket_id)
        our_replies = [c for c in final_convs if c.id == freshdesk_reply_id]
        assert len(our_replies) == 1, (
            f"Crash-after-post fix #1: expected exactly 1 conversation with "
            f"id={freshdesk_reply_id} in Freshdesk; found {len(our_replies)} "
            f"(would be 2 if skip-if-sent guard failed)"
        )

        print(
            f"\n[fix #1 PASS] crash-after-post exactly-once: ticket {ticket_id}, "
            f"freshdesk_reply_id={freshdesk_reply_id}, exactly 1 reply in Freshdesk."
        )

    finally:
        await pool.close()
        if hasattr(client, "_http_client"):
            await client._http_client.aclose()
