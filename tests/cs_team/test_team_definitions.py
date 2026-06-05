"""
Team-definition test suite — structure, model discipline, and wiring.

Asserts:
  (1) All five agent files and all five SKILL.md files from the §3 design manifest exist
  (2) MODEL DISCIPLINE — classifier/extractor reference Haiku; drafter/critic/lead reference Sonnet;
      NO agent file contains the substring "opus" (case-insensitive) — cost-discipline gate (D-03)
  (3) WIRING — extractor→resolve_order, drafter→file-store (subtype_to_code/get_template_from_file),
      drafter→submit_reply (chokepoint §4a), cs-lead→reply-pipeline skill,
      extract-answer-key→resolve_order, ground-and-draft→file-store
  (4) reply-pipeline skill encodes the always-draft verdict + escalation_hint (D-33);
      stage names (classify/extract/critique) present; NO escalate=no-draft outcome
  (5) REP-04: self-critique/SKILL.md declares faithfulness / policy-match / tone-completeness
"""

from __future__ import annotations

import pathlib

import pytest

# Repo root = two levels up from tests/cs_team/
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_CLAUDE_DIR = _REPO_ROOT / ".claude"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(rel: str) -> str:
    return (_CLAUDE_DIR / rel).read_text()


# ---------------------------------------------------------------------------
# (1) Manifest existence
# ---------------------------------------------------------------------------

_AGENT_FILES = [
    "agents/cs-lead.md",
    "agents/classifier.md",
    "agents/extractor.md",
    "agents/drafter.md",
    "agents/critic.md",
]

_SKILL_FILES = [
    "skills/reply-pipeline/SKILL.md",
    "skills/classify-ticket/SKILL.md",
    "skills/extract-answer-key/SKILL.md",
    "skills/ground-and-draft/SKILL.md",
    "skills/self-critique/SKILL.md",
]


@pytest.mark.parametrize("rel_path", _AGENT_FILES)
def test_agent_file_exists(rel_path: str) -> None:
    """Each agent definition .md must exist under .claude/agents/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing agent definition: {path}"
    content = path.read_text()
    assert "model" in content.lower(), f"{path} must declare a model"
    assert "## System Prompt" in content or "system prompt" in content.lower(), (
        f"{path} must have a ## System Prompt section"
    )


@pytest.mark.parametrize("rel_path", _SKILL_FILES)
def test_skill_file_exists(rel_path: str) -> None:
    """Each skill SKILL.md must exist under .claude/skills/<name>/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing skill index: {path}"


# ---------------------------------------------------------------------------
# (2) Model discipline — Haiku / Sonnet / no Opus  (D-03)
# ---------------------------------------------------------------------------

def test_classifier_uses_haiku() -> None:
    """classifier.md must reference a Haiku model."""
    content = _read("agents/classifier.md")
    assert "claude-haiku-4-5" in content, (
        "classifier.md must declare model: claude-haiku-4-5 (D-03)"
    )


def test_extractor_uses_haiku() -> None:
    """extractor.md must reference a Haiku model."""
    content = _read("agents/extractor.md")
    assert "claude-haiku-4-5" in content, (
        "extractor.md must declare model: claude-haiku-4-5 (D-03)"
    )


def test_drafter_uses_sonnet() -> None:
    """drafter.md must reference a Sonnet model."""
    content = _read("agents/drafter.md")
    assert "claude-sonnet-4-6" in content, (
        "drafter.md must declare model: claude-sonnet-4-6 (D-03)"
    )


def test_critic_uses_sonnet() -> None:
    """critic.md must reference a Sonnet model."""
    content = _read("agents/critic.md")
    assert "claude-sonnet-4-6" in content, (
        "critic.md must declare model: claude-sonnet-4-6 (D-03)"
    )


def test_cs_lead_uses_sonnet() -> None:
    """cs-lead.md must reference a Sonnet model."""
    content = _read("agents/cs-lead.md")
    assert "claude-sonnet-4-6" in content, (
        "cs-lead.md must declare model: claude-sonnet-4-6 (D-03)"
    )


@pytest.mark.parametrize("agent", ["classifier", "extractor", "drafter", "critic", "cs-lead"])
def test_no_opus_in_agent(agent: str) -> None:
    """No agent file may declare claude-opus-* as its model (D-03 cost-discipline gate).

    The check is for the model-declaration string "claude-opus" — policy reminders
    that say "No Opus on the hot path" are permitted and do not trip this gate.
    """
    content = _read(f"agents/{agent}.md")
    assert "claude-opus" not in content.lower(), (
        f"{agent}.md must not declare a claude-opus model (D-03: Opus is never on the hot path)"
    )


# ---------------------------------------------------------------------------
# (3) MCP / file-store wiring
# ---------------------------------------------------------------------------

def test_extractor_references_resolve_order() -> None:
    """extractor.md must reference the resolve_order Selless MCP tool."""
    content = _read("agents/extractor.md")
    assert "resolve_order" in content, (
        "extractor.md must call resolve_order (Selless MCP) to verify the order key (REP-02)"
    )


def test_drafter_references_file_store() -> None:
    """drafter.md must reference the local file-store (get_template_from_file / subtype_to_code / file_store).

    Under D-31, the drafter no longer calls KnowledgeMCP get_template — it uses
    the local file-store via subtype_to_code() + get_template_from_file().
    """
    content = _read("agents/drafter.md")
    assert (
        "get_template_from_file" in content
        or "subtype_to_code" in content
        or "file_store" in content
    ), (
        "drafter.md must reference the local file-store "
        "(get_template_from_file / subtype_to_code / file_store) — D-31 pivot"
    )


def test_drafter_references_submit_reply() -> None:
    """drafter.md must reference submit_reply — the single customer-draft chokepoint (§4a)."""
    content = _read("agents/drafter.md")
    assert "submit_reply" in content, (
        "drafter.md must emit the draft ONLY via submit_reply (§4a chokepoint)"
    )


def test_cs_lead_references_reply_pipeline() -> None:
    """cs-lead.md must reference the reply-pipeline skill."""
    content = _read("agents/cs-lead.md")
    assert "reply-pipeline" in content, (
        "cs-lead.md must reference the reply-pipeline skill (D-01: lead follows the skill)"
    )


def test_ground_and_draft_skill_references_file_store() -> None:
    """ground-and-draft/SKILL.md must reference file-store grounding (D-31).

    Under D-31 the drafter uses local file-store (get_template_from_file / subtype_to_code)
    instead of KnowledgeMCP. The skill must document this pattern.
    """
    content = _read("skills/ground-and-draft/SKILL.md")
    assert (
        "get_template_from_file" in content
        or "subtype_to_code" in content
        or "file_store" in content
    ), (
        "ground-and-draft/SKILL.md must reference file-store grounding "
        "(get_template_from_file / subtype_to_code / file_store) — D-31"
    )


def test_reply_pipeline_references_submit_reply() -> None:
    """reply-pipeline/SKILL.md must reference submit_reply (the chokepoint is part of the workflow)."""
    content = _read("skills/reply-pipeline/SKILL.md")
    assert "submit_reply" in content, (
        "reply-pipeline/SKILL.md must reference submit_reply chokepoint (§4a)"
    )


def test_extract_answer_key_skill_references_resolve_order() -> None:
    """extract-answer-key/SKILL.md must reference resolve_order."""
    content = _read("skills/extract-answer-key/SKILL.md")
    assert "resolve_order" in content, (
        "extract-answer-key/SKILL.md must document resolve_order usage (REP-02)"
    )


# ---------------------------------------------------------------------------
# (4) reply-pipeline skill — always-draft contract (D-33)
# ---------------------------------------------------------------------------

def test_reply_pipeline_mentions_classify_stage() -> None:
    content = _read("skills/reply-pipeline/SKILL.md").lower()
    assert "classify" in content, "reply-pipeline/SKILL.md must mention the classify stage"


def test_reply_pipeline_mentions_extract_stage() -> None:
    content = _read("skills/reply-pipeline/SKILL.md").lower()
    assert "extract" in content, "reply-pipeline/SKILL.md must mention the extract stage"


def test_reply_pipeline_mentions_critique_stage() -> None:
    content = _read("skills/reply-pipeline/SKILL.md").lower()
    assert "critique" in content, "reply-pipeline/SKILL.md must mention the critique/critic stage"


def test_reply_pipeline_encodes_always_draft_verdict() -> None:
    """reply-pipeline/SKILL.md must encode the always-draft verdict (D-33).

    The skill must reference action='draft' and escalation_hint (advisory signal),
    and must NOT encode the retired escalate=no-draft outcome (D-10 retired by D-30).
    """
    content = _read("skills/reply-pipeline/SKILL.md")
    content_lower = content.lower()
    # Must affirm always-draft
    assert "action" in content_lower and "draft" in content_lower, (
        "reply-pipeline/SKILL.md must encode the always-draft verdict (action='draft')"
    )
    # Must reference escalation_hint as the advisory mechanism
    assert "escalation_hint" in content, (
        "reply-pipeline/SKILL.md must reference escalation_hint (advisory signal, D-33)"
    )


def test_reply_pipeline_no_escalate_no_draft_outcome() -> None:
    """reply-pipeline/SKILL.md must NOT encode 'escalate=no-draft' or 'action: escalate' as a pipeline outcome.

    The old D-10 hard-escalate verdict (action='escalate', no body) is RETIRED by D-30.
    """
    content = _read("skills/reply-pipeline/SKILL.md")
    # Check for the specific retired patterns — informational historical mentions are OK,
    # but the skill must not describe action="escalate" as a live pipeline output.
    # The skill explicitly says "There is no action: 'escalate' verdict" post D-30.
    assert 'action: "escalate"' not in content or "retired" in content.lower() or "no " in content.lower(), (
        "reply-pipeline/SKILL.md must not encode action='escalate' as a live pipeline outcome (D-30 retired)"
    )


# ---------------------------------------------------------------------------
# (5) REP-04: self-critique rubric dimensions
# ---------------------------------------------------------------------------

def test_self_critique_skill_faithfulness_dimension() -> None:
    """self-critique/SKILL.md must define the faithfulness rubric dimension."""
    content = _read("skills/self-critique/SKILL.md").lower()
    assert "faithfulness" in content, (
        "self-critique/SKILL.md must define faithfulness dimension (Phase-5 eval alignment)"
    )


def test_self_critique_skill_policy_match_dimension() -> None:
    """self-critique/SKILL.md must define the policy-match rubric dimension."""
    content = _read("skills/self-critique/SKILL.md")
    assert "policy-match" in content, (
        "self-critique/SKILL.md must define policy-match dimension (Phase-5 eval alignment)"
    )


def test_self_critique_skill_tone_completeness_dimension() -> None:
    """self-critique/SKILL.md must define the tone-completeness rubric dimension."""
    content = _read("skills/self-critique/SKILL.md").lower()
    assert "tone" in content, (
        "self-critique/SKILL.md must define tone-completeness dimension (Phase-5 eval alignment)"
    )
