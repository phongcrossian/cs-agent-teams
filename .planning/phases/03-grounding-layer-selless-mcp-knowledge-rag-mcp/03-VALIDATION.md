---
phase: 03
slug: grounding-layer-selless-mcp-knowledge-rag-mcp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` §Validation Architecture. Per-task map is completed after the planner assigns task IDs.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (asyncio_mode=auto) + respx (HTTP mock) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (extend Phase-2 config) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~30 seconds (mock-backed; live Selless/Voyage behind `@pytest.mark.sandbox`) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q` (mock-backed, fast)
- **After every plan wave:** Run `pytest tests/` (full mock suite)
- **Before `/gsd:verify-work`:** Full suite green + standalone smoke demo (mock) passing; live `sandbox` smoke once Selless/Voyage creds supplied
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Requirement → behavior map confirmed from RESEARCH §Phase Requirements → Test Map. Task IDs (`03-NN-MM`) filled in after planning; the planner MUST attach an `<automated>` command to each task matching a row below.

| Requirement | Wave | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| KB-03 | 1 | Ingest builds chunks + exact tables from Phase-1 snapshots | — | centralized store, no raw per-reply reads | integration | `pytest tests/ingest/test_pipeline.py -x` | ❌ W0 | ⬜ pending |
| KB-04 | 1 | Re-ingest idempotent (re-run = no dup; changed re-embeds) | — | versioned re-index | integration | `pytest tests/ingest/test_idempotent.py -x` | ❌ W0 | ⬜ pending |
| KB-05 | 2 | semantic_search returns citations w/ source/authority/recency/conflict | — | cited grounding | integration | `pytest tests/knowledge_mcp/test_semantic.py -x` | ❌ W0 | ⬜ pending |
| KB-05 | 2 | lookup_threshold returns exact value (D-10) | — | anti-hallucination exact path | unit | `pytest tests/knowledge_mcp/test_exact.py -x` | ❌ W0 | ⬜ pending |
| KB-05 (D-13) | 2 | conflicting passages → all + conflict flag | — | no self-arbitration | unit | `pytest tests/knowledge_mcp/test_conflict.py -x` | ❌ W0 | ⬜ pending |
| KB-05 (D-14) | 2 | override row resolves a conflict | — | human-ruling wins | unit | `pytest tests/knowledge_mcp/test_override.py -x` | ❌ W0 | ⬜ pending |
| SEL-01/02/03 | 3 | keyed tools return whitelisted fields (mock) | T-03-AC | keyed-only access | unit | `pytest tests/selless_mcp/test_tools.py -x` | ❌ W0 | ⬜ pending |
| SEL-02/03 (D-03) | 3 | resolve_order: exact code/email → single identity, no fuzzy/browse | T-03-AC | no cross-customer browsing | unit | `pytest tests/selless_mcp/test_resolve_scope.py -x` | ❌ W0 | ⬜ pending |
| SEL-04 (D-04) | 3 | whitelist hard-denies payment/cost/supplier/other-customer fields | T-03-ID | field-boundary deny | unit | `pytest tests/selless_mcp/test_whitelist.py -x` | ❌ W0 | ⬜ pending |
| SEL-04 (D-06/07) | 3 | every call writes a PII-redacted audit row | T-03-ID | Presidio before persist | integration | `pytest tests/selless_mcp/test_audit.py -x` | ❌ W0 | ⬜ pending |
| SEL-04 (D-08) | 3 | rate limit + read-only enforced at MCP boundary | T-03-DoS | MCP is sole boundary | unit | `pytest tests/selless_mcp/test_rate_limit.py -x` | ❌ W0 | ⬜ pending |
| All (success criteria) | 4 | standalone MCP-client smoke proves all 4 criteria | — | end-state without Phase-4 | integration | `pytest tests/smoke/test_grounding_demo.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/ingest/test_pipeline.py` + `test_idempotent.py` — KB-03/KB-04
- [ ] `tests/knowledge_mcp/test_semantic.py`, `test_exact.py`, `test_conflict.py`, `test_override.py` — KB-05/D-13/D-14
- [ ] `tests/selless_mcp/test_tools.py`, `test_resolve_scope.py`, `test_whitelist.py`, `test_audit.py`, `test_rate_limit.py` — SEL-01..04 / D-03/D-04
- [ ] `tests/smoke/test_grounding_demo.py` — standalone end-state (`@pytest.mark.sandbox`)
- [ ] `tests/conftest.py` additions — db_pool with pgvector codec, `MockSellessClient` fixtures (from `03-SELLESS-API.md` live JSON), stub embedder (avoid Voyage calls in unit tests)
- [ ] Framework install (human-verify checkpoint): `uv add fastmcp voyageai pgvector` + `CREATE EXTENSION vector`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Selless API reachable + field shapes match mock | SEL-01..03 | API behind network/gateway; no creds asserted in CI | Run `tests/smoke/test_grounding_demo.py` with `--sandbox` against live base URL once gateway access confirmed |
| Voyage embeddings live quality | KB-05 | Costs API credits; gated behind sandbox marker | Run semantic smoke with real `voyage-3-large` key |
| Freshdesk ticket-content fetch via ticket-do mapping (D-05) | SEL-03 | Cross-system join (Selless mapping → Freshdesk client); composed in Phase 4 | Verify `ticket-do` returns `fd_ticket_id`, then Phase-2 Freshdesk client fetches conversation |

*Selless live wiring depends on gateway access; mock path is fully automated.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
