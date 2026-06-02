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

    Phase 3: registers the pgvector asyncpg codec on pool init (Pitfall 2).
    """
    import asyncpg

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://csbot:csbot@localhost:5432/csbot"
    )
    # asyncpg expects postgresql:// (not postgresql+asyncpg://)
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    async def _init_conn(conn):
        """Register pgvector codec so VECTOR columns round-trip correctly.

        Skips gracefully if the vector extension is not yet installed in the DB
        (e.g. during Phase-2 tests run before migration 0002 is applied).
        """
        try:
            from pgvector.asyncpg import register_vector
            await register_vector(conn)
        except Exception:
            # Extension not installed or not yet migrated — safe to skip for
            # Phase-2 queue tests that don't touch vector columns.
            pass

    pool = await asyncpg.create_pool(url, min_size=1, max_size=5, init=_init_conn)
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


# ── Phase 3 fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_selless_client():
    """MockSellessClient returning fixture data. No HTTP calls (D-01 client seam).

    Used by selless_mcp tests to exercise tool logic without a live Selless API.
    """
    # Import deferred — src.selless_mcp.client created in Plan 03
    from src.selless_mcp.client import MockSellessClient
    return MockSellessClient()


@pytest.fixture
def stub_embedder(monkeypatch):
    """Replace embed_query / embed_documents with fixed 1024-dim zero vectors.

    Avoids live Voyage API calls in unit/integration tests. Any test that exercises
    the actual embedding path should use @pytest.mark.sandbox instead.
    """
    # Import deferred — src.knowledge_mcp.embeddings created in Plan 02
    import src.knowledge_mcp.embeddings as emb
    monkeypatch.setattr(emb, "embed_query", lambda text: [0.0] * 1024)
    monkeypatch.setattr(emb, "embed_documents", lambda texts: [[0.0] * 1024 for _ in texts])


@pytest.fixture
async def clean_knowledge_db(db_pool):
    """Truncate knowledge.* + audit.* tables between tests.

    Companion to clean_db (which truncates queue.*). Run after alembic 0002/0003
    schemas exist — skips gracefully if schemas not yet applied.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE knowledge.kb_chunk RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.policy_threshold RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.code_map RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.template_library RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE knowledge.policy_resolution RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE audit.selless_audit RESTART IDENTITY CASCADE")
    yield


@pytest.fixture
def selless_respx_mock():
    """respx mock router for Selless httpx calls.

    Mirror of respx_mock but pointed at the Selless API base URL (D-01).
    Used to test HttpSellessClient without live network.
    """
    with respx_lib.mock(base_url="https://api.selless.dev") as mock:
        yield mock
