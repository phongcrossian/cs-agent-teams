---
phase: 08-ticket-re-classification-fd-property-write-back
plan: "03"
subsystem: harness-prompt-builders
tags: [enum-injection, prompt-engineering, fd-classification, tdd, gap-closure]

dependency_graph:
  requires: ["08-01", "08-02"]
  provides: ["enum-constrained classify/draft prompts for Rootcause/Flow/Section_Flow"]
  affects: ["scripts/test_tickets_run.py", "scripts/test_test_tickets_run.py"]

tech_stack:
  added: []
  patterns:
    - "field_choices() read at prompt-build time — no hard-coded enum literals"
    - "_fd_enum_constraint_block() helper mirrors existing ALLOWED TEMPLATE CODES pattern"
    - "TDD RED/GREEN discipline: 3 failing tests committed before fix"

key_files:
  created: []
  modified:
    - scripts/test_tickets_run.py
    - scripts/test_test_tickets_run.py

decisions:
  - "_fd_enum_constraint_block() is a module-level helper (not inline) so both builders share identical block text"
  - "Enum lists sourced from field_choices() at call time — editing the snapshot changes the prompt with no code change"
  - "Test C uses 'System_limitation' (not the first value 'Shipping') to avoid false positives from coincidental substring matches in prompt template text"
  - "_SUBTYPE_TEMPLATES and template_code injection left entirely untouched (blocking anti-pattern from 08-CONTEXT)"
  - "section_flow slot added explicitly to _build_draft_prompt2 JSON schema (model can now fill it; assembler fallback still present)"

metrics:
  duration: "~10 minutes"
  completed: "2026-06-08T02:39:27Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  tests_added: 3
  tests_total_after: 102
---

# Phase 08 Plan 03: Enum Injection for Rootcause/Flow/Section_Flow — Summary

**One-liner:** Inject `field_choices()`-sourced verbatim-enum constraint block into both prompt builders, closing SC#2 PARTIAL gap so AI picks valid Rootcause/Flow/Section_Flow enum values.

---

## What Was Built

Closed the SC#2 gap identified in 08-VERIFICATION.md: the AI was emitting free-text for Rootcause, Flow, and Section_Flow because the prompt builders gave open-ended slots with no enum constraint. The fix follows the same pattern already used for `template_code` (the ALLOWED TEMPLATE CODES BY SUB-TYPE block).

**`_fd_enum_constraint_block()` (new helper in `scripts/test_tickets_run.py`)**

Reads `field_choices("Rootcause")`, `field_choices("Flow")`, `field_choices("Section_Flow")` at call time and renders a HARD-CONSTRAINT instruction block:

```
ALLOWED FD CLASSIFICATION ENUM VALUES (verbatim-enum discipline — 08-CONTEXT VERB-01):
For each of the following fields, you MUST choose a value VERBATIM from its allowed list.
If none of the allowed values fits, leave the field empty (""). NEVER invent, paraphrase,
or free-pick a value — the validator will flag any non-verbatim value as 'invalid'.

  Rootcause: Shipping, Fulfillment, Product, Content, Customer, Undefined, NA, Policy,
             System_error, Transaction, Agent_error, Supplier, Other, System_limitation
  Flow: REPLACEMENT_DEFINE, CANCEL_IN_POLICY, ...
  Section_Flow: BRA_SIZING, DRESS_SIZING, ...
```

**Injection points:**

- `_build_classify_prompt`: enum block injected before `<ticket_metadata>` so Pass-1 is enum-aware
- `_build_draft_prompt2`: enum block injected before JSON schema; `flow`/`rootcause`/`section_flow` slots updated to reference "pick VERBATIM from ALLOWED list above, else empty"; `section_flow` slot added explicitly

**Import added:**
`from src.file_store.ticket_fields_store import field_choices` in `scripts/test_tickets_run.py`

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED — offline tests assert enum injection | f6eb6f4 | scripts/test_test_tickets_run.py |
| 2 | GREEN — inject allowed enum into both builders | c6c2d7d | scripts/test_tickets_run.py |

---

## Test Results

| Suite | Before | After |
|-------|--------|-------|
| Harness tests (scripts/test_test_tickets_run.py) | 27 pass | 30 pass (+3 new) |
| Loader tests (tests/test_ticket_fields_store.py) | 31 pass | 31 pass |
| Validator tests (tests/test_fd_classification.py) | 41 pass | 41 pass |
| **Total** | **99** | **102** |

3 new tests added (all in `test_test_tickets_run.py`):
- `test_classify_prompt_enum_injection` — asserts all Rootcause/Flow/Section_Flow values in classify prompt
- `test_draft_prompt2_enum_injection` — asserts all Rootcause/Flow/Section_Flow values in draft prompt
- `test_verbatim_enum_loader_sourced` — asserts "System_limitation" (snapshot-unique value) proves loader-sourced injection

---

## Deviations from Plan

**1. [Rule 1 - Bug fix] Test C false-positive with first Rootcause value**

- **Found during:** Task 1 (RED verification)
- **Issue:** Test C initially sampled `rootcause_values[0]` which is "Shipping". "Shipping" was already present in the prompt template text (as a substring of "Change_Shipping_Address") — so the test passed even without the fix, giving a false RED.
- **Fix:** Changed Test C to use `"System_limitation"` — a value in the Rootcause snapshot enum that does not appear as a substring anywhere in the existing prompt template strings. Confirmed it was absent from the un-fixed prompt before committing.
- **Files modified:** `scripts/test_test_tickets_run.py`
- **Commit:** f6eb6f4

No other deviations. Plan executed exactly as written in all other respects.

---

## Verification Gates Passed

| Gate | Command | Result |
|------|---------|--------|
| 3 new tests pass | `pytest scripts/test_test_tickets_run.py -k "enum_injection or verbatim_enum" -q` | 3 passed |
| Full suite (102 tests) | `pytest scripts/test_test_tickets_run.py tests/test_ticket_fields_store.py tests/test_fd_classification.py -q` | 102 passed |
| No PUT/write path | `grep -nE "PUT|\.put\(|api/v2/tickets/.*reply" scripts/test_tickets_run.py` | empty (OK) |
| Loader-sourced (not literals) | `grep -v '^#' scripts/test_tickets_run.py | grep -c 'field_choices'` | 3 occurrences |

---

## Known Stubs

None. The enum block is fully wired via `field_choices()`. No placeholder text.

---

## Threat Flags

No new security-relevant surface introduced. This plan adds prompt text only — no network endpoint, no write path, no new schema. Threat register analysis (T-08-03-01 through T-08-03-SC) all MITIGATED or N/A per plan.

---

## What Remains (Manual Smoke)

A live smoke run is required to confirm SC#2 moves PARTIAL → VERIFIED in the phase verifier:

```
.venv/bin/python scripts/test_tickets_run.py collect --id <prod_ticket_id>
```

Open `test-tickets.xlsx`, FD re-classification section — Rootcause/Flow/Section_Flow should now show ✓ ("valid") instead of ✗ ("invalid") free-text. This requires `.env.prd` and the claude CLI.

---

## Self-Check: PASSED

Files exist:
- `scripts/test_tickets_run.py` — FOUND (modified)
- `scripts/test_test_tickets_run.py` — FOUND (modified)

Commits exist:
- `f6eb6f4` — FOUND (test(08-03): add failing tests for Rootcause/Flow/Section_Flow enum injection)
- `c6c2d7d` — FOUND (feat(08-03): inject Rootcause/Flow/Section_Flow allowed enum into classify+draft prompts)
