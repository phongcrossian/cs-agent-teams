---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
verified: 2026-06-02T07:55:00Z
status: passed
status_note: "Auto-verification 14/14. Lý do duy nhất verifier đặt human_needed (live Selless+Voyage sandbox path, Task 2 của 03-04) đã được user attest approved qua blocking human-verify checkpoint trong execute-phase. Live path vẫn @pytest.mark.sandbox (không chạy CI)."
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Chạy RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q với VOYAGE_API_KEY và SELLESS_API_GATEWAY_KEY thực sự được set trong .env"
    expected: "Live get_order_status trả về OrderDetail đúng shape (không có payment/cost/supplier); live semantic_search trả về cited passages; audit row được ghi vào DB"
    why_human: "Live Selless gateway được gate bởi network/VPN; Voyage tốn credit; live path không chạy trong CI theo thiết kế (sandbox marker)"
    status: approved-by-user-attestation
---

# Phase 3: Grounding Layer Verification Report

**Phase Goal:** Build the two separate grounding surfaces the drafter relies on — a transactional Selless MCP for scoped lookup-by-ID reads and a Knowledge MCP serving cited semantic search over an ingested, conflict-aware RAG store — so the orchestrator never reads source systems directly.
**Verified:** 2026-06-02T07:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | uv adds fastmcp, voyageai, pgvector to pyproject.toml và env import được | VERIFIED | `python -c "import fastmcp, voyageai, mcp, pgvector"` pass; Settings-OK confirmed |
| 2 | alembic upgrade head tạo knowledge.* và audit.* schemas với pgvector + pg_trgm | VERIFIED | `migrations/versions/0002_knowledge_schema.py` (revision 0002, down_revision 0001) và `0003_selless_audit.py` (revision 0003, down_revision 0002); 6 tables + 2 extensions |
| 3 | Settings expose Selless + Voyage + rate-limit fields, secrets redacted trong `__repr__` | VERIFIED | `repr(settings)` chứa `voyage_api_key=<REDACTED>` và `selless_api_gateway_key=<REDACTED>`; xác nhận bằng CLI |
| 4 | Ingest CLI chạy trên Phase-1 snapshots đưa prose chunks vào kb_chunk và exact rows vào policy_threshold / code_map / template_library | VERIFIED | `src/ingest/pipeline.py` có `ingest_all()` với 4 bước; `src/ingest/cli.py` có sub-command `re-ingest`; tests/ingest/ 100% pass |
| 5 | Re-ingest là idempotent: nội dung không đổi → no-op; nội dung đổi → re-embeds | VERIFIED | `ON CONFLICT (content_hash) DO UPDATE` trong `upsert_chunk()`; `test_idempotent.py` pass |
| 6 | THR-03 và THR-04 land như distinct exact rows mang conflict marker (CONTRA-01) | VERIFIED | `_THRESHOLD_CONFLICT_MAP` trong `sources.py` map THR-03/THR-04 → CONTRA-01; `test_pipeline.py` pass |
| 7 | semantic_search trả về cited passages với source, authority_rank, recency_flag, snapshot_version | VERIFIED | `assemble_citations()` trong `retrieval.py` carry đầy đủ Citation fields; `test_semantic.py` pass |
| 8 | Conflicting passages: conflict=True, tất cả được surface (không tự arbitrate) | VERIFIED | `apply_conflict_flag()` + `_sources_conflict()` trong `conflict.py`; `test_conflict.py` pass |
| 9 | Khi có policy_resolution override row: resolved_by_override=True, winning passage đứng đầu | VERIFIED | CR-01 đã được fix: `Citation.conflict_id` field + `_PROSE_CONFLICT_MAP` trong sources.py + `metadata["conflict_id"]` trong pipeline + `apply_override()` đọc từ `c.conflict_id`; `test_override.py` pass |
| 10 | lookup_threshold trả về exact stored value; get_template trả về scaffold theo code | VERIFIED | `exact.py` với `lookup_threshold_row()` và `fetch_template_row()` dùng parameterized queries; `test_exact.py` pass |
| 11 | get_order_status / get_customer_info / get_purchase_history trả về only D-04 whitelisted fields | VERIFIED | `whitelist.py` với `_DENY_FIELDS` frozenset + explicit field extraction (không `**raw`); `test_whitelist.py` + `test_tools.py` pass |
| 12 | Mọi Selless tool call ghi PII-redacted row vào audit.selless_audit; audit là fail-closed | VERIFIED | CR-02 đã được fix: `AuditMiddleware` với finally block, `_write_audit_row` không swallow exceptions, `assert_audit_pool_configured()` tại startup; `test_audit.py` pass |
| 13 | Rate limit enforced + read-only (không có write tool) | VERIFIED | `_TokenBucketRateLimiter` wired trong `mcp.add_middleware()`; tất cả tools có `readOnlyHint=True`; không có write method; `test_rate_limit.py` pass |
| 14 | get_ticket_history(order_id) compose Selless ticket-do mapping → Freshdesk client → whitelisted TicketHistory (agent/agent_id denied) | VERIFIED | `_impl_get_ticket_history()` trong server.py: bước 1 fetch_ticket_mapping, bước 2 fd.get_ticket, bước 3 apply_ticket_history_whitelist; `test_ticket_history.py` pass |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `migrations/versions/0002_knowledge_schema.py` | knowledge schema: kb_chunk, policy_threshold, code_map, template_library, policy_resolution | VERIFIED | CREATE EXTENSION IF NOT EXISTS vector; HNSW + FTS + trgm indexes; UNIQUE on content_hash |
| `migrations/versions/0003_selless_audit.py` | audit.selless_audit PII-redacted table | VERIFIED | CREATE TABLE audit.selless_audit; index on (tool, created_at) |
| `src/config.py` | Selless + Voyage + rate-limit settings, secrets redacted | VERIFIED | 7 new fields: selless_api_base_url, selless_api_gateway_key, voyage_api_key, voyage_model, voyage_output_dimension, selless_rate_limit_rps, selless_rate_limit_burst |
| `src/ingest/pipeline.py` | normalize→chunk→embed→content-hash upsert orchestration (idempotent) | VERIFIED | `IngestPipeline.ingest_all()` + `upsert_chunk()` với ON CONFLICT; conflict_id trong metadata JSONB |
| `src/ingest/cli.py` | python -m src.ingest.cli re-ingest entrypoint | VERIFIED | `re-ingest` sub-command trong argparse |
| `src/ingest/sources.py` | readers cho WorkFlow.svg, template .md, Confluence PDF, POLICY-THRESHOLD-INDEX.md, CODE-MAP.md | VERIFIED | >30 lines; `_PROSE_CONFLICT_MAP` + `_THRESHOLD_CONFLICT_MAP` |
| `src/knowledge_mcp/embeddings.py` | Voyage voyage-3-large wrapper (query vs document input_type) | VERIFIED | lazy voyageai.Client singleton; `embed_query()` + `embed_documents()` |
| `src/knowledge_mcp/server.py` | FastMCP server với semantic_search / lookup_threshold / lookup_code / get_template (readOnlyHint) | VERIFIED | 4 tools với `ToolAnnotations(readOnlyHint=True)`; boundary docstring |
| `src/knowledge_mcp/retrieval.py` | RRF-fused hybrid search (vector ANN + FTS) + citation assembly | VERIFIED | `_rrf_fuse()` + `hybrid_search()` + `assemble_citations()`; `embedding <=>` operator |
| `src/knowledge_mcp/conflict.py` | D-13 conflict flag + D-14 override resolution (>20 lines) | VERIFIED | 186 lines; `_extract_conflict_ids()` đọc `c.conflict_id`; `apply_override()` query `policy_resolution` |
| `src/knowledge_mcp/models.py` | Citation, SemanticSearchResult, ThresholdResult, TemplateResult | VERIFIED | class Citation với `conflict_id: Optional[str]` field (added bởi CR-01 fix) |
| `src/selless_mcp/client.py` | SellessClient Protocol + MockSellessClient + HttpSellessClient | VERIFIED | class MockSellessClient; @runtime_checkable Protocol; HttpSellessClient với httpx+tenacity |
| `src/selless_mcp/whitelist.py` | D-04 map-and-whitelist (explicit field extraction, hard-deny list) | VERIFIED | `_DENY_FIELDS` frozenset 14 items; apply_order/customer/ticket_history_whitelist |
| `src/selless_mcp/audit.py` | AuditMiddleware PII-redacted rows (D-06/D-07) | VERIFIED | fail-closed: INSERT failure propagates; pool-unset raises RuntimeError; `assert_audit_pool_configured()` |
| `src/selless_mcp/server.py` | FastMCP server, read-only tools, rate-limit + audit middleware | VERIFIED | `readOnlyHint=True` + `openWorldHint=False` trên tất cả 5 tools; middleware wired |
| `tests/smoke/test_grounding_demo.py` | MCP-client smoke proving all 4 criteria (mock-backed) | VERIFIED | 4 mock-backed assertions + `@pytest.mark.sandbox` cho live variant; `lookup_threshold` + `selless_audit` present |
| `README-grounding.md` | How to run both MCPs + ingest CLI + smoke demo | VERIFIED | 172 lines — đủ nội dung |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/conftest.py db_pool` | `pgvector.asyncpg.register_vector` | pool init codec registration | VERIFIED | `register_vector` trong conftest.py |
| `migrations/0002` | `migrations/0001` | down_revision chain | VERIFIED | `down_revision = "0001"` trong 0002; `down_revision = "0002"` trong 0003 |
| `src/ingest/pipeline.py` | `knowledge.kb_chunk` | INSERT ... ON CONFLICT (content_hash) DO UPDATE | VERIFIED | `ON CONFLICT (content_hash) DO UPDATE` trong `upsert_chunk()` |
| `src/ingest/pipeline.py` | `src/knowledge_mcp/embeddings.py` | `embed_documents` call during ingest | VERIFIED | `from src.knowledge_mcp.embeddings import embed_documents` + `result = embed_documents(bodies)` |
| `src/ingest/sources.py` | `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/` | frozen snapshot reads | VERIFIED | `_PROSE_CONFLICT_MAP` references snapshot filenames |
| `src/knowledge_mcp/server.py` | `src/knowledge_mcp/retrieval.py` | `hybrid_search` call | VERIFIED | `candidates = await hybrid_search(query, top_k=top_k)` |
| `src/knowledge_mcp/retrieval.py` | `knowledge.kb_chunk` | vector + FTS parameterized queries | VERIFIED | `embedding <=> $1::vector` + `plainto_tsquery('english', $1)` |
| `src/knowledge_mcp/conflict.py` | `knowledge.policy_resolution` | override lookup by conflict_id | VERIFIED | `SELECT ... FROM knowledge.policy_resolution WHERE conflict_id = ANY($1::text[])` |
| `src/selless_mcp/server.py` | `src/selless_mcp/whitelist.py` | tools return `apply_*_whitelist(raw)` | VERIFIED | `apply_order_whitelist` import + usage trong `_impl_get_order_status()` |
| `src/selless_mcp/audit.py` | `audit.selless_audit` | parameterized insert of redacted row | VERIFIED | `INSERT INTO audit.selless_audit ... VALUES ($1, $2, $3, $4, $5, $6)` |
| `src/selless_mcp/audit.py` | `src/guards/pii.py` | `redact_text` before persist | VERIFIED | `from src.guards.pii import redact_text`; dùng trong `on_call_tool()` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/knowledge_mcp/server.py::semantic_search` | `candidates` | `hybrid_search()` → `knowledge.kb_chunk` (ANN + FTS queries) | Yes — parameterized DB queries | FLOWING |
| `src/knowledge_mcp/conflict.py::apply_override` | `rows` | `knowledge.policy_resolution` SELECT | Yes — parameterized SELECT; empty if no override rows seeded | FLOWING |
| `src/selless_mcp/server.py::get_order_status` | `raw` | `MockSellessClient.fetch_order()` in tests; `HttpSellessClient` in prod | Yes — mock returns fixture dict with DENY fields to prove whitelist | FLOWING |
| `src/selless_mcp/audit.py::_write_audit_row` | INSERT | `audit.selless_audit` | Yes — parameterized INSERT; fail-closed | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Settings import + secrets redacted | `python -c "import fastmcp, voyageai, mcp, pgvector; from src.config import settings; assert settings.voyage_model == 'voyage-3-large'; r = repr(settings); assert 'voyage_api_key=<REDACTED>' in r and 'selless_api_gateway_key=<REDACTED>' in r; print('Settings-OK')"` | Settings-OK | PASS |
| All Phase 3 tests green | `pytest tests/ingest/ tests/knowledge_mcp/ tests/selless_mcp/ tests/smoke/ -q` | 100 passed, 1 skipped (sandbox) | PASS |
| Phase 3 did not regress Phase 2 tests | `git log e2619b0..HEAD -- tests/test_poller.py tests/test_queue.py` (empty output) | Phase 3 commits không touch Phase 2 test files | PASS |

### Probe Execution

Không có probe scripts theo quy ước `scripts/*/tests/probe-*.sh`. Smoke demo (`tests/smoke/test_grounding_demo.py`) đóng vai trò là executable end-state proof — đã chạy và pass (mock-backed path).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| KB-03 | 03-01, 03-04 | Ingest → normalize → index pipeline xây centralized RAG store | SATISFIED | `src/ingest/pipeline.py::ingest_all()`; `test_pipeline.py` pass |
| KB-04 | 03-01, 03-04 | Knowledge content có thể re-sync/re-index khi policies thay đổi | SATISFIED | `ON CONFLICT (content_hash) DO UPDATE`; `test_idempotent.py` pass |
| KB-05 | 03-02, 03-04 | MCP Knowledge server trả lời semantic queries với source citations | SATISFIED | `semantic_search` tool trả về `SemanticSearchResult{citations, conflict, resolved_by_override}`; hybrid RRF search |
| SEL-01 | 03-03, 03-04 | MCP Selless trả về order info và current order status | SATISFIED | `get_order_status()` → `apply_order_whitelist()` → `OrderDetail` (incl. product fields) |
| SEL-02 | 03-03, 03-04 | MCP Selless trả về customer info và purchase/order history | SATISFIED | `get_customer_info()` + `get_purchase_history()` tools |
| SEL-03 | 03-03, 03-04 | MCP Selless trả về prior ticket history | SATISFIED | `get_ticket_history()` compose Selless ticket-do → Freshdesk client → `TicketHistory`; agent/agent_id denied |
| SEL-04 | 03-03, 03-04 | MCP Selless enforce scoped read-only, rate limiting, audit logging | SATISFIED | `_TokenBucketRateLimiter` + `AuditMiddleware`; tất cả tools `readOnlyHint=True`; fail-closed audit |

**Không có orphaned requirements** — tất cả 7 requirement IDs (KB-03, KB-04, KB-05, SEL-01, SEL-02, SEL-03, SEL-04) đều được claimed bởi plans và được verify.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/selless_mcp/audit.py` | 107, 109 | `result.model_fields` trên instance (Pydantic 2.11 deprecation) | WARNING | `DeprecationWarning` khi chạy smoke test; deprecated in V2.11, sẽ removed trong V3.0. Chưa broken nhưng sẽ cần fix trước khi upgrade Pydantic |
| `src/ingest/cli.py` | 87 | `datetime.datetime.utcnow()` deprecated Python 3.14+ | WARNING | DeprecationWarning trên runtime target (requires-python >=3.14); run_id là timezone-naive |
| `src/ingest/normalize.py` | 40 | `# TBD entries — use best-known expansions` | INFO | Comment trong dict literal — không phải debt marker theo nghĩa code path unimplemented; expansion values đã được fill (`"MOQ": "Minimum Order Quantity"`) |
| `src/ingest/sources.py` | 406 | Sentinel check cho `"TBD"` string trong template_ref | INFO | Data-driven guard (not code debt) — checks nếu template reference chưa được fill trong CODE-MAP.md source data |

**Debt marker gate:** Không có `TBD`, `FIXME`, hay `XXX` unreferenced nào trong src/ files được modified bởi Phase 3. Hai chỗ liên quan `TBD` trong ingest/ đều là data/comment context, không phải unresolved code debt.

### Blocker Resolution Confirmation (từ 03-REVIEW.md)

**CR-01 (D-14 override dead code) — ĐÃ ĐƯỢC FIX và VERIFIED:**
- `Citation.conflict_id: Optional[str] = None` field được thêm vào models.py
- `_PROSE_CONFLICT_MAP` trong sources.py map source filenames → CONTRA-* IDs
- `ingest_all()` carry `conflict_id` vào `kb_chunk.metadata` JSONB
- `assemble_citations()` đọc `metadata.get("conflict_id")` → populate `Citation.conflict_id`
- `_extract_conflict_ids()` đọc `c.conflict_id` trực tiếp (không còn abuse `snapshot_version`)
- `test_override.py` pass với integration tests thực sự

**CR-02 (AuditMiddleware swallows failures) — ĐÃ ĐƯỢC FIX và VERIFIED:**
- `_write_audit_row` không còn `try/except` — INSERT failures propagate
- Pool-unset path raise `RuntimeError` (trừ khi `_audit_test_bypass=True`)
- `assert_audit_pool_configured()` tại server startup enforcement
- `AuditMiddleware.finally` block để `_write_audit_row` exceptions propagate (fail-closed)
- `test_audit.py` pass bao gồm fail-closed tests

### Human Verification Required

#### 1. Live Sandbox Smoke (Task 2 của 03-04 — human-attested blocking checkpoint)

**Test:** Set `VOYAGE_API_KEY` và nếu cần `SELLESS_API_GATEWAY_KEY` trong `.env`, sau đó chạy `RUN_SANDBOX=1 pytest tests/smoke/test_grounding_demo.py -m sandbox -x -q`

**Expected:**
- Live `get_order_status` trả về `OrderDetail` đúng whitelisted shape — không có `payment`, `total_product_cost`, `supplier_name`, `handling_fee` fields
- Live `semantic_search` trả về ít nhất 1 cited passage sau khi ingest từ snapshots thực tế
- Live `audit.selless_audit` row được ghi sau Selless call
- Field shapes của live `OrderDetail` khớp với mock fixtures trong `MockSellessClient` (flag nếu có drift)

**Why human:** Live Selless gateway (`https://api.selless.dev`) được gate bởi network/VPN access — không thể verify trong CI tự động. Voyage API tốn credits. Đây là blocking human-verify checkpoint được thiết kế trong 03-04 Plan Task 2.

**Note:** User đã attest live path qua human attestation (per context notes). Nếu attestation đã được xác nhận, status có thể upgrade lên `passed`.

### Gaps Summary

Không có gaps thực sự. Tất cả 14 must-have truths đã được VERIFIED, tất cả 7 requirement IDs đã được SATISFIED, tất cả artifacts tồn tại và substantive và wired và data flowing.

Hai warnings (Pydantic deprecation, utcnow deprecation) là kỹ thuật nợ nhỏ — không block phase goal. Chúng đã được document trong 03-REVIEW.md (WR-01, WR-05) như là follow-up items.

**Đính chính (orchestrator re-run sạch sau gap-closure):** Không có failures. Báo cáo trước đó nêu "3 failures trong test_poller.py/test_queue.py" không tái lập được — chạy lại sạch: full suite `pytest -q` = **144 passed, 4 skipped (sandbox), 0 failed**; `pytest tests/test_poller.py tests/test_queue.py -q` = **23 passed, 0 failed**. Phán đoán "pre-existing Phase 2 failures" là false alarm và đã được loại bỏ.

Lý do status `human_needed`: Live Selless gateway + Voyage path (Task 2 của 03-04) là blocking human-verify checkpoint theo thiết kế — đây là lần đầu tiên cross gateway-trust boundary thực sự. Nếu human đã attest live path, trạng thái thực chất là `passed`.

---

_Verified: 2026-06-02T07:55:00Z_
_Verifier: Claude (gsd-verifier)_
