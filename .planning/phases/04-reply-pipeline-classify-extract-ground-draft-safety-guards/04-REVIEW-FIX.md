---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
fixed_at: 2026-06-04T02:20:00Z
review_path: .planning/phases/04-reply-pipeline-classify-extract-ground-draft-safety-guards/04-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-06-04T02:20:00Z
**Source review:** .planning/phases/04-reply-pipeline-classify-extract-ground-draft-safety-guards/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-04, CR-02, WR-01, WR-02, WR-03, IN-03)
- Fixed: 6
- Skipped: 0
- Deferred (out of scope per fix_scope): IN-01, IN-02 (explicit decision: plan 04-11)

## Fixed Issues

### CR-01: `operational_action` escalation silently dropped when payload carries an explicit `signals` dict

**Files modified:** `.claude/hooks/escalation_gate.py`
**Commit:** 36aa73c
**Applied fix:** Rewrote `_derive_signals` to copy the explicit signals dict (never mutate
caller's dict) and then ALWAYS call `_derive_operational_action` regardless of how signals
was sourced. Previously the function early-returned the explicit dict without ever calling
`_derive_operational_action`, so `signals={all-False}+customer_request="Review"` persisted
`operational_action=False` and let `submit_reply` pass (exit 0).

**Live repro confirmed closed:**
- WRITE `signals={all-False}+customer_request="Review"` → exit 1, state file has `operational_action=true`
- READ `PreToolUse@submit_reply` → exit 2 (blocked)

---

### WR-04: `_derive_operational_action` first-source-wins lets a benign top-level `customer_request` mask a nested escalating one

**Files modified:** `.claude/hooks/escalation_gate.py`
**Commit:** 36aa73c (same commit as CR-01)
**Applied fix:** Rewrote `_derive_operational_action` to scan ALL payload sources before
evaluating any rule (any-source-escalates). Now collects `all_customer_requests` (list from
all sources), `any_asserts_mutation_true`, and `any_asserts_mutation_explicit_false` across
all sources, then applies Rules 1/2/3 on the full picture. Rule 3 escalates if ANY source
sets a mutation-asserting sub-type AND no source explicitly sets `asserts_mutation=False`
(fail-closed). The first-source-wins bug where top-level `Ask_About_Order` masked nested
`Review` is closed.

---

### CR-02: Threshold caps are global, not per-sub-type — out-of-flow offers authorized

**Files modified:** `.claude/hooks/authorized_offer.py`
**Commit:** b5b121e
**Applied fix:** Added `SUBTYPE_ALLOWED_OFFER_KEYS: dict[str, frozenset[str]]` mapping each
sub-type to its legal offer dimensions, grounded in `04-AUTHORIZED-OFFER-RULES.md` §2 and
`POLICY-THRESHOLD-INDEX.md`. The `(d)` check in `authorize_offer` now iterates `offered.items()`
and rejects any key not in `allowed_offer_keys = SUBTYPE_ALLOWED_OFFER_KEYS.get(sub_type, frozenset())`
with `unauthorized:offer_key_not_allowed:<key>` before threshold caps are checked.
Fail-closed default: unlisted sub-types get `frozenset()`.

Key map:
- `Return`, `Partial_Refund` → `{refund_pct, discount_pct}` (THR-07, THR-05)
- `Full_Refund` → `{refund_pct}` (THR-07, evidence-gated)
- `Cancel_Order` → `{retention_pct}` (THR-06 ≤20%)
- `Ask_About_Delivery_Status` → `{comp_pct}` (THR-08 ≤50%)
- `Replace`, `Change_*`, inquiry sub-types → `frozenset()` (no monetary pct)

**Live repro confirmed closed:**
- `authorize_offer("Cancel_Order","F1",{"refund_pct":50},...)` → `(False, "unauthorized:offer_key_not_allowed:refund_pct")`

---

### WR-01: Unknown / mistyped offered keys are silently ignored (not fail-closed)

**Files modified:** `.claude/hooks/authorized_offer.py`
**Commit:** b5b121e (same commit as CR-02)
**Applied fix:** Folded into the CR-02 allowed-key gate. The new loop iterates `offered.items()`
and rejects any key not in `SUBTYPE_ALLOWED_OFFER_KEYS[sub_type]` — this catches both out-of-flow
legitimate keys AND unknown/mistyped keys (e.g. `"refundpct"`) in a single gate with the same
`unauthorized:offer_key_not_allowed:<key>` reason.

---

### WR-02: Negative percentages and bool values pass the threshold check

**Files modified:** `.claude/hooks/authorized_offer.py`
**Commit:** b5b121e (same commit as CR-02)
**Applied fix:** Added type and range validation inside the `(d)` loop before any comparison:
`isinstance(offered_val, bool)` → reject; `not isinstance(offered_val, (int, float))` → reject;
`offered_val < 0` → reject. All return `(False, "unauthorized:invalid_offer_value:<key>")`.

---

### WR-03: `authorize_offer` raises `TypeError` on non-numeric offered values

**Files modified:** `.claude/hooks/authorized_offer.py`
**Commit:** b5b121e (same commit as CR-02)
**Applied fix:** Same validation block as WR-02. The `isinstance(offered_val, (int, float))` check
rejects strings before any `>` comparison is attempted, so the function returns
`(False, "unauthorized:invalid_offer_value:<key>")` instead of raising `TypeError`. The function
now always honours its `(bool, str)` return contract on caller-supplied data.

---

### IN-03: Docs claim an offer block is "required" for informational replies — contract drift

**Files modified:** `.claude/agents/drafter.md`, `.claude/skills/ground-and-draft/SKILL.md`
**Commit:** 05a63e4
**Applied fix:** Updated both docs to state the offer block is OPTIONAL for purely informational
replies (no commitment term in the body). Added explanation that `pre_send_guard` only requires
an offer block when a commitment term is present; omitting it for informational replies is correct
behavior. The example block is retained for documentation purposes but no longer described as
mandatory. No behavior change — docs now match the enforced hook behavior.

## Skipped Issues

None — all in-scope findings were fixed.

## Out-of-Scope (Deferred by explicit decision)

### IN-01: STUB(RD-Q2) eligibility defaults are optimistic

**Reason:** Deferred to plan 04-11 per explicit fix_scope instruction. `default_eligibility()`
and the STUB markers left unchanged.

### IN-02: STUB(RD-Q3) Full_Refund evidence-gating treated as satisfied

**Reason:** Deferred to plan 04-11 per explicit fix_scope instruction.

---

## Verification Results

**Full test suite:** 276 passed, 6 skipped (0 failed)

**Live repro — escalation bypass (CR-01):**
- WRITE `{"hook_event_name":"PostToolUse","signals":{all-False},"customer_request":"Review"}` → exit 1, `operational_action=true` in state file
- READ `{"hook_event_name":"PreToolUse","tool_name":"submit_reply",...}` → exit 2 (BLOCKED)
- Status: CONFIRMED CLOSED

**Live repro — out-of-flow offer (CR-02):**
- `authorize_offer("Cancel_Order","F1",{"refund_pct":50},{"in_warranty":True,"prior_remediation":False})` → `(False, "unauthorized:offer_key_not_allowed:refund_pct")`
- Status: CONFIRMED CLOSED

---

_Fixed: 2026-06-04T02:20:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
