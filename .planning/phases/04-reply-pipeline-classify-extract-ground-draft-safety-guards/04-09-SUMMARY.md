---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "09"
subsystem: safety-guards
tags: [pre_send_guard, d26, safe-04, authorized-offer, tdd, hooks, deterministic]
dependency_graph:
  requires: ["04-05", "04-06"]
  provides: ["pre_send_guard.D-26-authorized-offer-test"]
  affects: ["04-10-drafter", "04-11-eligibility"]
tech_stack:
  added: []
  patterns: ["importlib absolute-path module load", "tripwire + offer-block dual-path guard", "TDD RED/GREEN"]
key_files:
  created:
    - tests/cs_team/test_pre_send_guard_authorized.py
  modified:
    - .claude/hooks/pre_send_guard.py
decisions:
  - "D-26 supersedes D-13: block-all replaced by authorized/unauthorized offer test delegating to authorize_offer"
  - "Commitment-term lexicon demoted from blocker to tripwire: commitment term with no offer block → exit 2; with authorized offer → exit 0"
  - "authorize_offer imported via importlib.util.spec_from_file_location (absolute path) — no sys.path manipulation needed when hook runs as uv run python .claude/hooks/pre_send_guard.py"
  - "Offer sub_type is required; missing key → KeyError → outer except → exit 2 (fail-closed)"
  - "Pure-informational replies (no commitment term, no offer block) unconditionally exit 0"
metrics:
  duration_minutes: 4
  completed_date: "2026-06-03"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 04 Plan 09: Pre-Send Guard D-26 Authorized-Offer Rework Summary

**One-liner:** Replaced block-all D-13 commitment guard in `pre_send_guard.py` with the D-26 §0 authorized/unauthorized test by delegating to `authorize_offer` (from 04-06), allowing in-policy templated offers (exit 0) while blocking every unauthorized axis (exit 2), with a 12-test subprocess proof suite.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing test suite for D-26 guard | 7424fb8 | tests/cs_team/test_pre_send_guard_authorized.py |
| 1 | Rework pre_send_guard to authorized-offer test | ae41579 | .claude/hooks/pre_send_guard.py |
| 2 | Subprocess exit-code proof suite | (included in RED commit 7424fb8) | tests/cs_team/test_pre_send_guard_authorized.py |

## What Was Built

### `.claude/hooks/pre_send_guard.py` (reworked)

D-26 §0 authorized-offer guard replacing the block-all D-13 guard:

**Module-load pattern:**
- `authorize_offer` and `default_eligibility` imported via `importlib.util.spec_from_file_location` using the sibling module's absolute path. Works correctly when invoked as `uv run python .claude/hooks/pre_send_guard.py` without sys.path manipulation.

**Commitment-term lexicon (retained as tripwire):**
- Same 4 patterns as D-13 (refund/reimburse, credit/coupon/voucher, charge/debit/payment, replace/exchange/swap)
- Role changed: tripwire only — if body has commitment term AND no offer block → exit 2 (`unauthorized:commitment_without_offer`)

**New helpers:**
- `_extract_offer(payload)` — reads `tool_input["offer"]` from the drafter-supplied payload
- `_has_commitment_term(body)` — tripwire check against `_COMMITMENT_PATTERNS`
- `_block(reason)` — prints escalate JSON and exits 2

**Decision flow in `main()`:**
1. Parse stdin JSON (fail-closed on error → exit 2)
2. Extract body + offer block
3. If offer block present: call `authorize_offer(sub_type, template_code, offered, eligibility, asserts_mutation)` → exit 2 on UNAUTHORIZED, exit 0 on AUTHORIZED
4. If no offer and commitment term in body → exit 2 (tripwire)
5. If no offer and no commitment term → exit 0 (pure informational)

**Preserved invariants:**
- NEVER auto-strips body (no `.replace()` / `re.sub()` calls — grep proves 0)
- submit_reply remains the sole emission path (§4a unchanged)
- Fail-closed: missing `sub_type` key → `KeyError` → outer except → exit 2
- D-26 documented in module docstring

### `tests/cs_team/test_pre_send_guard_authorized.py` (created)

12-test subprocess proof suite covering all 10 unauthorized axes + 2 authorized contracts:

| # | Test | Expected |
|---|------|----------|
| 1 | Authorized B7 Partial_Refund (50% + 40%) | exit 0 |
| 2 | Pure informational body | exit 0 |
| 3 | Over-threshold (70% refund, cap=50%) | exit 2 |
| 4 | Out-of-template (code X999) | exit 2 |
| 5 | Ineligible (in_warranty=False) | exit 2 |
| 6 | Second-remediation (prior_remediation=True) | exit 2 |
| 7 | Operational assertion (asserts_mutation=True) | exit 2 |
| 8 | Review force-escalate | exit 2 |
| 9 | Commitment term, no offer block (refund) | exit 2 |
| 10 | Commitment term, no offer block (replace) | exit 2 |
| 11 | Malformed stdin | exit 2 |
| 12 | Offer missing required sub_type key | exit 2 |

## Deviations from Plan

None — plan executed exactly as written.

The test file was created in the RED phase commit (`7424fb8`) and served as both the RED-phase proof of test failure AND the Task 2 proof suite after the guard implementation (GREEN). No separate Task 2 commit was needed because the file was already committed and the tests passed GREEN without modification.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (failing tests) | 7424fb8 | PASS — 3 tests confirmed current block-all guard: authorized B7 blocked (exit 2 not 0), operational-assertion not checked (exit 0 not 2), Review not checked (exit 0 not 2) |
| GREEN (implementation) | ae41579 | PASS — all 12 tests pass; plan verify assertions PASS |

## Verification Results

```
=== Acceptance criteria ===
authorize_offer calls in guard:    10  (≥ 2 ✓)
exit-2 paths in guard:              2  (≥ 2 ✓)
exit-0 paths in guard:              2  (≥ 1 ✓)
no auto-strip (.replace/re.sub):    0  (= 0 ✓)
D-26 documented:                    4  (≥ 1 ✓)

=== Inline exit-code checks ===
auth=0  (authorized B7 offer)    ✓
over=2  (70% refund)             ✓
nooffer=2 (commitment-no-offer)  ✓

=== Test suites ===
test_pre_send_guard_authorized.py: 12 passed (≥ 10 ✓, exit-0 asserts=2 ✓, exit-2 asserts=10 ✓)
test_hooks_subprocess.py:          21 passed (no regression ✓)
total: 33 passed in 1.52s
```

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The guard remains deterministic, stdlib-only, and LLM-free. All plan threat mitigations implemented:

| Threat ID | Mitigation | Verified |
|-----------|------------|---------|
| T-04-09-01 | authorize_offer numeric + registry check → exit 2 on over-threshold/out-of-template | test_over_threshold_refund_70_exits_2, test_out_of_template_unknown_code_exits_2 |
| T-04-09-02 | Commitment-term tripwire requires authorized offer block, else exit 2 | test_commitment_without_offer_block_exits_2, test_replace_commitment_without_offer_block_exits_2 |
| T-04-09-03 | asserts_mutation=True → operational_assertion → exit 2 | test_operational_assertion_exits_2 |
| T-04-09-04 | Missing sub_type key → KeyError → outer except → exit 2 | test_offer_missing_required_key_exits_2 |
| T-04-09-05 | No .replace/re.sub in codebase (grep proof: 0) | grep -ciE "\.replace\(|re\.sub\(" returns 0 |

## Known Stubs

None introduced in this plan. The eligibility stub (`default_eligibility()`) is in `authorized_offer.py` (plan 04-06), not in `pre_send_guard.py`. Plan 04-11 replaces it with real Selless-grounded eligibility data.

## Self-Check: PASSED

- `.claude/hooks/pre_send_guard.py` exists: FOUND
- `tests/cs_team/test_pre_send_guard_authorized.py` exists: FOUND
- Commits 7424fb8, ae41579: FOUND in git log
- 33 tests pass (12 new + 21 existing), 0 failures
