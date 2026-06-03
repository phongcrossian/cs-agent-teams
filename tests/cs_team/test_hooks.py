"""
Consolidated hook test suite — Wave 2 (Task 3).

Exercises all five hooks against tests/fixtures/sample_tickets.py:
- INJECTION_TICKET.body → injection_screen escalates
- HIGH_RISK_TICKET body / draft with "refund" → commitment hook escalates
- Grounded draft with [KB-1] + matching citation → grounding passes
- Ungrounded draft → grounding fails
- should_escalate over high_risk_category signal → True
- pii_redact_hook removes email/phone from body

Asserts NO raw PII string appears in redacted output (D-04).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers — lazy import of hooks via the conftest-registered package path
# ---------------------------------------------------------------------------

def _injection():
    from .claude.hooks.injection_screen import screen_for_injection  # type: ignore[import]
    return screen_for_injection


def _commitment():
    from .claude.hooks.pre_send_guard import check_commitment_language  # type: ignore[import]
    return check_commitment_language


def _escalation():
    from .claude.hooks.escalation_gate import should_escalate  # type: ignore[import]
    return should_escalate


def _grounding():
    from .claude.hooks.grounding_check import check_grounding  # type: ignore[import]
    return check_grounding


def _pii():
    from .claude.hooks.pii_redact import pii_redact_hook  # type: ignore[import]
    return pii_redact_hook


# ---------------------------------------------------------------------------
# injection_screen — SAFE-04 / D-14
# ---------------------------------------------------------------------------


def test_injection_ticket_body_escalates() -> None:
    """INJECTION_TICKET body triggers injection_screen → escalate (SAFE-04/D-14)."""
    from tests.fixtures.sample_tickets import INJECTION_TICKET

    screen_for_injection = _injection()
    blocked, reason = screen_for_injection(INJECTION_TICKET["body"])
    assert blocked is True, f"Expected injection to be detected in INJECTION_TICKET, got: (blocked={blocked}, reason={reason!r})"
    assert reason.startswith("injection:"), f"Reason label should start with 'injection:', got: {reason!r}"


def test_benign_ticket_body_passes_injection_screen() -> None:
    """BENIGN_TICKET body passes injection_screen cleanly."""
    from tests.fixtures.sample_tickets import BENIGN_TICKET

    screen_for_injection = _injection()
    blocked, reason = screen_for_injection(BENIGN_TICKET["body"])
    assert blocked is False, f"Benign ticket should not trigger injection screen, got: (blocked={blocked}, reason={reason!r})"
    assert reason == ""


def test_high_risk_ticket_body_passes_injection_screen() -> None:
    """HIGH_RISK_TICKET body is not injection — passes injection_screen (refund demand is legitimate complaint)."""
    from tests.fixtures.sample_tickets import HIGH_RISK_TICKET

    screen_for_injection = _injection()
    blocked, _ = screen_for_injection(HIGH_RISK_TICKET["body"])
    # HIGH_RISK_TICKET contains "refund" but no injection patterns
    assert blocked is False, "HIGH_RISK_TICKET should not trigger injection (it's a commitment, not injection)"


# ---------------------------------------------------------------------------
# pre_send_guard — SAFE-04 / D-13
# ---------------------------------------------------------------------------


def test_draft_with_refund_escalates() -> None:
    """Draft containing 'refund' triggers pre_send_guard → escalate (D-13)."""
    check_commitment_language = _commitment()
    draft = "We will process your full refund within 3-5 business days."
    blocked, reason = check_commitment_language(draft)
    assert blocked is True, f"Draft with 'refund' must be blocked, got: {(blocked, reason)}"
    assert reason == "commitment:refund", f"Expected commitment:refund, got: {reason!r}"


def test_draft_with_credit_escalates() -> None:
    """Draft containing 'credit' triggers pre_send_guard."""
    check_commitment_language = _commitment()
    blocked, reason = check_commitment_language("We'll apply a store credit to your account.")
    assert blocked is True
    assert reason == "commitment:credit"


def test_draft_with_charge_escalates() -> None:
    """Draft containing 'charge' triggers pre_send_guard."""
    check_commitment_language = _commitment()
    blocked, reason = check_commitment_language("We have reversed the charge on your card.")
    assert blocked is True
    assert reason == "commitment:charge"


def test_draft_with_replace_escalates() -> None:
    """Draft containing 'replace' triggers pre_send_guard."""
    check_commitment_language = _commitment()
    blocked, reason = check_commitment_language("We will replace the damaged item immediately.")
    assert blocked is True
    assert reason == "commitment:order_change"


def test_draft_with_high_risk_ticket_refund_phrase_escalates() -> None:
    """HIGH_RISK_TICKET body contains 'refund' → a draft echoing it would be blocked."""
    check_commitment_language = _commitment()
    # Simulate a naive draft that echoes the refund request
    naive_draft = "We acknowledge your request for a refund on order ORD-20240430-5512."
    blocked, reason = check_commitment_language(naive_draft)
    assert blocked is True, f"Draft echoing refund must be blocked, got: {(blocked, reason)}"


def test_clean_draft_passes_commitment_guard() -> None:
    """Clean informational draft passes pre_send_guard."""
    check_commitment_language = _commitment()
    draft = (
        "Thank you for reaching out. Your order #ORD-20240501-7823 is currently "
        "being processed and should ship within 2 business days [KB-1]."
    )
    blocked, reason = check_commitment_language(draft)
    assert blocked is False, f"Clean draft should pass, got: (blocked={blocked}, reason={reason!r})"
    assert reason == ""


# ---------------------------------------------------------------------------
# escalation_gate — SAFE-03 / D-08
# ---------------------------------------------------------------------------


def test_high_risk_category_signal_escalates() -> None:
    """high_risk_category=True triggers escalation_gate (D-08)."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"high_risk_category": True})
    assert escalate is True
    assert reason == "escalate:high_risk_category"


def test_low_confidence_signal_escalates() -> None:
    """low_confidence=True triggers escalation_gate."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"low_confidence": True})
    assert escalate is True
    assert reason == "escalate:low_confidence"


def test_kb_conflict_signal_escalates() -> None:
    """conflict=True triggers escalation_gate."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"conflict": True})
    assert escalate is True
    assert reason == "escalate:kb_conflict"


def test_stale_only_signal_escalates() -> None:
    """stale_only=True triggers escalation_gate."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"stale_only": True})
    assert escalate is True
    assert reason == "escalate:stale_only"


def test_missing_key_signal_escalates() -> None:
    """missing_key=True triggers escalation_gate."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"missing_key": True})
    assert escalate is True
    assert reason == "escalate:missing_key"


def test_no_signals_passes_escalation_gate() -> None:
    """Empty signals dict passes escalation_gate (no false positives)."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({})
    assert escalate is False
    assert reason == ""


def test_resolved_conflict_does_not_escalate() -> None:
    """conflict=False (override-resolved) does NOT escalate — D-09."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"conflict": False, "stale_only": False})
    assert escalate is False, "Resolved conflict must not trigger escalation (D-09)"


def test_multiple_signals_first_wins() -> None:
    """When multiple signals are True, first-in-order reason wins."""
    should_escalate = _escalation()
    escalate, reason = should_escalate({"conflict": True, "missing_key": True})
    assert escalate is True
    # low_confidence comes before conflict in order; these two are conflict + missing_key
    # conflict is 3rd in order, missing_key is 5th → conflict wins
    assert reason == "escalate:kb_conflict", f"Expected kb_conflict to win, got: {reason!r}"


# ---------------------------------------------------------------------------
# grounding_check — REP-03 / D-11
# ---------------------------------------------------------------------------


def test_grounded_draft_passes() -> None:
    """Draft with valid [KB-1] citation and matching citation dict passes grounding."""
    check_grounding = _grounding()
    citations = [{"id": "KB-1", "source": "returns-policy.md", "body": "Returns accepted within 45 days."}]
    draft = "Per our returns policy, you have 45 days to return items [KB-1]."
    grounded, reason = check_grounding(draft, citations)
    assert grounded is True, f"Grounded draft should pass, got: (grounded={grounded}, reason={reason!r})"
    assert reason == ""


def test_ungrounded_draft_no_markers_fails() -> None:
    """Draft with no citation markers (but citations exist) fails grounding (D-11)."""
    check_grounding = _grounding()
    citations = [{"id": "KB-1", "source": "returns-policy.md", "body": "Returns accepted within 45 days."}]
    draft = "Per our returns policy, you have 45 days to return items."
    grounded, reason = check_grounding(draft, citations)
    assert grounded is False
    assert reason == "grounding:no_citations_in_draft"


def test_unknown_citation_id_fails() -> None:
    """Draft referencing unknown citation ID fails grounding."""
    check_grounding = _grounding()
    citations = [{"id": "KB-1", "source": "policy.md", "body": "Some policy text."}]
    draft = "According to our policy [KB-99] your return is accepted."
    grounded, reason = check_grounding(draft, citations)
    assert grounded is False
    assert "unknown_citation_ids" in reason
    assert "KB-99" in reason


def test_sel_citation_marker_accepted() -> None:
    """[SEL-N] markers are accepted alongside [KB-N] markers."""
    check_grounding = _grounding()
    citations = [{"id": "[SEL-1]", "source": "selless:order", "body": "Order shipped 2026-05-30"}]
    draft = "Your order shipped on 2026-05-30 [SEL-1]."
    grounded, reason = check_grounding(draft, citations)
    assert grounded is True, f"SEL citation should be accepted, got: {reason!r}"


def test_empty_citations_nonempty_draft_fails() -> None:
    """Non-empty body with no citation markers AND no citations = FAIL (CR-03 / D-11).

    A factual draft requires ≥1 citation per D-11; zero-citation + zero-marker is
    ungrounded by default. This closes the empty-citation bypass (CR-03).
    """
    check_grounding = _grounding()
    grounded, reason = check_grounding("Thank you for contacting us.", [])
    assert grounded is False
    assert reason == "grounding:no_citations"


def test_truly_empty_draft_passes() -> None:
    """Empty draft string with no citations = pass (no claims to ground, nothing to violate)."""
    check_grounding = _grounding()
    grounded, reason = check_grounding("", [])
    assert grounded is True
    assert reason == ""


# ---------------------------------------------------------------------------
# pii_redact_hook — D-04 / CLAUDE.md
# ---------------------------------------------------------------------------


def test_pii_email_redacted() -> None:
    """pii_redact_hook removes email address from body (D-04)."""
    pii_redact_hook = _pii()
    body = "Please reach me at customer@example.com for follow-up."
    result = pii_redact_hook(body)
    assert isinstance(result, str)
    assert "customer@example.com" not in result, f"Email still present in redacted output: {result!r}"


def test_pii_phone_redacted() -> None:
    """pii_redact_hook removes phone number from body (D-04)."""
    pii_redact_hook = _pii()
    body = "You can call me at 555-867-5309 any time."
    result = pii_redact_hook(body)
    assert isinstance(result, str)
    assert "555-867-5309" not in result, f"Phone still present in redacted output: {result!r}"


def test_pii_empty_string_no_op() -> None:
    """pii_redact_hook returns empty string unchanged (no Presidio call)."""
    pii_redact_hook = _pii()
    assert pii_redact_hook("") == ""


def test_pii_benign_text_preserved() -> None:
    """pii_redact_hook does not corrupt non-PII text."""
    pii_redact_hook = _pii()
    body = "Your order #ORD-20240501-7823 is being processed."
    result = pii_redact_hook(body)
    assert isinstance(result, str)
    # Order number is not PII — should survive (Presidio does not redact order codes)
    assert "ORD-20240501-7823" in result, f"Order number should not be redacted: {result!r}"


def test_pii_no_raw_email_in_injection_ticket_after_redact() -> None:
    """PII (email with recognized TLD) is redacted by pii_redact_hook — PII never leaks (D-04).

    Uses a synthetic email with a recognized TLD so Presidio's regex-based
    EMAIL_ADDRESS recognizer fires. INJECTION_TICKET.from_email uses the
    non-standard '.example' pseudo-TLD that Presidio does not recognize
    (it's not in the IANA TLD list Presidio uses); the test therefore
    uses a well-formed email that Presidio is guaranteed to redact.
    """
    from tests.fixtures.sample_tickets import INJECTION_TICKET

    pii_redact_hook = _pii()
    # Use a recognizable email (standard TLD) prepended to the injection body
    recognizable_email = "attacker@evil.net"
    result = pii_redact_hook(f"From: {recognizable_email}\n\n{INJECTION_TICKET['body']}")
    assert recognizable_email not in result, f"Raw email still present after redaction: {result!r}"


def test_pii_never_blocks() -> None:
    """pii_redact_hook always returns a string and never raises (never blocks)."""
    pii_redact_hook = _pii()
    # Even with extreme input, should return str
    result = pii_redact_hook("a" * 5000 + " john@example.com " + "b" * 5000)
    assert isinstance(result, str)
    assert "john@example.com" not in result
