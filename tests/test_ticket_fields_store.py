"""
Tests for src/file_store/ticket_fields_store.py

Covers the behaviors from 08-01-PLAN.md Task 1:
1. level_in_choices() returns the 3 macro keys
2. customer_requests_for("Complaint") returns 5 children verbatim; unknown -> []
3. field_choices("Level_in") returns 3 macro keys; field_choices("Customer_Request") returns
   flattened union of all nested children (deduped)
4. field_choices("Rootcause") returns [] for empty-enum snapshot (fail-soft, no raise)
5. field_choices("Bogus_Field") returns [] (unknown field, fail-soft)
6. Missing snapshot file -> all functions return empty/typed-falsey, never raise

Tests are fully offline: loader is monkeypatched to a FAKE snapshot fixture for
populated-enum cases. The committed snapshot is only used in a smoke test that
verifies the nested Level_in keys exist.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Fake snapshot fixture used by most tests (avoids coupling to live file)
# ---------------------------------------------------------------------------

FAKE_SNAPSHOT: dict = {
    "_meta": {"source": "test", "captured": "2026-01-01", "version": 1},
    "nested": {
        "Level_in": {
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
    },
    "dropdowns": {
        "Rootcause": [],
        "Flow": [],
        "Section_Flow": [],
        "Product_line": ["Bra", "Pants"],
        "Level_out": [],
        "Package_status": [],
        "Category": [],
    },
}

FAKE_SNAPSHOT_WITH_ROOTCAUSE: dict = {
    "_meta": {"source": "test", "captured": "2026-01-01", "version": 1},
    "nested": {
        "Level_in": {
            "Inquiry": ["Ask_About_Product"],
        }
    },
    "dropdowns": {
        "Rootcause": ["Wrong_Item", "Damaged", "Not_Received"],
        "Flow": ["Standard", "Express"],
        "Section_Flow": [],
    },
}


@pytest.fixture(autouse=True)
def reset_store_cache():
    """Reset module-level cache before each test to isolate state."""
    import src.file_store.ticket_fields_store as store
    store._CACHE = None
    yield
    store._CACHE = None


@pytest.fixture
def fake_snapshot(tmp_path):
    """Write FAKE_SNAPSHOT to a temp file and return its Path."""
    p = tmp_path / "freshdesk-ticket-fields.json"
    p.write_text(json.dumps(FAKE_SNAPSHOT), encoding="utf-8")
    return p


@pytest.fixture
def fake_snapshot_with_rootcause(tmp_path):
    """Write FAKE_SNAPSHOT_WITH_ROOTCAUSE to a temp file and return its Path."""
    p = tmp_path / "freshdesk-ticket-fields.json"
    p.write_text(json.dumps(FAKE_SNAPSHOT_WITH_ROOTCAUSE), encoding="utf-8")
    return p


@pytest.fixture
def missing_snapshot(tmp_path):
    """Return a path that does not exist."""
    return tmp_path / "does-not-exist.json"


# ---------------------------------------------------------------------------
# Helpers to call loader with an injected path
# ---------------------------------------------------------------------------

def _level_in_choices(snapshot_path: Path) -> list[str]:
    import src.file_store.ticket_fields_store as store
    store._CACHE = None
    return store.level_in_choices(snapshot_path=snapshot_path)


def _customer_requests_for(level_in: str, snapshot_path: Path) -> list[str]:
    import src.file_store.ticket_fields_store as store
    store._CACHE = None
    return store.customer_requests_for(level_in, snapshot_path=snapshot_path)


def _field_choices(field: str, snapshot_path: Path) -> list[str]:
    import src.file_store.ticket_fields_store as store
    store._CACHE = None
    return store.field_choices(field, snapshot_path=snapshot_path)


# ---------------------------------------------------------------------------
# Tests: level_in_choices()
# ---------------------------------------------------------------------------

class TestLevelInChoices:
    def test_returns_three_macro_keys(self, fake_snapshot):
        result = _level_in_choices(fake_snapshot)
        assert result == ["Inquiry", "Change_Request", "Complaint"]

    def test_returns_list_type(self, fake_snapshot):
        result = _level_in_choices(fake_snapshot)
        assert isinstance(result, list)

    def test_missing_snapshot_returns_empty(self, missing_snapshot):
        result = _level_in_choices(missing_snapshot)
        assert result == []

    def test_missing_snapshot_never_raises(self, missing_snapshot):
        # Must not raise — fail-soft
        result = _level_in_choices(missing_snapshot)
        assert isinstance(result, list)

    def test_smoke_real_snapshot_has_expected_keys(self):
        """Smoke: the committed snapshot must contain the known Level_in keys."""
        import src.file_store.ticket_fields_store as store
        result = store.level_in_choices()
        assert "Inquiry" in result
        assert "Change_Request" in result
        assert "Complaint" in result


# ---------------------------------------------------------------------------
# Tests: customer_requests_for()
# ---------------------------------------------------------------------------

class TestCustomerRequestsFor:
    def test_complaint_returns_five_children(self, fake_snapshot):
        result = _customer_requests_for("Complaint", fake_snapshot)
        assert len(result) == 5

    def test_complaint_includes_return(self, fake_snapshot):
        result = _customer_requests_for("Complaint", fake_snapshot)
        assert "Return" in result

    def test_complaint_includes_review(self, fake_snapshot):
        result = _customer_requests_for("Complaint", fake_snapshot)
        assert "Review" in result

    def test_complaint_values_are_verbatim(self, fake_snapshot):
        result = _customer_requests_for("Complaint", fake_snapshot)
        expected = ["Review", "Return", "Replace", "Full_Refund", "Partial_Refund"]
        assert result == expected

    def test_unknown_level_in_returns_empty(self, fake_snapshot):
        result = _customer_requests_for("__nope__", fake_snapshot)
        assert result == []

    def test_unknown_level_in_never_raises(self, fake_snapshot):
        result = _customer_requests_for("TOTALLY_UNKNOWN", fake_snapshot)
        assert isinstance(result, list)

    def test_inquiry_returns_five_children(self, fake_snapshot):
        result = _customer_requests_for("Inquiry", fake_snapshot)
        assert len(result) == 5
        assert "Ask_About_Product" in result
        assert "Ask_About_Delivery_Status" in result

    def test_missing_snapshot_returns_empty(self, missing_snapshot):
        result = _customer_requests_for("Complaint", missing_snapshot)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: field_choices()
# ---------------------------------------------------------------------------

class TestFieldChoices:
    def test_level_in_returns_three_macro_keys(self, fake_snapshot):
        result = _field_choices("Level_in", fake_snapshot)
        assert result == ["Inquiry", "Change_Request", "Complaint"]

    def test_customer_request_returns_flattened_union(self, fake_snapshot):
        result = _field_choices("Customer_Request", fake_snapshot)
        # All 3 groups combined: 5 + 5 + 5 = 15 unique values
        assert len(result) == 15

    def test_customer_request_includes_return(self, fake_snapshot):
        result = _field_choices("Customer_Request", fake_snapshot)
        assert "Return" in result

    def test_customer_request_includes_cancel_order(self, fake_snapshot):
        result = _field_choices("Customer_Request", fake_snapshot)
        assert "Cancel_Order" in result

    def test_customer_request_includes_ask_about_product(self, fake_snapshot):
        result = _field_choices("Customer_Request", fake_snapshot)
        assert "Ask_About_Product" in result

    def test_customer_request_no_duplicates(self, fake_snapshot):
        result = _field_choices("Customer_Request", fake_snapshot)
        assert len(result) == len(set(result)), "Customer_Request choices must be deduplicated"

    def test_rootcause_returns_empty_for_empty_enum(self, fake_snapshot):
        """Current snapshot: Rootcause is [] — loader must return [] without raising."""
        result = _field_choices("Rootcause", fake_snapshot)
        assert result == []

    def test_rootcause_returns_values_when_populated(self, fake_snapshot_with_rootcause):
        """When the snapshot has values, they should be returned verbatim."""
        result = _field_choices("Rootcause", fake_snapshot_with_rootcause)
        assert result == ["Wrong_Item", "Damaged", "Not_Received"]

    def test_flow_returns_empty_for_empty_enum(self, fake_snapshot):
        result = _field_choices("Flow", fake_snapshot)
        assert result == []

    def test_section_flow_returns_empty_for_empty_enum(self, fake_snapshot):
        result = _field_choices("Section_Flow", fake_snapshot)
        assert result == []

    def test_bogus_field_returns_empty(self, fake_snapshot):
        result = _field_choices("Bogus_Field", fake_snapshot)
        assert result == []

    def test_bogus_field_never_raises(self, fake_snapshot):
        result = _field_choices("TOTALLY_BOGUS_123", fake_snapshot)
        assert isinstance(result, list)

    def test_missing_snapshot_returns_empty_for_level_in(self, missing_snapshot):
        result = _field_choices("Level_in", missing_snapshot)
        assert result == []

    def test_missing_snapshot_returns_empty_for_customer_request(self, missing_snapshot):
        result = _field_choices("Customer_Request", missing_snapshot)
        assert result == []

    def test_missing_snapshot_returns_empty_for_rootcause(self, missing_snapshot):
        result = _field_choices("Rootcause", missing_snapshot)
        assert result == []

    def test_missing_snapshot_never_raises(self, missing_snapshot):
        for field in ["Level_in", "Customer_Request", "Rootcause", "Flow", "Bogus"]:
            result = _field_choices(field, missing_snapshot)
            assert isinstance(result, list)

    def test_product_line_returned_from_dropdowns(self, fake_snapshot):
        """Product_line has values in fake snapshot — should be returned."""
        result = _field_choices("Product_line", fake_snapshot)
        assert result == ["Bra", "Pants"]
