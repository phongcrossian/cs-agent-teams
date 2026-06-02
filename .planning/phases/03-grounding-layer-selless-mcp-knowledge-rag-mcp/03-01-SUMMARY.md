---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
plan: "01"
subsystem: knowledge-ingest
tags: [kb-ingest, rag, idempotent, voyage-embeddings, pgvector, d10-exact-split]
dependency_graph:
  requires: ["03-00"]
  provides: ["src/ingest/*", "src/knowledge_mcp/embeddings.py", "knowledge.kb_chunk", "knowledge.policy_threshold", "knowledge.code_map", "knowledge.template_library"]
  affects: ["03-02", "03-03"]
tech_stack:
  added: ["voyageai (voyage-3-large, 1024-dim)", "pdfminer.six (optional — Confluence PDFs)"]
  patterns:
    - "content_hash = sha256(source + \\x00 + body) — idempotent upsert key"
    - "ON CONFLICT (content_hash) DO UPDATE — prose re-embeds only when content changes"
    - "D-10: thresholds/codes/templates never pass through embeddings — exact tables only"
    - "inspect.isawaitable() — handle sync stub_embedder vs async embed_documents"
key_files:
  created:
    - src/ingest/__init__.py
    - src/ingest/normalize.py
    - src/ingest/chunk.py
    - src/ingest/sources.py
    - src/ingest/pipeline.py
    - src/ingest/cli.py
    - src/knowledge_mcp/__init__.py
    - src/knowledge_mcp/embeddings.py
  modified:
    - tests/ingest/test_pipeline.py
    - tests/ingest/test_idempotent.py
decisions:
  - "content_hash keyed on source+body SHA256 — unique per source path+content combination; changing either dimension triggers re-embed"
  - "inspect.isawaitable() used to handle sync stub_embedder fixture vs async Voyage production path — avoids conftest changes"
  - "pdfminer.six used for Confluence PDF extraction (optional dep — warns gracefully if missing); Confluence prose skipped in tests"
  - "MIN_CHARS=50 for chunk filter — avoids near-empty SVG label noise in kb_chunk"
metrics:
  duration: "35 min"
  completed: "2026-06-02"
  tasks_completed: 2
  files_changed: 10
---

# Phase 3 Plan 01: KB Data Layer and Snapshot Ingest Summary

**One-liner:** Idempotent ingest pipeline from Phase-1 snapshots into pgvector kb_chunk + exact policy_threshold/code_map/template_library tables, enforcing D-10 anti-hallucination split with voyage-3-large embeddings.

## What Was Built

The full `src/ingest/` package and `src/knowledge_mcp/embeddings.py` that together form the data-loading layer for the Knowledge RAG MCP.

### Task 1: Snapshot readers + GLOSSARY normalization + prose chunking

**`src/ingest/sources.py`** — readers for all Phase-1 snapshot types:
- `read_prose_sources()`: WorkFlow.svg (SVG text extraction via regex), template .md files, Confluence PDFs (pdfminer.six, graceful fallback)
- `read_threshold_rows()`: parses POLICY-THRESHOLD-INDEX.md markdown table into 18 rows; THR-03/THR-04 carry `conflict_id="CONTRA-01"` from CONFLICT-INVENTORY
- `read_code_map_rows()`: parses CODE-MAP.md into 83 code → action rows
- `read_templates()`: extracts template sections from template .md files into 121 template_library candidates
- Authority ranks per D-12: WorkFlow.svg=3, Templates=2, Confluence=1
- `billing-template.md` flagged `recency_flag="stale"` (STALE-01)

**`src/ingest/normalize.py`** — GLOSSARY-driven jargon expansion:
- Pre-compiled whole-word regex for CEE, SCE, DNR, RTS, OOS, TA, TO, WOC, WNF, DO, PO, TC, OB, MOQ, FFM, GRT
- Strips YAML frontmatter headers from markdown files
- Collapses excess whitespace

**`src/ingest/chunk.py`** — paragraph-boundary prose chunking:
- Primary split on double-newline paragraph boundaries
- Secondary split on sentence boundaries for paragraphs > 800 chars
- MIN_CHARS=50 filter to avoid near-empty label noise
- Fallback: returns full text as single passage rather than empty list

### Task 2: Voyage embeddings wrapper + idempotent pipeline + re-ingest CLI (TDD)

**`src/knowledge_mcp/embeddings.py`** — lazy Voyage client singleton:
- `embed_query(text)` — input_type="query", 1024-dim
- `embed_documents(texts)` — input_type="document", batched
- Reads VOYAGE_API_KEY via voyageai.Client() default env behavior
- Tests use `stub_embedder` fixture (zero vectors, no live API calls)

**`src/ingest/pipeline.py`** — idempotent ingest orchestration:
- `content_hash(source, body)` = sha256 of `source\x00body`
- `IngestPipeline.ingest_all(run_id)` orchestrates all 4 upsert flows
- `upsert_chunk()`: `INSERT ... ON CONFLICT (content_hash) DO UPDATE` — updates embedding+snapshot_version only
- Thresholds/codes/templates go to exact tables only (D-10 — never embedded)
- All SQL uses asyncpg `$N` parameters — no f-string SQL (T-03-01-T)
- `redact_text()` called before any log line with snapshot content (T-03-01-ID)

**`src/ingest/cli.py`** — D-16 re-ingest entrypoint:
- `python -m src.ingest.cli re-ingest [--run-id RUN_ID]`
- Opens asyncpg pool, runs IngestPipeline, prints summary counts
- Default run_id = UTC timestamp

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/ingest/test_pipeline.py | 17 | GREEN |
| tests/ingest/test_idempotent.py | 3 (+ 9 unit) | GREEN |
| **Total** | **29** | **ALL PASS** |

Key tests validated:
- KB-03: ingest creates kb_chunk + policy_threshold + code_map + template_library rows
- KB-04: second run produces same kb_chunk count (idempotent)
- D-10: no threshold value appears verbatim in kb_chunk.body
- THR-03 and THR-04 land as distinct rows with `conflict_id="CONTRA-01"`
- `python -m src.ingest.cli re-ingest --help` exits 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Regex missing trailing pipe in markdown table parser**
- **Found during:** Task 1 verification
- **Issue:** POLICY-THRESHOLD-INDEX.md and CODE-MAP.md markdown table rows end with `|` (trailing pipe); initial regex used `$` anchor which matched line end without the pipe, yielding 0 rows
- **Fix:** Changed regex from `([^|]*)$` to `([^|]*)\|` to match trailing pipe explicitly; confirmed 18 threshold rows and 83 code_map rows returned
- **Files modified:** src/ingest/sources.py
- **Commit:** f9ff15b (fix applied before commit)

**2. [Rule 1 - Bug] stub_embedder returns sync list but pipeline awaited it**
- **Found during:** Task 2 GREEN phase test run
- **Issue:** `conftest.py` `stub_embedder` fixture uses a sync lambda; `pipeline.py` used `await embed_documents(bodies)` which raised `TypeError: 'list' can't be awaited`
- **Fix:** Added `inspect.isawaitable()` check — awaits if coroutine (production Voyage path), calls directly if sync (stub path). No conftest change needed.
- **Files modified:** src/ingest/pipeline.py
- **Commit:** 4fdcbba (fix applied before commit)

## Known Stubs

None — all plan goals achieved. Confluence PDF extraction falls back gracefully to empty string when pdfminer.six is not installed (warns via logger). This is intentional: the `pdfminer.six` package is an optional dependency; if needed in production, install it. No data is silently lost — the warning is logged per file.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. All mitigations implemented:
- T-03-01-ID: `redact_text()` called before log lines in `pipeline.py`
- T-03-01-T: all SQL uses `$N` parameterized asyncpg queries
- T-03-01-HALL: D-10 enforced and tested — thresholds never in kb_chunk

## Self-Check: PASSED

All created files exist on disk:
- FOUND: src/ingest/__init__.py
- FOUND: src/ingest/normalize.py
- FOUND: src/ingest/chunk.py
- FOUND: src/ingest/sources.py
- FOUND: src/ingest/pipeline.py
- FOUND: src/ingest/cli.py
- FOUND: src/knowledge_mcp/__init__.py
- FOUND: src/knowledge_mcp/embeddings.py

All task commits confirmed in git log:
- FOUND: f9ff15b (Task 1 — snapshot readers + normalize + chunk)
- FOUND: 7dc2f6c (TDD RED — idempotent pipeline tests)
- FOUND: 4fdcbba (Task 2 GREEN — embeddings + pipeline + CLI)
