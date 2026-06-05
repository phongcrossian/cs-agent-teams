---
status: partial
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
source: [04-VERIFICATION.md]
started: 2026-06-05T08:30:00Z
updated: 2026-06-05T08:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run `/test-ticket --id <id>` against one real ticket from uat_ticket.csv
expected: test-tickets.xlsx written; terminal shows action=draft with non-empty body grounded on a real template phrase; no Freshdesk POST
result: [pending]
why_human: Requires live PROD Freshdesk GET + Selless read + real `claude --print` subprocess; cannot be validated without live credentials and running services.

### 2. Run a high-risk (refund/money) ticket via --id and inspect test-tickets.xlsx
expected: AI output block shows action=draft with non-null escalation_hint whose reason contains 'high_risk' or equivalent; CS reply column present for side-by-side
result: [pending]
why_human: pytest mocks the pipeline; confirming the real team produces the correct advisory hint shape on live ticket data requires human eyes on xlsx output.

### 3. Run a ticket with no order reference via --id; verify D-34 fallback in xlsx
expected: Draft body uses verify-order or clarify-order-info language; no fabricated order number (ORD-XXXXX) in draft
result: [pending]
why_human: D-34 fallback is unit-tested in simulation (30/30 always-draft tests); live execution with real ticket data needs human confirmation.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

> Superseded the prior (2026-06-04) D-26 authorized-offer UAT items — those guards were
> RETIRED by the D-29/D-30 always-draft pivot (D-32 deleted the four guard hooks). The
> three items above are the always-draft PoC's live-credential verification items.
