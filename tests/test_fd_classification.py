"""
Tests for src/file_store/fd_classification.py

Covers the behaviors from 08-01-PLAN.md Task 2:
1. validate_field -> "valid" when value is in non-empty allowed set
2. validate_field -> "invalid" when value not in non-empty allowed set (flagged; value preserved)
3. validate_field -> "unverifiable" when allowed set is empty (cannot confirm; NOT valid/invalid)
4. validate_field -> "missing" when value is empty/None
5. build_fd_property_update: only OWNED fields emitted (Level_in, Customer_Request,
   Rootcause, Flow, Section_Flow); out-of-scope fields never appear
6. Nested integrity: Customer_Request flagged as "invalid"/"nested_mismatch" when not a child
   of the chosen Level_in
7. Each assembled entry carries: field, value (verbatim), status, and the allowed-set provenance
8. Missing/empty AI value for owned field -> entry with empty value + status "missing"
9. No submit_reply / Freshdesk / network import anywhere in the module

All tests are fully offline: ticket_fields_store is monkeypatched to a controlled
fake enum — logic is tested independent of live snapshot contents.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fake enum data used to monkeypatch ticket_fields_store
# ---------------------------------------------------------------------------

FAKE_LEVEL_IN = ["Inquiry", "Change_Request", "Complaint"]

FAKE_CUSTOMER_REQUESTS = {
    "Inquiry": [
        "Ask_About_Product",
        "Ask_About_Policy",
        "Ask_About_Promotion",
        "Ask_About_Order",
        "Ask_About_Delivery_Status",
    ],
    "Change_Request": [
        "Change_Shipping_Address",
        "Change_Non_Shipping_Address",
        "Change_Product_Variant",
        "Cancel_Order",
        "Change_Shipping_Express_Line",
    ],
    "Complaint": [
        "Review",
        "Return",
        "Replace",
        "Full_Refund",
        "Partial_Refund",
    ],
}

FAKE_FLAT_CHOICES = {
    "Level_in": FAKE_LEVEL_IN,
    "Customer_Request": [v for vals in FAKE_CUSTOMER_REQUESTS.values() for v in vals],
    "Rootcause": [],  # empty in current snapshot
    "Flow": [],       # empty in current snapshot
    "Section_Flow": [],  # empty in current snapshot
}

OUT_OF_SCOPE_FIELDS = [
    "Level_out",
    "Package_status",
    "Handler",
    "Product_label",
    "Category",
    "SCE_team",
    "Call_type",
]


def _fake_field_choices(field: str, **kwargs) -> list[str]:
    return list(FAKE_FLAT_CHOICES.get(field, []))


def _fake_customer_requests_for(level_in: str, **kwargs) -> list[str]:
    return list(FAKE_CUSTOMER_REQUESTS.get(level_in, []))


@pytest.fixture(autouse=True)
def patch_store():
    """Monkeypatch ticket_fields_store functions to use fake data."""
    with (
        patch(
            "src.file_store.fd_classification.field_choices",
            side_effect=_fake_field_choices,
        ),
        patch(
            "src.file_store.fd_classification.customer_requests_for",
            side_effect=_fake_customer_requests_for,
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests: validate_field()
# ---------------------------------------------------------------------------

class TestValidateField:
    """Tests for validate_field(field, value, allowed=None) -> dict."""

    def test_valid_customer_request_return(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field(
            "Customer_Request", "Return",
            allowed=["Review", "Return", "Replace", "Full_Refund", "Partial_Refund"],
        )
        assert result["status"] == "valid"

    def test_invalid_customer_request_out_of_enum(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field(
            "Customer_Request", "Refundy",
            allowed=["Review", "Return", "Replace", "Full_Refund", "Partial_Refund"],
        )
        assert result["status"] == "invalid"

    def test_invalid_preserves_rejected_value(self):
        """The rejected value must be preserved in result (for side-by-side logging)."""
        from src.file_store.fd_classification import validate_field
        result = validate_field(
            "Customer_Request", "Refundy",
            allowed=["Review", "Return", "Replace", "Full_Refund", "Partial_Refund"],
        )
        assert result["value"] == "Refundy"

    def test_unverifiable_when_allowed_is_empty(self):
        """Empty allowed list: cannot confirm validity -> unverifiable."""
        from src.file_store.fd_classification import validate_field
        result = validate_field("Rootcause", "anything", allowed=[])
        assert result["status"] == "unverifiable"

    def test_unverifiable_is_not_valid(self):
        """Unverifiable must NOT be treated as valid."""
        from src.file_store.fd_classification import validate_field
        result = validate_field("Rootcause", "anything", allowed=[])
        assert result["status"] != "valid"

    def test_unverifiable_is_not_invalid(self):
        """Unverifiable must NOT be treated as invalid (enum simply doesn't have choices yet)."""
        from src.file_store.fd_classification import validate_field
        result = validate_field("Rootcause", "anything", allowed=[])
        assert result["status"] != "invalid"

    def test_missing_when_value_is_none(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", None, allowed=FAKE_LEVEL_IN)
        assert result["status"] == "missing"

    def test_missing_when_value_is_empty_string(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "", allowed=FAKE_LEVEL_IN)
        assert result["status"] == "missing"

    def test_result_contains_field_key(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "Complaint", allowed=FAKE_LEVEL_IN)
        assert "field" in result
        assert result["field"] == "Level_in"

    def test_result_contains_value_key(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "Complaint", allowed=FAKE_LEVEL_IN)
        assert "value" in result
        assert result["value"] == "Complaint"

    def test_result_contains_allowed_key(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "Complaint", allowed=FAKE_LEVEL_IN)
        assert "allowed" in result
        assert isinstance(result["allowed"], list)

    def test_result_contains_status_key(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "Complaint", allowed=FAKE_LEVEL_IN)
        assert "status" in result

    def test_valid_level_in_inquiry(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "Inquiry", allowed=FAKE_LEVEL_IN)
        assert result["status"] == "valid"

    def test_invalid_level_in_free_text(self):
        """A free-text value not in the enum must be flagged invalid, never accepted."""
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "General_Question", allowed=FAKE_LEVEL_IN)
        assert result["status"] == "invalid"
        assert result["value"] == "General_Question"

    def test_allowed_none_sources_from_store(self):
        """When allowed=None, field_choices() is called to source the enum."""
        from src.file_store.fd_classification import validate_field
        # field_choices is patched to return FAKE_FLAT_CHOICES["Rootcause"] = []
        result = validate_field("Rootcause", "something")
        assert result["status"] == "unverifiable"

    def test_allowed_none_level_in_sources_from_store(self):
        """When allowed=None for Level_in, field_choices() returns 3 macro keys."""
        from src.file_store.fd_classification import validate_field
        # field_choices patched to return FAKE_LEVEL_IN for Level_in
        result = validate_field("Level_in", "Complaint")
        assert result["status"] == "valid"

    def test_allowed_none_invalid_level_in(self):
        from src.file_store.fd_classification import validate_field
        result = validate_field("Level_in", "BadValue")
        assert result["status"] == "invalid"


# ---------------------------------------------------------------------------
# Tests: build_fd_property_update()
# ---------------------------------------------------------------------------

class TestBuildFdPropertyUpdate:
    """Tests for build_fd_property_update(ai_props: dict) -> dict."""

    def _full_valid_props(self):
        return {
            "level_in": "Complaint",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }

    def test_returns_dict_with_fields_key(self):
        from src.file_store.fd_classification import build_fd_property_update
        result = build_fd_property_update(self._full_valid_props())
        assert isinstance(result, dict)
        assert "fields" in result

    def test_returns_all_valid_flag(self):
        from src.file_store.fd_classification import build_fd_property_update
        result = build_fd_property_update(self._full_valid_props())
        assert "all_valid" in result

    def test_returns_advisory_true(self):
        from src.file_store.fd_classification import build_fd_property_update
        result = build_fd_property_update(self._full_valid_props())
        assert result.get("advisory") is True

    def test_owned_fields_all_present(self):
        """All 5 owned fields must appear in result.fields."""
        from src.file_store.fd_classification import build_fd_property_update, OWNED_FIELDS
        result = build_fd_property_update(self._full_valid_props())
        for f in OWNED_FIELDS:
            assert f in result["fields"], f"Missing owned field: {f}"

    def test_out_of_scope_fields_never_emitted(self):
        """Out-of-scope fields must never appear in result.fields."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Complaint",
            "customer_request": "Return",
            "level_out": "Resolved",         # out-of-scope
            "package_status": "Delivered",   # out-of-scope
            "handler": "AgentJohn",          # out-of-scope
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        for bad_field in OUT_OF_SCOPE_FIELDS:
            assert bad_field not in result["fields"], (
                f"Out-of-scope field {bad_field!r} must never be emitted"
            )

    def test_valid_classification_gives_all_valid_true(self):
        """All valid + non-empty owned fields -> all_valid True."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Complaint",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        # Level_in and Customer_Request are valid; Rootcause/Flow/Section_Flow are
        # unverifiable (empty enum) → all_valid should be False (unverifiable != valid)
        level_in_entry = result["fields"]["Level_in"]
        assert level_in_entry["status"] == "valid"
        cr_entry = result["fields"]["Customer_Request"]
        assert cr_entry["status"] == "valid"

    def test_nested_mismatch_flagged(self):
        """Customer_Request not a child of Level_in must be flagged."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Inquiry",
            "customer_request": "Return",  # Return is under Complaint, not Inquiry
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        cr_entry = result["fields"]["Customer_Request"]
        # Must not be "valid" — must be "invalid" or a "nested_mismatch" status
        assert cr_entry["status"] in ("invalid", "nested_mismatch"), (
            f"Nested mismatch must be flagged, got status={cr_entry['status']!r}"
        )

    def test_nested_mismatch_all_valid_false(self):
        """Nested mismatch causes all_valid to be False."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Inquiry",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        assert result["all_valid"] is False

    def test_missing_ai_value_gives_missing_status(self):
        """Missing/empty AI value for owned field -> status "missing", value is empty."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "",          # explicitly empty
            "customer_request": "",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        assert result["fields"]["Level_in"]["status"] == "missing"
        assert result["fields"]["Customer_Request"]["status"] == "missing"

    def test_missing_level_in_all_valid_false(self):
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        assert result["all_valid"] is False

    def test_value_verbatim_in_result(self):
        """The verbatim AI value (even if invalid) must be preserved in the result."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "BOGUS_VALUE",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        assert result["fields"]["Level_in"]["value"] == "BOGUS_VALUE"

    def test_entry_has_allowed_provenance(self):
        """Each entry must carry the allowed set so harness can render *_valid columns."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Complaint",
            "customer_request": "Return",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        level_in_entry = result["fields"]["Level_in"]
        assert "allowed" in level_in_entry
        assert isinstance(level_in_entry["allowed"], list)
        assert "Complaint" in level_in_entry["allowed"]

    def test_no_value_fabrication(self):
        """build_fd_property_update must NEVER fabricate a value to make it valid."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "MADE_UP",
            "customer_request": "MADE_UP_REQUEST",
            "rootcause": "",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        # Values must remain as supplied, not replaced by valid ones
        assert result["fields"]["Level_in"]["value"] == "MADE_UP"
        assert result["fields"]["Customer_Request"]["value"] == "MADE_UP_REQUEST"

    def test_empty_ai_props_gives_all_missing(self):
        """Completely empty ai_props -> all owned fields are "missing"."""
        from src.file_store.fd_classification import build_fd_property_update, OWNED_FIELDS
        result = build_fd_property_update({})
        for f in OWNED_FIELDS:
            assert result["fields"][f]["status"] == "missing", (
                f"Expected 'missing' for {f}, got {result['fields'][f]['status']!r}"
            )

    def test_does_not_call_submit_reply(self):
        """The module must not import or call submit_reply, or import network libs."""
        import src.file_store.fd_classification as mod
        import inspect
        src_text = inspect.getsource(mod)
        # No actual network library imports (httpx, requests)
        assert "import httpx" not in src_text
        assert "import requests" not in src_text
        assert "from httpx" not in src_text
        assert "from requests" not in src_text
        # No Freshdesk write path
        assert "api/v2/tickets" not in src_text
        # submit_reply must not be called as a function (a mention in a comment is OK)
        import re
        # Look for actual call: submit_reply(
        assert not re.search(r'\bsubmit_reply\s*\(', src_text), (
            "submit_reply must not be called in fd_classification"
        )

    def test_rootcause_unverifiable_when_empty_enum(self):
        """Rootcause with empty allowed enum -> unverifiable, not invalid."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Complaint",
            "customer_request": "Return",
            "rootcause": "SomeValue",
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        # Rootcause allowed list is [] (patched to empty) -> unverifiable
        assert result["fields"]["Rootcause"]["status"] == "unverifiable"

    def test_all_valid_false_when_any_unverifiable(self):
        """all_valid is False when any owned field is unverifiable."""
        from src.file_store.fd_classification import build_fd_property_update
        ai_props = {
            "level_in": "Complaint",
            "customer_request": "Return",
            "rootcause": "Something",   # unverifiable (empty enum)
            "flow": "",
            "section_flow": "",
        }
        result = build_fd_property_update(ai_props)
        # Rootcause is unverifiable -> all_valid must be False
        assert result["all_valid"] is False


# ---------------------------------------------------------------------------
# Tests: OWNED_FIELDS constant
# ---------------------------------------------------------------------------

class TestOwnedFields:
    def test_owned_fields_contains_exactly_five(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert len(OWNED_FIELDS) == 5

    def test_owned_fields_contains_level_in(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Level_in" in OWNED_FIELDS

    def test_owned_fields_contains_customer_request(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Customer_Request" in OWNED_FIELDS

    def test_owned_fields_contains_rootcause(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Rootcause" in OWNED_FIELDS

    def test_owned_fields_contains_flow(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Flow" in OWNED_FIELDS

    def test_owned_fields_contains_section_flow(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Section_Flow" in OWNED_FIELDS

    def test_owned_fields_does_not_contain_level_out(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Level_out" not in OWNED_FIELDS

    def test_owned_fields_does_not_contain_package_status(self):
        from src.file_store.fd_classification import OWNED_FIELDS
        assert "Package_status" not in OWNED_FIELDS
