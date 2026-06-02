# Design — `cs-agent-team` (Claude Code Agent Team, local-first)

**Date:** 2026-06-02
**Status:** Approved (brainstorming) — ready for planning/build
**Supersedes:** the PydanticAI staged-pipeline approach in `04-CONTEXT.md` and the four `04-*-PLAN.md` files (D-01..D-14 logic is preserved but re-homed; see §8).

---

## 1. Purpose & scope

Build the customer-support email auto-reply system as a **standard Claude Code agent team**
(`.claude/` with `agents/`, `skills/`, `hooks/`, `CLAUDE.md`, MCP wiring) that runs **locally first**
(PoC against the developer's Claude subscription via the `claude` CLI / Claude Agent SDK).

The same team-kit is later **packaged as a Layer-4 plugin** for the `samx` managed-agents platform
(`plugin/cs-agent-team-kit/`), where the platform harness calls the team **lead** directly and
production inference runs on **AWS Bedrock**. Nothing in the local design blocks that move — model
provider is env-driven and the `.claude/` layout maps onto a platform team-kit.

**In scope (local PoC):**
- A `.claude/` agent team: a **team lead** + member subagents (classifier, extractor, drafter, critic).
- Skills holding the reply **workflow** and the **template-fill** procedure.
- Deterministic **hooks** enforcing the safety-critical guards.
- Wiring the two **Phase-3 MCP servers** (Selless + Knowledge) as the team's grounding tools.
- Running end-to-end on a **sample ticket** in **DRY_RUN** → producing a grounded draft OR an
  escalation verdict, with guards demonstrably enforced.

**Out of scope (deferred):**
- Live Freshdesk webhook/queue intake + posting (reuse Phase-2 later as an integration bridge).
- Packaging into the `samx` platform plugin (`team.yaml` / `pipeline.yaml` DSL).
- AWS Bedrock cut-over (design supports it; not exercised in the local PoC).
- The Phase-5 offline eval harness (will replay golden tickets through this same team in dummy-mode).

**Reused as-is:** Phase-1 KB survey + CODE-MAP/templates; Phase-2 Freshdesk I/O + queue + loop-guard
+ Presidio; Phase-3 Selless MCP + Knowledge MCP.

---

## 2. Architecture

The Claude Agent SDK / `claude` CLI invokes the **team lead** (`cs-lead`). The lead orchestrates a
fixed procedure, delegating heavy stages to member subagents and calling MCP tools. **Determinism and
safety are enforced by deterministic hooks** (and the lead's workflow skill), not left to the model's
discretion.

```
Claude Agent SDK / claude CLI
        │ (calls the team lead)
        ▼
   cs-lead  ──orchestrates──►  classify → [escalation gate] → extract → ground+draft → critique
        │                         │                              │            │            │
        │ delegates to            ▼                              ▼            ▼            ▼
        │                    classifier(Haiku)            extractor(Haiku)  drafter(Sonnet) critic(Sonnet)
        │                                                       │            │
        ▼                                              Selless MCP    Knowledge MCP (semantic_search,
   emits VERDICT:  {action: "draft", body, citations}    (resolve_order,  lookup_code, get_template)
                   or {action: "escalate", reason, signals}  get_order_status, ...)

        ▲ deterministic HOOKS wrap every tool/stage:
          commitment-block · injection-screen · escalation-gate · grounding-check · pii-redact
```

**Flow (lead procedure):** classify → (escalation gate) → extract (resolve order key) →
ground + draft (cited) → self-critique → emit verdict. **Any** risk signal — low confidence,
ambiguous category, missing lookup key, Knowledge-MCP conflict flag, stale-only grounding, deterministic
risk/keyword hit, commitment-language hit, injection suspicion, or a failed critique after one redraft —
forces an **`escalate`** verdict with **no customer draft**. **DRY_RUN only**: the verdict is captured/logged;
nothing is posted to Freshdesk in this phase.

---

## 3. `.claude/` layout

```
.claude/
├── agents/
│   ├── cs-lead.md          # TEAM LEAD — entry point; executes the reply-pipeline skill, owns the verdict
│   ├── classifier.md       # Haiku — support category + confidence bucket (high/med/low) + high-risk marker
│   ├── extractor.md        # Haiku — answer-key (order_code, customer_email, issue_type, product refs); resolve_order
│   ├── drafter.md          # Sonnet — grounded reply with inline citations; selects+fills template
│   └── critic.md           # Sonnet — rubric scoring: faithfulness / policy-match / tone-completeness → pass|fail
├── skills/
│   ├── reply-pipeline/SKILL.md      # THE WORKFLOW — stage order, delegation, escalation rules, verdict shape
│   ├── classify-ticket/SKILL.md     # two-level taxonomy guidance (category vs CODE-MAP)
│   ├── extract-answer-key/SKILL.md  # extraction schema + resolve_order usage + missing-key→escalate
│   ├── ground-and-draft/SKILL.md    # retrieval policy + how to select/fill a template (content via get_template)
│   └── self-critique/SKILL.md       # rubric dimensions (kept aligned with Phase-5 eval rubric)
├── hooks/                  # deterministic guards (Python; reuse src/guards/)
│   ├── injection_screen.py # PreToolUse — screen the untrusted email body; suspicion → escalate
│   ├── pre_send_guard.py   # blocks commitment-language re refunds/credits/charges/order-changes → escalate
│   ├── escalation_gate.py  # conflict/stale-only/missing-key/low-confidence/risk → escalate verdict, no draft
│   ├── grounding_check.py  # every factual claim must map to a citation; else fail → redraft-once → escalate
│   └── pii_redact.py       # Presidio redaction before any log/trace write (reuses src/guards/pii.py)
├── settings.json           # MCP server registration + hook bindings + per-stage model + DRY_RUN flag
└── CLAUDE.md               # team rules (non-negotiables) — the LLM-readable copy of the safety contract
```

### Where each concern lives (explicit decisions)
- **Workflow** → `skills/reply-pipeline/SKILL.md`; `cs-lead.md` only references it. Hard ordering &
  early-exit are enforced by `hooks/escalation_gate.py`, not by trusting the model to remember.
- **Rules** → stated in `CLAUDE.md` (always-on, LLM-readable) **and** enforced in `hooks/` for the
  non-negotiables. Agent-local rules (e.g. citation discipline) live in that agent's own `.md`.
- **Templates** → remain in the **Knowledge MCP**, fetched at runtime via `get_template(code)`
  (centralized, versioned, cited — per the CLAUDE.md "centralized KB, no raw-source-per-reply" rule).
  `ground-and-draft` documents *selection/fill*; it does not hard-code template bodies.

---

## 4. Safety model (hybrid: deterministic hooks + agent)

Business-critical decisions run as **code in hooks** that the lead and subagents cannot bypass;
soft quality is judged by the LLM critic.

| Concern | Mechanism | Decision |
|---|---|---|
| Commitment language (refund/credit/charge/order-change) | `pre_send_guard.py` — deterministic block + escalate; never auto-strip-and-send | D-13 / SAFE-04 |
| Prompt injection in email body | body delimited as untrusted data in every prompt + `injection_screen.py`; suspicion → escalate | D-14 / SAFE-04 |
| High-risk routing (money/legal/complex) | defense-in-depth, any-signal-escalates: deterministic keywords + risk marker + category | D-08 / SAFE-03 |
| Knowledge conflict flag / stale-only grounding | `escalation_gate.py` forces escalate | D-09 |
| Missing lookup key / low confidence | escalate (never fabricate context) | D-06 / D-07 |
| Ungrounded claims | inline citations + `grounding_check.py` + critic faithfulness dimension | D-11 |
| Self-critique fail | redraft once → escalate if still failing | D-12 |
| PII in logs/traces | `pii_redact.py` (Presidio) before any sink | D-04 + CLAUDE.md |
| Escalate semantics | early-exit verdict, NO customer draft (DRY_RUN) | D-10 |

---

## 5. Model assignment & provider

- **Per stage:** classify / extract / risk → **Haiku 4.5**; draft + critic → **Sonnet 4.6**.
  **No Opus on the hot path** (reserved for Phase-5 judge). Set in `settings.json` per agent.
- **Provider (env-driven, no code change):**
  - **PoC (local):** `claude` CLI authenticated via the developer's Claude subscription (`claude login`).
  - **Production:** `CLAUDE_CODE_USE_BEDROCK=1` + AWS creds + Bedrock model-ID mapping per stage.
- **Prompt caching:** cache the system prompt + retrieved policy/template blocks (largest cost lever).

> Open items to verify at build time: (a) whether the local Agent SDK run authenticates via the
> Claude subscription vs an API key; (b) the exact Bedrock model IDs that map to Haiku/Sonnet.

---

## 6. Grounding (reuse Phase-3 MCPs)

- **Knowledge MCP** (`src/knowledge_mcp`): `semantic_search` (cited, conflict/stale-aware),
  `lookup_threshold`, `lookup_code`, `get_template`. Registered in `settings.json`.
- **Selless MCP** (`src/selless_mcp`): `resolve_order`, `get_order_status`, `get_customer_info`,
  `get_purchase_history`, `get_ticket_history` — keyed reads only, field-whitelisted, audited.
- The `drafter` may only state facts that come from a citation (Knowledge) or a whitelisted Selless
  field; `grounding_check.py` enforces this.

---

## 7. Local PoC entry & demo

- A thin runner (`scripts/cs_team_demo.py` or `claude` headless invocation) feeds a **sample ticket**
  (benign and high-risk variants) to `cs-lead` and prints the resulting verdict.
- **Acceptance:** benign ticket → `draft` verdict with ≥1 citation and no commitment language;
  high-risk ticket (e.g. refund request / injection attempt) → `escalate` verdict with the triggering
  signal and **no draft**. PII never appears in logs/traces.

---

## 8. Relationship to GSD Phase 4 (what changes)

- This design **replaces** the PydanticAI staged-pipeline implementation planned in `04-02`.
- **Preserved:** the 14 locked decisions D-01..D-14 (re-homed: stages→agents, controller→lead+hooks,
  guards→hooks, schema/verdict→the verdict the lead emits), the threat model, the worker-seam reuse
  (deferred to the integration step), DRY_RUN-only posture, Phase-5 rubric alignment.
- **Action:** rewrite `04-CONTEXT.md` to this direction and re-plan Phase 4 (the existing four
  `04-*-PLAN.md` are stale) before/at build, per GSD.

---

## 9. Open questions (non-blocking, resolve at build)
1. Local Agent SDK auth: Claude subscription vs API key for the PoC run.
2. Bedrock per-stage model-ID mapping (for the production cut-over).
3. Whether `cs-lead` delegates to subagents via the Task/subagent mechanism or runs stages inline via
   skills — pick the simplest that keeps hooks enforceable.
4. Hook transport: Claude Code `settings.json` hooks (shell→Python) vs Agent SDK programmatic hooks —
   choose based on which the local runner uses.
