# Phase 5: Offline Evaluation Harness (THE GATE) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 5-offline-evaluation-harness-the-gate
**Areas discussed:** Golden dataset, Replay execution, Scoring, Quality bar / go-live gate, Two-track eval (Ticket Properties + First Reply)

---

## Golden dataset

| Option | Description | Selected |
|--------|-------------|----------|
| ~100–150 tickets, manually stratified | Enough for gate v1, low judge/Batch cost, fast iteration | ✓ |
| ~300–500 tickets | Stronger statistics, more cost/curation | |
| Few thousand | Comprehensive but expensive, slow | |

| Option | Description | Selected |
|--------|-------------|----------|
| No reference — ticket + grounded sources only | Reference-free rubric scoring | |
| Human-curated clean "gold" subset | High quality, human effort | |
| Use historical agent replies as-is | Cheapest; past replies may be wrong | ✓ (later re-scoped) |

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic (promptfoo red-team) + Phase-1 CONFLICT-INVENTORY | Reuse existing assets | ✓ |
| Real tickets only from Freshdesk export | Realistic but sparse on injection cases | |
| Mixed: real base + synthetic for missing strata | | |

**User's choice:** ~100–150 tickets; keep historical replies; synthetic + CONFLICT-INVENTORY for hard strata.
**Notes:** "Use historical replies as-is" was flagged as conflicting with the ROADMAP goal ("not similarity
to flawed past replies"). Re-scoped in the Scoring area to **reference-aware-but-not-binding**.

---

## Replay execution

| Option | Description | Selected |
|--------|-------------|----------|
| Two-tier: real LLM for gate + simulation for CI | Gate reflects production; sim for fast smoke | (recommended) |
| Real LLM only | Closest to production; CI slow/costly | ✓ |
| Simulation only | Cheap/deterministic but doesn't measure real LLM quality | |

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed fixture/snapshot, KB version-pinned | Reproducible, no drift | (recommended) |
| Live MCP | Production-close, may drift | ✓ |
| Live Knowledge + Selless fixture | | |

| Option | Description | Selected |
|--------|-------------|----------|
| temperature=0 + snapshot version + Batch API | Reproducible + 50% cost cut | ✓ |
| Run N times, measure variance | Stronger for edge cases, costlier | |
| Single run, accept variance | Simplest, risky near thresholds | |

**User's choice:** Real LLM only; live MCP; temperature=0 + snapshot version + Batch API.
**Notes:** Reconciled "live MCP" + "snapshot version" → live MCP on a **version-pinned KB snapshot**.
Flagged that **Batch API may be incompatible** with the multi-turn agent CLI → research item, fallback to
sync + caching + concurrency.

---

## Scoring

| Option | Description | Selected |
|--------|-------------|----------|
| Reference-free primary; old reply = context only | Faithfulness/correctness vs grounded sources | ✓ (after reconcile) |
| Old reply as weighted reference for correctness | Risk of penalizing correct-but-different replies | |
| Old reply as the primary gold standard | Conflicts directly with goal | ✗ (initially picked, then overridden) |

| Option | Description | Selected |
|--------|-------------|----------|
| Ragas (grounding) + DeepEval G-Eval (rubric) | Locked CLAUDE.md stack | ✓ |
| DeepEval G-Eval only | Loses retrieval/generation separation | |
| Hand-written LLM-judge | Flexible, loses standardization | |

| Option | Description | Selected |
|--------|-------------|----------|
| Opus 4.7 (D-03, Phase-5 only) | Highest judging quality, allowed off hot path | ✓ |
| Sonnet 4.6 | Cheaper, lower discrimination | |
| Mixed / multi-judge panel | Stronger but costly | |

**User's choice:** reference-aware-not-binding; Ragas + DeepEval G-Eval; Opus 4.7 judge.
**Notes:** Explicit conflict-resolution question asked. User confirmed: historical reply = **strong
reference**, but the binding pass/fail score is **faithfulness/correctness/tone** — goal-compatible.

---

## Quality bar / go-live gate

| Option | Description | Selected |
|--------|-------------|----------|
| Hard zero-tolerance gates + scored thresholds | Safety hard, quality scored | ✓ |
| Scored aggregate only | Can average away safety failures | |
| Hard binary only | Misses faithfulness/tone signal | |

Hard gates (multiSelect): **0 commitment leak ✓**, **100% high-risk escalation ✓**,
0 injection bypass (not selected), 0 ungrounded claim (not selected).

| Option | Description | Selected |
|--------|-------------|----------|
| Set starting thresholds + must pass held-out | Illustrative numbers, tuned by research | ✓ |
| Let research propose thresholds from baseline | Defer numbers to plan | |
| Thresholds + human sign-off on final verdict | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per-stratum bar | High-risk/injection stricter | ✓ |
| Global bar | Can hide concentrated failure | |
| Both global + per-stratum check | | |

**User's choice:** hard + scored; hard gates = commitment leak + high-risk escalation; starting thresholds
+ held-out must pass; per-stratum bar.
**Notes:** Injection-bypass and ungrounded-claim were NOT selected as hard gates; flagged that since Phase-4
hooks already enforce them, eval should still measure them and treat nonzero as a regression failure
(recorded as recommended hard gates, pending review confirmation).

---

## Two-track evaluation (user clarification via free-text)

The user clarified what "test results" means against their real Freshdesk Production export:
1. **Ticket Properties** the AI classifies/would update vs the properties the CS agent actually entered.
2. **First reply** the AI drafts vs the reply actually sent to the customer.

Clarifying answers:
- CS-agent workflow = **read → look up order → fill ticket properties → reply**; asked to verify against code.
- "First reply" = **first public agent reply right after the ticket is received**.
- Export file provided: `60000264798_tickets-June-03-2026-09_05.csv` (found in Phase-1 snapshots, 3 rows).

Workflow/code check findings (folded into CONTEXT D-14..D-19 + GAPS):
- The Freshdesk `Type` field is empty; classification lives in **custom fields** (Customer_Request,
  Feedback_Issue, Additional_Feedback, Rootcause, Rootcause_type, Section_Flow) = Phase-1 CODE-MAP taxonomy.
- Body-measurement custom fields are out of scope for AI classification.
- AI verdict schema emits no structured property updates → mapping gap.
- The CSV has properties only (no reply text) → Track-B reference needs conversations export/API.

---

## Post-discussion investigation (user-requested) — workflow / case-handling check

User asked to verify whether the agent team already updates ticket properties, and to fetch a real reply
from Freshdesk (`.env.prd`, `shophelp.freshdesk.com`).

Findings:
- **No property-update capability.** classifier emits `{category, code, confidence, high_risk}`, extractor
  emits `{order_ref, customer_email, issue_type, product_refs, ...}`, but the final verdict is only
  `{action, body, citations}` / escalate — no Freshdesk property write; `reply_mcp` has `submit_reply` only.
- **Live fetch worked.** Ticket 7732073's first public agent reply = template **B7** verbatim
  (50% refund + 40% VIP discount), a within-guarantee non-defective product-complaint resolution.
- **Critical:** this is the *correct templated flow*, but Phase-4 `pre_send_guard.py` (D-13) blocks all
  commitment language → would escalate it. User decided to **reopen Phase 4** to make the guard
  template + threshold aware. Captured as CONTEXT D-25..D-28; gate redefinition (D-27) and a BLOCKING
  Phase-4 sequencing dependency recorded.

| Option | Description | Selected |
|--------|-------------|----------|
| Guard template + threshold aware (revisit Phase 4) | Allow authorized in-policy offers; block only out-of-template/over-threshold/fabricated | ✓ |
| v1 keep D-13 block-all, automate only no-money flows | Safe, low coverage, no Phase-4 change | |
| Let Phase-5 eval measure/expose first | Quantify false-escalation before deciding | |
| Discuss more before locking | | |

---

## Claude's Discretion
- JSONL/report schema and location; Ragas config; G-Eval prompt wording; how to expose classifier/extractor
  structured output for Track A; score persistence (Langfuse vs JSON); held-out split mechanics.

## Deferred Ideas
- Multi-judge panel; live shadow mode (SHAD-01); feedback loop (FEED-01); per-category threshold tuning
  (THRS-01); golden-set expansion beyond ~150; formalizing injection/ungrounded as hard gates (review).
