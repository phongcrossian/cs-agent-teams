---
phase: 04
slug: reply-pipeline-classify-extract-ground-draft-safety-guards
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-03
---

# Phase 04 — Validation Strategy

> Per-phase validation contract. The **enforceable / deterministic** behavior of this phase
> (the safety chokepoint) is fully covered by automated tests — including real **subprocess**
> tests that exercise the deployed exit-code contract, not just in-process logic. The remaining
> requirement dimensions are **LLM output quality** (classification accuracy, extraction accuracy,
> critique scoring), which are non-deterministic by nature and are deferred — by design — to the
> Phase-5 offline-eval harness (SAFE-01/SAFE-02). They are recorded as Manual-Only here, not as
> coverage gaps.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (+ stdlib `subprocess` for deployed-hook proofs) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/cs_team -q` |
| **Full suite command** | `.venv/bin/pytest -q` |
| **Estimated runtime** | ~70 seconds (full) / ~10 seconds (cs_team subset) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/cs_team -q`
- **After every plan wave:** Run `.venv/bin/pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green (last run: 287 passed, 10 skipped, 0 failed)
- **Max feedback latency:** ~70 seconds

---

## Per-Task Verification Map

| Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File | Status |
|-------------|------------|-----------------|-----------|-------------------|------|--------|
| **REP-03** (no ungrounded claims) | T-04-01-04 / T-04-04-02/03 | Draft missing/unknown citation → grounding_check exit 2 → escalate | unit + **subprocess** | `.venv/bin/pytest tests/cs_team/test_hooks_subprocess.py -q` | `test_hooks_subprocess.py` (ungrounded/empty-citation/unknown-id → returncode==2), `test_hooks.py` (D-11 block) | ✅ green |
| **SAFE-03** (route high-risk → human) | T-04-01-03 / T-04-05-01/02 | Accumulated risk signal at submit_reply → escalation_gate exit 2; missing run-state → fail-closed exit 2 | unit + **subprocess** | `.venv/bin/pytest tests/cs_team/test_hooks_subprocess.py -q` | `test_hooks_subprocess.py` (`test_write_high_risk_then_submit_reply_returns_2`, `test_no_state_file_returns_2`, `test_cs_run_id_unset_returns_2`), `test_hooks.py` (D-08) | ✅ green |
| **SAFE-04** (block commitment language + injection) | T-04-01-01/02 / T-04-04-01/04 | Commitment language or injection in draft/body → pre_send_guard / injection_screen non-zero (block) | unit + **subprocess** | `.venv/bin/pytest tests/cs_team/test_hooks_subprocess.py -q` | `test_hooks_subprocess.py` (`test_commitment_language_returns_2`, `*_override_returns_nonzero`, `test_missing_body_field_returns_nonzero`), `test_hooks.py` (D-13/D-14) | ✅ green |
| **REP-01** (routing: classify → escalate vs draft) | T-04-03-04/05 | Benign→draft, high-risk→escalate, injection→escalate through the bound chain (mock LLM, deterministic) | e2e (mock LLM) | `.venv/bin/pytest tests/cs_team/test_e2e_dry_run.py -q` | `test_e2e_dry_run.py` (`test_benign_ticket_produces_draft`, `test_high_risk_ticket_escalates`, `test_injection_ticket_escalates`) | ✅ green |
| **REP-01/02/03/04** (agent + skill structure, model discipline) | T-04-02-05 / T-04-00-03/04 | Correct agents/skills exist; Haiku on classify/extract, Sonnet on draft/critic/lead, no Opus; chokepoint bindings present | structural | `.venv/bin/pytest tests/cs_team/test_team_definitions.py tests/cs_team/test_settings_hook_bindings.py -q` | `test_team_definitions.py`, `test_settings_hook_bindings.py` | ✅ green |
| **REP-04** (self-critique rubric dimensions defined) | — | Critic agent + self-critique skill declare faithfulness / policy-match / tone-completeness dimensions | structural | `.venv/bin/pytest tests/cs_team/test_team_definitions.py -q` | `test_team_definitions.py` (`test_self_critique_skill_*_dimension`) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all automatable phase requirements. The Phase-04 Wave-0 bootstrap
(`04-00`) already installed the cs_team test package, fixtures (`conftest.py`,
`tests/fixtures/sample_tickets.py`), and the subprocess proof harness was added in `04-05`/review.
No additional Wave-0 test scaffolding required.

---

## Manual-Only Verifications

These dimensions are **LLM output quality** — non-deterministic and not unit-testable without
asserting on live model output (which would produce flaky tests). They are deferred to the
**Phase-5 offline-eval harness** (SAFE-01 golden-dataset scoring, SAFE-02 go-live quality gate),
and to the two live-Claude-session human checks recorded in `04-VERIFICATION.md`.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Classification assigns the *correct* support category | REP-01 | LLM judgment; correctness is a quality metric, not a boolean | Phase-5 eval: score classifier output vs golden labels on the Freshdesk export |
| Extraction returns *accurate* order_ref / customer / issue_type | REP-02 | LLM judgment over free-text ticket | Phase-5 eval: field-level accuracy vs golden answer key |
| Self-critique *scores* the draft meaningfully against the rubric | REP-04 | LLM-as-judge quality; deterministic only at the structural/dimension level | Phase-5 eval: critic-score correlation vs reference agent replies (Ragas/DeepEval) |
| Live stateful veto blocks `submit_reply` on the real Claude Code runtime | SAFE-03 | Requires a live cs-agent-team session; subprocess proves exit code, not the runtime binding firing | `04-VERIFICATION.md` live check #1: run team with a high-risk ticket, confirm runtime blocks submit_reply |
| Live runner injection pre-screen reaches the real subagent surface | SAFE-04 | Requires `use_live_claude=True`; no SubagentStart event exists, so the runner pre-screen is the enforced path | `04-VERIFICATION.md` live check #2: run `cs_team_demo.py` live with INJECTION_TICKET, confirm no subagent sees unscreened body |

---

## Validation Sign-Off

- [x] All enforceable behaviors have automated verify (incl. deployed-surface subprocess proofs)
- [x] Sampling continuity: no 3 consecutive enforceable behaviors without automated verify
- [x] Wave 0 covers all MISSING references (none outstanding)
- [x] No watch-mode flags
- [x] Feedback latency < 70s
- [x] LLM-quality dimensions explicitly recorded as Manual-Only and deferred to Phase-5 eval (SAFE-01/02)
- [x] `nyquist_compliant: true` set in frontmatter (enforceable contract fully sampled)

**Approval:** approved 2026-06-03
