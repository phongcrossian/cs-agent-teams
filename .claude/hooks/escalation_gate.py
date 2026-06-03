"""
Escalation gate — SAFE-03 / D-08 / D-09.

Deterministic (no LLM). OR-gate over risk signals: ANY single True signal
forces escalation (fail-closed, additive per D-08).

This SAME script serves TWO invocation contexts (design §4a — no 6th script):
  1. PostToolUse / SubagentStop (early-exit / accumulation context):
     Reads classifier/extractor stage result fields from the payload,
     derives signals, OR-merges them into the per-run CS_RUN_ID state file.
     Exits 1 to signal escalation when a signal is present, 0 when clean.
     When CS_RUN_ID is unset (non-cs-team session), this is a NO-OP (exit 0).
  2. PreToolUse @ submit_reply (final-risk veto context):
     Reads accumulated risk state from the per-run CS_RUN_ID state file.
     BLOCKS (exit 2) if any signal is set, if the state file is missing,
     or if CS_RUN_ID is unset — the hard gate. This is the security default:
     no state means "we cannot prove the ticket is low-risk".

State-file design (CR-02 / SAFE-03):
  - Location: ${TMPDIR or /tmp}/cs_run_state/<CS_RUN_ID>.json
    Python tempfile.gettempdir() used — never hardcoded /tmp.
  - Key: env var CS_RUN_ID (set once by the runner per ticket run).
  - Schema: {"signals": {...}, "updated_at": "<iso8601>"}
  - Lifecycle: created/updated at PostToolUse+SubagentStop (WRITE side);
    read at PreToolUse@submit_reply (READ side); runner deletes at run end.
  - Fail-closed READ: no CS_RUN_ID / no file / unparseable -> escalate (exit 2).
  - Concurrency: per CS_RUN_ID so parallel runs do not collide.
  - No PII: stores only boolean signal flags + timestamp; no ticket body.

Contract (mirrors src/guards/loop_guard.should_suppress):
    should_escalate(signals: dict) -> tuple[bool, str]
    - bool: True = escalate
    - str: reason label (e.g. "escalate:kb_conflict"); "" when no signal

Fail-closed: malformed stdin -> escalate.

Override-resolved conflicts (D-09):
    When the Knowledge MCP resolves a conflict via override_resolution,
    the upstream stage clears conflict=False BEFORE emitting the verdict.
    A resolved conflict does NOT false-escalate here — the source of truth
    is the signals dict, not a raw conflict flag from the MCP.

NO-OP safety outside a CS run:
    When invoked WITHOUT an active CS_RUN_ID (e.g. on generic
    PostToolUse/SubagentStop in a non-cs-team session), the WRITE side
    finds no env var, writes nothing, and exits 0. The READ side
    (PreToolUse@submit_reply) is only reached when the hook is bound
    explicitly to submit_reply — a tool that only the cs-team uses.
    Result: this hook is a NO-OP in unrelated sessions.
"""

from __future__ import annotations

import datetime
import json
import os
import re as _re
import sys
import tempfile
from pathlib import Path

# CR-02: safe run-id regex — blocks path traversal via env-var injection
_SAFE_RUN_ID = _re.compile(r'^[A-Za-z0-9_\-]{1,128}$')

# Signal key order: first match wins (mirrors should_suppress layer order)
_SIGNAL_ORDER: list[tuple[str, str]] = [
    ("low_confidence",      "escalate:low_confidence"),
    ("high_risk_category",  "escalate:high_risk_category"),
    ("conflict",            "escalate:kb_conflict"),
    ("stale_only",          "escalate:stale_only"),
    ("missing_key",         "escalate:missing_key"),
]

_ALL_SIGNAL_KEYS: list[str] = [k for k, _ in _SIGNAL_ORDER]


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


# ---------------------------------------------------------------------------
# Per-run state-file helpers (CR-02 — stateful veto)
# ---------------------------------------------------------------------------


def _state_path() -> "Path | None":
    """Return the Path to this run's state file, or None if CS_RUN_ID unset/invalid.

    CR-02: CS_RUN_ID is validated against _SAFE_RUN_ID before use in any
    filesystem path. An invalid (potentially traversal) run_id is treated as
    unset: READ side will fail-closed (exit 2); WRITE side is a NO-OP.
    """
    run_id = os.environ.get("CS_RUN_ID")
    if not run_id:
        return None
    if not _SAFE_RUN_ID.match(run_id):
        # Invalid CS_RUN_ID — path traversal attempt or malformed value.
        # Treat as unset: READ side fails closed; WRITE side is NO-OP.
        return None
    state_dir = Path(tempfile.gettempdir()) / "cs_run_state"
    return state_dir / f"{run_id}.json"


def _empty_signals() -> dict:
    """Return an all-False signals dict matching _SIGNAL_ORDER keys."""
    return {k: False for k in _ALL_SIGNAL_KEYS}


def _write_signals(signals: dict) -> None:
    """OR-merge *signals* into the per-run state file (additive, never clears True).

    - Reads the existing file first (tolerates missing/partial).
    - OR-combines: a True can never be flipped back to False (D-08 additive).
    - Stamps updated_at as ISO8601 UTC.
    - Creates parent dir if absent.
    - If CS_RUN_ID is unset (not a cs-team run), silently skips (NO-OP).
    """
    path = _state_path()
    if path is None:
        return  # Not a cs-team run — NO-OP

    # Read existing state (tolerate missing/corrupt)
    existing: dict = _empty_signals()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            for k in _ALL_SIGNAL_KEYS:
                if data.get("signals", {}).get(k):
                    existing[k] = True
        except Exception:  # noqa: BLE001
            pass  # Start from all-False if unparseable

    # OR-merge incoming signals (True can only be set, never cleared)
    for k in _ALL_SIGNAL_KEYS:
        if signals.get(k):
            existing[k] = True

    # Write state file (parent dir created if absent)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "signals": existing,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(state))


def _read_signals() -> "dict | None":
    """Read the persisted signals dict from the per-run state file.

    Returns the signals dict (may be all-False) if file exists and is parseable.
    Returns None when:
      - CS_RUN_ID env var is unset, OR
      - the state file does not exist, OR
      - the file is unparseable.

    Callers in the READ (final-veto) context MUST escalate when None is returned
    (fail-closed: no state = cannot prove ticket is low-risk).
    """
    path = _state_path()
    if path is None:
        return None  # CS_RUN_ID unset

    if not path.exists():
        return None  # No state file for this run

    try:
        data = json.loads(path.read_text())
        signals = data.get("signals")
        if not isinstance(signals, dict):
            return None
        # Return a normalised dict with all known keys defaulting to False
        return {k: bool(signals.get(k, False)) for k in _ALL_SIGNAL_KEYS}
    except Exception:  # noqa: BLE001
        return None  # Unparseable -> fail closed


def main() -> None:
    """Claude Code hook entry point.

    Serves both PostToolUse/SubagentStop (WRITE side) and
    PreToolUse@submit_reply (READ/veto side).

    WRITE side (PostToolUse / SubagentStop):
      - Derives signals from payload.
      - OR-merges signals into the per-run CS_RUN_ID state file.
      - When CS_RUN_ID is unset, this is a NO-OP (non-cs-team session).
      - Exits 0 when no signal; exits 1 when a signal is present (early signal).

    READ side (PreToolUse@submit_reply):
      - Reads the per-run CS_RUN_ID state file.
      - FAIL CLOSED: no CS_RUN_ID / no file / unparseable -> exit 2 (BLOCK).
      - If accumulated signals contain any True -> exit 2 (BLOCK).
      - All-clean signals -> exit 0.

    Fail-closed on parse error:
      - stdin is read once into raw bytes first so we can attempt context
        detection even when JSON parsing fails.
      - If raw stdin contains "submit_reply" and "PreToolUse" (final-veto
        context markers), any error exits 2 (BLOCK — fail-closed).
      - Otherwise (WRITE side / SubagentStop / non-cs-team generic session),
        any error exits 1 (non-blocking warning). This preserves the NO-OP
        contract for unrelated PostToolUse/* sessions: Claude Code treats
        non-2 non-zero as a non-blocking warning, so the tool still runs.
      - Rationale: grounding_check.py and pre_send_guard.py run BEFORE this
        hook in the PreToolUse@submit_reply chain (see settings.json) and
        already exit 2 on malformed input — the chokepoint stays protected
        even if this hook falls back to exit 1 on WRITE-side parse errors.
    """
    # CR-01: read stdin once into raw_bytes so we can inspect content for
    # context detection even when JSON parsing fails later.
    try:
        raw_bytes = sys.stdin.buffer.read()
    except Exception:  # noqa: BLE001
        raw_bytes = b""

    try:
        payload = json.loads(raw_bytes)

        # Detect PreToolUse@submit_reply context (final-risk veto).
        # CR-01 (WR-02): use AND — both conditions must hold simultaneously.
        # OR was overly broad: any PreToolUse (regardless of tool) would
        # have triggered the READ/veto path if settings.json ever widened
        # the binding beyond submit_reply.
        is_final_veto = (
            payload.get("tool_name") == "submit_reply"
            and payload.get("hook_event_name") == "PreToolUse"
        )

        if is_final_veto:
            # READ side: check persisted accumulated signals
            signals = _read_signals()
            if signals is None:
                # Fail-closed: no state -> cannot prove low-risk
                print(json.dumps({
                    "action": "escalate",
                    "reason": "escalate:no_run_state",
                    "detail": "CS_RUN_ID unset or state file missing/unparseable — fail-closed",
                }))
                sys.exit(2)

            escalate, reason = should_escalate(signals)
            if escalate:
                print(json.dumps({
                    "action": "escalate",
                    "reason": reason,
                    "risk_signals": [k for k, _ in _SIGNAL_ORDER if signals.get(k)],
                }))
                sys.exit(2)

            sys.exit(0)

        else:
            # WRITE side: accumulate signals into per-run state file
            derived = _derive_signals(payload)
            _write_signals(derived)

            escalate, reason = should_escalate(derived)
            if escalate:
                print(json.dumps({
                    "action": "escalate",
                    "reason": reason,
                    "risk_signals": [k for k, _ in _SIGNAL_ORDER if derived.get(k)],
                }))
                sys.exit(1)

            sys.exit(0)

    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"escalation_gate:error:{exc}"}))
        # CR-01: determine exit code based on raw stdin content.
        # If raw bytes contain both final-veto context markers, exit 2 (BLOCK).
        # Otherwise exit 1 (non-blocking) to preserve NO-OP for generic
        # PostToolUse/* bindings in unrelated sessions.
        if b'"submit_reply"' in raw_bytes and b'"PreToolUse"' in raw_bytes:
            sys.exit(2)
        sys.exit(1)


if __name__ == "__main__":
    main()
