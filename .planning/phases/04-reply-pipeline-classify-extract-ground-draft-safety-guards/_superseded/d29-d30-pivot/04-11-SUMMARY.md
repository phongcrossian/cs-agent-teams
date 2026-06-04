---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: 11
status: deferred
deferred: true
checkpoint_decision: not-ready
date: 2026-06-04
requirements: [SAFE-04]
tasks_completed: 1
tasks_total: 3
---

# 04-11 SUMMARY — Real eligibility/evidence wiring (DEFERRED)

## Outcome: DEFERRED by checkpoint decision

The blocking `checkpoint:decision` (Task: "Confirm real eligibility + evidence surface
readiness") was presented to the developer on 2026-06-04. **Decision recorded: `not-ready`.**

The developer confirmed that the real Selless eligibility surface and evidence intake do **not
yet exist** — this is the expected state for the current local PoC. Per the `not-ready` option,
the auto-wiring tasks (Task 1: wire real eligibility/evidence; Task 2: fail-closed degradation
tests) are **not executed**. The plan remains deferred to a future phase/time.

## What was decided (Task 1 of 3 — the checkpoint — resolved)

- **RULES §4.2 (eligibility fields):** Selless does NOT yet expose warranty purchase/delivery
  dates, prior-remediation state, real variant stock, or a scoped product-info API. Not ready to wire.
- **RULES §4.3 (evidence intake):** The model for receiving + verifying Full_Refund evidence
  (photo + shipping label) is not yet decided/built. Not ready to wire.

## What was NOT done (deliberately deferred)

- Task 2 (auto): wire real eligibility + evidence into `authorize_offer` at the
  `STUB (RD-Q2)` / `STUB (RD-Q3)` markers in `.claude/hooks/authorized_offer.py`. **Not done.**
- Task 3 (auto, tdd): `tests/cs_team/test_real_eligibility.py`. **Not created.**
- `src/selless_mcp/models.py` / `server.py` / `whitelist.py` eligibility-field additions. **Not done.**

## Current state retained (intentional)

- `authorize_offer()` continues to consume `default_eligibility()` (the RD-Q2 optimistic stub)
  and accept-as-sufficient evidence (RD-Q3). The `STUB (RD-Q2)` / `STUB (RD-Q3)` markers placed
  in plan 04-06 remain in place, clearly scoping the future swap points.
- **Guard structure is unchanged and complete.** The §0 decision logic, signature, and exit-code
  contract built in 04-06/04-09 already accept the real fields at the STUB points — only the data
  source behind those markers is deferred.

## Known limitation (carry-forward to Phase 5)

- AUTO* rows remain stub-optimistic; the D-27 hard gate ("0 UNAUTHORIZED commitments") cannot be
  fully exercised against *real* order eligibility until this plan is un-deferred.
- Threat T-04-11-01 (missing real field silently passing as optimistic stub) and T-04-11-02
  (fabricated evidence authorizing Full_Refund) are **NOT yet mitigated by real wiring** — they
  remain open pending the real-data swap. The fail-closed degradation guarantee is a DESIGN
  requirement of the future wiring, not yet implemented.

## Future trigger to un-defer

Re-open and execute 04-11 (Tasks 2–3) when BOTH are true:
1. Selless MCP exposes the eligibility fields (warranty dates, prior-remediation, variant stock)
   with D-04 whitelist + audit entries; AND
2. The evidence intake/verification model (RULES §4.3) is decided (human-in-loop vs automated).

This is naturally a Phase-5 / post-PoC concern (real eligibility is a prerequisite for fully
exercising the D-27 gate).

## Self-Check: PASSED (as a deferral record)

- Checkpoint decision recorded: `not-ready`.
- No production code changed by this plan (stub + markers intentionally retained).
- Full `tests/cs_team` suite remains green (250 passed, 6 skipped) — no regression from deferral.
