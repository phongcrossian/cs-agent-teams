---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "05"
subsystem: safety-hooks
tags: [gap-closure, escalation-gate, stateful-veto, injection-screen, subprocess-tests, CR-02, CR-04]
dependency_graph:
  requires: ["04-00", "04-01", "04-02", "04-03", "04-04"]
  provides: ["SAFE-03", "SAFE-04", "REP-03"]
  affects:
    - .claude/hooks/escalation_gate.py
    - .claude/settings.json
    - scripts/cs_team_demo.py
    - tests/cs_team/test_hooks_subprocess.py
tech_stack:
  added: []
  patterns:
    - stateful-per-run-veto-file
    - fail-closed-read-no-state
    - CS_RUN_ID-lifecycle
    - subprocess-exit-code-proof
    - mandatory-non-bypassable-prescreen
key_files:
  modified:
    - .claude/hooks/escalation_gate.py
    - .claude/settings.json
    - scripts/cs_team_demo.py
  created:
    - tests/cs_team/test_hooks_subprocess.py
decisions:
  - "CR-02: escalation_gate uses tempfile.gettempdir()/cs_run_state/<CS_RUN_ID>.json for per-run state; fail-closed at READ when no CS_RUN_ID or no file"
  - "CR-04 deploy: mandatory runner pre-screen is the enforced D-14 path; Claude Code installed version has no SubagentStart event, so UserPromptSubmit + runner pre-screen cover interactive and runner-invoked paths respectively"
  - "WRITE side NO-OP: when CS_RUN_ID unset, _write_signals() skips disk write; WRITE side still exits 1 on derived signal (early-escalation preserved from prior behaviour)"
  - "Subprocess test: test_noop_without_cs_run_id_on_write_side asserts exit 1 (early-signal) AND no disk write, not exit 0 — this matches the deployed contract"
metrics:
  duration: "18 minutes"
  completed_date: "2026-06-03"
  tasks_completed: 3
  files_modified: 3
  files_created: 1
---

# Phase 04 Plan 05: Stateful Escalation Gate + Subprocess Test Suite Summary

**One-liner:** Made escalation_gate.py stateful via per-run CS_RUN_ID state files (CR-02/SAFE-03), enforced mandatory non-bypassable injection pre-screen in the runner with CS_RUN_ID lifecycle (CR-04/SAFE-04), and proved deployed hook exit-code contract with 16 subprocess tests (TEST GAP closed).

## What Was Built

Three gap-closure items to reach 4/4 must-haves for Phase 04 re-verification.

### Task 1: Stateful final-risk veto — escalation_gate.py + settings.json (CR-02)

**escalation_gate.py** — added three new state-file helpers:

- `_state_path() -> Path | None`: returns `${TMPDIR}/cs_run_state/<CS_RUN_ID>.json` or None when env var unset. Uses `tempfile.gettempdir()` — never hardcoded `/tmp`.
- `_write_signals(signals: dict)`: OR-merges signals into the state file. Reads existing file first (tolerates missing/corrupt). Never flips a True back to False (D-08 additive). Creates parent dir on first write. NO-OP when CS_RUN_ID unset.
- `_read_signals() -> dict | None`: returns parsed signals dict, or None when CS_RUN_ID unset / file absent / unparseable.

`main()` rewired to two contexts:
- **WRITE side** (PostToolUse/SubagentStop): derives signals from payload, calls `_write_signals()`, exits 1 on signal / 0 when clean.
- **READ side** (PreToolUse@submit_reply): calls `_read_signals()`; exits 2 (BLOCK) on None (fail-closed: no state = cannot prove low-risk) OR any True signal.

**settings.json**: added `"CS_RUN_ID": "${CS_RUN_ID}"` to the `env` block alongside `SEND_MODE`. Without this line hook subprocesses on the deployed path never receive the env var, making the stateful veto dead. All existing bindings and order preserved.

**NO-OP safety**: when CS_RUN_ID is unset (non-cs-team session), the WRITE side skips the disk write; the READ side is only reached via the `submit_reply`-bound PreToolUse hook, a tool used only by the cs-team. The gate does not block unrelated Claude Code sessions after deploy.

### Task 2: Mandatory runner pre-screen + CS_RUN_ID lifecycle + dead-var cleanup (CR-04 deploy)

**scripts/cs_team_demo.py**:

- `_pre_screen_ticket()` docstring updated: now explicitly documented as the "MANDATORY, NON-BYPASSABLE D-14 entry gate for the runner".
- `run_ticket()` restructured: injection pre-screen runs unconditionally at the very start, before `use_live_claude` branch. On detection, returns `escalate` immediately — CLI is never invoked (no subagent sees the body).
- CS_RUN_ID lifecycle: `run_id = f"{ticket_id}-{uuid4().hex[:8]}"` generated per `run_ticket()` call; `os.environ["CS_RUN_ID"] = run_id` set before any CLI/simulation call; `finally` block deletes state file (best-effort) and pops CS_RUN_ID from env.
- Added `_state_file_path(run_id)` helper mirroring escalation_gate.py path convention.
- **Dead variable removed**: `raw_body_for_check = verdict.get("body", "") or verdict.get("reason", "")` at ~line 469 removed along with the misleading `# (redact_text is called on any string before printing)` comment.

**D-14 subagent binding decision**: The installed Claude Code version does not expose a SubagentStart or PreToolUse-on-Task event. The mandatory runner pre-screen in `run_ticket()` is therefore the enforced D-14 path for the deployed runner. The `UserPromptSubmit` binding in settings.json covers interactive/REPL sessions. This dual-path is documented in the module docstring.

### Task 3: Subprocess exit-code proof suite (TEST GAP)

**tests/cs_team/test_hooks_subprocess.py** — 16 new tests, 4 classes:

| Class | Tests | What is proved |
|---|---|---|
| `TestPreSendGuardSubprocess` | 3 | commitment language -> 2; clean -> 0; replace -> 2 |
| `TestGroundingCheckSubprocess` | 4 | ungrounded -> 2; empty-citation bypass (CR-03) -> 2; unknown citation -> 2; grounded -> 0 |
| `TestEscalationGateSubprocess` | 5 | write-high-risk THEN submit_reply -> 2; no state file -> 2; CS_RUN_ID unset -> 2; clean all-False THEN submit_reply -> 0; WRITE-side NO-OP (no disk write + exits 1) |
| `TestInjectionScreenSubprocess` | 4 | instruction-override -> non-zero; missing body (CR-04) -> non-zero; clean -> 0; role-override -> non-zero |

Helper `_run_hook(name, payload, env=None)` uses `sys.executable` with cwd=repo root and PYTHONPATH override so `from src...` imports resolve. Empty-string sentinel in `env` dict = unset the var from merged env. Unique CS_RUN_ID per test + `finally` cleanup ensures isolation.

## Acceptance Test Results

### Task 1 acceptance criteria

| Test | Result |
|---|---|
| WRITE high_risk THEN submit_reply -> exit 2 | PASS |
| No state file for run -> exit 2 (fail-closed) | PASS |
| CS_RUN_ID unset -> exit 2 (fail-closed) | PASS |
| Clean all-False WRITE then submit_reply -> exit 0 | PASS |
| `grep -c CS_RUN_ID escalation_gate.py` >= 2 | PASS (19) |
| `grep -c CS_RUN_ID settings.json` >= 1 | PASS (1) |
| settings.json valid JSON | PASS |
| test_settings_hook_bindings.py green | PASS (13 passed) |

### Task 2 acceptance criteria

| Test | Result |
|---|---|
| `grep -c raw_body_for_check cs_team_demo.py` == 0 | PASS (0) |
| `grep -c CS_RUN_ID cs_team_demo.py` >= 1 | PASS (8) |
| INJECTION_TICKET short-circuits before CLI | PASS |
| BENIGN_TICKET produces draft in simulation | PASS |
| settings.json valid JSON | PASS |
| test_e2e_dry_run.py green | PASS (22 passed, 6 skipped live) |

### Task 3 acceptance criteria

| Test | Result |
|---|---|
| `pytest tests/cs_team/test_hooks_subprocess.py -q` | PASS (16 passed) |
| `grep -c 'subprocess'` >= 1 | PASS (11) |
| `grep -c 'returncode'` >= 6 | PASS (62) |
| `grep -c 'returncode == 2'` >= 5 | PASS (22) |
| `grep -c 'returncode == 0'` >= 3 | PASS (13) |
| Full regression `pytest tests/cs_team/ -q` | PASS (138 passed, 6 skipped) |

## Commits

| Hash | Task | Description |
|---|---|---|
| 577c627 | Task 1 | feat(04-05): stateful final-risk veto — per-run CS_RUN_ID state file (CR-02) |
| 120207f | Task 2 | feat(04-05): mandatory runner pre-screen + CS_RUN_ID lifecycle + dead-var cleanup (CR-04) |
| 9468587 | Task 3 | test(04-05): subprocess exit-code proof suite for all PreToolUse hooks (TEST GAP) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_noop_without_cs_run_id_on_write_side expected exit 0 but deployed behaviour is exit 1**
- **Found during:** Task 3 first test run (1 failure)
- **Issue:** The test initially asserted `returncode == 0` for WRITE side with CS_RUN_ID unset, assuming it would be a complete NO-OP. However, the WRITE side still exits 1 when `_derive_signals()` finds a True signal — this is the correct "early escalation signal" behaviour preserved from before CR-02 (the NO-OP only applies to the disk write, not the exit code signal).
- **Fix:** Updated test to assert `returncode == 1` (early-signal, not final veto) AND also asserted `state_file.exists() == False` (the actual NO-OP invariant: no disk write). Added detailed docstring explaining the distinction.
- **Files modified:** `tests/cs_team/test_hooks_subprocess.py`
- **Commit:** 9468587

### D-14 Subagent Binding (documentation deviation)

The plan asked to "add an injection_screen binding on the subagent task-delivery event if Claude Code exposes one (e.g. a PreToolUse matcher on the Task/subagent tool, or SubagentStart)". The installed Claude Code version does not expose a `SubagentStart` event or a hookable Task delivery event. Rather than inventing a non-existent binding, the mandatory runner pre-screen in `run_ticket()` is documented as the enforced D-14 path (as the plan explicitly allows). This is documented in the SUMMARY (per plan requirement: "document which mechanism was used") and in the `cs_team_demo.py` module docstring.

## Known Stubs

None — all three files are fully implemented and wired.

## Threat Flags

No new security-relevant surface introduced. This plan closes existing gaps:
- T-04-05-01/02: stateful veto + fail-closed (escalation_gate.py CR-02)
- T-04-05-03: mandatory runner pre-screen (cs_team_demo.py CR-04)
- T-04-05-04: subprocess tests prove deployed exit-code contract (TEST GAP)
- T-04-05-05: state file stores only boolean flags + timestamp, no PII

## Self-Check: PASSED

- `.claude/hooks/escalation_gate.py` exists and contains `_write_signals`, `_read_signals`, `CS_RUN_ID` (19 occurrences)
- `.claude/settings.json` contains `CS_RUN_ID` (1 occurrence); valid JSON confirmed
- `scripts/cs_team_demo.py`: `raw_body_for_check` count = 0; `CS_RUN_ID` count = 8
- `tests/cs_team/test_hooks_subprocess.py` exists with 16 tests, 22 `returncode == 2`, 13 `returncode == 0`
- Commits 577c627, 120207f, 9468587 exist in git log
- 138 pytest tests pass (6 skipped live-gated); 0 failures
