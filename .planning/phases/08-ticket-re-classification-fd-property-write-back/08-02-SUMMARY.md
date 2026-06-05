---
phase: 08-ticket-re-classification-fd-property-write-back
plan: "02"
subsystem: harness
tags: [fd-classification, validation, xlsx, side-by-side, advisory, dry-run, tdd, phase-8]
dependency_graph:
  requires:
    - "src/file_store/fd_classification.py (build_fd_property_update, OWNED_FIELDS)"
    - "src/file_store/ticket_fields_store.py (field_choices, customer_requests_for)"
    - "scripts/test_tickets_run.py::_process_row (08-01 harness, _extract_fd_props)"
  provides:
    - "scripts/test_tickets_run.py::_assemble_fd_property_update (category->Level_in adapter)"
    - "scripts/test_tickets_run.py::_fd_field_match (per-field AI vs CS gold comparison)"
    - "scripts/test_tickets_run.py::_process_row (adds fd_property_update + fd_field_match to record)"
    - "scripts/test_tickets_run.py::build_xlsx (FD re-classification section with per-field status + match + N/M summary)"
  affects:
    - "test-tickets.xlsx (new section per ticket sheet)"
    - ".test-tickets-data.jsonl (new keys: fd_property_update, fd_field_match)"
tech_stack:
  added: []
  patterns:
    - "category->Level_in macro map (complaint->Complaint, change_request->Change_Request, inquiry->Inquiry)"
    - "per-field match: True/False/None(no_gold), case-insensitive, owned-field scope only"
    - "build_xlsx section mirroring template_valid ✓/✗ style (status flag inline with AI value)"
    - "graceful legacy-record handling (missing fd_property_update keys -> no crash)"
    - "gitignore PII-bearing output (test-tickets.xlsx, mirrors .test-tickets-data.jsonl)"
key_files:
  created: []
  modified:
    - path: "scripts/test_tickets_run.py"
      description: "Added _assemble_fd_property_update, _fd_field_match, OWNED_FIELDS import, _process_row wiring, build_xlsx FD re-classification section"
    - path: "scripts/test_test_tickets_run.py"
      description: "Extended with 14 new offline tests: _assemble_fd_property_update (6) + _fd_field_match (5) + build_xlsx Task 2 (4)"
    - path: ".gitignore"
      description: "Added test-tickets.xlsx to prevent PII-bearing output from being committed"
decisions:
  - "_CATEGORY_TO_LEVEL_IN map is the single source of truth for category->Level_in derivation; not derived from level_in_choices() at call time to keep the adapter pure and offline-testable"
  - "test for empty-enum 'unverifiable' updated: snapshot Rootcause/Flow/Section_Flow were populated after 08-01 (no longer empty); invented values correctly return 'invalid' not 'unverifiable'"
  - "FD re-classification section placed after existing '— FD ticket properties —' section to preserve existing sheet layout; no structural reorder"
  - "match comparison is case-insensitive (enum labels can differ in casing between AI and CS gold)"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
  tests_added: 14
  tests_green: 27
---

# Phase 8 Plan 02: Harness Wiring — fd_property_update Assembly + xlsx Side-by-Side Summary

**One-liner:** Wires the 08-01 validator into the harness: `_assemble_fd_property_update` + `_fd_field_match` helpers attached to `_process_row`, and a per-field AI-vs-CS-gold comparison section rendered in `build_xlsx` with `✓`/`✗` status flags and an N/M summary row.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Failing tests for _assemble_fd_property_update + _fd_field_match | `3255677` | `scripts/test_test_tickets_run.py` |
| 1 | Assemble fd_property_update into record + per-field match | `1da238e` | `scripts/test_tickets_run.py`, `scripts/test_test_tickets_run.py` |
| 2 | Render side-by-side in build_xlsx + DRY_RUN assertion + gitignore | `14d869a` | `scripts/test_tickets_run.py`, `scripts/test_test_tickets_run.py`, `.gitignore` |

## What Was Built

### Task 1: `_assemble_fd_property_update` + `_fd_field_match` + `_process_row` wiring

**`_assemble_fd_property_update(ai_props)`** — thin adapter in `scripts/test_tickets_run.py`:
- Derives `Level_in` from `ai_props["category"]` via `_CATEGORY_TO_LEVEL_IN` map (`complaint`→`Complaint`, `change_request`→`Change_Request`, `inquiry`→`Inquiry`)
- Normalizes AI keys (`customer_request`, `rootcause`, `flow`, `step`→`section_flow`) and passes to `build_fd_property_update`
- Returns the verbatim `{fields, all_valid, advisory: True}` block — never coerces out-of-enum values
- Advisory/additive only (D-33): no verdict change, no reply path change, no Freshdesk write

**`_fd_field_match(fd_update, fd_props)`** — per-owned-field comparison:
- Compares AI value (from `fd_update["fields"][field]["value"]`) to CS gold (from `fd_props[field]`)
- `match=True` / `False` (case-insensitive exact) / `None` (field absent from CS gold → `status="no_gold"`)
- Out-of-scope FD fields (Package_status, Handler, Level_out) are excluded from the result
- Scope locked to `OWNED_FIELDS` = `(Level_in, Customer_Request, Rootcause, Flow, Section_Flow)`

**`_process_row` wiring** — purely additive:
- After `run_ai_team(...)`, computes `fd_update = _assemble_fd_property_update(ai["properties"])` and `fd_match = _fd_field_match(fd_update, fd_props)`
- Adds `fd_property_update` and `fd_field_match` keys to the returned record dict
- `assert settings.dry_run` already in `run_ai_team` — no new write path introduced

### Task 2: `build_xlsx` FD re-classification section + gitignore

**New section per sheet: `— FD re-classification (AI vs CS gold) —`**:
- Column headers: Field | CS gold | AI value + status | Match
- Per `OWNED_FIELDS` row:
  - Col B: CS gold value from `rec["fd_props"]`
  - Col C: AI value + inline status flag (`✓ valid` / `✗ INVALID (not in enum)` / `unverifiable (enum empty)` / `✗ nested_mismatch` / `missing`) — mirrors the `template_valid` ✓/✗ style
  - Col D: `match` / `differ` / `no gold`
- Summary row: `FD per-field match: N/M owned fields match CS gold`
- Graceful: records without `fd_property_update`/`fd_field_match` keys (legacy) render without crash

**`.gitignore`**: `test-tickets.xlsx` added (PII-bearing xlsx output; T-08-07 / D-04 posture)

## Test Results

```
scripts/test_test_tickets_run.py    27 passed  (13 prior + 14 new)
tests/test_ticket_fields_store.py   30 passed  (08-01, no regression)
tests/test_fd_classification.py     42 passed  (08-01, no regression)
Total                               99 passed, 0 failed
```

All tests fully offline. No network, no claude CLI, no Freshdesk, no Selless calls.

TDD gate sequence validated:
1. `test(08-02)` RED commit `3255677`: `ImportError` for both helpers — confirmed failing
2. `feat(08-02)` GREEN commit `1da238e`: 23/23 passing after implementation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_assemble_fd_property_update_empty_enum_unverifiable` — snapshot assumption stale**
- **Found during:** Task 1 GREEN verification
- **Issue:** Test asserted `Rootcause`/`Flow`/`Section_Flow` have empty enums → `unverifiable`. The 08-01 SUMMARY noted "currently empty" but the snapshot was populated between planning and execution — `field_choices("Rootcause")` returns `['Shipping', 'Fulfillment', 'Product', 'Content', 'Customer']`. A value not in a non-empty enum correctly returns `invalid`, not `unverifiable`.
- **Fix:** Renamed test to `test_assemble_fd_property_update_out_of_enum_invalid`; asserts invented values return `invalid` (or `unverifiable` if enum happens to be empty) and are never coerced — preserves the core correctness requirement
- **Files modified:** `scripts/test_test_tickets_run.py`
- **Commit:** `1da238e` (fixed before commit)

## Security / Threat Register

All T-08-05..T-08-07 mitigations implemented:

| Threat ID | Mitigation | Verified |
|-----------|-----------|---------|
| T-08-05 | No `PUT /tickets/{id}` path added; `assert settings.dry_run` in `run_ai_team`; grep-gate test confirms only read-only GETs remain | `test_no_live_write_path_in_harness` + plan verification grep |
| T-08-06 | `validate_field` status rendered verbatim in xlsx; `invalid` → `✗ INVALID (not in enum)` never hidden | `test_build_xlsx_fd_reclassification_per_field_status` |
| T-08-07 | `test-tickets.xlsx` added to `.gitignore` | `grep -q "test-tickets.xlsx" .gitignore` → GITIGNORE_OK |

## Known Stubs

None. The `fd_property_update` block is assembled from the real AI output and validated against the real snapshot enums. The xlsx section renders the actual assembled data. No hardcoded placeholders.

## Threat Flags

None. No new network endpoints, auth paths, or Freshdesk write surfaces introduced. `_assemble_fd_property_update` and `_fd_field_match` are pure dict functions. `build_xlsx` is read-only rendering. The only FD verbs in the harness remain GET.

## Self-Check: PASSED

Files exist:
- `scripts/test_tickets_run.py` (contains `_assemble_fd_property_update`, `_fd_field_match`, `OWNED_FIELDS`, `build_fd_property_update` import) — FOUND
- `scripts/test_test_tickets_run.py` (27 tests, imports `_assemble_fd_property_update`, `_fd_field_match`, `OWNED_FIELDS`) — FOUND
- `.gitignore` (contains `test-tickets.xlsx`) — FOUND

Commits exist:
- `3255677` — TDD RED tests — FOUND
- `1da238e` — Task 1 feat commit — FOUND
- `14d869a` — Task 2 feat commit — FOUND
