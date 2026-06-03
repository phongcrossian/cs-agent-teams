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

D-14 enforcement (injection pre-screen):
  - The ticket body is ALWAYS injection-screened via _pre_screen_ticket() at the very
    start of run_ticket(), BEFORE any CLI invocation or simulation branch.
  - This is the mandatory, non-bypassable D-14 entry gate for the runner.
  - On injection detection, run_ticket() returns an escalate verdict immediately
    and the `claude` CLI is NEVER invoked (no subagent sees the body).
  - Settings note: Claude Code does not expose a dedicated SubagentStart event in
    the installed version; the mandatory runner pre-screen above is therefore the
    enforced D-14 path on the deployed runner. The UserPromptSubmit binding in
    settings.json provides the gate for interactive/REPL sessions.

CS_RUN_ID lifecycle:
  - run_ticket() generates a unique CS_RUN_ID per invocation and exports it to
    os.environ before calling the CLI, so that settings.json-bound hook subprocesses
    inherit it via the "CS_RUN_ID": "${CS_RUN_ID}" env forwarding line.
  - A finally block deletes the per-run state file (best-effort) to honour the
    ephemeral lifecycle defined in escalation_gate.py.

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
import os
import re
import subprocess
import sys
import tempfile
import uuid
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
_has_commitment_term = _pre_send_guard_mod._has_commitment_term

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
# -p/--print = non-interactive mode (outputs response and exits); --output-format json
# for machine-parseable verdict output.
_CLAUDE_CLI = ["claude", "--print", "--output-format", "json"]

# Verdict schema expected from cs-lead
_DRAFT_ACTION = "draft"
_ESCALATE_ACTION = "escalate"

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

    Returns {"action": "escalate", "reason": "parse_error"} on failure (fail-closed).
    """
    # Primary path: unwrap the claude --output-format json envelope
    try:
        outer = json.loads(raw_output.strip())
        if isinstance(outer, dict) and "result" in outer:
            inner_str = outer["result"]
            if isinstance(inner_str, str):
                try:
                    inner = json.loads(inner_str.strip())
                    if "action" in inner and inner["action"] in (_DRAFT_ACTION, _ESCALATE_ACTION):
                        return inner
                except json.JSONDecodeError:
                    # inner might itself contain embedded JSON — fall through to scan
                    pass
            elif isinstance(inner_str, dict) and "action" in inner_str:
                return inner_str
    except json.JSONDecodeError:
        pass

    # Fallback: scan for last {"action": ...} object in raw output
    # Use a broader pattern that handles nested objects via json.loads
    raw = raw_output
    start = 0
    best: dict[str, Any] | None = None
    while True:
        idx = raw.find('"action"', start)
        if idx == -1:
            break
        # Walk back to find the opening brace
        brace_pos = raw.rfind("{", 0, idx)
        if brace_pos == -1:
            start = idx + 1
            continue
        # Try to parse from brace_pos onward with increasing length
        for end in range(len(raw), brace_pos, -1):
            try:
                obj = json.loads(raw[brace_pos:end])
                if isinstance(obj, dict) and obj.get("action") in (_DRAFT_ACTION, _ESCALATE_ACTION):
                    best = obj
                    break
            except json.JSONDecodeError:
                continue
        start = idx + 1

    if best is not None:
        return best

    logger.warning("cs_team_demo: could not parse verdict from output (fail-closed → escalate)")
    return {"action": _ESCALATE_ACTION, "reason": "parse_error", "signals": {}}


def _build_prompt(ticket: dict) -> str:
    """Build the cs-lead prompt for a single ticket (wrapped as untrusted data per D-14).

    CR-03 / D-14: ALL attacker-controllable fields (subject, order_ref, body)
    are PII-redacted AND wrapped in untrusted-data boundary tags so the model
    cannot be confused about what is trusted system context vs. ticket input.
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
        "Reply with exactly ONE JSON object:\n"
        '  draft:    {"action": "draft", "body": "...", "citations": [{"id": "KB-1", ...}]}\n'
        '  escalate: {"action": "escalate", "reason": "...", "signals": {...}}\n'
    )


# ---------------------------------------------------------------------------
# Pre-screen helper — D-14 mandatory entry gate
# ---------------------------------------------------------------------------


def _pre_screen_ticket(ticket: dict) -> tuple[bool, str]:
    """Run injection_screen on ALL attacker-controllable ticket fields BEFORE sending to cs-lead.

    This is the MANDATORY, NON-BYPASSABLE D-14 entry gate for the runner.
    It runs unconditionally at the very start of run_ticket(), before any
    branch (CLI path or simulation path). On a positive detection the caller
    returns an escalate verdict immediately — the CLI is never invoked and
    no subagent ever sees the fields.

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


def _post_screen_draft(draft_body: str, citations: list[dict]) -> tuple[bool, str]:
    """Run commitment-language + grounding checks on the draft body.

    Mirrors the PreToolUse hook chain (grounding_check → pre_send_guard).
    Returns (should_escalate: bool, reason: str).
    """
    # Grounding check first (D-11)
    grounded, reason = check_grounding(draft_body, citations)
    if not grounded:
        return True, reason
    # Commitment language tripwire (D-26) — bare commitment term with no offer block → escalate
    if _has_commitment_term(draft_body):
        return True, "unauthorized:commitment_without_offer"
    return False, ""


_SAFE_RUN_ID_RE = re.compile(r'^[A-Za-z0-9_\-]{1,128}$')


def _sanitize_ticket_id(ticket_id: str) -> str:
    """Sanitize ticket_id for safe use in CS_RUN_ID (CR-02 path-traversal guard).

    Strips any character outside [A-Za-z0-9_-] and truncates to 64 chars.
    Falls back to "unknown" if the result is empty.
    """
    sanitized = re.sub(r'[^A-Za-z0-9_\-]', '', ticket_id)[:64]
    return sanitized if sanitized else "unknown"


def _state_file_path(run_id: str) -> Path:
    """Return the per-run state file path for *run_id* (mirrors escalation_gate.py).

    CR-02: run_id is validated against _SAFE_RUN_ID_RE before path construction.
    Returns a path in a fallback "invalid" slot if run_id fails validation
    (should never happen since callers sanitize ticket_id before building run_id).
    """
    if not _SAFE_RUN_ID_RE.match(run_id):
        # Defensive: return a deterministic safe path that won't escape cs_run_state/
        run_id = "invalid"
    return Path(tempfile.gettempdir()) / "cs_run_state" / f"{run_id}.json"


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
        - Injection pre-screen runs unconditionally before any CLI or simulation
          branch (D-14 mandatory non-bypassable gate).
        - CS_RUN_ID exported so settings.json-bound hook subprocesses share state
          with the stateful escalation_gate veto (CR-02 / SAFE-03).
    """
    # Safety assertion: DRY_RUN must always be True in this phase
    assert settings.dry_run, (
        "FATAL: settings.dry_run is False — aborting to prevent accidental Freshdesk post."
    )

    ticket_id = ticket.get("ticket_id", "unknown")
    redacted_subject = redact_text(ticket.get("subject", ""))

    # D-14 MANDATORY PRE-SCREEN — runs unconditionally before any branch.
    # This is the enforced non-bypassable entry gate: if injection is detected,
    # we return escalate immediately and the CLI is never invoked.
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

    # Generate a unique CS_RUN_ID for this ticket run and export it so that
    # settings.json-bound escalation_gate hook subprocesses share the same
    # per-run state file (CR-02 / SAFE-03).
    # CR-02: sanitize ticket_id before embedding in the run_id path component.
    safe_ticket_id = _sanitize_ticket_id(str(ticket_id))
    run_id = f"{safe_ticket_id}-{uuid.uuid4().hex[:8]}"
    os.environ["CS_RUN_ID"] = run_id
    state_file = _state_file_path(run_id)

    try:
        if use_live_claude:
            # Live path: shell out to `claude` CLI (requires human checkpoint approval + auth)
            return await _run_via_claude_cli(ticket, redacted_subject)
        else:
            # Simulation path: apply hook logic locally (CI / DRY_RUN; no real LLM)
            return _simulate_verdict(ticket)
    finally:
        # Best-effort cleanup: remove the per-run state file to honour the
        # ephemeral lifecycle defined in escalation_gate.py state-file design.
        try:
            if state_file.exists():
                state_file.unlink()
        except OSError:
            pass
        # Remove CS_RUN_ID from env so it does not leak into the next call
        os.environ.pop("CS_RUN_ID", None)


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

    CR-04: High-risk detection is based on ticket *category/metadata*, NOT on
    commitment-language scan of the ticket body. In production, pre_send_guard.py
    checks commitment language only on the *draft* body — never on the inbound
    ticket. Checking `check_commitment_language(ticket_body)` here was a
    simulation divergence: it caused false escalations when a customer *mentioned*
    words like "refund" in their message, while missing commitment language
    injected into a mock draft. The correct production-aligned flow is:
      1. Check ticket category/metadata for known high-risk labels.
      2. Generate a mock draft.
      3. Run _post_screen_draft (grounding + commitment-language) on the DRAFT.
    """
    ticket_id = ticket.get("ticket_id", "unknown")

    # HIGH_RISK: use ticket category/metadata, not commitment-language scan on body.
    # This mirrors production: high-risk routing is a classifier decision based on
    # category, not a regex scan of what the customer wrote.
    _HIGH_RISK_CATEGORIES = frozenset({
        "refund", "money", "legal", "complaint", "complex", "exchange",
        "chargeback", "dispute",
    })
    category = str(ticket.get("category", "")).lower().strip()
    if category in _HIGH_RISK_CATEGORIES:
        logger.info(
            "simulate_verdict: high-risk category=%r — escalating ticket_id=%s",
            category,
            ticket_id,
        )
        return {
            "action": _ESCALATE_ACTION,
            "reason": "escalate:high_risk_category",
            "signals": {"high_risk_category": True},
        }

    # BENIGN: produce a minimal mock draft (the real LLM would produce this).
    # Draft must pass the hook chain: citations present + no commitment language.
    mock_citations = [{"id": "KB-1", "text": "Order status policy [KB-1]"}]
    mock_draft = (
        "Thank you for contacting us about your order. "
        "Based on our records [KB-1], your order is currently being processed. "
        "You will receive a shipping confirmation shortly.\n\n"
        "Best regards,\nCustomer Support"
    )

    # CR-04: Post-screen the DRAFT body through the real hook functions.
    # This is where commitment-language and grounding checks belong — on the
    # draft output, not on the inbound ticket body.
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
    if _has_commitment_term(body):
        return False, "commitment language found in draft (D-26 tripwire)"
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
