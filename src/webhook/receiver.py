"""
receiver.py — FastAPI webhook receiver for Freshdesk events.

Security contract (T-02-15, T-02-17, T-02-18):
  - HMAC-SHA256 signature verified BEFORE any I/O (verify_signature with compare_digest).
  - Raw body is NEVER logged (may contain PII).
  - Only ticket_id (int) is extracted from payload — no other field used in downstream logic.

Design: RESOLVE-THEN-ENQUEUE (D-02).
  Uses resolve_inbound_and_enqueue from src.poller.reconcile — the shared helper
  (single definition, imported by both webhook and poller).

Health endpoint: GET /health → 200.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request, Response

from src.poller.reconcile import resolve_inbound_and_enqueue
from src.webhook.signature import verify_signature

logger = logging.getLogger(__name__)

app = FastAPI(title="Freshdesk Webhook Receiver")

# ── Test injection point (set by tests to bypass pool creation) ───────────────
# Tests set receiver._test_pool = db_pool so that the receiver uses the test pool.
_test_pool: asyncpg.Pool | None = None


# ── Internal pool factory ─────────────────────────────────────────────────────

async def _get_pool() -> asyncpg.Pool:
    """Return test pool if injected; otherwise create a new pool from env."""
    if _test_pool is not None:
        return _test_pool

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://csbot:csbot@localhost:5432/csbot"
    )
    return await asyncpg.create_pool(database_url, min_size=1, max_size=5)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — returns 200."""
    return {"status": "ok"}


@app.post("/webhook/freshdesk")
async def webhook_freshdesk(request: Request) -> dict[str, str]:
    """Receive a Freshdesk webhook event.

    1. Read raw body.
    2. If webhook_secret configured: verify HMAC-SHA256 signature BEFORE any I/O.
       Bad/missing signature → 401 (T-02-15 spoofing prevention).
    3. Parse JSON; extract ticket_id.
    4. Resolve latest inbound customer message (via should_suppress — fix #4).
    5. Enqueue with idempotency key = "ticket_id:inbound_msg_id" (D-02).

    Returns {"status": "queued"} or {"status": "ignored"}.
    NEVER logs raw body (T-02-17).
    """
    # ── Step 1: Read raw body ─────────────────────────────────────────────────
    body: bytes = await request.body()

    # ── Step 2: Verify signature (BEFORE any I/O) ─────────────────────────────
    webhook_secret_str = os.environ.get("WEBHOOK_SECRET", "")
    if webhook_secret_str:
        secret_bytes = webhook_secret_str.encode()
        signature = request.headers.get("X-Freshdesk-Signature")
        if not verify_signature(body, signature, secret_bytes):
            # Log only that verification failed — no raw body or key (T-02-17)
            logger.warning("webhook_signature_invalid")
            raise HTTPException(status_code=401, detail="Invalid or missing signature")

    # ── Step 3: Parse JSON, extract ticket_id (T-02-18: only extract int) ─────
    try:
        import json
        data: dict[str, Any] = json.loads(body)
    except Exception:
        logger.warning("webhook_json_parse_error")
        return {"status": "ignored", "reason": "invalid_json"}

    ticket_id: int | None = None
    ticket_obj = data.get("ticket")
    if isinstance(ticket_obj, dict):
        ticket_id = ticket_obj.get("id")
    if ticket_id is None:
        ticket_id = data.get("ticket_id")

    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.info("webhook_no_ticket_id")
        return {"status": "ignored", "reason": "no_ticket_id"}

    # ── Step 4+5: Resolve inbound message + enqueue ───────────────────────────
    # Import settings lazily to allow env override in tests
    from src.config import Settings
    s = Settings()

    freshdesk_domain = os.environ.get("FRESHDESK_DOMAIN", s.freshdesk_domain)
    freshdesk_api_key = os.environ.get("FRESHDESK_API_KEY", s.freshdesk_api_key)

    from src.freshdesk_io.client import FreshdeskClient
    import httpx

    # Use respx-compatible httpx client (tests mock at httpx level)
    http_client = httpx.AsyncClient(
        auth=(freshdesk_api_key, "X"),
        base_url=f"https://{freshdesk_domain}.freshdesk.com",
        timeout=30.0,
    )
    client = FreshdeskClient(
        domain=freshdesk_domain,
        api_key=freshdesk_api_key,
        _http_client=http_client,
    )

    pool = await _get_pool()
    async with pool.acquire() as conn:
        # Minimal payload (no raw body — T-02-17)
        payload: dict[str, Any] = {"ticket_id": ticket_id}
        inserted = await resolve_inbound_and_enqueue(
            client,
            conn,
            ticket_id,
            payload,
            selless_sync_user_ids=s.selless_sync_user_ids,
        )

    logger.info(
        "webhook_processed",
        extra={"ticket_id": ticket_id, "queued": inserted},
    )
    return {"status": "queued" if inserted else "ignored"}
