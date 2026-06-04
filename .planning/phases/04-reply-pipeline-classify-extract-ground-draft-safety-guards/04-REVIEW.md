---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
reviewed: 2026-06-04T02:05:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - .claude/hooks/authorized_offer.py
  - .claude/hooks/escalation_gate.py
  - .claude/hooks/pre_send_guard.py
  - .claude/agents/classifier.md
  - .claude/agents/drafter.md
  - .claude/skills/classify-ticket/SKILL.md
  - .claude/skills/ground-and-draft/SKILL.md
  - scripts/cs_team_demo.py
  - tests/cs_team/test_authorized_offer.py
  - tests/cs_team/test_authorized_offer_red.py
  - tests/cs_team/test_classifier_subtype_contract.py
  - tests/cs_team/test_drafter_offer_contract.py
  - tests/cs_team/test_e2e_dry_run.py
  - tests/cs_team/test_escalation_gate_operational.py
  - tests/cs_team/test_hooks.py
  - tests/cs_team/test_hooks_red.py
  - tests/cs_team/test_pre_send_guard_authorized.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-04T02:05:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This phase reopened Phase 4 to swap the block-all D-13 commitment guard for a
template+threshold-aware authorized-offer guard (D-26). The new logic spans three
safety-critical deterministic hooks: `authorized_offer.py` (the §0 decision core),
`pre_send_guard.py` (PreToolUse@submit_reply tripwire + offer authorization), and
`escalation_gate.py` (accumulated-risk veto, now extended with an
`operational_action` signal for Review / Full_Refund / mutation-asserting drafts).

The test suite is broad (250 passed, 6 skipped) and per-hook unit/subprocess coverage
is genuinely good. The D-13 → D-26 refactor was carried through cleanly: the
`check_commitment_language` symbol referenced by older tests is gone and replaced with
`_has_commitment_term` everywhere (only a comment in `cs_team_demo.py` mentions the
old name), so the memory-flagged "three test files expect a removed function" concern
is resolved.

However, the suite has a blind spot that conceals a **real escalation bypass**:
`escalation_gate._derive_signals` returns early whenever the payload carries an
explicit `signals` dict, so it **never derives `operational_action`** for that payload.
A classifier/stage that emits both a `signals` dict (the documented escalation-semantics
shape in `.claude/CLAUDE.md`) **and** `customer_request: "Review"` (or `Full_Refund`,
or a mutation-asserting change_request with no offer block) will pass the final
submit_reply veto with `returncode 0` — the exact "force-escalate" cases this rework
exists to protect. I reproduced this end-to-end through the WRITE→READ subprocess
flow (CR-01).

A second Critical concerns `authorize_offer`: threshold caps are keyed globally, not
per sub-type, so an out-of-flow numeric offer (e.g. `refund_pct: 50` on a
`Cancel_Order`) is authorized because the refund cap (50%) is checked independently of
whether refunds are valid for that sub-type (CR-02).

The STUB(RD-Q2)/STUB(RD-Q3) optimistic eligibility defaults are recorded as Info
(known deferred to plan 04-11), not Critical, per the review scope note.

## Critical Issues

### CR-01: `operational_action` escalation silently dropped when payload carries an explicit `signals` dict

**File:** `.claude/hooks/escalation_gate.py:119-140` (with `:143-187`)
**Issue:**
`_derive_signals` short-circuits on the first explicit signals container:

```python
for key in ("signals", "risk_signals", "escalation_signals"):
    if isinstance(payload.get(key), dict):
        return payload[key]          # <-- returns BEFORE operational_action is derived
```

`_derive_operational_action` is only invoked in the **fallback** branch (line 138),
reached only when no explicit `signals`/`risk_signals`/`escalation_signals` dict is
present. But the escalation-semantics shape documented in `.claude/CLAUDE.md`
("Escalation Semantics Reference") is exactly `{"action": ..., "signals": {...}}` —
a stage emitting a `signals` dict alongside `customer_request: "Review"` is the
expected case, not an exotic one.

Reproduced end-to-end (real subprocesses, WRITE then READ@submit_reply):

- WRITE `{"hook_event_name":"PostToolUse","signals":{...all False...},"customer_request":"Review"}` → state file persists `operational_action: false`.
- READ `{"hook_event_name":"PreToolUse","tool_name":"submit_reply",...}` → **returncode 0 (PASS)**.

The Review / Full_Refund / mutation-assertion force-escalate path (D-08 additive — the
purpose of plan 04-08) is bypassed. The subprocess tests in
`test_escalation_gate_operational.py` only send `customer_request` at the top level
*without* an accompanying `signals` dict, so they pass while the bug is live.

`pre_send_guard.py` independently blocks Review/Full_Refund *when an offer block is
present* (via `authorize_offer`), but `escalation_gate` is the designated catch for
no-offer / informational Review/Full_Refund drafts and for mutation-asserting
change_request drafts carrying no offer block. Those reach submit_reply with no offer
→ `pre_send_guard` exits 0 → `escalation_gate` is the only remaining gate → bypass.

**Fix:** Always derive `operational_action`, regardless of how `signals` was sourced.
Replace the early-return with a merge:

```python
def _derive_signals(payload: dict) -> dict:
    signals: dict | None = None
    for key in ("signals", "risk_signals", "escalation_signals"):
        if isinstance(payload.get(key), dict):
            signals = dict(payload[key])  # copy; do not mutate caller dict
            break
    if signals is None:
        for key in ("tool_result", "result", "output"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                for sig_key in ("signals", "risk_signals", "escalation_signals"):
                    if isinstance(nested.get(sig_key), dict):
                        signals = dict(nested[sig_key]); break
            if signals is not None:
                break
    if signals is None:
        known = {k for k, _ in _SIGNAL_ORDER}
        signals = {k: bool(payload.get(k, False)) for k in known if k in payload}
    _derive_operational_action(payload, signals)  # ALWAYS
    return signals
```

Add regression tests sending an all-False `signals` dict **plus** `customer_request:
"Review"` (and `Full_Refund`, and `Change_Product_Variant` with no `asserts_mutation`)
asserting READ@submit_reply returns 2.

---

### CR-02: Threshold caps are global, not per-sub-type — out-of-flow offers authorized

**File:** `.claude/hooks/authorized_offer.py:137-153` and `:273-278`
**Issue:**
`THRESHOLD_CAPS` maps each percentage key to a single global cap, and the check loop
validates every offered key against its own cap independently of `sub_type`:

```python
for pct_key, entry in THRESHOLD_CAPS.items():
    offered_val = offered.get(pct_key)
    if offered_val is not None and offered_val > entry["cap"]:
        return False, f"unauthorized:over_threshold:{entry['thr_id']}"
```

Nothing ties a cap key to the sub-type's allowed offer dimension. Reproduced:

- `authorize_offer("Cancel_Order","F1",{"refund_pct":50},{in_warranty:True,prior_remediation:False})` → **`(True,"authorized:F1")`**.

`Cancel_Order` is a ≤20% *retention* flow (THR-06) with no refund authority, yet a
50% `refund_pct` is authorized because the global `refund_pct` cap is 50 and the loop
never asks whether refund is a legal dimension for `Cancel_Order`. Same for
`retention_pct` on a `Return`, or `comp_pct` on a `Partial_Refund`. The drafter's
sub-type→THR table is advisory; the guard — the deterministic backstop meant to
re-authorize regardless of the drafter's proposal — does not enforce that mapping.

**Fix:** Gate each offered key by an allowed-dimension set per sub-type (fail-closed):

```python
SUBTYPE_ALLOWED_OFFER_KEYS = {
    "Cancel_Order": frozenset({"retention_pct"}),
    "Partial_Refund": frozenset({"refund_pct", "discount_pct"}),
    "Return": frozenset({"refund_pct", "discount_pct"}),
    "Full_Refund": frozenset({"refund_pct"}),
    "Ask_About_Delivery_Status": frozenset({"comp_pct"}),
    # ... explicit per sub-type
}
allowed = SUBTYPE_ALLOWED_OFFER_KEYS.get(sub_type, frozenset())
for pct_key in offered:
    if pct_key not in allowed:
        return False, f"unauthorized:offer_key_not_allowed:{pct_key}"
```

Add tests proving `refund_pct` on `Cancel_Order`, `retention_pct` on `Return`, and
`comp_pct` on `Partial_Refund` are all rejected.

## Warnings

### WR-01: Unknown / mistyped offered keys are silently ignored (not fail-closed)

**File:** `.claude/hooks/authorized_offer.py:273-278`
**Issue:** The cap loop iterates `THRESHOLD_CAPS` keys and reads them from `offered`.
Any key in `offered` that is not a known cap key is never inspected. Reproduced:
`authorize_offer("Partial_Refund","B7",{"refundpct":999,"refund_pct":50},...)` →
`(True,"authorized:B7")` — the typo'd `refundpct:999` is silently dropped. For a
fail-closed safety guard, an unrecognized offer dimension should escalate, not be
ignored.
**Fix:** After validating known caps, reject any offered key not in the known set:
`unknown = set(offered) - set(THRESHOLD_CAPS); if unknown: return False, f"unauthorized:unknown_offer_key:{sorted(unknown)[0]}"`. (Combines naturally with CR-02's allowed-key gate.)

### WR-02: Negative percentages and bool values pass the threshold check

**File:** `.claude/hooks/authorized_offer.py:277`
**Issue:** The cap check is only `offered_val > entry["cap"]`. A negative value
(`refund_pct: -10` → `-10 > 50` is False) passes, and `True` passes (`True == 1`).
Reproduced: `{"refund_pct": -10}` → authorized; `{"refund_pct": True}` → authorized.
A negative/bool value is a malformed payload that should fail-closed rather than be
treated as in-bounds, and silently coercing `True` → 1% is a type-confusion footgun.
**Fix:** Reject when `not isinstance(offered_val,(int,float))`, when
`isinstance(offered_val,bool)`, or when `offered_val < 0`; return
`unauthorized:invalid_offer_value:<key>`.

### WR-03: `authorize_offer` raises `TypeError` on non-numeric offered values; safety depends entirely on the caller's try/except

**File:** `.claude/hooks/authorized_offer.py:277` (raise site); `.claude/hooks/pre_send_guard.py:184-192` (caller)
**Issue:** `authorize_offer("Partial_Refund","B7",{"refund_pct":"100"},...)` raises
`TypeError: '>' not supported between instances of 'str' and 'int'`. The docstring
promises a deterministic `(bool,str)` return, but the function can throw. Today this is
contained because `pre_send_guard.main()` wraps the call in `except Exception → exit 2`.
But `authorized_offer.py` is also documented as consumed by the drafter path (module
docstring, "Consumed by ... drafter (plan 04-10)"), and any future caller that does not
wrap it inherits a crash instead of an escalate. A safety-core decision function should
never raise on caller-supplied data.
**Fix:** Coerce/validate inside `authorize_offer` (see WR-02) so it returns
`(False,"unauthorized:invalid_offer_value:<key>")` instead of raising. Keep the
caller try/except as defense-in-depth.

### WR-04: `_derive_operational_action` first-source-wins lets a benign top-level `customer_request` mask a nested escalating one

**File:** `.claude/hooks/escalation_gate.py:165-187` (with `_iter_payload_sources` :190-196)
**Issue:** The loop assigns `customer_request` from the **first** source that has it
(top-level wins over nested `tool_result`/`result`/`output`). Reproduced:
`{"customer_request":"Ask_About_Order","tool_result":{"customer_request":"Review"}}`
→ `operational_action` not set → no escalation. If two stages disagree, the benign
top-level value suppresses the escalating nested one. For a fail-closed additive gate
the safe resolution is "any source says Review/Full_Refund/mutation → escalate", not
"first source wins".
**Fix:** Scan all sources; escalate if *any* yields an escalating `customer_request`
or truthy `asserts_mutation`. For Rule 3, escalate if any source sets a
mutation-asserting sub-type and no source explicitly sets `asserts_mutation=False`.

## Info

### IN-01: STUB(RD-Q2) eligibility defaults are optimistic — known deferred (plan 04-11)

**File:** `.claude/hooks/authorized_offer.py:182-201` (`default_eligibility`), `:283`, `:292`; `.claude/hooks/pre_send_guard.py:181`
**Issue:** `default_eligibility()` returns `in_warranty=True, prior_remediation=False,
variant_in_stock=True`. When `pre_send_guard` receives an offer with no `eligibility`
dict it falls back to these optimistic defaults (`pre_send_guard.py:181`), so an offer
omitting the eligibility block is authorized as in-warranty/first-remediation. The
in-function gates (`:283`, `:292`) do fail-closed when *individual* fields are missing,
but the `default_eligibility()` fallback supplies the optimistic dict before those
gates run. Documented RD-Q2 PoC stub, deferred to plan 04-11.
**Fix:** None this phase (deferred by decision). When 04-11 wires Selless, replace the
call-site fallback `offer.get("eligibility") or default_eligibility()` with a real
lookup and consider escalating a no-eligibility-block offer instead of defaulting to
optimism.

### IN-02: STUB(RD-Q3) Full_Refund evidence-gating treated as satisfied — known deferred

**File:** `.claude/hooks/authorized_offer.py:288-294`
**Issue:** `Full_Refund` is documented as evidence-gated, but the §0 path treats
evidence as sufficient this phase (only warranty + prior-remediation gates apply);
A4/A5 authorize on `in_warranty=True` alone. The design relies on `escalation_gate`'s
`operational_action` escalation for `Full_Refund` as the real protection — but see
CR-01, where that escalation is currently bypassable, leaving this stub less protected
than assumed. Known deferred to plan 04-11.
**Fix:** None this phase; revisit alongside the CR-01 fix and 04-11 evidence wiring.

### IN-03: Docs claim an offer block is "required" for informational replies, but the guard does not enforce it — contract drift

**File:** `.claude/agents/drafter.md:212-223`, `.claude/skills/ground-and-draft/SKILL.md:217-226` vs `.claude/hooks/pre_send_guard.py:175-202`
**Issue:** Drafter/skill docs state "the offer block is still required" for
informational replies (empty `offered`). But `pre_send_guard` treats a missing offer
block + no commitment term as a clean pass (`:196-202`); the inquiry-sub-type
`authorized:no_offer` path in `authorize_offer` only runs when an offer block is
actually supplied. The documented hard requirement is neither enforced nor necessary —
harmless drift, but it can mislead maintainers into believing the guard validates
inquiry offer blocks.
**Fix:** Align the docs with enforced behavior (offer block optional when no commitment
term is present).

---

_Reviewed: 2026-06-04T02:05:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
