---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "04"
subsystem: safety-hooks
tags: [gap-closure, hooks, exit-code, grounding, injection, pii]
dependency_graph:
  requires: ["04-00", "04-01", "04-02", "04-03"]
  provides: ["SAFE-03", "SAFE-04", "REP-03"]
  affects: [".claude/hooks/pre_send_guard.py", ".claude/hooks/grounding_check.py", ".claude/hooks/injection_screen.py", ".claude/hooks/pii_redact.py"]
tech_stack:
  added: []
  patterns: ["exit-2-block-contract", "fail-closed-body-extraction", "payload-passthrough-on-error"]
key_files:
  modified:
    - .claude/hooks/pre_send_guard.py
    - .claude/hooks/grounding_check.py
    - .claude/hooks/injection_screen.py
    - .claude/hooks/pii_redact.py
    - tests/cs_team/test_hooks.py
decisions:
  - "CR-01: All PreToolUse@submit_reply guards use exit 2 (BLOCK) — not exit 1 — matching escalation_gate.py pattern"
  - "CR-03: Empty-body + empty-citation draft now fails grounding_check (grounding:no_citations) per D-11; only truly-empty string passes"
  - "CR-04: injection_screen._extract_body raises ValueError on missing prompt/body field — main() except escalates instead of passing empty string"
  - "CR-05: pii_redact error path passes original payload through unchanged (not {}) — raw_stdin captured before json.loads for fallback"
  - "D-04 PostToolUse timing limitation documented in pii_redact.py docstring — PostToolUse cannot fully satisfy before-ANY-log guarantee"
metrics:
  duration: "8 minutes"
  completed_date: "2026-06-03"
  tasks_completed: 2
  files_modified: 5
---

# Phase 04 Plan 04: Hook Exit-Code Fix + Gap-Closure Summary

**One-liner:** Fixed 4 deployed hooks to properly BLOCK submit_reply (exit 2 not exit 1), closed the empty-citation grounding bypass (CR-01/CR-03), and made injection_screen + pii_redact fail-closed/non-corrupting (CR-04/CR-05).

## What Was Built

Gap-closure for SAFE-03/SAFE-04/REP-03: four hook files corrected so the Claude Code PreToolUse contract is properly enforced at runtime.

### Task 1: Exit codes + empty-citation bypass (CR-01, CR-03)

**pre_send_guard.py:**
- Both `sys.exit(1)` calls in `main()` changed to `sys.exit(2)` — commitment-match branch and except/fail-closed branch
- Module docstring updated: "exits 2 (BLOCK/escalate) on match, 0 (pass) when clean"
- No changes to `check_commitment_language()` logic

**grounding_check.py:**
- Both `sys.exit(1)` calls in `main()` changed to `sys.exit(2)` — not-grounded branch and except/fail-closed branch
- Module docstring updated: "exits 2 (BLOCK/escalate) on failure"
- Rule 3 (CR-03): added check for non-empty body with zero markers AND zero citations → returns `(False, "grounding:no_citations")` instead of passing. D-11 requires ≥1 citation for any factual claim.

**tests/cs_team/test_hooks.py:**
- `test_empty_citations_empty_draft_passes` renamed to `test_empty_citations_nonempty_draft_fails` — now asserts FAIL (grounding:no_citations) for the non-empty body case
- Added `test_truly_empty_draft_passes` — empty string `""` with no citations still passes (no claims to ground)

### Task 2: Fail-closed body extraction + non-corrupting pii_redact (CR-04, CR-05)

**injection_screen.py:**
- `_extract_body()`: changed `return ""` to `raise ValueError("injection_screen:no_body_field")` when neither "prompt" nor "body" key present
- `main()` existing except branch catches this and escalates with `sys.exit(1)` (correct — this hook serves UserPromptSubmit, not PreToolUse@submit_reply)
- Module docstring updated to document fail-closed behavior

**pii_redact.py:**
- `main()` restructured: `raw_stdin = sys.stdin.read()` captured before `json.loads(raw_stdin)` so error path has access to original input
- Error path: `print("{}")` removed; replaced with `json.dumps(payload)` if payload was parsed, else `print(raw_stdin)` — no field corruption
- Module docstring: added D-04 PostToolUse timing limitation section explaining the residual mitigation (point-of-write redaction in submit_reply + trace sink)

## Acceptance Test Results

All subprocess acceptance tests passed:

| Test | Exit Code | Result |
|------|-----------|--------|
| pre_send_guard BLOCK (refund) | 2 | PASS |
| pre_send_guard PASS (clean cited) | 0 | PASS |
| grounding_check BLOCK (empty citations) | 2 | PASS |
| grounding_check PASS (grounded) | 0 | PASS |
| injection_screen BLOCK (missing body) | 1 (non-0) | PASS |
| injection_screen PASS (clean prompt) | 0 | PASS |
| injection_screen BLOCK (injection) | 1 (non-0) | PASS |
| pii_redact passthrough (other=keep, not {}) | 0 | PASS |

pytest: **38 passed** in 1.85s (`tests/cs_team/test_hooks.py tests/cs_team/test_hooks_red.py`)

## Commits

| Hash | Task | Description |
|------|------|-------------|
| 6b32c45 | Task 1 | fix(04-04): exit 2 BLOCK + close empty-citation bypass (CR-01, CR-03) |
| c0a057b | Task 2 | fix(04-04): fail-closed body extraction + non-corrupting pii_redact error path (CR-04, CR-05) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_empty_citations_empty_draft_passes asserted old PASS behavior**
- **Found during:** Task 1 — CR-03 changes check_grounding() so non-empty body + empty citations now FAILs
- **Issue:** The existing test asserted `grounded is True` for `check_grounding("Thank you for contacting us.", [])` — this would fail after CR-03
- **Fix:** Renamed test to `test_empty_citations_nonempty_draft_fails`, updated assertion to expect `grounded is False` with reason `grounding:no_citations`. Added separate `test_truly_empty_draft_passes` for the `check_grounding("", [])` case which remains PASS (no claims to ground in an empty draft).
- **Files modified:** `tests/cs_team/test_hooks.py`
- **Commit:** 6b32c45

## Known Stubs

None — all hooks are fully implemented and wired.

## Threat Flags

No new security-relevant surface introduced. This plan closes existing gaps (T-04-04-01 through T-04-04-05) in already-deployed hooks.

## Self-Check: PASSED

- `.claude/hooks/pre_send_guard.py` exists and contains `sys.exit(2)` (count: 2)
- `.claude/hooks/grounding_check.py` exists and contains `sys.exit(2)` (count: 2)
- `.claude/hooks/injection_screen.py` exists and contains `raise ValueError("injection_screen:no_body_field")`
- `.claude/hooks/pii_redact.py` exists, no `print("{}")`, has `raw_stdin` passthrough
- Commits 6b32c45 and c0a057b exist in git log
- 38 pytest tests pass
