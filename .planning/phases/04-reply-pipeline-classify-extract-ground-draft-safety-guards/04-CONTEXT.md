# Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft) + Safety Guards - Context

**Gathered:** 2026-06-02 · **Re-homed:** 2026-06-03 (architecture pivot) · **Updated:** 2026-06-04 (PoC pivot D-29/D-30) · **Updated:** 2026-06-05 (`/test-ticket` command — D-41..D-45, see section)
**Status:** Ready for planning (RE-OPEN for code rework — see PIVOT below)
**Canonical design:** `docs/specs/2026-06-02-cs-agent-team-design.md` (APPROVED — planner MUST read, but read through the D-29/D-30 delta)

> ## ⚠️ PIVOT 2026-06-04 (D-29 / D-30) — always-draft PoC; RAG + hard guard/escalation RETIRED
>
> After a 30-ticket live test the RAG-grounded, fail-closed pipeline could not draft (empty KB, no Voyage
> key) and escalated everything. User-confirmed direction change (commit 070509a). **This pivot edited only
> docs (PROJECT/ROADMAP/REQUIREMENTS/CLAUDE.md); the Phase-4 CODE still implements the old fail-closed guard
> architecture.** This CONTEXT update captures the decisions for the **follow-on code rework** that aligns
> the `cs-agent-team` implementation with the pivot.
>
> **Locked by the pivot (do NOT re-decide):**
> - **D-29 — Template/Selless grounding, no RAG.** Reply grounding = local **Template library + Workflow/
>   CODE-MAP**, filled with **Selless (prod)** order data. No semantic RAG, no Voyage embeddings, no mandatory
>   `[KB-N]`/`[SEL-N]` citations.
> - **D-30 — Always-draft PoC.** Pipeline always produces a customer draft. **RETIRED:** D-08 (any-signal
>   escalate), D-10 (escalate=no-draft), D-11 (mandatory citations), **D-26/D-27** (authorized-offer guard +
>   zero-UNAUTHORIZED gate). Offers filled per template, not blocked/stripped.
> - **Safety floor kept:** D-14 (injection screening), D-04 (PII redaction), D-03 (model split, no Opus hot
>   path), Phase-6 kill-switch. **DRY_RUN only** — ⚠️ revisit the removed guard before any live (non-DRY_RUN) send.
>
> **The `<reopen_decisions>` block below (D-26/D-27 authorized-offer guard) is SUPERSEDED by D-30** — kept
> for historical context only; do NOT plan against it.

<pivot_decisions>
## PIVOT CODE-REWORK DECISIONS (2026-06-04) — D-31..D-34

> These four implementation decisions were captured in this discussion. They tell the planner HOW to land the
> D-29/D-30 pivot in the Phase-4 code. They sit ON TOP of D-29/D-30 (which are locked policy, not re-decided).

- **D-31 (locked) — Retire Knowledge MCP → local file-store.** Remove the Knowledge MCP from the runtime
  grounding path. The drafter reads the **26 local template snapshots** + the **Workflow/CODE-MAP** directly
  from files (matches the prototyped file-based draft mode). No `semantic_search`, no pgvector/Voyage. The
  Knowledge MCP server code may be archived but is **not wired** into the team. (Selless MCP STAYS.)
- **D-32 (locked) — DELETE the retired guard hooks.** Remove `pre_send_guard.py`, `escalation_gate.py`,
  `grounding_check.py`, and `authorized_offer.py` entirely (code + their `settings.json` PreToolUse wiring).
  **Keep `injection_screen.py` (D-14) and `pii_redact.py` (D-04) active** — that is the remaining safety
  floor. ⚠️ Trade-off accepted: the before-live "revisit guard" task must re-author a guard from scratch
  (the pivot docs retain the strike-through D-26 spec as the reference for that future work).
- **D-33 (locked) — Always `action=draft` + optional advisory hint.** The verdict is always
  `{action: "draft", body, ...}`. There is no `escalate=no-draft` outcome. An **optional advisory field**
  (e.g. `escalation_hint` for money/legal/injection signals) MAY be attached for downstream human triage,
  but it never suppresses the draft. (Mirrors the "Escalation Semantics Reference (advisory)" in
  `.claude/CLAUDE.md`.)
- **D-34 (locked) — Flow-aware Selless fallback (NOT blind placeholders).** When Selless returns no order
  data, the drafter MUST consult the **Workflow/CODE-MAP** to choose the correct flow rather than fabricate
  numbers. A missing order is a **signal** (customer hasn't purchased yet / wrong order code) → draft the
  appropriate template (e.g. verify-order / clarify-order-info). Placeholder tokens (e.g. `[TRACKING_LINK]`,
  `[ETA]`) are allowed ONLY for infrastructure fields when the flow has established the order is VALID but a
  detail is pending. Never invent order facts.

</pivot_decisions>

<validation_decisions>
## WORKFLOW-VALIDATION RE-DISCUSSION (2026-06-04) — D-35..D-40

> Captured in a discuss-phase re-run focused on **proving the always-draft workflow runs correctly on
> real PROD tickets** and **fixing why the template comes out wrong**. These sit ON TOP of D-29..D-34
> (locked policy) and govern the validation harness + iteration loop (`scripts/test_tickets_run.py`,
> output `test-tickets.xlsx`). Priority stated by user: **workflow-correctness first, keep it simple.**

**Immediate finding (this session):** `test-tickets.xlsx` currently has the **"AI Team value" column
empty** on all 30 sheets — the iter-4 run was paused at 1/30 (see `.continue-here.md`). The xlsx must be
re-populated before any AI-vs-CS comparison is meaningful. The harness has TWO execution paths today —
`collect()` (real `.claude/` team via `claude` CLI) and a standalone `draft()` shortcut
(`_SUBTYPE_TEMPLATES` + `_build_draft_prompt` + `fetch_selless_order`). D-35 picks the real-team path.

- **D-35 (locked) — Validate through the REAL agent-team.** The validation loop drives each ticket
  through the real `.claude/` cs-agent-team (cs-lead + subagents + hooks) via the headless `claude` CLI
  path (`collect()` / `cs_team_demo.py` machinery), NOT the standalone `draft()` shortcut. Rationale:
  "đưa vào agent teams xử lý" — fidelity to production over speed. The standalone `draft()` path is
  **deprecated for validation** (may remain as a debug aid but is not the source of truth).
  ⚠️ Trade-off accepted: slower per ticket; acceptable for workflow-correctness fidelity.
- **D-36 (locked) — CS Agent handling = absolute gold standard.** Every divergence between the AI output
  and the actual CS-agent handling is treated as an **AI error to fix** (we do NOT argue "AI may be more
  correct than CS"). This overrides the `.continue-here.md` advisory note that CS sometimes over-offers —
  for this validation pass, CS is ground truth.
- **D-37 (locked) — Properties scope = EXTENDED.** The harness computes and writes to `test-tickets.xlsx`
  the extended property set side-by-side with CS values: `Customer_Request` sub-type, **template code**,
  `Flow`, `STEP`, `Rootcause`, `Resolution status`, plus the **Reply** body. Every divergence from CS is
  annotated with the reason (per D-40).
- **D-38 (locked) — Stopping criterion = template code + Reply match CS 100%.** "Làm đi làm lại đến lúc
  hết lỗi" is defined NARROWLY: the iteration loop ends when **template code AND Reply content match CS
  on all tickets**. The other extended properties (sub-type, Flow, STEP, Rootcause, Resolution) are
  **recorded + diff-noted for reference only** and do NOT block the loop. This deliberately avoids
  non-convergence on subjective columns (Rootcause/Resolution) while keeping the user's core question
  ("vì sao template không đúng") as the binding gate. Bám đúng "làm đơn giản".
- **D-39 (locked) — PROD, strictly read-only + absolute DRY_RUN.** These are real PROD tickets.
  Freshdesk PROD: **GET only** (ticket description_text + first public CS reply); the harness MUST never
  POST a reply to Freshdesk. Selless PROD (`api.selless.com`): read-only, resolve by human order code
  (`/po/search` → `/po/{id}`). Config: `selless_env=prod` (single source of truth, `src/config.py`,
  commit `1a0d66a`); Freshdesk creds from `.env.prd`. Outputs ONLY to local gitignored `test-tickets.xlsx`
  + `.test-tickets-data.jsonl`. No sandbox-post path is enabled.
- **D-40 (locked) — Dedicated AI-vs-CS checker agent.** A dedicated checker (per-category, general-purpose
  subagent reading `.cs-compare/<cat>.json`) compares AI vs CS for each ticket, classifies each
  template/Reply divergence, **explains WHY they differ**, and feeds fix guidance back into the loop.
  The "why-different" reason is **always recorded in the xlsx** (kept even after the divergence is fixed,
  as an audit trail). Iteration = edit prompt/`_SUBTYPE_TEMPLATES`/map → re-run real team → rebuild
  `.cs-compare` → spawn checker(s) → merge findings → rebuild xlsx → read divergence counts → repeat.

### Claude's Discretion (validation)
- Checker agent count/shape (per-category vs single), prompt wording, and the exact `.cs-compare` JSON
  schema — pick the simplest that surfaces per-ticket template/Reply divergence + reason.
- How the real-team `collect()` path reports computed Properties back for the xlsx (verdict payload shape).
- Whether to keep `draft()` as a debug shortcut or delete it once `collect()` is the validated path.
</validation_decisions>

<test_ticket_command_decisions>
## `/test-ticket` COMMAND RE-DISCUSSION (2026-06-05) — D-41..D-45

> Captured in a discuss-phase re-run focused on turning the working validation harness
> (`scripts/test_tickets_run.py`) into a **clean, on-demand command for arbitrary tickets** —
> run a single ticket by ID or a list from a CSV, drive them through the REAL agent-team, and
> emit the same `test-tickets.xlsx`. These sit ON TOP of D-29..D-40 (locked policy + the validation
> harness) and DO NOT re-decide them. Reuses: D-35 (real-team path), D-36 (CS = gold), D-37
> (extended properties), D-39 (PROD strictly read-only + DRY_RUN), D-40 (checker reason in xlsx).
> User priority restated: **làm đơn giản** — repackage the existing engine, don't rebuild it.

**Data source confirmed:** the "FB Product" lookup = **Freshdesk** (ticket: Customer First Request =
`description_text`, + first public **CS Agent reply**) **+ Selless PROD** (`api.selless.com`,
read-only, resolve by human order code) for order/Properties. Same prod surface already wired (D-39).

- **D-41 (locked) — Command form factor = Slash-command + CLI subcommand (engine in the CLI).**
  Add a python subcommand `run` to `scripts/test_tickets_run.py` accepting `--id <ticket_id>` (single)
  and `--list <csv>` (batch) — this is the reusable engine (headless/CI-safe). Add a **thin**
  `.claude/commands/test-ticket.md` slash-command that dispatches to it so the user can type
  `/test-ticket --id 33403` / `/test-ticket --list uat_ticket.csv` inside Claude Code. The slash file
  holds NO logic — it shells into the CLI. `run` reuses the existing `collect()` real-team machinery
  (D-35), then the existing `build_xlsx()`.
- **D-42 (locked) — `--list` CSV schema = the `uat_ticket.csv` format.** Semicolon-delimited (`;`),
  header `Level_in;Resolved date;Ticket ID`. The harness reads **`Ticket ID`** as the key, uses
  **`Level_in`** as the category bucket (for grouping + `--per-cat`), and treats `Resolved date` as
  informational only. (Reference file: `.../01-knowledge-survey-conflict-inventory/snapshots/confluence/ticket-sample/uat_ticket.csv`.)
- **D-43 (locked) — Batch caps, no silent truncation.** `--list` supports `--limit N` (total cap)
  and `--per-cat N` (per `Level_in` cap) with a **safe default** (e.g. 10/category) so a 4,500-row
  file never silently fans out to thousands of real-team `claude` calls. Whatever is dropped by a cap
  MUST be `log()`-ed (count + which buckets) — never silently truncated. `--id` runs exactly one.
- **D-44 (locked) — Output = keep the current `test-tickets.xlsx` format.** 1 sheet per ticket,
  property rows + CS-vs-AI side-by-side columns (D-37 extended set) + the per-ticket checker
  reason/fix (D-40). Both `--id` and `--list` write to the same gitignored `test-tickets.xlsx`
  (overwrite per run) — matches the user's "output ra giống file test-tickets.xlsx". Outputs ONLY to
  the local gitignored xlsx + `.test-tickets-data.jsonl` (D-39); never POSTs to Freshdesk.
- **D-45 (locked) — Properties scope = EXTENDED (D-37) unchanged.** Surface `Customer_Request`
  sub-type, **template code**, `Flow`, `STEP`, `Rootcause`, `Resolution status`, plus the **Reply**
  body — CS vs AI side-by-side. Binding match gate stays D-38 (template code + Reply); other columns
  recorded + diff-noted for reference.

### Claude's Discretion (`/test-ticket`)
- Exact subcommand name (`run` vs reusing/renaming `collect`) and flag plumbing — keep `--id` and
  `--list` as the public surface; reuse `collect()` internally.
- Default cap values for `--limit`/`--per-cat` and the warn-threshold; the `.claude/commands/test-ticket.md`
  wording and how it forwards args to the CLI.
- Whether `--list` also accepts a plain one-`Ticket ID`-per-line file as a convenience in addition to
  the `uat_ticket.csv` (`;`-delimited) format — pick the simplest robust parse.

> **MUST honor the blocking "free-pick template" anti-pattern** (`.continue-here.md`): the `run` path
> reuses the deterministic sub-type→allowed-codes map (`_SUBTYPE_TEMPLATES`, PASS-2). Do NOT introduce
> a category-glob free-pick in the new command path.

</test_ticket_command_decisions>

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
## ~~REOPEN (2026-06-03) — Authorized-Offer Guard (D-26/D-27, supersedes block-all D-13)~~ — SUPERSEDED by D-30 (2026-06-04)

> ⚠️ **SUPERSEDED by the D-29/D-30 pivot (see top).** The authorized-offer guard (D-26/D-27) is RETIRED:
> the always-draft PoC does not block offers and the Phase-5 gate is advisory (not "0 UNAUTHORIZED"). This
> entire block is retained as the **reference spec for the future before-live guard re-authoring** (D-32),
> NOT as a plannable decision for the current rework. Do not plan against it.

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

### Pivot sources (READ FIRST — override everything below where they conflict)
- `CLAUDE.md` (root) — PIVOT 2026-06-04 banner + stack deltas (Voyage/pgvector-as-RAG/Ragas dropped)
- `.claude/CLAUDE.md` — agent safety contract, D-29/D-30 banner, retired-rule strike-throughs, the surviving
  safety floor (D-14 injection + D-04 PII + D-03 models + kill-switch) and the advisory escalation payload
- Commit `070509a` — the exact pivot diff (docs-only; code rework pending = this phase's work)
- `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP-templates.md` + the 26 template snapshots
  in `.../01-knowledge-survey-conflict-inventory/snapshots/*.md` — the local file-store grounding surface (D-31)

### Validation harness (D-35..D-40 — READ for the workflow-validation loop)
- `scripts/test_tickets_run.py` — the harness: `collect()` (real-team path, D-35), `draft()` (deprecated
  standalone shortcut), `_SUBTYPE_TEMPLATES`, `_build_draft_prompt`, `fetch_selless_order`, `build_xlsx()`
- `scripts/cs_team_demo.py` — production runner machinery reused by the harness (redaction, CLI invoke,
  parse, pre/post-screen)
- `test-tickets.xlsx` (gitignored output) + `.test-tickets-data.jsonl` (gitignored per-ticket records)
- `.cs-compare/<category>.json` — checker-agent inputs (AI-vs-CS per-ticket verdicts)
- `src/config.py` — `selless_env` single source of truth (commit `1a0d66a`); `.env.prd` — Freshdesk PROD creds
- `.continue-here.md` (this phase dir) — blocking anti-patterns + paused iter-4 state

### `/test-ticket` command (D-41..D-45 — READ for the on-demand command)
- `scripts/test_tickets_run.py` — add the `run --id / --list` subcommand (engine; reuses `collect()` + `build_xlsx()`)
- `.claude/commands/test-ticket.md` — NEW thin slash-command wrapper that dispatches to the CLI (no logic)
- `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/confluence/ticket-sample/uat_ticket.csv`
  — the `--list` CSV format (`;`-delimited, header `Level_in;Resolved date;Ticket ID`)

### This phase's design (READ THROUGH THE D-29/D-30 DELTA)
- `docs/specs/2026-06-02-cs-agent-team-design.md` — the approved agent-team architecture, `.claude/`
  layout, safety model, provider plan, local PoC acceptance (the RAG/guard/escalation parts are superseded)

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

> ⚠️ **Replan required.** The 12 existing Phase-4 plans (04-00..04-11) were built for the RAG-grounded,
> fail-closed, authorized-offer-guard architecture. Under D-29/D-30 + D-31..D-34 they are **stale**. The
> rework is a NEW plan set: delete 4 guard hooks (D-32), retire Knowledge MCP wiring → file-store (D-31),
> make the verdict always-draft + advisory hint (D-33), make the drafter flow-aware on missing Selless data
> (D-34), and strip `voyageai`/`pgvector` (RAG use) from `pyproject.toml`. Keep `injection_screen.py` +
> `pii_redact.py`. Current `scripts/cs_team_demo.py` still emits escalate verdicts — it must be reworked too.

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
- **⚠️ BEFORE-LIVE BLOCKER — re-author an output guard.** D-32 deletes the guard hooks for the DRY_RUN PoC.
  Before any live (non-DRY_RUN) send at 23k/week, a guard MUST be re-authored (use the struck-through D-26
  authorized-offer spec as the reference). Tracked here so it is not lost. DRY_RUN only until then.
- Real Selless eligibility wiring (warranty dates, prior-remediation, variant stock) — was deferred as 04-11.
- Live Freshdesk webhook/queue intake + posting (reuse Phase-2 as an integration bridge).
- `samx` platform plugin packaging (`team.yaml`/`pipeline.yaml`).
- AWS Bedrock cut-over (env-driven; not exercised locally).
- Per-claim attribution verifier; agent-suggestion drafts on escalate; LLM-on-guard; per-category
  thresholds (THRS-01); multi-issue/multi-language decomposition.

</deferred>

---

*Phase: 4-reply-pipeline-classify-extract-ground-draft-safety-guards*
*Context re-homed 2026-06-03 to the Claude Code agent-team architecture (design: docs/specs/2026-06-02-cs-agent-team-design.md)*
