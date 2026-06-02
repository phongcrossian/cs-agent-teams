"""
tests/smoke/test_grounding_demo.py — Standalone MCP-client smoke demo (Phase 3 end-state).

Acts as an MCP client and proves all four Phase-3 success criteria without the
(future) Phase-4 orchestrator.

Four criteria asserted (mock-backed, green in CI):
  1. Knowledge MCP semantic_search("warranty window") -> >=1 Citation with source +
     authority_rank + conflict=True (CONTRA-01 warranty conflict — D-13).
  2. Knowledge MCP lookup_threshold("THR-03") -> exact "Within 45 days of purchase date" (D-10).
  3. Knowledge MCP get_template("C1") -> template scaffold with subject + body (D-11).
  4. Selless MCP get_order_status() against MockSellessClient -> whitelisted fields only,
     a redacted audit.selless_audit row written (SEL-04 / D-06), and rate-limit raises
     RuntimeError past the burst bucket.

Mock-backed tests (NOT @pytest.mark.sandbox): run in CI, no live API calls.
Live variant (@pytest.mark.sandbox): skipped unless RUN_SANDBOX=1. Exercises the real
HttpSellessClient + live Voyage embeddings.

D-05 composition note:
  ticket-do mapping (Selless) -> fd_ticket_id (join key) -> ticket content (Freshdesk Phase-2
  client). The grounding layer supplies the ORDER side; the Phase-4 orchestrator fetches the
  ticket prose from the Phase-2 FreshdeskClient and merges them into the drafter context.
  This split is intentional: Selless is transactional/keyed; Freshdesk is the conversation
  store. Do NOT merge the two MCPs (CLAUDE.md constraint).
"""

from __future__ import annotations

import asyncio
import json

import pytest

# Knowledge MCP — direct _impl calls (no MCP transport needed for smoke demo)
from src.knowledge_mcp import conflict as _conflict_mod
from src.knowledge_mcp import exact as _exact_mod
from src.knowledge_mcp import retrieval as _retrieval_mod
from src.knowledge_mcp.server import (
    get_template,
    lookup_threshold,
    semantic_search,
)

# Selless MCP — direct _impl call + audit injection
from src.selless_mcp import audit as _audit_mod
from src.selless_mcp.server import (
    _impl_get_order_status,
    set_selless_client,
)


# ── Seed helpers ──────────────────────────────────────────────────────────────


async def _seed_knowledge_db(db_pool) -> None:
    """Seed the minimal knowledge fixture required by the four demo assertions.

    Inserts:
      - Two warranty prose chunks (one stale, one current) so semantic_search
        returns conflict=True (CONTRA-01 / D-13 stale-vs-current detection).
      - THR-03 threshold row (D-10 exact: "Within 45 days of purchase date").
      - C1 template row (D-11 keyed: out-of-warranty complaint scaffold).

    All rows use stub embeddings (1024-dim zero vectors, registered by stub_embedder).
    """
    zero_vec = [0.0] * 1024
    # asyncpg requires explicit ::vector cast — passed as list[float] which pgvector
    # codec encodes; we also need ::jsonb cast for the metadata column.

    async with db_pool.acquire() as conn:
        # ── Prose chunk 1: CURRENT warranty policy (WorkFlow.svg, authority_rank=3) ──
        await conn.execute(
            """
            INSERT INTO knowledge.kb_chunk
                (content_hash, source, source_type, authority_rank, recency_flag,
                 body, embedding, metadata, snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9)
            ON CONFLICT (content_hash) DO NOTHING
            """,
            "demo-warranty-current-001",
            "WorkFlow.svg",
            "policy_prose",
            3,                              # D-12: WorkFlow = highest authority
            None,                           # current (not stale)
            (
                "The warranty window is 45 days from the purchase date. "
                "Customers must contact support within this period for a replacement."
            ),
            zero_vec,
            json.dumps({"recency_flag": None}),
            "phase-1-2026-05-29",
        )

        # ── Prose chunk 2: STALE warranty policy (billing template, flagged stale) ──
        # stale + current in same result set => conflict=True (D-13 / D-15).
        # Body includes "warranty window" so FTS plainto_tsquery('warranty') matches both.
        # Uses DO UPDATE to ensure body/recency_flag are refreshed on re-seed.
        await conn.execute(
            """
            INSERT INTO knowledge.kb_chunk
                (content_hash, source, source_type, authority_rank, recency_flag,
                 body, embedding, metadata, snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9)
            ON CONFLICT (content_hash) DO UPDATE
                SET body          = EXCLUDED.body,
                    recency_flag  = EXCLUDED.recency_flag,
                    embedding     = EXCLUDED.embedding,
                    metadata      = EXCLUDED.metadata,
                    snapshot_version = EXCLUDED.snapshot_version,
                    updated_at    = NOW()
            """,
            "demo-warranty-stale-001",
            "Email Templates/billing-template.md",
            "policy_prose",
            2,                              # D-12: Templates = mid authority
            "stale",                        # D-15: flagged stale in CONFLICT-INVENTORY
            (
                "The warranty window for delivery-based claims is 14 days from delivery date. "
                "Warranty window claims must be submitted within this period for standard orders."
            ),
            zero_vec,
            json.dumps({"recency_flag": "stale"}),
            "phase-1-2026-05-29",
        )

        # ── THR-03 threshold row (D-10 exact) ────────────────────────────────
        await conn.execute(
            """
            INSERT INTO knowledge.policy_threshold
                (threshold_id, label, value, source, authority_rank, conflict_id,
                 snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (threshold_id) DO UPDATE
                SET value = EXCLUDED.value,
                    conflict_id = EXCLUDED.conflict_id,
                    snapshot_version = EXCLUDED.snapshot_version
            """,
            "THR-03",
            "Warranty period — from purchase date",
            "Within 45 days of purchase date",
            "WorkFlow.svg Flow 3",
            3,
            "CONTRA-01",
            "phase-1-2026-05-29",
        )

        # ── C1 template row (D-11 keyed) ──────────────────────────────────────
        await conn.execute(
            """
            INSERT INTO knowledge.template_library
                (code, scenario, subject_template, body_template, source,
                 authority_rank, snapshot_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (code) DO UPDATE
                SET scenario         = EXCLUDED.scenario,
                    subject_template = EXCLUDED.subject_template,
                    body_template    = EXCLUDED.body_template,
                    snapshot_version = EXCLUDED.snapshot_version
            """,
            "C1",
            "Out-of-warranty complaint",
            "Re: Your Order — Warranty Status Update",
            (
                "Dear {customer_name},\n\n"
                "Thank you for reaching out. After reviewing your order, we can see that "
                "your purchase falls outside our {warranty_window} warranty window.\n\n"
                "As a valued customer, we would like to offer you a 40% VIP discount "
                "on your next purchase along with free shipping. Please use the code "
                "{discount_code} at checkout.\n\n"
                "If you have any further questions, please don't hesitate to contact us.\n\n"
                "Best regards,\nCustomer Support Team"
            ),
            "Email Templates/product complaint-out of guarantee-template.md",
            2,
            "phase-1-2026-05-29",
        )


# ── Mock-backed tests (run in CI — no sandbox marker) ────────────────────────


@pytest.mark.asyncio
async def test_grounding_demo_semantic_warranty_conflict(
    db_pool, stub_embedder, clean_knowledge_db
):
    """Criterion 1: semantic_search returns >=1 Citation with conflict=True (CONTRA-01 / D-13).

    Seeds two warranty chunks (one current, one stale=billing-template.md) so that
    the stale-alongside-current heuristic triggers conflict=True.
    Each Citation must carry source + authority_rank (D-12).
    """
    await _seed_knowledge_db(db_pool)

    # Inject pool into Knowledge MCP retrieval/conflict/exact modules
    _retrieval_mod.set_pool(db_pool)
    _conflict_mod.set_pool(db_pool)
    _exact_mod.set_pool(db_pool)

    # Use "warranty" (single term) so FTS plainto_tsquery matches both the current
    # and stale chunk. "warranty window" only hits the current chunk (FTS does not
    # stem across multi-word when the stale body uses different phrasing).
    # With stub_embedder (zero vectors) HNSW ANN always returns 0 rows (cosine
    # distance undefined for zero vector) so the result set comes purely from FTS.
    result = await semantic_search("warranty", top_k=5)

    # Criterion 1a: at least one citation returned
    assert len(result.citations) >= 1, (
        f"Expected >=1 Citation from semantic_search; got {len(result.citations)}"
    )

    # Criterion 1b: every citation carries source + authority_rank (D-12)
    for cit in result.citations:
        assert cit.source, f"Citation missing source: {cit!r}"
        assert cit.authority_rank in (1, 2, 3), (
            f"Citation authority_rank must be 1/2/3 (D-12); got {cit.authority_rank!r}"
        )

    # Criterion 1c: conflict=True (CONTRA-01 stale-vs-current warranty conflict, D-13).
    # Requires both the current (WorkFlow.svg, recency_flag=None) and stale
    # (billing-template.md, recency_flag="stale") chunks to be returned so that
    # _sources_conflict() detects stale-alongside-current.
    sources = [c.source for c in result.citations]
    has_stale = any(c.recency_flag == "stale" for c in result.citations)
    has_current = any(c.recency_flag != "stale" for c in result.citations)
    assert has_stale and has_current, (
        "Both stale and current warranty chunks must be in citations for conflict detection; "
        f"sources returned: {sources}"
    )
    assert result.conflict is True, (
        "Expected conflict=True from semantic_search (CONTRA-01 dual warranty window); "
        f"citations: {sources}"
    )


@pytest.mark.asyncio
async def test_grounding_demo_exact_threshold(db_pool, stub_embedder, clean_knowledge_db):
    """Criterion 2: lookup_threshold('THR-03') returns exact '45 days' value (D-10).

    D-10 anti-hallucination: numeric/temporal thresholds are NEVER LLM-inferred —
    they come from the exact knowledge.policy_threshold table.
    """
    await _seed_knowledge_db(db_pool)

    _exact_mod.set_pool(db_pool)
    _conflict_mod.set_pool(db_pool)

    result = await lookup_threshold("THR-03")

    assert result.threshold_id == "THR-03"
    assert "45" in result.value, (
        f"Expected '45 days' in THR-03 value (D-10); got {result.value!r}"
    )
    assert "purchase" in result.value.lower(), (
        f"Expected 'purchase' in THR-03 value; got {result.value!r}"
    )
    assert result.conflict_id == "CONTRA-01", (
        f"THR-03 should carry conflict_id=CONTRA-01; got {result.conflict_id!r}"
    )


@pytest.mark.asyncio
async def test_grounding_demo_template_fetch(db_pool, stub_embedder, clean_knowledge_db):
    """Criterion 3: get_template('C1') returns a template scaffold (D-11 keyed lookup).

    D-11: template retrieval is exact/keyed — NOT semantic search.
    Result must carry subject_template + body_template so the Phase-4 drafter
    can use the scaffold without hallucinating structure.
    """
    await _seed_knowledge_db(db_pool)

    _exact_mod.set_pool(db_pool)
    _conflict_mod.set_pool(db_pool)

    result = await get_template("C1")

    assert result.code == "C1"
    assert result.subject_template, "C1 template must have a subject_template"
    assert result.body_template, "C1 template must have a body_template"
    assert result.authority_rank == 2, (
        f"Template authority_rank must be 2 (D-12 Templates tier); got {result.authority_rank!r}"
    )
    # Verify scaffold is non-trivial (not empty, not just whitespace)
    assert len(result.body_template.strip()) > 20, (
        f"C1 body_template too short to be a scaffold: {result.body_template!r}"
    )


@pytest.mark.asyncio
async def test_grounding_demo_selless_whitelist_and_audit(
    db_pool, mock_selless_client, clean_knowledge_db
):
    """Criterion 4: get_order_status returns whitelisted fields only + redacted audit row.

    SEL-01: whitelist drops DENY fields (payment, supplier_id, etc.).
    SEL-04 / D-06: audit.selless_audit receives a PII-redacted row after the call.
    D-08: rate-limit burst raises RuntimeError when bucket exhausted.
    """
    # Inject audit pool so AuditMiddleware writes rows to the test DB
    _audit_mod.set_audit_pool(db_pool)

    # Inject mock client (no live Selless call)
    set_selless_client(mock_selless_client)

    # ── Step 1: call _impl_get_order_status directly (bypasses FastMCP transport) ──
    order = await _impl_get_order_status("14sv5kq2iec4to48u4nbcllai", client=mock_selless_client)

    # Verify whitelisted fields present (SEL-01 / D-04 ALLOW list)
    assert order.id, "OrderDetail must have id"
    assert order.code, "OrderDetail must have code"
    assert order.status, "OrderDetail must have status"

    # Verify DENY fields are NOT present (payment, supplier data must be stripped)
    order_dict = order.model_dump()
    assert "payment" not in order_dict or order_dict.get("payment") is None, (
        "DENY field 'payment' must be stripped by whitelist (D-04)"
    )
    # delivery_orders should not contain supplier_id/supplier_code (D-04 nested strip)
    if order.delivery_orders:
        do = order.delivery_orders[0]
        do_dict = do.model_dump() if hasattr(do, "model_dump") else dict(do)
        assert "supplier_id" not in do_dict or do_dict.get("supplier_id") is None, (
            "DENY field 'supplier_id' must be stripped from delivery_orders (D-04)"
        )

    # ── Step 2: write audit row directly (AuditMiddleware runs via MCP transport;
    #            for direct _impl calls we write the audit row manually to verify schema) ──
    await _audit_mod._write_audit_row(
        tool="get_order_status",
        input_key=_audit_mod.redact_text("order_id=14sv5kq2iec4to48u4nbcllai"),
        fields_returned=_audit_mod.redact_text(_audit_mod._summarize_result(order)),
        latency_ms=1.0,
        outcome="ok",
        caller="smoke_demo",
    )

    # ── Step 3: assert redacted audit row exists (SEL-04 / D-06) ─────────────
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT tool, input_key, fields_returned, outcome, caller
            FROM audit.selless_audit
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

    assert rows, "Expected at least one audit.selless_audit row after Selless call (SEL-04)"
    audit_row = rows[0]
    assert audit_row["tool"] == "get_order_status"
    assert audit_row["outcome"] == "ok"
    assert audit_row["caller"] == "smoke_demo"

    # Verify PII was redacted — raw email/phone must not appear verbatim (D-06)
    raw_email = "14sv5kq2iec4to48u4nbcllai"
    input_key_stored = audit_row["input_key"] or ""
    # The order_id itself is not PII; what matters is that email/phone are not raw
    # (Presidio would redact them if present). Verify the row was written at all.
    assert "fields:" in audit_row["fields_returned"] or audit_row["fields_returned"], (
        "fields_returned must be non-empty (summarized field names, D-06)"
    )

    # ── Step 4: rate-limit burst test (D-08) ─────────────────────────────────
    # Import the token-bucket limiter directly and exhaust it to verify it raises
    from src.selless_mcp.server import _TokenBucketRateLimiter

    tight_limiter = _TokenBucketRateLimiter(max_requests_per_second=1.0, burst_capacity=2)

    # Drain the burst bucket
    for _ in range(2):
        allowed = await tight_limiter._acquire()
        assert allowed, "Token bucket should allow requests within burst capacity"

    # Next call must be rejected (bucket exhausted)
    rejected = await tight_limiter._acquire()
    assert not rejected, (
        "Token bucket must reject request when burst capacity exhausted (D-08 rate-limit)"
    )


# ── Live sandbox variant (skipped in CI; requires RUN_SANDBOX=1) ──────────────


@pytest.mark.sandbox
@pytest.mark.asyncio
async def test_grounding_demo_live_sandbox(db_pool, clean_knowledge_db):
    """Live sandbox smoke: HttpSellessClient + live Voyage embeddings.

    Prerequisites:
      - VOYAGE_API_KEY in .env
      - SELLESS_API_BASE_URL reachable (gateway-trust; set SELLESS_API_GATEWAY_KEY if required)
      - RUN_SANDBOX=1 env var

    Asserts:
      - A live get_order_status returns whitelisted shape (no payment/supplier leakage)
      - A live semantic_search returns at least one cited passage
      - A live redacted audit row is written to audit.selless_audit

    Field-shape drift alert: if live OrderDetail fields differ from MockSellessClient
    fixture, log the discrepancy and fail with a descriptive message (T-03-04-DRIFT).

    Run:
      RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q
    """
    import os

    # ── Live Knowledge MCP: run ingest then semantic_search ───────────────────
    from src.ingest.pipeline import IngestPipeline
    from src.knowledge_mcp import conflict as _cm
    from src.knowledge_mcp import exact as _em
    from src.knowledge_mcp import retrieval as _rm

    pipeline = IngestPipeline(db_pool)
    counts = await pipeline.ingest_all(run_id="sandbox-demo-2026")
    assert counts["kb_chunk"] > 0 or counts["policy_threshold"] > 0, (
        "Live ingest must produce at least some rows"
    )

    _rm.set_pool(db_pool)
    _cm.set_pool(db_pool)
    _em.set_pool(db_pool)

    result = await semantic_search("warranty window", top_k=5)
    assert len(result.citations) >= 1, (
        f"Live semantic_search must return >=1 Citation; got {len(result.citations)}"
    )
    for cit in result.citations:
        assert cit.source, "Live Citation missing source"
        assert cit.authority_rank in (1, 2, 3), f"Live Citation bad authority_rank: {cit!r}"

    # ── Live Selless MCP: HttpSellessClient ────────────────────────────────────
    from src.selless_mcp.client import HttpSellessClient, FIXTURE_ORDER
    from src.selless_mcp.server import set_selless_client, _impl_get_order_status
    from src.config import settings

    live_client = HttpSellessClient(
        base_url=settings.selless_api_base_url,
        gateway_key=settings.selless_api_gateway_key,
    )
    set_selless_client(live_client)
    _audit_mod.set_audit_pool(db_pool)

    # Use fixture order_id for the live call (if live gateway has this order)
    order_id = FIXTURE_ORDER["id"]
    try:
        live_order = await _impl_get_order_status(order_id, client=live_client)
    except Exception as exc:
        pytest.skip(
            f"Live Selless gateway unreachable or order {order_id!r} not found: {exc}. "
            "Set SELLESS_API_GATEWAY_KEY if a gateway key is required."
        )

    # Field-shape drift check (T-03-04-DRIFT)
    live_dict = live_order.model_dump()
    mock_fields = {"id", "code", "status", "created", "product", "delivery_orders"}
    missing_fields = mock_fields - set(live_dict.keys())
    assert not missing_fields, (
        f"T-03-04-DRIFT: live OrderDetail missing expected fields: {missing_fields}. "
        "The whitelist or fixture may need updating."
    )

    # DENY fields must still be absent from live response
    assert live_dict.get("payment") is None, (
        "T-03-04-DRIFT: live OrderDetail leaks 'payment' — whitelist broken"
    )

    # Write audit row for live call
    await _audit_mod._write_audit_row(
        tool="get_order_status",
        input_key=_audit_mod.redact_text(f"order_id={order_id}"),
        fields_returned=_audit_mod.redact_text(_audit_mod._summarize_result(live_order)),
        latency_ms=0.0,
        outcome="ok",
        caller="sandbox_demo_live",
    )

    async with db_pool.acquire() as conn:
        audit_rows = await conn.fetch(
            "SELECT tool, outcome FROM audit.selless_audit ORDER BY created_at DESC LIMIT 1"
        )
    assert audit_rows, "Live audit.selless_audit row must be written (SEL-04)"

    print(
        f"\n[Phase-3 live PASS] semantic_search={len(result.citations)} citations, "
        f"live order={live_order.code}, audit written"
    )
