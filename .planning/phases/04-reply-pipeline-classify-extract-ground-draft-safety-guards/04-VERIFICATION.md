---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
verified: 2026-06-04T02:35:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed:
    - "CR-01: operational_action escalation bypass with explicit signals dict — FIXED (escalation_gate now always derives operational_action regardless of signals source; commit 36aa73c)"
    - "CR-02: out-of-flow offer keys authorized globally — FIXED (SUBTYPE_ALLOWED_OFFER_KEYS per-sub-type gate added; commit b5b121e)"
    - "WR-01/WR-02/WR-03: unknown keys, negative values, TypeError in authorize_offer — FIXED (same commit b5b121e)"
    - "WR-04: first-source-wins masked nested escalating customer_request — FIXED (any-source-escalates across all payload sources; commit 36aa73c)"
    - "IN-03: offer block documented as required for informational replies — docs aligned (commit 05a63e4)"
    - "SC4 (Criterion #4 REVISED): authorized-offer guard built — PERMIT authorized templated offers; BLOCK unauthorized commitments"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Update .claude/CLAUDE.md D-13 section to document D-26 supersession"
    expected: "D-13 section updated (or replaced) to state D-26 supersedes block-all for Phase 4+; safety contract matches what pre_send_guard.py actually enforces"
    why_human: "CLAUDE.md still documents D-13 as block-ALL commitment language with no mention of D-26 or authorized-offer exceptions. pre_send_guard.py docstring says D-26 SUPERSEDES D-13 but CLAUDE.md was not updated by the IN-03 fix (only drafter.md and skill were updated). Deterministic enforcement is unaffected but the safety contract is misleading. Requires developer decision on intended contract wording."
  - test: "Live pipeline round-trip: authorized Partial_Refund offer reaches submit_reply with exit 0"
    expected: "Drafter produces offer block (sub_type=Partial_Refund/Return, template_code in B-codes, pcts within THR-07/THR-05); pre_send_guard exits 0; escalation_gate exits 0; submit_reply reached (DRY_RUN=True to suppress Freshdesk post)"
    why_human: "The reopen's critical new behavior is that AUTHORIZED offers now PASS. Subprocess tests confirm exit 0 for authorized payloads. A full drafter→guard→submit_reply round-trip with real LLM-produced offer block has not been run end-to-end."
  - test: "Live pipeline round-trip: Review ticket never reaches submit_reply"
    expected: "escalation_gate WRITE fires operational_action=True; submit_reply PreToolUse veto exits 2; action=escalate; no customer reply"
    why_human: "CR-01 fix verified via subprocess and live WRITE→READ repro. Full Claude Code session confirmation required to prove the hook dispatch chain with real LLM classifier output emitting customer_request=Review."
deferred:
  - truth: "authorize_offer reads real eligibility (warranty dates THR-03/04, prior-remediation, real variant stock) from Selless instead of the RD-Q2 stub"
    addressed_in: "Plan 04-11 (deferred by checkpoint decision not-ready on 2026-06-04)"
    evidence: "04-11-SUMMARY.md: decision=not-ready; Selless eligibility fields do not yet exist; STUB(RD-Q2) markers retained in authorized_offer.py; guard structure already accepts real fields at swap points"
  - truth: "Full_Refund / evidence-gated paths validate real submitted evidence (photo + shipping label) instead of accept-as-sufficient (RD-Q3)"
    addressed_in: "Plan 04-11 (deferred by checkpoint decision not-ready on 2026-06-04)"
    evidence: "04-11-SUMMARY.md: STUB(RD-Q3) retained; evidence intake model not yet decided; escalation_gate operational_action signal serves as interim protection for Full_Refund"
---

# Phase 04 (Reopen): Reply Pipeline — D-26 Authorized-Offer Guard Verification Report

**Phase Goal (Reopen):** Assemble the per-ticket pipeline that re-classifies the ticket, extracts the answer key, drafts a citation-grounded reply via the two MCPs, self-critiques against the rubric, and is wrapped by escalation rules + output guards that make it safe to evaluate — with criterion #4 REVISED to block UNAUTHORIZED commitments while PERMITTING authorized templated offers within policy.

**Verified:** 2026-06-04T02:35:00Z
**Status:** human_needed
**Re-verification:** Yes — after reopen plans 04-06 through 04-10 (04-11 deferred by explicit not-ready checkpoint decision 2026-06-04)
**Plans executed this reopen:** 04-06 (authorized_offer module), 04-07 (classifier sub-type), 04-08 (escalation gate operational_action), 04-09 (pre_send_guard D-26), 04-10 (drafter D-26)
**Plans deferred:** 04-11 (real eligibility wiring — checkpoint decision not-ready)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Classifier emits `customer_request` level-2 sub-type from the 13-value RULES §2 enum; stays on Haiku; fail-closed null on ambiguity | ✓ VERIFIED | 13 sub-types in classifier.md (`grep -oE` count = 13); `model: claude-haiku-4-5` = 1; `customer_request` in output JSON; fail-closed rule documented; structural contract test passes in 276-test suite |
| 2 | Drafter selects templates by sub-type, grounds eligibility via Selless (RD-Q2 stub), passes structured offer block to submit_reply; never asserts completed operational action (RD-Q1) | ✓ VERIFIED | drafter.md: Sonnet count=1, asserts_mutation count=4, D-26 count=4, RD-Q2 count=5, "absolutely forbidden"=0, submit_reply=9; ground-and-draft/SKILL.md: D-26=3, customer_request=7, old D-13 ban section=0 |
| 3 | High-risk tickets (Review, Full_Refund, mutation-asserting change_request) auto-escalate at submit_reply via operational_action signal — additive, fail-closed, CR-01 fixed | ✓ VERIFIED | Live WRITE→READ repro: `signals={all-False}+customer_request="Review"` → WRITE exit=1 (`operational_action=true` in state); READ PreToolUse@submit_reply → exit=2 (BLOCKED). 6 signals in `_SIGNAL_ORDER`; `sys.exit(2)` = 3; 276 tests passed |
| 4 (REVISED) | Authorized-offer guard: BLOCKS unauthorized commitments (out-of-template, over-threshold, ineligible, out-of-flow keys, force-escalate sub-types); PERMITS authorized templated offers (exit 0); email body delimited and injection-screened | ✓ VERIFIED | Live checks: B7 50%+40% → exit=0; 70% refund → exit=2 (THR-07); commitment-without-offer → exit=2; Cancel_Order+refund_pct → exit=2 (CR-02 SUBTYPE_ALLOWED_OFFER_KEYS); Review → exit=2 (force_escalate). All 4 THR IDs present; 5 STUB markers; no network imports; injection_screen.py exists |

**Score:** 4/4 truths verified

---

### Deferred Items

Items not yet met but explicitly addressed via recorded decision (plan 04-11 not-ready checkpoint 2026-06-04).

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Real eligibility grounding (warranty window THR-03/04, prior-remediation, variant stock) replacing STUB(RD-Q2) | Plan 04-11 (deferred) | 04-11-SUMMARY.md: decision=not-ready; Selless fields do not yet exist; STUB markers at swap points in authorized_offer.py |
| 2 | Full_Refund evidence-gating (photo + shipping label) replacing STUB(RD-Q3) | Plan 04-11 (deferred) | 04-11-SUMMARY.md: evidence intake model not decided; operational_action signal as interim protection |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.claude/hooks/authorized_offer.py` | D-26 core: TEMPLATE_REGISTRY + THRESHOLD_CAPS + SUBTYPE_ALLOWED_OFFER_KEYS + FORCE_ESCALATE + default_eligibility + authorize_offer | ✓ VERIFIED | stdlib-only (comment "requests proof" is not an import); all 4 THR IDs (THR-05..08); 5 STUB markers; def authorize_offer → (bool, str); SUBTYPE_ALLOWED_OFFER_KEYS with per-sub-type allowed-key gate (CR-02 fix) |
| `.claude/hooks/pre_send_guard.py` | D-26 tripwire + authorize_offer delegation; exit 0 authorized, exit 2 unauthorized; no auto-strip | ✓ VERIFIED | `authorize_offer` references=10; `sys.exit(2)`=2; `sys.exit(0)`=1; `D-26`=4; no `.replace(` or `re.sub(` |
| `.claude/hooks/escalation_gate.py` | 6-signal OR-gate; CR-01 fix (always derives operational_action); CR-04/WR-04 any-source-escalates; fail-closed READ veto | ✓ VERIFIED | `_SIGNAL_ORDER` has 6 entries; all 5 original keys present; `_derive_operational_action` called unconditionally after any signals source; `sys.exit(2)`=3 |
| `.claude/agents/classifier.md` | 13 sub-type enum; Haiku; customer_request output field; fail-closed null | ✓ VERIFIED | All checks pass |
| `.claude/agents/drafter.md` | Sonnet; template-select by sub-type; eligibility stub (RD-Q2); D-26 offer block; RD-Q1 non-assertion; blanket ban removed | ✓ VERIFIED | All markers present; "absolutely forbidden"=0 |
| `.claude/skills/ground-and-draft/SKILL.md` | D-26 authorized offer section; customer_request; no D-13 ban | ✓ VERIFIED | D-26=3, customer_request=7, "Commitment Language Ban (D-13)"=0 |
| `.claude/skills/classify-ticket/SKILL.md` | customer_request sub-type taxonomy | ✓ VERIFIED | customer_request=4 |
| `tests/cs_team/test_authorized_offer.py` | ≥13 sub-types covered; authorized + unauthorized axes per RULES §2 row | ✓ VERIFIED | 59 test functions; 13 sub-types; passes |
| `tests/cs_team/test_classifier_subtype_contract.py` | All 13 sub-types; Haiku retention | ✓ VERIFIED | Exists; passes |
| `tests/cs_team/test_escalation_gate_operational.py` | Subprocess: Review → exit 2; existing signals survive | ✓ VERIFIED | Exists; passes |
| `tests/cs_team/test_pre_send_guard_authorized.py` | Subprocess: authorized=exit 0; each unauthorized axis=exit 2 | ✓ VERIFIED | returncode==0 assertions=2; returncode==2 assertions=10; passes |
| `tests/cs_team/test_drafter_offer_contract.py` | offer block; RD-Q1; no blanket ban in drafter/skill | ✓ VERIFIED | Exists; passes |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pre_send_guard.py` | `authorized_offer.py` | `_load_authorized_offer()` by absolute path + `authorize_offer(...)` call in `main()` | ✓ WIRED | importlib loads sibling by Path; authorize_offer called with offer fields; `grep -c "authorize_offer"` = 10 |
| `classifier.md` | `escalation_gate.py` | `customer_request` sub-type drives `_derive_operational_action` | ✓ WIRED | `_derive_operational_action` checks `customer_request ∈ {"Review","Full_Refund"}` and mutation sub-types across all payload sources (WR-04 any-source fix) |
| `drafter.md` | `pre_send_guard.py` | structured `offer` block in `submit_reply` `tool_input` consumed by `_extract_offer` | ✓ WIRED | drafter.md Step 6 shows full offer block JSON; `_extract_offer` reads `tool_input["offer"]` |
| `escalation_gate.py` | state file | WRITE (PostToolUse) OR-merge → READ (PreToolUse@submit_reply) veto | ✓ WIRED | Live repro: WRITE signals+Review → `operational_action=true` in state; READ submit_reply → exit=2 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `authorized_offer.py` | `eligibility["in_warranty"]` | `default_eligibility()` RD-Q2 stub | No — optimistic PoC stub; plan 04-11 deferred | ⚠️ STUB (accepted deferral, STUB markers present) |
| `authorized_offer.py` | `TEMPLATE_REGISTRY`, `THRESHOLD_CAPS`, `SUBTYPE_ALLOWED_OFFER_KEYS` | Module-level literals from CODE-MAP + POLICY-THRESHOLD-INDEX (Phase 1 survey) | Yes — deterministic policy data | ✓ FLOWING |
| `escalation_gate.py` | `signals["operational_action"]` | Derived from `customer_request` + `asserts_mutation` across all payload sources | Yes — real derivation from stage payloads | ✓ FLOWING |
| `pre_send_guard.py` | `offer["sub_type"]`, `offer["offered"]` | Drafter-supplied via `submit_reply` `tool_input["offer"]` | Flows through; validated against fixed registries | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Authorized B7 offer (50%+40%) → exit 0 | `printf '...offer:{sub_type:Partial_Refund,B7,refund_pct:50,discount_pct:40,...}' \| python pre_send_guard.py` | exit=0 | ✓ PASS |
| Over-threshold refund (70%) → exit 2 | Same but refund_pct:70 | exit=2, `pre_send_guard:unauthorized:over_threshold:THR-07` | ✓ PASS |
| Commitment term without offer block → exit 2 | `{"body":"We will refund you fully."}` | exit=2, `unauthorized:commitment_without_offer` | ✓ PASS |
| CR-01 fix: signals dict + Review → WRITE exit 1, READ exit 2 | WRITE `signals={all-False}+customer_request=Review`; READ `PreToolUse@submit_reply` | WRITE exit=1; READ exit=2 (BLOCKED) | ✓ PASS |
| CR-02 fix: Cancel_Order + refund_pct rejected | `authorize_offer("Cancel_Order","F1",{"refund_pct":50},...)` | `(False, "unauthorized:offer_key_not_allowed:refund_pct")` | ✓ PASS |
| Review → force_escalate | `authorize_offer("Review")` | `(False, "unauthorized:force_escalate:no_flow")` | ✓ PASS |
| asserts_mutation=True → unauthorized | `authorize_offer("Change_Shipping_Address",...,asserts_mutation=True)` | `(False, "unauthorized:operational_assertion")` | ✓ PASS |
| Full test suite | `.venv/bin/pytest tests/cs_team -q` | 276 passed, 6 skipped | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| REP-01 | 04-07 (reopen) | AI re-classifies ticket into correct support category + sub-type | ✓ SATISFIED | classifier.md emits category + 13-value customer_request sub-type; Haiku; structural contract test |
| REP-02 | 04-00..04-05 (pre-reopen) | AI extracts key info (order ref, customer, issue type) | ✓ SATISFIED | extractor.md exists; REQUIREMENTS.md traceability row is stale (marks Pending but artifact present and previously verified) |
| REP-03 | 04-10 (reopen) | AI drafts grounded reply with citations (no ungrounded claims) | ✓ SATISFIED | drafter.md D-11 inline citations; grounding_check.py at submit_reply chokepoint; ground-and-draft/SKILL.md |
| REP-04 | 04-00..04-05 (pre-reopen) | AI self-critique pass before send | ✓ SATISFIED | critic.md + self-critique/SKILL.md exist; REQUIREMENTS.md traceability row stale |
| SAFE-03 | 04-08 (reopen) | High-risk tickets auto-routed to human | ✓ SATISFIED | escalation_gate.py: high_risk_category + operational_action (Review/Full_Refund/mutation) force exit 2; live repro confirmed; REQUIREMENTS.md row stale (marks Pending) |
| SAFE-04 | 04-06, 04-09 (reopen) | Output guard blocks unauthorized commitments | ✓ SATISFIED | authorized_offer.py §0 gate; pre_send_guard.py D-26 tripwire + authorize_offer; authorized exit 0; all unauthorized axes exit 2 |

**Note:** REP-02, REP-04, SAFE-03 are marked Pending in REQUIREMENTS.md traceability table but implementations were verified in prior phases. The traceability table was not updated after those verifications — a stale bookkeeping issue, not a code gap.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.claude/CLAUDE.md` | 46 | D-13 section documents "Commitment language is blocked" (block-ALL) with no mention of D-26 or authorized-offer exceptions | ⚠️ WARNING | Contract-vs-code drift. pre_send_guard.py docstring states "D-26 SUPERSEDES the block-all D-13 guard" but CLAUDE.md safety contract was not updated (IN-03 fix updated drafter.md + skill only). No impact on deterministic enforcement — hooks enforce D-26 regardless — but misleads agent-team reasoning and maintainers. Routed to human verification item #1. |
| `.claude/hooks/authorized_offer.py` | 253–272 | `default_eligibility()` optimistic stub (in_warranty=True, prior_remediation=False) | ℹ️ INFO (accepted) | Known RD-Q2 PoC deferral. STUB markers present (5 occurrences). Plan 04-11 deferred by explicit not-ready checkpoint decision. |

---

### Human Verification Required

#### 1. Update .claude/CLAUDE.md D-13 to document D-26 supersession

**Test:** Read `.claude/CLAUDE.md` D-13 section (line 46). Decide whether to update D-13 to note D-26 supersedes it, replace D-13 with a D-26 section, or add a D-26 section after D-13. Edit accordingly so the safety contract matches what `pre_send_guard.py` actually enforces.

**Expected:** The safety contract accurately reflects that authorized templated offers within policy thresholds (per §0 of 04-AUTHORIZED-OFFER-RULES.md) are now PERMITTED — not blocked — by `pre_send_guard.py`. The old "block ALL commitment language" language should either be removed or qualified.

**Why human:** Contract wording decision. The verifier can confirm the drift exists (it does) but cannot choose the intended contract language on the developer's behalf. Fix is trivial but must reflect developer intent.

#### 2. Live pipeline round-trip: authorized offer passes through (SC4 PERMIT path)

**Test:** Run a Return or Partial_Refund ticket through the live Claude Code agent team (CS_RUN_ID exported) with an in-warranty order (use RD-Q2 stub defaults). Confirm the drafter emits a structured offer block, pre_send_guard exits 0, escalation_gate exits 0, and submit_reply is reached (DRY_RUN=True to suppress actual Freshdesk post).

**Expected:** Drafter produces offer block with sub_type in {Return, Partial_Refund}, template_code within B-codes (B3/B5/B6/B7), offered pcts within THR-07 (≤50%) and THR-05 (≤40%); guard chain exits 0; submit_reply call executed.

**Why human:** The critical new behavioral change of this reopen is that AUTHORIZED offers now PASS pre_send_guard. Subprocess tests confirm exit 0 for hardcoded authorized payloads. A full round-trip with real LLM-produced offer block is needed to confirm the drafter correctly emits the offer block in practice.

#### 3. Live pipeline round-trip: Review ticket never reaches submit_reply

**Test:** Run a ticket classified as Review through the live pipeline. Confirm operational_action=True is set at the WRITE stage and submit_reply PreToolUse veto fires exit 2.

**Expected:** escalation_gate WRITE exits 1 with `escalate:operational_action`; READ exits 2; action=escalate returned; no customer reply produced.

**Why human:** CR-01 fix verified via subprocess and live WRITE→READ repro. Full Claude Code session confirmation confirms hook dispatch chain with real LLM classifier output.

---

### Gaps Summary

No blocking gaps. All 4 success criteria for the reopen scope verified in the codebase.

One WARNING: `.claude/CLAUDE.md` D-13 section documents block-all behavior that was superseded by D-26 in plan 04-09. The IN-03 doc fix updated drafter.md and ground-and-draft/SKILL.md but not the canonical agent safety contract. Deterministic enforcement is unaffected. Routed to human verification item #1.

Two deferred items (RD-Q2 real eligibility, RD-Q3 evidence-gating) accepted by explicit not-ready checkpoint decision on 2026-06-04. These are carry-forwards to a future phase when the Selless eligibility surface and evidence intake model are built.

---

_Verified: 2026-06-04T02:35:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after reopen plans 04-06..04-10 (04-11 deferred by checkpoint decision)_
