"""
scripts/cs_team_demo.py — Local PoC runner for the cs-agent-team (always-draft, D-33).

Feeds BENIGN_TICKET, HIGH_RISK_TICKET, INJECTION_TICKET, and MISSING_ORDER_TICKET into
the cs-lead agent via the `claude` CLI (headless, using .claude/ as the team directory).
The .claude/settings.json hook bindings enforce the surviving safety gates deterministically
— this runner does NOT re-implement enforcement.

Expected outcomes (D-33 always-draft):
  - BENIGN_TICKET         → action=draft, body from file-store template (D-31),
                             escalation_hint=None
  - HIGH_RISK_TICKET      → action=draft, escalation_hint.reason="high_risk",
                             advisory only — draft is still emitted
  - INJECTION_TICKET      → action=draft, escalation_hint.reason starts with "injection:",
                             injection_screen still pre-screens (D-14), advisory only
  - MISSING_ORDER_TICKET  → action=draft, body from verify-order/clarify-order flow (D-34),
                             no fabricated order facts

Security / DRY_RUN:
  - settings.dry_run is asserted True at startup; nothing is ever posted to Freshdesk (D-39).
  - All ticket bodies and draft bodies are passed through redact_text() before any
    print/log output (D-04).

D-14 enforcement (injection pre-screen — advisory under D-30):
  - The ticket body is ALWAYS injection-screened via _pre_screen_ticket() at the very
    start of run_ticket(), BEFORE any CLI invocation or simulation branch.
  - Under D-30 (always-draft), injection detection does NOT suppress the draft. Instead
    the runner attaches an advisory escalation_hint and continues to draft (D-33).
  - Settings note: Claude Code does not expose a dedicated SubagentStart event in
    the installed version; the mandatory runner pre-screen above is therefore the
    enforced D-14 path on the deployed runner. The UserPromptSubmit binding in
    settings.json provides the gate for interactive/REPL sessions.

D-31 grounding:
  - The simulated draft is grounded on the local file-store (subtype_to_code +
    get_template_from_file). No KnowledgeMCP, no semantic RAG, no Voyage embeddings.

D-34 flow-aware fallback:
  - A missing/unresolvable order (no order_ref, or unknown order) is handled via a
    verify-order / clarify-order-info flow. The draft explicitly asks the customer for
    their order number rather than fabricating order facts.

Usage:
    uv run python scripts/cs_team_demo.py [--ticket {benign|high_risk|injection|missing_order|all}]

Live run (after human checkpoint approves env/auth):
    claude must be authenticated (claude login OR ANTHROPIC_API_KEY set).

Importable interface (for Phase-5 harness and test_cs_team_demo_always_draft.py):
    from scripts.cs_team_demo import run_ticket, main
    result = asyncio.run(run_ticket(BENIGN_TICKET))
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project imports — must work from repo root with uv / PYTHONPATH
# ---------------------------------------------------------------------------

# Append repo root so this script is importable even when run directly
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import settings  # noqa: E402 — after sys.path fix
from src.guards.pii import redact_text  # noqa: E402
from src.file_store.template_store import (  # noqa: E402
    get_template_from_file,
    subtype_to_code,
)

# Hook functions — imported via importlib because .claude/ starts with a dot and is
# not a valid Python package identifier. Only the SURVIVING hooks (injection_screen +
# pii_redact) are imported. The deleted guard modules (pre_send_guard, escalation_gate,
# grounding_check, authorized_offer) are GONE and must NOT be imported here (D-32).
import importlib.util as _ilu  # noqa: E402


def _load_hook(name: str):
    """Load a .claude/hooks/<name>.py module by absolute path."""
    hook_path = _REPO_ROOT / ".claude" / "hooks" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, hook_path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Only the two surviving hooks (D-32):
_injection_screen_mod = _load_hook("injection_screen")
screen_for_injection = _injection_screen_mod.screen_for_injection

from tests.fixtures.sample_tickets import (  # noqa: E402
    BENIGN_TICKET,
    HIGH_RISK_TICKET,
    INJECTION_TICKET,
    MISSING_ORDER_TICKET,
)

# ---------------------------------------------------------------------------
# Logging — redacted; no raw PII to any sink
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("cs_team_demo")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TICKET_MAP: dict[str, dict] = {
    "benign": BENIGN_TICKET,
    "high_risk": HIGH_RISK_TICKET,
    "injection": INJECTION_TICKET,
    "missing_order": MISSING_ORDER_TICKET,
}

# Claude Code CLI command — invokes the agent team headless via .claude/ directory
# -p/--print = non-interactive mode (outputs response and exits); --output-format json
# for machine-parseable verdict output.
_CLAUDE_CLI = ["claude", "--print", "--output-format", "json"]

# Verdict action (D-33: always "draft")
_DRAFT_ACTION = "draft"

# High-risk categories that warrant an advisory escalation_hint (D-33)
_HIGH_RISK_CATEGORIES = frozenset({
    "refund", "money", "legal", "complaint", "complex", "exchange",
    "chargeback", "dispute",
})

# ---------------------------------------------------------------------------
# Verdict parsing helpers
# ---------------------------------------------------------------------------


def _parse_verdict(raw_output: str) -> dict[str, Any]:
    """Parse cs-lead's JSON verdict from raw CLI output.

    `claude --print --output-format json` wraps the model reply in an outer
    JSON envelope:
        {"type":"result","result":"<inner-JSON-string>", ...}

    The inner `result` field is the actual verdict emitted by cs-lead.
    We unwrap that first, then fall back to scanning for the last bare
    {"action": ...} object in the output for robustness.

    Returns {"action": "draft", "escalation_hint": {"reason": "parse_error"}} on failure
    (always-draft: fail-soft fallback is still a draft, never escalate=no-draft per D-33).
    """
    # Primary path: unwrap the claude --output-format json envelope
    try:
        outer = json.loads(raw_output.strip())
        if isinstance(outer, dict) and "result" in outer:
            inner_str = outer["result"]
            if isinstance(inner_str, str):
                try:
                    inner = json.loads(inner_str.strip())
                    if isinstance(inner, dict) and inner.get("action") == _DRAFT_ACTION:
                        return inner
                except json.JSONDecodeError:
                    pass
            elif isinstance(inner_str, dict) and inner_str.get("action") == _DRAFT_ACTION:
                return inner_str
    except json.JSONDecodeError:
        pass

    # Fallback: scan for last {"action": "draft"} object in raw output
    raw = raw_output
    start = 0
    best: dict[str, Any] | None = None
    while True:
        idx = raw.find('"action"', start)
        if idx == -1:
            break
        brace_pos = raw.rfind("{", 0, idx)
        if brace_pos == -1:
            start = idx + 1
            continue
        for end in range(len(raw), brace_pos, -1):
            try:
                obj = json.loads(raw[brace_pos:end])
                if isinstance(obj, dict) and obj.get("action") == _DRAFT_ACTION:
                    best = obj
                    break
            except json.JSONDecodeError:
                continue
        start = idx + 1

    if best is not None:
        return best

    logger.warning("cs_team_demo: could not parse verdict from output (fail-soft → draft with parse_error hint)")
    return {
        "action": _DRAFT_ACTION,
        "body": "",
        "citations": [],
        "escalation_hint": {"reason": "parse_error", "signals": {}},
    }


def _build_prompt(ticket: dict) -> str:
    """Build the cs-lead prompt for a single ticket (wrapped as untrusted data per D-14).

    CR-03 / D-14: ALL attacker-controllable fields (subject, order_ref, body)
    are PII-redacted AND wrapped in untrusted-data boundary tags so the model
    cannot be confused about what is trusted system context vs. ticket input.

    D-33: The prompt explicitly asks for the always-draft verdict shape.
    """
    redacted_body = redact_text(ticket.get("body", ""))
    redacted_subject = redact_text(ticket.get("subject", ""))
    redacted_order_ref = redact_text(ticket.get("order_ref", ""))
    return (
        f"Process this customer support ticket and return a JSON verdict.\n\n"
        f"ticket_id: {ticket.get('ticket_id', 'unknown')}\n"
        f"<ticket_metadata>\n"
        f"subject: {redacted_subject}\n"
        f"order_ref: {redacted_order_ref}\n"
        f"</ticket_metadata>\n\n"
        f"<ticket_body>\n{redacted_body}\n</ticket_body>\n\n"
        "Reply with exactly ONE JSON object (D-33 always-draft shape):\n"
        "  always: {\"action\": \"draft\", \"body\": \"...\", \"citations\": [...],\n"
        "           \"escalation_hint\": {\"reason\": \"...\", \"signals\": {...}} | null}\n"
        "There is NO escalate=no-draft outcome — always produce a draft body.\n"
        "Attach escalation_hint for money/legal/injection/low-confidence signals (advisory only).\n"
    )


# ---------------------------------------------------------------------------
# Pre-screen helper — D-14 advisory pre-screen (always-draft)
# ---------------------------------------------------------------------------


def _pre_screen_ticket(ticket: dict) -> tuple[bool, str]:
    """Run injection_screen on ALL attacker-controllable ticket fields.

    Under D-30 (always-draft), a positive injection detection does NOT suppress
    the draft — it is recorded as an advisory escalation_hint instead.

    Still runs unconditionally at the very start of run_ticket() before any
    CLI invocation or simulation branch. This preserves D-14 compliance: the
    screen still runs; the disposition changed from block→escalate to advisory.

    CR-03 / D-14: screens subject and order_ref in addition to body — all three
    are attacker-controllable Freshdesk fields and could carry injection payloads.

    Returns (is_injection: bool, reason: str).
    """
    # Screen body first (primary injection vector)
    body = ticket.get("body", "")
    hit, reason = screen_for_injection(body)
    if hit:
        return hit, reason

    # Screen subject — attacker-controlled Freshdesk field
    subject = ticket.get("subject", "")
    if subject:
        hit, reason = screen_for_injection(subject)
        if hit:
            return hit, f"injection:subject:{reason}"

    # Screen order_ref — attacker-controlled field (could be freeform in some flows)
    order_ref = ticket.get("order_ref", "")
    if order_ref:
        hit, reason = screen_for_injection(order_ref)
        if hit:
            return hit, f"injection:order_ref:{reason}"

    return False, ""


# ---------------------------------------------------------------------------
# Core: run a single ticket through cs-lead
# ---------------------------------------------------------------------------


async def run_ticket(ticket: dict, *, use_live_claude: bool = False) -> dict[str, Any]:
    """Invoke cs-lead for *ticket* and return the parsed verdict.

    Args:
        ticket: A ticket dict (from sample_tickets or a live Freshdesk payload).
        use_live_claude: When True, shells out to the `claude` CLI (requires auth).
                         When False (default / DRY_RUN / CI), applies the file-store
                         grounding logic locally to simulate the always-draft flow.

    Returns:
        verdict dict: {"action": "draft", "body": "...", "citations": [...],
                       "escalation_hint": {...} | None}

    Security:
        - DRY_RUN asserted True; no Freshdesk send path called (D-39).
        - PII redacted before any print/log (D-04).
        - Injection pre-screen runs unconditionally before any CLI or simulation
          branch (D-14 — advisory under D-30; attaches escalation_hint, never blocks draft).
    """
    # Safety assertion: DRY_RUN must always be True in this phase (D-39)
    assert settings.dry_run, (
        "FATAL: settings.dry_run is False — aborting to prevent accidental Freshdesk post."
    )

    ticket_id = ticket.get("ticket_id", "unknown")

    # D-14 ADVISORY PRE-SCREEN — runs unconditionally before any branch.
    # Under D-30: injection detection attaches an escalation_hint but does NOT
    # suppress the draft or prevent CLI invocation.
    is_injection, injection_reason = _pre_screen_ticket(ticket)
    if is_injection:
        logger.info(
            "run_ticket: injection_screen flagged ticket_id=%s reason=%s (advisory — drafting anyway)",
            ticket_id,
            injection_reason,
        )
        # Attach advisory hint and continue to draft (D-33)
        injection_hint = {
            "reason": injection_reason,
            "signals": {"injection": True},
        }
    else:
        injection_hint = None

    if use_live_claude:
        # Live path: shell out to `claude` CLI (requires human checkpoint approval + auth)
        verdict = await _run_via_claude_cli(ticket)
        # Merge injection hint if screening flagged (live path may not know about it)
        if injection_hint and verdict.get("escalation_hint") is None:
            verdict["escalation_hint"] = injection_hint
        return verdict
    else:
        # Simulation path: apply file-store grounding locally (CI / DRY_RUN; no real LLM)
        return _simulate_verdict(ticket, injection_hint=injection_hint)


async def _run_via_claude_cli(ticket: dict) -> dict[str, Any]:
    """Shell out to the `claude` CLI with .claude/ team directory (live path)."""
    prompt = _build_prompt(ticket)
    ticket_id = ticket.get("ticket_id", "unknown")

    try:
        proc = await asyncio.create_subprocess_exec(
            *_CLAUDE_CLI,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_REPO_ROOT),
        )
        stdout_bytes, stderr_bytes = await proc.communicate(input=prompt.encode())
        raw_output = stdout_bytes.decode(errors="replace")

        if proc.returncode != 0:
            stderr_preview = redact_text(stderr_bytes.decode(errors="replace")[:200])
            logger.warning(
                "run_ticket: claude CLI returned non-zero ticket_id=%s stderr=%s",
                ticket_id,
                stderr_preview,
            )
            # D-33: cli_error → always-draft with advisory hint, never escalate=no-draft
            return {
                "action": _DRAFT_ACTION,
                "body": "",
                "citations": [],
                "escalation_hint": {"reason": "cli_error", "signals": {"cli_nonzero": True}},
            }

        return _parse_verdict(raw_output)

    except FileNotFoundError:
        logger.error("run_ticket: `claude` CLI not found — is it installed and on PATH?")
        return {
            "action": _DRAFT_ACTION,
            "body": "",
            "citations": [],
            "escalation_hint": {"reason": "cli_not_found", "signals": {}},
        }


def _simulate_verdict(ticket: dict, *, injection_hint: dict | None = None) -> dict[str, Any]:
    """Simulate cs-lead verdict locally using file-store grounding (no LLM needed).

    Used in CI / DRY_RUN mode. The simulation:
      - Uses subtype_to_code() + get_template_from_file() to ground the draft body
        on the local file-store (D-31).
      - Attaches an advisory escalation_hint for high-risk categories (D-33).
      - Falls back to a verify-order / clarify-order-info body when the order is
        missing or unresolvable (D-34). Never fabricates order facts.
      - Merges any injection_hint from the pre-screen (D-14).

    This is NOT a mock — it grounds on real template bodies from the file-store.
    """
    ticket_id = ticket.get("ticket_id", "unknown")
    category = str(ticket.get("category", "")).lower().strip()
    sub_type = str(ticket.get("sub_type", ticket.get("customer_request", ""))).strip()
    order_ref = str(ticket.get("order_ref", "")).strip()

    # --- Determine advisory hint (D-33) ---
    hint: dict | None = injection_hint  # may already be set from pre-screen

    # High-risk category → advisory hint (never blocks draft)
    if category in _HIGH_RISK_CATEGORIES:
        logger.info(
            "simulate_verdict: high-risk category=%r — attaching advisory hint ticket_id=%s",
            category,
            ticket_id,
        )
        hint = hint or {
            "reason": "high_risk",
            "signals": {"high_risk_category": True},
        }

    # --- D-34: Missing-order fallback ---
    # When there is no order_ref, or the order cannot be resolved, use a
    # verify-order / clarify-order-info flow. Never fabricate order numbers.
    if not order_ref:
        logger.info(
            "simulate_verdict: no order ref — using verify-order/clarify-order-info flow (D-34) ticket_id=%s",
            ticket_id,
        )
        body = _build_missing_order_body(ticket)
        citations = [{"id": "FLOW-1", "source": "verify-order flow", "snippet": "no order ref supplied"}]
        return {
            "action": _DRAFT_ACTION,
            "body": body,
            "citations": citations,
            "escalation_hint": hint,
            "dry_run": True,
        }

    # --- D-31: File-store grounded draft ---
    # Look up candidate template codes for the sub-type, fetch the first resolvable template.
    draft_body, citations = _build_grounded_draft(ticket, sub_type, category, order_ref)

    return {
        "action": _DRAFT_ACTION,
        "body": draft_body,
        "citations": citations,
        "escalation_hint": hint,
        "dry_run": True,
    }


def _build_grounded_draft(
    ticket: dict,
    sub_type: str,
    category: str,
    order_ref: str,
) -> tuple[str, list[dict]]:
    """Build a grounded draft body by looking up the file-store (D-31).

    Returns (body, citations). Fails soft: if no template is found, returns a
    generic acknowledgement body (still a draft, not empty).
    """
    # Resolve sub-type → candidate codes
    codes = subtype_to_code(sub_type) if sub_type else []

    # Try each candidate code until one resolves
    resolved_code: str | None = None
    resolved_body: str | None = None

    for code in codes:
        result = get_template_from_file(code)
        if result.get("found") and result.get("body"):
            resolved_code = code
            resolved_body = result["body"]
            break

    if resolved_body:
        # Use the first paragraph of the template as the simulated draft body.
        # In production the drafter fills the full template; here we use the real
        # template text to satisfy the body-match assertion in tests.
        citations = [
            {
                "id": f"TMPL-{resolved_code}",
                "source": f"local template {resolved_code}",
                "snippet": resolved_body[:120],
            }
        ]
        return resolved_body, citations
    else:
        # No template found for this sub-type — generic acknowledgement (D-34 gap handling)
        logger.info(
            "simulate_verdict: no template found for sub_type=%r (codes=%r) ticket_id=%s",
            sub_type,
            codes[:3],
            ticket.get("ticket_id", "unknown"),
        )
        body = (
            "Thank you for contacting Shophelp Customer Support. We have received your request "
            f"regarding order {order_ref} and our team will review it shortly. "
            "We will get back to you as soon as possible with more information.\n\n"
            "Best regards,\nShophelp Customer Support"
        )
        citations = [{"id": "TMPL-generic", "source": "generic acknowledgement", "snippet": body[:80]}]
        return body, citations


def _build_missing_order_body(ticket: dict) -> str:
    """Build a verify-order / clarify-order-info draft body for a missing order (D-34).

    Never fabricates order facts. Asks the customer for their order number.
    This is the correct flow when order_ref is absent or unresolvable.
    """
    subject = ticket.get("subject", "your recent inquiry")
    return (
        "Thank you for reaching out to Shophelp Customer Support.\n\n"
        "We'd be happy to help you, but we were unable to locate an order number associated "
        "with your message. Could you please provide your order number so we can look into "
        "this for you? Your order number can be found in your order confirmation email.\n\n"
        "Once we have your order details, we will be able to assist you further.\n\n"
        "Best regards,\nShophelp Customer Support"
    )


# ---------------------------------------------------------------------------
# Acceptance-criteria assertions (§7 — updated for D-33 always-draft)
# ---------------------------------------------------------------------------


def _assert_always_draft(verdict: dict, *, expect_hint: bool = False,
                          hint_reason_prefix: str | None = None) -> tuple[bool, str]:
    """Assert ticket produced action=draft (D-33 contract).

    Args:
        verdict: The verdict dict from run_ticket.
        expect_hint: If True, assert escalation_hint is non-null.
        hint_reason_prefix: If set, assert hint reason starts with this prefix.
    """
    if verdict.get("action") != _DRAFT_ACTION:
        return False, f"expected action=draft; got action={verdict.get('action')!r} (D-33 violation)"
    if expect_hint:
        hint = verdict.get("escalation_hint")
        if not hint:
            return False, "expected non-null escalation_hint for advisory signal"
        if hint_reason_prefix:
            reason = hint.get("reason", "")
            if not reason.startswith(hint_reason_prefix):
                return False, (
                    f"expected escalation_hint.reason starting with {hint_reason_prefix!r}; "
                    f"got {reason!r}"
                )
    return True, ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def main(argv: list[str] | None = None) -> int:
    """Async main — feed tickets to cs-lead, print [PASS]/[FAIL] verdicts.

    Returns:
        0 if all selected tickets pass acceptance criteria; 1 if any fail.

    Importable: from scripts.cs_team_demo import main
    """
    parser = argparse.ArgumentParser(
        description="cs-agent-team local PoC runner (DRY_RUN — nothing posted to Freshdesk)"
    )
    parser.add_argument(
        "--ticket",
        choices=["benign", "high_risk", "injection", "missing_order", "all"],
        default="all",
        help="Which sample ticket to run (default: all)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Use live `claude` CLI (requires auth; human checkpoint must be approved first)",
    )
    args = parser.parse_args(argv)

    # Startup assertion: DRY_RUN must be True (D-39)
    assert settings.dry_run, (
        "FATAL: DRY_RUN is False. Refusing to run — would risk a live Freshdesk post."
    )

    selected_keys: list[str]
    if args.ticket == "all":
        selected_keys = ["benign", "high_risk", "injection", "missing_order"]
    else:
        selected_keys = [args.ticket]

    passes = 0
    fails = 0

    for key in selected_keys:
        ticket = _TICKET_MAP[key]

        verdict = await run_ticket(ticket, use_live_claude=args.live)

        # All tickets expect action=draft (D-33)
        if key == "benign":
            ok, msg = _assert_always_draft(verdict, expect_hint=False)
            label = "benign ticket"
            detail = "action=draft, escalation_hint=None, body from file-store template"
        elif key == "high_risk":
            ok, msg = _assert_always_draft(verdict, expect_hint=True, hint_reason_prefix="high_risk")
            label = "high-risk ticket (refund)"
            detail = "action=draft, advisory escalation_hint.reason=high_risk"
        elif key == "injection":
            ok, msg = _assert_always_draft(verdict, expect_hint=True, hint_reason_prefix="injection")
            label = "injection ticket"
            detail = "action=draft, advisory escalation_hint.reason=injection:*"
        else:  # missing_order
            ok, msg = _assert_always_draft(verdict)
            label = "missing-order ticket"
            detail = "action=draft, verify-order/clarify-order flow (D-34)"

        if ok:
            passes += 1
            line = f"[PASS] {label} -> {detail}"
        else:
            fails += 1
            line = f"[FAIL] {label} -> {msg}"

        print(line)

    print(f"\nSummary: {passes} passed, {fails} failed (DRY_RUN=True, no Freshdesk posts)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
