"""
RED stubs asserting the §3 .claude/ manifest files exist.

Fails now (Wave 0 — files not created yet). Turns green by Wave 3 when the
agent definitions, skill indexes, and hook scripts are created.

§3 manifest (from design doc):
    .claude/agents/{cs-lead,classifier,extractor,drafter,critic}.md
    .claude/skills/{reply-pipeline,classify-ticket,extract-answer-key,ground-and-draft,self-critique}/SKILL.md
    .claude/hooks/{injection_screen,pre_send_guard,escalation_gate,grounding_check,pii_redact}.py
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


@pytest.mark.xfail(reason="Agent .md files not yet created — Wave 1/2", strict=True)
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


@pytest.mark.xfail(reason="Skill SKILL.md files not yet created — Wave 2/3", strict=True)
@pytest.mark.parametrize("rel_path", _SKILL_FILES)
def test_skill_file_exists(rel_path: str) -> None:
    """Each skill SKILL.md must exist under .claude/skills/<name>/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing skill index: {path}"


# ---------------------------------------------------------------------------
# Hook scripts
# ---------------------------------------------------------------------------

_HOOK_FILES = [
    "hooks/injection_screen.py",
    "hooks/pre_send_guard.py",
    "hooks/escalation_gate.py",
    "hooks/grounding_check.py",
    "hooks/pii_redact.py",
]


@pytest.mark.parametrize("rel_path", _HOOK_FILES)
def test_hook_file_exists(rel_path: str) -> None:
    """Each hook script must exist under .claude/hooks/."""
    path = _CLAUDE_DIR / rel_path
    assert path.exists(), f"Missing hook script: {path}"
    content = path.read_text()
    # Every hook must have a main() entry point
    assert "def main" in content, f"{path} must define a main() entry point"
    # Every hook must handle sys.stdin (Claude Code hook contract)
    assert "sys.stdin" in content or "stdin" in content, (
        f"{path} must read from sys.stdin (Claude Code hook contract)"
    )
