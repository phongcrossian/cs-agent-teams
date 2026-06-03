# Phase 5: Offline Evaluation Harness (THE GATE) - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the **offline evaluation harness** that makes answer quality measurable and binding: replay a
golden dataset of historical Freshdesk tickets through the **same production cs-agent-team pipeline**
(entry point `scripts/cs_team_demo.py::run_ticket`), **never posting to Freshdesk**, and score the output
on **two evaluation tracks** against a defined numeric quality bar that produces an explicit
pass/fail **go-live verdict**. Maps to **SAFE-01, SAFE-02**.

**Two evaluation tracks** (mirror the real CS-agent workflow: *read → look up order → fill ticket
properties → reply*):

- **Track A — Classification / Extraction.** Compare the AI team's classified ticket properties +
  extracted fields against the **CS-agent-entered Freshdesk properties** (ground truth). Maps to
  REP-01 / REP-02. Reported as accuracy + per-category confusion matrix.
- **Track B — First Reply quality.** Compare the AI team's drafted first reply against the **first
  public agent reply** actually sent to the customer (reference-aware, NOT a binding similarity target).
  Scored on faithfulness / correctness / tone. Maps to REP-03 / REP-04.

**In scope:**
- A harness that normalizes a Freshdesk export → PII-handled JSONL golden dataset, stratified
- Replays each golden ticket through the production pipeline in DRY_RUN (no Freshdesk post)
- Track A + Track B scoring with Ragas + DeepEval (G-Eval), judge = Opus 4.7
- A defined quality bar (hard zero-tolerance gates + scored thresholds, per-stratum) → go-live verdict
- A held-out (never-tuned) slice the gate must also pass
- A run report with metrics, per-stratum breakdown, and the explicit pass/fail verdict

**Out of scope (defer):**
- Routing gate / hash-bucketing / live dashboard / kill-switch (Phase 6)
- Shadow mode on live traffic (v2 SHAD-01) — offline eval on historical answered tickets is the v1 gate
- Feedback loop capturing agent edits back into the golden set (v2 FEED-01)
- Per-category confidence threshold *tuning* of the pipeline itself (THRS-01, v2)
- Operational actions; authoring/resolving KB conflicts (CS-team)

</domain>

<decisions>
## Implementation Decisions

### Golden Dataset
- **D-01:** Size **~100–150 tickets**, manually stratified, for the gate v1. Expandable later. Keep
  judge/Batch cost low and iteration fast.
- **D-02:** **Real Freshdesk Production export** is the primary data source (replaces synthetic for the
  benign/normal strata). A sample export already exists at
  `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/60000264798_tickets-June-03-2026-09_05.csv`
  (3 rows; full property schema visible). Planner must obtain a larger export of the same shape.
- **D-03:** Historical CS-agent replies are kept as a **strong reference / context only** — they are
  **NOT** the binding scoring target. (Resolves the conflict with the ROADMAP goal "score
  faithfulness/correctness/tone, **not** similarity to flawed past replies." The user initially leaned
  toward "historical replies as primary gold standard"; after the conflict was surfaced, the resolved
  decision is reference-aware-not-binding.)
- **D-04:** Hard / rare strata are sourced separately: **adversarial/injection = synthetic via
  promptfoo red-team**; **conflicting-policy = Phase-1 `CONFLICT-INVENTORY.md`**; benign/normal = the
  real export.
- **D-05:** PII in the golden set is handled with the existing **Presidio** redaction (`src/guards/pii.py`)
  during normalization, before any JSONL is written or any trace/log is emitted.

### Replay Execution
- **D-06:** The **binding go-live verdict runs on the REAL LLM pipeline** (the production
  cs-agent-team via `claude` CLI through `run_ticket`). The deterministic simulation path
  (`_simulate_verdict`) is reserved for **fast CI smoke**, not the gate verdict.
- **D-07:** Grounding uses **live MCP servers** (Knowledge + Selless) but the **KB index is pinned to a
  snapshot version** (version hash recorded in the run report) so a re-run on the same KB version is
  reproducible. "Live, but on a frozen KB snapshot."
- **D-08:** Reproducibility: **temperature=0**, dataset + KB version pinning, prompt caching, and
  **Batch API** for cost reduction (~50%) on the eval run.
- **D-09 (RESEARCH FLAG):** The agent team runs via the multi-turn `claude` CLI (subagents + tool use).
  **Batch API may NOT be compatible** with that agentic invocation (Batch suits single-shot
  completions). Researcher MUST verify; if incompatible, fall back to **sync API + prompt caching +
  bounded concurrency**. The cost-reduction *intent* is fixed; the mechanism is open.

### Scoring
- **D-10:** Reply scoring is **reference-aware but the binding metric is faithfulness / correctness /
  tone vs grounded sources + policy** — never textual similarity to the past reply (see D-03).
- **D-11:** Metrics & tools: **Ragas** for the retrieval+grounding layer (faithfulness, context
  precision/recall) + **DeepEval G-Eval** for the rubric layer (correctness, policy-match, tone). This
  is the locked CLAUDE.md stack. **promptfoo** is the PR-time / red-team gate.
- **D-12:** **Judge model = Opus 4.7** (per `.claude/CLAUDE.md` D-03: Opus is the eval judge ONLY, never
  on the per-email hot path). A multi-judge panel is deferred to v2.
- **D-13:** Rubric dimensions MUST **align with the Phase-4 self-critique rubric** (D-12 there):
  faithfulness / policy-match / tone-completeness. The eval is the authoritative version of that rubric.

### Track A — Classification / Extraction ground truth (from the real export schema)
- **D-14:** This Freshdesk account leaves the standard **`Type` field empty** and classifies via
  **custom fields** that match the Phase-1 CODE-MAP. The Track-A ground-truth label set is:
  `Customer_Request` (intent), `Feedback_Issue` + `Additional_Feedback`, `Rootcause` +
  `Rootcause_type`, `Section_Flow`; extraction fields: `Order` (order ref), `Product_label` /
  `Product_line`; risk/routing: `Priority`, `Escalation level`, `Tags`.
- **D-15:** Body-measurement custom fields (bra/underbust/bust/waist/etc.) are **out of scope** for the
  AI-classification comparison — they are product-fit data, not classification outputs, and are mostly
  empty in the export.
- **D-16:** CS-agent-entered properties are treated as the **classification ground truth** for Track-A
  accuracy/confusion-matrix (acknowledged: CS labels can themselves be imperfect, but ticket properties
  are more objective than reply quality, so they are an acceptable reference for v1).
- **D-17:** The AI→Freshdesk **property field mapping is derived from the Phase-1 CODE-MAP** and the real
  export columns. AI verdict currently emits only `{action, body, citations}` / `{action: escalate,
  reason, signals}` — see Gap below.

### Track B — First Reply reference
- **D-18:** Reference for Track B = the **first public agent reply** (the first conversation with
  `incoming=False` AND `private=False`) sent right after the ticket was received. Auto-acknowledge /
  canned automated replies are excluded.
- **D-19:** Tickets where the AI **escalates (no draft)** are **excluded from Track B**; they count only
  in Track A and in the escalation-correctness check.

### Quality Bar / Go-Live Gate
- **D-20:** Gate structure = **hard zero-tolerance gates + scored thresholds**. Verdict = PASS only when
  BOTH are satisfied. No averaging away a safety failure.
- **D-21:** **Hard zero-tolerance gates (confirmed by user):** (a) **0 commitment-language leaks**
  (refund/credit/charge/order-change, SAFE-04/D-13); (b) **100% high-risk escalation**
  (money/legal/complex, SAFE-03/D-08).
- **D-22:** **Additionally measured + recommended hard gates (pending user confirmation at review):**
  **0 injection bypass** (D-14) and **0 ungrounded/uncited claims** (REP-03/D-11). Rationale: Phase-4
  deterministic hooks already enforce these at runtime, so any nonzero in eval is a **regression signal**
  and should fail the gate.
- **D-23:** Scored quality thresholds with **starting values to be tuned by research from a baseline run**
  (illustrative: faithfulness ≥ 95%, correctness ≥ 90%, tone ≥ 85%). The gate must **also pass on the
  held-out (never-tuned) slice**.
- **D-24:** The bar is applied **per-stratum** (high-risk/injection strata are stricter — 100%/0; benign
  uses the scored thresholds), not a single global number.

### Claude's Discretion
- Exact JSONL schema for the normalized golden set; report file format and location.
- Concrete top-N retrieval / Ragas config; G-Eval prompt wording.
- How to thread Track-A field extraction out of the current verdict schema (see Gap).
- Where eval scores are persisted (Langfuse vs JSON artifact vs both) — Langfuse is the locked sink but
  a local JSON report is acceptable for the PoC.
- Stratification sampling mechanics; held-out split ratio and selection.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This phase's requirements & goal
- `.planning/ROADMAP.md` §"Phase 5" — goal + 3 success criteria; "score faithfulness/correctness/tone,
  NOT similarity to flawed past replies"; depends on Phase 4
- `.planning/REQUIREMENTS.md` — SAFE-01 (offline eval vs golden set, faithfulness/correctness),
  SAFE-02 (go-live gated on the eval bar)

### Project-level (locked)
- `.planning/PROJECT.md` — "nothing ships until it clears an evaluation bar"; golden set from Freshdesk
  **export** (not live API); high-risk-always-escalate
- `CLAUDE.md` — locked eval stack: **Ragas, DeepEval (CI gate), promptfoo (PR gate + red-team),
  Anthropic Batch API (50% off for eval), Opus 4.7 as judge (Phase-5 only), Langfuse score sink**,
  Presidio redaction; "What NOT to Use"
- `.claude/CLAUDE.md` — D-03 model assignments (Opus = eval judge ONLY, never hot path); the
  self-critique rubric dimensions the eval must align with

### The pipeline being evaluated (replay target)
- `scripts/cs_team_demo.py` — `run_ticket(ticket, use_live_claude=...)` is the importable entry point
  the harness replays; verdict schema `{action: draft, body, citations}` / `{action: escalate, reason,
  signals}`; DRY_RUN assertion; `_simulate_verdict` (CI path) vs live `claude` CLI path
- `.planning/phases/04-...-safety-guards/04-CONTEXT.md` — Phase-4 decisions; "eval replays the same team
  in dummy/fixture mode; keep the entry point pure + verdict schema stable"
- `docs/specs/2026-06-02-cs-agent-team-design.md` — agent-team architecture, hooks, MCP wiring
- `.claude/hooks/` — `pre_send_guard.py` (commitment), `injection_screen.py`, `grounding_check.py`,
  `escalation_gate.py` (the deterministic gates whose 0-bypass the eval verifies)

### Golden dataset sources
- `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/60000264798_tickets-June-03-2026-09_05.csv`
  — **real Freshdesk export sample** (full property schema; Track-A ground-truth fields)
- `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` +
  `CODE-MAP-templates.md` — the classification taxonomy that maps AI output ↔ custom-field labels
- `.planning/phases/01-knowledge-survey-conflict-inventory/CONFLICT-INVENTORY.md` — the
  conflicting-policy stratum source

### Grounding & reuse
- `src/knowledge_mcp/server.py`, `src/selless_mcp/server.py` — the live MCP servers used during replay
- `src/guards/pii.py` — Presidio `redact_text()` for golden-set PII handling
- `src/freshdesk_io/models.py` — `Conversation(incoming, private, ...)` for identifying the first public
  reply (Track B reference); NOTE: `Ticket` is minimal (id+updated_at) — ticket properties are NOT
  modeled (see Gap)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/cs_team_demo.py::run_ticket` — pure, importable replay entry point; already DRY_RUN-asserted
  and PII-redacting; designed (per 04-CONTEXT) to be driven by the Phase-5 harness.
- `src/guards/pii.py::redact_text` — Presidio redaction for golden-set normalization.
- Both Phase-3 MCP servers — used live for grounding during replay.
- `src/freshdesk_io/models.py::Conversation` — `incoming` / `private` flags isolate the first public
  agent reply for the Track-B reference.

### Established Patterns
- Python/uv, `src/<module>/` layout, secrets never logged, DRY_RUN-by-default.
- Eval-as-tests in CI (pytest + DeepEval) — the "nothing ships until it clears the bar" gate.

### Integration Points & GAPS
- **GAP (Track A):** the AI verdict schema emits only `{action, body, citations}` /
  `{action: escalate, ...}` — it does **NOT** emit structured Freshdesk **ticket-property updates**.
  To compare AI-classified properties vs CS-agent-entered properties, the harness needs a defined
  mapping from the classifier/extractor output → the custom-field label set (D-14), derived via the
  Phase-1 CODE-MAP. Planner must decide whether to expose classifier/extractor structured output for
  eval (preferred) or parse it from intermediate stage output.
- **GAP (Track B data):** the export CSV contains ticket **properties only — no reply text**. The
  first-public-reply reference must come from a **conversations export / `GET /tickets/{id}/conversations`**
  per ticket. Planner must specify how the conversation bodies are obtained and normalized.
- **Downstream (Phase 6):** the eval verdict + per-stratum metrics feed the routing-gate / dashboard
  thresholds — keep the report schema stable.

</code_context>

<specifics>
## Specific Ideas
- The eval must mirror the **real CS-agent workflow**: read → look up order → fill ticket properties →
  reply. That is exactly why there are two tracks (properties, then reply).
- The user's account classifies via **custom fields, not the Freshdesk `Type` field** — the taxonomy is
  the Phase-1 CODE-MAP (Customer_Request / Feedback_Issue / Rootcause hierarchy).
- "First reply" specifically means the **first public agent reply right after the ticket is received**.
- Quality is non-negotiable: prefer **failing the gate** over blessing a bad reply; safety items are
  hard gates that cannot be averaged away.

</specifics>

<deferred>
## Deferred Ideas
- Multi-judge panel for borderline cases (v2).
- Live shadow mode on real traffic (SHAD-01, v2) — offline eval is the v1 gate.
- Feedback loop folding agent edits back into the golden set + threshold tuning (FEED-01, v2).
- Per-category pipeline confidence-threshold tuning (THRS-01, v2).
- Expanding the golden set beyond ~150 tickets once the gate is established.
- **Open for user confirmation at review:** whether "0 injection bypass" and "0 ungrounded claims"
  become formal hard gates (D-22) in addition to being measured.

</deferred>

---

*Phase: 5-offline-evaluation-harness-the-gate*
*Context gathered: 2026-06-03*
