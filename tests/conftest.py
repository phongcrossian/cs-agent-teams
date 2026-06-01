"""
Test configuration and fixtures.

Fixtures:
  - db_pool: asyncpg connection pool (requires DATABASE_URL env)
  - clean_db: truncate queue tables between tests
  - respx_mock: mock httpx calls to Freshdesk

Sandbox tests (marker: sandbox) are skipped unless RUN_SANDBOX=1 env var is set.
"""

from __future__ import annotations

import os

import pytest
import respx as respx_lib


# ── Sandbox skip ──────────────────────────────────────────────────────────────

def pytest_collection_modifyitems(config, items):
    """Skip tests marked `sandbox` unless RUN_SANDBOX=1 is set."""
    run_sandbox = os.environ.get("RUN_SANDBOX", "").strip() == "1"
    skip_sandbox = pytest.mark.skip(reason="Sandbox tests skipped (set RUN_SANDBOX=1 to run)")
    for item in items:
        if item.get_closest_marker("sandbox") and not run_sandbox:
            item.add_marker(skip_sandbox)


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
async def db_pool():
    """asyncpg connection pool for test database.

    Requires DATABASE_URL env var pointing to a test Postgres instance.
    Falls back to the default docker-compose URL.

    Function-scoped (not session) to avoid pytest-asyncio event-loop-scope
    mismatch between session fixtures and function-scoped test loops.
    """
    import asyncpg

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://csbot:csbot@localhost:5432/csbot"
    )
    # asyncpg expects postgresql:// (not postgresql+asyncpg://)
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture
async def clean_db(db_pool):
    """Truncate all queue tables before each test to ensure isolation.

    Also resets poller_checkpoint to a known state (fix review #3).
    """
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE queue.ticket_queue RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE queue.dead_letter RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE queue.dry_run_log RESTART IDENTITY CASCADE")
        # Reset checkpoint to seed state
        await conn.execute(
            """
            INSERT INTO queue.poller_checkpoint (id, last_since, updated_at)
            VALUES (1, NOW() - INTERVAL '1 hour', NOW())
            ON CONFLICT (id) DO UPDATE
                SET last_since = NOW() - INTERVAL '1 hour',
                    updated_at = NOW()
            """
        )
    yield


# ── HTTP mock fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def respx_mock():
    """respx mock router for Freshdesk httpx calls.

    Automatically activated and deactivated around each test.
    Base URL: https://<domain>.freshdesk.com
    """
    with respx_lib.mock(base_url="https://testdomain.freshdesk.com") as mock:
        yield mock
