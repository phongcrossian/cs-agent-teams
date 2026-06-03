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

Known limitation (D-04 / CR-05): This hook runs as a PostToolUse hook, meaning it
fires *after* the tool has already executed and any logging/tracing that the tool
itself performs may have already occurred. D-04's "before ANY log/trace" guarantee
is therefore NOT fully met by this hook alone. The residual mitigations are:
  1. submit_reply itself redacts at the persistence boundary (src/reply_mcp/server.py
     _dry_run) before writing to any store.
  2. Any downstream trace sink (Langfuse, OpenTelemetry) MUST apply Presidio redaction
     at the sink before persisting spans.
This PostToolUse hook is defense-in-depth for the payload flowing to Claude Code's
own logging, not a substitute for point-of-write redaction.
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

    Error path (CR-05): on any exception, pass the original payload through
    unchanged rather than emitting {} (which would corrupt all fields and lose
    downstream context). If stdin is unparseable, echo raw stdin back unchanged.
    """
    raw_stdin: str = sys.stdin.read()
    payload: dict | None = None
    try:
        payload = json.loads(raw_stdin)

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
        # On any error, pass the original payload through unchanged (no field corruption).
        # If we already parsed the payload before the error, re-serialize it.
        # If stdin was never parseable, echo the raw stdin string back unchanged.
        try:
            if payload is not None:
                print(json.dumps(payload))
            else:
                print(raw_stdin)
        except Exception:  # noqa: BLE001
            print(raw_stdin)
        sys.exit(0)


if __name__ == "__main__":
    main()
