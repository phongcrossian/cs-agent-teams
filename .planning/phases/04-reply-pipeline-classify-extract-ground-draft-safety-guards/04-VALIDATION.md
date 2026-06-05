---
phase: 04
slug: reply-pipeline-classify-extract-ground-draft-safety-guards
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-03
updated: 2026-06-05
---

# Phase 04 — Validation Strategy

> Per-phase validation contract. The **enforceable / deterministic** behavior of this phase
> (the always-draft pipeline + surviving safety floor) is fully covered by automated tests.
> The remaining requirement dimensions are **LLM output quality** (classification accuracy,
> extraction accuracy, critique scoring), which are non-deterministic by nature and are deferred
> — by design — to the Phase-5 offline-eval harness (SAFE-01/SAFE-02). They are recorded as
> Manual-Only here, not as coverage gaps.
>
> **Pivot (2026-06-05 — plans 04-01..04-05):** The fail-closed guard architecture (D-08/D-10/D-11/D-26)
> is retired. The pipeline is now **always-draft** (D-33). Four guard hooks deleted; two surviving
> hooks (injection_screen + pii_redact) are the enforced safety floor. KnowledgeMCP removed (D-31).
> Tests updated in plan 04-04 to match this reality.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (+ stdlib `subprocess` for deployed-hook proofs) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/cs_team -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~70 seconds (full) / ~5 seconds (cs_team subset) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/cs_team -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green (last run: 97 passed, 5 skipped, 0 failed)
- **Max feedback latency:** ~70 seconds

---

## Per-Task Verification Map

| Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File | Status |
|-------------|------------|-----------------|-----------|-------------------|------|--------|
| **SAFE-04** (injection screening, D-14) | T-04-04-01 | Injection body → `injection_screen` non-zero (advisory block + escalation_hint attached); clean body → exit 0 | unit + **subprocess** | `uv run pytest tests/cs_team/test_hooks_subprocess.py tests/cs_team/test_hooks.py -q` | `test_hooks_subprocess.py` (`TestInjectionScreenSubprocess`), `test_hooks.py` (injection cases) | ✅ green |
| **SAFE-04** (PII redaction, D-04) | T-04-04-01 | PII (email/phone) redacted before any log/trace; `pii_redact_hook` never blocks | unit | `uv run pytest tests/cs_team/test_hooks.py tests/cs_team/test_hooks_red.py -q` | `test_hooks.py` (pii cases), `test_hooks_red.py` (`test_pii_redact_hook_*`) | ✅ green |
| **SAFE-03** (advisory escalation_hint for high-risk, D-33) | T-04-04-02 | High-risk ticket → `action="draft"` WITH non-null `escalation_hint`; NEVER `action="escalate"` with no body | e2e (mock) | `uv run pytest tests/cs_team/test_e2e_dry_run.py -q` | `test_e2e_dry_run.py` (`test_high_risk_ticket_produces_draft_with_hint`, `test_high_risk_ticket_never_escalate_verdict`) | ✅ green |
| **REP-01** (always-draft routing: all tickets → draft) | T-04-03-04 | Benign → `action="draft"` no hint; high-risk → `action="draft"` + hint; injection → `action="draft"` + hint | e2e (mock) | `uv run pytest tests/cs_team/test_e2e_dry_run.py -q` | `test_e2e_dry_run.py` (`test_benign_ticket_produces_draft`, `test_high_risk_ticket_produces_draft_with_hint`, `test_injection_ticket_produces_draft_with_hint`) | ✅ green |
| **REP-01/02/03/04** (agent + skill structure, model discipline) | T-04-02-05 / T-04-00-03/04 | Correct agents/skills exist; Haiku on classify/extract, Sonnet on draft/critic/lead, no claude-opus; file-store grounding (D-31); two surviving hooks | structural | `uv run pytest tests/cs_team/test_team_definitions.py tests/cs_team/test_settings_hook_bindings.py tests/cs_team/test_team_kit_structure.py -q` | `test_team_definitions.py`, `test_settings_hook_bindings.py`, `test_team_kit_structure.py` | ✅ green |
| **REP-04** (self-critique rubric dimensions defined) | — | Critic agent + self-critique skill declare faithfulness / policy-match / tone-completeness dimensions | structural | `uv run pytest tests/cs_team/test_team_definitions.py -q` | `test_team_definitions.py` (`test_self_critique_skill_*_dimension`) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all automatable phase requirements. The Phase-04 Wave-0 bootstrap
(`04-00`) already installed the cs_team test package, fixtures (`conftest.py`,
`tests/fixtures/sample_tickets.py`). The subprocess proof harness was added in `04-05`/review
and slimmed to injection_screen only in 04-04.
No additional Wave-0 test scaffolding required.

---

## Manual-Only Verifications

These dimensions are **LLM output quality** — non-deterministic and not unit-testable without
asserting on live model output (which would produce flaky tests). They are deferred to the
**Phase-5 offline-eval harness** (SAFE-01 golden-dataset scoring, SAFE-02 go-live quality gate).

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Classification assigns the *correct* support category | REP-01 | LLM judgment; correctness is a quality metric, not a boolean | Phase-5 eval: score classifier output vs golden labels on the Freshdesk export |
| Extraction returns *accurate* order_ref / customer / issue_type | REP-02 | LLM judgment over free-text ticket | Phase-5 eval: field-level accuracy vs golden answer key |
| Self-critique *scores* the draft meaningfully against the rubric | REP-04 | LLM-as-judge quality; deterministic only at the structural/dimension level | Phase-5 eval: critic-score correlation vs reference agent replies |
| Live always-draft run: injection pre-screen fires and attaches advisory hint | SAFE-04 | Requires a live cs-agent-team session; subprocess proves exit code only | `04-VERIFICATION.md` live check: run team with INJECTION_TICKET live, confirm advisory `escalation_hint` attached + action="draft" |
| Live always-draft run: high-risk ticket drafts with advisory hint | SAFE-03 | Requires `use_live_claude=True`; advisory hint is LLM-pipeline output | `04-VERIFICATION.md` live check: run `cs_team_demo.py` with HIGH_RISK_TICKET live, confirm `action="draft"` + non-null `escalation_hint` |

---

## Validation Sign-Off

- [x] All enforceable behaviors have automated verify (incl. deployed-surface subprocess proofs)
- [x] Sampling continuity: no 3 consecutive enforceable behaviors without automated verify
- [x] Wave 0 covers all MISSING references (none outstanding)
- [x] No watch-mode flags
- [x] Feedback latency < 70s
- [x] LLM-quality dimensions explicitly recorded as Manual-Only and deferred to Phase-5 eval (SAFE-01/02)
- [x] `nyquist_compliant: true` set in frontmatter (enforceable contract fully sampled by rewritten suite)
- [x] All deleted-function references removed (stateful-veto subprocess tests, escalate=no-draft
  e2e tests, and guard-hook subprocess proofs removed from prior version in plan 04-04)
- [x] Commands updated to `uv run pytest tests/cs_team`

**Approval:** re-approved 2026-06-05 (post 04-04 always-draft test cleanup)
