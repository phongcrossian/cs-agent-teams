---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "07"
subsystem: classifier
tags: [classifier, sub-type, taxonomy, haiku, contract-test]
dependency_graph:
  requires: ["04-02"]
  provides: ["customer_request sub-type in classifier output"]
  affects: ["04-08 escalation_gate operational-action trigger", "04-09 pre_send_guard authorized-offer check", "04-10 drafter template selection"]
tech_stack:
  added: []
  patterns: ["additive JSON field", "fail-closed null emission", "structural contract test"]
key_files:
  created:
    - tests/cs_team/test_classifier_subtype_contract.py
  modified:
    - .claude/agents/classifier.md
    - .claude/skills/classify-ticket/SKILL.md
decisions:
  - "customer_request is additive after category in the output JSON — downstream consumers read it by name, not position; no breaking change"
  - "Fail-closed rule: unknown sub-type → null + confidence:low → escalates; never guesses"
  - "Review sub-type always escalates (no template in Phase 1 COVERAGE-MAP); labelled explicitly so the gate can apply the correct rule"
  - "change_request macro-category added to Level-1 taxonomy table in classifier.md (was previously implicit)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-03"
  tasks: 2
  files: 3
---

# Phase 04 Plan 07: Classifier Level-2 Sub-Type Extension Summary

**One-liner:** Classifier now emits a fixed 13-value `customer_request` sub-type (RULES §2 enum) alongside existing fields, making the per-sub-type rule table addressable by downstream guards — Haiku preserved, additive schema, CI-gated.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add customer_request sub-type to classifier agent + skill | 950152e | `.claude/agents/classifier.md`, `.claude/skills/classify-ticket/SKILL.md` |
| 2 | Structural contract test for the sub-type schema | d1f2fb8 | `tests/cs_team/test_classifier_subtype_contract.py` |

---

## What Was Built

### Task 1 — Classifier + Skill extension

**`.claude/agents/classifier.md`** — extended with:
- New "Level-2 — Customer_Request sub-type" section documenting the fixed 13-value enum
- Macro-category → sub-type grouping table (product_complaint/return_request → Return/Replace/Partial_Refund/Full_Refund/Review; cancellation_request → Cancel_Order; change_request → Change_Shipping_Address/Change_Product_Variant; order_status → Ask_About_Delivery_Status/Ask_About_Order; general_inquiry → Ask_About_Policy/Ask_About_Product/Ask_About_Promotion)
- Fail-closed rule: `customer_request: null` + `confidence: low` when sub-type cannot be confidently determined
- `change_request` added to the Level-1 macro-category table (was previously absent)
- `"customer_request"` field added to the Output Format JSON, positioned after `category`
- All 13 sub-type values enumerated in the Output Format doc block
- Model stays `claude-haiku-4-5` (D-03); no drafting behavior added

**`.claude/skills/classify-ticket/SKILL.md`** — extended with:
- New "Level-2 Customer_Request Sub-Type" section with full 13-value table grouped by macro-category
- Per-sub-type selection guidance (key signals for each value)
- Fail-closed rule documented
- `"customer_request"` added to the Output JSON block with null semantics

### Task 2 — Structural contract test

**`tests/cs_team/test_classifier_subtype_contract.py`** (19 tests, all green):
- Parametrized test: each of the 13 RULES §2 sub-types appears verbatim in classifier.md
- `customer_request` field present in classifier.md
- `model: claude-haiku-4-5` declared (D-03 gate)
- No `opus` reference in classifier.md (D-03 hot-path guard)
- `customer_request` field present in classify-ticket/SKILL.md
- Fail-closed rule documented in classifier.md
- Module-level enum constant sanity check (exactly 13 values)

---

## Verification

```
.venv/bin/pytest tests/cs_team/test_classifier_subtype_contract.py -q
19 passed in 0.41s

grep -c "model: claude-haiku-4-5" .claude/agents/classifier.md  → 1
grep -c "opus" .claude/agents/classifier.md                      → 0
```

All acceptance criteria met:
- All 13 sub-types in classifier.md: PASS
- `customer_request` in both files: PASS (3 occurrences in classifier.md, 4 in SKILL.md)
- Haiku preserved, no opus: PASS
- Fail-closed rule present: PASS (2 matching lines)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Added `change_request` to Level-1 taxonomy table**
- **Found during:** Task 1
- **Issue:** The Level-1 macro-category table in `classifier.md` did not include `change_request`, but the RULES §2 sub-types `Change_Shipping_Address` and `Change_Product_Variant` map to it. Without the entry, the table was incomplete and the sub-type grouping had a dangling reference.
- **Fix:** Added `change_request` row to the Level-1 table in `classifier.md` with description "Change shipping address, product variant, or other order details".
- **Files modified:** `.claude/agents/classifier.md`
- **Commit:** 950152e

No other deviations — plan executed as written.

---

## Known Stubs

None. The classifier agent is a prompt-document (not executable); the sub-type field is fully specified with all 13 values enumerated, the fail-closed rule, and the macro-category grouping. No placeholder text or empty data sources.

---

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The classifier.md and SKILL.md are prompt documents only. The contract test makes no network calls. Threat model (T-04-07-01/T-04-07-02) addressed:

- **T-04-07-01 (Tampering):** sub-type is a label only; escalation_gate (04-08) + injection_screen still gate downstream — classifier labelling cannot bypass the guard chain.
- **T-04-07-02 (Repudiation):** fail-closed rule documented and contract-tested: unknown → null + confidence:low → escalate.

---

## Self-Check: PASSED

- `.claude/agents/classifier.md` — exists, contains `customer_request`, all 13 sub-types, `model: claude-haiku-4-5`, no `opus`
- `.claude/skills/classify-ticket/SKILL.md` — exists, contains `customer_request`
- `tests/cs_team/test_classifier_subtype_contract.py` — exists, 19 tests green
- Commits 950152e and d1f2fb8 — both present in git log
