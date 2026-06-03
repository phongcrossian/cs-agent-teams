# Phase 4: Reply Pipeline (Agent Team) - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 18 (5 hooks + 5 agents + 5 skills + CLAUDE.md + settings.json + 1 runner)
**Analogs found:** 7 / 18 (remaining 11 are new Claude Code conventions)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.claude/hooks/injection_screen.py` | guard/middleware | request-response | `src/guards/loop_guard.py` | role-match |
| `.claude/hooks/pre_send_guard.py` | guard/middleware | request-response | `src/guards/loop_guard.py` | exact |
| `.claude/hooks/escalation_gate.py` | guard/middleware | request-response | `src/guards/loop_guard.py` | exact |
| `.claude/hooks/grounding_check.py` | guard/middleware | request-response | `src/guards/loop_guard.py` | role-match |
| `.claude/hooks/pii_redact.py` | guard/middleware | transform | `src/guards/pii.py` | exact |
| `.claude/agents/cs-lead.md` | agent definition | event-driven | none — new convention | no analog |
| `.claude/agents/classifier.md` | agent definition | request-response | none — new convention | no analog |
| `.claude/agents/extractor.md` | agent definition | request-response | none — new convention | no analog |
| `.claude/agents/drafter.md` | agent definition | request-response | none — new convention | no analog |
| `.claude/agents/critic.md` | agent definition | request-response | none — new convention | no analog |
| `.claude/skills/reply-pipeline/SKILL.md` | skill/workflow | event-driven | none — new convention | no analog |
| `.claude/skills/classify-ticket/SKILL.md` | skill/workflow | request-response | none — new convention | no analog |
| `.claude/skills/extract-answer-key/SKILL.md` | skill/workflow | request-response | none — new convention | no analog |
| `.claude/skills/ground-and-draft/SKILL.md` | skill/workflow | request-response | none — new convention | no analog |
| `.claude/skills/self-critique/SKILL.md` | skill/workflow | request-response | none — new convention | no analog |
| `.claude/settings.json` | config/wiring | config | `src/knowledge_mcp/server.py` + `src/selless_mcp/server.py` | partial |
| `.claude/CLAUDE.md` | config/rules | config | `CLAUDE.md` (root) | role-match |
| `scripts/cs_team_demo.py` | runner/utility | request-response | `tests/smoke/test_grounding_demo.py` | role-match |
| `src/config.py` *(extend)* | config | config | self | self-extend |

---

## Pattern Assignments

### `.claude/hooks/injection_screen.py` (guard, request-response)

**Analog:** `src/guards/loop_guard.py`

**Core pattern — deterministic guard returning `(bool, reason)`** (lines 157–193):
```python
def should_suppress(
    conv: Conversation,
    headers: dict[str, str] | None = None,
    from_email: str | None = None,
    selless_sync_user_ids: frozenset[int] | set[int] = frozenset(),
) -> tuple[bool, str]:
    """Returns (suppress: bool, reason: str).
    reason is empty string when suppress=False.
    Layers applied in order; first suppression reason wins.
    """
    # Layer 1 …
    if headers is not None:
        if is_auto_reply_by_headers(headers):
            return True, "layer1:auto_reply_header"
    # …
    return False, ""
```

**Mirror pattern for injection_screen.py:**
```python
def screen_for_injection(body: str) -> tuple[bool, str]:
    """Return (suspicious: bool, reason: str).
    reason is empty string when suspicious=False.
    Patterns applied in order; first match wins.
    """
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(body):
            return True, f"injection:{label}"
    return False, ""
```

**Module-level compiled patterns (mirror loop_guard._NO_REPLY_PATTERN)** (lines 92–96):
```python
_NO_REPLY_PATTERN = re.compile(
    r"^(no[._-]?reply|noreply|mailer-daemon|…)@",
    re.IGNORECASE,
)
```

**Hook entry point shape** — the hook must export a single callable that Claude Code `settings.json` can invoke via `command`. The function should read stdin JSON (Claude Code hook contract), call the screen function, and exit with code 1 + reason when escalating:
```python
import json, sys

def main() -> None:
    payload = json.load(sys.stdin)
    body = _extract_body(payload)
    suspicious, reason = screen_for_injection(body)
    if suspicious:
        print(json.dumps({"action": "escalate", "reason": reason}))
        sys.exit(1)   # non-zero → hook blocks the action
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### `.claude/hooks/pre_send_guard.py` (guard, request-response)

**Analog:** `src/guards/loop_guard.py` — closest pattern is the `should_suppress` unified entry point.

**Deterministic commitment-language block pattern:**
```python
import re
from __future__ import annotations

_COMMITMENT_PATTERNS = [
    (re.compile(r"\b(refund|reimburse)\b", re.IGNORECASE), "commitment:refund"),
    (re.compile(r"\b(credit|coupon|voucher)\b", re.IGNORECASE), "commitment:credit"),
    (re.compile(r"\b(charge|debit|payment)\b", re.IGNORECASE), "commitment:charge"),
    (re.compile(r"\b(replace|exchange|swap)\b", re.IGNORECASE), "commitment:order_change"),
]

def check_commitment_language(draft: str) -> tuple[bool, str]:
    """Return (has_commitment: bool, reason: str).
    Deterministic — never strips and sends; always escalates on match (D-13).
    """
    for pattern, label in _COMMITMENT_PATTERNS:
        if pattern.search(draft):
            return True, label
    return False, ""
```

**Same `main()` + `sys.exit(1)` hook pattern as injection_screen.py above.**

---

### `.claude/hooks/escalation_gate.py` (guard, request-response)

**Analog:** `src/guards/loop_guard.py` — the multi-layer OR-combination pattern.

**Multi-signal OR-gate pattern** (mirror of layers 1–4 in `should_suppress`, lines 175–193):
```python
def should_escalate(signals: dict) -> tuple[bool, str]:
    """Return (escalate: bool, reason: str).
    ANY signal triggers escalation — fail-closed, additive (D-08).
    """
    if signals.get("low_confidence"):
        return True, "escalate:low_confidence"
    if signals.get("high_risk_category"):
        return True, "escalate:high_risk_category"
    if signals.get("conflict"):           # Knowledge MCP conflict flag (D-09)
        return True, "escalate:kb_conflict"
    if signals.get("stale_only"):         # stale-only grounding (D-09)
        return True, "escalate:stale_only"
    if signals.get("missing_key"):        # extractor missing lookup key (D-07)
        return True, "escalate:missing_key"
    return False, ""
```

**Signal sourcing:** `signals` dict is assembled from the conversation context payload that Claude Code passes to hooks. Keys map to fields in the intermediate verdict JSON the lead emits at each stage.

---

### `.claude/hooks/grounding_check.py` (guard, request-response)

**Analog:** `src/guards/loop_guard.py` (structural), `src/selless_mcp/server.py` field whitelist (content).

**Inline-citation check pattern:**
```python
import re

_CITATION_MARKER = re.compile(r"\[(?:KB|SEL)-\d+\]")  # e.g. [KB-1], [SEL-2]

def check_grounding(draft: str, citations: list[dict]) -> tuple[bool, str]:
    """Return (grounded: bool, reason: str).
    Every factual sentence must carry a citation marker pointing to a
    Knowledge or whitelisted Selless field (D-11).
    """
    markers_in_draft = set(_CITATION_MARKER.findall(draft))
    if not markers_in_draft and citations:
        return False, "grounding:no_citations_in_draft"
    # All markers must refer to a known citation
    known_ids = {c["id"] for c in citations}
    unknown = markers_in_draft - known_ids
    if unknown:
        return False, f"grounding:unknown_citation_ids:{','.join(sorted(unknown))}"
    return True, ""
```

**Same `main()` + `sys.exit(1)` hook exit pattern.**

---

### `.claude/hooks/pii_redact.py` (guard, transform)

**Analog:** `src/guards/pii.py` — **reuses `redact_text` directly**; the hook is a thin wrapper.

**Imports pattern** (lines 1–17 of `src/guards/pii.py`):
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine as _AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine as _AnonymizerEngine
```

**Lazy-singleton pattern** (lines 39–53 of `src/guards/pii.py`):
```python
_analyzer: "_AnalyzerEngine | None" = None
_anonymizer: "_AnonymizerEngine | None" = None

def _get_engines() -> "tuple[_AnalyzerEngine, _AnonymizerEngine]":
    global _analyzer, _anonymizer
    if _analyzer is None or _anonymizer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer
```

**`redact_text` entry point** (lines 56–82 of `src/guards/pii.py`) — **import and call directly**:
```python
from src.guards.pii import redact_text

def pii_redact_hook(text: str) -> str:
    """Wrap redact_text for the hook entry point.
    Called before any log/trace write (D-04 + CLAUDE.md).
    """
    return redact_text(text)
```

**Hook `main()` pattern** — redacts the relevant fields in the payload and writes redacted version back to stdout:
```python
def main() -> None:
    payload = json.load(sys.stdin)
    if "body" in payload:
        payload["body"] = redact_text(payload["body"])
    print(json.dumps(payload))
    sys.exit(0)  # pii_redact never blocks; it only transforms
```

---

### `.claude/settings.json` (config/wiring)

**Analog:** `src/knowledge_mcp/server.py` (lines 32–33) and `src/selless_mcp/server.py` (lines 150–160) — MCP server init patterns.

**MCP server name declarations** (server.py pattern to reference for the launch command):
```python
# knowledge_mcp/server.py line 32
mcp = FastMCP(name="KnowledgeMCP", on_duplicate="error")

# selless_mcp/server.py line 150
mcp = FastMCP(name="SellessMCP", on_duplicate="error")
```

**settings.json must register both MCP servers as tools and bind hooks. Shape:**
```json
{
  "mcpServers": {
    "KnowledgeMCP": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.knowledge_mcp.server"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}",
        "VOYAGE_API_KEY": "${VOYAGE_API_KEY}"
      }
    },
    "SellessMCP": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.selless_mcp.server"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}",
        "SELLESS_API_BASE_URL": "${SELLESS_API_BASE_URL}"
      }
    }
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "*", "hooks": [{ "type": "command", "command": "uv run python .claude/hooks/injection_screen.py" }] }
    ],
    "PostToolUse": [
      { "matcher": "*", "hooks": [{ "type": "command", "command": "uv run python .claude/hooks/pii_redact.py" }] }
    ]
  },
  "env": {
    "SEND_MODE": "dry_run"
  }
}
```

**Note:** Exact `hooks` key names and `matcher` syntax must be verified against the Claude Code `settings.json` spec at build time (open question §9.4 of design).

---

### `scripts/cs_team_demo.py` (runner/utility, request-response)

**Analog:** `tests/smoke/test_grounding_demo.py` — standalone script that feeds fixture data, calls MCP implementation functions directly, and prints assertions/results.

**Module-level client injection pattern** (lines 36–51 of smoke demo):
```python
from src.knowledge_mcp.server import semantic_search, lookup_threshold, get_template
from src.selless_mcp.server import _impl_get_order_status, set_selless_client
```

**Async main entry point pattern** (smoke demo, lines 183–193):
```python
import asyncio

async def main() -> None:
    # 1. Feed sample ticket (benign + high-risk variants)
    # 2. Invoke cs-lead (via claude CLI subprocess or Agent SDK)
    # 3. Parse verdict JSON
    # 4. Assert acceptance criteria
    pass

if __name__ == "__main__":
    asyncio.run(main())
```

**DRY_RUN output pattern** (from `src/work_queue/send.py` lines 105–121):
```python
# _dry_run: logs the would-be action; never calls Freshdesk
logger.info(
    "send_dry_run",
    extra={"ticket_id": ticket_id, "inbound_msg_id": inbound_msg_id},
)
return {"dry_run": True}
```

**Config singleton import** (from `src/config.py` line 162):
```python
from src.config import settings   # module-level singleton, import here
```

**Acceptance criteria shape to print:**
```
[PASS] benign ticket -> action=draft, citations>=1, no commitment language
[PASS] high-risk ticket (refund) -> action=escalate, reason=commitment:refund, no draft
[PASS] injection ticket -> action=escalate, reason=injection:..., no draft
[PASS] PII absent from logs/traces
```

---

### `src/config.py` *(extend)* (config, self-extend)

**Analog:** self — extend the existing `Settings` class.

**Existing class and singleton pattern** (lines 28–162):
```python
class Settings(BaseSettings):
    # … existing fields …

    # === Phase 4 additions — agent team ======================================
    anthropic_api_key: str = Field(default="", description="Anthropic API key — NEVER log")
    claude_model_classify: str = Field(default="claude-haiku-4-5", description="Haiku for classify/extract stages (D-03)")
    claude_model_draft: str = Field(default="claude-sonnet-4-6", description="Sonnet for draft/critic stages (D-03)")
    # Bedrock cut-over: set CLAUDE_CODE_USE_BEDROCK=1 + AWS_* envs; no code change needed
    dry_run: bool = Field(default=True, description="DRY_RUN flag for the agent team (never posts to Freshdesk in PoC)")

    def __repr__(self) -> str:
        # mirror existing pattern — never expose api_key values
        return (
            f"Settings(send_mode={self.send_mode!r}, "
            f"claude_model_classify={self.claude_model_classify!r}, "
            f"claude_model_draft={self.claude_model_draft!r}, "
            f"anthropic_api_key=<REDACTED>, …)"
        )

settings = Settings()   # module-level singleton — import from here
```

**Security pattern — secrets never logged** (lines 142–151 of `src/config.py`): reproduce the `__repr__` override that redacts `anthropic_api_key` exactly as `freshdesk_api_key` is redacted.

---

## Shared Patterns

### Guard return signature — `(bool, reason: str)`
**Source:** `src/guards/loop_guard.py` lines 157–193 (`should_suppress`)
**Apply to:** ALL five `.claude/hooks/*.py` files

Every hook guard function MUST return `tuple[bool, str]` where:
- `bool` = whether the action is blocked/flagged
- `str` = reason label (snake_case:sub_label format, e.g. `"escalate:kb_conflict"`); empty string when not blocking

```python
def _check(input_: str) -> tuple[bool, str]:
    if _PATTERN.search(input_):
        return True, "gate:label"
    return False, ""
```

### PII redaction before any log/trace
**Source:** `src/guards/pii.py` line 56 (`redact_text`) and `src/work_queue/send.py` lines 105–107
**Apply to:** `pii_redact.py` hook, `scripts/cs_team_demo.py`, any place that logs ticket body

```python
from src.guards.pii import redact_text
body_safe = redact_text(conv.body_text)
logger.info("processing", ticket_id=ticket_id, body_preview=body_safe[:100])
```

### DRY_RUN-by-default posture
**Source:** `src/config.py` lines 57–61 (`SendMode.DRY_RUN`) and `src/work_queue/send.py` lines 85–88
**Apply to:** `scripts/cs_team_demo.py`, `src/config.py` extension, `.claude/settings.json`

```python
class SendMode(str, Enum):
    DRY_RUN = "dry_run"
    LIVE = "live"

# Always default to DRY_RUN; never send live in PoC
send_mode: SendMode = Field(default=SendMode.DRY_RUN, …)
```

### Secrets never in `__repr__`/logs
**Source:** `src/config.py` lines 142–151
**Apply to:** `src/config.py` extension (new `anthropic_api_key` field)

```python
def __repr__(self) -> str:
    return (
        f"Settings(…, "
        f"freshdesk_api_key=<REDACTED>, webhook_secret=<REDACTED>, "
        f"selless_api_gateway_key=<REDACTED>, voyage_api_key=<REDACTED>)"
    )
```

### Lazy singleton for expensive initialisation
**Source:** `src/guards/pii.py` lines 39–53
**Apply to:** `.claude/hooks/pii_redact.py`

```python
_analyzer: "_AnalyzerEngine | None" = None
_anonymizer: "_AnonymizerEngine | None" = None

def _get_engines() -> "tuple[_AnalyzerEngine, _AnonymizerEngine]":
    global _analyzer, _anonymizer
    if _analyzer is None or _anonymizer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer
```

### FastMCP server registration (for settings.json launch command)
**Source:** `src/knowledge_mcp/server.py` line 32 and `src/selless_mcp/server.py` line 150
**Apply to:** `.claude/settings.json` MCP server entries

Both servers are launched via `uv run python -m src.<module>.server`. The module entry point exposes a `mcp` object (`FastMCP` instance); FastMCP's `run()` or `__main__` block handles the MCP wire protocol.

---

## No Analog Found

Files using new Claude Code conventions — planner should follow Claude Code agent/skill/hook format from the Claude Code documentation:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.claude/agents/cs-lead.md` | agent definition | event-driven | No `.claude/agents/` directory exists yet; new Claude Code convention |
| `.claude/agents/classifier.md` | agent definition | request-response | Same — new convention |
| `.claude/agents/extractor.md` | agent definition | request-response | Same — new convention |
| `.claude/agents/drafter.md` | agent definition | request-response | Same — new convention |
| `.claude/agents/critic.md` | agent definition | request-response | Same — new convention |
| `.claude/skills/reply-pipeline/SKILL.md` | skill/workflow | event-driven | New Claude Code skill convention |
| `.claude/skills/classify-ticket/SKILL.md` | skill/workflow | request-response | Same — new convention |
| `.claude/skills/extract-answer-key/SKILL.md` | skill/workflow | request-response | Same — new convention |
| `.claude/skills/ground-and-draft/SKILL.md` | skill/workflow | request-response | Same — new convention |
| `.claude/skills/self-critique/SKILL.md` | skill/workflow | request-response | Same — new convention |
| `.claude/CLAUDE.md` | rules/config | config | Root `CLAUDE.md` is a project-level file; the `.claude/CLAUDE.md` is an agent-team-scoped rules file (different scope/role); follow existing `CLAUDE.md` as content model but keep it team-scoped |

**For the agent `.md` files:** each must declare `model`, `description`, and a `## System Prompt` section. Safety-critical rules (no ungrounded claims, escalation semantics) belong in `CLAUDE.md` (always-on), not in individual agent `.md` files. Agent-local rules (e.g. citation discipline for `drafter.md`) live in that agent's own `.md`.

**For the skill `SKILL.md` files:** each must be a lightweight index (~130 lines) listing the skill's purpose, inputs, outputs, and constraints. The `reply-pipeline` skill encodes the stage order (classify → escalation gate → extract → ground+draft → critique) and escalation rules. It is the single workflow authority; hooks enforce the non-negotiables deterministically.

---

## Metadata

**Analog search scope:** `src/guards/`, `src/work_queue/`, `src/config.py`, `src/knowledge_mcp/server.py`, `src/selless_mcp/server.py`, `tests/smoke/`, `tests/test_loop_guard.py`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-03
