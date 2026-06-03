---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "08"
subsystem: safety-guards
tags: [escalation-gate, operational-action, rulesbased-guard, tdd]
dependency_graph:
  requires: ["04-05", "04-07"]
  provides: ["escalation-gate-operational-action-signal"]
  affects: [".claude/hooks/escalation_gate.py"]
tech_stack:
  added: []
  patterns: ["OR-gate signal extension", "fail-closed derivation", "subprocess hook testing"]
key_files:
  created:
    - tests/cs_team/test_escalation_gate_operational.py
  modified:
    - .claude/hooks/escalation_gate.py
decisions:
  - "operational_action placed after the five base signals in _SIGNAL_ORDER so existing reasons take first-match precedence (additive per D-08)"
  - "_MUTATION_ASSERTING_SUBTYPES frozenset centralizes the §1 change_request sub-type list for easy audit"
  - "_derive_operational_action + _iter_payload_sources extracted as named helpers (not inlined) to keep _derive_signals readable"
  - "change_request sub-type without asserts_mutation=False treated as escalate (fail-closed §1 execution boundary)"
metrics:
  duration: "10m"
  completed: "2026-06-03"
  tasks_completed: 2
  files_modified: 2
---

# Phase 04 Plan 08: Escalation Gate Operational-Action Signal Summary

**One-liner:** `operational_action` signal added to escalation_gate.py OR-gate so Review, Full_Refund, and asserting change_request sub-types escalate deterministically without weakening any prior trigger.

## What Was Built

### Task 1 — Add operational_action signal to the OR-gate (feat)

Extended `.claude/hooks/escalation_gate.py`:

- Appended `("operational_action", "escalate:operational_action")` to `_SIGNAL_ORDER` after the five existing signals. First-match precedence preserved — base signals still win when both are True.
- Added `_MUTATION_ASSERTING_SUBTYPES` frozenset: `{Change_Shipping_Address, Change_Product_Variant, Change_Non_Shipping_Address, Express_Line}` — the §1 execution-boundary sub-types.
- Added `_derive_operational_action(payload, signals)` (mutates signals in place):
  - Rule 1: `customer_request ∈ {Review, Full_Refund}` → `operational_action = True`
  - Rule 2: `asserts_mutation` truthy → `operational_action = True` (RD-Q1)
  - Rule 3: `customer_request ∈ _MUTATION_ASSERTING_SUBTYPES` AND `asserts_mutation` is not explicitly `False` → `operational_action = True` (fail-closed §1 boundary)
- Added `_iter_payload_sources(payload)` helper to scan top-level and nested `tool_result/result/output` containers — consistent with existing `_derive_signals` nesting logic.
- Wired `_derive_operational_action` into `_derive_signals` fallback path.
- All five original signals, dual-context exit-code, fail-closed, and `_SAFE_RUN_ID` guard untouched.

### Task 2 — Subprocess + derivation tests (test)

Created `tests/cs_team/test_escalation_gate_operational.py` (11 tests, all pass):

| Test class | Coverage |
|---|---|
| `TestOperationalActionReviewSubprocess` | Review → exit-2; Full_Refund → exit-2 |
| `TestOperationalActionAssertsMutationSubprocess` | asserts_mutation=True → exit-2; change_request sub-type no explicit False → exit-2 |
| `TestExistingSignalRegressionSubprocess` | high_risk_category still blocks (T-04-08-02 regression guard) |
| `TestCleanSignalsSubprocess` | all-False + Ask_About_Order + asserts_mutation=False → exit-0 |
| `TestShouldEscalatePrecedenceUnit` | Unit: precedence, all-False clean, six signals in _SIGNAL_ORDER, operational_action at index 5 |

## Verification Evidence

```
uv run pytest tests/cs_team/test_escalation_gate_operational.py -q
11 passed in 1.01s

grep -c "operational_action" .claude/hooks/escalation_gate.py  → 10  (≥ 2 required)
grep -oE "low_confidence|..." | sort -u | wc -l              → 5   (all 5 base keys present)
grep -c "sys.exit(2)" .claude/hooks/escalation_gate.py       → 3   (≥ 2 required)
```

## Decisions Made

1. **operational_action at position 5 (last) in _SIGNAL_ORDER** — base signals (low_confidence, high_risk_category, conflict, stale_only, missing_key) take first-match precedence. The new signal is additive and never displaces existing escalation reasons.
2. **`_MUTATION_ASSERTING_SUBTYPES` frozenset** — centralizes the §1 change_request sub-type list so it can be audited and extended without touching derivation logic.
3. **fail-closed for change_request sub-type without `asserts_mutation=False`** — if the upstream stage does not explicitly confirm no mutation was asserted, the gate defaults to escalate. This mirrors the overall fail-closed design (D-08).
4. **`_derive_operational_action` as named helper** — keeps `_derive_signals` focused on nesting-path resolution; derivation logic is separately readable and testable.

## Deviations from Plan

None — plan executed exactly as written. The two helpers (`_derive_operational_action`, `_iter_payload_sources`) are implementation detail of the single `_derive_signals` extension described in the plan's `<action>` block, not architectural additions.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The hook reads from `${TMPDIR}/cs_run_state/<CS_RUN_ID>.json` — same state-file pattern already audited in 04-04/04-05. `_SAFE_RUN_ID` guard untouched (T-04-08-03 mitigated).

## Self-Check: PASSED

- `.claude/hooks/escalation_gate.py` exists: FOUND
- `tests/cs_team/test_escalation_gate_operational.py` exists: FOUND
- Task 1 commit `f276837` exists: FOUND
- Task 2 commit `ceeb870` exists: FOUND
- 11 tests pass: VERIFIED
