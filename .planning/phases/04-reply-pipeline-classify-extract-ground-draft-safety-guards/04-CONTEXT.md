# Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Assemble the **per-ticket orchestrator** that turns an inbound Freshdesk ticket into a
safe, grounded candidate reply (or an escalation verdict). It re-classifies the ticket,
extracts the answer-key, drafts a citation-grounded reply via the two Phase-3 MCPs,
self-critiques against a quality rubric, and is wrapped by escalation rules + output
guards so its output is safe to evaluate in Phase 5.

This is the **first place LLM calls enter the codebase**.

Maps to requirements **REP-01, REP-02, REP-03, REP-04, SAFE-03, SAFE-04**.

**In scope:**
- A standalone, callable orchestrator module (classify → extract → ground → draft → self-critique)
- Re-classification into a support category with a confidence signal (REP-01)
- Extraction of order ref / customer / issue type as a structured (Pydantic) model (REP-02)
- Citation-grounded drafting over Selless + Knowledge MCP data, no ungrounded claims (REP-03)
- A self-critique pass scoring the draft against the quality rubric before any send (REP-04)
- High-risk escalation routing — any high-risk signal escalates the whole ticket (SAFE-03)
- Output guard blocking commitment-language + prompt-injection screening on email body (SAFE-04)
- Wiring the orchestrator into the Phase-2 worker DRY_RUN seam (`worker.py` `canned_body`)
- Langfuse tracing + Anthropic prompt caching for the new LLM calls

**Out of scope (defer):**
- The numeric go-live quality bar + golden-dataset replay/scoring — **Phase 5** (the eval harness consumes this orchestrator)
- The single routing gate (deterministic hash-bucket shadow/live), live dashboard, kill-switch — **Phase 6**
- Live sending / staged 5%→100% rollout — **Phase 7** (Phase 4 runs DRY_RUN only)
- Per-category confidence thresholds (THRS-01), agent-edit feedback loop (FEED-01), live shadow mode (SHAD-01) — **v2**
- Operational actions (refund/replace/order changes) — out of the Phase-1 milestone entirely
- Authoring/resolving the 18 KB conflicts — CS-team responsibility (Phase 4 only *reacts* to the conflict flag)

</domain>

<decisions>
## Implementation Decisions

### Pipeline Shape & Deliverable
- **D-01: Deterministic staged pipeline, not an agentic tool-loop.** The orchestrator is a
  fixed sequential flow — classify → extract → retrieve(MCP) → draft → self-critique — where
  each stage is its own PydanticAI agent with a structured (Pydantic) output. Chosen for
  controllability (guards/escalation insertable between stages), traceability, and deterministic
  replay in the Phase-5 eval. Matches CLAUDE.md's rationale for picking PydanticAI over LangGraph
  ("mostly-linear pipeline"). Agentic self-directed tool-loop rejected as too hard to control/eval
  for a safety-critical path.
- **D-02: Deliverable = a standalone callable orchestrator module AND wired into the worker DRY_RUN seam.**
  Build the pipeline as a pure callable module that **both** the Phase-2 worker (`process_queue_row`,
  replacing the `canned_body` placeholder at `src/work_queue/worker.py:201-207`) **and** the Phase-5
  eval harness invoke through **one production code path** (roadmap: "replay through the same
  production pipeline code"). Also wire it into the worker to prove the end-to-end flow through
  `dry_run_log`. Inlining logic directly into the worker (no shared module) was rejected — it would
  prevent the eval harness from reusing the exact production path.
- **D-03: Model assignment per stage (within the CLAUDE.md-locked stack).**
  - Classify / risk-pass / extract → **Haiku 4.5** (high-frequency, cheap hot path).
  - Draft → **Sonnet 4.6**.
  - Self-critique → a **separate Sonnet 4.6 critic agent** (independent from the drafter; more
    objective than self-reflection, still cheap). **Opus 4.7 is NOT used on the per-email hot path**
    — reserved for the Phase-5 eval judge and hard escalated cases only (CLAUDE.md "What NOT to Use").
- **D-04: Wire Langfuse tracing + Anthropic prompt caching now.** Phase 4 introduces the first LLM
  calls, which is exactly the point CLAUDE.md defers observability to. Enable Langfuse via OpenTelemetry
  on every LLM call, and prompt-cache the system prompt + retrieved policy blocks (the largest cost
  lever at this volume). Langfuse becomes the single sink for traces now and Phase-5 eval scores later.

### Classify + Extract (REP-01 / REP-02)
- **D-05: Two-level taxonomy.** The classifier emits a **high-level support category** —
  order/tracking · returns/refunds/exchanges · quality-complaint · policy/product (+ a high-risk
  marker) — which drives routing/escalation. A **separate grounding step** maps to the Phase-1
  **CODE-MAP workflow code** (via Knowledge MCP `lookup_code` / `get_template`) to pick a reply
  template. Routing is kept decoupled from template selection. Classifying directly into raw
  CODE-MAP codes was rejected (too many classes, error-prone, routing must be derived backward).
- **D-06: Confidence = bucketed high/med/low with a single conservative global threshold; low → escalate.**
  Any **low** bucket (or ambiguity between two categories) routes the whole ticket to a human.
  Per-category numeric thresholds are explicitly deferred to v2 (THRS-01). A continuous 0–1
  self-reported score was rejected as less reliable than coarse buckets at v1.
- **D-07: Extraction → a structured Pydantic model; missing lookup key → escalate.** Extract
  `order_code`, `customer_email`, `issue_type`, product references, etc. into a schema-enforced
  model, and use Selless **`resolve_order`** to turn a human order code (e.g. `25044-67`) into the
  internal order `id`. If the question requires order/customer data but no order or customer key can
  be resolved → **escalate** (never guess / never fabricate context). Drafting a generic policy-only
  reply when keys are missing was rejected as context-thin and risk-prone.

### Escalation & Risk Posture (SAFE-03)
- **D-08: High-risk detection = defense-in-depth, any-signal-escalates.** Combine (1) **deterministic
  rules/keywords** for money/refund + legal/complaint terms (business logic, not toxicity filtering),
  (2) a conservative **Haiku risk-classifier pass**, and (3) the **category marker** from D-05. ANY
  positive signal escalates the entire ticket. Matches CLAUDE.md ("explicit guardrail rails + a Haiku
  classifier with conservative thresholds → human"; "no LLM moderation-only as the high-risk gate").
- **D-09: Grounding signals feed escalation.** The Knowledge MCP **conflict flag (D-13 of Phase 3)**
  **forces escalation** — that is precisely what D-13 was designed for; the pipeline never self-arbitrates
  conflicting policy. If the **only** evidence supporting a needed claim is **stale-flagged content
  (D-15)**, also escalate rather than draft on outdated policy. (Where the Phase-3 `policy_resolution`
  override table (D-14) has an authoritative ruling, that ruling wins and no conflict escalation fires.)
- **D-10: "Escalate" = early-exit verdict, NO customer draft (in DRY_RUN).** On any escalation signal
  the pipeline exits early and returns a structured verdict `{action: escalate, reason, risk_signals}`;
  it does **not** spend tokens drafting a customer reply. This is the signal Phase 5 measures for
  "100% high-risk escalation" and avoids agents copy-pasting an un-vetted draft. Drafting an
  agent-suggestion on escalate was rejected for v1 (token cost + un-vetted-send risk).

### Grounding, Self-Critique & Output Guards (REP-03 / REP-04 / SAFE-04)
- **D-11: No-ungrounded-claims enforced via inline citations + a critique attribution check.** The
  drafter must attach **inline citations** pointing back to the retrieved Knowledge passages / Selless
  fields it used; the self-critique's **faithfulness dimension** verifies every factual claim is
  attributable to a source. An unsupported claim fails critique. A separate per-claim attribution
  verifier was considered but deferred (extra hot-path LLM pass); pure prompt-only grounding was
  rejected as unprovable for Phase 5.
- **D-12: Self-critique rubric = faithfulness + policy-match + tone/completeness; fail → redraft once → escalate.**
  The Sonnet critic scores three dimensions: faithfulness/grounding, policy alignment, and
  tone/completeness. On fail, the critique feedback is fed back for **one** redraft; if it still fails,
  **escalate**. (Keep rubric dimensions synchronized with the Phase-5 eval rubric.) Straight
  escalate-on-fail (no redraft) was the conservative alternative; redraft-once was chosen to recover
  recoverable drafts while preserving the safety ceiling.
- **D-13: Output guard = deterministic rules; trigger → block send + escalate.** A deterministic
  guard (regex/validators, optionally hosted in Guardrails AI) blocks commitment-language about
  refunds/credits/charges/order-changes **regardless of category**. On a hit it **blocks the send and
  escalates** — it never auto-strips the offending text and sends anyway. Commitment language is
  business-critical, so the hard gate must be deterministic, not probabilistic. (An optional LLM
  layer on top is a future enhancement, not the gate.)
- **D-14: Prompt-injection handling = delimit body as data + deterministic screen → suspicion escalates.**
  The customer email body is always wrapped in a clearly-delimited untrusted block (e.g. XML-tagged)
  in every prompt so it is treated as data, not instructions; plus a deterministic screening step
  detects injection patterns ("ignore previous instructions", etc.) and **escalates on suspicion**.
  promptfoo red-team patterns (per CLAUDE.md) can seed the pattern set. Delimiting-only (relying on
  the model) was rejected — no active detection.

### Claude's Discretion
- Exact prompt templates, system-prompt wording, and the prompt-cache breakpoints (which blocks to cache).
- MCP-call orchestration details within a stage: retrieval `top_k`, when to call which MCP tool, retrieval
  budget per ticket, and how citations are threaded from MCP results into the draft.
- The concrete commitment-language rule set / regexes and the injection-pattern set (seed from promptfoo;
  keep deterministic and conservative).
- `src/` module layout for the new orchestrator package and per-stage agents; the structured verdict /
  draft result schema shape (must be consumable by both the worker and the Phase-5 harness).
- Whether to add a guardrails framework (NeMo Guardrails vs Guardrails AI) or implement the rails as
  plain validators — pick the lightest option that satisfies D-13/D-14; Presidio (already wired) stays
  the PII sidecar.
- Reuse of the httpx+tenacity / retry patterns and `Settings` config singleton for any new LLM-client config.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before planning or implementing.**

### Project-Level (locked)
- `.planning/PROJECT.md` — "answers customers only" boundary, two-MCP architecture, "nothing ships
  until it clears the eval bar", high-risk-always-escalate constraint, model-cost discipline
- `.planning/REQUIREMENTS.md` — **REP-01, REP-02, REP-03, REP-04, SAFE-03, SAFE-04** map to this phase
- `.planning/ROADMAP.md` §"Phase 4" — goal + the 4 success criteria this phase must make TRUE; depends on Phase 3
- `CLAUDE.md` — locked model stack (**Haiku 4.5** classify/route, **Sonnet 4.6** draft, **Opus 4.7**
  judge/hard-case ONLY — never per-email hot path), **PydanticAI** orchestration, **Anthropic SDK**
  prompt caching, **Langfuse** via OpenTelemetry, **NeMo Guardrails / Guardrails AI** for safety/escalation
  rails, **Presidio** PII sidecar, **promptfoo** red-team; "What NOT to Use" (no Opus hot path, no
  moderation-only high-risk gate, no logging raw ticket text, no reading raw Confluence/Sheets per reply)

### Phase 3 grounding surfaces (the tools this orchestrator consumes)
- `.planning/phases/03-grounding-layer-selless-mcp-knowledge-rag-mcp/03-CONTEXT.md` — the two MCPs'
  decisions; **D-13 conflict flag** (forces escalation here), **D-14 override table**, **D-15 stale flag**,
  **D-12 authority hierarchy**, **D-10 structured-exact vs semantic split**, **D-11 template library**
- `.planning/phases/03-grounding-layer-selless-mcp-knowledge-rag-mcp/03-SELLESS-API.md` — confirmed
  Selless surface + the **D-04 field whitelist/deny-list** the drafter's grounding must respect
- `src/knowledge_mcp/server.py` — Knowledge MCP tools: `semantic_search`, `lookup_threshold`,
  `lookup_code`, `get_template` (citation/conflict/stale metadata shapes)
- `src/selless_mcp/server.py` — Selless MCP tools: `get_order_status`, `get_customer_info`,
  `get_purchase_history`, `get_ticket_history`, `resolve_order`

### Phase 1 KB artifacts (taxonomy + template inputs)
- `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` + `CODE-MAP-templates.md` —
  workflow code → action → email template (D-05 two-level mapping)
- `.planning/phases/01-knowledge-survey-conflict-inventory/CONFLICT-INVENTORY.md` — the 18 conflicts
  behind the D-09 conflict-escalation behavior
- `.planning/phases/01-knowledge-survey-conflict-inventory/GLOSSARY.md` — internal jargon for normalization

### Phase 2 foundation (build on, don't duplicate)
- `src/work_queue/worker.py` §`process_queue_row` (lines ~201-207) — the **DRY_RUN seam** (`canned_body`)
  the orchestrator replaces (D-02)
- `src/work_queue/send.py` — mode-aware send + `dry_run_log` persistence (redaction boundary)
- `src/guards/pii.py` — Presidio redaction to reuse before any log/trace write
- `src/config.py` — pydantic-settings singleton; add LLM/model/Langfuse config here (secrets out of `__repr__`)
- `src/freshdesk_io/` (`client.py`, `rate_limit.py`, `errors.py`) — httpx+tenacity retry/error-taxonomy pattern

### External (to confirm during research)
- PydanticAI docs — multi-agent staged pipeline, structured output, MCP-client wiring, model-per-agent
- Anthropic SDK docs — prompt caching breakpoints + tool use over MCP
- Guardrails AI / NeMo Guardrails docs — deterministic output validators (commitment-language, injection)
- Langfuse + OpenTelemetry — instrumenting Anthropic/PydanticAI calls

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Worker DRY_RUN seam** (`src/work_queue/worker.py:201-207`): the `canned_body` placeholder is the
  documented Phase-4 integration point; replace with the orchestrator call (D-02).
- **Both MCP servers** (`src/knowledge_mcp/`, `src/selless_mcp/`): the grounding tools are already
  built, cited, conflict/stale-aware, scoped, and audited — the orchestrator consumes them via MCP.
- **Presidio redaction** (`src/guards/pii.py`): reuse before any Langfuse/log write to keep raw ticket
  PII out of observability (CLAUDE.md rule).
- **pydantic-settings config** (`src/config.py`): extend with Anthropic/model + Langfuse config.
- **httpx + tenacity pattern** (`src/freshdesk_io/`): mirror for any new outbound HTTP/LLM client retry.

### Established Patterns
- Python/uv, `src/<module>/` package layout, Alembic-migration-per-change, structured logs + metrics.
- Secrets never logged (`Settings.__repr__` redaction) — extend to the Anthropic API key.
- DRY_RUN-by-default send mode (D-05 of Phase 2): the orchestrator's output flows to `dry_run_log`, never live.

### Integration Points
- **Upstream:** the Phase-2 queue/worker hands a claimed ticket to the orchestrator (replacing `canned_body`).
- **Grounding:** the orchestrator is an MCP client of both Phase-3 servers; the **conflict flag** is the
  hook (D-09) and the **field whitelist** bounds what the drafter may state.
- **Downstream (Phase 5):** the eval harness invokes the **same orchestrator module** on the golden set
  (never posting to Freshdesk) — keep the entry point pure and side-effect-free except for tracing.
- **Downstream (Phase 6):** the escalate-vs-answer **verdict** (D-10) and guard outcomes are what the
  routing gate will consume; keep the verdict schema explicit and stable.

</code_context>

<specifics>
## Specific Ideas

- "First LLM calls in the codebase" — this phase is where the model stack, prompt caching, and tracing
  go live; treat cost discipline (Haiku/Sonnet split, no Opus on hot path, prompt caching) as a hard rule.
- Escalation is deliberately **fail-closed and additive**: classifier category OR deterministic rule OR
  Haiku risk-pass OR conflict-flag OR stale-only-grounding OR missing-key OR guard-hit OR critique-fail
  — any one routes to a human. The phase optimizes for *not sending a bad reply*, not for coverage.
- Commitment-language and prompt-injection gates are intentionally **deterministic** (not LLM-only) —
  business-critical decisions must not be probabilistic.
- The same self-critique rubric dimensions (faithfulness / policy-match / tone) should align with the
  Phase-5 offline eval rubric so the runtime gate and the offline gate measure the same thing.

</specifics>

<deferred>
## Deferred Ideas

- **Per-claim attribution verifier** — a dedicated pass splitting the draft into claims and checking each
  against sources (heavier than D-11's critique-embedded check). Revisit if Phase-5 faithfulness scores
  show the embedded check is insufficient.
- **Agent-suggestion drafts on escalation** — drafting a starting-point reply for the human agent on
  escalated tickets (D-10 rejected this for v1 on cost + un-vetted-send risk). Could pair with live
  shadow mode (SHAD-01, v2).
- **LLM layer on top of the deterministic output guard** — a classifier catching subtly-phrased
  commitments beyond the regex set (D-13 keeps the hard gate deterministic for now).
- **Per-category confidence thresholds (THRS-01)** — v2; Phase 4 uses one conservative global low→escalate.
- **Multi-issue / multi-language ticket decomposition** — splitting compound tickets; for now a
  complex/ambiguous ticket is simply escalated (D-08). Non-English is out of scope (US/English only).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 4-reply-pipeline-classify-extract-ground-draft-safety-guards*
*Context gathered: 2026-06-02*
