# Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 3-grounding-layer-selless-mcp-knowledge-rag-mcp
**Areas discussed:** Selless access & keying, Conflict-aware grounding, RAG content & authority, Selless scope/PII/audit

---

## Gray-area selection

User selected all four offered areas and added framing: Selless access via **API** (orders, customers, product, inventory); knowledge base (policy, workflow) stored in **Postgres** — because production deploy must connect the same way.

---

## Selless access & keying

### Selless API status
| Option | Description | Selected |
|--------|-------------|----------|
| Đã có đủ (docs+token) | Endpoints + credentials + docs ready to call now | |
| Có API nhưng chưa rõ endpoint | API exists but scattered/unstandardized — RESEARCH FLAG | ✓ |
| Chưa có quyền/credential | No access yet; build interface + mock first | |

### Selless MCP language
| Option | Description | Selected |
|--------|-------------|----------|
| Python/FastMCP | Same toolchain as repo + Knowledge MCP | ✓ |
| TypeScript SDK | Only if a Node/TS Selless backend is worth reusing | |

### Tool input keying
| Option | Description | Selected |
|--------|-------------|----------|
| Cả order_id và email | Each tool accepts order_id or verified email; no cross-customer search | ✓ |
| Chỉ order_id | Lookup by order ID only | |
| Bạn quyết định | Defer to researcher/planner | |

**User's choice:** API (endpoint unknown → research flag) · Python/FastMCP · key by both order_id and email.
**Notes:** Selless API is "built for the platform, not for AI" — researcher surveys it; user supplies docs/credentials when available.

---

## Conflict-aware grounding

### Behavior on conflicting passages
| Option | Description | Selected |
|--------|-------------|----------|
| Trả tất cả + cờ conflict | Return all conflicting passages + conflict flag; MCP does not arbitrate | ✓ |
| Xếp hạng → chọn winner | Pick a winner via authority/recency | |
| Winner + cờ để escalate | Return top-authority but still flag conflict | |

### Resolving the 18 known conflicts
| Option | Description | Selected |
|--------|-------------|----------|
| Override table | Ingest raw + policy-resolution/override table that wins when present | ✓ |
| Canonical trước ingest | CS Lead resolves all conflicts before ingest | |
| Chỉ flag query-time | Ingest raw + tag conflicts, push all arbitration to query-time | |

### Stale content
| Option | Description | Selected |
|--------|-------------|----------|
| Downrank + cảnh báo | Still retrievable but downranked + recency flag | ✓ |
| Loại khỏi retrieval | Exclude stale content entirely | |
| Bạn quyết định | Defer to planner | |

**User's choice:** Return-all + conflict flag · override table · downrank + recency flag.
**Notes:** Conservative anti-hallucination posture; CS Lead populates override rulings over time.

---

## RAG content & authority

### Thresholds & code-map storage
| Option | Description | Selected |
|--------|-------------|----------|
| Structured exact | Thresholds + code-map in Postgres exact-lookup tables; prose stays semantic | ✓ |
| Tất cả semantic | Chunk everything into the vector store | |
| Bạn quyết định | Defer | |

### Source authority hierarchy
| Option | Description | Selected |
|--------|-------------|----------|
| Confluence > Templates > Whimsical | Official docs rank highest | |
| Templates > Confluence > Whimsical | What agents actually send ranks highest | |
| Bạn quyết định / CS Lead | CS Lead decides; store as metadata | |

### Email Templates role
| Option | Description | Selected |
|--------|-------------|----------|
| Retrieval riêng 'template library' | Separate template-library retrieval surface | ✓ |
| Gộp chung policy RAG | Chunk into the same policy store, distinguish by metadata | |
| Bạn quyết định | Defer | |

### KB-04 re-sync trigger
| Option | Description | Selected |
|--------|-------------|----------|
| Manual re-export + lệnh re-ingest | Refresh snapshots + run idempotent re-ingest | ✓ |
| Watch nguồn tự động | Connect source APIs to auto-detect changes | |
| Bạn quyết định | Defer | |

**User's choice:** Structured exact (thresholds + code-map) · **authority WorkFlow > Templates > Confluence** (free-text: "Workflow quan trọng nhất, xong đến Template, cuối cùng là Confluence (trong này chủ yếu hướng dẫn)") · separate template library · manual re-export + re-ingest.
**Notes:** Authority order is intentionally workflow-first because the Whimsical diagram is the operational source of truth; Confluence is mostly guidance.

---

## Selless scope/PII/audit

### Scope mechanism
| Option | Description | Selected |
|--------|-------------|----------|
| Whitelist field cứng | Fixed allow-list; hard-deny card/cost/other-customer PII | ✓ |
| Trả tất, lọc sau | Return full Selless response, filter upstream | |
| Bạn quyết định | Defer whitelist to planner | |

### PII handling
| Option | Description | Selected |
|--------|-------------|----------|
| Đủ cho drafter, redact ở log | Real PII to drafter; Presidio redacts at log/audit boundary | ✓ |
| Redact cả với drafter | Tokenize PII even in model context | |
| Bạn quyết định | Defer | |

### Audit log
| Option | Description | Selected |
|--------|-------------|----------|
| Bảng Postgres, PII-redacted | Audit table: caller, tool, input ID, redacted fields, ts, latency | ✓ |
| Structured log/metric | JSON log + metric only | |
| Bạn quyết định | Defer | |

### Prior ticket history source (SEL-03)
| Option | Description | Selected |
|--------|-------------|----------|
| Từ Freshdesk | Reuse Phase-2 Freshdesk client for ticket history | |
| Từ Selless API | Selless exposes ticket history (two-way sync) — single transactional surface | ✓ |
| Bạn quyết định | Defer to researcher | |

**User's choice:** Hard field whitelist · PII to drafter + redact at log · Postgres audit table · ticket history from Selless API.
**Notes:** Keep Selless MCP as the single transactional surface; researcher to confirm Selless exposes ticket history.

---

## Claude's Discretion

- Phase 3 demonstrable end-state (standalone MCP smoke test — mirror Phase 2 sandbox demo)
- Selless MCP rate-limit values/algorithm (per-tool/per-minute)
- Embedding/index details within the locked stack (Voyage voyage-3-large, HNSW params, hybrid search wiring, optional reranker)
- Prose chunking strategy
- Exact Postgres schemas (KB chunks, exact tables, template library, override table, audit) + `src/` module layout
- Selless API client retry/backoff/error taxonomy (reuse Phase-2 httpx + tenacity pattern)

## Deferred Ideas

- Automated source-watching for re-sync (needs source-side API credentials)
- Pre-ingest canonical policy curation (long-term ideal once override rulings accumulate)
- Reranker tuning / hybrid-search weighting (follow-up if retrieval is the bottleneck)
- Channel scope vs volume re-check (project-level, for `/gsd:complete-milestone`)
