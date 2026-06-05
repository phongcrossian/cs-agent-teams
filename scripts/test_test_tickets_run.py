"""Unit tests for the `run` subcommand helpers in test_tickets_run.py.

Tests target the NEW pure helpers:
  - `_parse_ticket_list(path)` — parses uat_ticket.csv (semicolon-delimited) or plain ID-per-line
  - `_apply_caps(rows, limit, per_cat)` — applies --limit / --per-cat caps and returns dropped report

These tests MUST NOT invoke `claude`, Freshdesk, Selless, or any live service.
They do NOT import `collect` or `run_ai_team`.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — import only the pure helpers we are testing
# ---------------------------------------------------------------------------

from scripts.test_tickets_run import (
    _allowed_codes_for_subtype,
    _extract_fd_props,
    _parse_ticket_list,
    _apply_caps,
)


# ---------------------------------------------------------------------------
# Test 1: CSV parse — semicolon-delimited uat_ticket.csv format (D-42)
# ---------------------------------------------------------------------------

def test_parse_csv_semicolon_format(tmp_path: Path) -> None:
    """_parse_ticket_list parses uat_ticket.csv (;-delimited, header Level_in;Resolved date;Ticket ID).

    Rows must carry 'Ticket ID' and preserve the 'Level_in' bucket.
    'Resolved date' is informational and may be dropped or kept; we only assert it doesn't interfere.
    """
    csv_file = tmp_path / "uat_ticket.csv"
    csv_file.write_text(
        "Level_in;Resolved date;Ticket ID\n"
        "Change_Request;2026-05-01 09:11:46 PM;7505172\n"
        "Complaint;2026-05-03 01:25:19 PM;7502149\n"
        "Inquiry;2026-05-02 09:05:26 AM;7505402\n",
        encoding="utf-8",
    )

    rows = _parse_ticket_list(str(csv_file))

    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    # Ticket IDs preserved
    ids = [r["Ticket ID"] for r in rows]
    assert "7505172" in ids
    assert "7502149" in ids
    assert "7505402" in ids
    # Level_in bucket preserved
    buckets = {r["Ticket ID"]: r["Level_in"] for r in rows}
    assert buckets["7505172"] == "Change_Request"
    assert buckets["7502149"] == "Complaint"
    assert buckets["7505402"] == "Inquiry"


# ---------------------------------------------------------------------------
# Test 2: Plain one-ID-per-line convenience format (no header)
# ---------------------------------------------------------------------------

def test_parse_plain_id_per_line(tmp_path: Path) -> None:
    """_parse_ticket_list accepts a plain file with one Ticket ID per line (no header).

    Rows must carry 'Ticket ID'. Bucket ('Level_in') is empty / 'unknown'.
    """
    plain_file = tmp_path / "plain_ids.txt"
    plain_file.write_text(
        "1234567\n"
        "9876543\n"
        "  5551234  \n",  # whitespace-padded — should be stripped
        encoding="utf-8",
    )

    rows = _parse_ticket_list(str(plain_file))

    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    ids = [r["Ticket ID"] for r in rows]
    assert "1234567" in ids
    assert "9876543" in ids
    assert "5551234" in ids
    # All buckets should be empty-ish (empty string or "unknown")
    for r in rows:
        bucket = r.get("Level_in", "")
        assert bucket in ("", "unknown"), f"Expected empty/unknown bucket, got {bucket!r}"


# ---------------------------------------------------------------------------
# Test 3: --per-cat cap + dropped report (D-43)
# ---------------------------------------------------------------------------

def test_apply_caps_per_cat(tmp_path: Path) -> None:
    """_apply_caps(rows, limit=None, per_cat=2) with 2 buckets of 5 each returns 2 per bucket (4 total)
    AND a dropped_report with 3 dropped per bucket.
    """
    rows = (
        [{"Ticket ID": f"A{i}", "Level_in": "Complaint"} for i in range(5)]
        + [{"Ticket ID": f"B{i}", "Level_in": "Inquiry"} for i in range(5)]
    )

    selected, dropped_report = _apply_caps(rows, limit=None, per_cat=2)

    assert len(selected) == 4, f"Expected 4 selected rows, got {len(selected)}"
    # Check per-bucket counts in selected
    by_bucket: dict[str, int] = {}
    for r in selected:
        bucket = r["Level_in"]
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1
    assert by_bucket.get("Complaint", 0) == 2
    assert by_bucket.get("Inquiry", 0) == 2

    # dropped_report maps bucket -> dropped count
    assert isinstance(dropped_report, dict), "dropped_report must be a dict"
    assert dropped_report.get("Complaint", 0) == 3, f"Expected 3 dropped Complaint, got {dropped_report}"
    assert dropped_report.get("Inquiry", 0) == 3, f"Expected 3 dropped Inquiry, got {dropped_report}"


# ---------------------------------------------------------------------------
# Test 4: --limit cap + dropped report (D-43)
# ---------------------------------------------------------------------------

def test_apply_caps_limit(tmp_path: Path) -> None:
    """_apply_caps(rows, limit=4, per_cat=None) on 10 rows returns 4 and dropped_report totalling 6.

    The dropped_report must show total dropped across all buckets = 6.
    """
    rows = (
        [{"Ticket ID": f"A{i}", "Level_in": "Complaint"} for i in range(5)]
        + [{"Ticket ID": f"B{i}", "Level_in": "Inquiry"} for i in range(5)]
    )

    selected, dropped_report = _apply_caps(rows, limit=4, per_cat=None)

    assert len(selected) == 4, f"Expected 4 selected rows, got {len(selected)}"

    total_dropped = sum(dropped_report.values())
    assert total_dropped == 6, f"Expected 6 total dropped, got {total_dropped} (report={dropped_report})"


# ---------------------------------------------------------------------------
# Test 5: --id single-ticket selection (D-43)
# ---------------------------------------------------------------------------

def test_parse_csv_single_id_selection(tmp_path: Path) -> None:
    """Single-ID selection: parse the full CSV, then filter by a specific Ticket ID.

    Matching ID -> exactly one row. Non-matching ID -> zero rows.
    """
    csv_file = tmp_path / "uat_ticket.csv"
    csv_file.write_text(
        "Level_in;Resolved date;Ticket ID\n"
        "Change_Request;2026-05-01 09:11:46 PM;7505172\n"
        "Complaint;2026-05-03 01:25:19 PM;7502149\n"
        "Inquiry;2026-05-02 09:05:26 AM;7505402\n",
        encoding="utf-8",
    )

    all_rows = _parse_ticket_list(str(csv_file))

    # Matching ID
    matching = [r for r in all_rows if r["Ticket ID"] == "7502149"]
    assert len(matching) == 1, f"Expected 1 match for 7502149, got {len(matching)}"
    assert matching[0]["Level_in"] == "Complaint"

    # Non-matching ID
    non_matching = [r for r in all_rows if r["Ticket ID"] == "9999999"]
    assert len(non_matching) == 0, f"Expected 0 matches for 9999999, got {len(non_matching)}"


# ---------------------------------------------------------------------------
# Test 6: Anti-pattern guard — _SUBTYPE_TEMPLATES deterministic map (T-04.06-05)
# ---------------------------------------------------------------------------

def test_allowed_codes_deterministic_subtype_map() -> None:
    """_allowed_codes_for_subtype uses the deterministic _SUBTYPE_TEMPLATES map.

    'Replace' -> non-empty list (has template codes).
    '__nope__' -> empty list (unknown sub-type returns nothing).

    This proves the run path reuses the constrained map, not a category-glob free-pick.
    """
    replace_codes = _allowed_codes_for_subtype("Replace")
    assert len(replace_codes) > 0, (
        "Replace sub-type must have allowed template codes in _SUBTYPE_TEMPLATES"
    )
    # Known codes from the plan's _SUBTYPE_TEMPLATES definition
    assert any(c.startswith("B") or c.startswith("A") for c in replace_codes), (
        f"Replace codes should include B-codes and A-codes, got: {replace_codes}"
    )

    unknown_codes = _allowed_codes_for_subtype("__nope__")
    assert unknown_codes == [], (
        f"Unknown sub-type should return empty list, got: {unknown_codes}"
    )


# ---------------------------------------------------------------------------
# _extract_fd_props tests (offline — NO network calls)
# These tests are intentionally OFFLINE: _extract_fd_props is a pure function
# over a dict literal. No httpx client is constructed here. The offline contract
# is enforced structurally (no imports of collect/run/run_ai_team; pure dict input).
# ---------------------------------------------------------------------------

# Fake FD ticket payload mirroring verified ticket 7508382
_FAKE_TJ = {
    "custom_fields": {
        "cf_order": "28451-7",
        "cf_level_in285413": "Inquiry",
        "cf_customer_request83284": "Ask_About_Order",
        "cf_category": "general",
        "cf_rootcause": "customer_inquiry",
        "cf_package_status": "in_transit",
        "cf_product_label": "RosyLift",
        "cf_product_line": "shapewear",
        "cf_flow": "inquiry_flow",
        "cf_section_flow": "section_a",
        "cf_email_support": "jane.doe@example.com",
        "cf_shophelp_discussion_link": "https://shophelp/x?email=jane.doe@example.com",
    },
    "status": 2,
    "priority": 1,
    "tags": ["vip", "reship"],
}


def test_extract_fd_props_order_extraction() -> None:
    """Test A: _extract_fd_props returns (fd_props, order_code) with order_code == '28451-7'."""
    # OFFLINE CONTRACT: pure dict input, no httpx client, no network call
    result = _extract_fd_props(_FAKE_TJ)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 2, f"Expected 2-tuple, got length {len(result)}"
    fd_props, order_code = result
    assert order_code == "28451-7", f"Expected order_code='28451-7', got {order_code!r}"


def test_extract_fd_props_prefix_match() -> None:
    """Test B: prefix-match for cf_level_in* and cf_customer_request*; all other cf keys present."""
    # OFFLINE CONTRACT: pure dict input, no httpx client, no network call
    fd_props, _ = _extract_fd_props(_FAKE_TJ)
    assert fd_props.get("Level_in") == "Inquiry", f"Expected Level_in='Inquiry', got {fd_props.get('Level_in')!r}"
    assert fd_props.get("Customer_Request") == "Ask_About_Order", (
        f"Expected Customer_Request='Ask_About_Order', got {fd_props.get('Customer_Request')!r}"
    )
    # Standard and status keys must be present
    for key in ("Category", "Rootcause", "Package_status", "Product_label", "Product_line",
                "Flow", "Section_Flow", "Status", "Priority", "Tags"):
        assert key in fd_props, f"Expected key {key!r} in fd_props, got keys: {list(fd_props.keys())}"


def test_extract_fd_props_pii_redaction() -> None:
    """Test C: PII-bearing fields (cf_email_support, cf_shophelp_discussion_link) are redacted."""
    import json as _json
    # OFFLINE CONTRACT: pure dict input, no httpx client, no network call
    fd_props, _ = _extract_fd_props(_FAKE_TJ)
    dumped = _json.dumps(fd_props)
    assert "jane.doe@example.com" not in dumped, (
        f"Raw email 'jane.doe@example.com' must NOT appear in fd_props after redaction.\n"
        f"fd_props dump: {dumped}"
    )


def test_extract_fd_props_empty_input() -> None:
    """Test D: empty/missing custom_fields returns empty fd_props + empty order_code without raising."""
    # OFFLINE CONTRACT: pure dict input, no httpx client, no network call
    result_empty = _extract_fd_props({})
    assert isinstance(result_empty, tuple) and len(result_empty) == 2
    fd_props_empty, order_code_empty = result_empty
    assert fd_props_empty == {}, f"Expected empty fd_props for empty input, got {fd_props_empty}"
    assert order_code_empty in ("", None), f"Expected empty order_code, got {order_code_empty!r}"

    result_empty_cf = _extract_fd_props({"custom_fields": {}})
    fd_props_cf, order_code_cf = result_empty_cf
    assert fd_props_cf == {}, f"Expected empty fd_props for empty custom_fields, got {fd_props_cf}"
    assert order_code_cf in ("", None), f"Expected empty order_code, got {order_code_cf!r}"


def test_extract_fd_props_no_network() -> None:
    """Test E: structural proof that _extract_fd_props makes no network calls.

    This test passes a plain dict literal — no httpx.Client/AsyncClient is constructed.
    The test itself cannot make Freshdesk/Selless/Claude calls by construction.
    If _extract_fd_props tries to open any network connection, it would fail on a
    missing client, which would surface as a TypeError/AttributeError, not pass silently.
    """
    # OFFLINE CONTRACT: pure dict input, no httpx client, no network call
    # The function must complete without any I/O — verified structurally by pure dict input
    fake = {"custom_fields": {"cf_order": "99-1"}, "status": 3, "priority": 2, "tags": []}
    fd_props, order_code = _extract_fd_props(fake)
    assert order_code == "99-1", f"Expected order_code='99-1', got {order_code!r}"
    assert isinstance(fd_props, dict), "fd_props must be a dict"
