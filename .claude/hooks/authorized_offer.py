"""
authorized_offer — D-26 guard core (SAFE-04).

Deterministic, LLM-free, stdlib-only module.
Decides AUTHORIZED vs UNAUTHORIZED for a drafted offer given:
  (sub_type, template_code, offered, eligibility, asserts_mutation)

§0 gate order (applied in sequence — first failure wins):
  (a) Force-escalate sub-types (Review) or asserts_mutation=True
  (b) Inquiry sub-types with no offer → authorized:no_offer
  (c) template_code must be in TEMPLATE_REGISTRY[sub_type]
  (d) Each offered pct must be ≤ its cap (THRESHOLD_CAPS)
  (e) eligibility["in_warranty"] must be True
  (f) eligibility["prior_remediation"] must be False
  (g) All clear → authorized

Contract (mirrors src/guards/loop_guard.should_suppress):
    authorize_offer(...) -> tuple[bool, str]
    - bool: True = authorized (allow draft)
    - str:  reason label (e.g. "authorized:B7", "unauthorized:over_threshold:THR-07")

No LLM calls. No network. No third-party imports.

Consumed by:
  - .claude/hooks/pre_send_guard.py (plan 04-09): replaces block-all with §0 test
  - .claude/skills/ground-and-draft/ drafter (plan 04-10): template selection guidance

Eligibility stub:
  See default_eligibility() and the STUB markers below (RD-Q2, RD-Q3).
  Plan 04-11 replaces the stub with real Selless-grounded eligibility data.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TEMPLATE_REGISTRY
# Mapping: sub_type -> frozenset of approved template codes for that flow.
# Derived from CODE-MAP-templates.md (Phase 1 survey).
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY: dict[str, frozenset[str]] = {
    # COMPLAINT — non-defective (fit/satisfaction): B-codes + some A/C codes
    "Return": frozenset({
        # B-codes: within-guarantee, non-defective return flow
        "B3", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12", "B13",
        # A-codes: within-guarantee, defective/wrong/missing items return variants
        "A4", "A5", "A6", "A7", "A8", "A9",
        # C-code: out-of-guarantee (discount only, no replacement/refund)
        "C1",
    }),

    # COMPLAINT — replacement flow (A-codes + G11/G14 DNR/RTS replacements)
    "Replace": frozenset({
        "A1", "A2", "A3",   # can-replace variants (request measurements)
        "B1", "B2",          # non-defective can-replace
        "G11", "G14",        # DNR / RTS complimentary replacement (shipping inquiry)
    }),

    # COMPLAINT — partial refund (B7 cannot-replace, B3 variant-unavailable, A9 partial)
    "Partial_Refund": frozenset({
        "B3",   # cannot replace, variant unavailable: 50% OR 40%+free-ship
        "B7",   # cannot replace: 50% refund AND 40%+free-ship
        "A9",   # within-guarantee partial refund (variable amount)
    }),

    # COMPLAINT — full refund (evidence-gated; stricter checks apply — see STUB RD-Q3)
    "Full_Refund": frozenset({
        "A4",   # cannot replace, evidence provided: full refund
        "A5",   # cannot replace, evidence needed: requests proof
        "A9",   # partial/full hybrid (variable refund amount)
        "G15",  # DNR full refund option
    }),

    # Review complaint — NO flow exists (Phase-1 gap); always force-escalate
    # (Handled via FORCE_ESCALATE_SUBTYPES — empty set here is belt-and-suspenders)
    "Review": frozenset(),

    # CHANGE_REQUEST — cancellation (retention F-codes; ≤20% retention offer)
    "Cancel_Order": frozenset({
        # Can-cancel retention codes (New/Processing/Pending orders)
        "F1", "F2", "F3", "F4", "F7", "F9", "F10", "F14", "F15", "F16", "F21", "F23",
        # In-transit / SCE-confirm codes
        "F5", "F17", "F18",
        # Cannot-cancel codes (order in processing / delivered)
        "F6", "F8", "F11", "F19", "F20",
        # Confirmation / resume codes
        "F12", "F13", "F22",
    }),

    # CHANGE_REQUEST — shipping address (E-codes)
    "Change_Shipping_Address": frozenset({
        "E1",    # can change (within window)
        "E2",    # in-transit, SCE to confirm
        "E3",    # cannot change (delivered)
        "E13",   # invalid address warning
    }),

    # CHANGE_REQUEST — product variant (E-codes)
    "Change_Product_Variant": frozenset({
        "E4",    # can change, same/lower price (request measurements)
        "E5",    # can change, higher price (invoice sent)
        "E6",    # in-transit, SCE to confirm
        "E7",    # cannot change (delivered)
        "E10",   # cannot add items (offer 20% discount on new order)
        "E11",   # variant changed successfully
        "E12",   # resumed original after no response
    }),

    # INQUIRY — informational sub-types; no template-gated commitment required.
    # Ask_About_Delivery_Status (WISMO) may carry a late-ship compensation offer
    # (THR-08 ≤50%) using shipping-inquiry G-codes. When offered dict is non-empty
    # it falls through to §0(c)/(d) checks — G-codes are valid templates here.
    # All other inquiry sub-types have empty sets (no commitment template required).
    "Ask_About_Delivery_Status": frozenset({
        # Common-scenario shipping templates (G1–G9) used for WISMO with comp offers
        "G1", "G2", "G4", "G5", "G6", "G7", "G8", "G9",
        # DNR templates (tracking + replacement)
        "G10", "G11", "G13", "G14", "G15",
        # OOS templates
        "G3.1", "G3.2",
        # Test-contract template
        "G12",
    }),
    "Ask_About_Order":           frozenset(),   # order details from Selless; no offer template
    "Ask_About_Policy":          frozenset(),   # cited KB policy; no offer template
    "Ask_About_Product":         frozenset(),   # product facts via scoped API; no offer template
    "Ask_About_Promotion":       frozenset(),   # cited promo/KB; no offer template (do not invent)
}

# ---------------------------------------------------------------------------
# THRESHOLD_CAPS
# Mapping: cap_key -> {"cap": <numeric>, "thr_id": "<THR-XX>"}
# Each offered percentage is checked against the relevant cap.
# Derived from POLICY-THRESHOLD-INDEX.md (Phase 1 survey).
# ---------------------------------------------------------------------------

THRESHOLD_CAPS: dict[str, dict] = {
    # refund_pct cap: Return / Partial_Refund / Full_Refund flows
    # THR-07: 50% refund offer (B7/B3 product complaint non-warranty path)
    "refund_pct": {"cap": 50, "thr_id": "THR-07"},

    # discount_pct cap: aftersale VIP promotion (40% + free shipping)
    # THR-05: 40% discount + free shipping (C1/B7/B3 complaint templates)
    "discount_pct": {"cap": 40, "thr_id": "THR-05"},

    # retention_pct cap: cancellation retention offer (≤20%)
    # THR-06: courtesy/retention cap (Cancel_Order F-codes)
    "retention_pct": {"cap": 20, "thr_id": "THR-06"},

    # comp_pct cap: late-shipment compensation (WISMO / Ask_About_Delivery_Status)
    # THR-08: up to 50% discount in shipping common scenarios
    "comp_pct": {"cap": 50, "thr_id": "THR-08"},
}

# ---------------------------------------------------------------------------
# FORCE_ESCALATE_SUBTYPES
# Sub-types that ALWAYS escalate — no template-based offer exists.
# "Review" = RULES §2A gap confirmed (Q2: no dedicated template, CS team to define flow).
# ---------------------------------------------------------------------------

FORCE_ESCALATE_SUBTYPES: frozenset[str] = frozenset({"Review"})

# ---------------------------------------------------------------------------
# INQUIRY_SUBTYPES
# Sub-types that are purely informational — no commitment template required.
# An empty offered dict for these is always authorized:no_offer.
# ---------------------------------------------------------------------------

_INQUIRY_SUBTYPES: frozenset[str] = frozenset({
    "Ask_About_Delivery_Status",
    "Ask_About_Order",
    "Ask_About_Policy",
    "Ask_About_Product",
    "Ask_About_Promotion",
})


# ---------------------------------------------------------------------------
# Eligibility stub
# ---------------------------------------------------------------------------

def default_eligibility() -> dict:
    """Return the PoC stub eligibility dict (RD-Q2).

    # STUB (RD-Q2): real eligibility comes from Selless MCP in plan 04-11.
    # This stub returns optimistic defaults so the PoC pipeline can draft
    # in-warranty, first-remediation, in-stock cases without a live lookup.
    # Plan 04-11 replaces this function with a Selless-grounded check.
    # Fail-closed posture: when fields are absent, authorize_offer defaults
    # to False for in_warranty and True for prior_remediation (blocks offer).

    Fields:
      in_warranty (bool): True if order is within THR-03/THR-04 window.
      prior_remediation (bool): True if a prior refund/replacement was given.
      variant_in_stock (bool): True if replacement variant is available.
    """
    return {
        "in_warranty": True,
        "prior_remediation": False,
        "variant_in_stock": True,
    }


# ---------------------------------------------------------------------------
# Core guard function
# ---------------------------------------------------------------------------

def authorize_offer(
    sub_type: str,
    template_code: str | None = None,
    offered: dict | None = None,
    eligibility: dict | None = None,
    asserts_mutation: bool = False,
) -> tuple[bool, str]:
    """Decide AUTHORIZED vs UNAUTHORIZED for a drafted offer.

    Parameters
    ----------
    sub_type : str
        Level-2 Customer_Request taxonomy value (e.g. "Return", "Partial_Refund").
    template_code : str | None
        The template code the drafter selected (e.g. "B7", "F1").
        Required for offer sub-types; optional for inquiry sub-types.
    offered : dict | None
        Numeric offer values to check against THRESHOLD_CAPS.
        Keys: "refund_pct", "discount_pct", "retention_pct", "comp_pct".
        Missing keys are not checked.
    eligibility : dict | None
        Eligibility state for the order.
        # STUB (RD-Q2): replaced by real Selless check in plan 04-11.
        Keys: "in_warranty" (bool), "prior_remediation" (bool), "variant_in_stock" (bool).
        Missing keys default to fail-closed values (False for in_warranty, True for
        prior_remediation).
    asserts_mutation : bool
        True when the draft claims a completed operational action
        (cancel/address/variant change). Per RD-Q1 and §1, the AI must not
        assert a mutation it did not cause. Forces unauthorized.

    Returns
    -------
    tuple[bool, str]
        (True, "authorized:<code>") when the offer is authorized.
        (False, "unauthorized:<reason>") for any failure.
        Reason strings are deterministic (no randomness).
    """
    if offered is None:
        offered = {}
    if eligibility is None:
        eligibility = {}

    # (a) Force-escalate sub-types — no flow exists
    if sub_type in FORCE_ESCALATE_SUBTYPES:
        return False, "unauthorized:force_escalate:no_flow"

    # (a) Operational-action assertion boundary (RD-Q1 / §1)
    # The AI must not claim "we've canceled/updated…" without the mutation
    # having occurred. Any draft asserting a completed mutation is blocked.
    if asserts_mutation:
        return False, "unauthorized:operational_assertion"

    # (b) Inquiry sub-types with no meaningful offer → authorized:no_offer
    # These are purely informational; no template-gated commitment required.
    # Exception: Ask_About_Delivery_Status may carry a compensation offer
    # (THR-08 ≤50%) — if offered dict is non-empty, fall through to checks.
    if sub_type in _INQUIRY_SUBTYPES and not offered:
        return True, "authorized:no_offer"

    # (c) Template code must be in the registry for this sub-type
    approved_templates = TEMPLATE_REGISTRY.get(sub_type, frozenset())
    if template_code is None or template_code not in approved_templates:
        return False, "unauthorized:out_of_template"

    # (d) Each offered percentage must be ≤ its threshold cap
    for pct_key, entry in THRESHOLD_CAPS.items():
        offered_val = offered.get(pct_key)
        if offered_val is not None:
            if offered_val > entry["cap"]:
                return False, f"unauthorized:over_threshold:{entry['thr_id']}"

    # (e) Warranty eligibility gate
    # STUB (RD-Q2): real eligibility comes from Selless MCP in plan 04-11.
    # Fail-closed default: missing in_warranty treated as False (blocked).
    in_warranty = eligibility.get("in_warranty", False)
    if not in_warranty:
        return False, "unauthorized:ineligible:warranty"

    # (f) Prior-remediation gate — no second remediation at the same tier
    # STUB (RD-Q2): real prior-remediation state from Selless in plan 04-11.
    # STUB (RD-Q3): evidence treated as sufficient this phase (Full_Refund
    # evidence-gating deferred — plan 04-11 adds photo/label verification).
    # Fail-closed default: missing prior_remediation treated as True (blocked).
    prior_remediation = eligibility.get("prior_remediation", True)
    if prior_remediation:
        return False, "unauthorized:second_remediation"

    # All §0 checks passed — offer is authorized
    return True, f"authorized:{template_code}"
