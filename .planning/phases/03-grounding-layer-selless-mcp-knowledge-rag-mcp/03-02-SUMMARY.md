---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
plan: "02"
subsystem: knowledge-mcp-query
tags: [rag, semantic-search, rrf, conflict-detection, override-resolution, exact-lookup, fastmcp, d10, d13, d14, d15]
dependency_graph:
  requires: ["03-01"]
  provides:
    - "src/knowledge_mcp/models.py"
    - "src/knowledge_mcp/retrieval.py"
    - "src/knowledge_mcp/exact.py"
    - "src/knowledge_mcp/conflict.py"
    - "src/knowledge_mcp/server.py"
  affects: ["03-03", "04-*"]
tech_stack:
  added: []
  patterns:
    - "RRF k=60 hybrid: vector ANN (pgvector <=>) + FTS (plainto_tsquery) fused in Python"
    - "module-ref embed_query call so monkeypatch stub_embedder replaces it at test time"
    - "inspect.isawaitable() bridges sync stub_embedder fixture vs async Voyage production"
    - "pool injection via set_pool(pool) + optional pool= parameter for test isolation"
    - "conflict_id embedded in snapshot_version as 'conflict:<ID>:<run>' for override lookup"
    - "FastMCP on_duplicate='error' (not on_duplicate_tools — API changed in installed version)"
key_files:
  created:
    - src/knowledge_mcp/models.py
    - src/knowledge_mcp/retrieval.py
    - src/knowledge_mcp/exact.py
    - src/knowledge_mcp/conflict.py
    - src/knowledge_mcp/server.py
  modified:
    - tests/knowledge_mcp/test_semantic.py
    - tests/knowledge_mcp/test_exact.py
    - tests/knowledge_mcp/test_conflict.py
    - tests/knowledge_mcp/test_override.py
decisions:
  - "module-ref embed_query via 'import src.knowledge_mcp.embeddings as _embeddings_mod' so monkeypatch works — direct import into namespace bypasses fixture patch"
  - "pool injection: set_pool(pool) + optional pool= kwarg — no global singleton (tests inject via fixture, server sets on startup)"
  - "conflict_id convention in snapshot_version: 'conflict:<CONTRA-ID>:<run_id>' — enables apply_override to recover conflict_id from Citation without a separate metadata field"
  - "FastMCP API: on_duplicate_tools renamed to on_duplicate in installed version — fixed as Rule 3 auto-fix"
  - "stale-vs-stale not flagged as conflict (no current counterpart = no dispute); stale+current = conflict (D-13)"
metrics:
  duration: "45 min"
  completed: "2026-06-02"
  tasks_completed: 2
  files_changed: 9
---

# Phase 3 Plan 02: Knowledge MCP Query Surface Summary

**One-liner:** RRF-fused hybrid search (vector ANN + FTS) with D-12 authority citations, D-13 conflict flagging, D-14 override resolution, and D-10 exact-lookup tools wired into a FastMCP server — 16 tests GREEN.

## What Was Built

The complete query surface for the Knowledge RAG MCP, building on the Plan 01 ingest layer.

### Task 1: Models + hybrid retrieval + exact-lookup tools

**`src/knowledge_mcp/models.py`** — four Pydantic models:
- `Citation`: text, source, source_type, authority_rank (D-12), recency_flag (D-15), snapshot_version, score
- `SemanticSearchResult`: citations list, conflict (D-13), resolved_by_override (D-14)
- `ThresholdResult`: threshold_id, value, source, conflict_id, override_resolution
- `TemplateResult`: code, scenario, subject_template, body_template, source, authority_rank

**`src/knowledge_mcp/retrieval.py`** — RRF hybrid search:
- `hybrid_search(query, top_k, pool)`: embeds query → vector ANN (HNSW, cosine) top-20 + FTS (plainto_tsquery) top-20 → fuses with RRF k=60 in Python → returns top_k candidates
- `assemble_citations(rows)`: converts raw kb_chunk rows to Citation objects carrying D-12/D-15 metadata
- `SET LOCAL hnsw.ef_search = 100` for better ANN recall
- All SQL parameterized ($N); `embedding <=> $1::vector` operator used

**`src/knowledge_mcp/exact.py`** — D-10 anti-hallucination exact-lookup:
- `lookup_threshold_row(threshold_id, pool)`: `SELECT * FROM knowledge.policy_threshold WHERE threshold_id = $1`; raises KeyError if not found; also fetches override_resolution from policy_resolution if conflict_id present
- `lookup_code_row(code, pool)`: exact code_map lookup; raises KeyError if not found
- `fetch_template_row(code, pool)`: exact template_library lookup; raises KeyError if not found

### Task 2: Conflict flag + override resolution + FastMCP server

**`src/knowledge_mcp/conflict.py`** — D-13/D-14 conflict layer:
- `apply_conflict_flag(citations)`: detects conflict via stale+current coexistence and conflict_ids embedded in snapshot_version; returns `ConflictResult(has_conflict, resolved=False)` — MCP never self-arbitrates
- `apply_override(citations, pool)`: queries `knowledge.policy_resolution WHERE conflict_id = ANY($1::text[])` (parameterized); if winning_source found, reorders citations with winner first; returns `(reordered, resolved_by_override)`; never drops any citation (D-13 surface-all)

**`src/knowledge_mcp/server.py`** — FastMCP server with 4 read-only tools:
- `semantic_search(query, top_k)`: hybrid_search → assemble_citations → apply_override (D-14) → apply_conflict_flag (D-13) → SemanticSearchResult
- `lookup_threshold(threshold_id)`: delegates to lookup_threshold_row (D-10)
- `lookup_code(code)`: delegates to lookup_code_row (D-10)
- `get_template(code)`: delegates to fetch_template_row (D-11)
- All tools: `ToolAnnotations(readOnlyHint=True)`
- Boundary docstring per CLAUDE.md architecture contract

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/knowledge_mcp/test_semantic.py | 3 | GREEN |
| tests/knowledge_mcp/test_exact.py | 4 | GREEN |
| tests/knowledge_mcp/test_conflict.py | 6 | GREEN |
| tests/knowledge_mcp/test_override.py | 3 | GREEN |
| **Total** | **16** | **ALL PASS** |

Key behaviors validated:
- KB-05: semantic_search returns citations with source/authority_rank/snapshot_version/score
- D-10: lookup_threshold returns exact "45 days" value; unknown id raises KeyError
- D-12: authority_rank is int (3=WorkFlow, 2=Templates, 1=Confluence)
- D-13: stale+current mix → conflict=True; single non-conflicting source → conflict=False; MCP resolved=False (no self-arbitration)
- D-14: policy_resolution row → resolved_by_override=True and winning_source first; no row → resolved=False
- D-15: stale-flagged kb_chunk surfaces with recency_flag="stale" in Citation
- All SQL parameterized; embedding <=> operator used; no f-string SQL (T-03-02-T)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] monkeypatch stub_embedder bypassed by direct import**
- **Found during:** Task 1 GREEN phase — test_semantic_search_returns_citations raised voyageai.AuthenticationError
- **Issue:** `from src.knowledge_mcp.embeddings import embed_query` binds the name into retrieval's local namespace; monkeypatch replaces `emb.embed_query` on the embeddings module object but the local binding in retrieval.py still points to the original function
- **Fix:** Changed import to `import src.knowledge_mcp.embeddings as _embeddings_mod` and call via `_embeddings_mod.embed_query(query)` — exactly the module-reference pattern used in ingest/pipeline.py (03-01 precedent)
- **Files modified:** src/knowledge_mcp/retrieval.py
- **Commit:** bb942e1

**2. [Rule 3 - Blocking] FastMCP API: on_duplicate_tools renamed to on_duplicate**
- **Found during:** Task 2 — import of server.py raised TypeError
- **Issue:** Installed FastMCP version no longer accepts `on_duplicate_tools` kwarg; correct arg is `on_duplicate`
- **Fix:** Changed `FastMCP(name="KnowledgeMCP", on_duplicate_tools="error")` to `FastMCP(name="KnowledgeMCP", on_duplicate="error")`
- **Files modified:** src/knowledge_mcp/server.py
- **Commit:** 4f5f6e0 (applied before commit)

## Known Stubs

None — all plan goals achieved. The conflict_id convention (embedding `"conflict:<CONTRA-ID>:<run>"` in snapshot_version) is a pragmatic encoding since Citation has no separate metadata field. This is self-contained and documented in decisions above.

## Threat Flags

No new threat surface beyond the plan's threat model. All mitigations implemented:
- T-03-02-T: all SQL uses asyncpg `$N` parameterized queries including `plainto_tsquery($1)` and `ANY($1::text[])`
- T-03-02-HALL: D-10 exact-lookup enforced; lookup_threshold_row never calls any LLM
- T-03-02-ARB: D-13 MCP never self-arbitrates; apply_conflict_flag always sets resolved=False; only a human-populated policy_resolution row causes reordering

## Self-Check: PASSED

All created files exist on disk:
- FOUND: src/knowledge_mcp/models.py
- FOUND: src/knowledge_mcp/retrieval.py
- FOUND: src/knowledge_mcp/exact.py
- FOUND: src/knowledge_mcp/conflict.py
- FOUND: src/knowledge_mcp/server.py

All task commits confirmed in git log:
- FOUND: bb942e1 (Task 1 — models + retrieval + exact)
- FOUND: 4f5f6e0 (Task 2 — conflict + override + server)

16 tests GREEN: `pytest tests/knowledge_mcp/ -q` → 16 passed
