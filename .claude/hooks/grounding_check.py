"""
Grounding check — REP-03 / D-11.

Deterministic (no LLM). Verifies that every factual claim in a customer draft
carries at least one inline citation marker ([KB-N] or [SEL-N]) referencing
a citation returned by the Knowledge or Selless MCP in this run.

Design rule (D-11): no ungrounded claims. A draft with zero citation markers
when citations exist, or with markers pointing to unknown citation IDs, fails.

Contract (mirrors src/guards/loop_guard.should_suppress):
    check_grounding(draft: str, citations: list[dict]) -> tuple[bool, str]
    - bool: True = grounded (PASS), False = NOT grounded (FAIL)
    - str: "" when grounded; failure reason when not (e.g. "grounding:no_citations_in_draft")

Hook entry point: main() reads stdin JSON {"draft": "...", "citations": [...]},
calls check_grounding, exits 1 (block/escalate) on failure, 0 (pass) on success.
Fail-closed: malformed stdin → escalate (exit 1).
"""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Citation marker pattern: [KB-N] or [SEL-N] (PATTERNS.md lines 163-184)
# ---------------------------------------------------------------------------

_CITATION_MARKER = re.compile(r"\[(?:KB|SEL)-\d+\]")


def check_grounding(draft: str, citations: list[dict]) -> tuple[bool, str]:
    """Return (grounded: bool, reason: str).

    grounded=True means PASS (all markers map to known citations, or no citations
    exist and draft has no markers — e.g. empty citations list).
    grounded=False means FAIL with a reason label.

    Rules:
    1. If citations exist but draft has NO citation markers → fail.
    2. If draft markers reference unknown citation IDs → fail.
    3. If all markers map to known IDs (or no markers AND no citations) → pass.
    """
    markers_in_draft: set[str] = set(_CITATION_MARKER.findall(draft))

    # Rule 1: citations provided but none cited in draft
    if citations and not markers_in_draft:
        return False, "grounding:no_citations_in_draft"

    # Rule 2: markers reference unknown citations
    if markers_in_draft:
        known_ids: set[str] = {c["id"] for c in citations if "id" in c}
        unknown = markers_in_draft - known_ids
        if unknown:
            return False, f"grounding:unknown_citation_ids:{','.join(sorted(unknown))}"

    # All checks passed
    return True, ""


def _extract_draft_and_citations(payload: dict) -> tuple[str, list[dict]]:
    """Extract draft text and citations list from the hook payload.

    PreToolUse(submit_reply) payload:
      {"tool_name": "submit_reply", "tool_input": {"body": "...", "citations": [...]}}

    Standalone / test payload:
      {"draft": "...", "citations": [...]}
    """
    # PreToolUse context
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, dict):
        draft = str(tool_input.get("body", tool_input.get("draft", "")))
        citations = tool_input.get("citations", [])
        if draft or citations:
            return draft, citations if isinstance(citations, list) else []

    # Standalone / test context
    draft = str(payload.get("draft", payload.get("body", "")))
    citations = payload.get("citations", [])
    return draft, citations if isinstance(citations, list) else []


def main() -> None:
    """Claude Code hook entry point (PreToolUse on submit_reply).

    Reads stdin JSON, verifies draft grounding.
    Exits 1 (block/escalate) if not grounded, 0 (pass) if grounded.
    Fail-closed: any parse/runtime error → escalate.
    """
    try:
        payload = json.load(sys.stdin)
        draft, citations = _extract_draft_and_citations(payload)
        grounded, reason = check_grounding(draft, citations)
        if not grounded:
            print(json.dumps({"action": "escalate", "reason": reason}))
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"grounding_check:error:{exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
