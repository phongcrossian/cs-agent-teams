"""
Structural assertion: ALL FIVE hooks are bound in .claude/settings.json with §4a events.

This test runs NOW (Wave 0) and stays green throughout all waves.
It is the enforcement gate ensuring the §4a non-bypassable chokepoint design is not
accidentally broken by future edits to settings.json.

§4a binding requirements:
  1. PreToolUse matched to "submit_reply" → ordered list of THREE hooks:
       [0] grounding_check.py  (grounding enforcement, D-11)
       [1] pre_send_guard.py   (commitment language block, D-13)
       [2] escalation_gate.py  (final accumulated risk check — the hard gate)
     Any of these returning non-zero (exit 2) blocks submit_reply → escalate verdict (D-10).

  2. UserPromptSubmit → injection_screen.py on inbound body (D-14).

  3. PostToolUse (broad) → escalation_gate.py (same script, accumulates risk signals early;
     also pii_redact.py before any log/trace sink).

  4. SubagentStop → escalation_gate.py (same script, risk accumulation on subagent results).

  5. pii_redact.py → PostToolUse (broad matcher).

  Note: escalation_gate.py is bound in TWO contexts — it is NOT a 6th script.
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


def test_three_mcp_servers_registered(settings: dict) -> None:
    """settings.json must register KnowledgeMCP, SellessMCP, and ReplyMCP."""
    mcp_servers = settings.get("mcpServers", {})
    required = {"KnowledgeMCP", "SellessMCP", "ReplyMCP"}
    missing = required - set(mcp_servers.keys())
    assert not missing, f"Missing MCP server registrations: {missing}"


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
# Hook 1: PreToolUse(submit_reply) — ordered chain
# ---------------------------------------------------------------------------


def test_pre_tool_use_submit_reply_binding_exists(settings: dict) -> None:
    """PreToolUse section must contain a binding with matcher 'submit_reply'."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    matchers = [b.get("matcher", "") for b in pre_tool_use]
    assert "submit_reply" in matchers, (
        f"No PreToolUse binding with matcher='submit_reply' found; matchers: {matchers}"
    )


def test_pre_tool_use_submit_reply_has_three_hooks(settings: dict) -> None:
    """PreToolUse(submit_reply) must have exactly 3 hooks in order."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    submit_binding = next(
        (b for b in pre_tool_use if b.get("matcher") == "submit_reply"), None
    )
    assert submit_binding is not None, "No PreToolUse binding for submit_reply"
    hooks = submit_binding.get("hooks", [])
    assert len(hooks) == 3, (
        f"PreToolUse(submit_reply) must have exactly 3 hooks; got {len(hooks)}: {hooks}"
    )


def test_pre_tool_use_submit_reply_order_grounding_first(settings: dict) -> None:
    """PreToolUse(submit_reply) hook[0] must be grounding_check.py."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    submit_binding = next(b for b in pre_tool_use if b.get("matcher") == "submit_reply")
    hooks = submit_binding["hooks"]
    cmd0 = hooks[0].get("command", "")
    assert "grounding_check.py" in cmd0, (
        f"PreToolUse(submit_reply)[0] must be grounding_check.py; got: {cmd0}"
    )


def test_pre_tool_use_submit_reply_order_pre_send_guard_second(settings: dict) -> None:
    """PreToolUse(submit_reply) hook[1] must be pre_send_guard.py."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    submit_binding = next(b for b in pre_tool_use if b.get("matcher") == "submit_reply")
    hooks = submit_binding["hooks"]
    cmd1 = hooks[1].get("command", "")
    assert "pre_send_guard.py" in cmd1, (
        f"PreToolUse(submit_reply)[1] must be pre_send_guard.py; got: {cmd1}"
    )


def test_pre_tool_use_submit_reply_order_escalation_gate_third(settings: dict) -> None:
    """PreToolUse(submit_reply) hook[2] must be escalation_gate.py (final risk check)."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    submit_binding = next(b for b in pre_tool_use if b.get("matcher") == "submit_reply")
    hooks = submit_binding["hooks"]
    cmd2 = hooks[2].get("command", "")
    assert "escalation_gate.py" in cmd2, (
        f"PreToolUse(submit_reply)[2] must be escalation_gate.py (final-risk); got: {cmd2}"
    )


# ---------------------------------------------------------------------------
# Hook 2: UserPromptSubmit → injection_screen.py
# ---------------------------------------------------------------------------


def test_user_prompt_submit_has_injection_screen(settings: dict) -> None:
    """UserPromptSubmit must bind injection_screen.py."""
    user_prompt_submit = _collect_hooks_for_event(settings, "UserPromptSubmit")
    all_cmds = _all_hook_commands(user_prompt_submit)
    assert any("injection_screen.py" in cmd for cmd in all_cmds), (
        f"injection_screen.py not found in UserPromptSubmit hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Hook 3: PostToolUse → escalation_gate.py (early-exit risk accumulation)
# ---------------------------------------------------------------------------


def test_post_tool_use_has_escalation_gate(settings: dict) -> None:
    """PostToolUse must bind escalation_gate.py (same script as submit_reply final-risk)."""
    post_tool_use = _collect_hooks_for_event(settings, "PostToolUse")
    all_cmds = _all_hook_commands(post_tool_use)
    assert any("escalation_gate.py" in cmd for cmd in all_cmds), (
        f"escalation_gate.py not found in PostToolUse hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Hook 4: SubagentStop → escalation_gate.py
# ---------------------------------------------------------------------------


def test_subagent_stop_has_escalation_gate(settings: dict) -> None:
    """SubagentStop must bind escalation_gate.py."""
    subagent_stop = _collect_hooks_for_event(settings, "SubagentStop")
    all_cmds = _all_hook_commands(subagent_stop)
    assert any("escalation_gate.py" in cmd for cmd in all_cmds), (
        f"escalation_gate.py not found in SubagentStop hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Hook 5: PostToolUse → pii_redact.py
# ---------------------------------------------------------------------------


def test_post_tool_use_has_pii_redact(settings: dict) -> None:
    """PostToolUse must bind pii_redact.py (before any log/trace sink)."""
    post_tool_use = _collect_hooks_for_event(settings, "PostToolUse")
    all_cmds = _all_hook_commands(post_tool_use)
    assert any("pii_redact.py" in cmd for cmd in all_cmds), (
        f"pii_redact.py not found in PostToolUse hooks; commands: {all_cmds}"
    )


# ---------------------------------------------------------------------------
# Cross-check: escalation_gate.py appears in BOTH contexts (no 6th script)
# ---------------------------------------------------------------------------


def test_escalation_gate_bound_in_two_contexts(settings: dict) -> None:
    """escalation_gate.py must be bound in BOTH the PreToolUse(submit_reply) chain AND
    PostToolUse/SubagentStop — same script, two contexts (no 6th hook script)."""
    pre_tool_use = _collect_hooks_for_event(settings, "PreToolUse")
    submit_binding = next(
        (b for b in pre_tool_use if b.get("matcher") == "submit_reply"), None
    )
    assert submit_binding is not None
    submit_cmds = [h.get("command", "") for h in submit_binding.get("hooks", [])]
    assert any("escalation_gate.py" in cmd for cmd in submit_cmds), (
        "escalation_gate.py missing from PreToolUse(submit_reply) chain"
    )

    post_tool_use = _collect_hooks_for_event(settings, "PostToolUse")
    subagent_stop = _collect_hooks_for_event(settings, "SubagentStop")
    post_cmds = _all_hook_commands(post_tool_use) + _all_hook_commands(subagent_stop)
    assert any("escalation_gate.py" in cmd for cmd in post_cmds), (
        "escalation_gate.py missing from PostToolUse/SubagentStop (second binding context)"
    )


# ---------------------------------------------------------------------------
# Overall completeness snapshot
# ---------------------------------------------------------------------------


def test_all_five_hook_scripts_referenced_in_settings(settings: dict) -> None:
    """All five hook scripts must appear somewhere in settings.json."""
    settings_str = json.dumps(settings)
    required_scripts = [
        "grounding_check.py",
        "pre_send_guard.py",
        "escalation_gate.py",
        "injection_screen.py",
        "pii_redact.py",
    ]
    missing = [s for s in required_scripts if s not in settings_str]
    assert not missing, f"Hook scripts missing from settings.json: {missing}"
