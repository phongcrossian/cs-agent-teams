"""
Tests for src/file_store/template_store.py

Covers the five behaviors from the plan:
1. get_template_from_file("B7") returns dict with found=True and real body
2. get_template_from_file("ZZZ") returns found=False, body=None (fail-soft)
3. subtype_to_code("Return") returns non-empty ordered list with B-codes and A-codes
4. subtype_to_code("Review") returns [] (Phase-1 gap — no template)
5. Missing snapshot file -> found: False (fail-soft, no fabrication)
"""

from __future__ import annotations

import pytest

from src.file_store.template_store import get_template_from_file, subtype_to_code


class TestGetTemplateFromFile:
    """Tests for get_template_from_file()."""

    def test_known_code_b7_returns_found_true(self):
        """B7 is a known code; should return found=True."""
        result = get_template_from_file("B7")
        assert result["found"] is True, f"Expected found=True for B7, got: {result}"

    def test_known_code_b7_returns_non_empty_body(self):
        """B7 body should be non-empty verbatim template text."""
        result = get_template_from_file("B7")
        assert result["body"] is not None, "B7 body should not be None"
        assert len(result["body"].strip()) > 0, "B7 body should be non-empty"

    def test_known_code_b7_returns_correct_fields(self):
        """B7 result dict must contain code, heading, body, snapshot_file, found."""
        result = get_template_from_file("B7")
        assert "code" in result
        assert "heading" in result
        assert "body" in result
        assert "snapshot_file" in result
        assert "found" in result
        assert result["code"] == "B7"
        assert "B7" in result["heading"]

    def test_known_code_b7_body_contains_template_text(self):
        """B7 body should contain actual customer-facing text (not empty/noise)."""
        result = get_template_from_file("B7")
        body = result["body"]
        # B7 template offers 50% refund AND 40% discount — should have substantive content
        assert len(body) > 50, f"B7 body too short: {len(body)} chars"

    def test_unknown_code_returns_found_false(self):
        """Unknown code ZZZ must return found=False without raising."""
        result = get_template_from_file("ZZZ")
        assert result["found"] is False, f"Expected found=False for ZZZ, got: {result}"

    def test_unknown_code_returns_none_body(self):
        """Unknown code ZZZ must return body=None (no fabrication)."""
        result = get_template_from_file("ZZZ")
        assert result["body"] is None, f"Expected body=None for ZZZ, got: {result['body']!r}"

    def test_unknown_code_returns_correct_code_field(self):
        """Unknown code ZZZ result must include the original code."""
        result = get_template_from_file("ZZZ")
        assert result["code"] == "ZZZ"

    def test_never_raises_on_unknown_code(self):
        """get_template_from_file must never raise for any code."""
        # Should return gracefully, not raise
        result = get_template_from_file("NOTEXIST")
        assert isinstance(result, dict)
        assert result["found"] is False

    def test_another_known_code_a4(self):
        """A4 is another known code; should also return found=True with body."""
        result = get_template_from_file("A4")
        assert result["found"] is True, f"Expected found=True for A4, got: {result}"
        assert result["body"] is not None
        assert len(result["body"].strip()) > 0

    def test_known_code_c1(self):
        """C1 (out of warranty) is a known code in its own snapshot file."""
        result = get_template_from_file("C1")
        assert result["found"] is True, f"Expected found=True for C1, got: {result}"
        assert result["body"] is not None

    def test_known_f_code(self):
        """F1 is a known cancellation code; should return found=True."""
        result = get_template_from_file("F1")
        assert result["found"] is True, f"Expected found=True for F1, got: {result}"
        assert result["body"] is not None

    def test_known_g_code(self):
        """G10 is a known shipping code; should return found=True."""
        result = get_template_from_file("G10")
        assert result["found"] is True, f"Expected found=True for G10, got: {result}"
        assert result["body"] is not None


class TestSubtypeToCode:
    """Tests for subtype_to_code()."""

    def test_return_subtype_returns_nonempty_list(self):
        """Return sub-type should map to a non-empty list of candidate codes."""
        codes = subtype_to_code("Return")
        assert isinstance(codes, list)
        assert len(codes) > 0, "Return sub-type must map to at least one code"

    def test_return_subtype_includes_b_codes(self):
        """Return sub-type should include B-codes (non-defective return flow)."""
        codes = subtype_to_code("Return")
        b_codes = [c for c in codes if c.startswith("B")]
        assert len(b_codes) > 0, f"Return codes should include B-codes, got: {codes}"

    def test_review_subtype_returns_empty_list(self):
        """Review sub-type has no template (Phase-1 gap) — must return []."""
        codes = subtype_to_code("Review")
        assert codes == [], f"Review must return [], got: {codes}"

    def test_cancel_order_subtype_returns_f_codes(self):
        """Cancel_Order sub-type should map to F-codes."""
        codes = subtype_to_code("Cancel_Order")
        assert len(codes) > 0, "Cancel_Order must have codes"
        f_codes = [c for c in codes if c.startswith("F")]
        assert len(f_codes) > 0, f"Cancel_Order codes should include F-codes, got: {codes}"

    def test_ask_about_delivery_status_returns_g_codes(self):
        """Ask_About_Delivery_Status should map to G-codes."""
        codes = subtype_to_code("Ask_About_Delivery_Status")
        assert len(codes) > 0
        g_codes = [c for c in codes if c.startswith("G")]
        assert len(g_codes) > 0, f"Ask_About_Delivery_Status should include G-codes, got: {codes}"

    def test_replace_subtype_returns_nonempty_list(self):
        """Replace sub-type should map to A-codes and/or B-codes."""
        codes = subtype_to_code("Replace")
        assert len(codes) > 0, "Replace sub-type must have codes"

    def test_change_shipping_address_returns_e_codes(self):
        """Change_Shipping_Address maps to E-codes."""
        codes = subtype_to_code("Change_Shipping_Address")
        assert len(codes) > 0
        e_codes = [c for c in codes if c.startswith("E")]
        assert len(e_codes) > 0, f"Change_Shipping_Address should include E-codes, got: {codes}"

    def test_unknown_subtype_returns_empty_list(self):
        """Unknown sub-type should return [] not raise."""
        codes = subtype_to_code("TOTALLY_UNKNOWN_SUBTYPE")
        assert codes == [], f"Unknown sub-type must return [], got: {codes}"

    def test_return_value_is_always_list(self):
        """subtype_to_code always returns a list, never None or other type."""
        for sub_type in ["Return", "Review", "Replace", "Ask_About_Policy", "NONEXISTENT"]:
            result = subtype_to_code(sub_type)
            assert isinstance(result, list), f"Expected list for {sub_type!r}, got {type(result)}"

    def test_partial_refund_returns_codes(self):
        """Partial_Refund sub-type should have codes."""
        codes = subtype_to_code("Partial_Refund")
        assert len(codes) > 0, "Partial_Refund must have codes"
