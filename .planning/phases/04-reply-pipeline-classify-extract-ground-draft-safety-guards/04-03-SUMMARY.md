---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "03"
subsystem: scripts/demo-runner
tags: [always-draft, d33, d31-file-store, d34-fallback, d14-advisory, d32-guard-cleanup]
dependency_graph:
  requires: ["04-02", "04-00"]
  provides: ["always-draft-runner", "always-draft-contract-tests"]
  affects: ["scripts/cs_team_demo.py", "scripts/test_tickets_run.py", "tests/fixtures/sample_tickets.py"]
tech_stack:
  added: []
  patterns:
    - "File-store grounding via subtype_to_code() + get_template_from_file() (D-31)"
    - "Advisory escalation_hint — injection/high-risk never suppresses draft (D-30/D-33)"
    - "D-34 verify-order/clarify-order-info fallback on missing order_ref"
    - "TDD RED/GREEN pattern for always-draft contract"
key_files:
  created:
    - tests/test_cs_team_demo_always_draft.py
  modified:
    - scripts/cs_team_demo.py
    - scripts/test_tickets_run.py
    - tests/fixtures/sample_tickets.py
decisions:
  - "D-33 always-draft verified end-to-end: all four fixture types yield action=draft"
  - "Injection detection (D-14) now advisory — attaches escalation_hint, never blocks draft"
  - "File-store grounding (D-31) proven by W4 body-match assertion against real B7 template"
  - "D-34 fallback: missing order_ref → verify-order/clarify-order body, no fabricated facts"
  - "Deleted guard references (pre_send_guard/escalation_gate/grounding_check/authorized_offer/CS_RUN_ID) fully removed from scripts/"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-05"
  tasks: 2
  files: 4
---

# Phase 04 Plan 03: Always-Draft Demo Runner + Contract Tests Summary

Reworked `scripts/cs_team_demo.py` from the fail-closed escalate-emitting runner to the always-draft flow grounded on the local file-store (D-31), with advisory injection/high-risk hints (D-33), flow-aware fallback for missing orders (D-34), and a TDD contract test suite asserting the always-draft shape across four fixture types.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rework demo runner + clean test_tickets_run to always-draft | 736eba2 | scripts/cs_team_demo.py, scripts/test_tickets_run.py, tests/fixtures/sample_tickets.py |
| 2 (RED) | Add failing always-draft contract tests | c1c2cd2 | tests/test_cs_team_demo_always_draft.py |
| 2 (GREEN) | Tests pass on Task 1 implementation (30/30) | c1c2cd2 | — |

## What Was Built

### cs_team_demo.py — Always-Draft Runner

- **Deleted guard imports removed (D-32):** `pre_send_guard`, `escalation_gate`, `grounding_check`, `authorized_offer` — none imported or referenced. Only `injection_screen` (D-14) and `pii_redact` (D-04) survive.
- **D-31 file-store grounding:** `_simulate_verdict` now calls `subtype_to_code(sub_type)` → `get_template_from_file(code)` to build a real template-grounded draft body. No KnowledgeMCP, no Voyage, no pgvector.
- **D-33 always-draft verdict:** `_DRAFT_ACTION` is the only outcome. `_parse_verdict` fail-soft fallback returns `{"action":"draft", "escalation_hint": {"reason":"parse_error"}}` — never `escalate=no-draft`.
- **D-14 advisory:** `_pre_screen_ticket` still runs injection detection before any branch; on a hit it attaches `escalation_hint` and continues to draft (D-30 removes the blocking disposition).
- **D-34 fallback:** `_build_missing_order_body` returns a verify-order/clarify-order-info body when `order_ref` is empty/absent. Never fabricates order facts.
- **`_post_screen_draft` removed:** The commitment-language + grounding check on draft bodies is gone (guards deleted by D-32).
- **`CS_RUN_ID`, `_state_file_path`, `_sanitize_ticket_id` removed** from the signature and logic — the escalation_gate veto state pointer is gone.
- **`MISSING_ORDER_TICKET` added** to `_TICKET_MAP` and `--ticket` choices.
- **Unused stdlib imports removed:** `re`, `subprocess`, `tempfile`, `uuid`.

### test_tickets_run.py — Cleaned Validation Harness

- **Imports fixed:** `_post_screen_draft`, `_sanitize_ticket_id`, `_state_file_path` dropped from the cs_team_demo import.
- **`_load_authorize_offer` removed:** Function that `importlib`-loaded the deleted `authorized_offer.py` hook is gone.
- **`run_ai_team` rewritten:** `os.environ["CS_RUN_ID"]` set/pop and state-file cleanup removed; cli_error/injection paths return `{"action":"draft", ..., "escalation_hint": {...}}` never `action:escalate`.
- **`draft()` docstring updated:** Marked as debug shortcut; `collect()` is the D-35 validation path.

### tests/fixtures/sample_tickets.py — Template-Backed Fixtures (W4)

- **BENIGN_TICKET:** Updated to `sub_type=Return`, `order_ref` present, `expected_code="B7"`. Return → B7 is a template-backed sub-type (non-empty code list).
- **HIGH_RISK_TICKET:** Updated to `sub_type=Partial_Refund`, `category=refund`, `expected_code="B7"`. Partial_Refund → B7 is template-backed.
- **INJECTION_TICKET:** Unchanged body (injection patterns still valid); no sub_type added (test doesn't need a body-match assertion for injection).
- **MISSING_ORDER_TICKET (new):** `order_ref=""` — triggers the D-34 verify-order fallback.
- **No Review sub-type** used for BENIGN/HIGH_RISK (W4 guard — Review returns [] → empty body).

### tests/test_cs_team_demo_always_draft.py — Always-Draft Contract Tests

30 tests across 5 test classes:

| Class | Tests | What is asserted |
|-------|-------|-----------------|
| TestAlwaysDraftInvariant | 12 | All 4 fixtures: action=draft, body non-empty, no escalate=no-draft shape |
| TestBenignTicket | 4 | action=draft, escalation_hint=None, body matches real B7 template anchor (W4), ≥1 citation |
| TestHighRiskTicket | 4 | action=draft, escalation_hint.reason="high_risk", advisory-only, body matches B7 (W4) |
| TestInjectionTicket | 4 | action=draft, escalation_hint.reason starts with "injection:", advisory-only, signals.injection=True |
| TestMissingOrderTicket | 4 | action=draft, body references verify/clarify-order, no fabricated ORD-XXXXX pattern (D-34) |
| TestNoReviewSubtype | 2 | BENIGN/HIGH_RISK fixtures do not use Review sub-type (W4 guard) |

**W4 body-match:** the test fetches the real B7 template body via `get_template_from_file("B7")` and asserts the first 10 words appear verbatim in the draft. This proves the simulated body is grounded on real file-store content, not empty or invented.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_simulate_verdict` produced escalate on high-risk category**
- **Found during:** Task 1 (reading current code)
- **Issue:** The existing `_simulate_verdict` returned `{"action": "escalate", ...}` when the ticket category was in `_HIGH_RISK_CATEGORIES` — the retired D-08 behavior.
- **Fix:** Replaced with always-draft path; high-risk category now attaches advisory `escalation_hint` and continues to draft.
- **Files modified:** scripts/cs_team_demo.py
- **Commit:** 736eba2

**2. [Rule 1 - Bug] `_run_via_claude_cli` returned escalate on cli_error/FileNotFoundError**
- **Found during:** Task 1
- **Issue:** Both error paths returned `{"action": "escalate", ...}` — violated D-33.
- **Fix:** Both now return `{"action": "draft", ..., "escalation_hint": {"reason": "cli_error"}}`.
- **Files modified:** scripts/cs_team_demo.py
- **Commit:** 736eba2

**3. [Rule 1 - Bug] `test_tickets_run.py` `run_ai_team` cli_error path returned escalate**
- **Found during:** Task 1 (cleaning test_tickets_run)
- **Issue:** cli_error returned `{"action": "escalate", ...}`.
- **Fix:** Returns always-draft shape with advisory hint.
- **Files modified:** scripts/test_tickets_run.py
- **Commit:** 736eba2

**4. [Rule 2 - Missing Critical Functionality] Unused stdlib imports left in cs_team_demo.py**
- **Found during:** Task 1 post-edit review
- **Issue:** `re`, `subprocess`, `tempfile`, `uuid` were imported but no longer used after removing guard/CS_RUN_ID logic.
- **Fix:** Removed the four unused imports.
- **Files modified:** scripts/cs_team_demo.py
- **Commit:** 736eba2

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED — test commit | c1c2cd2 | test(04-03): add failing always-draft contract tests |
| GREEN — impl commit (pre-existing) | 736eba2 | refactor(04-03): rework demo runner |
| Tests pass | 30/30 in 0.56s | PASSED |

Note: Implementation (Task 1) was committed before the test file (Task 2 RED) per the plan's task ordering (Task 1 first, then Task 2 TDD). The tests were written against the committed implementation and all pass.

## Verification Results

```
$ PYTHONPATH=. .venv/bin/python -m pytest tests/test_cs_team_demo_always_draft.py -x -q
30 passed in 0.56s

$ PYTHONPATH=. .venv/bin/python scripts/cs_team_demo.py --ticket all
[PASS] benign ticket -> action=draft, escalation_hint=None, body from file-store template
[PASS] high-risk ticket (refund) -> action=draft, advisory escalation_hint.reason=high_risk
[PASS] injection ticket -> action=draft, advisory escalation_hint.reason=injection:*
[PASS] missing-order ticket -> action=draft, verify-order/clarify-order flow (D-34)
Summary: 4 passed, 0 failed (DRY_RUN=True, no Freshdesk posts)
```

Acceptance criteria met:
- `grep -in "pre_send_guard|escalation_gate|grounding_check|authorized_offer" scripts/cs_team_demo.py scripts/test_tickets_run.py` — no actual imports (comment-only references)
- `grep -in "CS_RUN_ID" scripts/test_tickets_run.py` — only in docstring comment
- `grep -in "file_store|get_template_from_file" scripts/cs_team_demo.py` — 4 lines
- `grep -in "escalation_hint" scripts/cs_team_demo.py` — multiple lines
- `grep -in "verify-order|clarify-order" scripts/cs_team_demo.py` — multiple lines
- `grep -in "injection_screen" scripts/cs_team_demo.py` — present

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. All changes are in scripts/tests. The DRY_RUN assertion remains in place (D-39). No new threats beyond what the plan's threat model covers.

## Known Stubs

None. The simulated draft body is grounded on the real B7 template body from the local file-store. The verify-order fallback body is a genuine clarification request (no stub data).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| Commit 736eba2 exists | FOUND |
| Commit c1c2cd2 exists | FOUND |
| tests/test_cs_team_demo_always_draft.py exists | FOUND |
| scripts/cs_team_demo.py exists | FOUND |
| pytest 30/30 pass | PASSED |
