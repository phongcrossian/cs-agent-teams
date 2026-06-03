---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
reviewed: 2026-06-03T04:23:59Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - .claude/hooks/injection_screen.py
  - .claude/hooks/pre_send_guard.py
  - .claude/hooks/escalation_gate.py
  - .claude/hooks/grounding_check.py
  - .claude/hooks/pii_redact.py
  - .claude/settings.json
  - src/reply_mcp/server.py
  - src/config.py
  - scripts/cs_team_demo.py
  - tests/cs_team/conftest.py
  - .claude/agents/cs-lead.md
  - .claude/agents/drafter.md
  - .claude/agents/classifier.md
findings:
  critical: 5
  warning: 7
  info: 4
  total: 16
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-03T04:23:59Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 4 implements a safety-critical, fail-closed email auto-reply pipeline gated by five
deterministic hooks. The architecture is sound in intent — single chokepoint, OR-gate
escalation, deterministic regex guards. However, adversarial review found **multiple ways the
deterministic guards fail OPEN rather than closed**, defeating the core invariants:

1. **The PreToolUse hook exit-code contract is wrong** (CR-01). The Claude Code PreToolUse hook
   protocol blocks a tool on **exit code 2**, not exit code 1. `grounding_check.py` and
   `pre_send_guard.py` — bound on `submit_reply` — exit **1** on a detected violation. In Claude
   Code, a non-zero exit other than 2 is a *non-blocking* error: stderr is surfaced to the model
   but the tool **still runs**. This means commitment language and ungrounded drafts are NOT
   actually blocked at the chokepoint. This breaks D-10, D-11, and D-13 simultaneously.

2. **`escalation_gate.py`'s "final-risk veto" reads signals the lead controls, with no fallback to
   fail-closed** (CR-02). On `submit_reply` the gate derives signals from the payload; if no
   signal keys are present (the normal case — `submit_reply(body, citations)` carries no risk
   signals), `should_escalate` returns `(False, "")` and the gate PASSES. The "final accumulated
   risk check" has nothing to read and silently approves.

3. **`grounding_check.py` accepts attacker-spoofable citation markers** (CR-03). A draft body
   echoing untrusted ticket text that happens to contain `[KB-1]` passes grounding as long as the
   citations list (model-supplied, same untrusted lineage) contains an `id: "KB-1"`. There is no
   verification that the cited text actually supports the claim, nor that the citation came from a
   real MCP retrieval this run — defeating D-11's "cited sources must be retrieved in this run."

4. **`injection_screen` is bound on `UserPromptSubmit` but reads `prompt`, while the actual
   ticket body is delivered to subagents as tool/agent input** (CR-04) — the untrusted body may
   never pass through the screen on the real CLI path.

5. **`pii_redact.py` fails OPEN and the demo logs partially-controlled content** (CR-05 / WR-04).

The local simulation path in `cs_team_demo.py` masks all of these because it re-implements the
checks in-process with correct boolean logic — so tests are green while the deployed hook chain
(exit codes, binding events) does not enforce the same guarantees. **Green tests here are
evidence the simulation is correct, not that the chokepoint is.**

## Critical Issues

### CR-01: PreToolUse guards exit 1 (non-blocking) instead of 2 — commitment + grounding guards DO NOT block submit_reply

**File:** `.claude/hooks/grounding_check.py:107`, `.claude/hooks/pre_send_guard.py:101`
**Issue:**
Claude Code's hook protocol treats PreToolUse exit codes as: `0` = allow, `2` = **block the
tool**, any other non-zero = non-blocking error (model sees stderr, tool still executes). Both
guards bound on `submit_reply` exit `1` on violation:

- `pre_send_guard.py:98-101` — commitment language detected → `sys.exit(1)`
- `grounding_check.py:105-108` — not grounded → `sys.exit(1)`

`escalation_gate.py` correctly uses `sys.exit(2)` in the final-veto branch (line 122), proving the
authors know the 2-vs-1 distinction exists — but the other two PreToolUse hooks were not updated.
Net effect: a draft containing "I'll issue your refund" or with zero citations is **not blocked**;
`submit_reply` runs and the reply is persisted (and in LIVE mode would be sent). This silently
breaks D-10, D-11, and D-13 at the one place they are supposed to be hard-enforced.

The module docstrings even disagree with the code: `pre_send_guard.py:16` says "blocks the
submit_reply tool (exit 2 → escalate)" per CLAUDE.md §D-13, but the code exits 1.

**Fix:**
```python
# pre_send_guard.py main() and grounding_check.py main():
if blocked:                      # (or: if not grounded:)
    print(json.dumps({"action": "escalate", "reason": reason}))
    sys.exit(2)                  # PreToolUse: 2 = BLOCK the tool (was 1)
```
Also fix the fail-closed `except` branches in both PreToolUse hooks to `sys.exit(2)` — a crashing
guard currently exits 1 and therefore fails OPEN at the chokepoint. Add a test that asserts the
*process exit code* (subprocess), not just the in-process boolean return, for each PreToolUse hook.

### CR-02: escalation_gate final-veto reads no signals on submit_reply → silently passes (fail-open)

**File:** `.claude/hooks/escalation_gate.py:57-88`, `91-124`
**Issue:**
On `submit_reply`, `_derive_signals` looks for `signals`/`risk_signals`/`escalation_signals` dicts,
then nested under `tool_result`/`result`/`output`, then scans top-level for known signal keys. The
`submit_reply(body, citations)` PreToolUse payload is `{"tool_name":"submit_reply",
"tool_input":{"body":..., "citations":[...]}}` — it carries **none** of those keys. So
`_derive_signals` returns `{}`, `should_escalate({})` returns `(False, "")`, and the gate exits 0
(PASS). The "final accumulated risk check" that CLAUDE.md §4a relies on to veto a draft when
upstream risk was detected has nothing to read and approves unconditionally.

This is a fail-open: the entire premise of the third PreToolUse hook (catch accumulated risk before
the irreversible send) does not function. Claude Code hooks are stateless subprocesses; there is no
shared "accumulated risk state" being passed to this invocation, and nothing persists it between
the PostToolUse/SubagentStop invocations (where signals DO arrive) and this PreToolUse invocation.

**Fix:**
The gate cannot rely on in-band signals at the chokepoint because the chokepoint payload has none.
Persist escalation state out-of-band (e.g. a per-run file under a run-id env var that PostToolUse
writes and PreToolUse reads), and **fail closed if no state file is found** for the active run:
```python
if is_final_veto:
    state = _load_run_state(os.environ.get("CS_RUN_ID"))
    if state is None:           # no upstream gate ran → cannot prove safe
        print(json.dumps({"action": "escalate", "reason": "escalate:no_risk_state"}))
        sys.exit(2)
    signals = state.get("signals", {})
```
At minimum, document that without a state-passing mechanism this third hook is decorative, and do
not claim §4a's "final accumulated risk check" is enforced.

### CR-03: grounding_check accepts spoofed citation markers — no source-fidelity or provenance check

**File:** `.claude/hooks/grounding_check.py:34-68`
**Issue:**
`check_grounding` passes if every `[KB-N]`/`[SEL-N]` marker in the draft has a matching `id` in the
`citations` list, OR if there are no citations and no markers. Two exploitable gaps:

1. **Provenance not verified.** Both `body` and `citations` are supplied by the (LLM, downstream of
   attacker-controlled ticket text) caller of `submit_reply`. A model that hallucinates a fact and
   emits `citations=[{"id":"KB-1","text":"<anything>"}]` with `...the warranty is 5 years [KB-1]`
   passes. There is no check that `KB-1` corresponds to an actual `semantic_search`/`get_template`
   result retrieved in this run, which is exactly what D-11 requires ("citing sources not retrieved
   in this run is forbidden").
2. **Empty-citations bypass.** If the draft contains **no markers and no citations**, the function
   returns `(True, "")` (line 67-68, Rule 3). A draft that simply makes ungrounded factual claims
   with zero citations and an empty `citations=[]` list PASSES. D-11 says "every factual claim MUST
   carry an inline citation" — a claim-bearing draft with zero citations is the canonical violation,
   yet it is graded as grounded. The check only fires when citations are *present but uncited*.

Combined with CR-01 (exit 1, non-blocking), an ungrounded draft is doubly un-blocked.

**Fix:**
- Require `citations` non-empty for any draft (the tool signature implies it; enforce it):
  `if not citations: return False, "grounding:no_citations_supplied"`.
- Verify each citation `id` against the run's actual retrieval log (persisted by the Knowledge/
  Selless MCP tool calls for this run), not just self-consistency within the payload.
- Keep the unknown-marker check, but treat "claims present, markers absent" as fail. Detecting
  "factual claim" deterministically is hard; the safe deterministic proxy is "non-empty draft body
  ⇒ at least one citation marker required."

### CR-04: injection_screen binds UserPromptSubmit/`prompt`, but the untrusted ticket body reaches subagents as agent input — body may never be screened

**File:** `.claude/settings.json:47-57`, `.claude/hooks/injection_screen.py:116-128`
**Issue:**
The screen is bound only to `UserPromptSubmit` with matcher `*`, and `_extract_body` reads
`payload["prompt"]`. On the real CLI path, the cs-lead receives the ticket and delegates to
`classifier`/`extractor`/`drafter` subagents; the untrusted `<ticket_body>` is passed as **subagent
task input**, which is not a `UserPromptSubmit` event. So an injection that arrives via the ticket
body (the documented attack surface, D-14) is screened only if the entire body happens to be the
top-level user prompt. In the demo this is hidden because `_pre_screen_ticket`
(`cs_team_demo.py:199-206`) calls `screen_for_injection(ticket["body"])` directly — but that is the
simulation, not the bound hook. The deployed binding does not guarantee the body is screened before
a subagent sees it, violating D-14 step 2 ("Screened by injection_screen.py before any agent sees
it").

Additionally `_extract_body` only checks `prompt` then `body`; if the harness wraps the prompt in
`messages`/`content` the body silently extracts to `""` and the screen passes (fail-open on a shape
mismatch). For a fail-closed screen, an unrecognized payload shape should escalate, not pass.

**Fix:**
- Screen the body at the point it is read into the pipeline (a deterministic pre-step in the runner
  AND a hook that fires on the event that actually carries the body), not only on UserPromptSubmit.
- In `_extract_body`, if neither `prompt` nor `body` is present, return a sentinel that causes
  `main()` to escalate rather than treating "no body found" as clean.

### CR-05: pii_redact fails OPEN and silently drops the payload on error (data-corruption + PII-leak risk)

**File:** `.claude/hooks/pii_redact.py:68-76`
**Issue:**
On any exception (including Presidio raising `OSError` when `en_core_web_lg` is missing — explicitly
called out in `src/guards/pii.py:11`), the hook prints `"{}"` and exits 0. Two problems:

1. **PII-leak fail-open:** if `redact_text` raises *after* the payload was read but the hook is
   being relied upon to redact before a downstream trace sink, emitting `{}` means the downstream
   consumer gets an empty payload — but any sink that already captured the raw `tool_input`
   upstream of this PostToolUse hook still holds unredacted PII. The hook cannot retroactively
   redact, and by design (PostToolUse) it runs *after* the tool already executed/logged. Redaction
   that runs after the sink is not a redaction guarantee. D-04 requires redaction *before* any
   log/trace; a PostToolUse transform cannot satisfy "before."
2. **Payload corruption:** replacing the whole payload with `{}` on a transient error discards the
   tool result for every downstream PostToolUse consumer, not just the PII fields.

**Fix:**
- Move redaction to the point of capture (wrap the logger/trace exporter so it redacts at write
  time), not a PostToolUse hook that runs after the tool. PostToolUse cannot enforce "before any
  log/trace."
- On error, emit the original payload structure with the sensitive fields replaced by a hard
  placeholder (`"<REDACTION_FAILED>"`) rather than `{}` — never pass raw text through, and never
  blank the entire payload.
- Pre-flight check for the spaCy model at startup so redaction never silently no-ops in prod.

## Warnings

### WR-01: pre_send_guard regex over-blocks common benign words ("bill", "charge", "credit", "payment")

**File:** `.claude/hooks/pre_send_guard.py:44-46`
**Issue:** `\b(charge|debit|payment|invoice|bill)\b` matches "your card will not be charged",
"no payment is required", "we have your billing address on file", and the name "Bill". While
over-escalation is the safe direction (acceptable for a fail-closed system), at 23k emails/week
this likely escalates a large fraction of legitimate order-status replies, undermining the
business goal (auto-reply at scale). Flagged as WARNING, not BLOCKER, because it errs safe.
**Fix:** Tighten to commitment phrasing (e.g. require a first-person/future commitment verb:
`\b(we('| wi)ll|I('| wi)ll|you('| wi)ll get a?)\s+\w*\s*(refund|credit|charge...)`), and add a
test corpus of benign replies to measure the false-escalation rate against the eval bar.

### WR-02: injection_screen `^|\n` anchoring misses CRLF and Unicode line separators

**File:** `.claude/hooks/injection_screen.py:93-100`
**Issue:** The `injected_instructions` pattern anchors on `(^|\n)`. Email bodies from Freshdesk are
frequently CRLF (`\r\n`); the `\r` is not consumed but `SYSTEM:` after `\r\n` still follows a `\n`
so this specific case is OK — however Unicode line separators (U+2028/U+2029) and leading
whitespace tricks (` SYSTEM:`) are not covered. More importantly, none of the patterns use
`re.MULTILINE` semantics consistently and rely on literal `\n`. **Fix:** Normalize the body
(`unicodedata.normalize`, strip zero-width chars, collapse CRLF→LF) before screening; use
`re.MULTILINE` with `^` anchors.

### WR-03: injection_screen is trivially evadable (no obfuscation handling) — defense-in-depth gap

**File:** `.claude/hooks/injection_screen.py:29-101`
**Issue:** Pure literal/word-boundary regex is bypassed by base64, zero-width-space insertion
(e.g. inserting a zero-width space U+200B mid-word: "ig" + U+200B + "nore previous instructions"), homoglyphs, or simple rewording ("from now on, behave as
though..."). This is inherent to regex injection screening and acceptable IF it is defense-in-depth
behind a model that is independently instructed to treat the body as data. It is a WARNING because
CLAUDE.md positions hooks as the *hard* gate; a regex screen is not a hard gate against injection.
**Fix:** Document explicitly that injection_screen is best-effort and that the real control is
prompt-level data delimiting + the downstream guards; do not represent it as a complete control.

### WR-04: cs_team_demo logs an injection reason derived from untrusted body without redaction

**File:** `scripts/cs_team_demo.py:258-262`, `469-471`
**Issue:** `logger.info("...reason=%s", injection_reason)` logs the injection label — which is a
fixed enum string, so this specific line is safe. But line 469 builds
`raw_body_for_check = verdict.get("body","") or verdict.get("reason","")` and the comment at 470-471
says "redact_text is called on any string before printing" — it is NOT; `raw_body_for_check` is
assigned and never used or printed, which is dead code that *implies* a redaction guarantee that the
code does not provide. If a future edit prints it, raw draft body leaks. **Fix:** Remove the dead
`raw_body_for_check` block, or actually redact and use it. Do not leave a comment asserting a
redaction that no code performs (D-04 footgun).

### WR-05: submit_reply LIVE mode silently falls back to dry_run — config lie

**File:** `src/reply_mcp/server.py:60-64`
**Issue:** When `SEND_MODE=live`, the tool logs a warning and runs `_dry_run` anyway. This is safe
for Phase 1 but means a future operator who sets `SEND_MODE=live` expecting sends gets silent
no-ops with no error surfaced to the caller (`{"submitted": True, "dry_run": True}` is returned —
note `dry_run: True` even though caller requested live). A caller cannot distinguish "sent" from
"silently dropped." **Fix:** In LIVE mode with no implementation, `raise NotImplementedError`
(fail-closed and loud) rather than returning a success-shaped dict, so misconfiguration is caught.

### WR-06: _dry_run swallows all DB errors as best-effort — silent loss of the audit trail

**File:** `src/reply_mcp/server.py:96-98`
**Issue:** `except Exception ... logger.warning(...)` then returns `{"submitted": True}`. The
dry_run_log is the audit record proving what the system would have sent. Swallowing every persist
failure (connection, auth, schema drift) while still returning `submitted: True` means a broken DB
yields a green pipeline with no audit trail. **Fix:** Distinguish CI/no-DB (acceptable skip) from
prod persist failure; in prod, a failed audit write should escalate/error, not return success.

### WR-07: escalation_gate context detection misfires for PostToolUse on submit_reply

**File:** `.claude/hooks/escalation_gate.py:106-110`, `.claude/settings.json:58-71`
**Issue:** `escalation_gate.py` is bound on **both** PreToolUse@submit_reply AND PostToolUse@`*`.
`is_final_veto` is true if `hook_event_name == "PreToolUse"` OR `tool_name == "submit_reply"`. In
the PostToolUse@submit_reply invocation, `tool_name == "submit_reply"` is true, so the PostToolUse
run is misclassified as the final veto and would `exit(2)` if any signal were set — but PostToolUse
ignores exit 2 (it is not a blocking event), so an escalation intended as a post-hoc signal is lost.
Conversely a genuine PreToolUse block depends on signals that aren't present (see CR-02). The
dual-purpose script's context detection is ambiguous. **Fix:** Branch on `hook_event_name` alone
(it is authoritative), and assert the expected event is present rather than inferring from
`tool_name`.

## Info

### IN-01: grounding_check normalizes citation IDs inconsistently with the marker regex

**File:** `.claude/hooks/grounding_check.py:56-63`
**Issue:** Markers are extracted as bracketed (`[KB-1]`); citation ids are normalized by wrapping
bare ids. But an id like `"KB-1 "` (trailing space) or `"kb-1"` (lowercase) will not match the
case-sensitive bracketed marker, producing a false `unknown_citation_ids` failure. Low impact
(fails safe), but brittle. **Fix:** Strip/uppercase ids during normalization.

### IN-02: tests/cs_team/claude symlink committed into the repo is fragile cross-platform

**File:** `tests/cs_team/claude -> ../../.claude`
**Issue:** A committed symlink breaks on Windows checkouts and on `git archive`/zip exports;
`conftest.py` already loads hooks via importlib, making the symlink redundant for the documented
import path. **Fix:** Remove the symlink and rely solely on the conftest importlib shim, or document
the symlink as required and add a CI guard.

### IN-03: settings.py NoDecode set parsing raises ValueError on non-int CSV (DoS-on-startup)

**File:** `src/config.py:159-169`
**Issue:** `parse_selless_sync_user_ids` does `int(x.strip())`; a malformed env value
(`SELLESS_SYNC_USER_IDS=abc`) crashes process startup with an unhandled `ValueError`. Low severity
(config, not request path). **Fix:** Catch and either skip invalid entries with a warning or raise a
clear configuration error message.

### IN-04: cs_team_demo `_simulate_verdict` is structurally divergent from the real chokepoint

**File:** `scripts/cs_team_demo.py:329-380`
**Issue:** The simulation applies grounding+commitment checks with correct in-process boolean logic
and exit-code-independent flow, so the demo and tests pass even though the deployed hooks fail open
(CR-01/CR-02). This is the root cause of the green-tests/broken-gate divergence. **Fix:** Add an
integration test that invokes each hook as a subprocess via the exact `settings.json` command and
asserts the process exit code (0 vs 2), so the test surface matches the deployed enforcement
surface.

---

_Reviewed: 2026-06-03T04:23:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
