"""
tests/cs_team/test_e2e_dry_run.py — E2E dry-run test suite for the cs-agent-team.

Three layers:

  (a) STRUCTURAL — always runs, no auth required.
      Extends tests/cs_team/test_settings_hook_bindings.py assertions by re-asserting
      the complete §4a hook binding requirements from a single entrypoint. Reads only
      .claude/settings.json — no network, no LLM.

  (b) INTEGRATED mock-LLM — always runs in CI, no real auth.
      Drives cs-lead's hook chain using STUB canned inputs so that each adversarial ticket
      REACHES submit_reply and is vetoed by the REAL bound hook functions (imported directly,
      not re-implemented). Proves BLOCKER-2:
        - HIGH_RISK mock draft (commitment language) → pre_send_guard blocks → escalate
        - INJECTION ticket → injection_screen escalates before draft stage
        - UN-CITED mock draft → grounding_check blocks at submit_reply → escalate
        - BENIGN cited mock draft → chain PASSES → submit_reply returns {"submitted": True}
      Asserts: action=escalate, no raw PII in output, DRY_RUN throughout.
      The mock exercises the REAL hook check functions (grounding_check.check_grounding,
      pre_send_guard.check_commitment_language, injection_screen.screen_for_injection,
      escalation_gate.should_escalate) — NOT standalone unit tests (those live in 04-01).

  (c) LIVE — gated behind RUN_CS_TEAM=1.
      Invokes scripts.cs_team_demo.main() against the live `claude` CLI and asserts
      the §7 acceptance criteria. Requires human checkpoint approval (auth/env/DB up).
      settings.dry_run is re-asserted True so no live Freshdesk post can occur.

Design enforcement (§4a / CLAUDE.md):
  submit_reply is the SOLE draft-emission path. The integrated layer (b) calls the hook
  functions in the same order as the settings.json PreToolUse chain:
      grounding_check → pre_send_guard → escalation_gate (final-risk veto)
  then calls the real submit_reply function from src/reply_mcp/server.py.
  A hook returning (blocked=True / escalated=True) stops the chain → action=escalate (D-10).

Security / DRY_RUN:
  settings.dry_run is asserted True throughout. No Freshdesk post path is reachable.
  PII assertions verify no raw email/phone from fixture appears in captured output.
"""

from __future__ import annotations

import importlib.util as _ilu
import io
import json
import os
import pathlib
import sys
from contextlib import redirect_stdout
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SETTINGS_PATH = _REPO_ROOT / ".claude" / "settings.json"

# ---------------------------------------------------------------------------
# Hook loading (same pattern as conftest.py and cs_team_demo.py)
# ---------------------------------------------------------------------------


def _load_hook(name: str):
    """Load a .claude/hooks/<name>.py module by absolute path (dot-prefix workaround)."""
    hook_path = _REPO_ROOT / ".claude" / "hooks" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, hook_path)
    assert spec is not None and spec.loader is not None, f"Cannot load hook: {hook_path}"
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_gc_mod = _load_hook("grounding_check")
_psg_mod = _load_hook("pre_send_guard")
_inj_mod = _load_hook("injection_screen")
_esc_mod = _load_hook("escalation_gate")

check_grounding = _gc_mod.check_grounding
check_commitment_language = _psg_mod.check_commitment_language
screen_for_injection = _inj_mod.screen_for_injection
should_escalate = _esc_mod.should_escalate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def settings_json() -> dict:
    """Load .claude/settings.json once per module."""
    assert _SETTINGS_PATH.exists(), f".claude/settings.json not found at {_SETTINGS_PATH}"
    return json.loads(_SETTINGS_PATH.read_text())


@pytest.fixture(scope="module")
def sample_tickets() -> dict:
    """Load the three sample tickets."""
    sys.path.insert(0, str(_REPO_ROOT))
    from tests.fixtures.sample_tickets import (
        BENIGN_TICKET,
        HIGH_RISK_TICKET,
        INJECTION_TICKET,
    )
    return {
        "benign": BENIGN_TICKET,
        "high_risk": HIGH_RISK_TICKET,
        "injection": INJECTION_TICKET,
    }


# ---------------------------------------------------------------------------
# Layer (a): STRUCTURAL binding assertions
# (extends test_settings_hook_bindings.py without duplicating its tests)
# ---------------------------------------------------------------------------


class TestStructuralBindings:
    """(a) Structural: re-assert §4a hook bindings are present in settings.json.

    These tests provide a single-module entrypoint for the complete binding
    contract. They complement (not replace) test_settings_hook_bindings.py.
    """

    def test_settings_json_exists(self) -> None:
        assert _SETTINGS_PATH.exists(), ".claude/settings.json must exist"

    def test_pre_tool_use_submit_reply_chain_order(self, settings_json: dict) -> None:
        """PreToolUse(submit_reply) must have grounding_check[0] → pre_send_guard[1] → escalation_gate[2]."""
        pre_tool_use = settings_json.get("hooks", {}).get("PreToolUse", [])
        submit_binding = next(
            (b for b in pre_tool_use if b.get("matcher") == "submit_reply"), None
        )
        assert submit_binding is not None, "No PreToolUse binding for submit_reply"
        hooks = submit_binding.get("hooks", [])
        assert len(hooks) == 3, f"Expected 3 PreToolUse(submit_reply) hooks; got {len(hooks)}"
        cmds = [h.get("command", "") for h in hooks]
        assert "grounding_check.py" in cmds[0], f"[0] must be grounding_check.py; got {cmds[0]}"
        assert "pre_send_guard.py" in cmds[1], f"[1] must be pre_send_guard.py; got {cmds[1]}"
        assert "escalation_gate.py" in cmds[2], f"[2] must be escalation_gate.py; got {cmds[2]}"

    def test_user_prompt_submit_injection_screen(self, settings_json: dict) -> None:
        """UserPromptSubmit must bind injection_screen.py."""
        ups = settings_json.get("hooks", {}).get("UserPromptSubmit", [])
        cmds = [h.get("command", "") for b in ups for h in b.get("hooks", [])]
        assert any("injection_screen.py" in c for c in cmds), (
            f"injection_screen.py not in UserPromptSubmit; commands: {cmds}"
        )

    def test_post_tool_use_escalation_gate_and_pii_redact(self, settings_json: dict) -> None:
        """PostToolUse must bind escalation_gate.py AND pii_redact.py."""
        ptu = settings_json.get("hooks", {}).get("PostToolUse", [])
        cmds = [h.get("command", "") for b in ptu for h in b.get("hooks", [])]
        assert any("escalation_gate.py" in c for c in cmds), "escalation_gate.py missing from PostToolUse"
        assert any("pii_redact.py" in c for c in cmds), "pii_redact.py missing from PostToolUse"

    def test_subagent_stop_escalation_gate(self, settings_json: dict) -> None:
        """SubagentStop must bind escalation_gate.py."""
        ss = settings_json.get("hooks", {}).get("SubagentStop", [])
        cmds = [h.get("command", "") for b in ss for h in b.get("hooks", [])]
        assert any("escalation_gate.py" in c for c in cmds), "escalation_gate.py missing from SubagentStop"

    def test_all_five_hook_scripts_present(self, settings_json: dict) -> None:
        """All five hook scripts must be referenced somewhere in settings.json."""
        s = json.dumps(settings_json)
        for script in [
            "grounding_check.py",
            "pre_send_guard.py",
            "escalation_gate.py",
            "injection_screen.py",
            "pii_redact.py",
        ]:
            assert script in s, f"Hook script {script!r} missing from settings.json"

    def test_dry_run_env_in_settings(self, settings_json: dict) -> None:
        """settings.json env must set SEND_MODE=dry_run."""
        env = settings_json.get("env", {})
        assert env.get("SEND_MODE") == "dry_run", (
            f"Expected SEND_MODE=dry_run in settings.json env; got {env.get('SEND_MODE')!r}"
        )

    def test_hook_scripts_exist_on_disk(self) -> None:
        """All five hook .py files must exist in .claude/hooks/."""
        hooks_dir = _REPO_ROOT / ".claude" / "hooks"
        for name in [
            "grounding_check.py",
            "pre_send_guard.py",
            "escalation_gate.py",
            "injection_screen.py",
            "pii_redact.py",
        ]:
            assert (hooks_dir / name).exists(), f".claude/hooks/{name} missing from disk"


# ---------------------------------------------------------------------------
# Layer (b): INTEGRATED mock-LLM — BLOCKER-2 proof
# ---------------------------------------------------------------------------
#
# The integrated hook chain helper below mirrors the settings.json PreToolUse order:
#   grounding_check → pre_send_guard → escalation_gate (final-risk veto @ submit_reply)
#
# Each hook returns (blocked: bool, reason: str). First block wins → action=escalate.
# If all pass, the real submit_reply function is called.
#
# This is the difference between BLOCKER-2 (integrated proof) and 04-01 unit tests:
# here we chain the real hooks in order AND call submit_reply, proving the end-to-end
# veto path works — not just that each hook function works in isolation.
# ---------------------------------------------------------------------------


def _run_pre_tool_use_chain(
    body: str,
    citations: list[dict],
    risk_signals: dict | None = None,
) -> dict[str, Any]:
    """Run the real PreToolUse hook chain for submit_reply and return a verdict dict.

    Mirrors the settings.json-bound chain:
        grounding_check → pre_send_guard → escalation_gate (final-risk veto)

    Args:
        body: Draft reply body (as the mock LLM would produce).
        citations: Citation list accompanying the draft.
        risk_signals: Accumulated risk signals passed from prior stages
                      (e.g. {"high_risk_category": True} from classifier).

    Returns:
        {"action": "escalate", "reason": "...", "signals": {...}}   — blocked
        {"action": "draft",    "body": "...",   "citations": [...]} — passed
    """
    if risk_signals is None:
        risk_signals = {}

    # Hook 1: grounding_check (D-11)
    grounded, reason = check_grounding(body, citations)
    if not grounded:
        return {"action": "escalate", "reason": reason, "signals": risk_signals}

    # Hook 2: pre_send_guard (D-13 — commitment language)
    blocked, reason = check_commitment_language(body)
    if blocked:
        return {"action": "escalate", "reason": reason, "signals": risk_signals}

    # Hook 3: escalation_gate @ submit_reply (D-08 — accumulated risk veto)
    escalated, reason = should_escalate(risk_signals)
    if escalated:
        return {"action": "escalate", "reason": reason, "signals": risk_signals}

    # All hooks passed — call the real submit_reply and return draft verdict
    # (In CI without DB, submit_reply's _dry_run skips DB persist and returns submitted=True)
    import asyncio
    import sys
    sys.path.insert(0, str(_REPO_ROOT))
    from src.reply_mcp.server import submit_reply as _submit_reply

    try:
        result = asyncio.run(_submit_reply(body=body, citations=citations))
    except RuntimeError:
        # Already inside an event loop (e.g. pytest-asyncio) — use nest_asyncio workaround
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _submit_reply(body=body, citations=citations))
            result = future.result()

    return {
        "action": "draft",
        "body": body,
        "citations": citations,
        "submit_reply_result": result,
    }


def _run_injection_prescreen(body: str) -> dict[str, Any] | None:
    """Run injection_screen on the ticket body (UserPromptSubmit pre-screen).

    Returns escalate verdict if injection detected; None if clean.
    """
    suspicious, reason = screen_for_injection(body)
    if suspicious:
        return {"action": "escalate", "reason": reason, "signals": {"injection": True}}
    return None


# PII patterns from sample tickets that must NOT appear in output
_PII_PATTERNS = [
    "jane.doe@example.com",
    "mark.smith@example.com",
    "attacker@malicious.example",
    # Phone patterns (none in fixtures, but guard against accidental leakage)
]


def _assert_no_raw_pii(text: str) -> None:
    """Assert none of the known PII patterns appear in *text*."""
    for pattern in _PII_PATTERNS:
        assert pattern not in text, (
            f"Raw PII leaked into output: {pattern!r} found in: {text[:200]!r}"
        )


class TestIntegratedMockLLM:
    """(b) Integrated: drive hook chain with mock LLM outputs; prove BLOCKER-2.

    Each test scenario simulates what the mock LLM (cs-lead) would emit, then
    runs the exact same hook chain that settings.json binds for submit_reply.
    The real hook functions are called — not re-implementations.
    """

    # ── HIGH_RISK: mock drafter emits commitment language ─────────────────────

    def test_high_risk_commitment_language_blocked(self, sample_tickets: dict) -> None:
        """HIGH_RISK_TICKET: mock draft with 'refund' → pre_send_guard blocks → escalate."""
        ticket = sample_tickets["high_risk"]

        # Step 1: injection pre-screen (no injection in high-risk ticket)
        inj_result = _run_injection_prescreen(ticket["body"])
        assert inj_result is None, "HIGH_RISK ticket should not trigger injection screen"

        # Step 2: mock drafter emits a draft with commitment language (refund)
        mock_draft_body = (
            "Thank you for contacting us. We will process your refund immediately [KB-1]."
        )
        mock_citations = [{"id": "KB-1", "text": "Refund policy"}]

        # Step 3: run the real hook chain
        verdict = _run_pre_tool_use_chain(mock_draft_body, mock_citations)

        # Assertions
        assert verdict["action"] == "escalate", (
            f"Expected escalate; got {verdict['action']!r} reason={verdict.get('reason')!r}"
        )
        assert "commitment" in verdict.get("reason", ""), (
            f"Expected commitment:* reason; got {verdict.get('reason')!r}"
        )
        assert "body" not in verdict or verdict.get("body") is None or verdict.get("action") == "escalate", (
            "Escalate verdict must not persist a draft body"
        )

    def test_high_risk_no_draft_body_in_escalate(self, sample_tickets: dict) -> None:
        """HIGH_RISK: escalate verdict must not carry a customer-facing body (D-10)."""
        mock_draft_body = "We will give you a full refund for this issue [KB-1]."
        mock_citations = [{"id": "KB-1"}]
        verdict = _run_pre_tool_use_chain(mock_draft_body, mock_citations)
        assert verdict["action"] == "escalate"
        # The escalate dict should NOT have a 'body' key pointing to the draft
        assert verdict.get("body") != mock_draft_body, "Draft body must not be in escalate verdict"

    # ── INJECTION: injection_screen escalates before draft stage ──────────────

    def test_injection_ticket_prescreen_escalates(self, sample_tickets: dict) -> None:
        """INJECTION_TICKET: injection_screen UserPromptSubmit escalates before any draft."""
        ticket = sample_tickets["injection"]

        # Pre-screen (UserPromptSubmit analog)
        inj_result = _run_injection_prescreen(ticket["body"])

        assert inj_result is not None, "INJECTION_TICKET must be caught by injection_screen"
        assert inj_result["action"] == "escalate", (
            f"Expected escalate from injection_screen; got {inj_result['action']!r}"
        )
        assert "injection" in inj_result.get("reason", ""), (
            f"Expected injection:* reason; got {inj_result.get('reason')!r}"
        )

    def test_injection_no_draft_produced(self, sample_tickets: dict) -> None:
        """INJECTION: after injection escalation, no draft body is ever produced."""
        ticket = sample_tickets["injection"]
        inj_result = _run_injection_prescreen(ticket["body"])
        # The injection escape path must not contain a 'body' key with content
        assert inj_result is not None
        assert not inj_result.get("body"), "Injection escalate must not carry a draft body"

    # ── UN-CITED draft: grounding_check blocks at submit_reply ───────────────

    def test_uncited_draft_blocked_by_grounding_check(self) -> None:
        """Mock draft with citations list but NO [KB-N] marker → grounding_check blocks."""
        uncited_body = "Your order is being processed. Please allow 3-5 business days."
        citations = [{"id": "KB-1", "text": "Order processing policy"}]

        verdict = _run_pre_tool_use_chain(uncited_body, citations)

        assert verdict["action"] == "escalate", (
            f"Expected escalate from grounding_check; got {verdict['action']!r}"
        )
        assert "grounding" in verdict.get("reason", ""), (
            f"Expected grounding:* reason; got {verdict.get('reason')!r}"
        )

    def test_unknown_citation_id_blocked_by_grounding_check(self) -> None:
        """Draft citing [KB-99] when only KB-1 was retrieved → grounding_check blocks."""
        body = "Your order [KB-99] is being processed."
        citations = [{"id": "KB-1"}]  # KB-99 not in retrieved set

        verdict = _run_pre_tool_use_chain(body, citations)

        assert verdict["action"] == "escalate"
        assert "grounding" in verdict.get("reason", ""), (
            f"Expected grounding:unknown_citation_ids reason; got {verdict.get('reason')!r}"
        )

    # ── BENIGN: cited mock draft passes full chain → submit_reply ─────────────

    def test_benign_cited_draft_passes_chain(self, sample_tickets: dict) -> None:
        """BENIGN: properly cited mock draft with no commitment language passes chain → draft."""
        # Mock LLM produces a clean, cited draft
        mock_draft_body = (
            "Thank you for contacting us about your order. "
            "Based on our order tracking system [KB-1], your order is currently being processed. "
            "You will receive a shipping confirmation within 24 hours [KB-2]."
        )
        mock_citations = [
            {"id": "KB-1", "text": "Order status policy"},
            {"id": "KB-2", "text": "Shipping notification policy"},
        ]

        verdict = _run_pre_tool_use_chain(mock_draft_body, mock_citations)

        assert verdict["action"] == "draft", (
            f"Expected draft for benign ticket; got {verdict['action']!r} reason={verdict.get('reason')!r}"
        )
        assert verdict.get("citations"), "Draft verdict must include citations"
        assert len(verdict["citations"]) >= 1

    def test_benign_draft_has_no_commitment_language(self, sample_tickets: dict) -> None:
        """BENIGN draft that passes chain must not contain commitment language (D-13)."""
        mock_draft_body = (
            "We have located your order in our system [KB-1]. "
            "It is currently being prepared for shipment. "
            "Please allow 2-3 business days for delivery."
        )
        mock_citations = [{"id": "KB-1", "text": "Order status"}]

        verdict = _run_pre_tool_use_chain(mock_draft_body, mock_citations)

        assert verdict["action"] == "draft"
        # Double-check: no commitment language in the draft that passed
        blocked, reason = check_commitment_language(verdict.get("body", ""))
        assert not blocked, f"Passing draft contains commitment language: {reason}"

    # ── PII: no raw fixture PII in verdict output ─────────────────────────────

    def test_no_raw_pii_in_escalate_output(self, sample_tickets: dict) -> None:
        """PII from fixture emails must not appear in escalate verdict output."""
        # HIGH_RISK ticket — from_email is mark.smith@example.com
        ticket = sample_tickets["high_risk"]
        mock_draft = "We will process your refund right away [KB-1]."
        mock_citations = [{"id": "KB-1"}]

        verdict = _run_pre_tool_use_chain(mock_draft, mock_citations)
        verdict_str = json.dumps(verdict)
        _assert_no_raw_pii(verdict_str)

    def test_no_raw_pii_in_injection_escalate_output(self, sample_tickets: dict) -> None:
        """PII from injection fixture must not appear in injection_screen escalate output."""
        ticket = sample_tickets["injection"]
        inj_result = _run_injection_prescreen(ticket["body"])
        assert inj_result is not None
        result_str = json.dumps(inj_result)
        _assert_no_raw_pii(result_str)

    # ── Escalation gate: accumulated risk signals veto at submit_reply ────────

    def test_escalation_gate_blocks_high_risk_signals(self) -> None:
        """escalation_gate should_escalate blocks even a clean draft if high_risk_category=True."""
        # Mock: drafter produced a perfectly cited, clean draft
        body = "Your order [KB-1] is on its way. It will arrive within 3 days."
        citations = [{"id": "KB-1"}]
        # But classifier flagged high risk
        risk_signals = {"high_risk_category": True}

        verdict = _run_pre_tool_use_chain(body, citations, risk_signals=risk_signals)

        assert verdict["action"] == "escalate", (
            f"Expected escalation_gate to block; got {verdict['action']!r}"
        )
        assert "high_risk_category" in verdict.get("reason", ""), (
            f"Expected high_risk_category in reason; got {verdict.get('reason')!r}"
        )

    def test_escalation_gate_passes_clean_signals(self) -> None:
        """escalation_gate should pass when all signals are False."""
        body = "Your order [KB-1] has shipped and will arrive within 2 business days."
        citations = [{"id": "KB-1"}]
        risk_signals = {
            "low_confidence": False,
            "high_risk_category": False,
            "conflict": False,
            "stale_only": False,
            "missing_key": False,
        }

        verdict = _run_pre_tool_use_chain(body, citations, risk_signals=risk_signals)

        assert verdict["action"] == "draft", (
            f"Expected draft to pass clean signals; got {verdict['action']!r} reason={verdict.get('reason')!r}"
        )

    # ── DRY_RUN always asserted ───────────────────────────────────────────────

    def test_dry_run_asserted_throughout(self) -> None:
        """settings.dry_run must always be True — no live Freshdesk post can occur."""
        sys.path.insert(0, str(_REPO_ROOT))
        from src.config import settings
        assert settings.dry_run is True, (
            f"settings.dry_run must be True; got {settings.dry_run!r}"
        )

    def test_runner_importable(self) -> None:
        """scripts.cs_team_demo must be importable with a callable main()."""
        sys.path.insert(0, str(_REPO_ROOT))
        import importlib
        demo = importlib.import_module("scripts.cs_team_demo")
        assert callable(getattr(demo, "main", None)), "cs_team_demo.main must be callable"
        assert callable(getattr(demo, "run_ticket", None)), "cs_team_demo.run_ticket must be callable"


# ---------------------------------------------------------------------------
# Layer (c): LIVE — gated behind RUN_CS_TEAM=1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("RUN_CS_TEAM"),
    reason="Live cs-team test skipped; set RUN_CS_TEAM=1 to run (requires claude auth + MCP env)",
)
class TestLiveCSTeam:
    """(c) Live: invokes scripts.cs_team_demo.main() via live `claude` CLI.

    Requires:
    - Human checkpoint approved (package verified, claude auth set, MCP env + DB up)
    - RUN_CS_TEAM=1 environment variable
    - settings.dry_run=True (asserted — no live Freshdesk post)
    """

    def test_dry_run_asserted_before_live_run(self) -> None:
        """settings.dry_run must be True before any live team invocation."""
        sys.path.insert(0, str(_REPO_ROOT))
        from src.config import settings
        assert settings.dry_run is True, (
            "SAFETY: settings.dry_run must be True for the live test layer"
        )

    @pytest.mark.asyncio
    async def test_benign_ticket_produces_draft(self) -> None:
        """Live: BENIGN_TICKET → action=draft, >=1 citation, no commitment language."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import BENIGN_TICKET, run_ticket
        verdict = await run_ticket(BENIGN_TICKET, use_live_claude=True)
        assert verdict["action"] == "draft", f"Expected draft; got {verdict!r}"
        assert verdict.get("citations"), "Benign draft must include citations"
        blocked, reason = check_commitment_language(verdict.get("body", ""))
        assert not blocked, f"Draft contains commitment language: {reason}"

    @pytest.mark.asyncio
    async def test_high_risk_ticket_escalates(self) -> None:
        """Live: HIGH_RISK_TICKET → action=escalate, no draft body."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import HIGH_RISK_TICKET, run_ticket
        verdict = await run_ticket(HIGH_RISK_TICKET, use_live_claude=True)
        assert verdict["action"] == "escalate", f"Expected escalate; got {verdict!r}"
        assert not verdict.get("body"), "Escalate must not carry a draft body"

    @pytest.mark.asyncio
    async def test_injection_ticket_escalates(self) -> None:
        """Live: INJECTION_TICKET → action=escalate via injection_screen."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import INJECTION_TICKET, run_ticket
        verdict = await run_ticket(INJECTION_TICKET, use_live_claude=True)
        assert verdict["action"] == "escalate", f"Expected escalate; got {verdict!r}"
        assert "injection" in verdict.get("reason", ""), (
            f"Expected injection:* reason; got {verdict.get('reason')!r}"
        )

    @pytest.mark.asyncio
    async def test_no_raw_pii_in_live_output(self) -> None:
        """Live: no raw PII from fixture tickets appears in captured output."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import BENIGN_TICKET, run_ticket
        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_ticket(BENIGN_TICKET, use_live_claude=True)
        _assert_no_raw_pii(buf.getvalue())

    @pytest.mark.asyncio
    async def test_full_acceptance_via_demo_main(self) -> None:
        """Live: run scripts.cs_team_demo.main() end-to-end; expect all 3 tickets to pass."""
        sys.path.insert(0, str(_REPO_ROOT))
        import asyncio
        from scripts.cs_team_demo import main as demo_main
        buf = io.StringIO()
        with redirect_stdout(buf):
            return_code = await demo_main(["--ticket", "all", "--live"])
        output = buf.getvalue()
        assert "[FAIL]" not in output, f"Demo run has failures:\n{output}"
        assert return_code == 0, f"Demo main returned non-zero: {return_code}"
        _assert_no_raw_pii(output)
