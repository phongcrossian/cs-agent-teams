---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
plan: "04"
subsystem: testing
tags: [smoke-demo, mcp-client, knowledge-rag, selless-mcp, pgvector, voyage, freshdesk]

# Dependency graph
requires:
  - phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
    provides: Knowledge MCP (semantic_search, lookup_threshold, get_template) + Selless MCP (get_order_status, audit middleware, rate-limiter)
provides:
  - Standalone MCP-client smoke demo (tests/smoke/test_grounding_demo.py) proving all four Phase-3 success criteria end-to-end without Phase-4 orchestrator
  - README-grounding.md with full run instructions (alembic, ingest CLI, MCP servers, mock + live smoke)
  - Live HttpSellessClient + Voyage path verified by human attestation (sandbox-gated, user-approved)
affects: [04-draft-reply-orchestrator, 05-offline-eval-harness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone MCP-client smoke test pattern: call tool functions directly (no HTTP), seed minimal fixtures, assert all phase success criteria in one file"
    - "Sandbox marker pattern: @pytest.mark.sandbox skips live tests unless RUN_SANDBOX=1; live path never runs in CI"
    - "Human-verify gate pattern: blocking checkpoint documents live verification steps, user attests approval, executor records truthfully"

key-files:
  created:
    - tests/smoke/test_grounding_demo.py
    - README-grounding.md
  modified: []

key-decisions:
  - "Live HttpSellessClient + Voyage path is sandbox-gated and never runs in CI; Phase-3 live verification is human-attested (user ran RUN_SANDBOX=1 and approved)"
  - "Zero-vector HNSW limitation documented in smoke demo: mock path seeds two warranty chunks with real insert so conflict=True fires via D-13 stale-vs-current detection"
  - "PydanticDeprecatedSince211 warning in src/selless_mcp/audit.py:69 (result.model_fields on instance instead of class) is harmless now — tidy to class access in a later plan"
  - "D-05 Freshdesk composition note captured in README: ticket-do mapping comes from Selless; ticket content (email body/subject) comes from Phase-2 Freshdesk client — wired in Phase 4"

patterns-established:
  - "Phase-close smoke demo pattern: one file, direct tool calls as MCP client, 4 assertions covering all success criteria, sandbox marker for live variant"
  - "Human-verify gate documentation: record user attestation truthfully; do not fabricate machine-run output for gateway/credential-gated paths"

requirements-completed: [KB-03, KB-04, KB-05, SEL-01, SEL-02, SEL-03, SEL-04]

# Metrics
duration: ~10min (continuation agent — write SUMMARY + state update only)
completed: 2026-06-02
---

# Phase 03 Plan 04: Smoke Demo + Live Gateway Verification Summary

**Standalone MCP-client smoke demo proving all four Phase-3 success criteria (semantic conflict, exact threshold, template fetch, scoped/audited/rate-limited Selless read) mock-backed and green; live Selless gateway + Voyage path human-attested and approved**

## Performance

- **Duration:** ~10 min (continuation finalization only; Task 1 was executed by prior agent)
- **Started:** 2026-06-02T07:16:00Z (Task 1 execution)
- **Completed:** 2026-06-02T07:22:00Z
- **Tasks:** 2 (Task 1: auto-executed; Task 2: human-verify checkpoint, approved)
- **Files modified:** 2

## Accomplishments

- `tests/smoke/test_grounding_demo.py` mock-backed test is GREEN: all four Phase-3 success criteria asserted in a single standalone file without the Phase-4 orchestrator
- Seed helper inserts two warranty chunks (current + stale) so `conflict=True` fires via D-13 stale-vs-current detection; asserts `audit.selless_audit` redacted row written after Selless call (SEL-04/D-06); asserts token-bucket rate-limiter rejects requests past burst capacity (D-08)
- `README-grounding.md` (172 lines) documents the full grounding layer: alembic migrations, ingest CLI, MCP server startup, mock smoke command, live sandbox command, and D-05 Freshdesk composition note
- Live HttpSellessClient + Voyage embeddings (`voyage-3-large`) path verified by blocking human-verify gate — user attested `RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q` passed: live `get_order_status` returned whitelisted shape with no payment/cost/supplier leakage; live `semantic_search` returned cited passages; no field-shape drift reported

## Task Commits

Each task was committed atomically:

1. **Task 1: Standalone MCP-client smoke demo (mock-backed) + README** - `e12c5ca` (feat)
2. **Task 2: Live gateway + Voyage verification** - human-verify gate, no code commit (user attestation)

**Plan metadata:** *(this SUMMARY commit)*

## Files Created/Modified

- `tests/smoke/test_grounding_demo.py` — 497-line standalone smoke demo; mock-backed test asserts all 4 Phase-3 criteria; `@pytest.mark.sandbox` live variant gated behind `RUN_SANDBOX=1`
- `README-grounding.md` — 172-line run guide: alembic, ingest CLI, Knowledge MCP + Selless MCP startup, mock + live smoke commands, D-05 composition note

## Decisions Made

- Live path stays sandbox-gated and is never run in CI; Phase-3 live verification is a one-time human-attested approval (blocking human-verify gate), not a recurring CI check
- `audit.selless_audit` row assertion uses `is not None` check on the first redacted row — sufficient to prove SEL-04 compliance without coupling to row count
- Zero-vector HNSW limitation: the mock smoke path uses a real DB insert with deterministic stub embeddings so `conflict=True` fires correctly via D-13; HNSW requires at least one indexed vector, documented in test comment
- D-05 Freshdesk composition deferred to Phase 4 as planned: README captures the split explicitly so Phase-4 implementer sees it immediately

## Deviations from Plan

None — plan executed exactly as written. Task 1 implemented the mock smoke demo and README per spec. Task 2 resolved via the blocking human-verify gate with user approval.

### Minor Follow-up Item (not a deviation)

`src/selless_mcp/audit.py:69` uses `result.model_fields` on a Pydantic model *instance* (should be `type(result).model_fields` or `result.__class__.model_fields` for class-level access). This triggers a `PydanticDeprecatedSince211` warning but does not affect correctness — field names are the same. Tidy to class access in a later plan.

## Issues Encountered

None during Task 1 execution. Task 2 (live gateway) is gateway/credential-gated and was handled by the blocking human-verify checkpoint as designed — not an issue, expected flow.

## Verification Record

**Task 2 — Live Gateway + Voyage: Human-Attested Approval**

The live Selless gateway and Voyage embeddings path is intentionally excluded from CI (`@pytest.mark.sandbox`, requires `RUN_SANDBOX=1` + live credentials). It was verified by the user via the blocking human-verify gate:

- User set `SELLESS_API_GATEWAY_KEY` and `VOYAGE_API_KEY` in `.env`
- User ran: `RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q`
- Result: **APPROVED** — live `get_order_status` returned whitelisted shape (no payment/cost/supplier field leakage); live `semantic_search` returned cited passages; no field-shape drift vs mock fixtures reported

The orchestrator did NOT machine-run the live path. This attestation is the human-verify gate resolution as documented in the plan (`<resume-signal>` response: "approved").

## Threat Surface Scan

No new security-relevant surface introduced in this plan. `tests/smoke/test_grounding_demo.py` is a test file (no production endpoints). `README-grounding.md` is documentation. The trust boundary crossing (smoke demo → live Selless gateway, smoke demo → live Voyage) was covered by the plan's threat model (T-03-04-DRIFT, T-03-04-GATE, T-03-04-ID) and mitigated by the human-verify gate + whitelist explicit-extraction pattern.

## Next Phase Readiness

- Phase 3 grounding layer is complete and verified: Knowledge RAG MCP + Selless transactional MCP are both operational
- Phase 4 (draft-reply orchestrator) can proceed — it connects to both MCPs via their FastMCP tool interfaces
- D-05 Freshdesk composition (ticket-do mapping from Selless + email body from Freshdesk client) is documented in README-grounding.md for Phase-4 implementer
- The five P0 content blockers (AI-01 to AI-06) remain open — Phase 4 drafting quality will be limited until CS team authors the missing policy content; these are CS-team action items, not Phase-4 blockers for the pipeline itself

---
*Phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp*
*Completed: 2026-06-02*
