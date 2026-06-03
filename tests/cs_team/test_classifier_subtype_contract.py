"""
Structural contract test for the classifier level-2 sub-type schema.

Asserts that:
- .claude/agents/classifier.md documents all 13 Customer_Request sub-types
- .claude/agents/classifier.md contains the customer_request output field
- .claude/agents/classifier.md declares model: claude-haiku-4-5 (D-03)
- .claude/agents/classifier.md contains no reference to opus (D-03)
- .claude/skills/classify-ticket/SKILL.md contains customer_request

No LLM calls, no network access. Pure file-content assertions.
"""

from __future__ import annotations

import pathlib

import pytest

# Repository root — two levels up from tests/cs_team/
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_CLAUDE_DIR = _REPO_ROOT / ".claude"

# ---------------------------------------------------------------------------
# Canonical 13-value Customer_Request sub-type enum (RULES §2)
# ---------------------------------------------------------------------------

CUSTOMER_REQUEST_SUBTYPES: tuple[str, ...] = (
    "Return",
    "Replace",
    "Partial_Refund",
    "Full_Refund",
    "Review",
    "Cancel_Order",
    "Change_Shipping_Address",
    "Change_Product_Variant",
    "Ask_About_Delivery_Status",
    "Ask_About_Order",
    "Ask_About_Policy",
    "Ask_About_Product",
    "Ask_About_Promotion",
)

assert len(CUSTOMER_REQUEST_SUBTYPES) == 13, "Enum must have exactly 13 values"

# ---------------------------------------------------------------------------
# Paths under assertion
# ---------------------------------------------------------------------------

_CLASSIFIER_MD = _CLAUDE_DIR / "agents" / "classifier.md"
_SKILL_MD = _CLAUDE_DIR / "skills" / "classify-ticket" / "SKILL.md"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def classifier_text() -> str:
    assert _CLASSIFIER_MD.exists(), f"Missing: {_CLASSIFIER_MD}"
    return _CLASSIFIER_MD.read_text()


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert _SKILL_MD.exists(), f"Missing: {_SKILL_MD}"
    return _SKILL_MD.read_text()


@pytest.mark.parametrize("subtype", CUSTOMER_REQUEST_SUBTYPES)
def test_all_subtypes_in_classifier(subtype: str, classifier_text: str) -> None:
    """Every sub-type in the canonical enum must appear verbatim in classifier.md."""
    assert subtype in classifier_text, (
        f"Sub-type '{subtype}' missing from {_CLASSIFIER_MD}. "
        "All 13 RULES §2 values must be documented."
    )


def test_customer_request_field_in_classifier(classifier_text: str) -> None:
    """classifier.md must declare the customer_request output field."""
    assert "customer_request" in classifier_text, (
        f"'customer_request' field missing from {_CLASSIFIER_MD}. "
        "The output JSON must include this field."
    )


def test_haiku_model_in_classifier(classifier_text: str) -> None:
    """classifier.md must declare model: claude-haiku-4-5 (D-03 compliance)."""
    assert "model: claude-haiku-4-5" in classifier_text, (
        f"'model: claude-haiku-4-5' not found in {_CLASSIFIER_MD}. "
        "Classifier must stay on Haiku (D-03 — no Opus on the hot path)."
    )


def test_no_opus_in_classifier(classifier_text: str) -> None:
    """classifier.md must not reference opus (D-03 — Opus is never on the hot path)."""
    assert "opus" not in classifier_text.lower(), (
        f"'opus' found in {_CLASSIFIER_MD}. "
        "The classifier hot path must not use Opus (D-03)."
    )


def test_customer_request_field_in_skill(skill_text: str) -> None:
    """classify-ticket/SKILL.md must document the customer_request field."""
    assert "customer_request" in skill_text, (
        f"'customer_request' field missing from {_SKILL_MD}. "
        "The skill must document the full output schema."
    )


def test_fail_closed_rule_in_classifier(classifier_text: str) -> None:
    """classifier.md must document the fail-closed rule: null + confidence:low."""
    # Accept any of the documented phrasings
    has_null_rule = (
        "customer_request: null" in classifier_text
        or "cannot be confidently determined" in classifier_text
        or "confidence: low" in classifier_text
    )
    assert has_null_rule, (
        f"Fail-closed rule (null + confidence:low) not found in {_CLASSIFIER_MD}. "
        "The classifier must document that an unresolvable sub-type → null + low confidence."
    )


def test_subtype_count_is_exactly_13() -> None:
    """Sanity check: the module constant must enumerate exactly 13 sub-types."""
    assert len(CUSTOMER_REQUEST_SUBTYPES) == 13, (
        f"CUSTOMER_REQUEST_SUBTYPES has {len(CUSTOMER_REQUEST_SUBTYPES)} values; expected 13."
    )
