---
phase: 08-ticket-re-classification-fd-property-write-back
verified: 2026-06-05T11:15:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The pipeline emits an fd_property_update block with a verbatim enum value per owned field, grounded in ticket + Selless + CODE-MAP"
    status: partial
    reason: >
      The fd_property_update block IS emitted and the validation infrastructure IS correct
      (validate_field flags free-text as "invalid"). However, the classifier/extractor
      prompts (_build_classify_prompt, _build_draft_prompt2 in scripts/test_tickets_run.py)
      do NOT inject the allowed enum values for Rootcause, Flow, and Section_Flow into the
      model's instructions. The prompt asks for '"rootcause": "<root cause if determinable>"'
      and '"flow": "<workflow/flow name>"' as open free-text slots — not constrained to the
      enum. A live smoke run (ticket 7508382) confirmed the AI emits free-text values such as
      "Variant unavailable / order cancelled" for Rootcause, which validate_field correctly
      flags as "invalid". The block is emitted and validated; the prompt-side enum injection
      is the missing piece.
    artifacts:
      - path: "scripts/test_tickets_run.py"
        issue: "_build_classify_prompt and _build_draft_prompt2 do not inject ALLOWED enum values for Rootcause/Flow/Section_Flow into the model prompt"
    missing:
      - "Add allowed enum injection for Rootcause, Flow, and Section_Flow to _build_classify_prompt and/or _build_draft_prompt2 (similar to how ALLOWED TEMPLATE CODES BY SUB-TYPE are already injected for template_code)"
      - "Plan 08-03: classifier/extractor prompt enum injection for Rootcause/Flow/Section_Flow"
---

# Phase 8: Ticket Re-Classification & FD Property Write-Back Verification Report

**Phase Goal:** Beyond drafting the customer reply, the Agent Team RE-CLASSIFIES each ticket and DEFINES the core Freshdesk classification properties — Level_in, Customer_Request (nested), Rootcause, Flow, Section_Flow — by mapping the AI's understanding (ticket body + Selless order data + Workflow/CODE-MAP) to the EXACT ticket_fields dropdown enum values, and emits a DRY_RUN "would-be FD property update" (classify → map → validate against enum → log to xlsx/jsonl). Produces and validates the mapping + the classified property set; the live FD write is deferred.
**Verified:** 2026-06-05T11:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A static enum loader exposes the FD ticket_fields choices (nested Level_in→Customer_Request taxonomy + Rootcause/Flow/Section_Flow), read from the committed snapshot with no network call | VERIFIED | `src/file_store/ticket_fields_store.py` exists (184 lines), anchored at repo-root, lazy-cached, fail-soft. Snapshot is populated: Rootcause=14 values, Flow=7 values, Section_Flow=5 values, Level_in=9 keys. 31 offline tests green. `level_in_choices()`, `field_choices()`, `customer_requests_for()` all return correct values from the real snapshot. |
| 2 | The pipeline emits an fd_property_update block with a verbatim enum value per owned field, grounded in ticket + Selless + CODE-MAP | PARTIAL | The block IS emitted in `_process_row` (lines 1431-1432) and the validator correctly flags out-of-enum values. However, the classifier prompts do NOT inject allowed enum values for Rootcause/Flow/Section_Flow — the AI emits free-text (e.g. "Variant unavailable / order cancelled") which validate_field correctly marks "invalid". Level_in and Customer_Request ARE constrained by the prompt (the enum taxonomy is embedded in the customer_request field description). Rootcause/Flow/Section_Flow lack prompt-side enum injection. |
| 3 | Every emitted value is validated against the allowed enum; an invalid/out-of-enum value is flagged (never silently accepted) | VERIFIED | `validate_field()` enforces: value in non-empty allowed → "valid"; value not in non-empty allowed → "invalid" (verbatim preserved); empty allowed → "unverifiable"; no value → "missing". Tested with 42 offline tests. Out-of-enum free-text values confirmed "invalid" via live check. `build_xlsx` renders ✓/✗ status per field. |
| 4 | The validation harness shows AI-defined properties vs CS gold FD custom_fields side-by-side with a per-field match metric | VERIFIED | `build_xlsx()` lines 1192-1253 render "— FD re-classification (AI vs CS gold) —" section with CS gold (col B), AI value + status (col C), match result (col D), and summary row "FD per-field match: N/M owned fields match CS gold". `_fd_field_match()` computes match/differ/no_gold per owned field. 27 harness tests green including xlsx rendering test. |
| 5 | DRY_RUN only — no live PUT /tickets/{id} path; assert no Freshdesk write occurs beyond the existing submit_reply chokepoint | VERIFIED | `grep -nE "PUT|\.put\(|api/v2/tickets/.*reply" scripts/test_tickets_run.py` returns no results. `assert settings.dry_run` is present at both `run()` entry (line 1467) and `run_ai_team()` entry (line 579). No httpx.put or write-path import in file_store modules. .gitignore includes `test-tickets.xlsx` (line 43). |

**Score: 4/5 truths verified**

---

### Deferred Items

None.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/file_store/ticket_fields_store.py` | Static enum loader: field_choices/customer_requests_for/level_in_choices (min 60 lines) | VERIFIED | 184 lines. All 3 public functions present and wired to real snapshot. |
| `src/file_store/fd_classification.py` | Enum validation + fd_property_update assembly: validate_field, build_fd_property_update (min 60 lines) | VERIFIED | 234 lines. OWNED_FIELDS=5 fields, validate_field with 4 statuses, build_fd_property_update with nested integrity check. |
| `tests/test_ticket_fields_store.py` | Offline loader tests over fake snapshot payload | VERIFIED | 31 tests (fake fixture + 1 real smoke). All green. |
| `tests/test_fd_classification.py` | Offline validation + assembly tests | VERIFIED | 41 tests covering valid/invalid/unverifiable/missing/nested_mismatch/OWNED_FIELDS scope. All green. |
| `scripts/test_tickets_run.py` | fd_property_update assembled in _process_row + rendered in build_xlsx with per-field match + valid flags | VERIFIED | `_assemble_fd_property_update` and `_fd_field_match` wired at lines 1431-1432; xlsx section at lines 1192-1253. |
| `scripts/test_test_tickets_run.py` | Offline tests: assembly merged into record, per-field match metric, no live PUT | VERIFIED | 27 tests. Covers _assemble_fd_property_update (6 tests), _fd_field_match (4 tests), build_xlsx with fd section, no-PUT assertion. All green. |
| `.gitignore` | test-tickets.xlsx ignored | VERIFIED | Line 43: `test-tickets.xlsx` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/file_store/fd_classification.py` | `src/file_store/ticket_fields_store.py` | `from src.file_store.ticket_fields_store import field_choices, customer_requests_for` | WIRED | Line 29 of fd_classification.py |
| `src/file_store/ticket_fields_store.py` | `.planning/.../snapshots/freshdesk-ticket-fields.json` | `SNAPSHOT_PATH` constant anchored to repo root (line 38-45) | WIRED | Path confirmed, file exists, loader reads it |
| `scripts/test_tickets_run.py::_process_row` | `src/file_store/fd_classification.build_fd_property_update` | `_assemble_fd_property_update(ai["properties"])` at line 1431 | WIRED | Import at line 42-44; called in _process_row |
| `scripts/test_tickets_run.py::build_xlsx` | `rec fd_property_update + rec fd_field_match` | `fd_upd = rec.get("fd_property_update")` + iterates OWNED_FIELDS | WIRED | Lines 1193-1254; renders side-by-side with CS gold |
| `src/file_store/__init__.py` | All 6 public symbols | exports `level_in_choices`, `customer_requests_for`, `field_choices`, `validate_field`, `build_fd_property_update`, `OWNED_FIELDS` | WIRED | Lines 10-31 of __init__.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `ticket_fields_store.py` | `_CACHE` | `freshdesk-ticket-fields.json` (static file, committed) | Rootcause=14, Flow=7, Section_Flow=5 values | FLOWING |
| `fd_classification.py::validate_field` | `allowed` | `field_choices(field)` from loader | Returns real enum lists | FLOWING |
| `scripts/test_tickets_run.py::_process_row` | `fd_update`, `fd_match` | `_assemble_fd_property_update(ai["properties"])` → `build_fd_property_update()` → `validate_field()` | Emits block; AI values for Rootcause/Flow/Section_Flow are free-text (not enum-constrained) → flagged "invalid" by validator | PARTIAL — data flows, but AI does not produce verbatim enum values for Rootcause/Flow/Section_Flow |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 72 offline unit tests (loader + validator) | `pytest tests/test_ticket_fields_store.py tests/test_fd_classification.py -q` | 72 passed in 0.48s | PASS |
| 27 harness integration tests | `pytest scripts/test_test_tickets_run.py -q` | 27 passed in 1.37s | PASS |
| Loader returns populated enums from real snapshot | `field_choices('Rootcause')` | 14 values returned | PASS |
| validate_field flags free-text as invalid | `validate_field('Rootcause', 'Variant unavailable')` | status="invalid" | PASS |
| No PUT/write path in harness | `grep -nE "PUT|\.put\(" scripts/test_tickets_run.py` | empty output | PASS |
| No network imports in file_store modules | `grep -nE "httpx\|requests" ticket_fields_store.py fd_classification.py` | only in comments | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files found for this phase. Phase 8 has no conventional probe scripts.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REP-06 | 08-01, 08-02 | AI re-classifies ticket and defines core FD classification properties (Level_in, Customer_Request, Rootcause, Flow, Section_Flow) mapped to exact ticket_fields enum values, validated, DRY_RUN only | PARTIAL | SC#1, SC#3, SC#4, SC#5 fully met. SC#2 partially met: block emitted and validated correctly, but AI does not yet pick verbatim enum values for Rootcause/Flow/Section_Flow (prompt-side enum injection missing). |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX markers found in phase 8 files | — | — |

No stub patterns found. No hardcoded empty data in rendering paths. No placeholder implementations detected.

---

### Human Verification Required

None required. All verification items are programmatically checkable.

---

## Gaps Summary

**1 gap blocking full goal achievement:**

**SC#2 — Prompt-side enum injection for Rootcause/Flow/Section_Flow (PARTIAL)**

The infrastructure is complete and correct:
- The snapshot has real enum values (Rootcause=14, Flow=7, Section_Flow=5)
- `validate_field()` correctly flags free-text as "invalid" and would accept verbatim enum values as "valid"
- The `fd_property_update` block is emitted and rendered in the xlsx

The missing piece: `_build_classify_prompt()` and `_build_draft_prompt2()` in `scripts/test_tickets_run.py` instruct the AI with open-ended slots like `"rootcause": "<root cause if determinable>"` and `"flow": "<workflow/flow name>"`. The allowed enum values are not injected, so the AI produces free-text (e.g. "Variant unavailable / order cancelled" for Rootcause) which the validator correctly marks "invalid".

**Recommended fix (Plan 08-03):** Inject the allowed enum values for Rootcause, Flow, and Section_Flow into the classifier and drafter prompts — similar to how ALLOWED TEMPLATE CODES BY SUB-TYPE are already injected for `template_code`. The `field_choices()` function already provides the correct lists at runtime.

Note: Level_in and Customer_Request are partially constrained already because the prompt enumerates the sub-type values in the `customer_request` description field. The gap is specifically Rootcause/Flow/Section_Flow.

---

_Verified: 2026-06-05T11:15:00Z_
_Verifier: Claude (gsd-verifier)_
