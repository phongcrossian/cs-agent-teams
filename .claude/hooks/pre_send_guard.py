"""
Pre-send commitment language guard — SAFE-04 / D-13.

Deterministic (no LLM). Blocks any customer draft that contains commitment
language (refund, credit, charge, order-change) before submit_reply executes.

Design rule (D-13): NEVER auto-strip and send. Always escalate on match.
The hook BLOCKS the draft entirely; the human CS agent decides.

Contract (mirrors src/guards/loop_guard.should_suppress):
    check_commitment_language(draft: str) -> tuple[bool, str]
    - bool: True = commitment language found → block + escalate
    - str: reason label (e.g. "commitment:refund"); "" when clean

Hook entry point: main() reads stdin JSON (Claude Code PreToolUse hook contract
for submit_reply), calls check_commitment_language, exits 1 (block) on match,
0 (pass) when clean.
Fail-closed: malformed stdin → escalate.
"""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Module-level compiled commitment-language patterns (PATTERNS.md lines 110-124).
# Word-boundary anchors limit false positives while keeping conservative posture.
# ---------------------------------------------------------------------------

_COMMITMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Refund / reimburse commitments
    (
        re.compile(r"\b(refund|reimburse|reimbursement)\b", re.IGNORECASE),
        "commitment:refund",
    ),
    # Credit / coupon / voucher offers
    (
        re.compile(r"\b(credit|coupon|voucher|store\s+credit|gift\s+card)\b", re.IGNORECASE),
        "commitment:credit",
    ),
    # Charge / debit / payment language
    (
        re.compile(r"\b(charge|debit|payment|invoice|bill)\b", re.IGNORECASE),
        "commitment:charge",
    ),
    # Replace / exchange / swap / order-change commitments
    (
        re.compile(r"\b(replace|replacement|exchange|swap|reship|re-ship|resend|re-send)\b", re.IGNORECASE),
        "commitment:order_change",
    ),
]


def check_commitment_language(draft: str) -> tuple[bool, str]:
    """Return (has_commitment: bool, reason: str).

    Deterministic — never strips and sends; always escalates on match (D-13).
    Patterns applied in order; first match wins.
    """
    for pattern, label in _COMMITMENT_PATTERNS:
        if pattern.search(draft):
            return True, label
    return False, ""


def _extract_draft(payload: dict) -> str:
    """Extract the draft body from the hook payload.

    PreToolUse(submit_reply) payload carries tool inputs.
    Claude Code passes tool call arguments; the submit_reply tool accepts 'body'.
    """
    # Claude Code PreToolUse: {"tool_name": "submit_reply", "tool_input": {"body": "...", ...}}
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, dict) and "body" in tool_input:
        return str(tool_input["body"])
    # Fallback: direct body field (test/standalone invocation)
    if "body" in payload:
        return str(payload["body"])
    # Fallback: draft field
    if "draft" in payload:
        return str(payload["draft"])
    return ""


def main() -> None:
    """Claude Code hook entry point (PreToolUse on submit_reply).

    Reads stdin JSON, checks draft body for commitment language.
    Exits 1 (block/escalate) if found, 0 (pass) when clean.
    Fail-closed: any parse/runtime error → escalate.
    """
    try:
        payload = json.load(sys.stdin)
        draft = _extract_draft(payload)
        blocked, reason = check_commitment_language(draft)
        if blocked:
            print(json.dumps({"action": "escalate", "reason": reason}))
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"pre_send_guard:error:{exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
