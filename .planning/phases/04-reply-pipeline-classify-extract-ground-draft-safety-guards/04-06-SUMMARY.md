---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "06"
subsystem: test-harness
tags: [tdd, harness, slash-command, run-subcommand, uat, D-41, D-42, D-43, D-44]
dependency_graph:
  requires:
    - 04-05  # always-draft rework complete; run_ai_team / build_xlsx in place
  provides:
    - run subcommand (--id / --list / --limit / --per-cat) in test_tickets_run.py
    - _parse_ticket_list + _apply_caps pure helpers
    - /test-ticket slash command
  affects:
    - scripts/test_tickets_run.py  # new run subcommand + _process_row refactor
    - scripts/test_test_tickets_run.py  # new unit test file
    - .claude/commands/test-ticket.md  # new slash command
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle for pure helpers (no live services in unit tests)
    - Shared _process_row coroutine reused by both collect() and run()
    - walk-up .env.prd discovery for worktree/main-repo layouts
key_files:
  created:
    - scripts/test_test_tickets_run.py
    - .claude/commands/test-ticket.md
  modified:
    - scripts/test_tickets_run.py
decisions:
  - "_process_row extracted as shared coroutine: both collect() and run() call it; avoids code duplication and keeps collect() behavior unchanged"
  - "per_cat default=10 (D-43): conservative cap aligns with existing collect() default, prevents accidental large fanout on the real team"
  - "Level_in bucket passed as category_hint to run_ai_team: normalized to collect() keys (change_request/complaint/inquiry); unknown values passed as-is (non-blocking)"
  - "_load_env_prd walk-up fix: walks parent directories from _REPO_ROOT to find .env.prd; resolves credential sharing between git worktree and main repo without symlinking sensitive files"
metrics:
  duration_minutes: 6
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 1
  completed_date: "2026-06-05"
---

# Phase 04 Plan 06: /test-ticket On-Demand Slash Command Summary

Repackaged the existing Phase-4 validation harness into a clean on-demand `/test-ticket` command: new `run` subcommand with `--id`/`--list`/`--limit`/`--per-cat`, pure CSV parse + cap helpers, and a thin slash wrapper — no logic duplication, deterministic `_SUBTYPE_TEMPLATES` map preserved.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Failing unit tests (RED) | `10a3325` | `scripts/test_test_tickets_run.py` (created) |
| 2 | `run` subcommand engine (GREEN) | `4afd24e` | `scripts/test_tickets_run.py` |
| 3 | `/test-ticket` slash command + smoke | `3ef159f` | `.claude/commands/test-ticket.md` (created), `scripts/test_tickets_run.py` |

## What Was Built

### `scripts/test_tickets_run.py` — `run` subcommand (D-41)

New helpers and entry point added to the existing harness:

- **`_parse_ticket_list(path)`** — parses `uat_ticket.csv` (semicolon-delimited, header `Level_in;Resolved date;Ticket ID`) OR a plain one-ID-per-line file (bucket = "unknown"). Returns `list[dict]` with `Ticket ID` and `Level_in`.
- **`_apply_caps(rows, limit, per_cat)`** — applies `--per-cat` (per-`Level_in` bucket) then `--limit` (total) caps. Returns `(selected_rows, dropped_report)` where `dropped_report` maps bucket → dropped count. Drops are always logged, never silent (D-43).
- **`_process_row()`** — shared async coroutine extracted from `collect()` body: `fetch_conversation` (Freshdesk GET) + `fetch_selless_order` (Selless read-only, when order code present) + `run_ai_team` (real team, DRY_RUN). Both `collect()` and `run()` call it — collect() behavior unchanged.
- **`run(ticket_id, list_path, limit, per_cat)`** — async entry: builds row set from `--id` (one synthetic row) or `--list` (parsed + capped CSV), processes each row via `_process_row`, writes `_DATA_PATH`, calls `build_xlsx()` (D-44). Asserts `settings.dry_run`; no Freshdesk POST path (D-39).
- **`main()` wiring** — `add_parser("run")` with `--id`, `--list`, `--limit`, `--per-cat`; dispatches to `asyncio.run(run(...))`.

### `.claude/commands/test-ticket.md` — thin slash wrapper (D-41)

Dispatches args verbatim to `scripts/test_tickets_run.py run`. Contains no Python logic. Documents DRY_RUN/read-only PROD, `--per-cat` default 10, dropped-count logging, `test-tickets.xlsx` output, and `uat_ticket.csv` format.

### `scripts/test_test_tickets_run.py` — 6 unit tests

| Test | What it covers |
|------|----------------|
| `test_parse_csv_semicolon_format` | Semicolon CSV parse, Level_in bucket preserved |
| `test_parse_plain_id_per_line` | Plain ID-per-line, bucket = empty/unknown |
| `test_apply_caps_per_cat` | `--per-cat=2` on 2×5 rows → 4 selected, 3+3 dropped report |
| `test_apply_caps_limit` | `--limit=4` on 10 rows → 4 selected, 6 total dropped |
| `test_parse_csv_single_id_selection` | Match/no-match filter after parse |
| `test_allowed_codes_deterministic_subtype_map` | `_allowed_codes_for_subtype("Replace")` non-empty; `"__nope__"` = empty — anti-pattern guard (T-04.06-05) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `.env.prd` not found when running from worktree**

- **Found during:** Task 3 smoke test
- **Issue:** `_load_env_prd()` used `_REPO_ROOT / ".env.prd"` but `_REPO_ROOT = Path(__file__).parent.parent` resolves to the worktree directory when running the worktree's script. `.env.prd` lives in the main repo only.
- **Fix:** Added walk-up logic in `_load_env_prd()`: if `.env.prd` is not at `_REPO_ROOT`, walk parent directories until found. Resolves credential sharing between worktrees and the main repo without symlinking sensitive files.
- **Files modified:** `scripts/test_tickets_run.py` (Task 3 commit `3ef159f`)

## Smoke Test Result

```
run --id 7505172 (Change_Request ticket from uat_ticket.csv)
→ Freshdesk GET OK, Selless=no order code, AI=draft, cr=Cancel_Order, tmpl=F1
→ test-tickets.xlsx written (6615 bytes), .test-tickets-data.jsonl written
→ Exit 0, no Freshdesk POST (D-39 DRY_RUN confirmed)
```

## Known Stubs

None — the `run` path wires directly into the existing real-team machinery (`run_ai_team`, `build_xlsx`). No placeholder data flows to xlsx output.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers. The `run` path reuses the existing Freshdesk GET + Selless read-only + local file-write surface. `assert settings.dry_run` preserved; no `/reply` POST path added (T-04.06-03 mitigated).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `scripts/test_test_tickets_run.py` exists | FOUND |
| `scripts/test_tickets_run.py` exists | FOUND |
| `.claude/commands/test-ticket.md` exists | FOUND |
| `04-06-SUMMARY.md` exists | FOUND |
| Commit `10a3325` (RED tests) | OK |
| Commit `4afd24e` (GREEN impl) | OK |
| Commit `3ef159f` (slash + smoke) | OK |
