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
