"""
Tests for KB-03: ingest pipeline builds chunks + exact tables from snapshots.

Task 1 coverage: sources, normalize, chunk modules.
Task 2 coverage (TDD): IngestPipeline full run against real DB.
"""

from __future__ import annotations

import pytest

# ── Task 1: sources / normalize / chunk unit tests ───────────────────────────


class TestThresholdReader:
    """read_threshold_rows() acceptance criteria."""

    def setup_method(self):
        from src.ingest.sources import read_threshold_rows
        self.rows = read_threshold_rows()
        self.by_id = {r["threshold_id"]: r for r in self.rows}

    def test_returns_nonempty(self):
        """At least some threshold rows are parsed."""
        assert len(self.rows) > 0, "Expected threshold rows, got 0"

    def test_thr03_present(self):
        """THR-03 (45 days from purchase) is present as a distinct row."""
        assert "THR-03" in self.by_id, "THR-03 not found in threshold rows"

    def test_thr04_present(self):
        """THR-04 (14 days from delivery) is present as a distinct row."""
        assert "THR-04" in self.by_id, "THR-04 not found in threshold rows"

    def test_thr03_has_contra01_conflict_id(self):
        """THR-03 carries conflict_id=CONTRA-01 from CONFLICT-INVENTORY."""
        row = self.by_id["THR-03"]
        assert row["conflict_id"] == "CONTRA-01", (
            f"THR-03 conflict_id expected 'CONTRA-01', got {row['conflict_id']!r}"
        )

    def test_thr04_has_contra01_conflict_id(self):
        """THR-04 carries conflict_id=CONTRA-01 from CONFLICT-INVENTORY."""
        row = self.by_id["THR-04"]
        assert row["conflict_id"] == "CONTRA-01", (
            f"THR-04 conflict_id expected 'CONTRA-01', got {row['conflict_id']!r}"
        )

    def test_thr03_value_contains_45_days(self):
        """THR-03 value references '45 days'."""
        row = self.by_id["THR-03"]
        assert "45" in row["value"], f"THR-03 value should contain '45', got: {row['value']!r}"

    def test_thr04_value_contains_14_days(self):
        """THR-04 value references '14 days'."""
        row = self.by_id["THR-04"]
        assert "14" in row["value"], f"THR-04 value should contain '14', got: {row['value']!r}"


class TestProseSourceReader:
    """read_prose_sources() acceptance criteria."""

    def setup_method(self):
        from src.ingest.sources import read_prose_sources
        self.records = read_prose_sources()

    def test_returns_nonempty(self):
        assert len(self.records) > 0, "Expected prose records, got 0"

    def test_workflow_svg_rank_3(self):
        """WorkFlow.svg source has authority_rank=3 (D-12)."""
        workflow = [r for r in self.records if r["source"] == "WorkFlow.svg"]
        assert len(workflow) >= 1, "WorkFlow.svg record not found"
        assert workflow[0]["authority_rank"] == 3, (
            f"WorkFlow.svg authority_rank expected 3, got {workflow[0]['authority_rank']}"
        )

    def test_template_sources_rank_2(self):
        """Email template sources have authority_rank=2 (D-12)."""
        templates = [r for r in self.records if r["source"].startswith("Email Templates/")]
        assert len(templates) > 0, "No Email Templates records found"
        for r in templates:
            assert r["authority_rank"] == 2, (
                f"{r['source']} should have authority_rank=2, got {r['authority_rank']}"
            )

    def test_workflow_svg_body_nonempty(self):
        """WorkFlow.svg body is non-empty (SVG text extracted)."""
        workflow = [r for r in self.records if r["source"] == "WorkFlow.svg"]
        assert workflow, "WorkFlow.svg record missing"
        assert len(workflow[0]["body"]) > 100, "WorkFlow.svg body too short — SVG extraction failed"

    def test_stale_billing_template_flagged(self):
        """billing-template.md is flagged recency_flag='stale' (STALE-01)."""
        billing = [
            r for r in self.records
            if r["source"] == "Email Templates/billing-template.md"
        ]
        assert billing, "billing-template.md record not found"
        assert billing[0]["recency_flag"] == "stale", (
            "billing-template.md should have recency_flag='stale' (STALE-01)"
        )


class TestNormalizeText:
    """normalize_text() acceptance criteria."""

    def test_cee_expansion(self):
        """'CEE' expands to plain-English form."""
        from src.ingest.normalize import normalize_text
        result = normalize_text("CEE handles this")
        assert "CEE" not in result, "CEE should be expanded"
        assert "Customer Email Experience" in result, (
            f"Expected 'Customer Email Experience' in result, got: {result!r}"
        )

    def test_dnr_expansion(self):
        """'DNR' expands to 'Delivered Not Received'."""
        from src.ingest.normalize import normalize_text
        result = normalize_text("DNR ticket")
        assert "Delivered Not Received" in result, (
            f"Expected 'Delivered Not Received' in result, got: {result!r}"
        )

    def test_oos_expansion(self):
        """'OOS' expands to 'Out of Stock'."""
        from src.ingest.normalize import normalize_text
        result = normalize_text("OOS scenario")
        assert "Out of Stock" in result

    def test_rts_expansion(self):
        """'RTS' expands to 'Returned to Sender'."""
        from src.ingest.normalize import normalize_text
        result = normalize_text("RTS shipment")
        assert "Returned to Sender" in result

    def test_empty_string(self):
        """Empty string is returned as-is."""
        from src.ingest.normalize import normalize_text
        assert normalize_text("") == ""

    def test_no_jargon(self):
        """Text without jargon is unchanged (modulo whitespace)."""
        from src.ingest.normalize import normalize_text
        text = "Customer wants a refund within 45 days."
        result = normalize_text(text)
        assert "45 days" in result


class TestChunkProse:
    """chunk_prose() acceptance criteria."""

    def test_returns_at_least_one_passage(self):
        """chunk_prose returns >= 1 passage for non-empty input."""
        from src.ingest.chunk import chunk_prose
        passages = chunk_prose("This is a test passage with enough text to not get filtered.", "test.md")
        assert len(passages) >= 1

    def test_no_empty_bodies(self):
        """chunk_prose never emits a passage with an empty body."""
        from src.ingest.chunk import chunk_prose
        long_text = "\n\n".join([f"Paragraph {i}: " + "x" * 100 for i in range(10)])
        passages = chunk_prose(long_text, "test.md")
        for p in passages:
            assert p["body"].strip() != "", "Empty body in passage"

    def test_source_preserved(self):
        """chunk_prose preserves the source in each passage."""
        from src.ingest.chunk import chunk_prose
        source = "WorkFlow.svg"
        passages = chunk_prose("A passage with enough content to be included and passed.", source)
        for p in passages:
            assert p["source"] == source

    def test_long_paragraph_split(self):
        """A paragraph over MAX_CHARS is split into multiple passages."""
        from src.ingest.chunk import chunk_prose
        # Create a paragraph > 800 chars
        long_para = "This is a long sentence with a clear end point. " * 25
        passages = chunk_prose(long_para, "test.md")
        assert len(passages) >= 2, "Long paragraph should be split into multiple passages"

    def test_empty_returns_empty(self):
        """Empty input returns empty list."""
        from src.ingest.chunk import chunk_prose
        assert chunk_prose("", "test.md") == []


# ── Task 2: IngestPipeline integration tests (TDD RED then GREEN) ────────────


@pytest.mark.asyncio
async def test_pipeline_creates_kb_chunks(db_pool, stub_embedder, clean_knowledge_db):
    """KB-03: running the pipeline against snapshot fixtures creates kb_chunk rows."""
    from src.ingest.pipeline import IngestPipeline

    pipeline = IngestPipeline(db_pool)
    result = await pipeline.ingest_all(run_id="test-run-kb03")

    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge.kb_chunk")

    assert count > 0, f"Expected kb_chunk rows after ingest, got {count}"
    assert result["kb_chunk"] > 0


@pytest.mark.asyncio
async def test_pipeline_loads_exact_tables(db_pool, stub_embedder, clean_knowledge_db):
    """KB-03: policy_threshold rows for THR-03/THR-04 and code_map rows loaded."""
    from src.ingest.pipeline import IngestPipeline

    pipeline = IngestPipeline(db_pool)
    await pipeline.ingest_all(run_id="test-run-kb03-exact")

    async with db_pool.acquire() as conn:
        thr03 = await conn.fetchrow(
            "SELECT * FROM knowledge.policy_threshold WHERE threshold_id = $1",
            "THR-03",
        )
        thr04 = await conn.fetchrow(
            "SELECT * FROM knowledge.policy_threshold WHERE threshold_id = $1",
            "THR-04",
        )
        code_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge.code_map")
        template_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge.template_library")

    assert thr03 is not None, "THR-03 not found in policy_threshold after ingest"
    assert thr04 is not None, "THR-04 not found in policy_threshold after ingest"
    assert thr03["conflict_id"] == "CONTRA-01", "THR-03 missing CONTRA-01 conflict_id"
    assert thr04["conflict_id"] == "CONTRA-01", "THR-04 missing CONTRA-01 conflict_id"
    assert code_count > 0, "code_map should have rows after ingest"
    assert template_count > 0, "template_library should have rows after ingest"


@pytest.mark.asyncio
async def test_d10_thresholds_not_in_kb_chunk(db_pool, stub_embedder, clean_knowledge_db):
    """D-10: threshold values are ONLY in policy_threshold, never in kb_chunk."""
    from src.ingest.pipeline import IngestPipeline

    pipeline = IngestPipeline(db_pool)
    await pipeline.ingest_all(run_id="test-run-d10")

    async with db_pool.acquire() as conn:
        # Get all threshold values
        threshold_rows = await conn.fetch("SELECT value FROM knowledge.policy_threshold")
        threshold_values = [r["value"] for r in threshold_rows]

        # Verify none of those exact values appear as the full body of a kb_chunk row
        for val in threshold_values:
            if not val or len(val) < 5:
                continue
            match = await conn.fetchrow(
                "SELECT id FROM knowledge.kb_chunk WHERE body = $1",
                val,
            )
            assert match is None, (
                f"Threshold value '{val}' found verbatim in kb_chunk — D-10 violation"
            )
