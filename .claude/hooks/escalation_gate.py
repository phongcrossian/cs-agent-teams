"""
Escalation gate — SAFE-03 / D-08 / D-09.

Deterministic (no LLM). OR-gate over risk signals: ANY single True signal
forces escalation (fail-closed, additive per D-08).

This SAME script serves TWO invocation contexts (design §4a — no 6th script):
  1. PostToolUse / SubagentStop (early-exit / accumulation context):
     Reads classifier/extractor stage result fields from the payload,
     derives signals, records/accumulates risk. Exits 1 to signal escalation.
  2. PreToolUse @ submit_reply (final-risk veto context):
     Re-reads accumulated risk state from the lead's context payload,
     and BLOCKS (exit 2) if any signal is set — the hard gate.

Contract (mirrors src/guards/loop_guard.should_suppress):
    should_escalate(signals: dict) -> tuple[bool, str]
    - bool: True = escalate
    - str: reason label (e.g. "escalate:kb_conflict"); "" when no signal

Fail-closed: malformed stdin → escalate.

Override-resolved conflicts (D-09):
    When the Knowledge MCP resolves a conflict via override_resolution,
    the upstream stage clears conflict=False BEFORE emitting the verdict.
    A resolved conflict does NOT false-escalate here — the source of truth
    is the signals dict, not a raw conflict flag from the MCP.
"""

from __future__ import annotations

import json
import sys

# Signal key order: first match wins (mirrors should_suppress layer order)
_SIGNAL_ORDER: list[tuple[str, str]] = [
    ("low_confidence",      "escalate:low_confidence"),
    ("high_risk_category",  "escalate:high_risk_category"),
    ("conflict",            "escalate:kb_conflict"),
    ("stale_only",          "escalate:stale_only"),
    ("missing_key",         "escalate:missing_key"),
]


def should_escalate(signals: dict) -> tuple[bool, str]:
    """Return (escalate: bool, reason: str).

    ANY signal triggers escalation — fail-closed, additive (D-08).
    First signal in _SIGNAL_ORDER wins when multiple are True.
    Override-resolved conflicts appear as conflict=False — not escalated (D-09).
    """
    for key, reason in _SIGNAL_ORDER:
        if signals.get(key):
            return True, reason
    return False, ""


def _derive_signals(payload: dict) -> dict:
    """Extract risk signals from the hook payload.

    Supports two invocation contexts:

    Context 1 — PostToolUse/SubagentStop (stage result):
      Payload may carry stage-specific fields at the top level or under
      'tool_result' / 'result' / 'output'. Extract standard signal keys.

    Context 2 — PreToolUse@submit_reply (final-risk veto):
      The lead passes accumulated risk state; signals may be nested under
      'risk_signals', 'escalation_signals', or 'signals'.

    Falls back to scanning top-level bool fields matching signal names.
    """
    # Explicit signals dict (either context)
    for key in ("signals", "risk_signals", "escalation_signals"):
        if isinstance(payload.get(key), dict):
            return payload[key]

    # Stage result context: signals embedded in tool_result / result
    for key in ("tool_result", "result", "output"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            for sig_key in ("signals", "risk_signals", "escalation_signals"):
                if isinstance(nested.get(sig_key), dict):
                    return nested[sig_key]

    # Final fallback: scan top-level for known signal keys
    known_keys = {k for k, _ in _SIGNAL_ORDER}
    signals = {k: bool(payload.get(k, False)) for k in known_keys if k in payload}
    return signals


def main() -> None:
    """Claude Code hook entry point.

    Serves both PostToolUse/SubagentStop (early-exit, exit 1 on escalate)
    and PreToolUse@submit_reply (final-risk veto, exit 2 to BLOCK).

    Determines context from payload shape:
    - PreToolUse with tool_name == "submit_reply" → exit 2 (hard block)
    - Otherwise → exit 1 (escalation signal)

    Fail-closed: any parse/runtime error → escalate.
    """
    try:
        payload = json.load(sys.stdin)

        # Detect PreToolUse@submit_reply context
        is_final_veto = (
            payload.get("tool_name") == "submit_reply"
            or payload.get("hook_event_name") == "PreToolUse"
        )

        signals = _derive_signals(payload)
        escalate, reason = should_escalate(signals)

        if escalate:
            print(json.dumps({
                "action": "escalate",
                "reason": reason,
                "risk_signals": [k for k, _ in _SIGNAL_ORDER if signals.get(k)],
            }))
            # exit 2 = hard BLOCK in PreToolUse context; exit 1 = escalation signal elsewhere
            sys.exit(2 if is_final_veto else 1)

        sys.exit(0)

    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"escalation_gate:error:{exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
