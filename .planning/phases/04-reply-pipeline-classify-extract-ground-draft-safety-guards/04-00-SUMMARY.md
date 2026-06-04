---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "00"
subsystem: file-store
tags: [file-store, template-lookup, D-31, PoC-pivot, RAG-removal]
dependency_graph:
  requires: []
  provides:
    - src/file_store/template_store.py (get_template_from_file, subtype_to_code)
  affects:
    - drafter agent (downstream consumer of get_template_from_file)
    - scripts/test_tickets_run.py (downstream consumer of subtype_to_code)
tech_stack:
  added:
    - src/file_store/ (new package — local file-based template lookup, no deps)
  patterns:
    - Two-pass heading extraction (prefer ## markdown headings over bare TOC entries)
    - Fail-soft returns (never raises, never fabricates; returns found=False on any miss)
    - Lazily parsed + cached CODE-MAP index (_INDEX global)
    - Repo-root anchor via Path(__file__).resolve().parent.parent.parent
key_files:
  created:
    - src/file_store/__init__.py
    - src/file_store/template_store.py
    - tests/test_file_store.py
  modified:
    - pyproject.toml (voyageai and pgvector RAG deps removed)
decisions:
  - "Two-pass heading extraction chosen: first pass seeks ## headings, second pass falls back to bare text. Snapshot files have bare TOC entries near the top that match heading text but contain no body content; preferring ## headings avoids false matches."
  - "subtype_to_code returns [] for unknown sub-types (not an error) — aligns with always-draft pipeline where unknown sub-type should still draft using caller's fallback logic."
  - "voyageai comment retained in pyproject.toml to document removal rationale and date (D-29 pivot 2026-06-04); the package entry itself is removed."
metrics:
  duration_minutes: 5
  completed: "2026-06-04"
  tasks: 2
  files: 4
---

# Phase 4 Plan 00: Local Template File-Store + RAG Dep Removal Summary

**One-liner:** File-based `get_template_from_file(code)` + `subtype_to_code(sub_type)` reading 26 local snapshots and CODE-MAP-templates.md, replacing the semantic-RAG Knowledge MCP as the drafter's grounding surface (D-31).

## What Was Built

### Task 1 — Local template file-store loader (TDD)

Created `src/file_store/` package implementing the D-31 local file-store:

- `get_template_from_file(code)` — looks up the code in a lazily-parsed CODE-MAP-templates.md index, resolves the snapshot file path (always anchored to `SNAPSHOTS_DIR`, never from runtime input — T-04-00-01), extracts the template body under the verbatim heading, and returns `{code, found, heading, body, snapshot_file, variants}`. Returns `found=False, body=None` on any miss (unknown code, missing file, heading not found) — never raises, never fabricates.
- `subtype_to_code(sub_type)` — maps the 13 `customer_request` sub-types to ordered candidate code lists per the SKILL.md table. `Review` returns `[]` (Phase-1 confirmed gap). Unknown sub-types return `[]`.
- No network, no DB, no embeddings, no `src.knowledge_mcp` imports.

Key implementation detail: snapshot files contain bare heading text in TOC-like sections near the top (e.g. `A4-Cannot replace-Evidence provided` at line 16) AND proper `## A4-...` headings further down. A single-pass scan matched the TOC entry first, returning an empty body. Solution: two-pass scan — pass 1 seeks `## heading` markdown lines, pass 2 falls back to bare text only when no markdown heading is found.

22 tests covering all 5 plan behaviors — all pass.

### Task 2 — Strip RAG dependencies from pyproject.toml

Removed `voyageai==0.3.7` and `pgvector>=0.4.2` from `pyproject.toml` per D-29 stack delta. `ragas` was not present. All non-RAG deps (`anthropic`, `fastmcp`, `presidio-analyzer`, `presidio-anonymizer`, etc.) remain intact. A comment documents the removal rationale and date.

## Commits

| Task | Hash | Message |
|------|------|---------|
| TDD RED | 94f2869 | test(04-00): add failing tests for template file-store loader |
| TDD GREEN | 7e43d12 | feat(04-00): implement local template file-store loader (D-31) |
| Task 2 | 4f9184a | chore(04-00): strip voyageai and pgvector RAG deps from pyproject.toml |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two-pass heading extraction for snapshot files with bare TOC entries**
- **Found during:** Task 1 GREEN phase (test `test_another_known_code_a4` failed)
- **Issue:** Snapshot files contain bare heading text (e.g. `A4-Cannot replace-Evidence provided`) as TOC-like entries near the file top, before the actual `## A4-...` content section. Single-pass scan matched the bare TOC entry first; the section body was empty (next heading immediately followed).
- **Fix:** Implemented two-pass extraction: pass 1 scans for proper `## heading` / `### heading` markdown lines; pass 2 falls back to bare text only if no markdown heading was found. This is the correct parsing semantics, not a workaround — the structured headings are the canonical content markers.
- **Files modified:** `src/file_store/template_store.py`
- **Commit:** 7e43d12

## Verification Evidence

```
.venv/bin/python -m pytest tests/test_file_store.py -x -q
22 passed in 0.40s

python -c "from src.file_store.template_store import get_template_from_file; r=get_template_from_file('B7'); assert r['found'] and r['body']"
# exits 0, B7 body length: 1013 chars

grep -n "^import\|^from" src/file_store/template_store.py | grep -i "knowledge_mcp|voyage|pgvector|semantic"
# returns nothing — PASS

subtype_to_code("Review") == []  # confirmed by test_review_subtype_returns_empty_list
```

## Known Stubs

None — the file-store is fully functional. Template bodies are read verbatim from real snapshot files.

## Threat Flags

None — no new network surface, no new untrusted input paths. Snapshot paths are anchored to `SNAPSHOTS_DIR` constant (T-04-00-01 mitigated).

## Self-Check: PASSED

Files exist:
- src/file_store/__init__.py — FOUND
- src/file_store/template_store.py — FOUND
- tests/test_file_store.py — FOUND

Commits exist:
- 94f2869 — FOUND (test RED)
- 7e43d12 — FOUND (feat GREEN)
- 4f9184a — FOUND (chore deps)
