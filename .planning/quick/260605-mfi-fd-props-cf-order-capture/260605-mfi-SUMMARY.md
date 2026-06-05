---
phase: quick-260605-mfi-fd-props-cf-order-capture
plan: 01
subsystem: validation-harness
tags: [fd-props, cf-order, selless-grounding, pii-redaction, tdd, xlsx, ticket-fields-snapshot]
dependency_graph:
  requires: []
  provides:
    - _extract_fd_props helper (scripts/test_tickets_run.py)
    - fd_props capture + cf_order -> Selless grounding
    - freshdesk-ticket-fields.json static enum snapshot
    - fetch_ticket_fields_snapshot.py offline regen script
  affects:
    - scripts/test_tickets_run.py
    - scripts/test_test_tickets_run.py
    - .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json
    - scripts/fetch_ticket_fields_snapshot.py
tech_stack:
  added: []
  patterns:
    - TDD RED->GREEN (offline pure-function tests, no network)
    - prefix-matched suffixed FD custom_fields (cf_level_in*, cf_customer_request*)
    - PII redaction via redact_text() on @/http values before storage (D-04)
    - setdefault merge of fd_props into cs_props (CSV values never overwritten)
key_files:
  modified:
    - scripts/test_tickets_run.py
    - scripts/test_test_tickets_run.py
  created:
    - .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json
    - scripts/fetch_ticket_fields_snapshot.py
decisions:
  - "PII-bearing cf values (containing @ or http) are always routed through redact_text() before storage — order_code is an order ref, not PII, and is left as-is"
  - "fd_props merged into cs_props via setdefault semantics — CSV-supplied values are never overwritten"
  - "order_code derivation: CSV row Order column first, fall back to fd_order_code from FD payload — reuses existing fetch_selless_order, no duplicate Selless logic"
  - "Dropdown values in freshdesk-ticket-fields.json committed as empty [] — Level_in nested taxonomy is the load-bearing data; dropdowns filled by regen script when needed"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-05"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
  files_created: 2
---

# Phase quick-260605-mfi Plan 01: FD Props + cf_order Capture Summary

**One-liner:** Pure `_extract_fd_props` helper captures Freshdesk custom_fields (prefix-matched suffixed keys, PII-redacted) and wires `cf_order` to the existing Selless lookup so the AI grounds on the real order without asking the customer.

## Tasks Completed

| Task | Name | Commit | Status |
|------|------|--------|--------|
| 1 | RED — offline tests for _extract_fd_props | 39ae4da | Done |
| 2 | GREEN — implement _extract_fd_props + wire + xlsx | 52d0689 | Done |
| 3 | Versioned static ticket_fields enum snapshot + regen | 45d2ef7 | Done |

## What Was Built

### _extract_fd_props(tj: dict) -> tuple[dict, str]

Pure function (no network calls) placed in `scripts/test_tickets_run.py` just above `fetch_conversation`:

- **Prefix-matched suffixed keys:** `cf_level_in285413` → `Level_in`, `cf_customer_request83284` → `Customer_Request` — robust to any numeric suffix
- **Fixed cf key mapping:** cf_category→Category, cf_rootcause→Rootcause, cf_package_status→Package_status, cf_product_label→Product_label, cf_product_line→Product_line, cf_flow→Flow, cf_section_flow→Section_Flow
- **Standard fields:** status→Status, priority→Priority, tags→Tags (list joined to comma string)
- **PII redaction (D-04, T-mfi-01):** cf_email_support, cf_shophelp_discussion_link, and any value containing `@` or `http` → `redact_text()` before storing
- **order_code:** exact `cf_order` key, not PII, left as-is
- **Empty-safe:** returns `({}, "")` for `{}` or `{"custom_fields": {}}` without raising

### Selless grounding via cf_order (MFI-1)

`_process_row` derives order_code as:
```python
order_code = (row.get("Order") or "").strip() or conv.get("fd_order_code", "")
```
The `--id` path (synthetic row, no Order column) now uses the FD `custom_fields.cf_order` to trigger the **existing** `fetch_selless_order` — no new Selless call added.

### fd_props in record + merged into cs_props (MFI-2)

- `fetch_conversation` returns `fd_props` and `fd_order_code` in its dict
- `_process_row` merges fd_props into cs_props using setdefault semantics (CSV-supplied values never overwritten)
- Record carries `"fd_props"` key at top level

### build_xlsx FD-properties section (MFI-4)

After the Checker block, a "— FD ticket properties —" labelled section lists each fd_props key/value in column A (label) / column C (value). No raw PII is printed to stdout (id/length/label-only logging preserved, T-mfi-02).

### Static ticket_fields enum snapshot (MFI-6)

`freshdesk-ticket-fields.json` at `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/`:
- `nested.Level_in`: full verified taxonomy (Inquiry/Change_Request/Complaint → Customer_Request children)
- `dropdowns`: 7 keys present as `[]` placeholder (filled by regen script)
- `_meta`: source, captured date, version, offline-contract note

### Offline regen script

`scripts/fetch_ticket_fields_snapshot.py` — `__main__`-guarded, GET-only, never imported by harness/tests.

## Test Results

```
11 passed (6 pre-existing + 5 new A-E) in 1.21s
```

Tests A–E are fully offline (pure dict input, no httpx client, no network).

## Deviations from Plan

None — plan executed exactly as written. `_SUBTYPE_TEMPLATES` and `_allowed_codes_for_subtype` are untouched.

## Safety Contract Verification

- `assert settings.dry_run` preserved in `run_ai_team` and `run` — confirmed
- No Freshdesk POST/reply path added — confirmed (`grep -E "reply|POST"` shows no write path)
- `_SUBTYPE_TEMPLATES` / template-selection logic untouched — confirmed
- PII redacted before storage: T-mfi-01 (fd_props), T-mfi-02 (stdout) — Test C asserts no raw email in fd_props

## Known Stubs

- `dropdowns` values in `freshdesk-ticket-fields.json` are `[]` — intentional placeholder. The nested `Level_in` taxonomy is the load-bearing data. Dropdown values (Rootcause, Flow, etc.) will be populated when the regen script is run with live credentials. These are informational lookups only; the AI Agent Team does not require them to draft.

## Self-Check: PASSED

- `_extract_fd_props` exists in scripts/test_tickets_run.py: confirmed (grep count = 2)
- `fd_order_code` in scripts/test_tickets_run.py: confirmed
- `freshdesk-ticket-fields.json` exists with Level_in taxonomy: SNAPSHOT-OK verified
- `fetch_ticket_fields_snapshot.py` exists with `__main__` guard: REGEN-OK verified
- Commits 39ae4da, 52d0689, 45d2ef7 exist: confirmed via git log
- All 11 tests pass: confirmed
