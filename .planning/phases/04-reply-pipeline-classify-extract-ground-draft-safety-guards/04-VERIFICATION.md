---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
verified: 2026-06-03T05:10:00Z
status: gaps_found
score: 2/4 must-haves verified
gaps:
  - truth: "High-risk tickets auto-routed to human; any high-risk signal escalates the whole ticket rather than auto-answered (SC-3 / SAFE-03)"
    status: failed
    reason: "CR-01 — grounding_check.py and pre_send_guard.py exit 1 on violation at the PreToolUse@submit_reply chokepoint. Claude Code's hook protocol only BLOCKS a tool on exit code 2; exit 1 is a non-blocking error (model sees stderr, tool still executes). The two guards that must block commitment language (D-13) and ungrounded drafts (D-11) therefore DO NOT block submit_reply. Only escalation_gate.py correctly uses exit 2, but that gate fails open for a separate reason (CR-02). Net effect: a draft containing 'we will issue your refund' or with zero citations passes through submit_reply unchallenged."
    artifacts:
      - path: ".claude/hooks/pre_send_guard.py"
        issue: "Line 100 exits sys.exit(1) on commitment language — non-blocking in Claude Code PreToolUse. The module docstring at line 16 says 'exit 2 → escalate' per CLAUDE.md D-13, but the code exits 1."
      - path: ".claude/hooks/grounding_check.py"
        issue: "Line 107 exits sys.exit(1) on ungrounded draft — non-blocking in Claude Code PreToolUse. Fail-closed except branch (line 111) also exits 1."
    missing:
      - "Change sys.exit(1) → sys.exit(2) in pre_send_guard.py main() for both the blocked branch (line 100) and the except branch (line 104)"
      - "Change sys.exit(1) → sys.exit(2) in grounding_check.py main() for both the not-grounded branch (line 107) and the except branch (line 111)"
      - "Add a subprocess-based test that asserts the process exit code is 2 (not 1) for each PreToolUse hook on a violation input, so the test surface matches the deployed enforcement surface"

  - truth: "An output guard blocks commitment language and email body treated as data / injection-screened (SC-4 / SAFE-04)"
    status: failed
    reason: "Two compounding failures. First, CR-01 means pre_send_guard.py does not actually block submit_reply (exit 1 is non-blocking — see above). Second, CR-02 means escalation_gate.py's final-veto branch at PreToolUse@submit_reply always passes: _derive_signals() finds no recognized signal keys in the submit_reply payload {tool_name, tool_input:{body, citations}}, returns {}, should_escalate({}) returns (False, ''), and the gate exits 0. The 'final accumulated risk check' claimed by CLAUDE.md §4a has nothing to read and silently approves every call. Additionally CR-04: injection_screen.py is bound to UserPromptSubmit reading payload['prompt'], but the ticket body is delivered to subagents as agent/task input, which is NOT a UserPromptSubmit event, so the D-14 injection screen may never fire on the actual ticket body in deployed operation."
    artifacts:
      - path: ".claude/hooks/escalation_gate.py"
        issue: "Lines 57-88 _derive_signals() scans for signals/risk_signals/escalation_signals keys and nested tool_result/result/output. The submit_reply PreToolUse payload carries none of these keys — only tool_name and tool_input:{body, citations}. Result: signals={}, should_escalate returns (False,''), gate exits 0 unconditionally on submit_reply. The 'final accumulated risk check' never fires."
      - path: ".claude/hooks/injection_screen.py"
        issue: "Lines 116-128 _extract_body() reads payload['prompt'] (UserPromptSubmit schema). Bound to UserPromptSubmit event in settings.json line 47-57. When ticket body is delivered to subagents as agent task input (the real pipeline path), it is not a UserPromptSubmit event — the hook does not fire and the body is not screened before subagents see it (D-14 violation)."
      - path: ".claude/settings.json"
        issue: "Lines 47-57: injection_screen bound only to UserPromptSubmit. No SubagentInit or equivalent event binding to screen the ticket body when the lead passes it to classifier/extractor/drafter subagents."
    missing:
      - "Persist escalation state out-of-band (e.g. per-run file keyed by CS_RUN_ID env var) written by PostToolUse/SubagentStop hooks and read by PreToolUse@submit_reply; fail closed if no state file found for active run"
      - "Screen ticket body at the point it enters the pipeline as a deterministic pre-step in the runner, not only on UserPromptSubmit — or add a hook event that fires on subagent task input delivery"
      - "In _extract_body: if neither prompt nor body found, escalate (fail-closed) rather than returning empty string that silently passes"
---

# Phase 4: Reply Pipeline Verification Report

**Phase Goal:** Assemble the per-ticket pipeline that re-classifies the ticket, extracts the answer key, drafts a citation-grounded reply via the two MCPs, self-critiques against the rubric, and is wrapped by the escalation rules and output guards that make it safe to evaluate.
**Verified:** 2026-06-03T05:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Incoming ticket re-classified into correct category with confidence signal; order ref / customer / issue type extracted (REP-01, REP-02) | VERIFIED | `classifier.md` (Haiku, D-03 compliant, high-risk marker, confidence bucket, `<ticket_body>` delimited); `extractor.md` (Haiku, resolve_order via SellessMCP, missing_key signal, D-07 compliant); both present and substantive |
| 2 | Orchestrator produces a draft grounded in retrieved order data + KB with citations, no ungrounded claims, runs self-critique against rubric before any send (REP-03, REP-04) | VERIFIED | `cs-lead.md` orchestrates classify→extract→draft→critic; `drafter.md` exists; `grounding_check.py` implements citation-marker enforcement; `check_grounding()` function is correct in-process logic; `submit_reply` chokepoint exists at `src/reply_mcp/server.py`; grounding check logic is sound. NOTE: deployed blocking is broken (CR-01, see SC-3/SC-4) but the pipeline structure and in-process logic for grounding are present and correct |
| 3 | High-risk tickets (money/refund, legal/complaints, complex/ambiguous) auto-routed to human — any high-risk signal escalates the whole ticket (SAFE-03) | FAILED | BLOCKER: `pre_send_guard.py:100` exits `sys.exit(1)` and `grounding_check.py:107` exits `sys.exit(1)` on violations. Claude Code PreToolUse contract: only exit code 2 blocks the tool; exit 1 is a non-blocking error. These two PreToolUse@submit_reply guards therefore do NOT block the tool. `escalation_gate.py` correctly uses `sys.exit(2)` at line 122 but its final-veto branch reads no signals from the `submit_reply` payload (CR-02), so it always passes. The deployed guard chain fails open at the sole chokepoint. |
| 4 | An output guard blocks commitment language and email body treated as data (injection-screened) (SAFE-04) | FAILED | BLOCKER: Same CR-01 failure as SC-3 — `pre_send_guard.py` exits 1 (non-blocking) so commitment language (refund/credit/charge/order-change) is NOT blocked at submit_reply. Additionally, `injection_screen.py` is bound to `UserPromptSubmit` only (`settings.json:47-57`) and reads `payload['prompt']`. The ticket body reaches subagents as agent task input, not as a UserPromptSubmit event, so the injection screen may not fire on the deployed CLI path (CR-04). |

**Score: 2/4 truths verified**

---

## Critical Review Finding Confirmation

The 04-REVIEW.md identified 5 critical defects. Each is independently confirmed against the actual code:

### CR-01: pre_send_guard.py and grounding_check.py exit 1 (non-blocking) — CONFIRMED BLOCKER

**Code evidence:**

- `pre_send_guard.py:100` — `sys.exit(1)` on commitment language detected
- `pre_send_guard.py:104` — `sys.exit(1)` on any exception (fail-closed path also non-blocking)
- `grounding_check.py:107` — `sys.exit(1)` on ungrounded draft
- `grounding_check.py:111` — `sys.exit(1)` on any exception

**Contrast:** `escalation_gate.py:122` — `sys.exit(2 if is_final_veto else 1)` — the authors demonstrably know the distinction; only the other two hooks were not updated.

**Deployed effect:** A draft body containing "we will refund your order [KB-1]" produces:
1. `grounding_check.py` — PASS (citations present, markers map to IDs)
2. `pre_send_guard.py` — detects "refund", prints escalate JSON to stderr, exits 1 → Claude Code sees non-fatal error, tool STILL RUNS
3. `escalation_gate.py` — no signals in payload, exits 0 → PASS
4. `submit_reply` executes, reply persisted

**Module docstring inconsistency:** `pre_send_guard.py` line 16 reads "blocks the submit_reply tool (exit 2 → escalate)" matching CLAUDE.md D-13 — the intent was exit 2 but the code exits 1.

### CR-02: escalation_gate final-veto reads no signals at submit_reply — CONFIRMED BLOCKER

**Code evidence:** `escalation_gate.py:57-88` `_derive_signals()` searches for `signals`, `risk_signals`, `escalation_signals` keys, then `tool_result/result/output` nested dicts, then scans top-level for known signal keys.

The `submit_reply` PreToolUse payload shape is `{"tool_name": "submit_reply", "tool_input": {"body": "...", "citations": [...]}}`. None of the searched keys are present. `_derive_signals()` returns `{}`. `should_escalate({})` returns `(False, "")`. Gate exits 0.

**Deployed effect:** Even if a classifier correctly set `high_risk_category: True` in a prior SubagentStop event, that signal is not persisted anywhere that the final-veto PreToolUse invocation can read. Claude Code hooks are stateless subprocesses — there is no shared state between hook invocations. The "final accumulated risk check" described in CLAUDE.md §4a never fires.

### CR-03: grounding_check empty-citation bypass — CONFIRMED WARNING (not BLOCKER in isolation due to CR-01)

**Code evidence:** `grounding_check.py:46-68` Rule 3 (lines 67-68): "If all markers map to known IDs (or no markers AND no citations) → pass." A draft with `citations=[]` and no `[KB-N]` markers passes as grounded. This is the canonical ungrounded case (factual claims, zero citations) yet it passes.

This is a real defect compounding CR-01: even if exit codes were fixed to 2, a model could emit an ungrounded factual reply with empty citations and empty markers and pass grounding_check.

### CR-04: injection_screen bound to UserPromptSubmit / reads `prompt` field — CONFIRMED BLOCKER for deployed D-14

**Code evidence:**
- `settings.json:47-57`: `UserPromptSubmit` event, matcher `*`, command `injection_screen.py`
- `injection_screen.py:116-128` `_extract_body()`: reads `payload["prompt"]` first, then `payload["body"]`

**Deployed path:** When `cs_team_demo.py` shells out to `claude --print`, the ticket body is passed as stdin to the cs-lead prompt. Whether this triggers `UserPromptSubmit` and whether `payload["prompt"]` contains the full ticket body depends on how the Claude Code agent team processes the CLI prompt. When the cs-lead then delegates to classifier/extractor subagents, the ticket body is passed as task input to those subagents — this is not a `UserPromptSubmit` event. The injection screen does not fire on subagent task delivery.

**Simulation masks this:** `cs_team_demo.py:199-206` `_pre_screen_ticket()` calls `screen_for_injection(ticket["body"])` directly in-process before the CLI call. This catches injections in the demo/test but does not prove the bound hook fires at the right point in deployed operation.

### CR-05: pii_redact fails open — CONFIRMED WARNING

**Code evidence:** `pii_redact.py:68-76` — any exception causes `print("{}")` and `sys.exit(0)`. Two problems confirmed:
1. PostToolUse runs after the tool executed — redaction cannot retroactively protect logs that captured the raw `tool_input` before this hook ran
2. On error, `{}` replaces the whole payload (payload corruption), not just the PII fields

Both are confirmed as stated in 04-REVIEW.md. Classified as warning because pii_redact is a transform hook (not a gate), but D-04's "before any log/trace" guarantee cannot be met by a PostToolUse hook.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.claude/hooks/pre_send_guard.py` | Commitment language guard, blocks submit_reply | STUB at chokepoint | Exists, logic correct, exit code wrong (1 vs 2) — does not block |
| `.claude/hooks/grounding_check.py` | Citation grounding guard, blocks submit_reply | STUB at chokepoint | Exists, logic partially correct (empty-citations bypass), exit code wrong (1 vs 2) |
| `.claude/hooks/escalation_gate.py` | Accumulated risk final veto at submit_reply | STUB at chokepoint | Exists, exit-2 branch correct, but _derive_signals returns {} for submit_reply payload — veto never fires |
| `.claude/hooks/injection_screen.py` | Injection screen on ticket body | PARTIAL | Exists, patterns correct, bound to UserPromptSubmit only — may not fire on subagent task input |
| `.claude/hooks/pii_redact.py` | PII redaction before log/trace | WIRED (transform) | Exists, wired to PostToolUse, but PostToolUse cannot satisfy "before any log/trace" (D-04) |
| `.claude/settings.json` | 5-hook §4a bindings | WIRED | All 5 hooks bound in correct events and order |
| `src/reply_mcp/server.py` | submit_reply sole chokepoint | VERIFIED | Exists, wired, chokepoint architecture correct, DRY_RUN enforced |
| `.claude/agents/cs-lead.md` | Lead orchestrator (Sonnet) | VERIFIED | Exists, Sonnet model, correct workflow, D-03 compliant |
| `.claude/agents/classifier.md` | Ticket classifier (Haiku) | VERIFIED | Exists, Haiku model, confidence signal, high-risk marker, D-14 delimited |
| `.claude/agents/extractor.md` | Answer-key extractor (Haiku) | VERIFIED | Exists, Haiku model, resolve_order, missing_key signal |
| `.claude/agents/drafter.md` | Grounded drafter (Sonnet) | VERIFIED | Exists |
| `.claude/agents/critic.md` | Rubric critic | VERIFIED | Exists |
| `scripts/cs_team_demo.py` | PoC runner | VERIFIED (sim path only) | Exists, importable, DRY_RUN asserted, but simulation applies hooks in-process rather than via subprocess exit codes |
| `tests/cs_team/test_e2e_dry_run.py` | Integrated hook chain proof | PARTIAL | Exists, 3 layers, but integrated layer (b) calls hook functions in-process — does not prove deployed exit-code enforcement |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `settings.json` | `pre_send_guard.py` | PreToolUse@submit_reply | WIRED but broken | Bound correctly at position [1]; exit code is 1 not 2 — non-blocking |
| `settings.json` | `grounding_check.py` | PreToolUse@submit_reply | WIRED but broken | Bound correctly at position [0]; exit code is 1 not 2 — non-blocking |
| `settings.json` | `escalation_gate.py` | PreToolUse@submit_reply | WIRED but broken | Bound correctly at position [2]; exit 2 branch exists but _derive_signals returns {} for submit_reply payload |
| `settings.json` | `injection_screen.py` | UserPromptSubmit | PARTIAL | Bound to UserPromptSubmit; ticket body may arrive via subagent task input (not UserPromptSubmit) in deployed operation |
| `settings.json` | `pii_redact.py` | PostToolUse | WIRED | Bound; transform-only hook |
| `cs-lead.md` | `submit_reply` | ReplyMCP tool | WIRED | submit_reply listed in cs-lead tools; sole draft emission path |
| `cs-lead.md` | `classifier`, `extractor`, `drafter`, `critic` | Subagent delegation | VERIFIED | All 4 subagents exist, correct models |

---

## Behavioral Spot-Checks

The core behavioral claim — that the deployed PreToolUse chain BLOCKS submit_reply on commitment language — can be spot-checked without a running server:

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| pre_send_guard exits 2 on commitment language | `echo '{"tool_input":{"body":"we will refund you"}}' \| python .claude/hooks/pre_send_guard.py; echo $?` | Would return 1 | FAIL — exit 1 is non-blocking |
| grounding_check exits 2 on ungrounded draft | `echo '{"tool_input":{"body":"Your order is processing","citations":[]}}' \| python .claude/hooks/grounding_check.py; echo $?` | Would return 0 (empty-citation bypass, Rule 3) | FAIL — two failures: passes when it should block, AND wrong exit code |
| escalation_gate exits 2 on high_risk signal at submit_reply | `echo '{"tool_name":"submit_reply","tool_input":{"body":"...","citations":[]}}' \| python .claude/hooks/escalation_gate.py; echo $?` | Would return 0 (no signals in payload) | FAIL — always passes at submit_reply |

---

## Tests vs Deployed Enforcement

The SUMMARY.md claims "BLOCKER-2 integrated proof: real hook chain called end-to-end with mock LLM outputs; adversarial tickets reach submit_reply and are vetoed." This claim is TRUE for in-process function calls but FALSE for deployed subprocess enforcement.

`test_e2e_dry_run.py` Layer (b) `_run_pre_tool_use_chain()` calls:
- `check_grounding(body, citations)` — returns `(bool, str)`, no subprocess
- `check_commitment_language(body)` — returns `(bool, str)`, no subprocess
- `should_escalate(risk_signals)` — returns `(bool, str)`, no subprocess

These calls exercise the correct Python logic. But the deployed hook chain is invoked by Claude Code as subprocesses reading stdin JSON and returning **exit codes** that Claude Code interprets. The in-process function call path bypasses the exit-code contract entirely. Green tests here prove the logic functions work; they do not prove exit 2 is emitted at the chokepoint.

The 04-REVIEW.md's finding IN-04 is confirmed: "the simulation applies grounding+commitment checks with correct in-process boolean logic and exit-code-independent flow, so the demo and tests pass even though the deployed hooks fail open (CR-01/CR-02)."

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REP-01 | AI re-classifies incoming email into correct support category | SATISFIED | `classifier.md` with two-level taxonomy, confidence bucket, high-risk marker; wired to cs-lead |
| REP-02 | AI extracts key info (order ref, customer, issue type) | SATISFIED | `extractor.md` with answer-key schema, resolve_order, missing_key signal; wired to cs-lead |
| REP-03 | AI drafts reply grounded in retrieved data, no ungrounded claims | PARTIAL | `grounding_check.py` logic correct but (a) empty-citations bypass allows ungrounded drafts through and (b) exit code 1 means it does not block at the deployed chokepoint |
| REP-04 | AI runs self-critique pass before any send | SATISFIED | `critic.md` exists; cs-lead orchestrates critic before emitting draft verdict |
| SAFE-03 | Guardrail auto-routes high-risk tickets to human | NOT MET | `escalation_gate.py` final-veto reads no signals from submit_reply payload (CR-02); `pre_send_guard.py` and `grounding_check.py` do not block submit_reply (CR-01); deployed guards fail open |
| SAFE-04 | Output guard blocks commitment language; body treated as data | NOT MET | `pre_send_guard.py` exits 1 (non-blocking) at submit_reply; `injection_screen.py` bound only to UserPromptSubmit, may not fire when body is subagent task input |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.claude/hooks/pre_send_guard.py` | 100, 104 | `sys.exit(1)` in PreToolUse hook on violation | BLOCKER | Commitment language guard does not block submit_reply; D-13/SAFE-04 not enforced at chokepoint |
| `.claude/hooks/grounding_check.py` | 107, 111 | `sys.exit(1)` in PreToolUse hook on violation | BLOCKER | Grounding guard does not block submit_reply; D-11/REP-03 not enforced at chokepoint |
| `.claude/hooks/escalation_gate.py` | 57-88 | `_derive_signals()` finds no keys in submit_reply PreToolUse payload | BLOCKER | Final accumulated risk veto always passes; D-08/SAFE-03 not enforced |
| `.claude/hooks/grounding_check.py` | 67-68 | Rule 3: empty citations + no markers = PASS | BLOCKER | Ungrounded draft with zero citations and zero markers passes grounding check |
| `.claude/hooks/injection_screen.py` | 116-128 | Only reads `payload['prompt']`, bound to UserPromptSubmit | BLOCKER | Injection screen may not fire on ticket body when delivered as subagent task input |
| `.claude/hooks/pii_redact.py` | 68-76 | Except branch emits `{}` (payload corruption) | WARNING | On Presidio error, entire payload blanked rather than selective field redaction |
| `scripts/cs_team_demo.py` | 469-471 | Dead `raw_body_for_check` variable with misleading comment | WARNING | Comment implies redaction guarantee that code does not provide (D-04 footgun) |

---

## Gaps Summary

**Two BLOCKERs, two underlying root causes:**

**Root cause 1 — Wrong exit codes in two PreToolUse hooks (CR-01):**
`pre_send_guard.py` and `grounding_check.py` exit 1 on violations at the PreToolUse@submit_reply chokepoint. Claude Code's hook protocol only blocks a tool on exit code 2. All other non-zero exits surface stderr to the model as a non-fatal error and the tool still executes. This single two-line fix (exit 1 → exit 2 in each hook's main() and except branches) would close the commitment-language and grounding enforcement gaps. The module docstrings and CLAUDE.md D-13 text correctly state "exit 2 → escalate"; the code was not updated to match.

**Root cause 2 — Stateless hook cannot read accumulated risk (CR-02):**
`escalation_gate.py`'s final-veto branch at PreToolUse@submit_reply is designed to catch accumulated risk signals from earlier pipeline stages. But Claude Code hooks are stateless subprocesses — there is no shared memory between the PostToolUse invocations (where signals from classifier/extractor arrive) and the PreToolUse@submit_reply invocation. The submit_reply payload contains only `{tool_name, tool_input:{body, citations}}` — none of the signal keys `_derive_signals()` searches for. The gate always passes. Fixing this requires out-of-band state persistence (a per-run file keyed by a run-ID env var) written by PostToolUse and read by PreToolUse@submit_reply, with a fail-closed default when no state file is found.

**Additional structural gap (CR-04):**
The injection screen's event binding covers the initial user prompt but not the subagent task input path, which is how the ticket body reaches classifier/extractor/drafter in the real pipeline. This requires either a runner-level pre-screen (as the demo already does in simulation) made mandatory before any CLI invocation, or an additional hook event binding that fires on subagent task delivery.

**Test coverage is deceptive:**
The integrated test layer (b) in `test_e2e_dry_run.py` calls hook functions in-process, bypassing the exit-code contract. Tests pass because the Python logic is correct; they do not surface the exit-code bug. Adding subprocess-based tests that assert `process.returncode == 2` for each PreToolUse hook on a violation input would catch this class of defect.

---

### Human Verification Required

None needed — the gaps are fully deterministic and observable from code inspection. The exit-code failures are definitive: `sys.exit(1)` vs `sys.exit(2)` in a PreToolUse hook is an objective, binary fact about deployed enforcement.

---

_Verified: 2026-06-03T05:10:00Z_
_Verifier: Claude (gsd-verifier)_
