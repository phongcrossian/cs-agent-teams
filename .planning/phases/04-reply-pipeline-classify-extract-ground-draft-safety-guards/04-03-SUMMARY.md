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

duration: 35min
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

**CHECKPOINT REACHED** — tasks 1 and 2 are committed and green. A blocking human-verify
checkpoint (gate="blocking-human") is required before the live demo run can proceed.
This checkpoint is NOT auto-approvable. See "Awaiting" section below.

## Accomplishments

- `scripts/cs_team_demo.py`: async PoC runner feeding BENIGN/HIGH_RISK/INJECTION tickets through
  the real hook chain; redacts PII before all print/log output; asserts `settings.dry_run=True`;
  exposes importable `main()` and `run_ticket()` for the Phase-5 harness
- `tests/cs_team/test_e2e_dry_run.py` Layer (a) STRUCTURAL: re-asserts all five §4a hook bindings
  (order, events, scripts) from settings.json — runs in CI with no auth
- `tests/cs_team/test_e2e_dry_run.py` Layer (b) INTEGRATED (BLOCKER-2 proof): drives the real
  hook chain with canned mock LLM outputs, proves commitment-language/grounding/injection/
  escalation-gate all block correctly → escalate + no draft; benign cited draft passes → submit_reply
- Layer (c) LIVE: present, gated behind `RUN_CS_TEAM=1`, requires human checkpoint
- **35 passed, 6 skipped** (live layer) — deterministic layers green in CI

## Task Commits

1. **Task 1: scripts/cs_team_demo.py — local runner** — `0c7809b` (feat)
2. **Task 2: test_e2e_dry_run.py — structural + integrated layers** — `09b8dee` (test)

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

---

**Total deviations:** 1 auto-fixed (Rule 1 — import bug)
**Impact on plan:** Fix required for importability; no scope change.

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

## Awaiting Human Checkpoint

**Gate:** `blocking-human` — NOT auto-approvable

**What the human must verify before the live demo can run:**

1. **Package legitimacy**: Confirm the agent-team runtime package (`anthropic` / Claude CLI) is the
   official Anthropic package at https://pypi.org/project/anthropic — reject any typosquat.
2. **Auth**: Run `claude login` (Claude subscription) OR set `ANTHROPIC_API_KEY` in `.env`.
   Confirm which auth path is used for the PoC.
3. **MCP env + DB**: Export `DATABASE_URL`, `VOYAGE_API_KEY`, `SELLESS_API_BASE_URL` and confirm
   the Docker pgvector stack is up (`colima` + `docker-compose up -d`).
4. **DRY_RUN confirmed**: Verify `SEND_MODE=dry_run` / `settings.dry_run=True` before any live run.

**Resume signal:** Reply "approved" once all four are confirmed, then run:
```bash
RUN_CS_TEAM=1 .venv/bin/pytest tests/cs_team/test_e2e_dry_run.py -q
.venv/bin/python scripts/cs_team_demo.py --ticket all --live
```

## Self-Check

- [x] `scripts/cs_team_demo.py` exists and passes syntax + content checks
- [x] `tests/cs_team/test_e2e_dry_run.py` exists and 35 tests pass (6 skipped = live layer)
- [x] Commits `0c7809b` and `09b8dee` exist in git log
- [x] No modifications to STATE.md or ROADMAP.md

## Next Phase Readiness

- Phase-5 eval harness can import `from scripts.cs_team_demo import run_ticket, main`
- Verdict schema (`{"action": "draft"|"escalate", ...}`) is stable and tested
- Live demo run deferred to post-checkpoint human approval
