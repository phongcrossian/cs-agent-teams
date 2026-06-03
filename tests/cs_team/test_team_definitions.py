"""
Team-definition test suite — structure, model discipline, and MCP wiring.

Asserts:
  (1) All five agent files and all five SKILL.md files from the §3 design manifest exist
  (2) MODEL DISCIPLINE — classifier/extractor reference Haiku; drafter/critic reference Sonnet;
      NO agent file contains the substring "opus" (case-insensitive) — cost-discipline gate
  (3) WIRING — extractor→resolve_order, drafter→get_template+submit_reply (chokepoint §4a),
      cs-lead→reply-pipeline skill, ground-and-draft→get_template, reply-pipeline→submit_reply
  (4) reply-pipeline skill mentions all stage names and the escalate verdict
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
# (2) Model discipline — Haiku / Sonnet / no Opus
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
    """No agent file may reference an Opus model (D-03 cost-discipline gate)."""
    content = _read(f"agents/{agent}.md")
    assert "opus" not in content.lower(), (
        f"{agent}.md must not reference an Opus model (D-03: Opus is never on the hot path)"
    )


# ---------------------------------------------------------------------------
# (3) MCP wiring
# ---------------------------------------------------------------------------

def test_extractor_references_resolve_order() -> None:
    """extractor.md must reference the resolve_order Selless MCP tool."""
    content = _read("agents/extractor.md")
    assert "resolve_order" in content, (
        "extractor.md must call resolve_order (Selless MCP) to verify the order key (REP-02)"
    )


def test_drafter_references_get_template() -> None:
    """drafter.md must reference get_template (Knowledge MCP)."""
    content = _read("agents/drafter.md")
    assert "get_template" in content, (
        "drafter.md must call get_template (Knowledge MCP) — templates fetched at runtime (REP-03)"
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


def test_ground_and_draft_skill_references_get_template() -> None:
    """ground-and-draft/SKILL.md must reference get_template (templates centralized in Knowledge MCP)."""
    content = _read("skills/ground-and-draft/SKILL.md")
    assert "get_template" in content, (
        "ground-and-draft/SKILL.md must document get_template usage (templates in Knowledge MCP)"
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
# (4) reply-pipeline skill — stage names + verdict
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


def test_reply_pipeline_mentions_escalate_verdict() -> None:
    content = _read("skills/reply-pipeline/SKILL.md").lower()
    assert "escalate" in content, "reply-pipeline/SKILL.md must encode the escalate verdict"


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
