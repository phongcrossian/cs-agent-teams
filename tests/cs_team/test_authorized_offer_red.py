"""
RED-phase tests for authorized_offer module (Task 1 — TDD gate).

These tests MUST FAIL before authorized_offer.py is created.
They are the failing-test contract that GREEN phase must satisfy.

Run: uv run pytest tests/cs_team/test_authorized_offer_red.py -q
Expected before implementation: ImportError / AttributeError (module does not exist)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "authorized_offer.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("authorized_offer", _HOOK_PATH)
    assert spec is not None and spec.loader is not None, "authorized_offer.py not found"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_red_module_importable() -> None:
    """RED: module must exist and expose authorize_offer."""
    m = _load_module()
    assert hasattr(m, "authorize_offer"), "authorize_offer function missing"


def test_red_review_always_escalates() -> None:
    """RED: Review sub-type must always return (False, 'unauthorized:force_escalate:no_flow')."""
    m = _load_module()
    ok, reason = m.authorize_offer("Review")
    assert ok is False
    assert reason == "unauthorized:force_escalate:no_flow"


def test_red_partial_refund_authorized_happy_path() -> None:
    """RED: Partial_Refund with B7 within thresholds -> authorized."""
    m = _load_module()
    ok, reason = m.authorize_offer(
        "Partial_Refund", "B7",
        {"refund_pct": 50, "discount_pct": 40},
        {"in_warranty": True, "prior_remediation": False},
    )
    assert ok is True
    assert reason == "authorized:B7"


def test_red_partial_refund_over_threshold() -> None:
    """RED: Partial_Refund with 70% refund -> unauthorized:over_threshold:THR-07."""
    m = _load_module()
    ok, reason = m.authorize_offer(
        "Partial_Refund", "B7",
        {"refund_pct": 70},
        {"in_warranty": True, "prior_remediation": False},
    )
    assert ok is False
    assert "over_threshold" in reason
