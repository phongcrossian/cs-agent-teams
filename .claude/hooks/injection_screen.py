"""
Prompt injection screen — SAFE-04 / D-14.

Deterministic (no LLM). Screens inbound email body for instruction-override
attempts before any agent processes it.

Contract (mirrors src/guards/loop_guard.should_suppress):
    screen_for_injection(body: str) -> tuple[bool, str]
    - bool: True = injection suspected → escalate
    - str: reason label (e.g. "injection:ignore_instructions"); "" when clean

Hook entry point: main() reads stdin JSON (Claude Code hook contract),
calls screen_for_injection, exits 1 (block) on suspicion, 0 (pass) when clean.
Fail-closed: malformed stdin → escalate.
"""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Module-level compiled injection patterns (mirrors loop_guard._NO_REPLY_PATTERN)
# Seeded from promptfoo red-team patterns (D-14, CLAUDE.md).
# Conservative: escalate on any match.
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # "ignore/disregard previous/prior/all instructions/directives/guidelines"
    (
        re.compile(
            r"\b(ignore|disregard|forget|skip|override)\s+(all\s+)?"
            r"(previous|prior|earlier|above|your)\s+(instructions?|directives?|guidelines?|rules?|prompts?|context)",
            re.IGNORECASE,
        ),
        "ignore_instructions",
    ),
    # "ignore the system prompt" / "disregard the system prompt"
    (
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass|reveal|show|print|output|dump)\s+"
            r"(the\s+)?(system\s+prompt|system\s+message|system\s+context|safety\s+rules?|safety\s+instructions?)",
            re.IGNORECASE,
        ),
        "system_prompt_override",
    ),
    # "you are now [a/an] <different persona>" / role-override patterns
    (
        re.compile(
            r"\byou\s+are\s+now\s+(an?\s+)?(unrestricted|uncensored|unfiltered|jailbroken|"
            r"different|new|alternative|evil|free|helpful\s+assistant)",
            re.IGNORECASE,
        ),
        "role_override",
    ),
    # "act as [a/an] <unrestricted>" / "pretend you are"
    (
        re.compile(
            r"\b(act\s+as|pretend\s+(you\s+are|to\s+be)|roleplay\s+as|simulate\s+being)\s+"
            r"(an?\s+)?(unrestricted|uncensored|unfiltered|jailbroken|different|evil|free)",
            re.IGNORECASE,
        ),
        "persona_override",
    ),
    # Fenced tool-call / function-call injection mimicry: <tool_call>, [TOOL_CALL], ```tool
    (
        re.compile(
            r"(<tool_call>|\[TOOL_CALL\]|```\s*tool|<function_call>|\[FUNCTION_CALL\]|"
            r"<system>|\[SYSTEM\])",
            re.IGNORECASE,
        ),
        "tool_call_injection",
    ),
    # "reveal your system prompt" / "show me your instructions" / "what are your instructions"
    (
        re.compile(
            r"\b(reveal|show|print|output|dump|tell\s+me|what\s+are)\s+"
            r"(your\s+)?(system\s+prompt|instructions?|directives?|guidelines?|rules?|training|context)",
            re.IGNORECASE,
        ),
        "prompt_extraction",
    ),
    # "this is a test by the (system administrator|developer|operator)"
    (
        re.compile(
            r"\bthis\s+is\s+a\s+test\s+by\s+the\s+(system\s+administrator|developer|operator|security\s+team)",
            re.IGNORECASE,
        ),
        "false_authority",
    ),
    # "new instructions:" / "updated instructions:" / "SYSTEM:" at start of line
    (
        re.compile(
            r"(^|\n)\s*(new\s+instructions?|updated\s+instructions?|revised\s+instructions?|"
            r"SYSTEM\s*:|ADMIN\s*:|OPERATOR\s*:)\s*",
            re.IGNORECASE,
        ),
        "injected_instructions",
    ),
]


def screen_for_injection(body: str) -> tuple[bool, str]:
    """Return (suspicious: bool, reason: str).

    reason is empty string when suspicious=False.
    Patterns applied in order; first match wins (mirrors should_suppress layer logic).
    """
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(body):
            return True, f"injection:{label}"
    return False, ""


def _extract_body(payload: dict) -> str:
    """Extract the email body from the hook payload.

    Claude Code UserPromptSubmit payloads carry the user message in 'prompt'.
    Downstream callers may pass raw body in 'body'. Support both.
    """
    # UserPromptSubmit schema: {"prompt": "...", ...}
    if "prompt" in payload:
        return str(payload["prompt"])
    # Fallback: explicit body field
    if "body" in payload:
        return str(payload["body"])
    return ""


def main() -> None:
    """Claude Code hook entry point.

    Reads stdin JSON, screens the email body for injection attempts.
    Exits 1 (block/escalate) if suspicious, 0 (pass) if clean.
    Fail-closed: any parse/runtime error → escalate.
    """
    try:
        payload = json.load(sys.stdin)
        body = _extract_body(payload)
        suspicious, reason = screen_for_injection(body)
        if suspicious:
            print(json.dumps({"action": "escalate", "reason": reason}))
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"injection_screen:error:{exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
