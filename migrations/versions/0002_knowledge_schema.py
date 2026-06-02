"""Knowledge schema: kb_chunk, policy_threshold, code_map, template_library, policy_resolution.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-02

Design note: knowledge tables live in schema `knowledge` (not `public` or `queue`).
Phase-2 design note (0001 line 9): Phase 3 uses schema `knowledge` to maintain
clear separation with `queue`. pgvector extension installed in the shared DB (public
extension slot) so all schemas can reference the vector type.

Authority hierarchy (D-12): WorkFlow=3 > Email Templates=2 > Confluence=1.
Stored as `authority_rank` INT column — tunable without schema change.

Idempotent ingest (KB-04): UNIQUE index on content_hash makes re-runs safe.
HNSW index (D-09): m=16, ef_construction=64 — standard pgvector recommendation.
Hybrid search (KB-05): FTS via body_tsv GENERATED ALWAYS + GIN, trgm via gin_trgm_ops.

Exact lookup tables (D-10): policy_threshold and code_map store as rows, never vectors.
Template library (D-11): separate retrieval type, keyed by code.
Override table (D-14): policy_resolution wins when a CS Lead ruling exists.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Schema + extensions ───────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")      # pgvector (Pitfall 2)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")     # hybrid search

    # ── knowledge.kb_chunk ────────────────────────────────────────────────────
    # Prose chunks: vector + FTS + trgm for hybrid retrieval (KB-05).
    # body_tsv: GENERATED ALWAYS so FTS stays in sync without application logic.
    # embedding VECTOR(1024): voyage-3-large output dimension.
    # content_hash: SHA-256 of source+body — drives idempotent upsert (KB-04).
    op.execute(
        """
        CREATE TABLE knowledge.kb_chunk (
            id               BIGSERIAL   PRIMARY KEY,
            content_hash     TEXT        NOT NULL,
            source           TEXT        NOT NULL,
            source_type      TEXT        NOT NULL,
            authority_rank   INTEGER     NOT NULL,
            recency_flag     TEXT,
            body             TEXT        NOT NULL,
            body_tsv         TSVECTOR    GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
            embedding        VECTOR(1024),
            metadata         JSONB       NOT NULL DEFAULT '{}',
            snapshot_version TEXT        NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # UNIQUE on content_hash for idempotent upsert (KB-04)
    op.execute(
        "CREATE UNIQUE INDEX idx_kb_chunk_hash ON knowledge.kb_chunk (content_hash)"
    )

    # HNSW index for ANN vector search (D-09 / CLAUDE.md mandate)
    op.execute(
        """
        CREATE INDEX idx_kb_chunk_hnsw ON knowledge.kb_chunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # FTS index on generated tsvector column
    op.execute(
        "CREATE INDEX idx_kb_chunk_fts ON knowledge.kb_chunk USING gin (body_tsv)"
    )

    # trgm index for fuzzy/substring match arm of hybrid search
    op.execute(
        "CREATE INDEX idx_kb_chunk_trgm ON knowledge.kb_chunk USING gin (body gin_trgm_ops)"
    )

    # ── knowledge.policy_threshold ────────────────────────────────────────────
    # D-10: exact numeric/temporal thresholds; NEVER chunked into vectors.
    # 25 rows from POLICY-THRESHOLD-INDEX.md; conflict_id links to CONFLICT-INVENTORY.
    op.execute(
        """
        CREATE TABLE knowledge.policy_threshold (
            threshold_id     TEXT        PRIMARY KEY,
            label            TEXT        NOT NULL,
            value            TEXT        NOT NULL,
            source           TEXT        NOT NULL,
            authority_rank   INTEGER     NOT NULL,
            conflict_id      TEXT,
            snapshot_version TEXT        NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ── knowledge.code_map ────────────────────────────────────────────────────
    # D-10: workflow code → action + template ref; exact lookup only.
    op.execute(
        """
        CREATE TABLE knowledge.code_map (
            code             TEXT        PRIMARY KEY,
            action           TEXT        NOT NULL,
            template_code    TEXT,
            source           TEXT        NOT NULL,
            snapshot_version TEXT        NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ── knowledge.template_library ────────────────────────────────────────────
    # D-11: reply template scaffolds — separate retrieval type (keyed by code).
    # authority_rank DEFAULT 2 (Email Templates = 2 per D-12).
    op.execute(
        """
        CREATE TABLE knowledge.template_library (
            code             TEXT        PRIMARY KEY,
            scenario         TEXT        NOT NULL,
            subject_template TEXT        NOT NULL,
            body_template    TEXT        NOT NULL,
            source           TEXT        NOT NULL,
            authority_rank   INTEGER     NOT NULL DEFAULT 2,
            snapshot_version TEXT        NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ── knowledge.policy_resolution ───────────────────────────────────────────
    # D-14: override table for known conflicts. When a CS Lead rules, the winning
    # source/value is stored here. semantic_search checks this table and puts the
    # winner first + sets resolved_by_override=True.
    op.execute(
        """
        CREATE TABLE knowledge.policy_resolution (
            conflict_id      TEXT        PRIMARY KEY,
            winning_source   TEXT        NOT NULL,
            resolved_value   TEXT        NOT NULL,
            resolved_by      TEXT,
            resolved_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes            TEXT
        )
        """
    )


def downgrade() -> None:
    # Drop in reverse creation order
    op.execute("DROP TABLE IF EXISTS knowledge.policy_resolution")
    op.execute("DROP TABLE IF EXISTS knowledge.template_library")
    op.execute("DROP TABLE IF EXISTS knowledge.code_map")
    op.execute("DROP TABLE IF EXISTS knowledge.policy_threshold")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_trgm")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_fts")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_hnsw")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_kb_chunk_hash")
    op.execute("DROP TABLE IF EXISTS knowledge.kb_chunk")
    op.execute("DROP SCHEMA IF EXISTS knowledge")
    # Note: extensions (vector, pg_trgm) are not dropped — they may be shared
    # by other schemas/users. Drop manually if truly removing pgvector from DB.
