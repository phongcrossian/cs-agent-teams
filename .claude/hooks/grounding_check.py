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
calls check_grounding, exits 2 (BLOCK/escalate) on failure, 0 (pass) on success.
Fail-closed: malformed stdin → escalate (exit 2 = BLOCK).
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

    grounded=True means PASS (all markers map to known citations).
    grounded=False means FAIL with a reason label.

    Rules:
    1. If citations exist but draft has NO citation markers → fail.
    2. If draft markers reference unknown citation IDs → fail.
    3. If draft body is non-empty AND has NO citation markers AND has NO citations → fail.
       A factual draft requires ≥1 citation per D-11; empty-citation + empty-marker is
       ungrounded by default (closes the empty-citation bypass, CR-03).
    """
    markers_in_draft: set[str] = set(_CITATION_MARKER.findall(draft))

    # Rule 1: citations provided but none cited in draft
    if citations and not markers_in_draft:
        return False, "grounding:no_citations_in_draft"

    # Rule 3 (CR-03): non-empty body with zero markers AND zero citations → ungrounded.
    # D-11 requires ≥1 citation for any factual claim; a draft with no citations at all
    # cannot be verified as grounded.
    if draft and not markers_in_draft and not citations:
        return False, "grounding:no_citations"

    # Rule 2: markers reference unknown citations
    # Normalize citation IDs: accept both "KB-1" and "[KB-1]" as equivalent.
    # Markers extracted from draft are always in "[KB-1]" form (with brackets).
    # Citation dicts may use either form — normalize to bracketed form for comparison.
    if markers_in_draft:
        raw_ids: set[str] = {c["id"] for c in citations if "id" in c}
        # Normalize: wrap bare IDs (without brackets) to bracketed form
        known_ids: set[str] = {
            f"[{cid}]" if not cid.startswith("[") else cid
            for cid in raw_ids
        }
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
            sys.exit(2)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(json.dumps({"action": "escalate", "reason": f"grounding_check:error:{exc}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
