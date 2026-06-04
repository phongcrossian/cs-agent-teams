# Requirements: Customer Support Email Automation (Phase 1)

**Defined:** 2026-05-27
**Core Value:** AI sends accurate, trustworthy customer email replies at scale so support volume grows without growing headcount linearly — answer quality is non-negotiable; nothing ships until it clears an evaluation bar.

> **PIVOT — 2026-06-04 (D-29 / D-30, user-confirmed).** A live 30-ticket test showed the RAG-grounded path could not draft (empty KB, no Voyage key). The product direction is now **PoC-first, always-draft**: reply grounding = **Template library (local) + Workflow/CODE-MAP (local) + Selless API (production)**; **semantic RAG / Voyage embeddings dropped (KB-05 superseded)**; the **hard output guard / escalation / mandatory-citation requirements are retired** (SAFE-04 superseded; SAFE-03 → advisory; D-08/D-10/D-11/D-13/D-26/D-27 retired). Remaining safety floor: injection screening (D-14) + PII redaction (D-04) + kill-switch (SAFE-06).
> ⚠️ **Trade-off:** removing the guard lets the AI auto-send unauthorized refund/credit/legal commitments at scale — accepted as a deliberate PoC-direction decision; revisit before any live (non-DRY_RUN) send.

## v1 Requirements

Requirements for the initial release. Each maps to roadmap phases.

### Knowledge Base

- [x] **KB-01**: Knowledge survey produces an inventory of all sources (Confluence spaces, Google Sheets/Docs), their formats, and coverage per common ticket type
- [x] **KB-02**: Knowledge survey produces a conflict inventory flagging stale, contradictory, or missing policy content
- [x] **KB-03**: An ingest → normalize → index pipeline builds a centralized RAG store from the surveyed sources
- [x] **KB-04**: Knowledge content can be re-synced/re-indexed when policies change
- [~] **KB-05** *(SUPERSEDED by D-29, 2026-06-04)*: ~~An MCP Knowledge server answers semantic queries over the RAG store and returns source citations~~ → replaced by **local template lookup (exact/keyed `get_template`) + Workflow/CODE-MAP mapping**. No semantic search, no Voyage embeddings.

### Transactional Data (MCP Selless)

- [x] **SEL-01**: An MCP Selless server returns order info and current order status by order ID or customer email
- [x] **SEL-02**: MCP Selless returns customer info and purchase/order history
- [x] **SEL-03**: MCP Selless returns the customer's prior ticket history for context
- [x] **SEL-04**: MCP Selless enforces scoped read-only permissions, rate limiting, and audit logging on every call

### Reply Pipeline

- [x] **REP-01**: AI re-classifies an incoming email/ticket into the correct support category
- [ ] **REP-02**: AI extracts the key info needed to answer (order ref, customer, issue type)
- [x] **REP-03** *(reworded by D-29, 2026-06-04)*: AI drafts a reply by selecting the correct **template** (via Workflow/CODE-MAP) and filling it from **Selless order data (production)** + the ticket. Grounding = approved template + order data; mandatory inline citations no longer required (D-11 retired).
- [ ] **REP-04**: AI runs a self-critique pass scoring the draft against the quality rubric before any send
- [x] **REP-05**: AI posts the approved reply into the correct existing Freshdesk ticket via API, idempotently (no duplicate sends)

### Safety & Rollout

- [ ] **SAFE-01** *(rescoped by D-30)*: An offline evaluation harness scores AI replies against a golden dataset of historical Freshdesk tickets (real agent replies as reference), reporting **template-selection correctness + reply-quality** (faithfulness/correctness/tone) — **advisory scores**, not a hard gate
- [ ] **SAFE-02** *(rescoped by D-30)*: Go-live is informed by the offline-eval scores (advisory bar) — no longer a hard "0-UNAUTHORIZED-commitments" block (D-21/D-27 retired)
- [x] **SAFE-03** *(ADVISORY per D-30)*: ~~auto-routes high-risk tickets to a human instead of auto-answering~~ → downgraded to optional/advisory routing; the always-draft pipeline does not block. ⚠️ Re-evaluate for money/legal before any live send
- [~] **SAFE-04** *(SUPERSEDED/REMOVED by D-30, 2026-06-04)*: ~~An output guard blocks commitment-language the system is not authorized to make~~ → the hard `pre_send_guard` block is retired; the pipeline always drafts. Offers are filled per the chosen template.
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
| KB-03 | Phase 3 | Complete |
| KB-04 | Phase 3 | Complete |
| KB-05 | Phase 3 | Superseded (D-29) — local template lookup, no RAG |
| SEL-01 | Phase 3 | Complete |
| SEL-02 | Phase 3 | Complete |
| SEL-03 | Phase 3 | Complete |
| SEL-04 | Phase 3 | Complete |
| REP-01 | Phase 4 | Complete |
| REP-02 | Phase 4 | Pending |
| REP-03 | Phase 4 | Complete |
| REP-04 | Phase 4 | Pending |
| REP-05 | Phase 2 | Complete |
| SAFE-01 | Phase 5 | Pending (rescoped D-30 — advisory scores) |
| SAFE-02 | Phase 5 | Pending (rescoped D-30 — advisory bar) |
| SAFE-03 | Phase 4 | Advisory (D-30 — non-blocking) |
| SAFE-04 | Phase 4 | Superseded (D-30 — guard removed) |
| SAFE-05 | Phase 7 | Pending |
| SAFE-06 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-27*
*Last updated: 2026-06-04 — PoC pivot (D-29/D-30): dropped semantic RAG/Voyage (KB-05 superseded), reground on Template+Workflow+Selless (REP-03), retired hard guard/escalation/citations (SAFE-04 superseded, SAFE-03 advisory), rescoped eval gate to advisory (SAFE-01/02).*
