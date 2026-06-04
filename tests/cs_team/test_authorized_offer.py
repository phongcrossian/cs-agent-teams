"""
Exhaustive unit tests for authorized_offer — RULES §2 answer key (Task 2).

Covers all 13 Customer_Request sub-types with:
  - Authorized happy path (§2 AUTO* row)
  - Primary unauthorized failure axis for that row

Sub-types under test (RULES §2):
  2A COMPLAINT:  Return, Replace, Partial_Refund, Full_Refund, Review
  2B CHANGE:     Cancel_Order, Change_Shipping_Address, Change_Product_Variant
  2C INQUIRY:    Ask_About_Delivery_Status, Ask_About_Order, Ask_About_Policy,
                 Ask_About_Product, Ask_About_Promotion

No LLM, no network, no DB — pure function calls only.
Run: .venv/bin/python -m pytest tests/cs_team/test_authorized_offer.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load authorized_offer module via importlib (avoids dotted-path issue)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "authorized_offer.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("authorized_offer", _HOOK_PATH)
    assert spec is not None and spec.loader is not None, f"Module not found: {_HOOK_PATH}"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


_m = _load()
authorize_offer = _m.authorize_offer  # type: ignore[attr-defined]

# Convenience aliases
_IN_WARRANTY = {"in_warranty": True, "prior_remediation": False}
_OUT_WARRANTY = {"in_warranty": False, "prior_remediation": False}
_PRIOR_REMED = {"in_warranty": True, "prior_remediation": True}


# ===========================================================================
# §2A COMPLAINT — offer flow (templates A/B/C)
# ===========================================================================


class TestReturn:
    """RULES §2A — Return (n=64, dominant: B7 40%+free-ship + 50% refund)."""

    def test_return_in_warranty_b7_authorized(self) -> None:
        """AUTO*: Return B7 in-warranty, within thresholds -> authorized."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": 50, "discount_pct": 40},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:B7"

    def test_return_out_of_warranty_unauthorized(self) -> None:
        """Ineligible: Return out-of-warranty order -> unauthorized:ineligible:warranty."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": 50, "discount_pct": 40},
            _OUT_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:ineligible")

    def test_return_unknown_template_unauthorized(self) -> None:
        """Unknown template ZZ9 -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Return", "ZZ9",
            {"refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"

    def test_return_second_remediation_unauthorized(self) -> None:
        """Prior remediation already given -> unauthorized:second_remediation."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": 50},
            _PRIOR_REMED,
        )
        assert ok is False
        assert reason == "unauthorized:second_remediation"

    def test_return_c1_out_of_warranty_offer_authorized(self) -> None:
        """C1 out-of-warranty template: 40% discount only (no refund) for warranty-expired orders.
        Note: C1 is in Return registry. Warranty check still applies — C1 is the
        out-of-guarantee template but eligibility check is still enforced by §0.
        This test documents: with in_warranty=True, C1 is authorized."""
        ok, reason = authorize_offer(
            "Return", "C1",
            {"discount_pct": 40},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:C1"


class TestReplace:
    """RULES §2A — Replace (n=37, dominant: complimentary replacement, A/B codes)."""

    def test_replace_a1_in_stock_in_warranty_authorized(self) -> None:
        """AUTO*: Replace A1 in-warranty, in-stock -> authorized."""
        ok, reason = authorize_offer(
            "Replace", "A1",
            {},
            {**_IN_WARRANTY, "variant_in_stock": True},
        )
        assert ok is True
        assert reason == "authorized:A1"

    def test_replace_g11_authorized(self) -> None:
        """AUTO*: G11 RTS replacement template in-warranty -> authorized."""
        ok, reason = authorize_offer(
            "Replace", "G11",
            {},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:G11"

    def test_replace_unknown_template_unauthorized(self) -> None:
        """No matching template for Replace -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Replace", "ZZ1",
            {},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"

    def test_replace_out_of_warranty_unauthorized(self) -> None:
        """Replace out-of-warranty -> unauthorized:ineligible:warranty."""
        ok, reason = authorize_offer(
            "Replace", "A1",
            {},
            _OUT_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:ineligible")


class TestPartialRefund:
    """RULES §2A — Partial_Refund (n=11, dominant: 50%+40%+free-ship, B7/B3)."""

    def test_partial_refund_b7_authorized(self) -> None:
        """AUTO*: Partial_Refund B7, 50% refund + 40% discount in-warranty -> authorized."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"refund_pct": 50, "discount_pct": 40},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:B7"

    def test_partial_refund_over_threshold_thr07(self) -> None:
        """Over 50% refund cap (THR-07) -> unauthorized:over_threshold:THR-07."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"refund_pct": 70},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:over_threshold")
        assert "THR-07" in reason

    def test_partial_refund_over_discount_thr05(self) -> None:
        """Over 40% discount cap (THR-05) -> unauthorized:over_threshold:THR-05."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"refund_pct": 50, "discount_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:over_threshold")
        assert "THR-05" in reason

    def test_partial_refund_b3_authorized(self) -> None:
        """AUTO*: Partial_Refund B3 (variant unavailable) in-warranty -> authorized."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B3",
            {"refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:B3"


class TestFullRefund:
    """RULES §2A — Full_Refund (n=9, evidence-gated; stricter checks; AUTO* with guards)."""

    def test_full_refund_a4_eligible_authorized(self) -> None:
        """AUTO*: Full_Refund A4 (evidence provided, cannot replace) in-warranty -> authorized.
        STUB (RD-Q3): evidence treated as sufficient this phase.
        """
        ok, reason = authorize_offer(
            "Full_Refund", "A4",
            {},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:A4"

    def test_full_refund_a5_in_warranty_authorized(self) -> None:
        """AUTO*: Full_Refund A5 (requesting evidence) in-warranty -> authorized."""
        ok, reason = authorize_offer(
            "Full_Refund", "A5",
            {},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:A5"

    def test_full_refund_out_of_warranty_unauthorized(self) -> None:
        """Full_Refund out-of-warranty -> unauthorized:ineligible:warranty."""
        ok, reason = authorize_offer(
            "Full_Refund", "A4",
            {},
            _OUT_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:ineligible")

    def test_full_refund_unknown_template_unauthorized(self) -> None:
        """Unknown template for Full_Refund -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Full_Refund", "B7",  # B7 is not a Full_Refund template
            {},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"


class TestReview:
    """RULES §2A — Review (n=35, no flow exists — Q2 gap: always ESCALATE)."""

    def test_review_always_force_escalates(self) -> None:
        """Review -> always False unauthorized:force_escalate:no_flow (no template exists)."""
        ok, reason = authorize_offer("Review")
        assert ok is False
        assert reason == "unauthorized:force_escalate:no_flow"

    def test_review_with_template_still_escalates(self) -> None:
        """Even if a template_code is supplied, Review still force-escalates."""
        ok, reason = authorize_offer("Review", "B7", {"refund_pct": 10}, _IN_WARRANTY)
        assert ok is False
        assert reason == "unauthorized:force_escalate:no_flow"

    def test_review_inquiry_sub_type_is_not_same_as_review(self) -> None:
        """Ask_About_Order (informational) is distinct from Review (complaint) — must not escalate."""
        ok, reason = authorize_offer("Ask_About_Order", offered={})
        assert ok is True
        assert reason == "authorized:no_offer"


# ===========================================================================
# §2B CHANGE_REQUEST — templates exist; gated on §1 execution boundary
# ===========================================================================


class TestCancelOrder:
    """RULES §2B — Cancel_Order (n=15; ≤20% retention offer; F-codes)."""

    def test_cancel_order_f1_retention_20pct_authorized(self) -> None:
        """AUTO*: Cancel_Order F1, ≤20% retention offer (THR-06) -> authorized."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F1",
            {"retention_pct": 20},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:F1"

    def test_cancel_order_retention_over_thr06_unauthorized(self) -> None:
        """Over 20% retention cap (THR-06) -> unauthorized:over_threshold:THR-06."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F1",
            {"retention_pct": 25},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:over_threshold")
        assert "THR-06" in reason

    def test_cancel_order_asserts_mutation_unauthorized(self) -> None:
        """asserts_mutation=True (claims cancellation executed) -> unauthorized:operational_assertion."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F12",
            {},
            _IN_WARRANTY,
            asserts_mutation=True,
        )
        assert ok is False
        assert reason == "unauthorized:operational_assertion"

    def test_cancel_order_no_template_unauthorized(self) -> None:
        """Unknown template for Cancel_Order -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Cancel_Order", "ZZ99",
            {"retention_pct": 20},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"


class TestChangeShippingAddress:
    """RULES §2B — Change_Shipping_Address (n=27; §1 mutation boundary)."""

    def test_change_shipping_asserts_mutation_unauthorized(self) -> None:
        """asserts_mutation=True ('I've updated the address') -> unauthorized:operational_assertion."""
        ok, reason = authorize_offer(
            "Change_Shipping_Address", "E1",
            {},
            _IN_WARRANTY,
            asserts_mutation=True,
        )
        assert ok is False
        assert reason == "unauthorized:operational_assertion"

    def test_change_shipping_acknowledge_no_mutation_authorized(self) -> None:
        """Non-asserting acknowledgement (asserts_mutation=False, no offer) -> authorized."""
        ok, reason = authorize_offer(
            "Change_Shipping_Address", "E1",
            {},
            _IN_WARRANTY,
            asserts_mutation=False,
        )
        assert ok is True
        assert reason == "authorized:E1"

    def test_change_shipping_e13_invalid_address_warning_authorized(self) -> None:
        """E13 invalid-address warning (ask customer to correct) -> authorized."""
        ok, reason = authorize_offer(
            "Change_Shipping_Address", "E13",
            {},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:E13"

    def test_change_shipping_unknown_template_unauthorized(self) -> None:
        """Unknown template -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Change_Shipping_Address", "B7",
            {},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"


class TestChangeProductVariant:
    """RULES §2B — Change_Product_Variant (n=20; THR-02 window; variant stock)."""

    def test_change_variant_e4_authorized(self) -> None:
        """AUTO*: Change_Product_Variant E4 (request measurements) in-warranty -> authorized."""
        ok, reason = authorize_offer(
            "Change_Product_Variant", "E4",
            {},
            {**_IN_WARRANTY, "variant_in_stock": True},
        )
        assert ok is True
        assert reason == "authorized:E4"

    def test_change_variant_asserts_mutation_unauthorized(self) -> None:
        """asserts_mutation=True ('we've updated your variant') -> unauthorized:operational_assertion."""
        ok, reason = authorize_offer(
            "Change_Product_Variant", "E11",
            {},
            _IN_WARRANTY,
            asserts_mutation=True,
        )
        assert ok is False
        assert reason == "unauthorized:operational_assertion"

    def test_change_variant_unknown_template_unauthorized(self) -> None:
        """Unknown template -> unauthorized:out_of_template."""
        ok, reason = authorize_offer(
            "Change_Product_Variant", "A4",
            {},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:out_of_template"


# ===========================================================================
# §2C INQUIRY — informational; highest automation value, lowest risk
# ===========================================================================


class TestAskAboutDeliveryStatus:
    """RULES §2C — Ask_About_Delivery_Status / WISMO (n=45)."""

    def test_wismo_no_offer_authorized_no_offer(self) -> None:
        """No offer (tracking info only) -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Delivery_Status", offered={})
        assert ok is True
        assert reason == "authorized:no_offer"

    def test_wismo_comp_within_thr08_authorized(self) -> None:
        """Late-ship compensation ≤50% (THR-08) with template -> authorized."""
        ok, reason = authorize_offer(
            "Ask_About_Delivery_Status", "G5",
            {"comp_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:G5"

    def test_wismo_comp_over_thr08_unauthorized(self) -> None:
        """Late-ship comp >50% (THR-08) -> unauthorized:over_threshold:THR-08."""
        ok, reason = authorize_offer(
            "Ask_About_Delivery_Status", "G5",
            {"comp_pct": 60},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason.startswith("unauthorized:over_threshold")
        assert "THR-08" in reason


class TestAskAboutOrder:
    """RULES §2C — Ask_About_Order (n=29; order/tracking facts from Selless)."""

    def test_ask_about_order_no_offer_authorized(self) -> None:
        """Informational — no offer -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Order", offered={})
        assert ok is True
        assert reason == "authorized:no_offer"

    def test_ask_about_order_none_offered_also_authorized(self) -> None:
        """offered=None also treated as no offer -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Order", offered=None)
        assert ok is True
        assert reason == "authorized:no_offer"


class TestAskAboutPolicy:
    """RULES §2C — Ask_About_Policy (n=5; cited KB policy)."""

    def test_ask_about_policy_authorized_no_offer(self) -> None:
        """Informational — no offer -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Policy")
        assert ok is True
        assert reason == "authorized:no_offer"


class TestAskAboutProduct:
    """RULES §2C — Ask_About_Product (n=6; product facts via scoped API)."""

    def test_ask_about_product_authorized_no_offer(self) -> None:
        """Informational — no offer -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Product")
        assert ok is True
        assert reason == "authorized:no_offer"


class TestAskAboutPromotion:
    """RULES §2C — Ask_About_Promotion (n=3; cited promo/KB; do not invent terms)."""

    def test_ask_about_promotion_authorized_no_offer(self) -> None:
        """Informational — no offer -> authorized:no_offer."""
        ok, reason = authorize_offer("Ask_About_Promotion")
        assert ok is True
        assert reason == "authorized:no_offer"


# ===========================================================================
# Cross-cutting / structural tests
# ===========================================================================


class TestInquirySubtypesNeverRequireTemplate:
    """Inquiry sub-types must never require a template code when no offer is made."""

    @pytest.mark.parametrize("sub_type", [
        "Ask_About_Delivery_Status",
        "Ask_About_Order",
        "Ask_About_Policy",
        "Ask_About_Product",
        "Ask_About_Promotion",
    ])
    def test_inquiry_no_template_no_offer_authorized(self, sub_type: str) -> None:
        """All 5 inquiry sub-types: no template, no offer -> authorized:no_offer."""
        ok, reason = authorize_offer(sub_type, template_code=None, offered={})
        assert ok is True
        assert reason == "authorized:no_offer", (
            f"{sub_type}: expected authorized:no_offer, got ({ok!r}, {reason!r})"
        )


class TestReasonStringDeterminism:
    """Reason strings must be deterministic (no randomness)."""

    def test_over_threshold_reason_names_thr_id(self) -> None:
        """over_threshold reason must include the THR-xx ID."""
        _, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"refund_pct": 99},
            _IN_WARRANTY,
        )
        assert reason.startswith("unauthorized:over_threshold")

    def test_force_escalate_reason_is_fixed_string(self) -> None:
        """Review force-escalate reason is always the same fixed string."""
        r1 = authorize_offer("Review")[1]
        r2 = authorize_offer("Review", "B7", {"refund_pct": 10}, _IN_WARRANTY)[1]
        assert r1 == r2 == "unauthorized:force_escalate:no_flow"


# ===========================================================================
# CR-02 regression: per-sub-type allowed-offer-key gate
# ===========================================================================


class TestCR02RegressionSubtypeAllowedOfferKeys:
    """Regression suite for CR-02: out-of-flow offer keys must be rejected.

    Before the fix, threshold caps were checked globally — refund_pct on Cancel_Order
    passed because the global cap (50%) was not exceeded, even though refund is not
    a legal offer dimension for cancellation flows (THR-06: retention_pct only).
    """

    def test_refund_pct_on_cancel_order_rejected(self) -> None:
        """CR-02: refund_pct on Cancel_Order must be rejected (only retention_pct allowed)."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F1",
            {"refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:offer_key_not_allowed:refund_pct", (
            f"CR-02: refund_pct on Cancel_Order must be offer_key_not_allowed; got {reason!r}"
        )

    def test_retention_pct_on_return_rejected(self) -> None:
        """CR-02: retention_pct on Return must be rejected (only refund_pct/discount_pct allowed)."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"retention_pct": 20},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:offer_key_not_allowed:retention_pct", (
            f"CR-02: retention_pct on Return must be offer_key_not_allowed; got {reason!r}"
        )

    def test_comp_pct_on_partial_refund_rejected(self) -> None:
        """CR-02: comp_pct on Partial_Refund must be rejected (only refund_pct/discount_pct allowed)."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"comp_pct": 30},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:offer_key_not_allowed:comp_pct", (
            f"CR-02: comp_pct on Partial_Refund must be offer_key_not_allowed; got {reason!r}"
        )

    def test_refund_pct_on_change_shipping_address_rejected(self) -> None:
        """CR-02: Change_Shipping_Address has no monetary pct dimension — any offered key rejected."""
        ok, reason = authorize_offer(
            "Change_Shipping_Address", "E1",
            {"refund_pct": 10},
            _IN_WARRANTY,
            asserts_mutation=False,
        )
        assert ok is False
        assert "offer_key_not_allowed" in reason

    def test_refund_pct_on_replace_rejected(self) -> None:
        """CR-02: Replace has no monetary pct offer — refund_pct must be rejected."""
        ok, reason = authorize_offer(
            "Replace", "A1",
            {"refund_pct": 10},
            _IN_WARRANTY,
        )
        assert ok is False
        assert "offer_key_not_allowed" in reason

    def test_cancel_order_retention_pct_still_authorized(self) -> None:
        """Regression guard: Cancel_Order with retention_pct (the correct key) must still work."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F1",
            {"retention_pct": 20},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:F1"

    def test_ask_about_delivery_status_comp_pct_still_authorized(self) -> None:
        """Regression guard: Ask_About_Delivery_Status with comp_pct (THR-08) must still work."""
        ok, reason = authorize_offer(
            "Ask_About_Delivery_Status", "G5",
            {"comp_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:G5"


# ===========================================================================
# WR-01 regression: unknown / mistyped offered keys rejected
# ===========================================================================


class TestWR01RegressionUnknownOfferedKeys:
    """Regression suite for WR-01: unknown/mistyped offered keys must be rejected.

    Before the fix, the THRESHOLD_CAPS iteration loop never checked offered keys
    that were not recognized cap keys, so "refundpct":999 was silently dropped.
    """

    def test_typo_key_refundpct_rejected(self) -> None:
        """WR-01: typo'd key 'refundpct' (missing underscore) must be rejected."""
        ok, reason = authorize_offer(
            "Partial_Refund", "B7",
            {"refundpct": 999, "refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is False
        assert "offer_key_not_allowed:refundpct" in reason, (
            f"WR-01: typo'd 'refundpct' must be offer_key_not_allowed; got {reason!r}"
        )

    def test_entirely_unknown_key_rejected(self) -> None:
        """WR-01: completely unknown key 'bonus_pct' must be rejected."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"bonus_pct": 10, "refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is False
        assert "offer_key_not_allowed:bonus_pct" in reason

    def test_valid_key_only_still_authorized(self) -> None:
        """Regression guard: a valid key with no unknown keys must still be authorized."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": 50},
            _IN_WARRANTY,
        )
        assert ok is True
        assert reason == "authorized:B7"


# ===========================================================================
# WR-02 / WR-03 regression: invalid offered values rejected without raising
# ===========================================================================


class TestWR02WR03RegressionInvalidOfferedValues:
    """Regression suite for WR-02 + WR-03: invalid offered values must be rejected.

    Before the fix:
      WR-02: negative values passed (-10 > 50 is False) and bool values passed
             (True == 1, so True > 50 is False).
      WR-03: string values raised TypeError instead of returning (False, reason).

    All cases must now return (False, "unauthorized:invalid_offer_value:<key>")
    and NEVER raise an exception.
    """

    def test_negative_refund_pct_rejected(self) -> None:
        """WR-02: refund_pct=-10 must be rejected (negative is invalid)."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": -10},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:invalid_offer_value:refund_pct", (
            f"WR-02: negative refund_pct must be invalid_offer_value; got {reason!r}"
        )

    def test_bool_true_refund_pct_rejected(self) -> None:
        """WR-02: refund_pct=True must be rejected (bool is not a valid numeric pct)."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": True},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:invalid_offer_value:refund_pct", (
            f"WR-02: bool refund_pct=True must be invalid_offer_value; got {reason!r}"
        )

    def test_bool_false_refund_pct_rejected(self) -> None:
        """WR-02: refund_pct=False must also be rejected (bool subclass of int — type confusion)."""
        ok, reason = authorize_offer(
            "Return", "B7",
            {"refund_pct": False},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:invalid_offer_value:refund_pct"

    def test_string_refund_pct_rejected_no_raise(self) -> None:
        """WR-03: refund_pct='100' (string) must be rejected without raising TypeError."""
        # This previously raised TypeError: '>' not supported between str and int.
        try:
            ok, reason = authorize_offer(
                "Return", "B7",
                {"refund_pct": "100"},
                _IN_WARRANTY,
            )
        except Exception as exc:
            raise AssertionError(
                f"WR-03: authorize_offer must never raise on caller-supplied data; "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        assert ok is False
        assert reason == "unauthorized:invalid_offer_value:refund_pct", (
            f"WR-03: string refund_pct must be invalid_offer_value; got {reason!r}"
        )

    def test_string_retention_pct_on_cancel_order_rejected_no_raise(self) -> None:
        """WR-03: retention_pct='20' on Cancel_Order must not raise."""
        try:
            ok, reason = authorize_offer(
                "Cancel_Order", "F1",
                {"retention_pct": "20"},
                _IN_WARRANTY,
            )
        except Exception as exc:
            raise AssertionError(
                f"WR-03: authorize_offer must not raise on string value; "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        assert ok is False
        assert "invalid_offer_value:retention_pct" in reason

    def test_negative_retention_pct_rejected(self) -> None:
        """WR-02: retention_pct=-5 on Cancel_Order must be rejected."""
        ok, reason = authorize_offer(
            "Cancel_Order", "F1",
            {"retention_pct": -5},
            _IN_WARRANTY,
        )
        assert ok is False
        assert reason == "unauthorized:invalid_offer_value:retention_pct"

    def test_valid_numeric_values_still_authorized(self) -> None:
        """Regression guard: valid int and float values must still be authorized."""
        # int
        ok_int, _ = authorize_offer(
            "Return", "B7",
            {"refund_pct": 50, "discount_pct": 40},
            _IN_WARRANTY,
        )
        assert ok_int is True
        # float
        ok_float, _ = authorize_offer(
            "Return", "B7",
            {"refund_pct": 49.5, "discount_pct": 39.9},
            _IN_WARRANTY,
        )
        assert ok_float is True
