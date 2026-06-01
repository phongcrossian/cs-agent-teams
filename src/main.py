"""
main.py — Entry point: webhook (uvicorn) + poller_loop + worker_loop + stale-recovery +
exhausted-sweeper running concurrently as a single process.

Architecture (D-09, D-11):
  - FastAPI webhook server: receives Freshdesk webhook events → resolve-then-enqueue.
  - Poller loop: reconciliation cadence (~5-15 min) with durable checkpoint (fix #3).
  - Worker loop: sequential SKIP LOCKED claim→process loop (D-11).
  - Stale-claim recovery: sweeps rows stuck in 'claimed' back to 'pending' (~10 min).
  - Exhausted-row sweeper: sweeps status='pending' rows with attempts>=max_attempts
    to dead_letter (fix #9 — no silent stuck rows).

DESIGN NOTE — webhook resolve-in-request:
  The webhook receiver calls resolve_inbound_and_enqueue() (which calls GET /conversations)
  synchronously before returning HTTP 200. If Freshdesk is slow or rate-limits (429),
  the webhook response may be delayed and Freshdesk may re-fire the webhook.
  Phase 2 accepts this trade-off: the poller (durable checkpoint, fix #3) is the
  backstop reconciliation path for events that are missed or duplicated — dedup is handled
  by ON CONFLICT DO NOTHING on idempotency_key (D-02). Optimizing to async webhook
  processing (return 200 immediately, resolve asynchronously) is a Phase 3+ concern.

Startup logging:
  Logs send_mode at startup (never logs API key, webhook secret, or any PII — D-12).

Graceful shutdown:
  SIGTERM/SIGINT → cancel all tasks → close pool + HTTP client.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

import asyncpg
import uvicorn

from src.config import Settings
from src.freshdesk_io.client import FreshdeskClient
from src.observability import configure_logging
from src.poller.reconcile import poller_loop
from src.webhook.receiver import app as webhook_app
from src.work_queue.claim import recover_stale_claims
from src.work_queue.dead_letter import PostgresDeadLetterSink, sweep_exhausted
from src.work_queue.worker import worker_loop

logger = logging.getLogger(__name__)

# ── Scheduler intervals ────────────────────────────────────────────────────────
_STALE_RECOVERY_INTERVAL_SECONDS = 600   # 10 minutes
_EXHAUSTED_SWEEP_INTERVAL_SECONDS = 600  # 10 minutes


async def _stale_recovery_scheduler(pool: asyncpg.Pool) -> None:
    """Periodically call recover_stale_claims to un-stick crashed-worker rows."""
    while True:
        try:
            async with pool.acquire() as conn:
                recovered = await recover_stale_claims(conn)
            if recovered:
                logger.info("stale_recovery_done", extra={"recovered": recovered})
        except Exception:
            logger.exception("stale_recovery_error")
        await asyncio.sleep(_STALE_RECOVERY_INTERVAL_SECONDS)


async def _exhausted_sweep_scheduler(pool: asyncpg.Pool, sink: PostgresDeadLetterSink) -> None:
    """Periodically sweep exhausted-unlettered rows to dead_letter (fix #9)."""
    while True:
        try:
            async with pool.acquire() as conn:
                swept = await sweep_exhausted(conn, sink)
            if swept:
                logger.info("exhausted_sweep_done", extra={"swept": swept})
        except Exception:
            logger.exception("exhausted_sweep_error")
        await asyncio.sleep(_EXHAUSTED_SWEEP_INTERVAL_SECONDS)


async def main() -> None:
    """Start all components and run until shutdown signal."""
    settings = Settings()
    configure_logging()

    # Log startup info — NEVER log secrets/PII (D-12)
    logger.info(
        "csbot_starting",
        extra={
            "send_mode": settings.send_mode.value,
            "freshdesk_domain": settings.freshdesk_domain,
            "poller_interval_seconds": settings.poller_interval_seconds,
        },
    )

    # ── Create shared resources ───────────────────────────────────────────────
    database_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool: asyncpg.Pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

    http_client = FreshdeskClient(
        domain=settings.freshdesk_domain,
        api_key=settings.freshdesk_api_key,
    )

    dead_letter_sink = PostgresDeadLetterSink()

    # ── uvicorn server config (programmatic — no bind yet) ───────────────────
    uv_config = uvicorn.Config(
        app=webhook_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    uv_server = uvicorn.Server(uv_config)

    # ── Collect all coroutines ────────────────────────────────────────────────
    tasks: list[asyncio.Task[Any]] = []

    async def _run_uvicorn() -> None:
        await uv_server.serve()

    loop = asyncio.get_running_loop()

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("csbot_shutdown_signal")
        uv_server.should_exit = True
        shutdown_event.set()
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    tasks = [
        asyncio.create_task(_run_uvicorn(), name="webhook"),
        asyncio.create_task(
            poller_loop(http_client, pool, settings),
            name="poller",
        ),
        asyncio.create_task(
            worker_loop(pool, http_client, settings, dead_letter_sink=dead_letter_sink),
            name="worker",
        ),
        asyncio.create_task(
            _stale_recovery_scheduler(pool),
            name="stale_recovery",
        ),
        asyncio.create_task(
            _exhausted_sweep_scheduler(pool, dead_letter_sink),
            name="exhausted_sweep",
        ),
    ]

    logger.info("csbot_running", extra={"tasks": [t.get_name() for t in tasks]})

    try:
        # Run until any task completes (or is cancelled on shutdown)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc:
                logger.exception("csbot_task_failed", exc_info=exc, extra={"task": task.get_name()})
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        logger.info("csbot_shutdown")
        await pool.close()
        # FreshdeskClient wraps an httpx.AsyncClient internally
        if hasattr(http_client, "_http_client"):
            await http_client._http_client.aclose()


def run() -> None:
    """Synchronous entry point for `python -m src.main` or script invocation."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
