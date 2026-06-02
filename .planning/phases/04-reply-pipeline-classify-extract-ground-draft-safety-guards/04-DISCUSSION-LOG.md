# Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 4-reply-pipeline-classify-extract-ground-draft-safety-guards
**Areas discussed:** Pipeline shape & deliverable, Classify + Extract (REP-01/02), Escalation & risk posture (SAFE-03), Grounding + Self-critique + Output guard (REP-03/04 + SAFE-04)

---

## Pipeline shape & deliverable

### Q1 — Orchestrator shape

| Option | Description | Selected |
|--------|-------------|----------|
| Staged cố định | Deterministic sequential pipeline, each stage a PydanticAI agent + structured output; easy to control/escalate/trace/eval | ✓ |
| Agentic tool-loop | One agent self-directs MCP calls until ready to draft; flexible but hard to control/guard/eval | |

**User's choice:** Staged cố định (recommended) → D-01

### Q2 — End-state / deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone orchestrator + wire into worker DRY_RUN | Pure callable module shared by worker AND Phase-5 harness (one production code path); also replace `canned_body` | ✓ |
| Only standalone orchestrator | Build module + standalone demo, leave worker seam untouched | |
| Wire directly into worker | Inline logic in `process_queue_row`; breaks eval-reuse-production-code | |

**User's choice:** Standalone orchestrator + wire into worker DRY_RUN (recommended) → D-02

### Q3 — Self-critique model (hot path ~3,200/day)

| Option | Description | Selected |
|--------|-------------|----------|
| Separate Sonnet critic | Independent Sonnet 4.6 critic; Opus reserved for Phase-5 judge + hard cases | ✓ |
| Drafter self-critiques (same Sonnet) | Cheapest; weaker independence | |
| Opus critic | Highest quality but violates "no Opus on per-email hot path" | |

**User's choice:** Separate Sonnet critic (recommended) → D-03

### Q4 — Observability + prompt caching

| Option | Description | Selected |
|--------|-------------|----------|
| Wire Langfuse + prompt caching now | Tracing via OTel + cache system/policy blocks from Phase 4; right per CLAUDE.md | ✓ |
| Only prompt caching, defer Langfuse | Cost savings now, traces later | |
| Defer both | Focus on logic; risk of retrofit | |

**User's choice:** Wire Langfuse + prompt caching now (recommended) → D-04

---

## Classify + Extract (REP-01/02)

### Q1 — Taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| Two-level: high-level category + CODE-MAP code | Category for routing/escalation; grounding step maps to CODE-MAP code for template | ✓ |
| Only 4 high-level categories | Simple; code-map mapping fully inside grounding/draft | |
| Raw CODE-MAP codes | Detailed but many classes, error-prone, routing derived backward | |

**User's choice:** Two-level (recommended) → D-05

### Q2 — Confidence representation + low-confidence action

| Option | Description | Selected |
|--------|-------------|----------|
| Bucket high/med/low + low→escalate | One conservative global threshold; matches v1 (THRS-01 deferred) | ✓ |
| 0–1 score + one threshold | Flexible but self-reported scores less reliable than buckets | |
| You decide | Defer representation to planner | |

**User's choice:** Bucket high/med/low + low→escalate (recommended) → D-06

### Q3 — Extraction + missing-key behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic model + resolve_order; missing key → escalate | Structured extraction; resolve_order for code→id; escalate if no order/customer key | ✓ |
| Pydantic model + resolve_order; missing key → general draft | Draft policy-only reply when keys missing; context-thin risk | |
| You decide the fields | Defer field list to planner | |

**User's choice:** Pydantic model + resolve_order; missing key → escalate (recommended) → D-07

---

## Escalation & risk posture (SAFE-03)

### Q1 — High-risk detection mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Combination: deterministic rules + Haiku risk-pass + category, any-signal→escalate | Defense-in-depth; matches CLAUDE.md "explicit rails + Haiku conservative", not moderation-only | ✓ |
| Only classifier category | Single source; misses high-risk when category mislabeled | |
| Only Haiku risk-classifier | No deterministic net for obvious money/legal terms | |

**User's choice:** Combination, any-signal→escalate (recommended) → D-08

### Q2 — Grounding signals → escalation

| Option | Description | Selected |
|--------|-------------|----------|
| Conflict→escalate (mandatory); stale-only→escalate | D-13 conflict forces handoff; stale-only evidence also escalates; D-14 ruling wins | ✓ |
| Conflict→escalate; stale→warn only, still draft | Less escalation but risk of replying on outdated policy | |
| You decide | Defer conflict/stale reading to planner | |

**User's choice:** Conflict→escalate mandatory; stale-only→escalate (recommended) → D-09

### Q3 — What "escalate" does in DRY_RUN

| Option | Description | Selected |
|--------|-------------|----------|
| Early-exit: verdict + reason, NO draft | Structured `{action: escalate, reason, risk_signals}`; saves tokens; Phase-5 measures this | ✓ |
| Draft "agent suggestion" + escalate flag | Starting point for agent; token cost + un-vetted-send risk | |

**User's choice:** Early-exit, no draft (recommended) → D-10

---

## Grounding + Self-critique + Output guard (REP-03/04 + SAFE-04)

### Q1 — Grounding enforcement (no ungrounded claims)

| Option | Description | Selected |
|--------|-------------|----------|
| Inline citations + critique attribution check | Drafter cites inline; critique faithfulness dimension verifies each claim has a source | ✓ |
| Separate per-claim attribution verifier | Strictest; extra hot-path LLM pass | |
| Prompt + general critique only | Lightest; hard to prove grounding for Phase 5 | |

**User's choice:** Inline citations + critique attribution check (recommended) → D-11

### Q2 — Self-critique rubric + fail action

| Option | Description | Selected |
|--------|-------------|----------|
| faithfulness+policy-match+tone; fail→redraft once→escalate | Recover recoverable drafts, then escalate | ✓ |
| Same rubric; fail→escalate straight | Simpler/more conservative; escalates more | |
| You decide rubric dimensions | Defer to planner/eval design | |

**User's choice:** faithfulness+policy-match+tone; fail→redraft once→escalate (recommended) → D-12

### Q3 — Output guard (commitment-language, SAFE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic rules, trigger→block+escalate | Regex/validators (optionally Guardrails AI); block send, never auto-strip; runs all categories | ✓ |
| Rules + LLM layer | Deterministic backstop + LLM classifier for subtle phrasing | |
| LLM classifier only | Flexible but probabilistic — unsuitable as money-commitment hard gate | |

**User's choice:** Deterministic rules, block+escalate (recommended) → D-13

### Q4 — Prompt-injection handling (SAFE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Delimit body as data + deterministic screen→suspicion escalates | XML-tagged untrusted block + heuristic injection screen; promptfoo red-team patterns seed it | ✓ |
| Delimit body only | Lightest; no active detection | |
| You decide | Defer screen mechanism to planner | |

**User's choice:** Delimit body + deterministic screen→escalate (recommended) → D-14

---

## Claude's Discretion

- Prompt templates / system-prompt wording / prompt-cache breakpoints
- MCP-call orchestration within a stage (retrieval `top_k`, which tool when, retrieval budget, citation threading)
- Concrete commitment-language regex set + injection-pattern set (seed from promptfoo)
- `src/` module layout for the orchestrator + per-stage agents; verdict/draft result schema shape
- Guardrails framework choice (NeMo vs Guardrails AI vs plain validators) — lightest that satisfies D-13/D-14
- Reuse of httpx+tenacity / Settings config patterns for new LLM-client config

## Deferred Ideas

- Per-claim attribution verifier (revisit if Phase-5 faithfulness insufficient)
- Agent-suggestion drafts on escalation (pairs with v2 shadow mode SHAD-01)
- LLM layer on top of the deterministic output guard
- Per-category confidence thresholds (THRS-01, v2)
- Multi-issue / multi-language ticket decomposition (complex tickets escalate for now; non-English out of scope)
