---
status: partial
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
source: [04-VERIFICATION.md]
started: 2026-06-04
updated: 2026-06-04
---

## Current Test

[awaiting human testing]

## Tests

### 1. Safety-contract D-13 → D-26 update (.claude/CLAUDE.md)
expected: The `.claude/CLAUDE.md` "D-13 — Commitment language is blocked" section is updated to D-26 authorized-offer semantics (block UNAUTHORIZED offers; permit authorized templated offers within policy) so the always-on safety contract matches the implemented code (`pre_send_guard.py` docstring already says "D-26 SUPERSEDES D-13"). Enforcement is UNAFFECTED (hooks enforce D-26 regardless of the prose), but the contract text is stale.
result: resolved (2026-06-04)
note: User approved the safety-contract edit. The `.claude/CLAUDE.md` "D-13" section was replaced with the "D-26 — Unauthorized commitments are blocked; authorized templated offers are permitted" section, matching the implemented code. (First automated attempt was correctly blocked by the harness auto-mode classifier pending explicit user authorization, which was then given.)

### 2. Live round-trip — authorized templated offer PASSES the guard
expected: In a full Claude Code cs-agent-team session (real LLM), a within-policy templated offer (e.g. B7: 50% refund + 40% VIP discount on an in-warranty, first-remediation order) is drafted, the drafter emits a correctly-formatted `offer` block, and `pre_send_guard` lets `submit_reply` through (exit 0). Verified so far only via subprocess tests with hardcoded payloads, not an end-to-end LLM round-trip.
result: [pending]

### 3. Live round-trip — Review / Full_Refund ticket NEVER reaches submit_reply
expected: In a full session, a `Review` (or `Full_Refund`, or mutation-asserting change_request with no offer) ticket escalates via `escalation_gate.operational_action` and never produces a customer draft. CR-01 fix confirmed via subprocess (WRITE exit 1 → READ@submit_reply exit 2); needs confirmation in the real hook-dispatch chain with LLM output.

## Summary

total: 3
passed: 1
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
