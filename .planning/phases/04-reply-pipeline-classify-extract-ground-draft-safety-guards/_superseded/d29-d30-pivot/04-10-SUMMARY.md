---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "10"
subsystem: drafter-agent
tags: [drafter, d26, rd-q1, rd-q2, authorized-offer, template-selection, eligibility-grounding, ground-and-draft]
dependency_graph:
  requires: ["04-06", "04-07", "04-09"]
  provides: ["drafter.D-26-offer-block", "ground-and-draft.sub-type-template-select", "test.drafter-offer-contract"]
  affects: ["04-11-eligibility-wiring"]
tech_stack:
  added: []
  patterns: ["sub-type-keyed template selection", "eligibility-grounded offer block", "D-26 authorized offer model", "RD-Q1 non-assertion rule", "RD-Q2 PoC stub"]
key_files:
  created:
    - tests/cs_team/test_drafter_offer_contract.py
  modified:
    - .claude/agents/drafter.md
    - .claude/skills/ground-and-draft/SKILL.md
decisions:
  - "Drafter now keys get_template on customer_request sub-type (not generic code); mapping table embedded as drafter/skill guidance"
  - "D-26 supersedes D-13: drafter may produce policy-bounded templated offers within THR-05/06/07/08; guard re-validates every offer"
  - "RD-Q1 enforced in drafter prompt: asserts_mutation=false in Phase 4; change_request drafts use non-asserting acknowledgement only"
  - "RD-Q2 eligibility stub: in_warranty=True, prior_remediation=False, variant_in_stock=True — marked STUB, plan 04-11 wires real Selless fields"
  - "Offer block shape (sub_type, template_code, offered{}, eligibility{}, asserts_mutation) is the drafter→guard contract"
metrics:
  duration_minutes: 12
  completed_date: "2026-06-03"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 04 Plan 10: Drafter Rework — Template-Select + Eligibility-Grounded Offers Summary

**One-liner:** Reworked drafter agent and ground-and-draft skill to select templates via Knowledge MCP `get_template` keyed on the classifier's `customer_request` sub-type, ground order eligibility (warranty window, prior-remediation, variant stock) via Selless before any offer using the RD-Q2 PoC stub, and pass a structured `offer` block to `submit_reply` for the D-26 guard to authorize — replacing the old D-13 blanket commitment ban.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rework drafter agent for template-select + eligibility-grounded offers | 17746e8 | .claude/agents/drafter.md |
| 2 | Update ground-and-draft skill + structural contract test | d4ffbba | .claude/skills/ground-and-draft/SKILL.md, tests/cs_team/test_drafter_offer_contract.py |

## What Was Built

### `.claude/agents/drafter.md` (reworked)

**Step 1 — Template Selection by Sub-Type:**
Added a full sub-type → template code mapping table. The drafter now selects the correct template code by matching the classifier's `customer_request` sub-type before calling `get_template(code)`. Covers all 12 sub-types: Return (B5/B6/B7/B3/A-codes/C1), Replace (A1/A2/A3/B1/B2/G11/G14), Partial_Refund (B7/B3/A9), Full_Refund (A4/A5/A9/G15), Review (force-escalate — no template), Cancel_Order (F1–F23 retention), Change_Shipping_Address (E1/E2/E3/E13), Change_Product_Variant (E4–E12), and all Inquiry sub-types.

**Step 2 — Ground Eligibility BEFORE Any Offer (new):**
The drafter now calls `resolve_order` / `get_order_status` before making any offer. Derives three eligibility fields: `in_warranty` (THR-03/04), `prior_remediation`, `variant_in_stock`. All three marked **STUB (RD-Q2)** with explicit notes that plan 04-11 wires real Selless fields. Fail-closed posture documented.

**Step 4 — D-26 Authorized Offer (replaces D-13 ban):**
Replaced the old "Commitment Language Ban (D-13)" step (which contained "absolutely forbidden") with "Authorized Offer (D-26)". The drafter may now produce policy-bounded offers within THR-05/06/07/08 caps. RD-Q1 rule stated explicitly: NEVER assert a completed operational action in Phase 4 (`asserts_mutation=false` always).

**Step 6 — submit_reply with structured offer block:**
Updated the `submit_reply` call to show the full offer block: `{sub_type, template_code, offered{refund_pct, discount_pct, …}, eligibility{in_warranty, prior_remediation, variant_in_stock}, asserts_mutation}`. Informational-reply pattern (empty `offered`) also documented.

### `.claude/skills/ground-and-draft/SKILL.md` (reworked)

- Step 1 updated with the same sub-type → template code mapping table
- New Step 2 "Eligibility Grounding Before Any Offer" with RD-Q2 STUB markers
- "Commitment Language Ban (D-13)" section replaced with "Authorized Offer (D-26)" listing THR-05/06/07/08 caps and unauthorized axes
- RD-Q1 non-assertion rule added
- Step 6 `submit_reply` example now includes the structured offer block

### `tests/cs_team/test_drafter_offer_contract.py` (created)

15 structural tests — no LLM, no network:

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_drafter_declares_sonnet` | `model: claude-sonnet-4-6` present |
| 2 | `test_drafter_contains_no_opus` | `opus` absent |
| 3 | `test_drafter_documents_asserts_mutation` | `asserts_mutation` present |
| 4 | `test_drafter_documents_d26` | `D-26` present |
| 5 | `test_drafter_documents_rd_q2_stub` | `RD-Q2` present |
| 6 | `test_drafter_documents_customer_request` | `customer_request` present |
| 7 | `test_drafter_documents_rd_q1_non_assertion` | RD-Q1 rule present |
| 8 | `test_drafter_no_absolutely_forbidden_blanket_ban` | `absolutely forbidden` absent |
| 9 | `test_drafter_documents_submit_reply_as_sole_path` | `submit_reply` present |
| 10 | `test_drafter_documents_eligibility_grounding` | `eligibility`/`warranty`/`prior_remediation` present |
| 11 | `test_skill_documents_customer_request` | SKILL has `customer_request` |
| 12 | `test_skill_documents_d26` | SKILL has `D-26` |
| 13 | `test_skill_no_old_d13_ban_heading` | `Commitment Language Ban (D-13)` absent from SKILL |
| 14 | `test_skill_documents_offer_block` | SKILL has `asserts_mutation` |
| 15 | `test_skill_documents_rd_q2_stub` | SKILL has `RD-Q2` |

**Result: 15 passed in 0.45s**

## Verification Results

```
=== drafter.md ===
model: claude-sonnet-4-6:     1  (= 1 ✓)
opus references:               0  (= 0 ✓)
asserts_mutation:              4  (≥ 1 ✓)
D-26:                          4  (≥ 1 ✓)
RD-Q2:                         5  (≥ 1 ✓)
customer_request:              6  (≥ 1 ✓)
absolutely forbidden:          0  (= 0 ✓)
submit_reply:                  9  (≥ 1 ✓)

=== ground-and-draft SKILL.md ===
customer_request:              7  (≥ 1 ✓)
D-26:                          3  (≥ 1 ✓)
Commitment Language Ban (D-13): 0  (= 0 ✓)

=== test_drafter_offer_contract.py ===
15 passed in 0.45s  ✓

=== guard verify (automated) ===
bash -c 'grep -q "model: claude-sonnet-4-6" ... && echo ok' → ok ✓

=== related tests (no regression) ===
test_team_kit_structure.py + test_pre_send_guard_authorized.py: 42 passed ✓
```

## Deviations from Plan

**1. [Rule 3 — Pre-existing blocker] test_e2e_dry_run.py collection error**
- **Found during:** Overall verification (regression check)
- **Issue:** `test_e2e_dry_run.py` imports `check_commitment_language` from `pre_send_guard` — an attribute removed in plan 04-09's D-26 rework. This is a pre-existing failure from 04-09 (not caused by 04-10).
- **Fix:** Not fixed in this plan (out-of-scope pre-existing issue). Logged to deferred-items.
- **Impact:** Plan 04-10's tests run cleanly; the regression is pre-existing.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| RD-Q2 eligibility stub (in_warranty=True, prior_remediation=False, variant_in_stock=True) | .claude/agents/drafter.md, .claude/skills/ground-and-draft/SKILL.md | Real warranty dates + prior-remediation state + inventory check not yet exposed as first-class Selless fields — plan 04-11 wires real fields. Optimistic by design for PoC. |

The RD-Q2 stub is intentional and STUB-marked throughout both documents. Plan 04-11 replaces it with fail-closed real Selless field grounding.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. Changes are documentation-only (agent prompt + skill + structural test). All plan threat mitigations implemented:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-04-10-01 | RD-Q1 rule + asserts_mutation=false in drafter + test asserts presence | DONE |
| T-04-10-02 | Guard re-validates via authorize_offer (04-09); drafter stays within THR caps | DONE (guard side) |
| T-04-10-03 | RD-Q2 stub accepted per plan; STUB-marked; 04-11 wires fail-closed real check | ACCEPTED |
| T-04-10-04 | D-11 inline citations + grounding_check still enforced at submit_reply | DONE (unchanged) |

## Self-Check: PASSED

- `.claude/agents/drafter.md` exists: FOUND
- `.claude/skills/ground-and-draft/SKILL.md` exists: FOUND
- `tests/cs_team/test_drafter_offer_contract.py` exists: FOUND
- Commits 17746e8, d4ffbba: FOUND in git log
- 15 drafter contract tests pass
- 42 related tests pass (no regression from plan 04-10 changes)
