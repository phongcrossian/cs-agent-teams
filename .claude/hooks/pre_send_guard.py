"""
Pre-send guard — D-26 authorized-offer test (SAFE-04).

D-26 SUPERSEDES the block-all D-13 guard (plan 04-09, 2026-06-03).
D-13 blocked ALL commitment language unconditionally — this caused the highest-volume
CS flows (Return, Replace, Partial_Refund) to always escalate, even when the offer was
policy-bounded and template-approved. D-26 replaces that with a precise test:

  AUTHORIZED (exit 0) iff:
    1. The offer follows an approved template for the sub_type (TEMPLATE_REGISTRY), AND
    2. All offered values are within the policy threshold caps (THRESHOLD_CAPS), AND
    3. The order is eligible (in_warranty, not prior_remediation), grounded via Selless, AND
    4. The draft does NOT assert a completed operational mutation (asserts_mutation=False).

  UNAUTHORIZED (exit 2 → escalate) for:
    - Commitment term in body with no offer block (unauthorized:commitment_without_offer)
    - Offer present but fails authorize_offer (over-threshold, out-of-template,
      ineligible, second-remediation, operational-assertion, force-escalate)
    - Malformed/missing offer fields when a commitment term is present

  PASS (exit 0) for:
    - Pure informational reply (no commitment term, no offer block)
    - Authorized offer (authorize_offer returns True)

Design rules (unchanged from D-13):
  - NEVER auto-strip commitment language and send — always block-and-escalate
  - Deterministic, LLM-free, stdlib-only
  - Fail-closed: any exception or missing required offer key → exit 2

Hook contract (Claude Code PreToolUse on submit_reply):
  stdin:  {"tool_name": "submit_reply", "tool_input": {"body": "...", "offer": {...}, ...}}
  exit 0: pass (draft may be submitted)
  exit 2: BLOCK (escalate verdict emitted to stdout as JSON)

submit_reply is the SOLE emission path for customer-facing content (§4a).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import authorize_offer from the sibling module using importlib.
# This works when the hook is invoked as `uv run python .claude/hooks/pre_send_guard.py`
# (the .claude/hooks/ directory is NOT on sys.path by default).
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).parent
_AUTHORIZED_OFFER_PATH = _HOOKS_DIR / "authorized_offer.py"

def _load_authorized_offer():
    """Load authorize_offer and default_eligibility from the sibling module by absolute path."""
    spec = importlib.util.spec_from_file_location("authorized_offer", _AUTHORIZED_OFFER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load authorized_offer from {_AUTHORIZED_OFFER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.authorize_offer, module.default_eligibility


authorize_offer, default_eligibility = _load_authorized_offer()


# ---------------------------------------------------------------------------
# Commitment-language tripwire lexicon (retained from D-13).
# Purpose changed: this lexicon is now a TRIPWIRE only.
# If the body contains a commitment term, an authorized offer block MUST accompany it.
# A commitment term with no offer block, or with an offer block that fails authorize_offer,
# → exit 2 (unauthorized).
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


def _has_commitment_term(body: str) -> bool:
    """Return True if the body contains any commitment-language term (tripwire)."""
    for pattern, _ in _COMMITMENT_PATTERNS:
        if pattern.search(body):
            return True
    return False


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


def _extract_offer(payload: dict) -> dict | None:
    """Extract the structured offer block from the hook payload, if present.

    The drafter (plan 04-10) passes the offer under tool_input["offer"]:
      {
        "sub_type": str,
        "template_code": str | None,
        "offered": {"refund_pct": float, "discount_pct": float, ...},
        "eligibility": {"in_warranty": bool, "prior_remediation": bool, ...},
        "asserts_mutation": bool,  # optional, default False
      }

    Returns None if no offer block is present in the payload.
    Raises KeyError / TypeError if the offer block is present but malformed
    (caller must treat this as fail-closed → exit 2).
    """
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, dict) and "offer" in tool_input:
        return tool_input["offer"]
    return None


def _block(reason: str) -> None:
    """Print escalate JSON payload and exit 2 (BLOCK)."""
    print(json.dumps({"action": "escalate", "reason": reason}))
    sys.exit(2)


def main() -> None:
    """Claude Code hook entry point (PreToolUse on submit_reply).

    D-26 decision flow:
      1. Parse stdin JSON (fail-closed on error → exit 2).
      2. Extract body + offer block.
      3. Tripwire: if body contains a commitment term AND no offer block → exit 2.
      4. If offer block present: call authorize_offer; exit 2 if UNAUTHORIZED.
      5. If offer block present AND authorized → exit 0.
      6. If no commitment term AND no offer block → exit 0 (pure informational).

    The body is NEVER auto-stripped or rewritten. Block-and-escalate only.
    """
    try:
        payload = json.load(sys.stdin)
        body = _extract_draft(payload)
        offer = _extract_offer(payload)

        has_commitment = _has_commitment_term(body)

        if offer is not None:
            # Offer block present — validate via authorize_offer.
            # Required field: sub_type. Missing → fail-closed.
            sub_type = offer["sub_type"]  # KeyError → caught by outer except → exit 2
            template_code = offer.get("template_code")
            offered = offer.get("offered") or {}
            eligibility = offer.get("eligibility") or default_eligibility()
            asserts_mutation = bool(offer.get("asserts_mutation", False))

            authorized, reason = authorize_offer(
                sub_type=sub_type,
                template_code=template_code,
                offered=offered,
                eligibility=eligibility,
                asserts_mutation=asserts_mutation,
            )
            if not authorized:
                _block(f"pre_send_guard:{reason}")
            # Authorized offer — exit 0
            sys.exit(0)

        # No offer block present.
        if has_commitment:
            # Commitment term without an authorized offer block → block (fail-closed tripwire).
            _block("unauthorized:commitment_without_offer")

        # Pure informational reply (no commitment term, no offer block) → pass.
        sys.exit(0)

    except SystemExit:
        raise  # let sys.exit() propagate normally
    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"pre_send_guard:error:{exc}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
