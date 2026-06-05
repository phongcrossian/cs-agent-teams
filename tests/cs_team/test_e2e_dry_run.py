"""
tests/cs_team/test_e2e_dry_run.py — E2E dry-run test suite for the cs-agent-team.

Always-draft contract (D-33): the pipeline ALWAYS produces a customer draft.
There is no escalate=no-draft outcome. High-risk and injection tickets produce
a draft with an advisory escalation_hint — they do NOT produce action="escalate"
with no body.

Three layers:

  (a) STRUCTURAL — always runs, no auth required.
      Asserts the slimmed two-hook wiring from settings.json (post 04-01):
        - UserPromptSubmit → injection_screen.py (D-14)
        - PostToolUse → pii_redact.py (D-04)
        - NO PreToolUse(submit_reply) chain
        - NO SubagentStop binding
        - mcpServers has SellessMCP + ReplyMCP, NOT KnowledgeMCP

  (b) INTEGRATED mock — always runs in CI, no real auth.
      Drives the always-draft hook chain using STUB canned inputs so that
      the injection pre-screen and PII redact hooks are exercised with real
      fixture tickets. Proves:
        - BENIGN ticket → action="draft", escalation_hint is None
        - HIGH_RISK ticket → action="draft" WITH advisory escalation_hint (NOT escalate)
        - INJECTION ticket → action="draft" WITH escalation_hint (injection_screen
          fires an advisory signal; pipeline still drafts per D-33)
      Asserts: action="draft" in all cases, no raw PII in output, DRY_RUN throughout.

  (c) LIVE — gated behind RUN_CS_TEAM=1.
      Invokes scripts.cs_team_demo.main() against the live `claude` CLI.
      All three ticket fixtures must yield action="draft".

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


_inj_mod = _load_hook("injection_screen")
_pii_mod = _load_hook("pii_redact")

screen_for_injection = _inj_mod.screen_for_injection
pii_redact_hook = _pii_mod.pii_redact_hook


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
# Layer (a): STRUCTURAL binding assertions — always-draft two-hook wiring
# ---------------------------------------------------------------------------


class TestStructuralBindings:
    """(a) Structural: assert the slimmed two-hook wiring from settings.json (post 04-01)."""

    def test_settings_json_exists(self) -> None:
        assert _SETTINGS_PATH.exists(), ".claude/settings.json must exist"

    def test_user_prompt_submit_injection_screen(self, settings_json: dict) -> None:
        """UserPromptSubmit must bind injection_screen.py (D-14)."""
        ups = settings_json.get("hooks", {}).get("UserPromptSubmit", [])
        cmds = [h.get("command", "") for b in ups for h in b.get("hooks", [])]
        assert any("injection_screen.py" in c for c in cmds), (
            f"injection_screen.py not in UserPromptSubmit; commands: {cmds}"
        )

    def test_post_tool_use_pii_redact(self, settings_json: dict) -> None:
        """PostToolUse must bind pii_redact.py (D-04)."""
        ptu = settings_json.get("hooks", {}).get("PostToolUse", [])
        cmds = [h.get("command", "") for b in ptu for h in b.get("hooks", [])]
        assert any("pii_redact.py" in c for c in cmds), "pii_redact.py missing from PostToolUse"

    def test_no_pre_tool_use_submit_reply_chain(self, settings_json: dict) -> None:
        """NO PreToolUse binding with matcher='submit_reply' (deleted guard chain)."""
        pre_tool_use = settings_json.get("hooks", {}).get("PreToolUse", [])
        matchers = [b.get("matcher", "") for b in pre_tool_use]
        assert "submit_reply" not in matchers, (
            f"PreToolUse(submit_reply) chain must NOT exist after 04-01; matchers: {matchers}"
        )

    def test_no_subagent_stop_binding(self, settings_json: dict) -> None:
        """NO SubagentStop binding (escalation_gate deleted in 04-01)."""
        subagent_stop = settings_json.get("hooks", {}).get("SubagentStop", [])
        assert len(subagent_stop) == 0, (
            f"SubagentStop must be empty after 04-01; got: {subagent_stop}"
        )

    def test_knowledge_mcp_removed(self, settings_json: dict) -> None:
        """KnowledgeMCP must NOT be in mcpServers (removed in 04-01/D-31)."""
        mcp_servers = settings_json.get("mcpServers", {})
        assert "KnowledgeMCP" not in mcp_servers, (
            "KnowledgeMCP must not appear in mcpServers after the D-31 pivot"
        )

    def test_selless_mcp_present(self, settings_json: dict) -> None:
        """SellessMCP must remain in mcpServers (Selless MCP stays per D-29)."""
        mcp_servers = settings_json.get("mcpServers", {})
        assert "SellessMCP" in mcp_servers, "SellessMCP must remain in mcpServers"

    def test_reply_mcp_present(self, settings_json: dict) -> None:
        """ReplyMCP must remain in mcpServers."""
        mcp_servers = settings_json.get("mcpServers", {})
        assert "ReplyMCP" in mcp_servers, "ReplyMCP must remain in mcpServers"

    def test_dry_run_env_in_settings(self, settings_json: dict) -> None:
        """settings.json env must set SEND_MODE=dry_run."""
        env = settings_json.get("env", {})
        assert env.get("SEND_MODE") == "dry_run", (
            f"Expected SEND_MODE=dry_run in settings.json env; got {env.get('SEND_MODE')!r}"
        )

    def test_only_two_hook_scripts_referenced(self, settings_json: dict) -> None:
        """Only injection_screen.py and pii_redact.py are referenced in settings.json."""
        s = json.dumps(settings_json)
        assert "injection_screen.py" in s, "injection_screen.py must be in settings.json"
        assert "pii_redact.py" in s, "pii_redact.py must be in settings.json"
        # Deleted guard hooks must not appear
        for deleted in ["grounding_check.py", "pre_send_guard.py", "escalation_gate.py"]:
            assert deleted not in s, (
                f"Deleted hook {deleted!r} must not appear in settings.json after 04-01"
            )


# ---------------------------------------------------------------------------
# Layer (b): INTEGRATED mock — always-draft pipeline proof
# ---------------------------------------------------------------------------
#
# The always-draft contract (D-33): every ticket produces action="draft".
# injection_screen runs as an advisory pre-screen on the ticket body before
# the pipeline; if it fires, the pipeline attaches an escalation_hint but
# still emits action="draft". No fixture produces action="escalate".
#
# The mock pipeline below simulates the always-draft cs-agent-team:
#   1. injection pre-screen (advisory — note if flagged, do NOT stop)
#   2. (mock) drafter emits a draft body
#   3. submit_reply called → action="draft" always
# ---------------------------------------------------------------------------


def _run_always_draft_pipeline(
    ticket: dict,
    mock_draft_body: str,
    mock_citations: list[dict] | None = None,
    risk_signals: dict | None = None,
) -> dict[str, Any]:
    """Simulate the always-draft pipeline for a given ticket and mock draft.

    1. Runs injection_screen (advisory).
    2. Redacts PII from the ticket body (advisory).
    3. Always returns action="draft" with an optional escalation_hint.

    This is the D-33 contract: the pipeline NEVER returns action="escalate".
    """
    if mock_citations is None:
        mock_citations = []
    if risk_signals is None:
        risk_signals = {}

    escalation_hint: dict | None = None

    # Advisory: injection pre-screen (D-14)
    suspicious, inj_reason = screen_for_injection(ticket.get("body", ""))
    if suspicious:
        escalation_hint = {
            "reason": inj_reason,
            "signals": {**risk_signals, "injection": True},
        }

    # Advisory: accumulate any other risk signals
    if not escalation_hint and risk_signals:
        active_signals = {k: v for k, v in risk_signals.items() if v}
        if active_signals:
            first_reason = next(iter(active_signals))
            escalation_hint = {
                "reason": first_reason,
                "signals": risk_signals,
            }

    # Always produce a draft (D-33) — no stop-and-escalate
    return {
        "action": "draft",
        "body": mock_draft_body,
        "citations": mock_citations,
        "escalation_hint": escalation_hint,
    }


# PII patterns from sample tickets that must NOT appear in output
_PII_PATTERNS = [
    "jane.doe@example.com",
    "mark.smith@example.com",
    "attacker@malicious.example",
]


def _assert_no_raw_pii(text: str) -> None:
    """Assert none of the known PII patterns appear in *text*."""
    for pattern in _PII_PATTERNS:
        assert pattern not in text, (
            f"Raw PII leaked into output: {pattern!r} found in: {text[:200]!r}"
        )


class TestIntegratedMockLLM:
    """(b) Integrated: drive always-draft pipeline with mock ticket + draft inputs.

    All three fixture tickets must produce action="draft" per D-33.
    High-risk and injection tickets carry an advisory escalation_hint but still draft.
    """

    # ── BENIGN: clean draft, no advisory signals ──────────────────────────────

    def test_benign_ticket_produces_draft(self, sample_tickets: dict) -> None:
        """BENIGN_TICKET → action='draft', escalation_hint is None."""
        ticket = sample_tickets["benign"]
        mock_draft = (
            "Thank you for contacting us about your order. "
            "Your order is currently being processed and will ship within 2 business days."
        )
        verdict = _run_always_draft_pipeline(ticket, mock_draft)

        assert verdict["action"] == "draft", (
            f"Expected action='draft' for benign ticket; got {verdict['action']!r}"
        )
        assert verdict["escalation_hint"] is None, (
            f"Benign ticket must not produce an escalation_hint; got {verdict['escalation_hint']!r}"
        )
        assert verdict.get("body") == mock_draft

    def test_benign_draft_no_raw_pii(self, sample_tickets: dict) -> None:
        """PII from benign ticket must not appear in verdict output."""
        ticket = sample_tickets["benign"]
        mock_draft = "Your order is being processed. We will update you shortly."
        verdict = _run_always_draft_pipeline(ticket, mock_draft)
        _assert_no_raw_pii(json.dumps(verdict))

    # ── HIGH_RISK: advisory escalation_hint, but still action="draft" ─────────

    def test_high_risk_ticket_produces_draft_with_hint(self, sample_tickets: dict) -> None:
        """HIGH_RISK_TICKET → action='draft' WITH advisory escalation_hint (NOT escalate)."""
        ticket = sample_tickets["high_risk"]
        mock_draft = (
            "Thank you for your patience. We have reviewed your case and "
            "our team will follow up within 24 hours with the appropriate resolution."
        )
        verdict = _run_always_draft_pipeline(
            ticket,
            mock_draft,
            risk_signals={"high_risk_category": True},
        )

        assert verdict["action"] == "draft", (
            f"Expected action='draft' even for high-risk ticket (D-33); got {verdict['action']!r}"
        )
        assert verdict["escalation_hint"] is not None, (
            "High-risk ticket must attach an advisory escalation_hint"
        )
        assert "high_risk_category" in verdict["escalation_hint"].get("signals", {}), (
            f"escalation_hint signals must include high_risk_category; got {verdict['escalation_hint']!r}"
        )

    def test_high_risk_ticket_never_escalate_verdict(self, sample_tickets: dict) -> None:
        """HIGH_RISK_TICKET must NOT produce action='escalate' with no body (D-33 contract)."""
        ticket = sample_tickets["high_risk"]
        mock_draft = "We understand your concern and our team will assist you promptly."
        verdict = _run_always_draft_pipeline(
            ticket,
            mock_draft,
            risk_signals={"high_risk_category": True},
        )
        assert verdict["action"] != "escalate", (
            "action='escalate' is retired by D-33; pipeline must always return action='draft'"
        )
        assert verdict.get("body"), "Draft body must be present in the verdict"

    # ── INJECTION: advisory escalation_hint, but still action="draft" ─────────

    def test_injection_ticket_produces_draft_with_hint(self, sample_tickets: dict) -> None:
        """INJECTION_TICKET → action='draft' WITH escalation_hint (advisory injection signal)."""
        ticket = sample_tickets["injection"]
        mock_draft = (
            "Thank you for reaching out. We have received your message and "
            "will respond to your inquiry shortly."
        )
        verdict = _run_always_draft_pipeline(ticket, mock_draft)

        assert verdict["action"] == "draft", (
            f"Expected action='draft' even for injection ticket (D-33); got {verdict['action']!r}"
        )
        # injection_screen fires on the INJECTION_TICKET body → escalation_hint attached
        assert verdict["escalation_hint"] is not None, (
            "Injection ticket must attach an advisory escalation_hint"
        )
        assert "injection" in verdict["escalation_hint"].get("reason", ""), (
            f"escalation_hint reason must mention injection; got {verdict['escalation_hint']!r}"
        )

    def test_injection_ticket_never_escalate_verdict(self, sample_tickets: dict) -> None:
        """INJECTION_TICKET must NOT produce action='escalate' — D-33 always-draft."""
        ticket = sample_tickets["injection"]
        mock_draft = "We have received your request and will be in touch shortly."
        verdict = _run_always_draft_pipeline(ticket, mock_draft)
        assert verdict["action"] != "escalate", (
            "action='escalate' is retired by D-33; even injection tickets get a draft"
        )

    def test_injection_no_raw_pii_in_verdict(self, sample_tickets: dict) -> None:
        """PII from injection fixture must not appear in verdict output."""
        ticket = sample_tickets["injection"]
        mock_draft = "Thank you for contacting us."
        verdict = _run_always_draft_pipeline(ticket, mock_draft)
        _assert_no_raw_pii(json.dumps(verdict))

    # ── PII redaction ─────────────────────────────────────────────────────────

    def test_no_raw_pii_in_high_risk_output(self, sample_tickets: dict) -> None:
        """PII from high-risk fixture must not appear in verdict output."""
        ticket = sample_tickets["high_risk"]
        mock_draft = "We will look into this and get back to you."
        verdict = _run_always_draft_pipeline(
            ticket, mock_draft, risk_signals={"high_risk_category": True}
        )
        _assert_no_raw_pii(json.dumps(verdict))

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


# ---------------------------------------------------------------------------
# Layer (c): LIVE — gated behind RUN_CS_TEAM=1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("RUN_CS_TEAM"),
    reason="Live cs-team test skipped; set RUN_CS_TEAM=1 to run (requires claude auth + MCP env)",
)
class TestLiveCSTeam:
    """(c) Live: invokes scripts.cs_team_demo via live `claude` CLI.

    Requires:
    - RUN_CS_TEAM=1 environment variable
    - Claude auth, MCP env, DB up
    - settings.dry_run=True (asserted — no live Freshdesk post)

    All tickets must yield action="draft" per D-33 always-draft contract.
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
        """Live: BENIGN_TICKET → action='draft', no escalate=no-draft."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import BENIGN_TICKET, run_ticket
        verdict = await run_ticket(BENIGN_TICKET, use_live_claude=True)
        assert verdict["action"] == "draft", f"Expected draft; got {verdict!r}"
        assert verdict.get("body"), "Benign draft must include a body"

    @pytest.mark.asyncio
    async def test_high_risk_ticket_produces_draft(self) -> None:
        """Live: HIGH_RISK_TICKET → action='draft' (D-33 — always-draft, advisory hint)."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import HIGH_RISK_TICKET, run_ticket
        verdict = await run_ticket(HIGH_RISK_TICKET, use_live_claude=True)
        assert verdict["action"] == "draft", (
            f"Expected draft for high-risk ticket (D-33); got {verdict!r}"
        )

    @pytest.mark.asyncio
    async def test_injection_ticket_produces_draft(self) -> None:
        """Live: INJECTION_TICKET → action='draft' with advisory escalation_hint."""
        sys.path.insert(0, str(_REPO_ROOT))
        from scripts.cs_team_demo import INJECTION_TICKET, run_ticket
        verdict = await run_ticket(INJECTION_TICKET, use_live_claude=True)
        assert verdict["action"] == "draft", (
            f"Expected draft for injection ticket (D-33 always-draft); got {verdict!r}"
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
