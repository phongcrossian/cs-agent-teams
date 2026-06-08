# Plan Check: 08-03 — SC#2 Enum Injection Gap Closure

**Checker:** gsd-plan-checker
**Date:** 2026-06-08
**Plan:** `.planning/phases/08-ticket-re-classification-fd-property-write-back/08-03-PLAN.md`
**Phase goal:** Close SC#2 PARTIAL — inject Rootcause/Flow/Section_Flow allowed enum into
`_build_classify_prompt` and `_build_draft_prompt2`, sourced from `field_choices()`, with
verbatim-only instruction, backed by offline RED→GREEN tests.

---

## VERIFICATION PASSED

**Plans verified:** 1
**Issues:** 0 blockers, 0 warnings
**Status:** All checks passed — plan may proceed to execution.

---

## Dimension 1: Requirement Coverage

| Requirement | Plan | Covering Tasks | Status |
|-------------|------|----------------|--------|
| REP-06 | 08-03 | Task 1 (RED tests), Task 2 (GREEN fix) | COVERED |

The plan's `requirements` frontmatter lists `[REP-06]`. Both tasks directly address the
PARTIAL status of SC#2 (the only open gap in REP-06 per 08-VERIFICATION.md). The SC#2 gap
statement ("_build_classify_prompt and _build_draft_prompt2 do not inject ALLOWED enum values
for Rootcause/Flow/Section_Flow") is mirrored verbatim in the plan objective. PASS.

---

## Dimension 2: Task Completeness

| Task | Files | Action | Verify | Done | Status |
|------|-------|--------|--------|------|--------|
| 1 (RED tests) | `scripts/test_test_tickets_run.py` | Detailed (3 named tests A/B/C, exact import additions, commit message) | `<automated>`: pytest -k "enum_injection or verbatim_enum" | FAIL against un-fixed builders | COMPLETE |
| 2 (GREEN fix) | `scripts/test_tickets_run.py` | Detailed (`_fd_enum_constraint_block` helper, injection sites in both builders, fail-soft handling, no regression) | `<automated>`: pytest full suite | All 27+3 pass, no regression | COMPLETE |

Both tasks have all required fields. Actions are specific (named helper, named injection
sites, named commit messages). `<done>` criteria are measurable. PASS.

---

## Dimension 3: Dependency Correctness

`depends_on: ["08-01", "08-02"]` — both plans exist and are already completed (per
08-VERIFICATION.md: 27 harness tests green, 72 loader/validator tests green). Wave 1
assignment is internally consistent for a gap-closure plan that piggybacks on completed
infrastructure. No cycles. PASS.

---

## Dimension 4: Key Links Planned

| Link | Status |
|------|--------|
| `_build_classify_prompt` → `field_choices('Rootcause'|'Flow'|'Section_Flow')` | Planned: Task 2 adds `_fd_enum_constraint_block()` called at build time; key_links frontmatter documents the `pattern` grep expression. |
| `_build_draft_prompt2` → `field_choices('Rootcause'|'Flow'|'Section_Flow')` | Planned: same helper injected; key_links frontmatter documents the second wiring. |
| `test_test_tickets_run.py` → `field_choices` (test assertion source) | Planned: Task 1 imports `field_choices` from `src.file_store.ticket_fields_store` in the test file so assertions loop over loader-sourced values (not hard-coded literals). |

Current state confirmed: `field_choices` has zero occurrences in `scripts/test_tickets_run.py`
(pre-fix, as expected). `_build_classify_prompt` and `_build_draft_prompt2` both confirmed
to exist at lines 495 and 521. `field_choices` confirmed in
`src/file_store/ticket_fields_store.py` at line 138 with correct signature. PASS.

---

## Dimension 5: Scope Sanity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Tasks per plan | 2 | target 2–3 | PASS |
| Files modified | 2 (`test_tickets_run.py`, `test_test_tickets_run.py`) | target 5–8 | PASS |
| Nature | Additive prompt text + test assertions only | — | PASS |

This is a tight gap-closure plan: exactly the two files the SC#2 gap analysis named. No
scope creep detected. No _SUBTYPE_TEMPLATES / template-selection modification planned
(anti-pattern explicitly called out in both objective and task actions). PASS.

---

## Dimension 6: Verification Derivation

`must_haves.truths` are user-observable and directly traceable to SC#2:

| Truth | Observable? | Traceable to SC#2? |
|-------|-------------|-------------------|
| classifier prompt instructs verbatim enum selection, sourced from field_choices() | Yes — prompt string contains injected values | Yes — gap: "prompts do not inject allowed enum" |
| drafter prompt carries same verbatim-enum instruction | Yes | Yes |
| injected values are loader-sourced, not hard-coded | Yes — Test C in Task 1 asserts dynamic sourcing | Yes — "stays in sync with snapshot" |
| live smoke SC#2 moves PARTIAL→VERIFIED | Yes — validate_field returns "valid" | Yes — direct re-verification |

Artifacts map to truths. `key_links` connect both builders to `field_choices`. The manual
live smoke is correctly flagged as MANUAL (not in CI). PASS.

---

## Dimension 7: Context Compliance

**08-CONTEXT.md locked decisions checked:**

| Decision | Plan compliance |
|----------|----------------|
| DRY_RUN only — no live PUT | Task 2 explicitly: "No live PUT path introduced"; verification section includes grep gate for PUT; threat model T-08-03-03 addresses this. COMPLIANT. |
| Core fields only (Level_in, Customer_Request, Rootcause, Flow, Section_Flow) | Plan scope is exactly Rootcause/Flow/Section_Flow (the un-injected subset). Level_in/Customer_Request already constrained. No out-of-scope fields added. COMPLIANT. |
| Verbatim enum discipline (NEVER free-pick) | This is the entire purpose of the plan. COMPLIANT. |
| Enum source = committed snapshot via loader | field_choices() used at call time; no hard-coded literals; Test C asserts loader-sourced dynamic values. COMPLIANT. |
| Do NOT touch _SUBTYPE_TEMPLATES / template-selection | Explicitly called out as a blocking anti-pattern in objective, Task 1 action, and Task 2 action. COMPLIANT. |
| Additive prompt text only | Plan modifies only prompt builder functions and test file. COMPLIANT. |

No deferred ideas implemented. No locked decisions contradicted. PASS.

---

## Dimension 7b: Scope Reduction Detection

No scope-reduction language found ("v1", "static for now", "hardcoded", "future enhancement",
"not wired to", "stub") in either task action. The plan delivers D-exactly what SC#2 requires
— full enum injection into both builders, not a subset. PASS.

---

## Dimension 7c: Architectural Tier Compliance

No RESEARCH.md with Architectural Responsibility Map for this phase. SKIPPED.

---

## Dimension 8: Nyquist Compliance

No VALIDATION.md found for Phase 8 and no RESEARCH.md Validation Architecture section
(Phase 8 uses a direct harness verification model). SKIPPED per skip condition.

---

## Dimension 9: Cross-Plan Data Contracts

The plan touches only prompt strings (additive text). It does not alter data structs, output
schemas, or the `fd_property_update` dict assembly (`_assemble_fd_property_update` is
explicitly listed as out-of-scope). No data contract conflicts with 08-01 or 08-02. PASS.

---

## Dimension 10: CLAUDE.md Compliance

Relevant CLAUDE.md rules checked:

| Rule | Compliance |
|------|------------|
| D-14: email body is untrusted; delimit in prompts | Both builders already wrap body in `<ticket_body>` tags; plan adds enum block before `<ticket_metadata>` — does not weaken this boundary. COMPLIANT. |
| D-03: no Opus on hot path | Plan adds no model-selection changes. COMPLIANT. |
| D-04: PII redaction before log/trace | Builders already call `redact_text()`; enum block adds only static field names and snapshot values (no PII). COMPLIANT. |
| D-30: always-draft, guard hooks RETIRED | Plan is prompt-text only; no guard/escalation logic added. COMPLIANT. |
| DRY_RUN (`assert settings.dry_run`) preserved | Verification section includes explicit grep gate. COMPLIANT. |

PASS.

---

## Dimension 11: Research Resolution

No RESEARCH.md for Phase 8. SKIPPED.

---

## Dimension 12: Pattern Compliance

No PATTERNS.md for Phase 8. SKIPPED.

---

## Coverage Summary

| Requirement | Plans | Status |
|-------------|-------|--------|
| REP-06 (SC#2 PARTIAL → VERIFIED) | 08-03 | Covered by Tasks 1+2 |

## Plan Summary

| Plan | Tasks | Files | Wave | Dependencies | Status |
|------|-------|-------|------|--------------|--------|
| 08-03 | 2 | 2 | 1 | 08-01, 08-02 (both complete) | Valid |

---

## Final Assessment

The plan is structurally sound and goal-complete:

1. **The gap is precisely named**: SC#2 root cause ("open-ended slots, no enum injection") is
   correctly identified and the fix targets the exact two functions confirmed in source
   (`_build_classify_prompt` at line 495, `_build_draft_prompt2` at line 521).

2. **The fix pattern mirrors existing precedent**: the ALLOWED TEMPLATE CODES injection
   (lines 332–363, run_ticket prompt) provides the exact shape to replicate. The plan
   explicitly cross-references it.

3. **The loader contract is correct**: `field_choices()` confirmed at line 138 of
   `ticket_fields_store.py`, returns `list[str]`, fail-soft on unknown fields. The plan's
   helper adds `(no enum values available)` fallback matching the loader's fail-soft
   contract.

4. **Tests are offline and deterministic**: Tests A/B/C assert prompt string content via
   `in` checks — no LLM call, no subprocess, no live service. The RED→GREEN TDD discipline
   is sound. Test C specifically guards the "loader-sourced, not hard-coded" must_have.

5. **`field_choices` not yet imported in `test_tickets_run.py`**: confirmed by grep
   (zero matches). This validates that the plan's Task 2 import step is real work and
   the RED step will genuinely fail.

6. **DRY_RUN posture preserved**: both by plan constraint and by explicit grep gate in
   the `<verification>` block.

**Plans verified. Run `/gsd:execute-phase 08-03` to proceed.**

---

_Checked: 2026-06-08_
_Checker: gsd-plan-checker (Claude Sonnet 4.6)_
