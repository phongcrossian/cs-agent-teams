"""
Structural assertion: the two surviving hooks are bound in .claude/settings.json
after the 04-01 guard deletion and D-31/D-32 pivot.

Always-draft two-hook wiring (post 04-01):
  1. UserPromptSubmit → injection_screen.py (D-14, injection screening)
  2. PostToolUse → pii_redact.py (D-04, PII redaction before log/trace)

What was REMOVED in 04-01 (must NOT be asserted or present):
  - PreToolUse(submit_reply) chain: grounding_check → pre_send_guard → escalation_gate
  - SubagentStop → escalation_gate
  - KnowledgeMCP in mcpServers (removed per D-31)

This test is the enforcement gate ensuring the always-draft two-hook wiring is not
accidentally re-broken by future edits to settings.json.
"""

from __future__ import annotations

import json
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SETTINGS_PATH = _REPO_ROOT / ".claude" / "settings.json"


@pytest.fixture(scope="module")
def settings() -> dict:
    """Load and parse .claude/settings.json once per test module."""
    assert _SETTINGS_PATH.exists(), f".claude/settings.json not found at {_SETTINGS_PATH}"
    with _SETTINGS_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# MCP server registrations
# ---------------------------------------------------------------------------


def test_selless_mcp_registered(settings: dict) -> None:
    """SellessMCP must be registered in mcpServers (stays per D-29)."""
    mcp_servers = settings.get("mcpServers", {})
    assert "SellessMCP" in mcp_servers, "SellessMCP must remain in mcpServers"


def test_reply_mcp_registered(settings: dict) -> None:
    """ReplyMCP must be registered in mcpServers."""
    mcp_servers = settings.get("mcpServers", {})
    assert "ReplyMCP" in mcp_servers, "ReplyMCP must remain in mcpServers"


def test_knowledge_mcp_removed(settings: dict) -> None:
    """KnowledgeMCP must NOT be in mcpServers (removed per D-31 file-store pivot)."""
    mcp_servers = settings.get("mcpServers", {})
    assert "KnowledgeMCP" not in mcp_servers, (
        "KnowledgeMCP must not appear in mcpServers after the D-31 always-draft pivot"
    )

def test_reply_mcp_uses_src_reply_mcp_server(settings: dict) -> None:
    """ReplyMCP launch command must reference src.reply_mcp.server."""
    args = settings["mcpServers"]["ReplyMCP"].get("args", [])
    assert "src.reply_mcp.server" in args, (
        f"ReplyMCP args must include 'src.reply_mcp.server'; got: {args}"
    )


# ---------------------------------------------------------------------------
# Hook binding helpers
# ---------------------------------------------------------------------------


def _collect_hooks_for_event(settings: dict, event: str) -> list[dict]:
    """Return all hook binding entries for a given event key."""
    return settings.get("hooks", {}).get(event, [])


def _all_hook_commands(bindings: list[dict]) -> list[str]:
    """Flatten all hook command strings from a list of binding entries."""
    commands: list[str] = []
    for binding in bindings:
        for hook in binding.get("hooks", []):
            cmd = hook.get("command", "")
            if cmd:
                commands.append(cmd)
    return commands


# ---------------------------------------------------------------------------
# Hook 1: UserPromptSubmit → injection_screen.py (D-14)
# ---------------------------------------------------------------------------


def test_user_prompt_submit_has_injection_screen(settings: dict) -> None:
    """UserPromptSubmit must bind injection_screen.py (D-14 — surviving safety floor)."""
    user_prompt_submit = _collect_hooks_for_event(settings, "UserPromptSubmit")
    all_cmds = _all_hook_commands(user_prompt_submit)
    assert any("injection_screen.py" in cmd for cmd in all_cmds), (
        f"injection_screen.py not found in UserPromptSubmit hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Hook 2: PostToolUse → pii_redact.py (D-04)
# ---------------------------------------------------------------------------


def test_post_tool_use_has_pii_redact(settings: dict) -> None:
    """PostToolUse must bind pii_redact.py (D-04 — PII redaction before any log/trace)."""
    post_tool_use = _collect_hooks_for_event(settings, "PostToolUse")
    all_cmds = _all_hook_commands(post_tool_use)
    assert any("pii_redact.py" in cmd for cmd in all_cmds), (
        f"pii_redact.py not found in PostToolUse hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Deleted bindings: must NOT be present after 04-01
# ---------------------------------------------------------------------------


def test_no_pre_tool_use_submit_reply_binding(settings: dict) -> None:
    """PreToolUse must NOT have a matcher='submit_reply' binding (guard chain deleted in 04-01)."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    matchers = [b.get("matcher", "") for b in pre_tool_use]
    assert "submit_reply" not in matchers, (
        f"PreToolUse(submit_reply) chain must be absent after 04-01; matchers: {matchers}"
    )


def test_no_subagent_stop_binding(settings: dict) -> None:
    """SubagentStop must NOT be bound (escalation_gate deleted in 04-01)."""
    subagent_stop = _collect_hooks_for_event(settings, "SubagentStop")
    assert len(subagent_stop) == 0, (
        f"SubagentStop must be empty after 04-01; got: {subagent_stop}"
    )


# ---------------------------------------------------------------------------
# Completeness: only the two surviving scripts referenced
# ---------------------------------------------------------------------------


def test_injection_screen_referenced_in_settings(settings: dict) -> None:
    """injection_screen.py must appear somewhere in settings.json."""
    assert "injection_screen.py" in json.dumps(settings), (
        "injection_screen.py must be referenced in settings.json"
    )


def test_pii_redact_referenced_in_settings(settings: dict) -> None:
    """pii_redact.py must appear somewhere in settings.json."""
    assert "pii_redact.py" in json.dumps(settings), (
        "pii_redact.py must be referenced in settings.json"
    )


def test_deleted_hooks_not_in_settings(settings: dict) -> None:
    """Deleted guard hook scripts must NOT appear in settings.json."""
    s = json.dumps(settings)
    for deleted in ["grounding_check.py", "pre_send_guard.py", "escalation_gate.py"]:
        assert deleted not in s, (
            f"Deleted hook {deleted!r} must not appear in settings.json after 04-01"
        )


# ---------------------------------------------------------------------------
# DRY_RUN env
# ---------------------------------------------------------------------------


def test_dry_run_env_in_settings(settings: dict) -> None:
    """settings.json env must set SEND_MODE=dry_run."""
    env = settings.get("env", {})
    assert env.get("SEND_MODE") == "dry_run", (
        f"Expected SEND_MODE=dry_run in settings.json env; got {env.get('SEND_MODE')!r}"
    )
