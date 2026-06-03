"""
tests/cs_team/test_escalation_gate_operational.py

Subprocess + unit proofs that the operational_action signal:
  1. Blocks submit_reply (returncode 2) when customer_request = "Review".
  2. Blocks submit_reply (returncode 2) when asserts_mutation = True (change_request path).
  3. Existing trigger (high_risk_category) still blocks — regression guard (T-04-08-02).
  4. Clean all-False signals + clean customer_request -> submit_reply passes (returncode 0).
  5. Unit: should_escalate precedence — operational_action fires only after five base signals
     are all False.

No real LLM, no network, no DB.
Uses the same _run_hook / _temp_run_id / _state_file helpers as test_hooks_subprocess.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Repo root + hook loader
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent

# Load escalation_gate module for in-process unit tests
def _load_escalation_gate():
    spec = importlib.util.spec_from_file_location(
        "escalation_gate",
        _REPO_ROOT / ".claude" / "hooks" / "escalation_gate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_EG = _load_escalation_gate()


# ---------------------------------------------------------------------------
# Subprocess helpers (mirrored from test_hooks_subprocess.py)
# ---------------------------------------------------------------------------

def _run_hook(
    name: str,
    payload: dict[str, Any],
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run `.claude/hooks/<name>.py` as a subprocess, piping *payload* as JSON to stdin."""
    hook_path = _REPO_ROOT / ".claude" / "hooks" / f"{name}.py"
    merged_env = os.environ.copy()
    if env:
        for k, v in env.items():
            if v == "":
                merged_env.pop(k, None)
            else:
                merged_env[k] = v
    pythonpath = merged_env.get("PYTHONPATH", "")
    merged_env["PYTHONPATH"] = (
        str(_REPO_ROOT) if not pythonpath else f"{_REPO_ROOT}:{pythonpath}"
    )
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload).encode(),
        capture_output=True,
        cwd=str(_REPO_ROOT),
        env=merged_env,
    )


def _temp_run_id() -> str:
    return f"test-op-{uuid.uuid4().hex[:12]}"


def _state_file(run_id: str) -> Path:
    return Path(tempfile.gettempdir()) / "cs_run_state" / f"{run_id}.json"


# ---------------------------------------------------------------------------
# Subprocess: operational_action via Review
# ---------------------------------------------------------------------------

class TestOperationalActionReviewSubprocess:
    """Prove Review customer_request forces exit-2 at submit_reply."""

    def test_write_review_then_submit_reply_returns_2(self) -> None:
        """WRITE customer_request=Review THEN submit_reply -> returncode 2 (blocked)."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            # WRITE side: PostToolUse carrying customer_request=Review
            write_payload = {
                "hook_event_name": "PostToolUse",
                "customer_request": "Review",
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode in (0, 1), (
                f"Write side crashed: {write_proc.returncode} stderr={write_proc.stderr!r}"
            )

            # READ side: PreToolUse@submit_reply must see operational_action accumulated
            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {"body": "x", "citations": []},
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 2, (
                f"Expected returncode 2 (Review escalate); got {read_proc.returncode}. "
                f"stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()

    def test_write_full_refund_then_submit_reply_returns_2(self) -> None:
        """WRITE customer_request=Full_Refund THEN submit_reply -> returncode 2 (blocked)."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            write_payload = {
                "hook_event_name": "PostToolUse",
                "customer_request": "Full_Refund",
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode in (0, 1), (
                f"Write side crashed: {write_proc.returncode} stderr={write_proc.stderr!r}"
            )

            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {"body": "x", "citations": []},
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 2, (
                f"Expected returncode 2 (Full_Refund escalate); got {read_proc.returncode}. "
                f"stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()


# ---------------------------------------------------------------------------
# Subprocess: operational_action via asserts_mutation (change_request path)
# ---------------------------------------------------------------------------

class TestOperationalActionAssertsMutationSubprocess:
    """Prove asserts_mutation=True forces exit-2 at submit_reply (RD-Q1)."""

    def test_write_asserts_mutation_then_submit_reply_returns_2(self) -> None:
        """WRITE asserts_mutation=True (change_request) THEN submit_reply -> returncode 2."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            # Simulate a drafter stage emitting a draft that claims a completed action
            write_payload = {
                "hook_event_name": "PostToolUse",
                "customer_request": "Change_Shipping_Address",
                "asserts_mutation": True,
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode in (0, 1), (
                f"Write side crashed: {write_proc.returncode} stderr={write_proc.stderr!r}"
            )

            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {"body": "x", "citations": []},
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 2, (
                f"Expected returncode 2 (asserts_mutation RD-Q1); got {read_proc.returncode}. "
                f"stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()

    def test_change_shipping_address_no_explicit_false_returns_2(self) -> None:
        """change_request sub-type without asserts_mutation=False -> returncode 2 (fail-closed §1)."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            # No asserts_mutation key — treated as "not explicitly False" → escalate
            write_payload = {
                "hook_event_name": "PostToolUse",
                "customer_request": "Change_Product_Variant",
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode in (0, 1), (
                f"Write side crashed: {write_proc.returncode} stderr={write_proc.stderr!r}"
            )

            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {"body": "x", "citations": []},
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 2, (
                f"Expected returncode 2 (Change_Product_Variant without asserts_mutation=False); "
                f"got {read_proc.returncode}. stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()


# ---------------------------------------------------------------------------
# Subprocess: regression guard — existing high_risk_category still blocks
# ---------------------------------------------------------------------------

class TestExistingSignalRegressionSubprocess:
    """T-04-08-02: prove adding operational_action did not weaken existing triggers."""

    def test_write_high_risk_category_then_submit_reply_returns_2(self) -> None:
        """WRITE high_risk_category=True THEN submit_reply -> returncode 2 (regression guard)."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            write_payload = {
                "hook_event_name": "PostToolUse",
                "signals": {"high_risk_category": True},
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode in (0, 1), (
                f"Write side crashed: {write_proc.returncode} stderr={write_proc.stderr!r}"
            )

            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {"body": "x", "citations": []},
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 2, (
                f"Regression: high_risk_category should still block; got {read_proc.returncode}. "
                f"stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()


# ---------------------------------------------------------------------------
# Subprocess: clean all-False path — passes through
# ---------------------------------------------------------------------------

class TestCleanSignalsSubprocess:
    """Prove that all-False signals with a non-escalating customer_request pass (returncode 0)."""

    def test_clean_signals_ask_about_order_returns_0(self) -> None:
        """WRITE all-False signals + customer_request=Ask_About_Order -> submit_reply passes (0)."""
        run_id = _temp_run_id()
        state_file = _state_file(run_id)
        env = {"CS_RUN_ID": run_id}

        try:
            write_payload = {
                "hook_event_name": "PostToolUse",
                "signals": {
                    "low_confidence": False,
                    "high_risk_category": False,
                    "conflict": False,
                    "stale_only": False,
                    "missing_key": False,
                    "operational_action": False,
                },
                "customer_request": "Ask_About_Order",
                "asserts_mutation": False,
            }
            write_proc = _run_hook("escalation_gate", write_payload, env=env)
            assert write_proc.returncode == 0, (
                f"Write side should exit 0 (clean); got {write_proc.returncode}. "
                f"stderr={write_proc.stderr!r}"
            )

            read_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "submit_reply",
                "tool_input": {
                    "body": "Your order [KB-1] is on its way.",
                    "citations": [{"id": "KB-1"}],
                },
            }
            read_proc = _run_hook("escalation_gate", read_payload, env=env)
            assert read_proc.returncode == 0, (
                f"Expected returncode 0 (clean pass); got {read_proc.returncode}. "
                f"stdout={read_proc.stdout!r}"
            )
        finally:
            if state_file.exists():
                state_file.unlink()


# ---------------------------------------------------------------------------
# Unit: should_escalate precedence
# ---------------------------------------------------------------------------

class TestShouldEscalatePrecedenceUnit:
    """In-process unit tests for should_escalate signal precedence."""

    def test_operational_action_alone_escalates(self) -> None:
        ok, reason = _EG.should_escalate({"operational_action": True})
        assert ok is True
        assert reason == "escalate:operational_action"

    def test_operational_action_fires_after_five_base_false(self) -> None:
        """operational_action wins when all five base signals are False."""
        signals = {
            "low_confidence": False,
            "high_risk_category": False,
            "conflict": False,
            "stale_only": False,
            "missing_key": False,
            "operational_action": True,
        }
        ok, reason = _EG.should_escalate(signals)
        assert ok is True
        assert reason == "escalate:operational_action"

    def test_base_signal_wins_over_operational_action(self) -> None:
        """First-match: low_confidence wins even when operational_action is also True."""
        signals = {k: False for k, _ in _EG._SIGNAL_ORDER}
        signals["low_confidence"] = True
        signals["operational_action"] = True
        ok, reason = _EG.should_escalate(signals)
        assert ok is True
        assert reason == "escalate:low_confidence"

    def test_all_false_returns_clean(self) -> None:
        ok, reason = _EG.should_escalate({k: False for k, _ in _EG._SIGNAL_ORDER})
        assert ok is False
        assert reason == ""

    def test_six_signals_present_in_order(self) -> None:
        """All six signals exist in _SIGNAL_ORDER (five base + operational_action)."""
        keys = [k for k, _ in _EG._SIGNAL_ORDER]
        assert "low_confidence" in keys
        assert "high_risk_category" in keys
        assert "conflict" in keys
        assert "stale_only" in keys
        assert "missing_key" in keys
        assert "operational_action" in keys
        # operational_action must come after the five base signals (additive, no reorder)
        assert keys.index("operational_action") == 5
