# Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards - Context

**Gathered:** 2026-06-02 · **Re-homed:** 2026-06-03 (architecture pivot — see below)
**Status:** Ready for planning
**Canonical design:** `docs/specs/2026-06-02-cs-agent-team-design.md` (APPROVED — planner MUST read)

> **ARCHITECTURE PIVOT (2026-06-03).** Phase 4 is now built as a **standard Claude Code agent team**
> (`.claude/` with `agents/`, `skills/`, `hooks/`, `CLAUDE.md`, MCP wiring) running **locally first**
> (PoC via the developer's Claude subscription / `claude` CLI), later packaged as a **Layer-4 plugin**
> for the `samx` managed-agents platform (production inference on AWS Bedrock). This **replaces** the
> earlier PydanticAI staged-pipeline approach. The 14 locked decisions D-01..D-14 are **preserved but
> re-homed** onto the agent team (see the mapping in §Decisions). The superseded plans are archived in
> `_superseded/`.

<domain>
## Phase Boundary

Build the **customer-support reply agent team** (`cs-agent-team`) that turns an inbound Freshdesk
ticket into a safe, grounded candidate reply **or** an escalation verdict. A **team lead** (`cs-lead`)
orchestrates a fixed procedure — classify → extract → ground → draft → self-critique — delegating to
member subagents and calling the two Phase-3 MCPs, wrapped by **deterministic hooks** (escalation,
commitment-block, injection-screen, grounding-check, PII-redact) that the lead/subagents cannot bypass.

This is the **first place LLM calls enter the product**. Maps to **REP-01, REP-02, REP-03, REP-04,
SAFE-03, SAFE-04**.

**In scope (local PoC):**
- A `.claude/` agent team: team lead + classifier/extractor/drafter/critic subagents (REP-01/02/03/04)
- The reply **workflow** as a skill (`reply-pipeline`) + template-fill skill (`ground-and-draft`)
- **Deterministic hooks** enforcing the safety-critical guards (SAFE-03/04, escalation, PII)
- Wiring the **Phase-3 Selless + Knowledge MCP servers** as the team's grounding tools
- A local runner that executes the team on a **sample ticket** in **DRY_RUN** → grounded draft OR
  escalate verdict, with guards demonstrably enforced
- Per-stage model assignment (Haiku classify/extract, Sonnet draft/critic; NO Opus) + prompt caching;
  env-driven provider so the same kit later runs on AWS Bedrock

**Out of scope (defer):**
- Live Freshdesk webhook/queue intake + posting — reuse Phase-2 later as an integration bridge
- Packaging into the `samx` platform plugin (`team.yaml` / `pipeline.yaml` DSL) — later
- AWS Bedrock cut-over — design supports it; not exercised in the local PoC
- Phase-5 offline eval harness (will replay golden tickets through this same team in dummy-mode)
- Operational actions (refund/replace/order changes); authoring/resolving KB conflicts (CS-team)

</domain>

<decisions>
## Implementation Decisions — D-01..D-14 re-homed onto the agent team

> Full rationale lives in the locked decisions; here is how each maps onto the Claude Code agent team.

- **D-01 (deterministic staged flow, not an agentic loop)** → the **team lead follows a fixed procedure**
  encoded in `skills/reply-pipeline/SKILL.md`; **hooks enforce stage order + early-exit**. The lead is
  constrained, not free-roaming.
- **D-02 (one shared production code path)** → the **`.claude/` team-kit IS the single path**; the local
  runner and (later) the Phase-2 worker + Phase-5 eval all invoke the same team. (Worker wiring deferred.)
- **D-03 (model per stage, no Opus hot path)** → set per agent in `settings.json`: classifier/extractor →
  **Haiku 4.5**, drafter/critic → **Sonnet 4.6**. No Opus.
- **D-04 (Langfuse + prompt caching)** → prompt-cache system prompt + retrieved policy/template blocks;
  tracing wired with PII redaction first. (Langfuse sink optional in local PoC; redaction is mandatory.)
- **D-05 (two-level taxonomy)** → `classifier` emits the support category + high-risk marker; a separate
  grounding step maps to the CODE-MAP via Knowledge MCP `lookup_code`/`get_template`.
- **D-06 (bucketed confidence, low→escalate)** → classifier returns high/med/low; `escalation_gate.py`
  escalates on low/ambiguous.
- **D-07 (structured extraction + resolve_order; missing key→escalate)** → `extractor` produces the
  answer-key and calls Selless `resolve_order`; missing key → escalate (no fabrication).
- **D-08 (defense-in-depth, any-signal-escalates)** → deterministic keyword rules + risk marker +
  category, OR-combined in `escalation_gate.py`.
- **D-09 (grounding signals feed escalation)** → Knowledge MCP **conflict flag** forces escalate;
  **stale-only** grounding forces escalate; override-resolved rulings win (no false escalation).
- **D-10 (escalate = early-exit, NO draft)** → the lead emits `{action: escalate, reason, risk_signals}`
  and does not draft.
- **D-11 (no ungrounded claims; inline citations + critique attribution)** → `drafter` attaches inline
  citations to Knowledge passages / whitelisted Selless fields; `grounding_check.py` + critic faithfulness
  dimension enforce attribution.
- **D-12 (self-critique rubric; fail→redraft once→escalate)** → `critic` (Sonnet) scores
  faithfulness/policy-match/tone-completeness; one redraft, then escalate. Keep dimensions aligned with
  the Phase-5 eval rubric.
- **D-13 (deterministic commitment-language guard; trigger→block+escalate)** → `pre_send_guard.py`
  blocks refund/credit/charge/order-change commitments regardless of category; never auto-strips.
- **D-14 (injection handling: delimit body + deterministic screen→escalate)** → every prompt wraps the
  email body as untrusted data; `injection_screen.py` escalates on suspicion. Seed patterns from promptfoo.

### Claude's Discretion
- Exact agent prompts / skill wording / prompt-cache breakpoints.
- Whether `cs-lead` delegates to subagents via the Task/subagent mechanism or runs stages inline via
  skills — pick the simplest that keeps **hooks enforceable**.
- Hook transport: Claude Code `settings.json` hooks (shell→Python) vs Agent SDK programmatic hooks —
  choose based on the local runner.
- Concrete commitment-language regex set + injection-pattern set (deterministic, conservative).
- The verdict schema shape (must be consumable later by the worker + Phase-5 harness).
- Retrieval `top_k` / which MCP tool when / citation threading.

</decisions>

<reopen_decisions>
## REOPEN (2026-06-03) — Authorized-Offer Guard (D-26/D-27, supersedes block-all D-13)

> **Why reopened.** The original D-13/SAFE-04 made `pre_send_guard.py` block ALL refund/credit/replace/charge
> language → escalate. A live Freshdesk fetch (312 real tickets) proved the *correct* CS flow resolves the
> highest-volume categories (complaint / cancellation / shipping) with **policy-bounded templated offers**
> (ticket 7732073's real reply == template **B7** verbatim). Block-all would escalate that entire volume and
> fail every correct reply. **The 6 plans 04-00..04-05 stay executed/verified; this reopen ADDS new plans
> (04-06+)** that make the guard template + threshold + eligibility aware.
>
> **Authoritative rule set:** `04-AUTHORIZED-OFFER-RULES.md` (THIS phase dir) — the data-derived case
> taxonomy → template → authorized offer/threshold → draft-vs-escalate boundary. The planner MUST read it.
> **Companion decisions:** `../05-offline-evaluation-harness-the-gate/05-CONTEXT.md` D-25..D-28.

**D-26 (locked) — template/threshold/eligibility-aware guard (supersedes D-13).** A commitment in a draft is
AUTHORIZED (allow) iff ALL hold: (1) it matches an **approved template** for the classified flow (A1–A9,
B1–B13, C1, cancellation t1–9, change t1–5, shipping t1–5); (2) the offered value is **within the policy
threshold** (POLICY-THRESHOLD-INDEX: THR-05 40% discount+free-ship, THR-06 ≤20% retention, THR-07 50% refund,
THR-08 ≤50% late-ship comp); (3) the **order is eligible** (warranty THR-03/04 = 45d purchase / 14d delivery;
not already at a higher remediation tier — "offered 50%/replacement before?"), grounded via Selless; (4) it
follows the documented Flow + policy. Anything else (over-threshold / out-of-template / ineligible /
second-remediation / fabricated) → block → escalate. **Threshold authority:** AI MAY commit up to
THR-05/06/07/08 **without per-case human sign-off** when eligibility is grounded and policy is followed;
out-of-policy → human.

**D-27 (locked) — gate redefinition.** Phase-5 hard gate becomes **"0 UNAUTHORIZED commitments"** (offers
failing the D-26 test), NOT "0 refund/commitment words". Templated, in-threshold offers are CORRECT.

### Reopen scope — components to rework (per RULES §3), planned as NEW plans on top of 04-00..04-05
- **classifier** — emit the level-2 `Customer_Request` sub-type (Return / Replace / Partial_Refund /
  Full_Refund / Review / Cancel_Order / Change_Shipping_Address / Change_Product_Variant /
  Ask_About_Delivery_Status / Ask_About_Order / Ask_About_Policy / Ask_About_Product / Ask_About_Promotion),
  not just the macro category, so the rule table is addressable.
- **escalation_gate.py** — ADD an "operational-action" trigger (any `change_request` sub-type that would
  assert a mutation, Full_Refund evidence-gated, Review) → escalate. KEEP all existing triggers.
- **pre_send_guard.py** — REPLACE block-all-commitment with the D-26 authorized/unauthorized test; allow an
  offer only if template + threshold + grounded eligibility all pass; block otherwise. Still deterministic,
  fail-closed, exit-2-blocks-submit_reply; never auto-strip.
- **drafter** — select the correct template via Knowledge MCP `get_template` for the classified sub-type;
  ground eligibility via Selless before any offer; **never claim an operational action was executed.**

### Reopen clarifications resolved by user (2026-06-03) — LOCKED for planning
- **RD-Q1 — change_request execution boundary = model (a) draft-after-ops / escalate-on-assertion.**
  Honors the Phase-1 constraint "answers customers only — never executes operational actions". The AI MUST
  NOT claim an action it did not cause. A draft that asserts "we've canceled / updated / changed…" without
  the mutation having occurred is UNAUTHORIZED → **escalate**. Only non-asserting phrasing may be drafted:
  the ≤20% retention offer (THR-06) and acknowledgement / next-step language. NO AI-triggered Selless
  mutation in Phase 4.
- **RD-Q2 — eligibility surface = DEMO STUB now, real API later.** For the local PoC demo, treat the
  eligibility/product surface as available: assume a product-info MCP check exists and assume **variant
  stock is always in-stock**. Wire the real Selless eligibility fields (warranty dates, prior-remediation
  state, real variant stock, scoped product-info API) in a **later/deferred plan**. Plans MUST mark these
  as stubbed/assumed and keep the guard's structure so the real check drops in without reshaping it.
- **RD-Q3 — evidence = accept-as-sufficient now, validate later.** For Full_Refund / evidence-gated paths,
  treat submitted evidence as sufficient/eligible in this phase; build the real photo/shipping-label
  **validation in a deferred plan**. (Pairs with D-26: still escalate if the case is out-of-policy on other
  axes.)

> **Source-of-truth precedence for planning:** `04-AUTHORIZED-OFFER-RULES.md` (rule table) + these RD-Qx
> answers OVERRIDE the stale "block all … regardless of category" wording of D-13 above. ROADMAP success
> criterion #4 has already been revised to match (2026-06-03).

</reopen_decisions>

<canonical_refs>
## Canonical References — downstream agents MUST read

### This phase's design (READ FIRST)
- `docs/specs/2026-06-02-cs-agent-team-design.md` — the approved agent-team architecture, `.claude/`
  layout, safety model, provider plan, local PoC acceptance

### Project-level (locked)
- `.planning/PROJECT.md` — "answers customers only", two-MCP architecture, "nothing ships until eval bar",
  high-risk-always-escalate, model-cost discipline
- `.planning/REQUIREMENTS.md` — REP-01..04, SAFE-03, SAFE-04
- `.planning/ROADMAP.md` §"Phase 4" — goal + 4 success criteria; depends on Phase 3
- `CLAUDE.md` — locked model stack (Haiku/Sonnet, NO Opus hot path), Langfuse, Presidio, promptfoo,
  "What NOT to Use". **Note:** the CLAUDE.md tech-stack table mandates PydanticAI; the planner should
  flag that this phase substitutes the **Claude Agent SDK / Claude Code agent-team** runtime and propose
  a CLAUDE.md update (model-cost + grounding rules still apply unchanged).

### Phase 3 grounding surfaces (consumed as MCP tools)
- `src/knowledge_mcp/server.py` — `semantic_search`, `lookup_threshold`, `lookup_code`, `get_template`
  (citation/conflict/stale metadata)
- `src/selless_mcp/server.py` — `resolve_order`, `get_order_status`, `get_customer_info`,
  `get_purchase_history`, `get_ticket_history` (field whitelist, audit)
- `.planning/phases/03-grounding-layer-selless-mcp-knowledge-rag-mcp/03-CONTEXT.md` — D-13 conflict flag,
  D-14 override table, D-15 stale flag (the escalation hooks here)

### Phase 1 KB artifacts
- `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` + `CODE-MAP-templates.md`
- `.planning/phases/01-knowledge-survey-conflict-inventory/CONFLICT-INVENTORY.md`, `GLOSSARY.md`

### Phase 2 foundation (reuse; live wiring deferred)
- `src/guards/pii.py` — Presidio redaction reused by `hooks/pii_redact.py`
- `src/work_queue/worker.py`, `src/work_queue/send.py` — the DRY_RUN seam for later integration
- `src/config.py` — pydantic-settings singleton (add provider/model config; secrets redacted)

### External (verify at build)
- Claude Agent SDK / Claude Code: agents, skills, hooks (`settings.json`), MCP wiring, subagents
- Bedrock provider env (`CLAUDE_CODE_USE_BEDROCK`) + per-stage model-ID mapping
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **Both MCP servers** (`src/knowledge_mcp/`, `src/selless_mcp/`) — cited, conflict/stale-aware, scoped,
  audited; registered as the team's MCP tools.
- **Presidio redaction** (`src/guards/pii.py`) — reused by the PII hook before any log/trace.
- **pydantic-settings** (`src/config.py`) — extend with provider/model config (Anthropic ↔ Bedrock).
- **Loop/idempotency guards + Freshdesk client** (`src/work_queue/`, `src/freshdesk_io/`) — reused when
  the live integration bridge is built (deferred).

### Established patterns
- Python/uv, `src/<module>/` layout, secrets never logged, DRY_RUN-by-default.
- Deterministic guards return `(bool, reason)` (see `src/guards/loop_guard.py`) — mirror for the new hooks.

### Integration points
- **Grounding:** the team is an MCP client of both Phase-3 servers; the conflict flag is the escalation
  hook; the Selless field whitelist bounds what the drafter may state.
- **Downstream (Phase 5):** the eval harness replays the golden set through the **same team** in
  dummy/fixture mode (no Freshdesk post) — keep the entry point pure + the verdict schema stable.
- **Downstream (live, deferred):** the Phase-2 worker `canned_body` seam will call the team; the verdict
  + guard outcomes feed the Phase-6 routing gate.

</code_context>

<specifics>
## Specific Ideas
- "First LLM calls in the product" — model-cost discipline (Haiku/Sonnet split, no Opus, prompt caching)
  is a hard rule.
- Escalation is fail-closed and additive — any one signal routes to a human. Optimize for *not sending a
  bad reply*, not coverage.
- Commitment-language + injection gates are **deterministic hooks**, not LLM-only.
- Keep the self-critique rubric dimensions aligned with the Phase-5 offline eval rubric.
- Build **portable**: the `.claude/` kit should drop into the `samx` platform as a Layer-4 plugin with
  minimal change; keep team logic in `.claude/`, not in bespoke wrapper code.

</specifics>

<deferred>
## Deferred Ideas
- Live Freshdesk webhook/queue intake + posting (reuse Phase-2 as an integration bridge).
- `samx` platform plugin packaging (`team.yaml`/`pipeline.yaml`).
- AWS Bedrock cut-over (env-driven; not exercised locally).
- Per-claim attribution verifier; agent-suggestion drafts on escalate; LLM-on-guard; per-category
  thresholds (THRS-01); multi-issue/multi-language decomposition.

</deferred>

---

*Phase: 4-reply-pipeline-classify-extract-ground-draft-safety-guards*
*Context re-homed 2026-06-03 to the Claude Code agent-team architecture (design: docs/specs/2026-06-02-cs-agent-team-design.md)*
