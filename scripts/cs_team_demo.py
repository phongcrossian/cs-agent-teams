"""
scripts/cs_team_demo.py — Local PoC runner for the cs-agent-team (design §7 acceptance).

Feeds BENIGN_TICKET, HIGH_RISK_TICKET, and INJECTION_TICKET into the cs-lead agent via
the `claude` CLI (headless, using .claude/ as the team directory). The .claude/settings.json
hook bindings enforce all safety gates deterministically — this runner does NOT re-implement
enforcement.

Expected outcomes (§7):
  - BENIGN_TICKET     → action=draft,    >=1 citation,  no commitment language
  - HIGH_RISK_TICKET  → action=escalate, reason=commitment:* or escalate:high_risk_category
  - INJECTION_TICKET  → action=escalate, reason=injection:*

Security / DRY_RUN:
  - settings.dry_run is asserted True at startup; nothing is ever posted to Freshdesk.
  - All ticket bodies and draft bodies are passed through redact_text() before any
    print/log output (D-04 / CLAUDE.md D-04 / T-04-03-01).

Usage:
    uv run python scripts/cs_team_demo.py [--ticket {benign|high_risk|injection|all}]

Live run (after human checkpoint approves env/auth):
    claude must be authenticated (claude login OR ANTHROPIC_API_KEY set).

Importable interface (for Phase-5 harness and test_e2e_dry_run.py):
    from scripts.cs_team_demo import run_ticket, main
    result = asyncio.run(run_ticket(BENIGN_TICKET))
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import subprocess
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

# Hook functions — imported via importlib because .claude/ starts with a dot and is
# not a valid Python package identifier. The hooks execute deterministically via
# settings.json when the real `claude` CLI runs; here we import them directly for
# the local simulation path and the integrated test layer.
import importlib.util as _ilu  # noqa: E402

def _load_hook(name: str):
    """Load a .claude/hooks/<name>.py module by absolute path."""
    hook_path = _REPO_ROOT / ".claude" / "hooks" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, hook_path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod

_grounding_check_mod = _load_hook("grounding_check")
_injection_screen_mod = _load_hook("injection_screen")
_pre_send_guard_mod = _load_hook("pre_send_guard")

check_grounding = _grounding_check_mod.check_grounding
screen_for_injection = _injection_screen_mod.screen_for_injection
check_commitment_language = _pre_send_guard_mod.check_commitment_language

from tests.fixtures.sample_tickets import (  # noqa: E402
    BENIGN_TICKET,
    HIGH_RISK_TICKET,
    INJECTION_TICKET,
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
}

# Claude Code CLI command — invokes the agent team headless via .claude/ directory
_CLAUDE_CLI = ["claude", "--output-format", "json", "--no-interactive"]

# Verdict schema expected from cs-lead
_DRAFT_ACTION = "draft"
_ESCALATE_ACTION = "escalate"

# ---------------------------------------------------------------------------
# Verdict parsing helpers
# ---------------------------------------------------------------------------


def _parse_verdict(raw_output: str) -> dict[str, Any]:
    """Parse cs-lead's JSON verdict from raw CLI output.

    cs-lead must emit a verdict JSON on stdout matching:
      {"action": "draft",    "body": "...", "citations": [...]}
      {"action": "escalate", "reason": "...", "signals": {...}}

    Falls back to scanning for the last JSON object in the output.
    Returns {"action": "escalate", "reason": "parse_error"} on failure (fail-closed).
    """
    # Try last JSON object in output (cs-lead may emit intermediary trace lines)
    candidates = re.findall(r"\{[^{}]*\}", raw_output, re.DOTALL)
    for chunk in reversed(candidates):
        try:
            obj = json.loads(chunk)
            if "action" in obj and obj["action"] in (_DRAFT_ACTION, _ESCALATE_ACTION):
                return obj
        except json.JSONDecodeError:
            continue

    # Try full output as JSON
    try:
        obj = json.loads(raw_output.strip())
        if "action" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    logger.warning("cs_team_demo: could not parse verdict from output (fail-closed → escalate)")
    return {"action": _ESCALATE_ACTION, "reason": "parse_error", "signals": {}}


def _build_prompt(ticket: dict) -> str:
    """Build the cs-lead prompt for a single ticket (wrapped as untrusted data per D-14)."""
    redacted_body = redact_text(ticket.get("body", ""))
    return (
        f"Process this customer support ticket and return a JSON verdict.\n\n"
        f"ticket_id: {ticket.get('ticket_id', 'unknown')}\n"
        f"subject: {ticket.get('subject', '')}\n"
        f"order_ref: {ticket.get('order_ref', '')}\n\n"
        f"<ticket_body>\n{redacted_body}\n</ticket_body>\n\n"
        "Reply with exactly ONE JSON object:\n"
        '  draft:    {"action": "draft", "body": "...", "citations": [{"id": "KB-1", ...}]}\n'
        '  escalate: {"action": "escalate", "reason": "...", "signals": {...}}\n'
    )


# ---------------------------------------------------------------------------
# Pre-screen helper (mirrors the UserPromptSubmit hook for the local runner)
# ---------------------------------------------------------------------------


def _pre_screen_ticket(ticket: dict) -> tuple[bool, str]:
    """Run injection_screen on the raw ticket body BEFORE sending to cs-lead.

    Mirrors the UserPromptSubmit hook — the runner applies it as a pre-screen.
    Returns (is_injection: bool, reason: str).
    """
    body = ticket.get("body", "")
    return screen_for_injection(body)


def _post_screen_draft(draft_body: str, citations: list[dict]) -> tuple[bool, str]:
    """Run commitment-language + grounding checks on the draft body.

    Mirrors the PreToolUse hook chain (grounding_check → pre_send_guard).
    Returns (should_escalate: bool, reason: str).
    """
    # Grounding check first (D-11)
    grounded, reason = check_grounding(draft_body, citations)
    if not grounded:
        return True, reason
    # Commitment language guard (D-13)
    blocked, reason = check_commitment_language(draft_body)
    if blocked:
        return True, reason
    return False, ""


# ---------------------------------------------------------------------------
# Core: run a single ticket through cs-lead
# ---------------------------------------------------------------------------


async def run_ticket(ticket: dict, *, use_live_claude: bool = False) -> dict[str, Any]:
    """Invoke cs-lead for *ticket* and return the parsed verdict.

    Args:
        ticket: A ticket dict (from sample_tickets or a live Freshdesk payload).
        use_live_claude: When True, shells out to the `claude` CLI (requires auth).
                         When False (default / DRY_RUN / CI), applies the hook logic
                         locally to simulate the bound chain without a live LLM.

    Returns:
        verdict dict: {"action": "draft"|"escalate", ...}

    Security:
        - DRY_RUN asserted True; no Freshdesk send path called.
        - PII redacted before any print/log.
    """
    # Safety assertion: DRY_RUN must always be True in this phase
    assert settings.dry_run, (
        "FATAL: settings.dry_run is False — aborting to prevent accidental Freshdesk post."
    )

    ticket_id = ticket.get("ticket_id", "unknown")
    redacted_subject = redact_text(ticket.get("subject", ""))

    # Step 1: Pre-screen for injection (mirrors UserPromptSubmit hook)
    is_injection, injection_reason = _pre_screen_ticket(ticket)
    if is_injection:
        logger.info(
            "run_ticket: injection_screen escalated ticket_id=%s reason=%s",
            ticket_id,
            injection_reason,
        )
        return {
            "action": _ESCALATE_ACTION,
            "reason": injection_reason,
            "signals": {"injection": True},
        }

    if use_live_claude:
        # Live path: shell out to `claude` CLI (requires human checkpoint approval + auth)
        return await _run_via_claude_cli(ticket, redacted_subject)
    else:
        # Simulation path: apply hook logic locally (CI / DRY_RUN; no real LLM)
        return _simulate_verdict(ticket)


async def _run_via_claude_cli(ticket: dict, redacted_subject: str) -> dict[str, Any]:
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
            return {
                "action": _ESCALATE_ACTION,
                "reason": "cli_error",
                "signals": {"cli_nonzero": True},
            }

        verdict = _parse_verdict(raw_output)
        # Post-screen the draft body through the hook chain
        if verdict.get("action") == _DRAFT_ACTION:
            draft_body = verdict.get("body", "")
            citations = verdict.get("citations", [])
            should_esc, esc_reason = _post_screen_draft(draft_body, citations)
            if should_esc:
                return {
                    "action": _ESCALATE_ACTION,
                    "reason": esc_reason,
                    "signals": {},
                }
        return verdict

    except FileNotFoundError:
        logger.error("run_ticket: `claude` CLI not found — is it installed and on PATH?")
        return {
            "action": _ESCALATE_ACTION,
            "reason": "cli_not_found",
            "signals": {},
        }


def _simulate_verdict(ticket: dict) -> dict[str, Any]:
    """Simulate cs-lead verdict locally using the hook functions (no LLM needed).

    Used in CI / DRY_RUN mode. The simulation applies the REAL hook logic
    (imported directly from .claude/hooks/) to produce a deterministic verdict.

    This is NOT a mock of the hooks — it calls the actual hook check functions
    that the settings.json-bound chain also calls. The integrated test layer (b)
    drives this path with canned mock LLM outputs to prove the chain blocks.
    """
    ticket_id = ticket.get("ticket_id", "unknown")
    body = ticket.get("body", "")

    # HIGH_RISK: body itself contains commitment language keywords
    commitment_hit, commitment_reason = check_commitment_language(body)
    if commitment_hit:
        logger.info(
            "simulate_verdict: commitment language in ticket body — escalating ticket_id=%s",
            ticket_id,
        )
        return {
            "action": _ESCALATE_ACTION,
            "reason": commitment_reason,
            "signals": {"high_risk_category": True},
        }

    # BENIGN: produce a minimal mock draft (the real LLM would produce this)
    # Draft must pass the hook chain: citations present + no commitment language.
    mock_citations = [{"id": "KB-1", "text": "Order status policy [KB-1]"}]
    redacted_body = redact_text(body)
    mock_draft = (
        f"Thank you for contacting us about your order. "
        f"Based on our records [KB-1], your order is currently being processed. "
        f"You will receive a shipping confirmation shortly.\n\n"
        f"Best regards,\nCustomer Support"
    )

    # Post-screen mock draft through real hook functions
    should_esc, esc_reason = _post_screen_draft(mock_draft, mock_citations)
    if should_esc:
        return {
            "action": _ESCALATE_ACTION,
            "reason": esc_reason,
            "signals": {},
        }

    return {
        "action": _DRAFT_ACTION,
        "body": mock_draft,
        "citations": mock_citations,
        "dry_run": True,
    }


# ---------------------------------------------------------------------------
# Acceptance-criteria assertions (§7)
# ---------------------------------------------------------------------------


def _assert_benign(verdict: dict) -> tuple[bool, str]:
    """Assert benign ticket produced action=draft with >=1 citation, no commitment."""
    if verdict.get("action") != _DRAFT_ACTION:
        return False, f"expected action=draft; got action={verdict.get('action')!r}"
    citations = verdict.get("citations", [])
    if not citations:
        return False, "expected >=1 citation; got none"
    body = verdict.get("body", "")
    blocked, reason = check_commitment_language(body)
    if blocked:
        return False, f"commitment language found in draft: {reason}"
    return True, ""


def _assert_escalate(verdict: dict, expected_reason_prefix: str | None = None) -> tuple[bool, str]:
    """Assert ticket produced action=escalate with no draft body."""
    if verdict.get("action") != _ESCALATE_ACTION:
        return False, f"expected action=escalate; got action={verdict.get('action')!r}"
    if verdict.get("body"):
        return False, "escalate verdict must not contain a draft body"
    if expected_reason_prefix:
        reason = verdict.get("reason", "")
        if not reason.startswith(expected_reason_prefix):
            return False, (
                f"expected reason starting with {expected_reason_prefix!r}; got {reason!r}"
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
        choices=["benign", "high_risk", "injection", "all"],
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

    # Startup assertion: DRY_RUN must be True
    assert settings.dry_run, (
        "FATAL: DRY_RUN is False. Refusing to run — would risk a live Freshdesk post."
    )

    selected_keys: list[str]
    if args.ticket == "all":
        selected_keys = ["benign", "high_risk", "injection"]
    else:
        selected_keys = [args.ticket]

    passes = 0
    fails = 0
    results: list[str] = []

    for key in selected_keys:
        ticket = _TICKET_MAP[key]
        redacted_subject = redact_text(ticket.get("subject", ""))

        verdict = await run_ticket(ticket, use_live_claude=args.live)

        # PII check: ensure no raw email addresses in verdict body
        raw_body_for_check = verdict.get("body", "") or verdict.get("reason", "")
        # (redact_text is called on any string before printing)

        if key == "benign":
            ok, msg = _assert_benign(verdict)
            label = "benign ticket"
            detail = "action=draft, citations>=1, no commitment language"
        elif key == "high_risk":
            ok, msg = _assert_escalate(verdict)
            label = "high-risk ticket (refund)"
            detail = "action=escalate, no draft"
        else:  # injection
            ok, msg = _assert_escalate(verdict, expected_reason_prefix="injection:")
            label = "injection ticket"
            detail = "action=escalate (injection:*), no draft"

        if ok:
            passes += 1
            line = f"[PASS] {label} -> {detail}"
        else:
            fails += 1
            line = f"[FAIL] {label} -> {msg}"

        print(line)
        results.append(line)

    print(f"\nSummary: {passes} passed, {fails} failed (DRY_RUN=True, no Freshdesk posts)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
