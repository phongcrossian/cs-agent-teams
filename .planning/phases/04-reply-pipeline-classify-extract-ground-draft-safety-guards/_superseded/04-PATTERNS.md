# Phase 4: Reply Pipeline (Classify, Extract, Ground, Draft, Safety Guards) - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 14 new/modified files
**Analogs found:** 13 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pipeline/__init__.py` | package init | — | `src/guards/__init__.py` | role-match |
| `src/pipeline/models.py` | model/schema | transform | `src/knowledge_mcp/models.py` | exact |
| `src/pipeline/orchestrator.py` | service/orchestrator | request-response | `src/work_queue/worker.py` | role-match |
| `src/pipeline/stages/classify.py` | service/agent | request-response | `src/selless_mcp/server.py` (`_impl_*` pattern) | role-match |
| `src/pipeline/stages/extract.py` | service/agent | request-response | `src/selless_mcp/server.py` (`_impl_*` pattern) | role-match |
| `src/pipeline/stages/ground.py` | service/agent | request-response | `src/knowledge_mcp/server.py` | role-match |
| `src/pipeline/stages/draft.py` | service/agent | request-response | `src/selless_mcp/server.py` (`_impl_*` pattern) | role-match |
| `src/pipeline/stages/critique.py` | service/agent | request-response | `src/selless_mcp/server.py` (`_impl_*` pattern) | role-match |
| `src/pipeline/escalation.py` | utility/guard | event-driven | `src/guards/loop_guard.py` | role-match |
| `src/pipeline/guards.py` | middleware/guard | request-response | `src/guards/pii.py` | role-match |
| `src/pipeline/tracing.py` | utility/config | event-driven | `src/observability.py` | role-match |
| `src/config.py` | config | — | `src/config.py` (extend) | exact |
| `src/work_queue/worker.py` | service/worker | request-response | self (modify seam lines 201–207) | exact |
| `src/pipeline/errors.py` | utility/errors | — | `src/freshdesk_io/errors.py` | exact |

---

## Pattern Assignments

### `src/pipeline/models.py` (model/schema, transform)

**Analog:** `src/knowledge_mcp/models.py` + `src/selless_mcp/models.py`

**Imports pattern** (`src/knowledge_mcp/models.py` lines 1–22):
```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
```

**Core Pydantic model pattern** (`src/knowledge_mcp/models.py` lines 24–44):
```python
class Citation(BaseModel):
    text: str
    source: str
    source_type: str
    authority_rank: int
    recency_flag: Optional[str] = None   # D-15: "stale" if flagged, else None
    snapshot_version: str
    score: float
    conflict_id: Optional[str] = None    # D-14: CONTRA-* if part of known conflict
```

**Whitelist boundary pattern** (`src/selless_mcp/models.py` lines 1–10):
```python
"""
SECURITY CONTRACT: these models ARE the whitelist boundary.
No field for any DENY-listed key (...) may appear here — ever.
"""
```

**New models to define for Phase 4** (apply same BaseModel pattern):
```python
# --- Verdict / pipeline output (D-10, D-02) ---
class EscalationVerdict(BaseModel):
    action: Literal["escalate"]
    reason: str
    risk_signals: list[str]   # which signals triggered (rule/haiku/category/conflict/stale/key/guard/critique)

class DraftVerdict(BaseModel):
    action: Literal["draft"]
    body_html: str            # citation-grounded HTML reply
    citations: list[Citation] # from knowledge_mcp.models.Citation
    critique_scores: CritiqueScores

class PipelineResult(BaseModel):
    verdict: EscalationVerdict | DraftVerdict

# --- Stage outputs (each stage is a Pydantic-validated struct) ---
class ClassifyOutput(BaseModel):
    category: Literal["order_tracking", "returns_refunds_exchanges",
                       "quality_complaint", "policy_product"]
    high_risk: bool
    confidence: Literal["high", "med", "low"]   # D-06 coarse buckets

class ExtractOutput(BaseModel):
    order_code: Optional[str] = None
    customer_email: Optional[str] = None
    issue_type: str
    product_refs: list[str] = []
    resolved_order_id: Optional[str] = None   # from selless resolve_order (D-07)
    requires_order_data: bool

class CritiqueScores(BaseModel):
    faithfulness: Literal["pass", "fail"]
    policy_match: Literal["pass", "fail"]
    tone_completeness: Literal["pass", "fail"]
    overall: Literal["pass", "fail"]
    feedback: str
```

---

### `src/pipeline/orchestrator.py` (service/orchestrator, request-response)

**Analog:** `src/work_queue/worker.py` — sequential staged flow with early-exit and structured error handling.

**Imports pattern** (`src/work_queue/worker.py` lines 31–55):
```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.config import SendMode
from src.guards.pii import redact_text
from src.observability import emit_alert, increment
```

**Sequential staged pipeline pattern** (`src/work_queue/worker.py` lines 80–228) — the `process_queue_row` function is the direct structural analog. Each numbered step maps to an orchestrator stage:

```python
async def run_pipeline(
    ticket_id: int,
    conversations: list[Conversation],
    settings: Any,
) -> PipelineResult:
    """
    Staged pipeline: classify → risk-check → extract → ground → draft → critique → guard.
    Each stage returns a Pydantic model; any escalation signal returns EscalationVerdict early.
    PII is redacted before any log/trace write (D-12 / CLAUDE.md).
    """
    # ── Stage 1: Inject-screen the email body (D-14) ─────────────────────────
    # Wrap body in untrusted XML delimiter; run deterministic injection patterns.
    # Suspicion → return EscalationVerdict immediately.

    # ── Stage 2: Classify (Haiku 4.5, D-03/D-05/D-06) ───────────────────────
    classify_out: ClassifyOutput = await _run_classify(body_delimited, settings)
    if classify_out.high_risk or classify_out.confidence == "low":
        return EscalationVerdict(action="escalate", reason="classifier", ...)

    # ── Stage 3: Extract + resolve_order (Haiku 4.5, D-07) ──────────────────
    extract_out: ExtractOutput = await _run_extract(body_delimited, classify_out, settings)
    if extract_out.requires_order_data and extract_out.resolved_order_id is None:
        return EscalationVerdict(action="escalate", reason="missing_key", ...)

    # ── Stage 4: Ground via MCPs (Knowledge + Selless) ───────────────────────
    ground_out: GroundOutput = await _run_ground(extract_out, settings)
    if ground_out.conflict and not ground_out.resolved_by_override:
        return EscalationVerdict(action="escalate", reason="conflict_flag", ...)
    if ground_out.stale_only:
        return EscalationVerdict(action="escalate", reason="stale_only_grounding", ...)

    # ── Stage 5: Draft (Sonnet 4.6, D-03/D-11) ──────────────────────────────
    draft_body = await _run_draft(ground_out, extract_out, settings)

    # ── Stage 6: Output guard (deterministic, D-13) ──────────────────────────
    if _has_commitment_language(draft_body):
        return EscalationVerdict(action="escalate", reason="guard_commitment_language", ...)

    # ── Stage 7: Self-critique (Sonnet 4.6 critic agent, D-12) ──────────────
    critique: CritiqueScores = await _run_critique(draft_body, ground_out, settings)
    if critique.overall == "fail":
        draft_body = await _run_draft(ground_out, extract_out, settings, feedback=critique.feedback)
        critique2 = await _run_critique(draft_body, ground_out, settings)
        if critique2.overall == "fail":
            return EscalationVerdict(action="escalate", reason="critique_fail_after_redraft", ...)

    return DraftVerdict(action="draft", body_html=draft_body, ...)
```

**Error handling pattern** (`src/work_queue/worker.py` lines 229–339) — mirror the same except/retry taxonomy for LLM client calls:
```python
    except SomeLLMFatalError as exc:
        redacted_error = f"llm_fatal: {type(exc).__name__} (no ticket details logged)"
        logger.error("pipeline_fatal_error",
                     extra={"ticket_id": ticket_id, "error_type": type(exc).__name__})
        raise  # caller (worker) handles dead-letter

    except SomeLLMTransientError as exc:
        redacted_error = f"llm_transient: {type(exc).__name__} (details redacted — D-12)"
        logger.warning("pipeline_transient_error",
                       extra={"ticket_id": ticket_id, "error_type": type(exc).__name__})
        raise  # caller handles retry / backoff
```

---

### `src/pipeline/stages/classify.py` (service/agent, request-response)

**Analog:** `src/selless_mcp/server.py` `_impl_*` pattern — standalone async function, injectable client, testable without framework.

**_impl pattern** (`src/selless_mcp/server.py` lines 168–172):
```python
async def _impl_get_order_status(order_id: str, client: SellessClient | None = None) -> OrderDetail:
    c = client or _get_client()
    raw = await c.fetch_order(order_id)
    return apply_order_whitelist(raw)
```

**Apply to classify.py:**
```python
async def run_classify(
    body_delimited: str,
    model_client: Any | None = None,   # injectable for tests (MockLLMClient)
) -> ClassifyOutput:
    """Classify ticket into support category + confidence + high_risk flag.

    Model: Haiku 4.5 (D-03 hot-path model — cheap/fast).
    Output: ClassifyOutput (Pydantic-validated).
    Escalation signals: high_risk=True OR confidence='low'.
    PII: body_delimited is already injection-screened; do NOT log raw.
    """
    client = model_client or _get_llm_client()
    # ... PydanticAI agent call → structured ClassifyOutput
    result = await client.run_structured(CLASSIFY_SYSTEM_PROMPT, body_delimited, ClassifyOutput)
    return result
```

---

### `src/pipeline/stages/extract.py` (service/agent, request-response)

**Analog:** `src/selless_mcp/server.py` `_impl_resolve_order` — structured extraction + external key resolution.

**resolve_order pattern** (`src/selless_mcp/server.py` lines 217–220):
```python
async def _impl_resolve_order(param: str, client: SellessClient | None = None) -> ResolvedOrder:
    c = client or _get_client()
    raw = await c.resolve_order(param)
    return ResolvedOrder(**raw)
```

**Apply to extract.py:**
```python
async def run_extract(
    body_delimited: str,
    classify_out: ClassifyOutput,
    mcp_client: Any | None = None,   # injectable Selless MCP client for tests
    llm_client: Any | None = None,
) -> ExtractOutput:
    """Extract structured fields; resolve order_code → internal order_id via Selless MCP.

    Model: Haiku 4.5.
    Missing key when requires_order_data=True → caller escalates (D-07).
    Calls selless_mcp.resolve_order(order_code) for internal ID resolution.
    """
```

---

### `src/pipeline/stages/ground.py` (service/agent, request-response)

**Analog:** `src/knowledge_mcp/server.py` — MCP tool orchestration, citation assembly, conflict/stale awareness.

**MCP tool call pattern** (`src/knowledge_mcp/server.py` lines 36–67):
```python
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def semantic_search(query: str, top_k: int = 5) -> SemanticSearchResult:
    candidates = await hybrid_search(query, top_k=top_k)
    citations = assemble_citations(candidates)
    citations, resolved_by_override = await apply_override(citations)
    conflict_result = apply_conflict_flag(citations)
    return SemanticSearchResult(
        citations=citations,
        conflict=conflict_result.has_conflict,
        resolved_by_override=resolved_by_override,
    )
```

**Citation/conflict/stale metadata shapes** (`src/knowledge_mcp/models.py` lines 24–44):
```python
class Citation(BaseModel):
    recency_flag: Optional[str] = None   # D-15: "stale" if flagged
    conflict_id: Optional[str] = None   # D-14: CONTRA-* if part of known conflict

class SemanticSearchResult(BaseModel):
    conflict: bool              # D-13: True → orchestrator must escalate
    resolved_by_override: bool  # D-14: True → override wins, no escalation needed
```

**Apply to ground.py:**
```python
async def run_ground(
    extract_out: ExtractOutput,
    knowledge_mcp: Any | None = None,   # injectable for tests
    selless_mcp: Any | None = None,
) -> GroundOutput:
    """Call Knowledge MCP (semantic_search, lookup_threshold, lookup_code, get_template)
    and Selless MCP (get_order_status, get_customer_info) to assemble grounding context.

    Escalation signals passed back to orchestrator:
      - result.conflict=True AND resolved_by_override=False → escalate (D-09)
      - all supporting citations have recency_flag="stale" → stale_only=True → escalate (D-09)
    """
```

---

### `src/pipeline/stages/draft.py` (service/agent, request-response)

**Analog:** `src/selless_mcp/server.py` `_impl_*` pattern for structured agent call.

**Inline citation constraint** (D-11 — no analog in codebase yet, use research pattern):
The drafter must attach inline citations (e.g. `[src: WorkFlow.svg]`) to every factual claim so the critic's faithfulness dimension can verify attribution. This is a prompt-engineering pattern, not a code pattern.

**Apply to draft.py:**
```python
async def run_draft(
    ground_out: GroundOutput,
    extract_out: ExtractOutput,
    llm_client: Any | None = None,
    critique_feedback: str | None = None,   # populated on redraft pass (D-12)
) -> str:
    """Draft a citation-grounded customer reply using Sonnet 4.6 (D-03).

    System prompt is prompt-cached (CLAUDE.md cost discipline).
    Email body is always passed as untrusted XML-delimited data (D-14).
    Inline citations required in output for faithfulness check (D-11).
    critique_feedback: non-None on the one-redraft pass (D-12).
    Returns: HTML body string (ready for Freshdesk POST).
    """
```

---

### `src/pipeline/stages/critique.py` (service/agent, request-response)

**Analog:** `src/selless_mcp/server.py` `_impl_*` injectable pattern — independent critic agent, structured Pydantic output.

**Apply to critique.py:**
```python
async def run_critique(
    draft_body: str,
    ground_out: GroundOutput,
    llm_client: Any | None = None,   # separate Sonnet 4.6 client instance (D-03)
) -> CritiqueScores:
    """Score draft against faithfulness / policy_match / tone_completeness (D-12).

    Model: Sonnet 4.6 CRITIC (separate agent from drafter — more objective, D-03).
    Output: CritiqueScores (Pydantic-validated; overall='fail' → orchestrator redrafts once).
    Rubric dimensions match Phase-5 eval rubric (D-12 requirement for consistency).
    """
```

---

### `src/pipeline/escalation.py` (utility/guard, event-driven)

**Analog:** `src/guards/loop_guard.py` — deterministic rule functions returning `(bool, reason_str)` tuple, no LLM involvement.

**Deterministic guard pattern** (`src/guards/loop_guard.py` — same structural shape as `should_suppress`):
```python
def should_suppress(
    conv: Conversation,
    headers: dict | None,
    from_email: str | None,
    selless_sync_user_ids: frozenset[int],
) -> tuple[bool, str]:
    """Return (suppress, reason). Single source of truth — called from both
    resolve step and worker (D-08 fix #4)."""
```

**Apply to escalation.py:**
```python
def check_deterministic_escalation(
    body_raw: str,
    classify_out: ClassifyOutput,
) -> tuple[bool, str]:
    """Deterministic keyword/rule escalation check (D-08 layer 1).

    Returns (should_escalate, reason).
    Checks: money/refund terms, legal/complaint terms, high_risk category marker.
    No LLM call — business logic rules, not toxicity filtering (CLAUDE.md).
    Conservative: any hit → escalate.
    """

def check_conflict_escalation(
    search_result: SemanticSearchResult,
) -> tuple[bool, str]:
    """D-09: conflict flag forces escalation unless policy_resolution override applies."""
    if search_result.conflict and not search_result.resolved_by_override:
        return True, "knowledge_conflict_unresolved"
    return False, ""

def check_stale_escalation(citations: list[Citation]) -> tuple[bool, str]:
    """D-09: if the ONLY evidence for a needed claim is stale-flagged → escalate."""
    if citations and all(c.recency_flag == "stale" for c in citations):
        return True, "stale_only_grounding"
    return False, ""
```

---

### `src/pipeline/guards.py` (middleware/guard, request-response)

**Analog:** `src/guards/pii.py` — deterministic singleton utility, no LLM, returns transformed/flagged output.

**Singleton lazy-init pattern** (`src/guards/pii.py` lines 39–53):
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

**Deterministic guard returning (bool, reason)** pattern — copy from `loop_guard.should_suppress`:
```python
# Compiled regex set loaded once (lazy singleton, same as pii.py pattern)
_COMMITMENT_PATTERNS: list[re.Pattern] | None = None

def _get_commitment_patterns() -> list[re.Pattern]:
    global _COMMITMENT_PATTERNS
    if _COMMITMENT_PATTERNS is None:
        _COMMITMENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _COMMITMENT_TERMS]
    return _COMMITMENT_PATTERNS

def check_commitment_language(body_html: str) -> tuple[bool, str]:
    """D-13: deterministic regex gate. Returns (blocked, reason).
    Match → block send + escalate. Never auto-strip and send.
    """
    for pat in _get_commitment_patterns():
        if pat.search(body_html):
            return True, f"commitment_language:{pat.pattern[:40]}"
    return False, ""

def screen_injection(body_raw: str) -> tuple[bool, str]:
    """D-14: deterministic injection pattern screen. Returns (suspicious, reason).
    Wrap body in XML delimiters at prompt construction; this checks for
    known injection phrases before prompt construction.
    """
```

---

### `src/pipeline/tracing.py` (utility/config, event-driven)

**Analog:** `src/observability.py` — thin wrapper over observability primitives.

**No close codebase analog** for Langfuse + OpenTelemetry (first LLM tracing in the codebase). Use RESEARCH.md pattern: OpenTelemetry SDK → Langfuse exporter. Wrap in the same module-level function style as `src/observability.py`.

**observability.py pattern to mirror:**
```python
# src/observability.py — increment() + emit_alert() thin wrappers
def increment(metric: str, **labels: Any) -> None: ...
def emit_alert(event: str, **context: Any) -> None: ...
```

**Apply to tracing.py:**
```python
# Module-level OTel tracer init (lazy, like pii.py engines)
_tracer: Any | None = None

def get_tracer():
    global _tracer
    if _tracer is None:
        from opentelemetry import trace
        _tracer = trace.get_tracer("csbot.pipeline")
    return _tracer

def trace_stage(stage_name: str, ticket_id: int, **attrs):
    """Context manager: wraps a pipeline stage in an OTel span → Langfuse."""
```

---

### `src/pipeline/errors.py` (utility/errors)

**Analog:** `src/freshdesk_io/errors.py` — three-class error taxonomy (fatal / transient / rate-limit).

**Error taxonomy pattern** (`src/freshdesk_io/errors.py` lines 1–35):
```python
class FreshdeskRateLimitError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")

class FreshdeskTransientError(Exception):
    """Raised on 5xx / transport timeout. Safe to retry with backoff."""

class FreshdeskFatalError(Exception):
    """Raised on 400/401/403/404/409. Do NOT retry — dead-letter immediately."""
```

**Apply to errors.py:**
```python
class PipelineFatalError(Exception):
    """LLM call returned an unrecoverable error (auth failure, invalid model).
    Worker dead-letters the row immediately — no retry."""

class PipelineTransientError(Exception):
    """LLM call failed transiently (network, 5xx). Worker retries with backoff."""

class PipelineEscalationError(Exception):
    """Pipeline exited via escalation path (not an error — signals clean early exit).
    Carries the EscalationVerdict for the caller."""
    def __init__(self, verdict: "EscalationVerdict") -> None:
        self.verdict = verdict
        super().__init__(f"escalated: {verdict.reason}")
```

---

### `src/config.py` (config — extend existing)

**Analog:** self — extend the existing `Settings` class and `__repr__` redaction.

**Phase 3 extension pattern** (`src/config.py` lines 90–129) — the `# === Phase 3 additions` block is the direct template to copy for Phase 4:
```python
# === Phase 3 additions — grounding layer =====================================
selless_api_base_url: str = Field(
    default="https://api.selless.dev/...",
    description="...",
)
selless_api_gateway_key: str = Field(
    default="",
    description="Optional gateway auth header value — NEVER log this value",
)
voyage_api_key: str = Field(
    default="",
    description="Voyage AI API key for voyage-3-large embeddings — NEVER log",
)
```

**Secret redaction pattern** (`src/config.py` lines 142–151):
```python
def __repr__(self) -> str:
    """Never expose api_key, webhook_secret, selless_api_gateway_key, or voyage_api_key."""
    return (
        f"Settings(send_mode={self.send_mode!r}, "
        f"freshdesk_domain={self.freshdesk_domain!r}, "
        f"freshdesk_api_key=<REDACTED>, webhook_secret=<REDACTED>, "
        f"selless_api_gateway_key=<REDACTED>, voyage_api_key=<REDACTED>)"
    )
```

**New Phase 4 fields to add** (copy the same Field pattern):
```python
# === Phase 4 additions — reply pipeline =====================================
anthropic_api_key: str = Field(
    default="",
    description="Anthropic API key — NEVER log this value",
)
classify_model: str = Field(
    default="claude-haiku-4-5",
    description="Haiku model for classify/extract/risk stages (D-03 hot path)",
)
draft_model: str = Field(
    default="claude-sonnet-4-6",
    description="Sonnet model for draft + self-critique stages (D-03)",
)
langfuse_public_key: str = Field(
    default="",
    description="Langfuse public key — NEVER log",
)
langfuse_secret_key: str = Field(
    default="",
    description="Langfuse secret key — NEVER log",
)
langfuse_host: str = Field(
    default="https://cloud.langfuse.com",
    description="Langfuse host (self-hosted or cloud)",
)
# Extend __repr__ to redact anthropic_api_key, langfuse_secret_key
```

---

### `src/work_queue/worker.py` — DRY_RUN seam replacement (D-02)

**Exact seam location** (`src/work_queue/worker.py` lines 201–219):
```python
# ── Step 6: Canned reply body (Phase 2 placeholder) ──────────────────
# SEAM: Phase 4 replaces this with classify → retrieve → draft pipeline.
# The variable name 'canned_body' signals this is intentional scaffolding.
canned_body = (
    "<p>Thank you for contacting support. "
    "We have received your message and will respond shortly.</p>"
)

# ── Step 7: Send reply (mode-aware D-05 + send-intent fix #1) ────────
await send_reply(
    client=client,
    conn=conn,
    ticket_id=ticket_id,
    inbound_msg_id=inbound_msg_id,
    body=canned_body,
    mode=settings.send_mode,
    row_id=row_id,
    claim_token=claim_token,
)
```

**Replace with** (preserving surrounding structure — steps 5 and 7 are untouched):
```python
# ── Step 6: Run orchestrator pipeline (Phase 4 — replaces canned_body) ───
from src.pipeline.orchestrator import run_pipeline
pipeline_result = await run_pipeline(
    ticket_id=ticket_id,
    conversations=conversations,
    settings=settings,
)

if pipeline_result.action == "escalate":
    # Escalated tickets are logged but not sent (D-10 — no draft in DRY_RUN)
    logger.info(
        "worker_escalated",
        extra={"row_id": row_id, "ticket_id": ticket_id,
               "reason": pipeline_result.reason},
    )
    await _mark_status(conn, row_id, "escalated")
    increment("escalated_total")
    return

reply_body = pipeline_result.body_html

# ── Step 7: Send reply (mode-aware D-05 + send-intent fix #1) ────────
await send_reply(
    client=client,
    conn=conn,
    ticket_id=ticket_id,
    inbound_msg_id=inbound_msg_id,
    body=reply_body,
    mode=settings.send_mode,
    row_id=row_id,
    claim_token=claim_token,
)
```

---

## Shared Patterns

### PII Redaction Before Any Log/Trace Write
**Source:** `src/guards/pii.py` lines 56–82 + `src/work_queue/send.py` lines 93–121
**Apply to:** `orchestrator.py`, `tracing.py`, any stage that logs ticket content

```python
from src.guards.pii import redact_text

# RULE: call redact_text() BEFORE any logger.* call, DB persist, or OTel span attribute
# that contains ticket body / customer content.
redacted_body = redact_text(raw_body)
logger.info("stage_input", extra={"ticket_id": ticket_id, "preview": redacted_body[:100]})
```

The `send.py` persistence boundary enforces this structurally (`src/work_queue/send.py` lines 106–116):
```python
async def _dry_run(conn, ticket_id, inbound_msg_id, body):
    redacted_body = redact_text(body)   # enforced HERE at persistence boundary
    await conn.execute(
        "INSERT INTO queue.dry_run_log (ticket_id, inbound_msg_id, action, body) VALUES ($1,$2,$3,$4)",
        ticket_id, inbound_msg_id, "reply", redacted_body,
    )
```

### Secret Redaction in `__repr__`
**Source:** `src/config.py` lines 142–151
**Apply to:** Phase 4 `Settings` additions — `anthropic_api_key`, `langfuse_secret_key` must be added to the `__repr__` exclusion list and never appear in logs.

### Tenacity Retry + Error Taxonomy for LLM Client
**Source:** `src/freshdesk_io/client.py` lines 53–95 + `src/freshdesk_io/errors.py`
**Apply to:** Any new HTTP/LLM client wrapper in the pipeline (Anthropic SDK calls via httpx fallback, Langfuse exporter)

```python
def _freshdesk_wait(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, FreshdeskRateLimitError):
        return float(exc.retry_after)
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    return base + random.uniform(-1.0, 1.0)

# Mirror for LLM client:
def _llm_wait(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, PipelineTransientError) and hasattr(exc, "retry_after"):
        return float(exc.retry_after)
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    return base + random.uniform(-1.0, 1.0)
```

```python
retry_dec = retry(
    stop=stop_after_attempt(settings.retry_max_attempts),
    wait=_llm_wait,
    retry=retry_if_exception_type((PipelineTransientError, httpx.TransportError)),
    reraise=True,
)
```

### Injectable Singleton Client Pattern
**Source:** `src/selless_mcp/server.py` lines 112–143 — `_get_client()` / `set_selless_client()` pattern
**Apply to:** Every pipeline stage that calls an LLM or MCP client

```python
_llm_client: Any | None = None

def set_llm_client(client: Any) -> None:
    global _llm_client
    _llm_client = client

def _get_llm_client() -> Any:
    global _llm_client
    if _llm_client is None:
        from anthropic import AsyncAnthropic
        _llm_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _llm_client
```

Tests call `set_llm_client(MockLLMClient())` — same pattern as `set_selless_client(MockSellessClient())`.

### Deterministic Guard Returns `(bool, str)` Tuple
**Source:** `src/guards/loop_guard.py` `should_suppress()` — returns `(suppress: bool, reason: str)`
**Apply to:** `escalation.py` `check_deterministic_escalation()`, `guards.py` `check_commitment_language()`, `guards.py` `screen_injection()`

Always returns `(bool, reason_str)` so the caller can log the exact reason in the escalation verdict's `risk_signals` list.

### Structured Logging with `extra={}` Dict
**Source:** `src/work_queue/worker.py` throughout — `logger.info("event_name", extra={"key": val})`
**Apply to:** All pipeline stages — use the same `logger.info/warning/error("event_name", extra={...})` pattern. Never log raw ticket body — always `redact_text()` first.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/pipeline/tracing.py` (Langfuse/OTel) | utility | event-driven | No OTel/Langfuse instrumentation exists yet — first LLM tracing in the codebase. Use RESEARCH.md patterns: OTel SDK + Langfuse exporter. Mirror the thin-wrapper style of `src/observability.py`. |

---

## Metadata

**Analog search scope:** `src/` (all 44 Python files)
**Files scanned:** 13 files read in full
**Pattern extraction date:** 2026-06-02
