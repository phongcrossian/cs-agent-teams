"""
tests/cs_team/test_pre_send_guard_authorized.py — Subprocess exit-code proofs for
the D-26 authorized-offer guard (plan 04-09).

This file is the load-bearing proof suite for the pre_send_guard.py rework.
It pipes submit_reply payloads to the real hook subprocess and asserts:
  - exit 0 for authorized in-policy templated offers (D-26 allows)
  - exit 2 for every unauthorized axis (D-26 blocks → escalate)

Coverage (10 axes):
  1. Authorized B7 Partial_Refund in-policy offer (50% refund + 40% discount) → exit 0
  2. Over-threshold (70% refund) → exit 2
  3. Out-of-template (unknown template code) → exit 2
  4. Ineligible (in_warranty=False) → exit 2
  5. Second-remediation (prior_remediation=True) → exit 2
  6. Operational assertion (Change_Shipping_Address + asserts_mutation=True) → exit 2
  7. Review force-escalate → exit 2
  8. Commitment term in body with no offer block → exit 2
  9. Pure informational body (no commitment, no offer) → exit 0
 10. Malformed stdin → exit 2 (fail-closed)

No real LLM, no network, no DB. All tests run in CI without skip markers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helper: run pre_send_guard as a real subprocess
# ---------------------------------------------------------------------------

def _run_hook(
    payload: dict[str, Any] | bytes,
) -> subprocess.CompletedProcess:
    """Run `.claude/hooks/pre_send_guard.py` as a subprocess, piping payload as JSON to stdin.

    Args:
        payload: Dict to JSON-encode (or raw bytes if already encoded/malformed).

    Returns:
        subprocess.CompletedProcess with .returncode, .stdout, .stderr.
    """
    hook_path = _REPO_ROOT / ".claude" / "hooks" / "pre_send_guard.py"

    merged_env = os.environ.copy()
    pythonpath = merged_env.get("PYTHONPATH", "")
    merged_env["PYTHONPATH"] = (
        str(_REPO_ROOT) if not pythonpath else f"{_REPO_ROOT}:{pythonpath}"
    )

    if isinstance(payload, bytes):
        stdin_bytes = payload
    else:
        stdin_bytes = json.dumps(payload).encode()

    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_bytes,
        capture_output=True,
        cwd=str(_REPO_ROOT),
        env=merged_env,
    )


def _submit_payload(body: str, offer: dict | None = None, citations: list | None = None) -> dict:
    """Build a submit_reply PreToolUse payload."""
    tool_input: dict[str, Any] = {"body": body, "citations": citations or []}
    if offer is not None:
        tool_input["offer"] = offer
    return {
        "tool_name": "submit_reply",
        "tool_input": tool_input,
    }


# ---------------------------------------------------------------------------
# Test class: D-26 authorized-offer guard
# ---------------------------------------------------------------------------


class TestPreSendGuardAuthorized:
    """Subprocess exit-code proofs for the D-26 authorized-offer guard."""

    # -----------------------------------------------------------------------
    # 1. Authorized in-policy offer → exit 0
    # -----------------------------------------------------------------------

    def test_authorized_b7_partial_refund_exits_0(self) -> None:
        """Authorized B7 Partial_Refund (50% refund + 40% discount, in-warranty) → exit 0.

        This is the load-bearing authorized exit-0 contract: an in-template,
        in-threshold, in-warranty, first-remediation offer MUST pass the guard.
        """
        payload = _submit_payload(
            body="We can offer a 50% refund and 40% discount [KB-1].",
            offer={
                "sub_type": "Partial_Refund",
                "template_code": "B7",
                "offered": {"refund_pct": 50, "discount_pct": 40},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 0, (
            f"Authorized B7 offer must exit 0; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    def test_authorized_pure_informational_exits_0(self) -> None:
        """Pure informational body (no commitment term, no offer block) → exit 0.

        Tracking-status or policy-explanation replies with no commitment language
        must pass the guard unconditionally.
        """
        payload = _submit_payload(
            body="Your order is currently being processed and will ship within 2 business days [KB-1].",
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 0, (
            f"Pure informational body must exit 0; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 2. Over-threshold → exit 2
    # -----------------------------------------------------------------------

    def test_over_threshold_refund_70_exits_2(self) -> None:
        """Over-threshold (70% refund, cap=50% THR-07) → exit 2.

        The guard must block numeric offers that exceed policy caps regardless
        of template code and eligibility.
        """
        payload = _submit_payload(
            body="We can offer a 70% refund [KB-1].",
            offer={
                "sub_type": "Partial_Refund",
                "template_code": "B7",
                "offered": {"refund_pct": 70},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Over-threshold refund (70%) must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 3. Out-of-template → exit 2
    # -----------------------------------------------------------------------

    def test_out_of_template_unknown_code_exits_2(self) -> None:
        """Out-of-template (unknown template code 'X999') → exit 2.

        Only template codes in TEMPLATE_REGISTRY for the sub_type are allowed.
        A fabricated or mismatched code must block.
        """
        payload = _submit_payload(
            body="We can offer a 50% refund [KB-1].",
            offer={
                "sub_type": "Partial_Refund",
                "template_code": "X999",
                "offered": {"refund_pct": 50},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Out-of-template code must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 4. Ineligible (in_warranty=False) → exit 2
    # -----------------------------------------------------------------------

    def test_ineligible_out_of_warranty_exits_2(self) -> None:
        """Ineligible order (in_warranty=False) → exit 2.

        An offer made for an out-of-warranty order must be blocked even if the
        template code and thresholds are within policy.
        """
        payload = _submit_payload(
            body="We can offer a 50% refund and 40% discount [KB-1].",
            offer={
                "sub_type": "Partial_Refund",
                "template_code": "B7",
                "offered": {"refund_pct": 50, "discount_pct": 40},
                "eligibility": {"in_warranty": False, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Out-of-warranty ineligible offer must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 5. Second-remediation (prior_remediation=True) → exit 2
    # -----------------------------------------------------------------------

    def test_second_remediation_exits_2(self) -> None:
        """Second remediation (prior_remediation=True) → exit 2.

        When a prior refund/replacement has already been given, a second offer
        at the same tier must be blocked.
        """
        payload = _submit_payload(
            body="We can offer a 50% refund [KB-1].",
            offer={
                "sub_type": "Partial_Refund",
                "template_code": "B7",
                "offered": {"refund_pct": 50},
                "eligibility": {"in_warranty": True, "prior_remediation": True},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Second-remediation offer must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 6. Operational assertion (asserts_mutation=True) → exit 2
    # -----------------------------------------------------------------------

    def test_operational_assertion_exits_2(self) -> None:
        """Operational assertion (Change_Shipping_Address + asserts_mutation=True) → exit 2.

        The AI must not claim a completed operational action it did not cause (RD-Q1 / §1).
        """
        payload = _submit_payload(
            body="We have successfully updated your shipping address [KB-1].",
            offer={
                "sub_type": "Change_Shipping_Address",
                "template_code": "E1",
                "offered": {},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
                "asserts_mutation": True,
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Operational-assertion offer must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 7. Review force-escalate → exit 2
    # -----------------------------------------------------------------------

    def test_review_force_escalate_exits_2(self) -> None:
        """Review sub_type (no dedicated template, Phase-1 gap) → exit 2 (force-escalate).

        Review has no approved flow; any offer under this sub_type must always escalate.
        """
        payload = _submit_payload(
            body="We appreciate your feedback and can offer a 40% discount [KB-1].",
            offer={
                "sub_type": "Review",
                "template_code": None,
                "offered": {"discount_pct": 40},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Review sub_type must force-escalate (exit 2); got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 8. Commitment term in body with no offer block → exit 2
    # -----------------------------------------------------------------------

    def test_commitment_without_offer_block_exits_2(self) -> None:
        """Commitment term ('refund') in body with NO offer block → exit 2 (fail-closed).

        The tripwire: if the body contains commitment language but no authorized
        offer block accompanies it, the guard must block (unauthorized:commitment_without_offer).
        """
        payload = _submit_payload(
            body="We will refund you fully for this inconvenience.",
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Commitment-without-offer-block must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    def test_replace_commitment_without_offer_block_exits_2(self) -> None:
        """Commitment term ('replace') in body with NO offer block → exit 2.

        A second variant of the tripwire to confirm the lexicon still fires
        for order-change commitment terms.
        """
        payload = _submit_payload(
            body="We will replace the damaged item immediately.",
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Replace commitment-without-offer-block must exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # 9. Malformed stdin → exit 2 (fail-closed)
    # -----------------------------------------------------------------------

    def test_malformed_stdin_exits_2(self) -> None:
        """Malformed JSON stdin → exit 2 (fail-closed).

        Any parse error or missing required fields must block, never pass.
        """
        proc = _run_hook(b'{"tool_name": "submit_reply", BROKEN_JSON')
        assert proc.returncode == 2, (
            f"Malformed stdin must exit 2 (fail-closed); got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    def test_offer_missing_required_key_exits_2(self) -> None:
        """Offer block present but missing required 'sub_type' key → exit 2 (fail-closed).

        Partial/malformed offer payloads must be treated as unauthorized.
        """
        payload = _submit_payload(
            body="We can offer a 50% refund [KB-1].",
            offer={
                # sub_type intentionally omitted
                "template_code": "B7",
                "offered": {"refund_pct": 50},
                "eligibility": {"in_warranty": True, "prior_remediation": False},
            },
            citations=[{"id": "KB-1"}],
        )
        proc = _run_hook(payload)
        assert proc.returncode == 2, (
            f"Offer with missing sub_type must exit 2 (fail-closed); got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
