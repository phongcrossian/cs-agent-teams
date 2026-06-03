---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "00"
subsystem: cs-agent-team-bootstrap
tags: [config, reply-mcp, settings, hooks, fixtures, tdd-red, safety-chokepoint]
dependency_graph:
  requires: []
  provides:
    - src/config.py (anthropic_api_key, claude_model_classify, claude_model_draft, claude_model_lead, dry_run)
    - src/reply_mcp/server.py (ReplyMCP + submit_reply chokepoint)
    - .claude/settings.json (3 MCPs + all-five-hook §4a bindings)
    - .claude/CLAUDE.md (team-scoped safety contract)
    - tests/fixtures/sample_tickets.py (BENIGN/HIGH_RISK/INJECTION)
    - tests/cs_team/test_settings_hook_bindings.py (structural enforcement gate)
  affects:
    - all future Wave 1-3 plans (consume config + chokepoint + fixtures)
tech_stack:
  added:
    - FastMCP ReplyMCP server (src/reply_mcp)
    - cs-team optional deps group in pyproject.toml (anthropic>=1.0.0)
  patterns:
    - §4a single-chokepoint: submit_reply is the ONLY draft-emission path; hooks are the hard gate
    - Settings extension with per-stage model fields + secret redaction in __repr__
    - RED/structural test pattern: xfail stubs for future waves; GREEN structural binding test now
key_files:
  created:
    - src/reply_mcp/__init__.py
    - src/reply_mcp/server.py
    - .claude/settings.json
    - .claude/CLAUDE.md
    - tests/fixtures/__init__.py
    - tests/fixtures/sample_tickets.py
    - tests/cs_team/__init__.py
    - tests/cs_team/test_hooks_red.py
    - tests/cs_team/test_team_kit_structure.py
    - tests/cs_team/test_settings_hook_bindings.py
  modified:
    - src/config.py (Phase 4 additions: anthropic_api_key, claude_model_classify/draft/lead, dry_run, __repr__)
    - CLAUDE.md (orchestration row updated to Claude Code agent team; PydanticAI deferred)
    - pyproject.toml (cs-team optional deps group)
decisions:
  - "submit_reply(body, citations) is the SOLE customer-draft chokepoint per §4a; hooks are the hard gate (D-10)"
  - "escalation_gate.py bound in TWO contexts (no 6th script): PreToolUse(submit_reply) final-risk + PostToolUse/SubagentStop early-exit"
  - "No Opus on hot path (D-03): claude_model_lead=claude-sonnet-4-6 (W3 fix); Opus reserved for Phase-5 judge"
  - "anthropic_api_key redacted in __repr__ — mirrors existing secret-redaction pattern exactly"
  - "DRY_RUN is the default posture for the agent-team PoC (never posts to Freshdesk)"
  - "root CLAUDE.md orchestration row updated only; all other rows/text preserved (single-row edit)"
metrics:
  duration: "~25 min"
  completed: "2026-06-03"
  tasks: 3
  files: 13
---

# Phase 04 Plan 00: Wave-0 Bootstrap (Config + ReplyMCP Chokepoint + Settings + Fixtures) Summary

Wave-0 bootstrap for cs-agent-team: per-stage model config with Haiku/Sonnet assignments, ReplyMCP submit_reply as the sole customer-draft chokepoint, all-five-hook §4a settings.json bindings, team-scoped safety contract in .claude/CLAUDE.md, sample ticket fixtures, and RED test scaffolds for Wave 1-3.

## What Was Built

### Task 1: src/config.py + src/reply_mcp + pyproject.toml

Extended `Settings` with Phase-4 agent-team fields:
- `anthropic_api_key` (NEVER logged — redacted in `__repr__` as `<REDACTED>`)
- `claude_model_classify = "claude-haiku-4-5"` (D-03 — cheap/fast classify/extract hot path)
- `claude_model_draft = "claude-sonnet-4-6"` (D-03 — Sonnet for draft/critic quality)
- `claude_model_lead = "claude-sonnet-4-6"` (W3 fix — no Opus on hot path)
- `dry_run = True` (DRY_RUN-by-default posture for the agent-team PoC)

Created `src/reply_mcp/server.py`: FastMCP `ReplyMCP` server exposing `submit_reply(body, citations)` — the **only path** to emit a customer-facing draft (design §4a). In DRY_RUN mode it mirrors the `_dry_run` pattern from `src/work_queue/send.py`: redacts body via `redact_text()` then persists to `queue.dry_run_log` with `action="reply"`.

Added `cs-team` optional deps group in `pyproject.toml` (anthropic>=1.0.0; claude-agent-sdk TBD pending human-verify in 04-03).

### Task 2: .claude/settings.json + .claude/CLAUDE.md + root CLAUDE.md

Created `.claude/settings.json` registering three MCP servers:
- `KnowledgeMCP` (uv run python -m src.knowledge_mcp.server; DATABASE_URL + VOYAGE_API_KEY)
- `SellessMCP` (uv run python -m src.selless_mcp.server; DATABASE_URL + SELLESS_API_BASE_URL)
- `ReplyMCP` (uv run python -m src.reply_mcp.server; DATABASE_URL)

Bound all five hooks per §4a:
1. `PreToolUse(submit_reply)`: ordered chain `grounding_check.py → pre_send_guard.py → escalation_gate.py`
2. `UserPromptSubmit`: `injection_screen.py`
3. `PostToolUse`: `escalation_gate.py` + `pii_redact.py` (early-exit accumulation + PII)
4. `SubagentStop`: `escalation_gate.py`

Created `.claude/CLAUDE.md` as the team-scoped safety contract: D-08 (any-signal-escalates), D-10 (no draft on escalate), D-11 (inline citations required), D-13 (commitment language blocked), D-14 (email body untrusted/delimited), D-03 (Haiku classify/extract; Sonnet draft/critic/lead; no Opus hot path), D-04 (PII redacted), and the submit_reply chokepoint rule. Header documents dual-CLAUDE collision resolution (scope separation: root = developer, .claude/CLAUDE.md = agent team).

Updated root `CLAUDE.md` orchestration row only: PydanticAI → Claude Code agent team / Claude Agent SDK, PydanticAI deferred.

### Task 3: Fixtures + RED stubs + structural binding test

- `tests/fixtures/sample_tickets.py`: 3 importable fixtures (BENIGN_TICKET, HIGH_RISK_TICKET, INJECTION_TICKET) — synthetic PII only
- `tests/cs_team/test_hooks_red.py`: 9 RED stubs (xfail strict) asserting `(bool, reason)` contract on five hook functions — turn green Wave 2
- `tests/cs_team/test_team_kit_structure.py`: 15 RED stubs (xfail strict) asserting §3 manifest (.claude/agents/*.md, skills/*/SKILL.md, hooks/*.py) — turn green Wave 3
- `tests/cs_team/test_settings_hook_bindings.py`: 13 structural assertions (GREEN now, stays green) enforcing §4a binding design: PreToolUse(submit_reply) ordered chain, injection_screen on UserPromptSubmit, escalation_gate in two contexts, pii_redact on PostToolUse

## Verification Results

```
cfg-OK           # Settings: claude_model_lead present, anthropic_api_key=<REDACTED>, no Opus
reply_mcp-OK     # submit_reply + ReplyMCP + redact_text + dry_run_log all present
settings-OK      # 3 MCPs registered, all 5 hook scripts referenced, submit_reply in chain
claudemd-OK      # .claude/CLAUDE.md has submit_reply + escalate + opus + citation; root updated
fixtures-OK      # BENIGN/HIGH_RISK/INJECTION importable with body + order_ref
13 passed        # test_settings_hook_bindings.py (structural gate — GREEN)
24 xfailed       # test_hooks_red.py + test_team_kit_structure.py (RED as expected)
```

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

## Known Stubs

None — no hardcoded empty values flowing to UI rendering. The `submit_reply` DRY_RUN path persists to DB best-effort with a documented `logger.warning` when DB is unavailable in PoC/CI. This is intentional PoC behavior (the plan specifies DRY_RUN persistence mirrors `_dry_run`); the warning is not a stub, it is a documented fallback.

## Threat Flags

No new security-relevant surfaces beyond those in the plan's threat model. The following mitigations from the threat register were applied:

| T-ID | Applied | Verified |
|------|---------|---------|
| T-04-00-01 | anthropic_api_key redacted in __repr__ | cfg-OK assertion |
| T-04-00-02 | submit_reply redacts body via redact_text before persistence | reply_mcp-OK assertion |
| T-04-00-03 | hooks pinned to .claude/hooks/*.py paths; structural test asserts order | 13 bindings tests GREEN |
| T-04-00-04 | submit_reply is ONLY draft path; hook chain is hard gate | settings-OK + CLAUDE.md chokepoint rule |

## Self-Check: PASSED

Files exist:
- src/config.py (modified) — FOUND
- src/reply_mcp/__init__.py — FOUND
- src/reply_mcp/server.py — FOUND
- .claude/settings.json — FOUND
- .claude/CLAUDE.md — FOUND
- tests/fixtures/sample_tickets.py — FOUND
- tests/cs_team/test_settings_hook_bindings.py — FOUND

Commits exist:
- 0ebd519 feat(04-00): extend config + add reply_mcp submit_reply chokepoint
- d41990b feat(04-00): add .claude/settings.json (3 MCPs + 5 hooks §4a) + .claude/CLAUDE.md
- 3a7142c test(04-00): add sample fixtures + RED hook stubs + settings binding structural test
