---
phase: 08-ticket-re-classification-fd-property-write-back
plan: "01"
subsystem: file_store
tags: [enum-loader, validation, fd-classification, offline, tdd, phase-8]
dependency_graph:
  requires:
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json"
    - "src/file_store/template_store.py (loader pattern)"
  provides:
    - "src/file_store/ticket_fields_store.py (level_in_choices, customer_requests_for, field_choices)"
    - "src/file_store/fd_classification.py (validate_field, build_fd_property_update, OWNED_FIELDS)"
  affects:
    - "08-02 harness wiring (consumes validate_field + build_fd_property_update)"
tech_stack:
  added: []
  patterns:
    - "repo-root-anchored static file read (mirrors template_store SNAPSHOTS_DIR pattern)"
    - "lazy module-level cache with injectable snapshot_path override for offline tests"
    - "fail-soft everywhere: missing file / malformed JSON / missing key -> [] never raises"
    - "verbatim enum enforcement: out-of-enum -> invalid, never coerced (mirrors allowed-codes guard)"
    - "empty-enum degrade: Rootcause/Flow/Section_Flow [] -> unverifiable (not valid/invalid)"
key_files:
  created:
    - path: "src/file_store/ticket_fields_store.py"
      description: "Static FD ticket_fields enum loader: level_in_choices(), customer_requests_for(), field_choices()"
      lines: 160
    - path: "src/file_store/fd_classification.py"
      description: "Enum-validation + fd_property_update assembler: validate_field(), build_fd_property_update(), OWNED_FIELDS"
      lines: 185
    - path: "tests/test_ticket_fields_store.py"
      description: "30 offline tests using fake snapshot fixture + 1 smoke test on real file"
      lines: 220
    - path: "tests/test_fd_classification.py"
      description: "42 offline tests (monkeypatched store): valid/invalid/unverifiable/missing + nested mismatch + OWNED_FIELDS"
      lines: 290
  modified:
    - path: "src/file_store/__init__.py"
      description: "Extended to export 3 loader functions + validate_field + build_fd_property_update + OWNED_FIELDS"
decisions:
  - "Inject snapshot_path as keyword-only arg (not a global override) to keep module-level cache for default path while allowing per-test fixture paths — avoids import-time side-effects"
  - "customer_requests_for() patched separately from field_choices() to enable precise nested-integrity test control"
  - "test_does_not_call_submit_reply checks for actual function call pattern (regex) not raw string — avoids false positive on docstring mentions"
  - "OWNED_FIELDS is a tuple (immutable) not a list — prevents accidental mutation"
  - "all_valid is False when any field is unverifiable (not just invalid) — conservative; unverifiable != valid"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
  tests_added: 72
  tests_green: 72
---

# Phase 8 Plan 01: Static FD Enum Loader + Validation Guard Summary

**One-liner:** Static ticket_fields enum loader (Level_in→Customer_Request nested + Rootcause/Flow/Section_Flow flat) + verbatim-enforcement validator with empty-enum unverifiable degrade, mirroring the allowed-codes guard discipline.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Static ticket_fields enum loader (offline) | `0fcd1cd` | `src/file_store/ticket_fields_store.py`, `tests/test_ticket_fields_store.py`, `src/file_store/__init__.py` |
| 2 | Enum-validation + fd_property_update assembler (offline) | `81a513c` | `src/file_store/fd_classification.py`, `tests/test_fd_classification.py`, `src/file_store/__init__.py` |

## What Was Built

### Task 1: `ticket_fields_store.py`

Static enum loader reading `freshdesk-ticket-fields.json` from the committed snapshot. Three public functions:

- `level_in_choices()` — returns `["Inquiry", "Change_Request", "Complaint"]`
- `customer_requests_for(level_in)` — returns verbatim children list; unknown level_in -> `[]`
- `field_choices(field)` — dispatches: `Level_in` → macro keys, `Customer_Request` → deduped union of all children, flat dropdowns → `dropdowns[field]` or `[]`, unknown → `[]`

Pattern mirrors `template_store.py`: repo-root anchor, lazy module-level cache, fail-soft on missing/malformed file. Injectable `snapshot_path=` keyword arg allows offline tests without network or touching the live file.

Key degrade behavior: `Rootcause`, `Flow`, `Section_Flow` are currently empty lists in the snapshot — `field_choices("Rootcause")` returns `[]` without raising, and the validator correctly treats this as `unverifiable`.

### Task 2: `fd_classification.py`

Enum validation + assembly, advisory-only (D-33):

- `OWNED_FIELDS = ("Level_in", "Customer_Request", "Rootcause", "Flow", "Section_Flow")` — hard scope boundary; out-of-scope fields (Level_out, Package_status, Handler, etc.) never emitted
- `validate_field(field, value, *, allowed=None)` — four-state status: `valid` / `invalid` / `unverifiable` (empty enum) / `missing` (no value). Out-of-enum values are flagged `invalid` and preserved verbatim — never coerced. When `allowed=None`, sourced from `field_choices(field)`.
- `build_fd_property_update(ai_props)` — assembles one entry per OWNED field; enforces nested integrity (Customer_Request validated against `customer_requests_for(level_in)` — mismatch → `nested_mismatch`); returns `{fields, all_valid, advisory: True}`. Never calls `submit_reply`, never posts to Freshdesk.

## Test Results

```
tests/test_ticket_fields_store.py    30 passed
tests/test_fd_classification.py      42 passed
Total                                72 passed, 0 failed
```

All tests are fully offline. No network, no DB, no live snapshot reads for populated-enum cases. TDD gate sequence validated:
1. `test(08-01)` RED phase: `ModuleNotFoundError` for both modules
2. `feat(08-01)` GREEN phase: 72/72 passing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] False-positive in `test_does_not_call_submit_reply`**
- **Found during:** Task 2 GREEN verification
- **Issue:** Test checked `"submit_reply" not in src_text` — failed because the string `submit_reply` appears in the module docstring as a prohibition note ("no submit_reply, no Freshdesk write")
- **Fix:** Changed test to check for actual function call pattern via regex (`r'\bsubmit_reply\s*\('`) and explicit import patterns (`import httpx`, `from requests`, etc.) — correctly distinguishes a comment mention from an actual call
- **Files modified:** `tests/test_fd_classification.py`
- **Commit:** `81a513c` (fixed before commit)

## TDD Gate Compliance

- RED gate: Both modules started with `ModuleNotFoundError` (30 + 42 errors) — confirmed failing
- GREEN gate: Both modules reach 100% passing after implementation — confirmed
- REFACTOR gate: Not needed — no cleanup required

## Security / Threat Register

All T-08-01..T-08-03 mitigations implemented:

| Threat ID | Mitigation | Verified |
|-----------|-----------|---------|
| T-08-01 | `validate_field` flags out-of-enum as `invalid`, never coerces | 42 tests including `test_invalid_*` and `test_no_value_fabrication` |
| T-08-02 | `SNAPSHOT_PATH` is a fixed constant, never built from runtime input | Source inspection + no runtime path construction |
| T-08-03 | `OWNED_FIELDS` tuple hard-limits output; 3 tests verify out-of-scope exclusion | `test_out_of_scope_fields_never_emitted` |

## Known Stubs

None. The loader reads the real snapshot; empty Rootcause/Flow/Section_Flow are an accurate reflection of the current snapshot state, not stubs. The `unverifiable` status is the correct degrade behavior until `scripts/fetch_ticket_fields_snapshot.py` repopulates them.

## Threat Flags

None. No new network endpoints, auth paths, or Freshdesk write surfaces introduced. The assembler is advisory-only; no `PUT /tickets/{id}` call path exists in this plan.

## Self-Check: PASSED

Files exist:
- `src/file_store/ticket_fields_store.py` — FOUND
- `src/file_store/fd_classification.py` — FOUND
- `tests/test_ticket_fields_store.py` — FOUND
- `tests/test_fd_classification.py` — FOUND
- `.planning/phases/01-.../snapshots/freshdesk-ticket-fields.json` — FOUND

Commits exist:
- `0fcd1cd` — Task 1 feat commit — FOUND
- `81a513c` — Task 2 feat commit — FOUND
