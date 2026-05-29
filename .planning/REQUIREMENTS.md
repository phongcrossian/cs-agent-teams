# Requirements: Customer Support Email Automation (Phase 1)

**Defined:** 2026-05-27
**Core Value:** AI sends accurate, trustworthy customer email replies at scale so support volume grows without growing headcount linearly — answer quality is non-negotiable; nothing ships until it clears an evaluation bar.

## v1 Requirements

Requirements for the initial release. Each maps to roadmap phases.

### Knowledge Base

- [x] **KB-01**: Knowledge survey produces an inventory of all sources (Confluence spaces, Google Sheets/Docs), their formats, and coverage per common ticket type
- [x] **KB-02**: Knowledge survey produces a conflict inventory flagging stale, contradictory, or missing policy content
- [ ] **KB-03**: An ingest → normalize → index pipeline builds a centralized RAG store from the surveyed sources
- [ ] **KB-04**: Knowledge content can be re-synced/re-indexed when policies change
- [ ] **KB-05**: An MCP Knowledge server answers semantic queries over the RAG store and returns source citations with each result

### Transactional Data (MCP Selless)

- [ ] **SEL-01**: An MCP Selless server returns order info and current order status by order ID or customer email
- [ ] **SEL-02**: MCP Selless returns customer info and purchase/order history
- [ ] **SEL-03**: MCP Selless returns the customer's prior ticket history for context
- [ ] **SEL-04**: MCP Selless enforces scoped read-only permissions, rate limiting, and audit logging on every call

### Reply Pipeline

- [ ] **REP-01**: AI re-classifies an incoming email/ticket into the correct support category
- [ ] **REP-02**: AI extracts the key info needed to answer (order ref, customer, issue type)
- [ ] **REP-03**: AI drafts a reply grounded in retrieved order data and knowledge-base content (no ungrounded claims)
- [ ] **REP-04**: AI runs a self-critique pass scoring the draft against the quality rubric before any send
- [ ] **REP-05**: AI posts the approved reply into the correct existing Freshdesk ticket via API, idempotently (no duplicate sends)

### Safety & Rollout

- [ ] **SAFE-01**: An offline evaluation harness scores AI replies against a golden dataset of historical Freshdesk tickets (real agent replies as reference), reporting faithfulness/correctness metrics
- [ ] **SAFE-02**: Go-live is gated on the offline-eval score meeting a defined quality bar
- [ ] **SAFE-03**: A guardrail layer auto-routes high-risk tickets (money/refund, legal/complaints, complex/ambiguous) to a human agent instead of auto-answering
- [ ] **SAFE-04**: An output guard blocks commitment-language (e.g. promising refunds/actions) the system is not authorized to make
- [ ] **SAFE-05**: A staged rollout control sends AI replies to a configurable percentage of volume (5% → 100%) with deterministic, stable bucketing
- [ ] **SAFE-06**: A live quality dashboard monitors AI reply performance, and a kill-switch can immediately halt auto-sending

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Safety & Quality

- **SHAD-01**: Live shadow mode — AI drafts on real incoming traffic but does not send; agents review/score the drafts before any live sending (deferred: offline eval on historical answered tickets serves as the v1 quality gate)
- **FEED-01**: Feedback loop capturing agent edits/corrections back into the golden eval set and threshold tuning
- **THRS-01**: Per-category confidence thresholds (vs a single global gate)
- **DEFL-01**: Deflection / auto-resolution metrics (answered vs resolved) with an honest measurement definition

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Operational actions (refund, replace, order/status changes) | Phase 1 answers customers only; ops stays manual on Selless CS Portal until reply quality is proven |
| Call/voice support automation | Deferred to a later phase; no concrete design yet |
| Contact Form chatbot across domains | Candidate for a later phase (≈phase 3) |
| Non-English languages | US market is always English |
| Authoring/curating new knowledge content | We ingest & normalize existing sources; writing missing/tacit knowledge is a CS-team responsibility surfaced by the survey |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| KB-01 | Phase 1 | Complete |
| KB-02 | Phase 1 | Complete |
| KB-03 | Phase 3 | Pending |
| KB-04 | Phase 3 | Pending |
| KB-05 | Phase 3 | Pending |
| SEL-01 | Phase 3 | Pending |
| SEL-02 | Phase 3 | Pending |
| SEL-03 | Phase 3 | Pending |
| SEL-04 | Phase 3 | Pending |
| REP-01 | Phase 4 | Pending |
| REP-02 | Phase 4 | Pending |
| REP-03 | Phase 4 | Pending |
| REP-04 | Phase 4 | Pending |
| REP-05 | Phase 2 | Pending |
| SAFE-01 | Phase 5 | Pending |
| SAFE-02 | Phase 5 | Pending |
| SAFE-03 | Phase 4 | Pending |
| SAFE-04 | Phase 4 | Pending |
| SAFE-05 | Phase 7 | Pending |
| SAFE-06 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-27*
*Last updated: 2026-05-27 after roadmap creation (traceability mapped to 7 phases)*
