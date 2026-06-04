# Customer Support Email Automation (Phase 1)

## What This Is

An AI system that automates customer-support **email** for a US e-commerce business: it re-classifies incoming tickets, extracts the key information needed to answer, and drafts & sends replies **directly into the existing ticket via the Freshdesk API**. It serves the internal CS operation (CS agents + ops) handling ~23,000 emails per 7 days, in English. Phase 1 **answers customers only** — it never executes operational actions (refund, replace, order changes); those stay manual on the Selless CS Portal.

## Core Value

AI sends accurate, trustworthy customer replies at scale so support volume grows without growing headcount linearly — **answer quality is non-negotiable; nothing ships until it clears an evaluation bar.**

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- [x] Knowledge-base **inventory/survey** documents sources, formats, coverage by ticket type, conflicts, update cadence, and tacit knowledge gaps — *Validated in Phase 1: Knowledge Survey & Conflict Inventory (2026-06-01). Delivered SURVEY/GLOSSARY/CODE-MAP/POLICY-THRESHOLD-INDEX/CONFLICT-INVENTORY/COVERAGE-MAP/ACTION-ITEMS; 5 human-review items tracked in 01-HUMAN-UAT.md.*
- [x] **MCP Selless** server exposes the necessary transactional reads (order status, customer info, purchase/order history, full ticket history) with scoped read permissions, rate limiting, and logging — *Validated in Phase 3: Grounding Layer (2026-06-02). Selless MCP is the sole security boundary: explicit-extraction field whitelist (D-04), keyed-only access (D-03), token-bucket rate limit + read-only (D-08), fail-closed PII-redacted audit per call (D-06/D-07). 48+ tests; live gateway human-attested.*
- [x] **MCP Knowledge** server provides semantic search over a centralized knowledge base (policies, product info, prior-ticket patterns) with source citations — *Validated in Phase 3: Grounding Layer (2026-06-02). Cited RRF hybrid search + exact lookups, conflict-aware (D-13 surface-all, D-14 CS-Lead override wired to real ingest data, D-15 stale flag), D-12 authority hierarchy in citations.*
- [x] Knowledge **ingest → normalize → index** pipeline builds the centralized RAG store from Confluence + Google Sheet/Doc — *Validated in Phase 3: Grounding Layer (2026-06-02). Idempotent content_hash upsert (KB-04), Voyage voyage-3-large embeddings into pgvector; re-ingest CLI (D-16).*
- [x] **Per-ticket reply pipeline + safety guards** (classify→extract→ground→draft→critique wrapped by escalation rules + output guards) is assembled as the cs-agent-team — *Validated in Phase 4: Reply Pipeline + Safety Guards (2026-06-04; REOPENED to make the commitment guard template/threshold-aware). REP-01..04, SAFE-03, SAFE-04. The block-all D-13 guard was superseded by the D-26 authorized-offer test (block UNAUTHORIZED offers; permit policy-bounded templated offers) + D-27 hard gate. 5 deterministic hooks, 4 team agents, 5 skills; 276 cs_team tests / 420 repo-wide. Code review found+fixed 2 critical bypasses (escalation + out-of-flow offer). Real-eligibility wiring (RD-Q2/RD-Q3) deferred to plan 04-11 by decision; reply-QUALITY validation is gated by the Phase-5 offline eval bar; 2 live round-trip checks tracked in 04-HUMAN-UAT.md.*

### Active

<!-- Current scope. Building toward these. Hypotheses until shipped & validated. -->

- [ ] AI re-classifies an incoming email/ticket into the correct support category
- [ ] AI extracts the key info needed to answer (order ref, customer, issue type)
- [ ] AI drafts a customer reply grounded in retrieved order data + policy knowledge
- [ ] AI posts the reply directly into the correct existing Freshdesk ticket via API
- [ ] **Offline evaluation harness** scores AI replies against a golden dataset of historical Freshdesk tickets (real agent replies as reference answers), iterated until a defined quality bar is met
- [ ] **Guardrails** auto-route high-risk tickets to a human agent (money-related, complaints/legal, complex/ambiguous) instead of auto-answering
- [ ] **Shadow mode**: AI drafts but does not send; agents review/score before any live sending
- [ ] **Staged rollout**: live on ~5% of volume → increase gradually toward 100% as quality holds

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Taking operational actions (refund, replace, order/status changes) — Phase 1 only answers customers; ops stays manual on Selless CS Portal until reply quality is proven
- Call/voice support — deferred to a later phase, no concrete design yet
- Contact Form chatbot across domains — candidate for a later phase (≈phase 3)
- Non-English languages — US market is always English
- Writing/curating the knowledge content itself — we ingest & normalize existing sources; authoring missing/tacit knowledge is a CS-team responsibility surfaced by the survey

## Context

- **Volume:** ~23,000 emails per 7 days (~3,200+/day). Market: US, language: English only.
- **Current channels:** email, Contact Form, call. Phase 1 = email only.
- **Current tooling:** CS agents answer via Freshdesk + Freshdesk Call. Ticket operations (refund/replace) happen on the **CS Portal in the Selless system**.
- **Email ingestion:** primarily email forwarding (IMAP/SMTP) into Freshdesk. Selless syncs tickets two-way with Freshdesk (pulls Freshdesk tickets; pushes tickets created in Selless, e.g. Contact Form).
- **Data the AI needs:** (1) order info + purchase history, (2) company policy (returns, warranty, shipping), (3) product catalog/variants, (4) the customer's prior ticket history.
- **Selless reality:** has APIs but built for the platform, not for AI — scattered across features. Decision: build an **MCP layer** so AI fetches only the needed fields under control.
- **Knowledge reality:** policies/knowledge are scattered across Confluence + Google Sheet/Doc, used today to train new CS hires. Quality/consistency is **not yet confirmed** — needs a survey before relying on it. Conflicting/stale content is the top hallucination risk.
- **Most common ticket types:** order/tracking questions · returns/refunds/exchanges · quality complaints · policy/product questions.
- **Highest-risk ticket types (always route to agent):** money-related · complaints/legal · complex/ambiguous multi-issue tickets.
- **Golden dataset:** historical tickets + real agent replies are obtainable from Freshdesk via **export** (not a convenient live API path) — usable as evaluation reference answers.
- **Prior session:** this project resumed from `Plan-discussion.md`, a verbatim transcript of the earlier deep-questioning session.

## Constraints

- **Integration**: AI must post replies through the **Freshdesk API into the existing ticket** — Why: keep full conversation history intact inside Freshdesk for agents.
- **Data access**: Selless reads go through a **dedicated MCP** with scoped permissions/rate-limit/logging — Why: native Selless APIs are scattered and not designed for AI; uncontrolled access is unsafe.
- **Architecture**: keep **two separate MCPs** — Selless (transactional, real-time, lookup-by-ID) and Knowledge (semantic RAG, centralized, cited) — Why: different update cadence, query model, and quality-control needs; mixing them is an architectural mistake.
- **Quality**: nothing goes live before clearing the offline-eval bar; high-risk categories always escalate to a human — Why: 23k/week volume makes a bad auto-reply high-blast-radius.
- **Rollout**: offline eval → shadow mode → live 5% → scale to 100% — Why: de-risk a large-volume rollout incrementally.
- **Knowledge readiness**: knowledge base must be surveyed and centralized before AI relies on it — Why: scattered/conflicting sources cause hallucinations; AI must not read raw Confluence/Sheets per-reply.

## Key Decisions

<!-- Decisions that constrain future work. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase 1 answers customers only; no operational actions | De-risk; prove reply quality before automating ops | — Pending |
| Build a dedicated MCP for Selless reads | Native APIs scattered, not AI-ready; need scoped/controlled access | — Pending |
| Two separate MCPs (Selless transactional + Knowledge RAG) | Different cadence, query model, and QC needs | — Pending |
| Centralize knowledge into a RAG store with citations | Cannot reliably read scattered Confluence/Sheets per-reply; need anti-hallucination grounding | — Pending |
| Offline eval on a golden set before any live use | Establish a measurable quality bar before exposing customers | — Pending |
| Rollout: offline eval → shadow → 5% live → scale | Incremental de-risking at high volume | — Pending |
| Auto-escalate high-risk tickets (money/legal/complex) to agents | Limit blast radius of wrong answers | — Pending |
| Knowledge survey is a lightweight inventory, not full collection, before planning | Avoid blocking on a "perfect" KB; detailed ingest is its own phase | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-04 — Phase 4 (Reply Pipeline + Safety Guards) complete (REOPENED for authorized-offer guard): cs-agent-team pipeline + 5 deterministic hooks shipped (REP-01..04, SAFE-03/04); block-all D-13 → D-26 authorized-offer + D-27 gate; verification 4/4 must-haves (human_needed: 2 live round-trips + done safety-contract update in 04-HUMAN-UAT.md); 2 critical code-review bypasses fixed; RD-Q2/RD-Q3 real eligibility deferred to 04-11. Next: Phase 5 offline-eval gate.*
