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
# SUBTYPE_ALLOWED_OFFER_KEYS
# Mapping: sub_type -> frozenset of offer-dimension keys that are LEGAL for that flow.
#
# Grounded in 04-AUTHORIZED-OFFER-RULES.md §2 and POLICY-THRESHOLD-INDEX.md:
#   Return           — refund (THR-07) + discount (THR-05)        §2A COMPLAINT
#   Partial_Refund   — refund (THR-07) + discount (THR-05)        §2A COMPLAINT
#   Full_Refund      — refund only (THR-07, evidence-gated)       §2A COMPLAINT §2A Q4
#   Replace          — no monetary pct offer; replacement is in-kind (A/B/G codes)
#   Cancel_Order     — retention_pct (THR-06 ≤20%) only           §2B CHANGE_REQUEST
#   Change_Shipping_Address  — no monetary pct dimension           §2B CHANGE_REQUEST
#   Change_Product_Variant   — no monetary pct dimension           §2B CHANGE_REQUEST
#   Change_Non_Shipping_Address / Express_Line — no monetary pct  §2B CHANGE_REQUEST
#   Ask_About_Delivery_Status — comp_pct (THR-08 ≤50%) for late-ship compensation §2C INQUIRY
#   Ask_About_Order/Policy/Product/Promotion — purely informational, no offer keys  §2C INQUIRY
#
# Fail-closed default: sub-types NOT listed here get frozenset() — any offered key is rejected.
# CR-02 fix: replaces global cap-only check with per-sub-type allowed-key gate.
# WR-01 fix: any key NOT in allowed set (including typos like "refundpct") is rejected.
# ---------------------------------------------------------------------------

SUBTYPE_ALLOWED_OFFER_KEYS: dict[str, frozenset[str]] = {
    # §2A COMPLAINT — Return: refund (THR-07) + discount (THR-05)
    # RULES §2A: "Offer alternatives BEFORE return: replacement OR 50% refund (THR-07),
    #             + 40% VIP discount + free shipping (THR-05)"
    "Return": frozenset({"refund_pct", "discount_pct"}),

    # §2A COMPLAINT — Replace: in-kind replacement, no monetary pct offer
    # RULES §2A: "Free replacement, keep original, request fit measurements"
    "Replace": frozenset(),

    # §2A COMPLAINT — Partial_Refund: refund (THR-07) + discount (THR-05)
    # RULES §2A: "50% refund (THR-07) + 40% discount (THR-05)"
    "Partial_Refund": frozenset({"refund_pct", "discount_pct"}),

    # §2A COMPLAINT — Full_Refund: refund only (THR-07); evidence-gated (RD-Q3)
    # RULES §2A §2A Q4: "Full refund per flow when variant unavailable / cannot replace"
    "Full_Refund": frozenset({"refund_pct"}),

    # §2A COMPLAINT — Review: always force-escalated (no flow); listed for completeness
    # RULES §2A Q2: "no dedicated template code found — named gap"
    "Review": frozenset(),

    # §2B CHANGE_REQUEST — Cancel_Order: retention_pct only (THR-06 ≤20%)
    # RULES §2B: "≤20% retention offer first (THR-06/16)"
    "Cancel_Order": frozenset({"retention_pct"}),

    # §2B CHANGE_REQUEST — Change_Shipping_Address: no monetary offer dimension
    # RULES §2B: "confirm address update; not yet shipped; valid address"
    "Change_Shipping_Address": frozenset(),

    # §2B CHANGE_REQUEST — Change_Product_Variant: no monetary offer dimension
    # RULES §2B: "variant swap + ask measurements; variant in stock"
    "Change_Product_Variant": frozenset(),

    # §2B CHANGE_REQUEST — Change_Non_Shipping_Address / Express_Line: no monetary offer
    # RULES §2B: "address/line edit; order state gate"
    "Change_Non_Shipping_Address": frozenset(),
    "Express_Line": frozenset(),

    # §2C INQUIRY — Ask_About_Delivery_Status (WISMO): comp_pct for late-ship compensation
    # RULES §2C: "if late (THR-09 >21d / THR-10 >35d) may offer compensation (THR-08 ≤50%)"
    "Ask_About_Delivery_Status": frozenset({"comp_pct"}),

    # §2C INQUIRY — purely informational sub-types: no monetary offer dimension
    "Ask_About_Order":     frozenset(),
    "Ask_About_Policy":    frozenset(),
    "Ask_About_Product":   frozenset(),
    "Ask_About_Promotion": frozenset(),
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

    # (d) Per-sub-type allowed-offer-key gate + value validation + threshold cap.
    #
    # CR-02 fix: each offered key is first checked against SUBTYPE_ALLOWED_OFFER_KEYS
    # for this sub_type. An out-of-flow key (e.g. refund_pct on Cancel_Order) is
    # rejected even if it is within the global threshold cap, because threshold caps
    # are global while offer dimensions are per-flow. fail-closed: sub-types not in
    # the map default to frozenset() (any key rejected).
    #
    # WR-01 fix: unknown/mistyped keys (not in SUBTYPE_ALLOWED_OFFER_KEYS AND not in
    # THRESHOLD_CAPS) are also caught here — any key not in the allowed set is rejected.
    #
    # WR-02/WR-03 fix: value type and range are validated inside authorize_offer so the
    # function never raises on caller-supplied data (bool, str, negative → reject).
    allowed_offer_keys = SUBTYPE_ALLOWED_OFFER_KEYS.get(sub_type, frozenset())
    for offered_key, offered_val in offered.items():
        # CR-02 / WR-01: reject any key not in the allowed set for this sub_type.
        # This catches both out-of-flow legitimate keys (e.g. refund_pct on Cancel_Order)
        # and unknown/mistyped keys (e.g. "refundpct") in a single gate.
        if offered_key not in allowed_offer_keys:
            return False, f"unauthorized:offer_key_not_allowed:{offered_key}"

        # WR-02 / WR-03: validate value type and range before any comparison.
        # bool is a subclass of int in Python — must be rejected before int check.
        # str values would raise TypeError on ">"; negative values are nonsensical.
        # The function must always return (bool, str), never raise.
        if isinstance(offered_val, bool):
            return False, f"unauthorized:invalid_offer_value:{offered_key}"
        if not isinstance(offered_val, (int, float)):
            return False, f"unauthorized:invalid_offer_value:{offered_key}"
        if offered_val < 0:
            return False, f"unauthorized:invalid_offer_value:{offered_key}"

        # Threshold cap check (only for recognized cap keys).
        cap_entry = THRESHOLD_CAPS.get(offered_key)
        if cap_entry is not None and offered_val > cap_entry["cap"]:
            return False, f"unauthorized:over_threshold:{cap_entry['thr_id']}"

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
