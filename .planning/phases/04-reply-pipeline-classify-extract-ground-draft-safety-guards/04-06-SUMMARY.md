---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "06"
subsystem: safety-guards
tags: [authorized-offer, d26, safe-04, deterministic, tdd, hooks]
dependency_graph:
  requires: ["04-01", "04-05"]
  provides: ["authorized_offer.authorize_offer", "TEMPLATE_REGISTRY", "THRESHOLD_CAPS"]
  affects: ["04-09-pre_send_guard", "04-10-drafter", "04-11-eligibility"]
tech_stack:
  added: []
  patterns: ["pure-stdlib module", "module-level literal registries", "(bool, reason) tuple contract", "TDD RED/GREEN/REFACTOR"]
key_files:
  created:
    - .claude/hooks/authorized_offer.py
    - tests/cs_team/test_authorized_offer.py
    - tests/cs_team/test_authorized_offer_red.py
  modified: []
decisions:
  - "TEMPLATE_REGISTRY uses frozenset per sub-type — O(1) membership check, immutable"
  - "Ask_About_Delivery_Status gets G-codes in registry (not empty set) because WISMO can carry THR-08 comp offer when offered dict is non-empty"
  - "§0 gate order: force-escalate → operational_assertion → no_offer → out_of_template → over_threshold → ineligible:warranty → second_remediation → authorized"
  - "default_eligibility() stub returns optimistic defaults (in_warranty=True, prior_remediation=False) so PoC pipeline can draft without live Selless"
  - "Fail-closed on missing eligibility fields: absent in_warranty defaults False (blocks), absent prior_remediation defaults True (blocks)"
metrics:
  duration_minutes: 8
  completed_date: "2026-06-03"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 04 Plan 06: Authorized-Offer Decision Module Summary

**One-liner:** Pure stdlib `authorize_offer(sub_type, template_code, offered, eligibility, asserts_mutation) -> (bool, str)` encoding the §0 AUTHORIZED/UNAUTHORIZED gate with TEMPLATE_REGISTRY (13 sub-types), THRESHOLD_CAPS (THR-05/06/07/08), force-escalate set (Review), and a clearly-marked RD-Q2 eligibility stub.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | RED-phase failing tests | 65746fb | tests/cs_team/test_authorized_offer_red.py |
| 1 | authorized_offer decision module | 7a8aa49 | .claude/hooks/authorized_offer.py |
| 2 | Exhaustive RULES §2 unit tests + WISMO fix | c4861c8 | tests/cs_team/test_authorized_offer.py, .claude/hooks/authorized_offer.py |

## What Was Built

### `.claude/hooks/authorized_offer.py`

Pure Python, stdlib-only, LLM-free module implementing the D-26 guard core:

**Module-level registries:**
- `TEMPLATE_REGISTRY`: 13 sub-type → frozenset of approved template codes derived from CODE-MAP-templates.md. Return={B3,B5..B13,A4..A9,C1}, Replace={A1..A3,B1,B2,G11,G14}, Partial_Refund={B3,B7,A9}, Full_Refund={A4,A5,A9,G15}, Cancel_Order={F1..F23}, Change_*={E-codes}, Ask_About_Delivery_Status={G-codes}, other inquiry=frozenset().
- `THRESHOLD_CAPS`: refund_pct→THR-07(50), discount_pct→THR-05(40), retention_pct→THR-06(20), comp_pct→THR-08(50).
- `FORCE_ESCALATE_SUBTYPES`: {"Review"} — Phase-1 gap, no flow exists (Q2).

**`authorize_offer()` — §0 gate order:**
1. Force-escalate sub-types (Review) → `unauthorized:force_escalate:no_flow`
2. `asserts_mutation=True` → `unauthorized:operational_assertion` (RD-Q1 / §1)
3. Inquiry sub-type + no offer → `authorized:no_offer`
4. `template_code` not in TEMPLATE_REGISTRY → `unauthorized:out_of_template`
5. Any offered pct > cap → `unauthorized:over_threshold:{THR-XX}`
6. `in_warranty` False → `unauthorized:ineligible:warranty`
7. `prior_remediation` True → `unauthorized:second_remediation`
8. All clear → `authorized:{template_code}`

**Stub markers:**
- `# STUB (RD-Q2)`: eligibility consumed at steps 6-7; `default_eligibility()` returns optimistic stub; plan 04-11 replaces with Selless check.
- `# STUB (RD-Q3)`: evidence treated as sufficient this phase (Full_Refund evidence-gating deferred to 04-11).

### `tests/cs_team/test_authorized_offer.py`

46 tests covering all 13 RULES §2 sub-types:
- §2A: Return(5), Replace(4), Partial_Refund(4), Full_Refund(4), Review(3)
- §2B: Cancel_Order(4), Change_Shipping_Address(4), Change_Product_Variant(3)
- §2C: Ask_About_Delivery_Status(3), Ask_About_Order(2), Ask_About_Policy(1), Ask_About_Product(1), Ask_About_Promotion(1)
- Cross-cutting: parametrized inquiry-no-template test (5 sub-types), reason-string determinism (2)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ask_About_Delivery_Status needed G-codes in TEMPLATE_REGISTRY**
- **Found during:** Task 2 test run
- **Issue:** WISMO sub-type had `frozenset()` (empty) in TEMPLATE_REGISTRY. When a late-ship compensation offer (`comp_pct`) was present, `offered` was non-empty so §0(b) did not short-circuit to `authorized:no_offer`. Flow fell through to §0(c) where G5 template code was not in the empty frozenset → `unauthorized:out_of_template` (wrong).
- **Fix:** Added all G-codes (G1-G15, G3.1, G3.2) to `Ask_About_Delivery_Status` registry. When offered is non-empty (compensation case), the G-code template is validated normally; when empty (tracking-only), §0(b) still short-circuits to `authorized:no_offer`.
- **Files modified:** `.claude/hooks/authorized_offer.py`
- **Commit:** c4861c8

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (failing tests) | 65746fb | PASS — 4 tests confirmed FileNotFoundError before implementation |
| GREEN (implementation) | 7a8aa49 | PASS — 4 RED tests pass; plan verify assertions pass |
| GREEN (exhaustive tests) | c4861c8 | PASS — 50 tests pass including WISMO fix |

## Verification Results

```
50 passed in 0.47s  (.venv/bin/python -m pytest tests/cs_team/test_authorized_offer.py tests/cs_team/test_authorized_offer_red.py -q)
Plan verify assertions: PASS
THR IDs present: THR-05 THR-06 THR-07 THR-08
Review occurrences in module: 5
STUB (RD-Q2/Q3) markers: 5
LLM/network imports: 0
```

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. Module is pure stdlib with no I/O. Threat mitigations from plan threat model all implemented:

| Threat ID | Mitigation | Verified |
|-----------|------------|---------|
| T-04-06-01 | TEMPLATE_REGISTRY membership check; unknown code → out_of_template | Yes — test_*_unknown_template_unauthorized |
| T-04-06-02 | THRESHOLD_CAPS numeric ≤ check; reason names THR-xx | Yes — test_*_over_threshold_* |
| T-04-06-03 | asserts_mutation=True → unauthorized:operational_assertion | Yes — test_*_asserts_mutation_unauthorized |
| T-04-06-04 | STUB (RD-Q2) documented; fail-closed field defaults | Yes — STUB markers in code; 04-11 replaces |

## Known Stubs

| Stub | File | Line (approx) | Reason |
|------|------|----------------|--------|
| `default_eligibility()` | .claude/hooks/authorized_offer.py | ~140 | RD-Q2: real Selless eligibility check wired in plan 04-11 |
| `in_warranty` / `prior_remediation` defaults | .claude/hooks/authorized_offer.py | ~250-260 | Fail-closed defaults until Selless data available |
| Evidence gate (Full_Refund) | .claude/hooks/authorized_offer.py | ~265 | RD-Q3: photo/label verification deferred to 04-11 |

These stubs do NOT prevent the plan goal — `authorize_offer` correctly gates authorized vs unauthorized using the stub surface. Plan 04-11 swaps `default_eligibility()` without reshaping the function signature.

## Self-Check: PASSED

- `.claude/hooks/authorized_offer.py` exists: FOUND
- `tests/cs_team/test_authorized_offer.py` exists: FOUND
- `tests/cs_team/test_authorized_offer_red.py` exists: FOUND
- Commits 65746fb, 7a8aa49, c4861c8: FOUND in git log
- 50 tests pass, 0 failures
