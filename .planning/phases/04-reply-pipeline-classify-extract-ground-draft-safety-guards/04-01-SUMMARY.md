---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "01"
subsystem: safety-hooks
tags: [d32, hook-deletion, always-draft, poc-pivot, safety-floor]
dependency_graph:
  requires: []
  provides: [hook-deletion-d32, slimmed-settings-json]
  affects: [04-02, 04-03, cs-team-hooks]
tech_stack:
  added: []
  patterns: [deterministic-hook-deletion, deletion-assertion-test]
key_files:
  created:
    - tests/test_hook_deletion.py
  modified:
    - .claude/settings.json
  deleted:
    - .claude/hooks/pre_send_guard.py
    - .claude/hooks/escalation_gate.py
    - .claude/hooks/grounding_check.py
    - .claude/hooks/authorized_offer.py
decisions:
  - "D-32 implemented: four retired guard hooks deleted; only injection_screen (D-14) + pii_redact (D-04) survive as the safety floor"
  - "CS_RUN_ID env key removed from settings.json — escalation_gate's stateful veto pointer no longer needed"
  - "submit_reply PreToolUse chain completely removed — chokepoint exists but is no longer blocked by guards"
  - "scripts/cs_team_demo.py and scripts/test_tickets_run.py tracked stragglers deferred to 04-03 Task 1"
metrics:
  duration: "4m 13s"
  completed_date: "2026-06-04"
  tasks: 2
  files_changed: 6
---

# Phase 04 Plan 01: Delete Retired Guard Hooks (D-32) Summary

**One-liner:** Deleted four fail-closed guard hooks (pre_send_guard, escalation_gate, grounding_check, authorized_offer) and their settings.json wiring per D-32 always-draft pivot, retaining injection_screen + pii_redact as the surviving safety floor.

## What Was Built

The four guard hook files retired by D-30/D-32 are now gone from `.claude/hooks/`. The `submit_reply` PreToolUse chain, the SubagentStop escalation_gate binding, the PostToolUse escalation_gate entry, and the `CS_RUN_ID` env pointer are all removed from `.claude/settings.json`. The surviving hooks — `injection_screen.py` (D-14, UserPromptSubmit) and `pii_redact.py` (D-04, PostToolUse) — remain wired and unchanged.

A deletion-assertion test (`tests/test_hook_deletion.py`, 15 assertions) gates the contract: four hook files absent, settings.json references no deleted hook name, no submit_reply PreToolUse matcher, no CS_RUN_ID, and both surviving hooks still wired.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Delete four retired guard hook files | 665937f | deleted: pre_send_guard.py, escalation_gate.py, grounding_check.py, authorized_offer.py |
| 2 | Slim settings.json + deletion assertion test | 902cfee | .claude/settings.json, tests/test_hook_deletion.py |

## Verification Results

- `test ! -f .claude/hooks/pre_send_guard.py && ... && echo DELETED` → DELETED
- `test -f .claude/hooks/injection_screen.py && test -f .claude/hooks/pii_redact.py` → 0 (survivors intact)
- `grep -c 'pre_send_guard\|escalation_gate\|grounding_check\|authorized_offer' .claude/settings.json` → 0
- `grep -c 'CS_RUN_ID' .claude/settings.json` → 0
- `.venv/bin/pytest tests/test_hook_deletion.py -x -q` → 15 passed

## Deviations from Plan

### Deferred Items (not deviations — expected per plan spec)

**1. scripts/cs_team_demo.py tracked straggler (deferred to 04-03 Task 1)**

The plan noted the ONE expected straggler as the untracked `scripts/test_tickets_run.py`. In practice BOTH scripts are tracked:

- `scripts/test_tickets_run.py` (line 398): `importlib`-loads `authorized_offer.py`; sets `CS_RUN_ID`
- `scripts/cs_team_demo.py` (lines 89–95): `_load_hook("grounding_check")` and `_load_hook("pre_send_guard")`; references `CS_RUN_ID` + `escalation_gate` in docstrings

Both are deferred to 04-03 Task 1 (the demo-runner rework), consistent with the plan's intent. Neither file was modified in this plan. These will cause `ImportError` / `FileNotFoundError` at runtime when those scripts are invoked before 04-03 lands.

## Known Stubs

None. This plan only deletes code; no stubs introduced.

## Threat Flags

No new threat surface introduced. The plan deliberately removes the output guard (T-04-01-01 accepted PoC trade-off: HIGH severity, DRY_RUN-only gate). The two surviving mitigations (T-04-01-02 injection screen, T-04-01-03 PII redaction) remain active and wired.

## Accepted Risk (documented)

**T-04-01-01 — Elevation of Privilege (HIGH, accepted):** With the guard removed, the cs-agent-team can draft (and once live, auto-send) unauthorized refund/credit/legal commitments at 23k/week. Accepted as a deliberate PoC decision. Bounded by `SEND_MODE=dry_run` — `submit_reply` never posts to Freshdesk in this phase. A guard MUST be re-authored before any live (non-DRY_RUN) send. Tracked in 04-CONTEXT `<deferred>`.

## Self-Check: PASSED

- `.claude/settings.json` exists and is valid JSON: confirmed
- `tests/test_hook_deletion.py` exists (163 lines): confirmed
- Commit 665937f (hook deletion) exists: confirmed
- Commit 902cfee (settings.json + test) exists: confirmed
- 15/15 assertions pass: confirmed
