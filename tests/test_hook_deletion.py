"""
test_hook_deletion.py — D-32 deletion-assertion test (plan 04-01).

Asserts:
  (a) The four retired guard hook files do not exist on disk.
  (b) settings.json parses as valid JSON and its serialised text contains
      neither the four deleted filenames nor 'submit_reply' in any
      PreToolUse matcher.
  (c) settings.json still references injection_screen.py and pii_redact.py
      (the surviving safety floor: D-14 + D-04).

These checks gate that only the two surviving hooks remain wired.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude" / "hooks"
_SETTINGS = _REPO_ROOT / ".claude" / "settings.json"

# ---------------------------------------------------------------------------
# (a) Deleted hook files must not exist
# ---------------------------------------------------------------------------

_DELETED_HOOK_FILES = [
    "pre_send_guard.py",
    "escalation_gate.py",
    "grounding_check.py",
    "authorized_offer.py",
]


@pytest.mark.parametrize("filename", _DELETED_HOOK_FILES)
def test_deleted_hook_file_absent(filename: str) -> None:
    """Each retired guard hook file must not exist (D-32)."""
    path = _HOOKS_DIR / filename
    assert not path.exists(), (
        f"Retired guard hook still present on disk: {path}\n"
        "D-32 requires it to be deleted. Run: git rm .claude/hooks/" + filename
    )


# ---------------------------------------------------------------------------
# (b) settings.json must parse as JSON and must not reference deleted hooks
# ---------------------------------------------------------------------------

_DELETED_HOOK_NAMES = [
    "pre_send_guard",
    "escalation_gate",
    "grounding_check",
    "authorized_offer",
]


@pytest.fixture(scope="module")
def settings_text() -> str:
    assert _SETTINGS.exists(), f"settings.json not found at {_SETTINGS}"
    return _SETTINGS.read_text()


@pytest.fixture(scope="module")
def settings_json(settings_text: str) -> dict:
    try:
        return json.loads(settings_text)
    except json.JSONDecodeError as exc:
        pytest.fail(f"settings.json is not valid JSON: {exc}")


def test_settings_json_parses(settings_json: dict) -> None:
    """settings.json must be valid JSON."""
    assert isinstance(settings_json, dict), "settings.json must be a JSON object"


@pytest.mark.parametrize("hook_name", _DELETED_HOOK_NAMES)
def test_deleted_hook_not_in_settings(settings_text: str, hook_name: str) -> None:
    """Each deleted hook name must not appear anywhere in settings.json text."""
    assert hook_name not in settings_text, (
        f"Deleted hook '{hook_name}' still referenced in .claude/settings.json.\n"
        "Remove all its wiring entries (PreToolUse, PostToolUse, SubagentStop)."
    )


def test_submit_reply_not_in_pretooluse(settings_json: dict) -> None:
    """The PreToolUse submit_reply chain must no longer exist (deleted by D-32)."""
    hooks = settings_json.get("hooks", {})
    pretooluse_entries = hooks.get("PreToolUse", [])
    submit_reply_matchers = [
        entry for entry in pretooluse_entries
        if entry.get("matcher") == "submit_reply"
    ]
    assert len(submit_reply_matchers) == 0, (
        "PreToolUse still has a 'submit_reply' matcher — the deleted guard chain "
        "must be removed from settings.json (D-32)."
    )


def test_cs_run_id_not_in_settings(settings_text: str) -> None:
    """CS_RUN_ID must be removed from settings.json env block (it existed only
    as escalation_gate's stateful veto state-file pointer)."""
    assert "CS_RUN_ID" not in settings_text, (
        "CS_RUN_ID still present in .claude/settings.json.\n"
        "Remove it from the 'env' block — escalation_gate (which read it) is deleted."
    )


# ---------------------------------------------------------------------------
# (c) Surviving hooks must still be wired in settings.json
# ---------------------------------------------------------------------------

_SURVIVING_HOOKS = [
    "injection_screen",
    "pii_redact",
]


@pytest.mark.parametrize("hook_name", _SURVIVING_HOOKS)
def test_surviving_hook_still_wired(settings_text: str, hook_name: str) -> None:
    """The surviving safety-floor hooks (D-14 injection + D-04 PII) must
    remain referenced in settings.json."""
    assert hook_name in settings_text, (
        f"Surviving hook '{hook_name}' is missing from .claude/settings.json.\n"
        "This hook is part of the mandatory safety floor and must remain wired."
    )


def test_injection_screen_in_userpromptsubmit(settings_json: dict) -> None:
    """injection_screen.py must be bound under UserPromptSubmit in settings.json."""
    hooks = settings_json.get("hooks", {})
    ups_entries = hooks.get("UserPromptSubmit", [])
    commands = [
        hook.get("command", "")
        for entry in ups_entries
        for hook in entry.get("hooks", [])
    ]
    assert any("injection_screen" in cmd for cmd in commands), (
        "injection_screen.py is not wired under UserPromptSubmit in settings.json.\n"
        "D-14 requires it to screen every user prompt."
    )


def test_pii_redact_in_posttooluse(settings_json: dict) -> None:
    """pii_redact.py must be bound under PostToolUse in settings.json."""
    hooks = settings_json.get("hooks", {})
    ptu_entries = hooks.get("PostToolUse", [])
    commands = [
        hook.get("command", "")
        for entry in ptu_entries
        for hook in entry.get("hooks", [])
    ]
    assert any("pii_redact" in cmd for cmd in commands), (
        "pii_redact.py is not wired under PostToolUse in settings.json.\n"
        "D-04 requires PII redaction to run after every tool call."
    )
