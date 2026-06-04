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
- [x] **Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards** - End-to-end grounded draft with classification, self-critique, escalation rules, and output guards (first pass completed 2026-06-03; **REOPENED 2026-06-03** — commitment guard must become template/threshold-aware; success criterion #4 revised) (completed 2026-06-04)
- [ ] **Phase 5: Offline Evaluation Harness (THE GATE)** - Score replies against a golden dataset on faithfulness/correctness; the bar that authorizes go-live
- [ ] **Phase 6: Routing Gate, Monitoring & Kill-Switch** - Single chokepoint with deterministic bucketing + live dashboard and kill-switch in place before any live send
- [ ] **Phase 7: Staged Rollout (5% → 100%)** - Controlled, quality-gated exposure scaling from 5% to full volume

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
**Plans**: 12 plans (10 waves; baseline 04-00..04-05 executed/verified in waves 1-6; REOPEN 2026-06-03 adds 04-06..04-11 in waves 7-10 for the D-26/D-27 authorized-offer guard rework — template/threshold/eligibility-aware; RE-PLANNED for the Claude Code agent-team architecture — docs/specs/2026-06-02-cs-agent-team-design.md; superseded PydanticAI plans archived in _superseded/; vertical MVP slices over a Wave-0 bootstrap; deterministic safety hooks built before the agent team that composes them)
- [x] 04-00-PLAN.md — Wave 0 bootstrap: extend src/config.py (Haiku/Sonnet classify/draft/lead models + DRY_RUN, secret-redacted, env-driven for Bedrock) + src/reply_mcp submit_reply chokepoint + .claude/settings.json (register 3 MCPs + bind ALL 5 hooks per design §4a) + .claude/CLAUDE.md team-safety contract + root CLAUDE.md orchestration row + fixtures + RED stubs + settings-hook-binding structural test (Wave 1)
- [x] 04-01-PLAN.md — Five deterministic hooks (no LLM, mirror loop_guard (bool,reason)): injection_screen + pre_send_guard commitment block (SAFE-04/D-13/D-14) + escalation_gate any-signal-escalates (SAFE-03/D-08/D-09) + grounding_check (REP-03/D-11) + pii_redact (D-04); fail-closed (Wave 2)
- [x] 04-02-PLAN.md — Agent team: cs-lead (entry) + classifier/extractor (Haiku, REP-01/02) + drafter/critic (Sonnet, REP-03/04, drafter emits via submit_reply only) + 5 skills incl. reply-pipeline workflow (D-01/D-10/D-12); no Opus; body delimited as untrusted (Wave 3)
- [x] 04-03-PLAN.md — Local PoC runner (DRY_RUN, via claude CLI + settings.json hooks) + INTEGRATED mock-LLM e2e proving high-risk/injection/un-cited drafts reach submit_reply and are blocked→escalate through the real bound chain + settings-hook-binding structural assertion (design §7/§4a) + blocking human-verify (package legitimacy + auth/env) (Wave 4)
- [x] 04-04-PLAN.md — Gap closure (CR-01/CR-03/CR-04-hook/CR-05): fix PreToolUse exit codes 1→2 in pre_send_guard + grounding_check so they actually BLOCK submit_reply; close grounding_check empty-citation bypass (≥1 citation per D-11); injection_screen._extract_body fail-closed on missing body; pii_redact error path stops corrupting payload + documents D-04 PostToolUse limitation (Wave 5)
- [x] 04-05-PLAN.md — Gap closure (CR-02/CR-04-deploy/test-gap): stateful final-risk veto via per-run CS_RUN_ID state file (PostToolUse/SubagentStop write, PreToolUse@submit_reply read, fail-closed) restoring SAFE-03; mandatory non-bypassable runner injection pre-screen on the real path + subagent binding restoring SAFE-04; subprocess test suite asserting deployed exit-code contract (returncode==2/0) for every PreToolUse hook (Wave 6)
- [x] 04-06-PLAN.md — REOPEN: deterministic authorized_offer module (.claude/hooks/authorized_offer.py) — §0 authorized/unauthorized test + per-sub-type template registry + THR-05/06/07/08 caps + RD-Q2 eligibility STUB; exhaustive RULES §2 unit tests (SAFE-04, Wave 7)
- [x] 04-07-PLAN.md — REOPEN: classifier emits level-2 customer_request sub-type (13-value RULES §2 enum), Haiku preserved, additive verdict schema; classify-ticket skill + contract test (REP-01, Wave 7)
- [x] 04-08-PLAN.md — REOPEN: escalation_gate.py + operational_action trigger (Review/Full_Refund/asserting-change_request per RD-Q1) keeping all existing triggers; subprocess exit-2 proofs (SAFE-03/REP-01, Wave 8)
- [x] 04-09-PLAN.md — REOPEN (load-bearing): pre_send_guard.py replaces block-all with the D-26 authorized-offer test via authorize_offer; exit-0 for in-policy templated offers / exit-2 for every unauthorized axis; never auto-strip, fail-closed; subprocess contract suite (SAFE-04, Wave 8)
- [x] 04-10-PLAN.md — REOPEN: drafter template-select by sub-type + eligibility grounding (RD-Q2 stub) + structured offer block to submit_reply + RD-Q1 never-assert-operational-action; ground-and-draft skill + contract test (REP-03/SAFE-04, Wave 9)
- [x] 04-11-PLAN.md — REOPEN (DEFERRED, autonomous:false): wire REAL Selless eligibility (warranty THR-03/04 window, prior-remediation, variant stock) + RD-Q3 evidence validation at the STUB swap points; fail-closed degradation when a real field is absent (SAFE-04, Wave 10)
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
| 4. Reply Pipeline + Safety Guards | 12/12 | Complete   | 2026-06-04 |
| 5. Offline Evaluation Harness (THE GATE) | 0/TBD | Blocked on Phase 4 reopen | - |
| 6. Routing Gate, Monitoring & Kill-Switch | 0/TBD | Not started | - |
| 7. Staged Rollout (5% → 100%) | 0/TBD | Not started | - |
