"""
Always-draft contract tests for cs_team_demo.py (D-33 / 04-03).

Asserts the always-draft contract across four fixture types:
  1. BENIGN_TICKET:        action=draft, escalation_hint=None, body matches real B7 template
  2. HIGH_RISK_TICKET:     action=draft, escalation_hint.reason="high_risk", body matches B7
  3. INJECTION_TICKET:     action=draft, escalation_hint.reason starts with "injection:"
  4. MISSING_ORDER_TICKET: action=draft, verify/clarify-order body, no fabricated order number

No fixture ever yields action=escalate with no body (D-33 non-negotiable).

All tests use the DRY_RUN simulation path (no live `claude` CLI, no Anthropic key needed).

W4 body-match assertion: BENIGN and HIGH_RISK use template-backed sub-types (Return,
Partial_Refund → code B7). The test fetches the real B7 template body via
get_template_from_file("B7") and asserts a verbatim substring appears in the draft.
This proves the simulated draft is grounded on the real local file-store (D-31),
not on an empty or invented body.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap (mirrors cs_team_demo.py)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.cs_team_demo import run_ticket  # noqa: E402
from src.file_store.template_store import get_template_from_file  # noqa: E402
from tests.fixtures.sample_tickets import (  # noqa: E402
    BENIGN_TICKET,
    HIGH_RISK_TICKET,
    INJECTION_TICKET,
    MISSING_ORDER_TICKET,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(ticket: dict) -> dict:
    """Sync wrapper for run_ticket (simulation path, no live claude CLI)."""
    return asyncio.run(run_ticket(ticket, use_live_claude=False))


def _get_template_body(code: str) -> str:
    """Return the real template body for *code* from the local file-store.

    Raises AssertionError if the template is not found (test-infrastructure failure).
    """
    result = get_template_from_file(code)
    assert result["found"], (
        f"Template code {code!r} not found in local file-store — "
        "check that the snapshot file is present in SNAPSHOTS_DIR. "
        "This is a test-infrastructure failure, not a product bug."
    )
    body = result["body"]
    assert body, f"Template code {code!r} found but body is empty"
    return body


def _first_words(text: str, n: int = 12) -> str:
    """Return first n whitespace-separated words of text (for clearer assertion messages)."""
    return " ".join(text.split()[:n])


# ---------------------------------------------------------------------------
# D-33 core invariant: ALL tickets yield action=draft (never escalate=no-draft)
# ---------------------------------------------------------------------------

class TestAlwaysDraftInvariant:
    """Every sample ticket must yield action='draft' — the non-negotiable D-33 contract."""

    @pytest.mark.parametrize("ticket,label", [
        (BENIGN_TICKET, "BENIGN"),
        (HIGH_RISK_TICKET, "HIGH_RISK"),
        (INJECTION_TICKET, "INJECTION"),
        (MISSING_ORDER_TICKET, "MISSING_ORDER"),
    ])
    def test_action_is_always_draft(self, ticket: dict, label: str) -> None:
        verdict = _run(ticket)
        assert verdict.get("action") == "draft", (
            f"[{label}] expected action='draft' (D-33); "
            f"got action={verdict.get('action')!r} — D-33 violated"
        )

    @pytest.mark.parametrize("ticket,label", [
        (BENIGN_TICKET, "BENIGN"),
        (HIGH_RISK_TICKET, "HIGH_RISK"),
        (INJECTION_TICKET, "INJECTION"),
        (MISSING_ORDER_TICKET, "MISSING_ORDER"),
    ])
    def test_body_is_present_and_non_empty(self, ticket: dict, label: str) -> None:
        """draft body must be non-empty — an empty body is not a valid always-draft response."""
        verdict = _run(ticket)
        assert verdict.get("action") == "draft", f"[{label}] action!=draft (covered by other test)"
        body = verdict.get("body", "")
        assert body and body.strip(), (
            f"[{label}] draft body is empty — file-store grounding or D-34 fallback failed"
        )

    @pytest.mark.parametrize("ticket,label", [
        (BENIGN_TICKET, "BENIGN"),
        (HIGH_RISK_TICKET, "HIGH_RISK"),
        (INJECTION_TICKET, "INJECTION"),
        (MISSING_ORDER_TICKET, "MISSING_ORDER"),
    ])
    def test_no_escalate_no_draft_shape(self, ticket: dict, label: str) -> None:
        """The old escalate=no-draft shape {action:escalate, reason:...} must NEVER appear."""
        verdict = _run(ticket)
        assert verdict.get("action") != "escalate", (
            f"[{label}] got action='escalate' — D-33 violated (always-draft PoC)"
        )
        # An escalate verdict with no body is the exact retired D-10 shape — double-check
        if verdict.get("action") == "escalate":
            assert False, (
                f"[{label}] D-10-style escalate=no-draft returned: {verdict!r}"
            )


# ---------------------------------------------------------------------------
# BENIGN_TICKET: action=draft, escalation_hint=None, body matches real B7 template
# ---------------------------------------------------------------------------

class TestBenignTicket:

    def test_action_draft(self) -> None:
        verdict = _run(BENIGN_TICKET)
        assert verdict["action"] == "draft"

    def test_escalation_hint_is_none(self) -> None:
        verdict = _run(BENIGN_TICKET)
        hint = verdict.get("escalation_hint")
        assert hint is None, (
            f"BENIGN ticket should have escalation_hint=None; got: {hint!r}"
        )

    def test_body_matches_real_template(self) -> None:
        """W4: body must contain a verbatim substring of the real B7 template body.

        This proves the draft is grounded on the local file-store (D-31), not on
        an empty or fabricated body.
        """
        expected_code = BENIGN_TICKET.get("expected_code", "B7")
        template_body = _get_template_body(expected_code)

        # Extract a distinctive 10-word phrase from the real template to match against
        template_words = template_body.split()
        assert len(template_words) >= 10, (
            f"Template {expected_code!r} body too short to assert a meaningful match"
        )
        # Use the first 10 words as the anchor substring
        anchor = " ".join(template_words[:10])

        verdict = _run(BENIGN_TICKET)
        draft_body = verdict.get("body", "")
        assert anchor in draft_body, (
            f"BENIGN draft body does not contain verbatim anchor from template {expected_code!r}.\n"
            f"Expected anchor (first 10 words of template): {anchor!r}\n"
            f"Draft body starts with: {_first_words(draft_body, 20)!r}"
        )

    def test_citations_present(self) -> None:
        verdict = _run(BENIGN_TICKET)
        citations = verdict.get("citations", [])
        assert len(citations) >= 1, "BENIGN draft must have at least one citation"


# ---------------------------------------------------------------------------
# HIGH_RISK_TICKET: action=draft, advisory escalation_hint.reason="high_risk"
# ---------------------------------------------------------------------------

class TestHighRiskTicket:

    def test_action_draft(self) -> None:
        verdict = _run(HIGH_RISK_TICKET)
        assert verdict["action"] == "draft"

    def test_escalation_hint_present_and_high_risk(self) -> None:
        verdict = _run(HIGH_RISK_TICKET)
        hint = verdict.get("escalation_hint")
        assert hint is not None, (
            "HIGH_RISK ticket must carry a non-null advisory escalation_hint"
        )
        reason = hint.get("reason", "")
        assert "high_risk" in reason, (
            f"HIGH_RISK escalation_hint.reason should contain 'high_risk'; got: {reason!r}"
        )

    def test_hint_is_advisory_only(self) -> None:
        """Hint must not change action — action must still be draft."""
        verdict = _run(HIGH_RISK_TICKET)
        assert verdict["action"] == "draft", (
            "escalation_hint must be advisory only — action must remain 'draft'"
        )

    def test_body_matches_real_template(self) -> None:
        """W4: body must contain a verbatim substring of the real B7 template body."""
        expected_code = HIGH_RISK_TICKET.get("expected_code", "B7")
        template_body = _get_template_body(expected_code)

        template_words = template_body.split()
        assert len(template_words) >= 10
        anchor = " ".join(template_words[:10])

        verdict = _run(HIGH_RISK_TICKET)
        draft_body = verdict.get("body", "")
        assert anchor in draft_body, (
            f"HIGH_RISK draft body does not contain verbatim anchor from template {expected_code!r}.\n"
            f"Expected anchor: {anchor!r}\n"
            f"Draft body starts with: {_first_words(draft_body, 20)!r}"
        )


# ---------------------------------------------------------------------------
# INJECTION_TICKET: action=draft, advisory escalation_hint.reason starts with "injection:"
# ---------------------------------------------------------------------------

class TestInjectionTicket:

    def test_action_draft(self) -> None:
        verdict = _run(INJECTION_TICKET)
        assert verdict["action"] == "draft", (
            "INJECTION ticket must yield action=draft (D-30: injection no longer suppresses draft)"
        )

    def test_escalation_hint_injection(self) -> None:
        verdict = _run(INJECTION_TICKET)
        hint = verdict.get("escalation_hint")
        assert hint is not None, (
            "INJECTION ticket must carry a non-null advisory escalation_hint"
        )
        reason = hint.get("reason", "")
        assert reason.startswith("injection:"), (
            f"INJECTION escalation_hint.reason must start with 'injection:'; got: {reason!r}"
        )

    def test_injection_hint_advisory_only(self) -> None:
        """injection_screen still flags (D-14) but draft is still emitted (D-30)."""
        verdict = _run(INJECTION_TICKET)
        assert verdict["action"] == "draft", (
            "injection escalation_hint must be advisory only — action must remain 'draft'"
        )

    def test_injection_signals_flag(self) -> None:
        verdict = _run(INJECTION_TICKET)
        hint = verdict.get("escalation_hint") or {}
        signals = hint.get("signals", {})
        assert signals.get("injection") is True, (
            f"INJECTION hint.signals.injection should be True; got signals={signals!r}"
        )


# ---------------------------------------------------------------------------
# MISSING_ORDER_TICKET: action=draft, verify/clarify-order body, no fabricated order number
# ---------------------------------------------------------------------------

class TestMissingOrderTicket:

    def test_action_draft(self) -> None:
        verdict = _run(MISSING_ORDER_TICKET)
        assert verdict["action"] == "draft"

    def test_body_references_verify_clarify_order(self) -> None:
        """D-34: body must reference a verify/clarify-order flow.

        The body should ask the customer for their order number rather than
        fabricating one. Keywords: 'order number' or 'provide your order' or
        similar verify-order phrasing.
        """
        verdict = _run(MISSING_ORDER_TICKET)
        body = verdict.get("body", "").lower()
        verify_patterns = [
            "order number",
            "provide your order",
            "order details",
            "order confirmation",
        ]
        matched = any(p in body for p in verify_patterns)
        assert matched, (
            f"MISSING_ORDER draft body should reference a verify/clarify-order flow.\n"
            f"Expected one of {verify_patterns!r} in body.\n"
            f"Body: {body[:300]!r}"
        )

    def test_body_contains_no_fabricated_order_number(self) -> None:
        """D-34: body must NOT contain an invented order number.

        A fabricated order number would look like ORD-XXXXXXXX-XXXX or similar
        patterns with mixed digits and dashes that the runner invented.
        The fixture has order_ref="" so any ORD-... in the body is fabricated.
        """
        verdict = _run(MISSING_ORDER_TICKET)
        body = verdict.get("body", "")
        # Regex: order numbers typically look like ORD-YYYYMMDD-NNNN or similar
        # The ticket has no real order ref — any ORD-... in the draft is fabricated
        fabricated_pattern = re.compile(
            r"\bORD-\d{4,}\b",
            re.IGNORECASE,
        )
        match = fabricated_pattern.search(body)
        assert match is None, (
            f"MISSING_ORDER draft body contains a fabricated order number: {match.group()!r}\n"
            f"D-34 violation: never invent order facts on a missing order.\n"
            f"Body: {body[:400]!r}"
        )

    def test_missing_order_hint_is_not_high_risk(self) -> None:
        """Missing-order ticket has no category — should produce no high_risk hint."""
        verdict = _run(MISSING_ORDER_TICKET)
        hint = verdict.get("escalation_hint")
        # hint may be None (fine) or present with a reason that is NOT high_risk
        if hint is not None:
            reason = hint.get("reason", "")
            assert "high_risk" not in reason, (
                f"MISSING_ORDER ticket should not have a high_risk hint; got reason={reason!r}"
            )


# ---------------------------------------------------------------------------
# W4 guard: no fixture uses Review sub-type (Review → [] → empty body)
# ---------------------------------------------------------------------------

class TestNoReviewSubtype:
    """W4: assert no BENIGN/HIGH_RISK fixture uses Review as the sub-type.

    Review returns subtype_to_code() == [] which yields an empty template body.
    Using it would allow a draft with an empty body to falsely pass action=draft.
    """

    def test_benign_not_review(self) -> None:
        sub = BENIGN_TICKET.get("sub_type", "")
        assert sub != "Review", (
            "BENIGN_TICKET uses sub_type='Review' — W4 violation. "
            "Use a template-backed sub-type (e.g. Return → B7)."
        )

    def test_high_risk_not_review(self) -> None:
        sub = HIGH_RISK_TICKET.get("sub_type", "")
        assert sub != "Review", (
            "HIGH_RISK_TICKET uses sub_type='Review' — W4 violation. "
            "Use a template-backed sub-type (e.g. Partial_Refund → B7)."
        )
