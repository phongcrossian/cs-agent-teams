"""
Structural assertions for the §3 .claude/ manifest files.

Asserts the agent definitions, skill indexes, and hook scripts
that comprise the always-draft cs-agent-team kit (post 04-01 pivot).

§3 manifest (always-draft):
    .claude/agents/{cs-lead,classifier,extractor,drafter,critic}.md
    .claude/skills/{reply-pipeline,classify-ticket,extract-answer-key,ground-and-draft,self-critique}/SKILL.md
    .claude/hooks/{injection_screen,pii_redact}.py   ← only the two surviving hooks

The four deleted guard hooks (pre_send_guard, escalation_gate, grounding_check,
authorized_offer) were removed in 04-01 and must NOT be asserted here.
"""

from __future__ import annotations

import pathlib

import pytest

# Root of the repo (two levels up from tests/cs_team/)
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_CLAUDE_DIR = _REPO_ROOT / ".claude"


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

_AGENT_FILES = [
    "agents/cs-lead.md",
    "agents/classifier.md",
    "agents/extractor.md",
    "agents/drafter.md",
    "agents/critic.md",
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


# ---------------------------------------------------------------------------
# Skill indexes
# ---------------------------------------------------------------------------

_SKILL_FILES = [
    "skills/reply-pipeline/SKILL.md",
    "skills/classify-ticket/SKILL.md",
    "skills/extract-answer-key/SKILL.md",
    "skills/ground-and-draft/SKILL.md",
    "skills/self-critique/SKILL.md",
]


@pytest.mark.parametrize("rel_path", _SKILL_FILES)
def test_skill_file_exists(rel_path: str) -> None:
    """Each skill SKILL.md must exist under .claude/skills/<name>/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing skill index: {path}"


# ---------------------------------------------------------------------------
# Hook scripts — only the two surviving hooks after 04-01
# ---------------------------------------------------------------------------

_HOOK_FILES = [
    "hooks/injection_screen.py",   # D-14 — injection screening (UserPromptSubmit)
    "hooks/pii_redact.py",         # D-04 — PII redaction (PostToolUse)
]


@pytest.mark.parametrize("rel_path", _HOOK_FILES)
def test_hook_file_exists(rel_path: str) -> None:
    """Each surviving hook script must exist under .claude/hooks/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing hook script: {path}"
    content = path.read_text()
    # Every hook must have a main() entry point
    assert "def main" in content, f"{path} must define a main() entry point"
    # Every hook must handle sys.stdin (Claude Code hook contract)
    assert "sys.stdin" in content or "stdin" in content, (
        f"{path} must read from sys.stdin (Claude Code hook contract)"
    )


def test_deleted_hook_files_absent() -> None:
    """The four guard hooks deleted in 04-01 must NOT exist on disk."""
    hooks_dir = _CLAUDE_DIR / "hooks"
    for name in [
        "pre_send_guard.py",
        "escalation_gate.py",
        "grounding_check.py",
        "authorized_offer.py",
    ]:
        assert not (hooks_dir / name).exists(), (
            f".claude/hooks/{name} must be absent after 04-01 guard deletion"
        )
