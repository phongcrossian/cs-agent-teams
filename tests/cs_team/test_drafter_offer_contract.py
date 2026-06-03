"""
Structural contract tests for the drafter agent and ground-and-draft skill.

Verifies that:
 - drafter.md documents the offer block (asserts_mutation, D-26, RD-Q2, customer_request)
 - drafter.md stays on claude-sonnet-4-6 (D-03: no Opus on hot path)
 - drafter.md no longer contains the old D-13 blanket-ban phrase "absolutely forbidden"
 - drafter.md documents RD-Q1 (never assert operational action)
 - ground-and-draft SKILL.md documents customer_request sub-type selection and D-26
 - ground-and-draft SKILL.md does NOT contain the old "Commitment Language Ban (D-13)" heading

No LLM calls. No network. Pure text/file assertions.
"""

from __future__ import annotations

import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_DRAFTER = _REPO_ROOT / ".claude" / "agents" / "drafter.md"
_SKILL = _REPO_ROOT / ".claude" / "skills" / "ground-and-draft" / "SKILL.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: pathlib.Path) -> str:
    assert path.exists(), f"Required file missing: {path}"
    return path.read_text()


# ---------------------------------------------------------------------------
# drafter.md — model / identity
# ---------------------------------------------------------------------------

def test_drafter_declares_sonnet() -> None:
    """D-03: drafter must stay on claude-sonnet-4-6 (no Opus on hot path)."""
    content = _read(_DRAFTER)
    assert "model: claude-sonnet-4-6" in content, (
        "drafter.md must declare 'model: claude-sonnet-4-6'"
    )


def test_drafter_contains_no_opus() -> None:
    """D-03: 'opus' must not appear in drafter.md — Opus is never on the hot path."""
    content = _read(_DRAFTER).lower()
    assert "opus" not in content, (
        "drafter.md must not reference 'opus' — Opus is reserved for Phase-5 eval judge only"
    )


# ---------------------------------------------------------------------------
# drafter.md — offer block (D-26 / RD-Q1 / RD-Q2)
# ---------------------------------------------------------------------------

def test_drafter_documents_asserts_mutation() -> None:
    """The offer block contract requires 'asserts_mutation' to be documented."""
    content = _read(_DRAFTER)
    assert "asserts_mutation" in content, (
        "drafter.md must document 'asserts_mutation' in the offer block (D-26 / RD-Q1)"
    )


def test_drafter_documents_d26() -> None:
    """D-26 supersedes D-13 — the drafter must reference D-26."""
    content = _read(_DRAFTER)
    assert "D-26" in content, (
        "drafter.md must reference 'D-26' (authorized offer model replacing D-13 ban)"
    )


def test_drafter_documents_rd_q2_stub() -> None:
    """RD-Q2 stub marker must be present — eligibility is stubbed until plan 04-11."""
    content = _read(_DRAFTER)
    assert "RD-Q2" in content, (
        "drafter.md must contain 'RD-Q2' stub marker for eligibility fields"
    )


def test_drafter_documents_customer_request() -> None:
    """The drafter must key template selection on customer_request sub-type."""
    content = _read(_DRAFTER)
    assert "customer_request" in content, (
        "drafter.md must reference 'customer_request' for sub-type-based template selection"
    )


def test_drafter_documents_rd_q1_non_assertion() -> None:
    """RD-Q1: drafter must document that it never asserts a completed operational action."""
    content = _read(_DRAFTER)
    lower = content.lower()
    # The rule appears under 'RD-Q1' label or as an explicit 'never' + 'operational' / 'mutation' statement
    assert "rd-q1" in lower or (
        "never" in lower and ("operational" in lower or "mutation" in lower)
    ), (
        "drafter.md must document RD-Q1 (never assert completed operational action)"
    )


def test_drafter_no_absolutely_forbidden_blanket_ban() -> None:
    """The old D-13 blanket ban phrase 'absolutely forbidden' must be gone."""
    content = _read(_DRAFTER).lower()
    assert "absolutely forbidden" not in content, (
        "drafter.md must NOT contain 'absolutely forbidden' — old D-13 blanket ban replaced by D-26"
    )


def test_drafter_documents_submit_reply_as_sole_path() -> None:
    """submit_reply must be referenced as the only emission path."""
    content = _read(_DRAFTER)
    assert "submit_reply" in content, (
        "drafter.md must reference submit_reply (the sole emission path, §4a)"
    )


def test_drafter_documents_eligibility_grounding() -> None:
    """Eligibility grounding (warranty, prior_remediation) must be documented."""
    content = _read(_DRAFTER).lower()
    assert "eligibility" in content or "warranty" in content or "prior_remediation" in content, (
        "drafter.md must document eligibility grounding before making any offer"
    )


# ---------------------------------------------------------------------------
# ground-and-draft SKILL.md — D-26 / customer_request
# ---------------------------------------------------------------------------

def test_skill_documents_customer_request() -> None:
    """Skill must document template selection keyed on customer_request sub-type."""
    content = _read(_SKILL)
    assert "customer_request" in content, (
        "ground-and-draft SKILL.md must reference 'customer_request' for sub-type-based template selection"
    )


def test_skill_documents_d26() -> None:
    """Skill must reference D-26 (authorized offer replacing D-13 ban)."""
    content = _read(_SKILL)
    assert "D-26" in content, (
        "ground-and-draft SKILL.md must reference 'D-26' authorized offer model"
    )


def test_skill_no_old_d13_ban_heading() -> None:
    """Old 'Commitment Language Ban (D-13)' heading must be gone from skill."""
    content = _read(_SKILL)
    assert "Commitment Language Ban (D-13)" not in content, (
        "ground-and-draft SKILL.md must NOT contain 'Commitment Language Ban (D-13)' heading — replaced by D-26 section"
    )


def test_skill_documents_offer_block() -> None:
    """Skill must document the structured offer block passed to submit_reply."""
    content = _read(_SKILL)
    assert "asserts_mutation" in content, (
        "ground-and-draft SKILL.md must document 'asserts_mutation' in the offer block"
    )


def test_skill_documents_rd_q2_stub() -> None:
    """Skill must carry the RD-Q2 stub marker for eligibility fields."""
    content = _read(_SKILL)
    assert "RD-Q2" in content, (
        "ground-and-draft SKILL.md must contain 'RD-Q2' eligibility stub marker"
    )
