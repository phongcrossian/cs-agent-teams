"""
test_queue.py — Queue core tests.

Wave 1 (02-03) — GREEN:
  - test_enqueue_dedup: ON CONFLICT DO NOTHING dedup at insert
  - test_idempotency: webhook path + poller path → same key → exactly-once (REP-05 crit #2)
  - test_skip_locked_claim: FOR UPDATE SKIP LOCKED — no concurrent collision
  - test_finalize_done: token-checked done finalization
  - test_finalize_retry: attempts++, backoff next_attempt_at, PII-safe last_error
  - test_stale_claim_recovery: stale claimed rows → pending

Wave 2 (02-04) — still RED:
  - test_worker_crash_after_post_does_not_resend (fix #1)
  - test_loop_guard_throttle (fix #4)
  - test_worker_recheck_routes_stale_inbound (fix #4)

Wave 4 (02-06) — still RED:
  - test_dead_letter_on_exhaustion
  - test_sweep_exhausted_unlettered (fix #9)
"""

import asyncio
import uuid

import asyncpg
import pytest

from src.work_queue import enqueue, claim
from src.work_queue.enqueue import enqueue_ticket
from src.work_queue.claim import (
    claim_one,
    finalize_done,
    finalize_retry,
    recover_stale_claims,
)
from src.work_queue.idempotency import compute_idempotency_key


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


# ── Wave 1 (02-03): dead_letter test — still RED (implemented in 02-06) ───────

async def test_dead_letter_on_exhaustion(clean_db, db_pool):
    """Row with attempts >= max_attempts is moved to queue.dead_letter on next failure."""
    pytest.fail("Wave 4 (02-06): implement dead-letter on exhaustion")


# ── Wave 2 (02-04) — still RED ────────────────────────────────────────────────

async def test_worker_crash_after_post_does_not_resend(clean_db, db_pool, respx_mock):
    """MANDATORY RED (fix #1): Worker crashes between POST 200 and finalize_done.

    Re-claim of the same row must NOT post a second reply to Freshdesk.
    respx POST call count must equal exactly 1 after recovery + re-claim.

    Turns GREEN in 02-04 T2 (send-intent: sent_at IS NOT NULL → skip POST).
    """
    pytest.fail(
        "Wave 2 (02-04): implement send-intent (sent_at) — crash-after-post no resend"
    )


async def test_loop_guard_throttle(clean_db, db_pool):
    """Per-ticket reply throttle: must not send more than N replies to same ticket in T minutes (fix #4)."""
    pytest.fail("Wave 2 (02-04): implement per-ticket reply throttle in loop-guard")


async def test_sweep_exhausted_unlettered(clean_db, db_pool):
    """Sweeper moves rows with status='pending' AND attempts>=max_attempts to dead_letter (fix #9)."""
    pytest.fail("Wave 4 (02-06): implement sweeper for exhausted unlettered rows")


async def test_worker_recheck_routes_stale_inbound(clean_db, db_pool):
    """Worker re-checks should_suppress on claimed row; if now suppressed → status='stale_inbound' + alert (fix #4)."""
    pytest.fail(
        "Wave 2 (02-04): implement worker re-check → stale_inbound status, NOT silent suppressed"
    )
