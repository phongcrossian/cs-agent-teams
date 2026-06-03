---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
verified: 2026-06-03T06:15:00Z
status: human_needed
score: 4/4 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 2/4
  gaps_closed:
    - "pre_send_guard.py and grounding_check.py now exit 2 (BLOCK) on violation and on internal error (CR-01)"
    - "Empty-citation no-marker draft now fails grounding_check — bypass closed (CR-03)"
    - "escalation_gate.py is now stateful via CS_RUN_ID per-run state file; READ side at submit_reply fails closed (CR-02)"
    - "injection_screen._extract_body raises on missing body field — fail-closed (CR-04 hook half)"
    - "pii_redact error path passes original payload through — no {} corruption (CR-05)"
    - "settings.json wires CS_RUN_ID env so hook subprocesses receive it; all §4a bindings intact"
    - "Subprocess test suite (16 tests) proves deployed exit-code contract for all PreToolUse hooks"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run a complete ticket through the live Claude Code agent team with CS_RUN_ID exported, inject a high-risk signal at the PostToolUse stage, and confirm submit_reply is blocked in the real runtime"
    expected: "submit_reply tool is blocked by escalation_gate (no reply posted); escalate verdict returned to cs-lead"
    why_human: "Requires a live Claude Code session with the agent team active — cannot verify the runtime hook dispatch chain without a real session"
  - test: "Send a ticket body containing 'ignore all previous instructions' through the runner (cs_team_demo.py with use_live_claude=False) and verify the pre-screen short-circuits before any CLI/subagent is invoked"
    expected: "run_ticket() returns action=escalate with reason starting injection: before the Claude Code subprocess is launched"
    why_human: "The simulation path confirms the Python pre-screen, but the live runner path requires a running Claude Code environment to confirm no subagent ever receives the unscreened body"
---

# Phase 04: Reply Pipeline — Safety Guards Re-Verification Report

**Phase Goal:** Build the end-to-end reply pipeline with deterministic safety guards that produce grounded drafts or escalate on risk/violation.
**Verified:** 2026-06-03T06:15:00Z
**Status:** human_needed (4/4 automated checks VERIFIED; 2 live-session items pending)
**Re-verification:** Yes — after gap-closure waves 04-04 and 04-05

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | REP-01/REP-02: Pipeline classifies, extracts, retrieves, drafts or escalates | ✓ VERIFIED | Unchanged from prior 2/4 pass; agent skills + MCP stubs exist and pass in-process e2e tests (22 passed, 6 skipped live-gated) |
| 2 | SAFE-03: Any risk signal blocks submit_reply via the stateful escalation_gate veto | ✓ VERIFIED | Subprocess proof: write high_risk → submit_reply → exit 2; no-state-file → exit 2; CS_RUN_ID unset → exit 2; clean all-False → exit 0. See evidence section. |
| 3 | SAFE-04: Commitment language blocked at deployed surface (exit 2, not exit 1); empty-citation bypass closed | ✓ VERIFIED | pre_send_guard: 2x sys.exit(2), 0x sys.exit(1) in code; subprocess BLOCK=2 PASS=0 confirmed. grounding_check: 2x sys.exit(2), Rule 3 CR-03 closes empty-citation case; subprocess BLOCK=2 PASS=0 confirmed. |
| 4 | Subprocess tests prove deployed exit-code contract (not in-process simulation) | ✓ VERIFIED | 16/16 tests PASS in tests/cs_team/test_hooks_subprocess.py using real subprocess calls via sys.executable |

**Score:** 4/4 truths verified

### Deferred Items

None.

---

## Detailed Evidence

### SC-3 / SAFE-03 — Stateful Escalation Gate (CR-02)

**Code review — escalation_gate.py:**

- `_state_path()` (line 125): returns `Path(tempfile.gettempdir()) / "cs_run_state" / f"{run_id}.json"` or None when CS_RUN_ID unset. Never hardcodes `/tmp`. ✓
- `_write_signals()` (line 139): OR-merges; never flips True→False (D-08 additive); creates parent dir; NO-OP when CS_RUN_ID unset. ✓
- `_read_signals()` (line 177): returns None when CS_RUN_ID unset / file absent / unparseable → callers must escalate. ✓
- `main()` READ side (lines 237–258): `is_final_veto` when `tool_name=="submit_reply"` or `hook_event_name=="PreToolUse"`; on `_read_signals()==None` → `sys.exit(2)`; on any True signal → `sys.exit(2)`; all-clean → `sys.exit(0)`. ✓
- `main()` WRITE side (lines 260–274): derives signals, writes to state file, exits 1 on signal / 0 when clean. ✓

**settings.json wiring:**

```
env: {"SEND_MODE": "dry_run", "CS_RUN_ID": "${CS_RUN_ID}"}
```

CS_RUN_ID forwarded to all hook subprocesses via settings.json env block. Without this line the stateful veto is dead on the deployed path. ✓

**Subprocess proofs (manual run, python3 .claude/hooks/escalation_gate.py):**

| Scenario | Command | Exit | Result |
|----------|---------|------|--------|
| WRITE high_risk then READ at submit_reply | PostToolUse payload → exit 1; submit_reply payload same CS_RUN_ID → exit 2 | 2 | BLOCK ✓ |
| No state file for run | submit_reply + CS_RUN_ID set, no file | 2 | BLOCK ✓ |
| CS_RUN_ID unset | submit_reply, no env var | 2 | BLOCK ✓ |
| Clean all-False WRITE then READ | PostToolUse all-False → exit 0; submit_reply → exit 0 | 0 | PASS ✓ |
| WRITE side, CS_RUN_ID unset | PostToolUse with signal, no env var | 1 | NO-OP disk, early signal ✓ |

**Residual warning (documented, not a blocker):** The outer `except` in `main()` (line 276–278) uses `sys.exit(1)` regardless of context. If `json.load(sys.stdin)` raises (malformed stdin from the Claude Code runtime itself), the hook exits 1 — which is non-blocking in a PreToolUse context. However: (a) `grounding_check.py` and `pre_send_guard.py` precede `escalation_gate.py` in the PreToolUse chain and both fail-closed with exit 2; (b) malformed stdin from Claude Code's own runtime is not a realistic attack vector. This is a defense-in-depth gap only; the §4a chain is protected by the two prior guards.

---

### SC-4 / SAFE-04 — Commitment Language Block + Injection Screen (CR-01, CR-03, CR-04)

**pre_send_guard.py exit-code audit:**

- Line 100: `sys.exit(2)` on commitment language match ✓
- Line 104: `sys.exit(2)` on except/fail-closed ✓
- `grep -c 'sys.exit(2)' .claude/hooks/pre_send_guard.py` → 2 ✓
- `grep -v '^#' .claude/hooks/pre_send_guard.py | grep -c 'sys.exit(1)'` → 0 ✓

**grounding_check.py exit-code audit:**

- Line 114: `sys.exit(2)` on not-grounded ✓
- Line 118: `sys.exit(2)` on except/fail-closed ✓
- `grep -c 'sys.exit(2)' .claude/hooks/grounding_check.py` → 2 ✓
- `grep -v '^#' .claude/hooks/grounding_check.py | grep -c 'sys.exit(1)'` → 0 ✓
- Rule 3 (CR-03) at lines 56–57: `if draft and not markers_in_draft and not citations: return False, "grounding:no_citations"` — empty-citation bypass closed ✓

**Subprocess proofs (manual run):**

| Hook | Payload | Exit | Result |
|------|---------|------|--------|
| pre_send_guard | body="we will refund you [KB-1]" | 2 | BLOCK ✓ |
| pre_send_guard | body="Your order ships soon [KB-1]" | 0 | PASS ✓ |
| grounding_check | body="Your order is processing", citations=[] | 2 | BLOCK ✓ (CR-03) |
| grounding_check | body="Your order [KB-1] is on its way", citations=[{id:KB-1}] | 0 | PASS ✓ |

**injection_screen.py fail-closed (CR-04):**

- `_extract_body()` (line 134): `raise ValueError("injection_screen:no_body_field")` when neither "prompt" nor "body" present ✓
- `main()` except (line 152–154): escalates with `sys.exit(1)` (correct — UserPromptSubmit context) ✓
- Note: injection_screen uses exit 1 (not 2) which is correct for its UserPromptSubmit binding; it is NOT a PreToolUse@submit_reply hook. The D-14 guarantee for the runner path is via cs_team_demo.py mandatory pre-screen (documented as the enforced path when no SubagentStart event is available). ✓

**pii_redact.py (CR-05):**

- `raw_stdin` captured before `json.loads` (line 57) ✓
- Error path: re-serializes `payload` if parsed, else prints `raw_stdin` (line 89–95) ✓
- `grep -c 'print("{}")' .claude/hooks/pii_redact.py` → 0 ✓
- D-04 PostToolUse timing limitation documented in module docstring ✓

---

### Subprocess Test Suite (TEST GAP Closed)

**File:** `tests/cs_team/test_hooks_subprocess.py`

**Run result:** `16 passed in 1.05s`

| Class | Tests | Coverage |
|-------|-------|---------|
| TestPreSendGuardSubprocess | 3 | commitment → 2; clean → 0; replace → 2 |
| TestGroundingCheckSubprocess | 4 | ungrounded → 2; empty-citation CR-03 → 2; unknown citation → 2; grounded → 0 |
| TestEscalationGateSubprocess | 5 | write-high-risk → read exit 2; no state file → 2; CS_RUN_ID unset → 2; clean → 0; WRITE NO-OP no disk write |
| TestInjectionScreenSubprocess | 4 | instruction-override → non-zero; missing body CR-04 → non-zero; clean → 0; role-override → non-zero |

**Subprocess proof (not in-process):** `grep -c 'subprocess' tests/cs_team/test_hooks_subprocess.py` → 11; `grep -c 'returncode' tests/cs_team/test_hooks_subprocess.py` → 62; `grep -c 'returncode == 2'` → 22; `grep -c 'returncode == 0'` → 13. All counts exceed acceptance thresholds. ✓

---

### settings.json Hook Wiring (§4a Chokepoint)

| Event | Matcher | Hook chain |
|-------|---------|-----------|
| PreToolUse | submit_reply | grounding_check → pre_send_guard → escalation_gate ✓ |
| PostToolUse | * | escalation_gate (WRITE side) → pii_redact ✓ |
| SubagentStop | * | escalation_gate (WRITE side) ✓ |
| UserPromptSubmit | * | injection_screen ✓ |

Chain order correct per CLAUDE.md §4a. `"CS_RUN_ID": "${CS_RUN_ID}"` in env block. ✓

---

### Required Artifacts

| Artifact | Status | Evidence |
|----------|--------|---------|
| `.claude/hooks/pre_send_guard.py` | ✓ VERIFIED | 2x sys.exit(2), 0x sys.exit(1), subprocess BLOCK=2 |
| `.claude/hooks/grounding_check.py` | ✓ VERIFIED | 2x sys.exit(2), CR-03 Rule 3, subprocess BLOCK=2 |
| `.claude/hooks/escalation_gate.py` | ✓ VERIFIED | _state_path/_write/_read helpers; READ exits 2 fail-closed; 19x CS_RUN_ID |
| `.claude/hooks/injection_screen.py` | ✓ VERIFIED | _extract_body raises on missing field; fail-closed |
| `.claude/hooks/pii_redact.py` | ✓ VERIFIED | no print("{}"), raw_stdin passthrough, D-04 limitation documented |
| `.claude/settings.json` | ✓ VERIFIED | §4a chain intact; CS_RUN_ID in env block |
| `scripts/cs_team_demo.py` | ✓ VERIFIED | CS_RUN_ID lifecycle (generate/export/finally-cleanup); mandatory pre-screen; raw_body_for_check removed |
| `tests/cs_team/test_hooks_subprocess.py` | ✓ VERIFIED | 16 subprocess tests, 16 PASSED, returncode==2 22x, returncode==0 13x |

---

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| pre_send_guard.py main() | Claude Code BLOCK | sys.exit(2) on commitment + on except | ✓ WIRED |
| grounding_check.py main() | Claude Code BLOCK | sys.exit(2) on ungrounded + on except; Rule 3 CR-03 | ✓ WIRED |
| escalation_gate.py READ side | per-run state file | _read_signals() → exit 2 on None/signal | ✓ WIRED |
| escalation_gate.py WRITE side | per-run state file | _write_signals() OR-merges at PostToolUse/SubagentStop | ✓ WIRED |
| settings.json env.CS_RUN_ID | hook subprocesses | "${CS_RUN_ID}" forwarding | ✓ WIRED |
| cs_team_demo.py run_ticket() | escalation_gate state | os.environ["CS_RUN_ID"] = run_id before CLI; finally cleanup | ✓ WIRED |

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| escalation_gate.py:278 | `sys.exit(1)` in outer except (cannot detect veto context after json.load fails) | Warning | Defense-in-depth gap only; grounding_check + pre_send_guard precede in chain and both exit 2 on error |

No TBD/FIXME/XXX markers found in modified files.

---

### Human Verification Required

#### 1. Live Session: Stateful Veto Blocks submit_reply in Real Runtime

**Test:** Start a Claude Code session with the cs-agent team, export `CS_RUN_ID=live-test-001`, run a ticket that triggers a high-risk signal at a PostToolUse stage, then observe whether the cs-lead's `submit_reply` call is blocked.
**Expected:** Claude Code reports the PreToolUse hook returned exit 2; the tool is blocked; the cs-lead receives an escalate verdict; no reply is posted to Freshdesk.
**Why human:** Requires an active Claude Code session with the agent team. The deployed hook dispatch chain (Claude Code runtime → hook subprocess → exit code → tool block) cannot be verified by grep or in-process tests. The subprocess tests confirm the exit codes but not Claude Code's runtime enforcement of them.

#### 2. Live Runner: Injection Pre-Screen Short-Circuits Before Subagent

**Test:** Run `python scripts/cs_team_demo.py --ticket injection` with `use_live_claude=True` (or any live mode) and verify the body is never delivered to any subagent.
**Expected:** `run_ticket()` returns `{"action": "escalate", "reason": "injection:..."}` before any Claude Code subprocess is launched; no subagent receives the ticket body.
**Why human:** The simulation path (`use_live_claude=False`) confirms the Python pre-screen in isolation. The live runner path requires a real Claude Code environment to confirm no subagent task delivery event carries the unscreened body.

---

### Gaps Summary

No automated gaps remain. All 4/4 must-have success criteria are verified by code inspection and subprocess execution. Two human verification items are pending — both require a live Claude Code session and cannot be resolved by static analysis or unit tests. These are expected residual items for any hook-based enforcement system.

---

*Verified: 2026-06-03T06:15:00Z*
*Verifier: Claude (gsd-verifier) — re-verification after gap-closure waves 04-04 and 04-05*
