# Roadmap: Customer Support Email Automation (Phase 1)

## Overview

This roadmap takes a high-volume (~23k emails/7 days, English, US e-commerce) AI support-email system from zero to a quality-gated live rollout. The journey follows the committed safe-deployment spine: survey the knowledge base and catalog its conflicts first (the #1 hallucination defense), build the isolated Freshdesk I/O layer and queued pipeline backbone everything posts through, stand up the two grounding surfaces (transactional Selless MCP + semantic Knowledge MCP/RAG), assemble the classify→extract→ground→draft orchestrator with its safety guards, then make the offline eval harness the load-bearing go-live gate. Only after monitoring + a kill-switch exist does a single routing gate enable the staged 5%→100% rollout. Nothing ships until it clears the evaluation bar.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Knowledge Survey & Conflict Inventory** - Catalog every KB source, coverage by ticket type, and conflicts/staleness before any RAG is built
- [x] **Phase 2: Freshdesk I/O Layer & Pipeline Backbone** - Isolated, rate-limit-aware Freshdesk client + queued intake with idempotent, loop-safe posting (completed 2026-06-01)
- [x] **Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP)** - Two separate scoped grounding surfaces: transactional reads + cited semantic search over the ingested KB (completed 2026-06-02)
- [x] **Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards** - End-to-end grounded draft with classification, self-critique, escalation rules, and output guards (first pass completed 2026-06-03; REOPENED 2026-06-03 for D-26/D-27 guard; **RE-OPENED AGAIN 2026-06-04 for the D-29/D-30 PoC pivot — always-draft code rework D-31..D-34: retire Knowledge MCP→file-store, DELETE guard hooks, always-draft+advisory verdict, flow-aware Selless fallback; 12 prior plans stale, new plan set needed**) (completed 2026-06-05)
- [ ] **Phase 5: Offline Evaluation Harness (THE GATE)** - Score replies against a golden dataset on faithfulness/correctness; the bar that authorizes go-live
- [ ] **Phase 6: Routing Gate, Monitoring & Kill-Switch** - Single chokepoint with deterministic bucketing + live dashboard and kill-switch in place before any live send
- [ ] **Phase 7: Staged Rollout (5% → 100%)** - Controlled, quality-gated exposure scaling from 5% to full volume
- [ ] **Phase 8: Ticket Re-Classification & FD Property Write-Back** - AI re-classifies each ticket and defines the core Freshdesk classification properties (Level_in, Customer_Request, Rootcause, Flow, Section_Flow) mapped to exact ticket_fields enums — DRY_RUN would-be update in PoC (live FD write-back deferred)

## Phase Details

### Phase 1: Knowledge Survey & Conflict Inventory
**Goal**: Produce a trustworthy picture of the existing knowledge base — what sources exist, what they cover, and where they conflict or go stale — so RAG is built on a known foundation rather than indexed blindly.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: KB-01, KB-02
**Success Criteria** (what must be TRUE):
  1. A reviewer can open a source inventory listing every Confluence space and Google Sheet/Doc with its format and last-update cadence
  2. A reviewer can see coverage mapped against the common ticket types (order/tracking, returns/refunds, quality complaints, policy/product) with gaps named
  3. A reviewer can read a conflict inventory that flags stale, contradictory, or missing policy content as explicit findings (not edge cases)
  4. CS-team-owned knowledge gaps (tacit/missing content) are surfaced as action items, not silently absorbed
**Plans**: 4 plans
- [x] 01-01-PLAN.md — Whimsical workflow vertical slice: SURVEY.md skeleton + GLOSSARY + CODE-MAP + Policy-Threshold Index (autonomous, Wave 1)
- [x] 01-02-PLAN.md — Email Templates survey + code→template wiring (Wave 2, CS-Lead-gated for full enumeration)
- [x] 01-03-PLAN.md — Confluence SCE root-cause guides survey + taxonomy (Wave 2, CS-Lead-gated access)
- [x] 01-04-PLAN.md — Convergence: conflict inventory + threshold axis, coverage-map CSV (evidence-validated), CS-team action items (Wave 3)

### Phase 2: Freshdesk I/O Layer & Pipeline Backbone
**Goal**: Stand up the only module allowed to talk to Freshdesk plus the queued, stateless intake it feeds — centralizing rate-limit handling, the reply-vs-note distinction, and the idempotency/loop guards that prevent duplicate or runaway sends.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: REP-05
**Success Criteria** (what must be TRUE):
  1. An inbound Freshdesk ticket event reaches a queued worker via webhook (with a safety-net poller as reconciliation backup) and is processed exactly once
  2. The system can post a reply into the correct existing ticket via the Freshdesk API, and a retried or duplicate inbound never produces a second send (idempotency key per inbound)
  3. The client honors Freshdesk rate limits (backoff/jitter, `Retry-After`) and routes repeated failures to a dead-letter path for a human instead of dropping silently
  4. Auto-generated / no-reply / mailer-daemon mail and synced ticket updates are detected and never trigger an auto-reply loop
**Plans**: 6 plans (5 waves; revised per cross-AI review — true exactly-once across crash, durable poller checkpoint, list_updated_tickets, unified loop-guard)
- [x] 02-01-PLAN.md — Wave 0 bootstrap: uv project + docker-compose Postgres 16 + Alembic schema `queue` (ticket_queue +sent_at/+freshdesk_reply_id, dead_letter, dry_run_log, poller_checkpoint) + test scaffolding (incl. 3 mandatory RED tests) + Presidio backend (Wave 0)
- [x] 02-02-PLAN.md — Freshdesk I/O client (reply public + note private, D-04) + list_updated_tickets/Ticket model + retry/Retry-After/error taxonomy (409→fatal) (D-10) (Wave 1)
- [x] 02-03-PLAN.md — Postgres idempotency queue (`src/work_queue/`): dedup-at-insert + SKIP LOCKED claim (deterministic order) + stale recovery (D-01/D-02/D-11) (Wave 1)
- [x] 02-04-PLAN.md — Worker assembly + unified loop-guard (D-06, should_suppress single source of truth + per-ticket throttle) + send-intent transactional/pre-send guard (exactly-once across crash) + DeadLetterSink protocol + Presidio PII redaction (D-12) + send-mode switch (D-05); D-07 sandbox verify checkpoint (Wave 2)
- [x] 02-05-PLAN.md — Intake: HMAC webhook receiver + reconciliation poller with durable checkpoint, both feeding the same queue via shared resolve (D-09) (Wave 3)
- [x] 02-06-PLAN.md — Retry/dead-letter hardening (D-10, PostgresDeadLetterSink + exhausted-sweeper) + main.py wiring + sandbox e2e demo proving exactly-once incl. crash-after-post (D-03) (Wave 4)

### Phase 3: Grounding Layer (Selless MCP + Knowledge RAG MCP)
> **PIVOT (D-29, 2026-06-04):** the **Knowledge semantic-RAG MCP is DEPRECATED** (no Voyage embeddings, no semantic_search). Grounding source is now the **local template store + Workflow/CODE-MAP** (exact `get_template`/keyed lookup) plus the **Selless MCP** (production reads), which both remain. Criterion #1 (cited semantic query) no longer applies.
**Goal**: Build the two separate grounding surfaces the drafter relies on — a transactional Selless MCP for scoped lookup-by-ID reads and a Knowledge MCP serving cited semantic search over an ingested, conflict-aware RAG store — so the orchestrator never reads source systems directly.
**Mode:** mvp
**Depends on**: Phase 1 (survey gates KB ingest), Phase 2 (foundation)
**Requirements**: KB-03, KB-04, KB-05, SEL-01, SEL-02, SEL-03, SEL-04
**Success Criteria** (what must be TRUE):
  1. The Knowledge MCP answers a semantic query over the ingested RAG store and returns passages with source citations carrying source/recency/authority metadata
  2. The KB ingest pipeline builds the centralized store from the surveyed Confluence + Google sources and can be re-synced/re-indexed when policies change
  3. The Selless MCP returns order status, customer info, purchase history, and prior ticket history keyed to the ticket's verified customer/order ID (no free-text cross-customer search)
  4. Every Selless MCP call is read-only, scope-enforced, rate-limited, and audit-logged
**Plans**: 5 plans (4 waves; vertical MVP slices over a Wave-0 bootstrap; Plans 02 & 03 run parallel in Wave 2)
- [x] 03-00-PLAN.md — Wave 0 bootstrap: deps (fastmcp/voyageai/pgvector, supply-chain human-verify) + Alembic 0002 knowledge schema (pgvector/pg_trgm) + 0003 audit schema + Settings extension + 12 RED test stubs (D-09)
- [x] 03-01-PLAN.md — KB ingest → normalize → index pipeline + idempotent re-ingest CLI; prose chunks + exact threshold/code-map/template rows from Phase-1 snapshots (KB-03/KB-04, D-10/D-16, Wave 1)
- [x] 03-02-PLAN.md — Knowledge MCP query surface: cited semantic_search (RRF hybrid) + exact lookup_threshold/lookup_code/get_template + conflict flag/override (KB-05, D-12/D-13/D-14/D-15, Wave 2)
- [x] 03-03-PLAN.md — Selless MCP: keyed reads + resolve_order + field whitelist + PII-redacted audit + rate-limit/read-only at the sole security boundary, on MockSellessClient (SEL-01..04, D-02/D-03/D-04/D-06/D-07/D-08, Wave 2)
- [x] 03-04-PLAN.md — Standalone MCP-client smoke demo proving all 4 success criteria + live gateway/Voyage human-verify (D-05, Wave 3)
**UI hint**: no

### Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards
**Goal**: Assemble the per-ticket pipeline that re-classifies the ticket, extracts the answer key, drafts a citation-grounded reply via the two MCPs, self-critiques against the rubric, and is wrapped by the escalation rules and output guards that make it safe to evaluate.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: REP-01, REP-02, REP-03, REP-04, SAFE-03, SAFE-04
**Success Criteria** (what must be TRUE):
  1. An incoming ticket is re-classified into the correct support category with a confidence signal, and the order ref / customer / issue type are extracted
  2. The orchestrator produces a draft grounded in **Selless order data + the selected template** (Workflow/CODE-MAP) — *(D-29/D-30 2026-06-04: mandatory inline citations and the self-critique-before-send hard gate are RETIRED; the pipeline always drafts)*
  3. ~~High-risk tickets are auto-routed to a human — any high-risk signal escalates~~ → *(D-30: ADVISORY/optional, non-blocking; always-draft. ⚠️ revisit money/legal before live send)*
  4. ~~An output guard blocks unauthorized commitments (out-of-template / over-threshold)~~ → *(SUPERSEDED by D-30, 2026-06-04: the hard `pre_send_guard` block is REMOVED — offers are filled per the chosen template, no block).* Email body is still treated as untrusted data (delimited, **injection-screened — retained, D-14**).
**Plans**: 7 plans (4 waves; RE-PLANNED 2026-06-04 from scratch for the D-29/D-30 always-draft PoC pivot, then targeted-revised to add the test-suite cleanup (04-04) + subagent-skill rework (04-05) — D-31..D-34 code rework; the prior 12 plans 04-00..04-11 were built for the now-retired RAG + fail-closed authorized-offer-guard architecture and are archived in _superseded/d29-d30-pivot/. New numbering from 04-00. MVP vertical slices: file-store + dep-strip / hook-deletion (Wave 1, parallel) → always-draft agent-team rework + subagent-skill rework (Wave 2, parallel) → end-to-end always-draft DRY_RUN demo + cs_team test-suite cleanup (Wave 3, parallel))
- [x] 04-00-PLAN.md — Local Template + Workflow/CODE-MAP file-store loader (get_template_from_file / subtype_to_code, reads the 26 Phase-1 snapshots; no RAG/MCP) + strip voyageai/pgvector(RAG)/ragas from pyproject.toml (D-31/REP-03, Wave 1)
- [x] 04-01-PLAN.md — DELETE the 4 retired guard hooks (pre_send_guard, escalation_gate, grounding_check, authorized_offer) + their settings.json wiring; KEEP injection_screen (D-14) + pii_redact (D-04); deletion-assertion test (D-32/SAFE-04/SAFE-03, Wave 1)
- [x] 04-02-PLAN.md — Always-draft agent-team rework: remove KnowledgeMCP from settings.json; cs-lead/classifier/extractor/drafter/critic agents + reply-pipeline/ground-and-draft skills → file-store grounding (D-31), action=draft + optional advisory escalation_hint (D-33), flow-aware Selless fallback (D-34); no semantic_search/mandatory-citations/D-26 gate; D-03/D-04/D-14 retained (REP-01/02/03/04 + SAFE-03, Wave 2)
- [x] 04-03-PLAN.md — Rework scripts/cs_team_demo.py to always-draft + advisory hint + D-34 fallback (no deleted-guard imports, file-store grounded, DRY_RUN submit_reply, injection_screen as advisory pre-screen); fixtures + always-draft contract test across benign/high-risk/injection/missing-order (SAFE-03/SAFE-04/REP-03, Wave 3)
- [x] 04-04-PLAN.md — Clean tests/cs_team to the always-draft contract: DELETE 6 retired-contract test files + slim conftest to injection_screen/pii_redact; REWRITE e2e/settings-bindings/team-definitions/kit-structure to always-draft + two-hook + file-store; pytest tests/cs_team -q GREEN (REP-01/REP-04/SAFE-03/SAFE-04, Wave 3)
- [x] 04-05-PLAN.md — Rework subagent-detail skills classify-ticket/extract-answer-key/self-critique to advisory signals + D-34 flow semantics + file-store faithfulness (no lookup_code/semantic_search/[KB-N]/escalate=no-draft; REP-01/02/04 + SAFE-03 dimensions kept), Wave 2
- [x] 04-06-PLAN.md — `/test-ticket` on-demand command (D-41..D-45): add `run --id/--list/--limit/--per-cat` subcommand to scripts/test_tickets_run.py reusing collect() real-team path (D-35) + build_xlsx(); parse `;`-delimited uat_ticket.csv (bucket by Level_in) capped with logged drops (D-43); thin .claude/commands/test-ticket.md slash wrapper (no logic); DRY_RUN read-only PROD, outputs to gitignored test-tickets.xlsx only (D-39/D-44); reuses deterministic _SUBTYPE_TEMPLATES (no free-pick) (REP-03/REP-04/SAFE-03/SAFE-04, Wave 1)
**UI hint**: no

### Phase 5: Offline Evaluation Harness (THE GATE)
> **PIVOT (D-30, 2026-06-04):** the gate is **rescoped from hard-blocking to ADVISORY**. It no longer gates on "0 UNAUTHORIZED commitments / 100% high-risk escalation" (D-21/D-27 retired). It **scores template-selection correctness + reply quality** (faithfulness/correctness/tone) vs the reference replies and reports them; go-live is informed, not hard-blocked, by these scores. Criterion #3 below is superseded accordingly.
**Goal**: Make answer quality measurable and binding — replay a golden dataset of historical tickets through the same production pipeline code, score faithfulness/correctness/tone (not similarity to flawed past replies), and define the numeric quality bar that gates go-live.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: SAFE-01, SAFE-02
**Success Criteria** (what must be TRUE):
  1. The harness replays the golden dataset (Freshdesk export → normalized, PII-handled JSONL) through the production orchestrator/guardrail code and never posts to Freshdesk
  2. Reports show faithfulness/correctness (and tone) metrics with a stratified set including high-risk, adversarial/injection, and conflicting-policy cases — plus a held-out set the pipeline was never tuned against
  3. A defined quality bar exists (e.g., grounding-correct ≥ target, zero refund-commitment leaks, 100% high-risk escalation) and a run produces an explicit pass/fail go-live verdict against it
**Plans**: TBD

### Phase 6: Routing Gate, Monitoring & Kill-Switch
**Goal**: Build the single chokepoint every candidate reply passes through — risk rules + grounding check + deterministic hash-bucket mode resolution — and the live monitoring dashboard plus kill-switch that MUST exist before any live send.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: SAFE-06
**Success Criteria** (what must be TRUE):
  1. Every candidate reply passes through one routing gate that decides escalate-vs-answer and shadow-vs-live via deterministic hash(ticket id) bucketing, so a retried ticket never flips mode
  2. A live quality dashboard shows reply performance, escalation rate, grounding-confidence distribution, reopen rate, and guardrail-trigger counts with alert thresholds
  3. A kill-switch can immediately halt all auto-sending and fall back to draft-only, verified working before any live percentage is enabled
**Plans**: TBD
**UI hint**: yes

### Phase 7: Staged Rollout (5% → 100%)
**Goal**: Expose the system to real volume incrementally and safely — flip one config value to send AI replies to a configurable percentage of traffic, holding and monitoring at each step, scaling toward 100% only while quality holds.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: SAFE-05
**Success Criteria** (what must be TRUE):
  1. A configurable rollout control sends AI replies to a defined percentage of volume (starting at ~5%) using deterministic, stable bucketing
  2. The percentage can be increased gradually toward 100%, with each increase gated on the eval bar holding and dashboard quality remaining healthy
  3. High-risk escalation rules stay permanent through scaling (coverage is quality-gated, not maximized), and the kill-switch remains the immediate fallback at every step
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Knowledge Survey & Conflict Inventory | 4/4 | Complete | 2026-05-29 |
| 2. Freshdesk I/O Layer & Pipeline Backbone | 6/6 | Complete   | 2026-06-01 |
| 3. Grounding Layer (Selless MCP + Knowledge RAG MCP) | 5/5 | Complete   | 2026-06-02 |
| 4. Reply Pipeline + Safety Guards | 7/7 | Complete   | 2026-06-05 |
| 5. Offline Evaluation Harness (THE GATE) | 0/TBD | Blocked on Phase 4 reopen | - |
| 6. Routing Gate, Monitoring & Kill-Switch | 0/TBD | Not started | - |
| 7. Staged Rollout (5% → 100%) | 0/TBD | Not started | - |
| 8. Ticket Re-Classification & FD Property Write-Back | 0/2 | Planned | - |

### Phase 8: Ticket Re-Classification & FD Property Write-Back

> **Scope note:** Re-classification is already in Phase-1 scope (REP-01). This phase extends it from
> "pick the support category for template selection" to "define the full set of CORE Freshdesk
> classification properties and prepare them for write-back into the ticket". Write-back is a NEW
> Freshdesk write path beyond the `submit_reply` chokepoint — it is **DRY_RUN-gated** in the PoC
> (classify + map + log a would-be update); the live `PUT /tickets/{id}` is DEFERRED. ⚠️ revisit
> before enabling any live property write at 23k/week.

**Goal**: Beyond drafting the customer reply, the Agent Team RE-CLASSIFIES each ticket and DEFINES the
core Freshdesk classification properties — **Level_in, Customer_Request (nested), Rootcause, Flow,
Section_Flow** — by mapping the AI's understanding (ticket body + Selless order data + Workflow/CODE-MAP)
to the EXACT `ticket_fields` dropdown enum values, and emits a **DRY_RUN "would-be FD property update"**
(classify → map → validate against enum → log to xlsx/jsonl). Produces and validates the mapping + the
classified property set; the live FD write is deferred.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: REP-06
**Scope boundary**: AI owns ONLY the core classification dropdowns above. Agent-workflow fields
(Handler, SCE team, Call type, Request to SCE, Level_out, Package_status, Product_label/line, …) stay
manual / out of scope for this phase.
**Success Criteria** (what must be TRUE):
  1. A static enum loader in the file-store exposes the FD `ticket_fields` choices (the nested
     Level_in→Customer_Request taxonomy + Rootcause/Flow/Section_Flow), read from the committed snapshot
     `freshdesk-ticket-fields.json` — no network at runtime.
  2. The pipeline emits an `fd_property_update` block with a verbatim enum value per owned field,
     grounded in ticket + Selless + CODE-MAP.
  3. Every emitted value is validated against the allowed enum; an invalid/out-of-enum value is flagged
     (never silently accepted) — same discipline as the allowed-template-codes anti-pattern guard.
  4. The validation harness shows AI-defined properties vs CS gold FD `custom_fields` side-by-side with a
     per-field match metric.
  5. DRY_RUN only — no live `PUT /tickets/{id}` path; assert no Freshdesk write occurs beyond the
     existing `submit_reply` chokepoint.

**Plans**: 2 plans (2 waves; offline foundation → harness wiring)
- [ ] 08-01-PLAN.md — Static ticket_fields enum loader (src/file_store/ticket_fields_store.py) + enum-validation/fd_property_update assembler (src/file_store/fd_classification.py); offline TDD; mirrors allowed-template-codes guard; empty-enum → unverifiable (Wave 1)
- [ ] 08-02-PLAN.md — Wire fd_property_update into the harness: assemble in _process_row + render AI-vs-CS-gold side-by-side with per-field match + *_valid in build_xlsx; assert DRY_RUN (no PUT); gitignore test-tickets.xlsx (Wave 2)
