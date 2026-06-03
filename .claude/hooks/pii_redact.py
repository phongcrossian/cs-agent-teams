"""
PII redaction hook — D-04 / CLAUDE.md.

Thin wrapper around src.guards.pii.redact_text (Presidio-backed).
This hook NEVER blocks — it only transforms the payload by redacting
PII before any log/trace sink sees it.

Contract:
    pii_redact_hook(text: str) -> str
    - returns redacted version of input text
    - empty/whitespace-only strings returned as-is (no Presidio call, per pii.py)

Hook entry point: main() reads stdin JSON (Claude Code PostToolUse hook contract),
redacts 'body' and 'draft' fields in the payload, prints redacted JSON,
exits 0 — NEVER exits 1 (this hook does not block).
"""

from __future__ import annotations

import json
import sys

from src.guards.pii import redact_text


def pii_redact_hook(text: str) -> str:
    """Wrap redact_text for the hook entry point.

    Called before any log/trace write (D-04 + CLAUDE.md).
    Returns the PII-redacted string; delegates entirely to redact_text.
    """
    return redact_text(text)


def main() -> None:
    """Claude Code hook entry point (PostToolUse).

    Reads stdin JSON, redacts 'body' and 'draft' fields (and any nested
    equivalents), prints the redacted payload as JSON, exits 0.
    This hook NEVER blocks — it transforms only.
    """
    try:
        payload = json.load(sys.stdin)

        # Redact top-level body/draft fields
        if "body" in payload and isinstance(payload["body"], str):
            payload["body"] = redact_text(payload["body"])
        if "draft" in payload and isinstance(payload["draft"], str):
            payload["draft"] = redact_text(payload["draft"])

        # Redact nested tool_input body/draft (PreToolUse context passthrough)
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, dict):
            if "body" in tool_input and isinstance(tool_input["body"], str):
                tool_input["body"] = redact_text(tool_input["body"])
            if "draft" in tool_input and isinstance(tool_input["draft"], str):
                tool_input["draft"] = redact_text(tool_input["draft"])

        # Redact tool_result body (PostToolUse context)
        tool_result = payload.get("tool_result")
        if isinstance(tool_result, dict):
            if "body" in tool_result and isinstance(tool_result["body"], str):
                tool_result["body"] = redact_text(tool_result["body"])

        print(json.dumps(payload))
        sys.exit(0)

    except Exception:  # noqa: BLE001 — pii_redact never blocks; pass through on error
        # On any error, print original payload unmodified (still don't block)
        # This is a transform hook — fail-open is acceptable here (we log, not gate)
        try:
            # Re-read stdin is not possible; emit empty pass-through
            print("{}")
        except Exception:  # noqa: BLE001
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
