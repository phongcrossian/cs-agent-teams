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

---
---

# SESSION 2 — 2026-06-04 — PoC pivot D-29/D-30 code-rework discussion

**Date:** 2026-06-04
**Trigger:** Update existing CONTEXT.md to align Phase-4 CODE with the D-29/D-30 PoC pivot (commit 070509a, docs-only). New decisions D-31..D-34.
**Areas discussed:** Knowledge MCP fate, Retired hooks handling, Escalation semantics, Selless grounding fallback

## Knowledge MCP fate (D-31)

| Option | Description | Selected |
|--------|-------------|----------|
| Retire MCP → local file-store | Drafter reads 26 template snapshots + CODE-MAP from files | ✓ |
| Keep thin keyed get_template MCP | Server with exact-key get_template/lookup_code only | |
| MCP shell file-backed | Keep MCP interface, file-backed | |

**User's choice:** Retire MCP → local file-store. Fewest moving parts; matches prototyped file-based draft mode. Selless MCP stays.

## Retired hooks handling (D-32)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep but no-op/advisory | Neutralize (exit 0), keep files for easy revert | |
| Delete entirely | Remove 4 guard hooks + settings.json wiring | ✓ |
| Keep code, untoggle settings.json only | Leave code, remove from PreToolUse chain | |

**User's choice:** Delete entirely (`pre_send_guard`, `escalation_gate`, `grounding_check`, `authorized_offer`). Keep `injection_screen` (D-14) + `pii_redact` (D-04). Trade-off: before-live guard re-authored from scratch (deferred BLOCKER).

## Escalation semantics (D-33)

| Option | Description | Selected |
|--------|-------------|----------|
| Always draft + advisory hint | action always = draft; optional escalation_hint for triage | ✓ |
| Drop escalation entirely | Verdict only {action: draft, body} | |
| Keep escalate=no-draft for injection | Always-draft except injection | |

**User's choice:** Always draft + advisory hint. Mirrors advisory escalation reference in `.claude/CLAUDE.md`; hint never suppresses the draft.

## Selless grounding fallback (D-34)

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder token + flag ungrounded | Fill [TRACKING_LINK]/[ETA], mark grounded=false | (refined) |
| Draft generic, no figures | Drop all order-data sentences | |
| Skip grounding, draft full template | Treat data as valid (demo-stub) | |

**User's choice (free-text refinement):** "Không có thông tin thì phải xem có đúng Flow không, có thể khách chưa mua hàng." → **Flow-aware fallback.** Missing order = a SIGNAL; consult Workflow/CODE-MAP and draft a verify-order/clarify template instead of fabricating numbers. Placeholder tokens only for infra fields once the flow establishes the order is VALID but a detail is pending. Confirmed in a follow-up question.

## Claude's Discretion (session 2)

- `pyproject.toml` removals (`voyageai`, `pgvector` as RAG, Ragas) — mechanical.
- Verdict schema shape for the advisory hint field.
- File-store read mechanism / CODE-MAP keying for the drafter.
- Agent prompt / skill wording updates for always-draft.

## Deferred Ideas (session 2)

- ⚠️ BEFORE-LIVE BLOCKER: re-author an output guard before any non-DRY_RUN send (reference = struck-through D-26 spec).
- Real Selless eligibility wiring (was 04-11).

---

## Session 3 — Workflow-validation re-discussion (2026-06-04)

**Focus:** Why the template comes out wrong in `test-tickets.xlsx`; prove the always-draft workflow
runs correctly on real PROD tickets; iterate AI-vs-CS until template + reply are correct. User priority:
workflow-correctness first, keep it simple. Language: Vietnamese.

**Areas discussed & selections:**

1. **Execution path** — options: real `.claude/` agent-team / standalone `draft()` / hybrid.
   → **Real agent-team (.claude/)** (D-35). Standalone `draft()` deprecated for validation.
2. **Ground truth** — options: CS as reference (not absolute) / CS as absolute gold.
   → **CS as absolute gold standard** (D-36). Every divergence = AI error to fix.
3. **Properties scope** — options: minimal (sub-type+code+reply) / extended (+Flow/STEP/Rootcause/Resolution).
   → **Extended** (D-37). All written to xlsx beside CS, divergences noted.
4. **PROD safety** — options: read-only + DRY_RUN / allow sandbox post.
   → **Read-only FD + Selless, absolute DRY_RUN** (D-39). Never POST to Freshdesk.
5. **Stopping criterion** (follow-up, to resolve absolute-gold × extended × simple tension) —
   options: 100% on core + advisory subjective / 100% on ALL / 100% on template code + Reply only.
   → **100% on template code + Reply only** (D-38). Other props recorded + diff-noted, non-blocking.

**Also captured:** dedicated AI-vs-CS checker agent that explains why AI differs and feeds fixes back,
reasons always recorded in xlsx (D-40).

**Immediate finding:** `test-tickets.xlsx` "AI Team value" column empty on all 30 sheets (iter-4 paused
at 1/30) — must re-populate via the real-team path before comparison is meaningful.

### Claude's discretion (session 3)
- Checker agent count/shape + `.cs-compare` JSON schema.
- Verdict payload shape for reporting computed Properties back to the xlsx.
- Keep vs delete `draft()` once `collect()` is the validated path.

---

## Session 4 — `/test-ticket` command (2026-06-05)

**Focus:** Turn the working harness (`scripts/test_tickets_run.py`) into an on-demand command — run a
single ticket by ID or a list from CSV through the REAL agent-team → same `test-tickets.xlsx`.
Priority: làm đơn giản (repackage, don't rebuild). Language: Vietnamese.

**Data source confirmed:** "FB Product" = Freshdesk (Customer First Request + first CS reply) + Selless
PROD (read-only) — same prod surface already wired (D-39).

**Areas discussed & selections:**

1. **Command form factor** — options: slash+CLI / CLI only / slash only.
   → **Slash + CLI** (D-41). python `run --id/--list` engine + thin `.claude/commands/test-ticket.md` wrapper.
2. **`--list` CSV format** — options: 1-col ticket_id / +expected / like `uat_ticket.csv`.
   → **like `uat_ticket.csv`** (D-42). `;`-delimited `Level_in;Resolved date;Ticket ID`; key=Ticket ID, group by Level_in.
3. **Output xlsx shape** — options: keep current / add Summary sheet / per-run filename.
   → **Keep current format** (D-44). Both `--id`/`--list` overwrite `test-tickets.xlsx`; local + DRY_RUN only.
4. **Properties scope** — options: extended D-37 / minimal 3-col.
   → **Extended D-37** (D-45).
5. **Batch caps** (follow-up — 4,500-row file risk) — options: `--limit`+`--per-cat` / run-all+confirm / no cap.
   → **`--limit` + `--per-cat`, safe default, log dropped** (D-43). No silent truncation.

### Claude's discretion (session 4)
- Exact subcommand name (`run` vs reuse `collect`); default cap values + warn threshold.
- `.claude/commands/test-ticket.md` wording / arg forwarding.
- Whether `--list` also accepts a plain one-ID-per-line file in addition to the `uat_ticket.csv` format.

> MUST honor the blocking "free-pick template" anti-pattern — reuse the deterministic
> sub-type→allowed-codes map (`_SUBTYPE_TEMPLATES`, PASS-2) in the new command path.
