# SECURITY.md — Phase 04 Security Audit

**Phase:** 04 — reply-pipeline-classify-extract-ground-draft-safety-guards
**Audit Date:** 2026-06-03
**Auditor:** gsd-security-auditor (Claude Sonnet 4.6)
**ASVS Level:** L1/L2 (default)
**Threats Total:** 34
**Threats Closed:** 32
**Threats Open (BLOCKER):** 0
**Advisory Warnings (not blockers):** 2

---

## Verdict: SECURED

All declared `mitigate` threats have confirmed code evidence. No declared mitigation is absent from the implementation. Two advisory items from 04-REVIEW.md (WR-03, WR-04) are documented below as accepted risks — they were explicitly classified as WARNINGs (not blockers) by the code reviewer and are not part of the threat register's `mitigate` dispositions.

---

## Threat Verification Table

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-04-00-01 | InfoDisclosure | mitigate | CLOSED | `src/config.py:171-184` — `__repr__` explicitly redacts `anthropic_api_key`, `freshdesk_api_key`, `webhook_secret`, `voyage_api_key`, `selless_api_gateway_key` as `<REDACTED>` |
| T-04-00-02 | InfoDisclosure | mitigate | CLOSED | `src/reply_mcp/server.py:73` — `redact_text(body)` called before DB persistence in `_dry_run`; `scripts/cs_team_demo.py:207-209` — `redact_text` on body/subject/order_ref before any print/log |
| T-04-00-03 | Tampering | mitigate | CLOSED | `.claude/settings.json:28-83` — all hooks pinned to `.claude/hooks/*.py`; PreToolUse(submit_reply) has 3-hook ordered chain `grounding_check→pre_send_guard→escalation_gate` |
| T-04-00-04 | EoP | mitigate | CLOSED | `src/reply_mcp/server.py:40` — sole `submit_reply` tool is the only draft-emission path; `.claude/CLAUDE.md §4a` and `drafter.md:12` enforce it |
| T-04-00-SC | Tampering | accept | CLOSED | Blocking human-verify checkpoint declared in `04-00-PLAN.md:197`; no net-new installs occur without it. Accepted policy per plan. |
| T-04-01-01 | Tampering | mitigate | CLOSED | `.claude/hooks/injection_screen.py:31-103` — 8 compiled patterns covering ignore/disregard, system-prompt override, role/persona override, tool-call injection, prompt extraction, false authority, injected-instructions; `main()` exits 1 on match, exits 1 on error (fail-closed via except:L152-154) |
| T-04-01-02 | EoP | mitigate | CLOSED | `.claude/hooks/pre_send_guard.py:32-53` — 4 pattern groups (refund, credit, charge, replace); `main()` exits 2 on match (L100) and exits 2 on error (L104); never strips and sends |
| T-04-01-03 | Spoofing/Repud | mitigate | CLOSED | `.claude/hooks/escalation_gate.py:77-87` — `should_escalate()` OR-gate over all signals; `_write_signals()` additive OR-merge never clears True; `_read_signals()` fail-closed returns None on missing/unparseable |
| T-04-01-04 | InfoDisclosure | mitigate | CLOSED | `.claude/hooks/grounding_check.py:34-75` — 3 rules: citations-present-but-no-markers, empty-citation+no-marker (CR-03 bypass closed), unknown citation IDs; exits 2 on failure (L114) and on error (L118) |
| T-04-01-05 | InfoDisclosure | mitigate | CLOSED | `.claude/hooks/pii_redact.py:34,63-80` — wraps `redact_text()` for top-level `body`/`draft`, nested `tool_input.body`/`tool_input.draft`, `tool_result.body`; PostToolUse binding in `settings.json:62-68`. Advisory WR-03 (subject/email fields not redacted) documented separately. |
| T-04-01-06 | DoS | mitigate | CLOSED | All 5 hooks have `except Exception` → escalate pattern: `injection_screen.py:152-154`(exit 1), `pre_send_guard.py:102-104`(exit 2), `grounding_check.py:116-118`(exit 2), `pii_redact.py:85-96`(exit 0 passthrough), `escalation_gate.py:311-319`(exit 2 final-veto / exit 1 write-side) |
| T-04-02-01 | Tampering | mitigate | CLOSED | `scripts/cs_team_demo.py:201-221` — `_build_prompt()` wraps body in `<ticket_body>` tags, subject+order_ref in `<ticket_metadata>` tags (CR-03 fix confirmed at L213-217); all fields PII-redacted first |
| T-04-02-02 | InfoDisclosure | mitigate | CLOSED | `.claude/agents/drafter.md:38` — `get_template(code)` from KnowledgeMCP; inline citations required; `grounding_check.py` enforces before submit_reply; `test_e2e_dry_run.py:378-401` — uncited drafts blocked |
| T-04-02-03 | EoP | mitigate | CLOSED | `.claude/CLAUDE.md D-13` — agent-level prohibition documented; `pre_send_guard.py:32-53` deterministic enforcement at submit_reply chokepoint |
| T-04-02-04 | Spoofing | mitigate | CLOSED | `.claude/hooks/escalation_gate.py:267-293` — escalation enforced by hooks, not by trusting agent output; `settings.json` hook chain is non-bypassable |
| T-04-02-05 | InfoDisclosure | mitigate | CLOSED | `tests/cs_team/test_team_definitions.py:75-121` — asserts `claude-haiku-4-5` in classifier+extractor, `claude-sonnet-4-6` in drafter+critic+cs-lead, no `opus` substring in any agent file |
| T-04-02-06 | Tampering | mitigate | CLOSED | `.claude/agents/drafter.md:38,118` — "Use `get_template(code)` from KnowledgeMCP"; `.claude/skills/ground-and-draft/SKILL.md:38,173` — runtime fetch, never hard-coded |
| T-04-03-01 | InfoDisclosure | mitigate | CLOSED | `scripts/cs_team_demo.py:15-18,207-209,340` — `redact_text()` on every body/draft/subject before print/log |
| T-04-03-02 | EoP | mitigate | CLOSED | `scripts/cs_team_demo.py:335-337` — `assert settings.dry_run` at startup; `src/reply_mcp/server.py:56-64` — LIVE path not implemented, falls back to dry_run; `test_e2e_dry_run.py:503-508` — dry_run asserted in test |
| T-04-03-03 | Tampering | accept | CLOSED | Blocking human checkpoint per plan; same as T-04-00-SC. Accepted policy. |
| T-04-03-04 | Spoofing | mitigate | CLOSED | `scripts/cs_team_demo.py:229-263,345-356` — `_pre_screen_ticket()` runs unconditionally before CLI invocation; returns escalate immediately on injection detection; screens body+subject+order_ref |
| T-04-03-05 | Repudiation | mitigate | CLOSED | `.claude/settings.json:29-45` — PreToolUse(submit_reply) chain: `grounding_check→pre_send_guard→escalation_gate`; any hook exit 2 blocks; `test_hooks_subprocess.py:113-154` proves exit codes |
| T-04-03-06 | EoP | mitigate | CLOSED | `src/reply_mcp/server.py:40` — sole tool; `settings.json:28-45` — ordered 3-hook PreToolUse chain on submit_reply |
| T-04-03-SC | Tampering | accept | CLOSED | Same blocking checkpoint as T-04-00-SC. Accepted. |
| T-04-04-01 | EoP | mitigate | CLOSED | `pre_send_guard.py:100` — `sys.exit(2)` on commitment match; `pre_send_guard.py:104` — `sys.exit(2)` on error; `test_hooks_subprocess.py:113-154` — subprocess returncode==2 asserted |
| T-04-04-02 | EoP | mitigate | CLOSED | `grounding_check.py:114` — `sys.exit(2)` on ungrounded; `grounding_check.py:118` — `sys.exit(2)` on error; `test_hooks_subprocess.py:164-219` — subprocess returncode==2 asserted |
| T-04-04-03 | Spoofing | mitigate | CLOSED | `grounding_check.py:53-57` — Rule 3 (CR-03): non-empty body + zero markers + zero citations → `False, "grounding:no_citations"`; `test_hooks_subprocess.py:179-192` — CR-03 bypass case asserts returncode==2 |
| T-04-04-04 | Tampering | mitigate | CLOSED | `injection_screen.py:127-134` — `_extract_body()` raises `ValueError("injection_screen:no_body_field")` when neither `prompt` nor `body` present; `test_hooks_subprocess.py:406-413` — missing-body payload asserts returncode!=0 |
| T-04-04-05 | InfoDisclosure | mitigate | CLOSED | `pii_redact.py:85-96` — error path re-serializes existing parsed payload or echoes raw stdin; does NOT blank to `{}`; original payload preserved on error (no field corruption) |
| T-04-04-SC | Tampering | accept | CLOSED | Plan-04-04 edits existing hook .py files only; no net-new installs. Accepted. |
| T-04-05-01 | EoP | mitigate | CLOSED | `escalation_gate.py:267-293` — final-veto: reads `_read_signals()`, exits 2 if None or any signal True; `_write_signals()` OR-merges at PostToolUse/SubagentStop; `settings.json:58-82` — escalation_gate bound to PostToolUse+SubagentStop for WRITE, PreToolUse(submit_reply) for READ. Advisory WR-04 (non-atomic write) documented separately. |
| T-04-05-02 | Tampering | mitigate | CLOSED | `escalation_gate.py:202-217` — `_read_signals()` returns None for: CS_RUN_ID unset, no file, unparseable; `main()` L275-282: None → exit 2; `test_hooks_subprocess.py:268-301` — no-state-file and CS_RUN_ID-unset cases assert returncode==2 |
| T-04-05-03 | Spoofing | mitigate | CLOSED | `scripts/cs_team_demo.py:345-356` — `_pre_screen_ticket()` is mandatory non-bypassable pre-screen in `run_ticket()` before any CLI/subagent call; screens body+subject+order_ref; returns escalate without invoking CLI on detection |
| T-04-05-04 | Repudiation | mitigate | CLOSED | `test_hooks_subprocess.py:110-601` — all PreToolUse hooks tested via real subprocess (`sys.executable` + hook .py); returncode==2 for every block scenario; returncode==0 for clean pass |
| T-04-05-05 | InfoDisclosure | mitigate | CLOSED | `escalation_gate.py:19-28` — state file stores only `{"signals": {...bool flags...}, "updated_at": "..."}`, no body/PII; `_write_signals()` only writes known signal keys from `_ALL_SIGNAL_KEYS`; finally block in `run_ticket()` deletes state file at run end (L377-383) |
| T-04-05-SC | Tampering | accept | CLOSED | Plan-04-05 edits existing files + new stdlib-only test; no net-new PyPI installs. Accepted. |

---

## Advisory Warnings (not blockers — from 04-REVIEW.md)

These were explicitly classified as WARNINGs (not CRITICALs) by the code reviewer. They do not map to `mitigate` dispositions in the threat register and are not blockers for shipping.

### WR-03 — pii_redact.py does not redact subject/email/customer_email/order_ref fields

**File:** `.claude/hooks/pii_redact.py:63-80`

**Detail:** The PostToolUse pii_redact hook redacts `body` and `draft` fields only. Fields `subject`, `email`, `customer_email`, `order_ref` in the hook payload are not redacted before reaching Claude Code's own logging. The residual mitigations are: (1) `scripts/cs_team_demo.py` calls `redact_text()` on subject/order_ref before building the prompt; (2) `submit_reply._dry_run` calls `redact_text(body)` at the persistence boundary; (3) escalate verdicts do not include raw ticket fields.

**Risk:** Partial D-04 coverage — subject/email fields may appear in Claude Code's PostToolUse logging payload in future tool calls that include those fields.

**Recommended fix:** Extend `pii_redact.py` to redact `_TOP_LEVEL_PII_FIELDS = {"body", "draft", "subject", "email", "customer_email", "order_ref"}` and apply same to `tool_input` and `tool_result`.

---

### WR-04 — escalation_gate._write_signals non-atomic file write

**File:** `.claude/hooks/escalation_gate.py:152-187` (`_write_signals`)

**Detail:** `Path.write_text()` is not atomic. Concurrent PostToolUse invocations sharing a `CS_RUN_ID` (parallel tool calls) could race, producing truncated JSON. When `_read_signals()` encounters unparseable JSON it returns None → exit 2 (fail-closed). Safety outcome is correct (false escalation, not false pass). However, false escalations on benign tickets are a correctness concern at scale.

**Risk:** False escalations under parallel tool calls for the same `CS_RUN_ID`. No false-pass risk.

**Recommended fix:** Use atomic rename pattern (`tempfile.mkstemp` + `os.replace`) for the write path.

---

## Accepted Risks Log

| Risk ID | Threat IDs | Description | Acceptance Rationale |
|---------|-----------|-------------|----------------------|
| ACCEPT-04-SC | T-04-00-SC, T-04-03-03, T-04-03-SC, T-04-04-SC, T-04-05-SC | Net-new PyPI package installs without Package Legitimacy Audit | Mitigated by blocking human-verify checkpoint before any install (documented in 04-00-PLAN.md, 04-03 plan). PoC phase; no new packages installed in gap-closure waves 04-04/04-05. |
| ACCEPT-WR-03 | T-04-01-05 (partial) | pii_redact.py PostToolUse hook does not cover subject/email/order_ref fields | Primary D-04 controls are at point-of-write (submit_reply._dry_run, cs_team_demo redact before prompt). PostToolUse hook is defense-in-depth. Residual partial coverage noted. Fix tracked as WR-03. |
| ACCEPT-WR-04 | T-04-05-01 (partial) | _write_signals non-atomic — race on concurrent PostToolUse | Fail-closed outcome (false escalation, not false pass). Correctness issue only. Fix tracked as WR-04. |

---

## Unregistered Flags

None. All items in SUMMARY.md `## Threat Flags` sections map to registered threat IDs in the threat register (CR-01→T-04-04-01/T-04-05-01, CR-02→T-04-05-02, CR-03→T-04-04-03, CR-04→T-04-04-04).

---

_Audit performed: 2026-06-03 by gsd-security-auditor_
_Implementation files: READ-ONLY. No implementation modifications made._
