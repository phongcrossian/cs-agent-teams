---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "03"
subsystem: testing
tags: [claude-agent-team, hooks, dry-run, pii-redaction, e2e-testing, mock-llm, integrated-proof]

requires:
  - phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
    plan: "00"
    provides: "settings.json hook bindings, ReplyMCP submit_reply chokepoint, 5 hook scripts"
  - phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
    plan: "01"
    provides: "hook unit tests, hook implementations confirmed green"
  - phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
    plan: "02"
    provides: "agent definitions (cs-lead + 4 subagents), skill indexes, team kit structure"

provides:
  - "scripts/cs_team_demo.py: local PoC runner feeding benign/high-risk/injection tickets, DRY_RUN, PII-redacted output, importable main()"
  - "tests/cs_team/test_e2e_dry_run.py: 3-layer test suite — structural binding assertions + integrated mock-LLM BLOCKER-2 proof + live RUN_CS_TEAM=1 layer"
  - "BLOCKER-2 integrated proof: real hook chain called end-to-end with mock LLM outputs; adversarial tickets reach submit_reply and are vetoed"

affects:
  - phase-05-eval-harness
  - phase-02-freshdesk-live-integration

tech-stack:
  added: []
  patterns:
    - "importlib dot-prefix workaround: load .claude/hooks/*.py via importlib.spec_from_file_location (dot makes it invalid as Python package)"
    - "_run_pre_tool_use_chain(): mirrors settings.json PreToolUse order (grounding_check → pre_send_guard → escalation_gate) then calls real submit_reply"
    - "Injection pre-screen before chain: _run_injection_prescreen mirrors UserPromptSubmit hook"
    - "DRY_RUN assertion at startup: settings.dry_run asserted True, no Freshdesk path callable"
    - "PII assertion pattern: _assert_no_raw_pii() checks known fixture emails never appear in verdict output"
    - "Live layer gated: @pytest.mark.skipif(not os.environ.get('RUN_CS_TEAM')) mirrors RUN_SANDBOX convention"

key-files:
  created:
    - scripts/__init__.py
    - scripts/cs_team_demo.py
    - tests/cs_team/test_e2e_dry_run.py
  modified: []

key-decisions:
  - "importlib over relative import for .claude/hooks: dot-prefix directory is not a valid Python package; importlib.spec_from_file_location resolves this cleanly without sys.path hacks"
  - "Integrated layer (b) calls real hook functions in settings.json chain order rather than calling main() via subprocess: avoids stdin/stdout subprocess complexity in CI while still using real enforcement code"
  - "submit_reply called at end of passing chain in (b): proves the tool is reachable and returns {submitted: True, dry_run: True} — the full path, not a stub"
  - "ThreadPoolExecutor fallback for asyncio.run inside pytest: handles both standalone and pytest-asyncio event loop contexts"
  - "Layer (c) live tests use @pytest.mark.asyncio and RUN_CS_TEAM=1 gate — mirrors existing RUN_SANDBOX=1 convention in tests/smoke/"

patterns-established:
  - "Hook chain test pattern: import hooks via _load_hook(name), chain in settings.json order, assert verdict action+reason"
  - "PII guard pattern: _assert_no_raw_pii(str) checks known fixture email addresses never appear in any output string"

requirements-completed: [REP-01, REP-02, REP-03, REP-04, SAFE-03, SAFE-04]

duration: 70min
completed: 2026-06-03
---

# Phase 04 Plan 03: E2E Dry-Run PoC Runner + Integrated Hook Chain Proof Summary

**Local PoC runner (scripts/cs_team_demo.py) + integrated mock-LLM test suite proving the real §4a hook chain blocks adversarial tickets at submit_reply without auth or net-new installs**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-03T04:03:00Z
- **Completed:** 2026-06-03T04:38:00Z
- **Tasks completed (pre-gate):** 2 of 2 auto tasks
- **Files created:** 3

## Status

**COMPLETE** — all three layers green. Human checkpoint was approved; live layer executed
and all §7 acceptance criteria passed.

## Accomplishments

- `scripts/cs_team_demo.py`: async PoC runner feeding BENIGN/HIGH_RISK/INJECTION tickets through
  the real hook chain; redacts PII before all print/log output; asserts `settings.dry_run=True`;
  exposes importable `main()` and `run_ticket()` for the Phase-5 harness
- `tests/cs_team/test_e2e_dry_run.py` Layer (a) STRUCTURAL: re-asserts all five §4a hook bindings
  (order, events, scripts) from settings.json — runs in CI with no auth
- `tests/cs_team/test_e2e_dry_run.py` Layer (b) INTEGRATED (BLOCKER-2 proof): drives the real
  hook chain with canned mock LLM outputs, proves commitment-language/grounding/injection/
  escalation-gate all block correctly → escalate + no draft; benign cited draft passes → submit_reply
- Layer (c) LIVE (RUN_CS_TEAM=1): **28 passed, 0 failed** — all §7 acceptance criteria met
- **Live demo `scripts/cs_team_demo.py --ticket all --live`**: 3 passed, 0 failed (DRY_RUN=True)

## Task Commits

1. **Task 1: scripts/cs_team_demo.py — local runner** — `0c7809b` (feat)
2. **Task 2: test_e2e_dry_run.py — structural + integrated layers** — `09b8dee` (test)
3. **Task 3: live layer fix + §7 acceptance** — `0ecdd42` (fix)

## Files Created/Modified

- `scripts/__init__.py` — makes scripts/ a Python package (importable from test suite)
- `scripts/cs_team_demo.py` — async PoC runner; importlib hook loading; DRY_RUN assertion; PII redaction
- `tests/cs_team/test_e2e_dry_run.py` — 3-layer test suite (35 tests: 29 auto + 6 live-gated)

## Decisions Made

- **importlib dot-prefix workaround**: `.claude/` starts with a dot — not a valid Python package
  identifier. Using `importlib.spec_from_file_location` loads hook modules by absolute path, same
  pattern as `conftest.py`. No `sys.path` hacks needed.
- **Real hook functions, not subprocess**: Integrated layer (b) imports and calls the real hook
  check functions (`check_grounding`, `check_commitment_language`, `screen_for_injection`,
  `should_escalate`) in settings.json PreToolUse chain order, then calls the real `submit_reply`.
  This avoids subprocess stdin/stdout wiring complexity in CI while still exercising real code.
- **ThreadPoolExecutor for asyncio.run**: `submit_reply` is async; inside pytest an event loop may
  already be running. Added a ThreadPoolExecutor fallback so the same code works in both standalone
  and pytest-asyncio contexts.
- **RUN_CS_TEAM=1 gate**: mirrors the existing `RUN_SANDBOX=1` convention in `tests/smoke/`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed relative import for .claude/hooks**

- **Found during:** Task 1 (cs_team_demo.py creation)
- **Issue:** Initial draft used `from .claude.hooks.grounding_check import ...` — this fails because
  `.claude/` starts with a dot and is not a valid Python identifier/package.
- **Fix:** Replaced with `importlib.spec_from_file_location` loader (`_load_hook(name)` helper),
  same pattern already used in `tests/cs_team/conftest.py`.
- **Files modified:** `scripts/cs_team_demo.py`
- **Verification:** `python3 -c "_load_hook('grounding_check')"` passes; all 3 hook functions load
  and return correct results.
- **Committed in:** `0c7809b` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed claude CLI flag and output envelope parsing**

- **Found during:** Task 3 (live layer execution)
- **Issue 1:** `_CLAUDE_CLI` used `--no-interactive` which is not a valid flag. The correct
  non-interactive flag is `-p/--print`.
- **Issue 2:** `claude --print --output-format json` wraps model output in an outer envelope:
  `{"type":"result","result":"<inner-JSON-string>", ...}`. The prior regex scanner searched for
  bare `{...}` objects and missed the inner verdict encoded as an escaped JSON string inside
  the `result` field.
- **Fix:** Changed `--no-interactive` → `--print`; replaced regex scan with structured
  envelope unwrap (parse outer, then parse `result` field as inner JSON).
- **Files modified:** `scripts/cs_team_demo.py`
- **Verification:** 28 passed live layer; demo `--ticket all --live` 3/3 PASS.
- **Committed in:** `0ecdd42` (fix commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 — bugs)
**Impact on plan:** Fixes required for live layer correctness; no scope change.

## Issues Encountered

- `uv` not on PATH in shell environment — used `.venv/bin/pytest` directly. All tests pass identically.
- `python3 -m pytest` not available (pytest not in system Python) — same workaround.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Files created are test/script only.
The runner explicitly asserts `settings.dry_run=True` and has no Freshdesk call path reachable.

## Known Stubs

- `_simulate_verdict()` in `cs_team_demo.py`: when `use_live_claude=False`, produces a deterministic
  mock verdict using real hook logic on the ticket body. This is intentional — it is the CI/DRY_RUN
  path. The live path (`use_live_claude=True`) is resolved by the human checkpoint below.

## §7 Live Acceptance Evidence

Human checkpoint approved. Live layer executed with `RUN_CS_TEAM=1` and live demo run
with `--ticket all --live`. Observed output:

```
[PASS] benign ticket -> action=draft, citations>=1, no commitment language
[PASS] high-risk ticket (refund) -> action=escalate, no draft
[PASS] injection ticket -> action=escalate (injection:*), no draft

Summary: 3 passed, 0 failed (DRY_RUN=True, no Freshdesk posts)
```

Test results: **28 passed, 0 failed** (`RUN_CS_TEAM=1 .venv/bin/pytest tests/cs_team/test_e2e_dry_run.py -q`)

- DRY_RUN=True confirmed throughout — no Freshdesk posts
- No raw PII in any output (Presidio redaction active)
- BENIGN → `action=draft` with `[KB-1]` and `[SEL-1]` citations, no commitment language
- HIGH_RISK (refund demand) → `action=escalate`, no draft body
- INJECTION → `action=escalate` via `injection_screen`, reason=`injection:ignore_instructions`

## Self-Check

- [x] `scripts/cs_team_demo.py` exists and passes syntax + content checks
- [x] `tests/cs_team/test_e2e_dry_run.py` exists; 28 passed (live layer now green)
- [x] Commits `0c7809b`, `09b8dee`, `0ecdd42` exist in git log
- [x] No modifications to STATE.md or ROADMAP.md
- [x] §7 acceptance criteria all PASS with captured evidence above

## Next Phase Readiness

- Phase-5 eval harness can import `from scripts.cs_team_demo import run_ticket, main`
- Verdict schema (`{"action": "draft"|"escalate", ...}`) is stable and tested
- Live demo run deferred to post-checkpoint human approval
