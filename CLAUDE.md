<!-- GSD:project-start source:PROJECT.md -->
## Project

**Customer Support Email Automation (Phase 1)**

An AI system that automates customer-support **email** for a US e-commerce business: it re-classifies incoming tickets, extracts the key information needed to answer, and drafts & sends replies **directly into the existing ticket via the Freshdesk API**. It serves the internal CS operation (CS agents + ops) handling ~23,000 emails per 7 days, in English. Phase 1 **answers customers only** — it never executes operational actions (refund, replace, order changes); those stay manual on the Selless CS Portal.

**Core Value:** AI sends accurate, trustworthy customer replies at scale so support volume grows without growing headcount linearly — **answer quality is non-negotiable; nothing ships until it clears an evaluation bar.**

### Constraints

- **Integration**: AI must post replies through the **Freshdesk API into the existing ticket** — Why: keep full conversation history intact inside Freshdesk for agents.
- **Data access**: Selless reads go through a **dedicated MCP** with scoped permissions/rate-limit/logging — Why: native Selless APIs are scattered and not designed for AI; uncontrolled access is unsafe.
- **Architecture**: keep **two separate MCPs** — Selless (transactional, real-time, lookup-by-ID) and Knowledge (semantic RAG, centralized, cited) — Why: different update cadence, query model, and quality-control needs; mixing them is an architectural mistake.
- **Quality**: nothing goes live before clearing the offline-eval bar; high-risk categories always escalate to a human — Why: 23k/week volume makes a bad auto-reply high-blast-radius.
- **Rollout**: offline eval → shadow mode → live 5% → scale to 100% — Why: de-risk a large-volume rollout incrementally.
- **Knowledge readiness**: knowledge base must be surveyed and centralized before AI relies on it — Why: scattered/conflicting sources cause hallucinations; AI must not read raw Confluence/Sheets per-reply.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Claude Sonnet 4.6** (Anthropic API) | API model `claude-sonnet-4-6` | Primary drafting + extraction model | Recommended production default in the current generation: near-Opus quality at ~$3/$15 per 1M tokens with 1M-token context at standard pricing. Strong instruction-following + grounding/citation behavior — the two traits that matter most for non-hallucinating support replies. Native MCP client support. |
| **Claude Haiku 4.5** (Anthropic API) | API model `claude-haiku-4-5` | Classification + routing + cheap extraction | $1/$5 per 1M tokens. At 3,200+ emails/day, the classifier and guardrail-router run on every email — Haiku keeps that high-frequency hot path cheap and fast while Sonnet handles the lower-volume final draft. |
| **Claude Opus 4.7** (Anthropic API) | API model `claude-opus-4-7` | Eval judge / hard-case escalation only | $5/$25. Reserve for LLM-as-judge scoring in the eval harness and for the hardest drafting cases — not the per-email hot path. |
| **MCP — Python SDK** | `mcp` v1.x (FastMCP 3.0 high-level API, Jan 2026) | Knowledge RAG MCP server | RAG/embeddings tooling is Python-native; co-locate the Knowledge server with the ingest/index pipeline. FastMCP's decorator API minimizes boilerplate. Stay on v1.x — v2 is pre-alpha. |
| **MCP — TypeScript SDK** | `@modelcontextprotocol/sdk` v1.29.x | Selless transactional MCP server | If Selless backend is Node/TS, build the transactional MCP there to reuse existing API clients/auth. Stay on v1.x; v2 is pre-alpha (anticipated Q1 2026, slipped). |
| **Claude Code agent team** (`.claude/`) / **Claude Agent SDK** | Phase 4 runtime | Agent/orchestration layer for the email pipeline | Claude Code agent team (.claude/) on Claude Agent SDK — PydanticAI deferred. Replaced by a standard Claude Code team-kit: cs-lead + subagents + deterministic hooks. Self-contained, local-first, Bedrock-ready (env-driven). PydanticAI superseded per 2026-06-02 design pivot. |
| **pgvector on PostgreSQL** | pgvector 0.8.x on Postgres 16/17 | Vector store for the Knowledge RAG base | Default 2026 recommendation for RAG under ~10–50M vectors. A policy/product KB is small (thousands–tens-of-thousands of chunks). One database for vectors + metadata + citations + ingest bookkeeping; no second datastore to operate. Hybrid search via `pg_trgm`/Postgres FTS + vector. |
| **Voyage `voyage-3-large`** | current | Embeddings for the Knowledge base | Top MTEB retrieval quality in 2026; strong on the precise-policy retrieval this domain needs. English-only requirement removes the multilingual constraint. |
| **Freshdesk REST API v2** | v2 | Read tickets/conversations, post replies into existing tickets | Constraint-mandated integration surface. `POST /api/v2/tickets/{id}/reply` to send, `GET /api/v2/tickets/{id}/conversations` for history. Basic Auth with API key (key as username, dummy password). |
| **Langfuse** | self-hosted (OSS) or Cloud | Tracing + observability + score store | Open-source, self-hostable, framework-agnostic via OpenTelemetry. Feature parity self-host vs cloud. Becomes the single sink for production traces *and* eval scores. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Ragas** | latest | RAG-specific eval metrics (faithfulness, context precision/recall, answer relevancy) | Core of the offline harness for the *retrieval+grounding* dimension. Minimal config, no labels needed for retrieval metrics. |
| **DeepEval** | latest | General LLM eval + CI/CD gate + custom criteria (G-Eval) | Score drafts vs golden agent replies (semantic similarity, correctness, custom "matches-policy" rubrics). First-class pytest/CI integration → the "nothing ships until it clears the bar" gate. |
| **promptfoo** | latest | PR-time eval gate + prompt regression + red-teaming | CLI eval gate in CI on prompt changes; red-team probes for jailbreak/prompt-injection (a real risk since email content is attacker-controllable). |
| **Microsoft Presidio** | `presidio-analyzer` / `presidio-anonymizer` 2.x | PII detection + redaction | Redact customer PII before logging/tracing and before non-essential model context. Pair with guardrails (Presidio is PII-only). |
| **NeMo Guardrails** *or* **Guardrails AI** | latest | Topic/safety/escalation rails + I/O validation | Enforce the "high-risk → human" routing (money/legal/complex) and validate output structure/groundedness. Presidio runs as a sidecar for PII. |
| **Anthropic Python SDK** | `anthropic` latest | LLM calls, prompt caching, Batch API | Prompt-cache the system prompt + retrieved policy blocks (largest cost lever at this volume). Use Batch API (50% off) for the offline eval runs over the golden dataset. |
| **httpx + tenacity** | latest | Freshdesk API client + retry/backoff | Respect Freshdesk per-minute rate limits (plan-dependent, e.g. ~700/min Enterprise); backoff on 429. |
| **OpenTelemetry SDK** | latest | Trace export to Langfuse | Vendor-neutral instrumentation so observability isn't locked to one tool. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Python packaging/venv | Fast, reproducible; standard in 2026 Python projects. |
| **pytest + DeepEval** | Eval-as-tests in CI | Treat the quality bar as a test suite that gates merges. |
| **Freshdesk data export** | Build the golden dataset | Historical tickets + agent replies via Freshdesk's export (UI/scheduled export), not a convenient live API path — confirmed in PROJECT context. Normalize export → golden JSONL. |
| **Docker Compose** | Local stack (Postgres+pgvector, Langfuse, MCP servers) | Reproducible dev/staging. |
## Installation
# Core pipeline (Python)
# RAG + eval
# Dev / eval gate
# Selless MCP server (if Node/TS backend)
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Claude Sonnet 4.6 | GPT-5.x / Gemini 3.x Pro | If existing org contracts/credits favor them, or if a head-to-head eval on *your* golden set shows higher faithfulness. Decide by eval, not by leaderboard. |
| Claude Sonnet 4.6 | Cohere Command R+ | If you want a model architected specifically for grounded RAG + citations and prefer its native retrieval behavior. Worth A/B-ing in the harness. |
| pgvector | Qdrant | If the KB unexpectedly grows past ~10M vectors or you need top-tier ANN price/performance at scale. Unlikely for a policy/product KB. |
| pgvector | Pinecone | Only if you want zero infra ops and accept managed cost; hard to justify here since you'll already run Postgres. |
| Voyage voyage-3-large | OpenAI text-embedding-3-large | If you're already on OpenAI infra/billing and want one vendor. Comparable quality. |
| Voyage voyage-3-large | Google text-embedding-005 | If embedding cost dominates (~30x cheaper); KB is small so cost is unlikely to dominate. |
| PydanticAI | LangGraph | If the pipeline grows genuinely stateful/branching multi-agent loops with HITL checkpoints + time-travel debugging. Adds orchestration overhead/latency; overkill for a linear classify→retrieve→draft flow. |
| PydanticAI | LlamaIndex | If retrieval becomes the dominant complexity (advanced indexing, query planning) — can be added *alongside* PydanticAI for the RAG layer only. |
| Langfuse | Arize Phoenix | If OpenTelemetry/OpenInference rigor + heavy offline experimentation UI is the priority and you have platform-eng capacity. |
| Langfuse | LangSmith | Only if you commit to LangChain/LangGraph; note LangSmith has **no self-hosted** option. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| MCP SDK **v2** (TS or Python) | Pre-alpha as of May 2026; v2 stable slipped past its Q1 2026 target | MCP SDK v1.x (recommended for production) |
| A **single merged MCP** for Selless + Knowledge | Violates a locked project decision; different cadence, query model (lookup-by-ID vs semantic), and QC needs | Two separate MCP servers |
| **Reading raw Confluence/Sheets per reply** | Scattered/conflicting/stale sources are the top hallucination risk (per PROJECT) | Centralized ingest→normalize→index pipeline into pgvector with citations |
| **Opus 4.7 on the per-email hot path** | 5x Haiku / 1.7x Sonnet cost at 3,200+/day adds up fast | Haiku for classify/route, Sonnet for draft; Opus only for judge/hard cases |
| **No prompt caching / no Batch API** | Largest avoidable cost at this volume; offline eval re-runs are expensive | Anthropic prompt caching (cache system + policy context) + Batch API (50% off) for eval runs |
| **LLM "moderation-only" as the high-risk gate** | Money/legal/complex routing is business logic, not toxicity filtering | Explicit guardrail rails + a Haiku classifier with conservative thresholds → human |
| **Logging raw ticket text to traces** | Customer PII leaks into observability store | Presidio redaction before Langfuse/log sink |
## Stack Patterns by Variant
- Build *both* MCP servers in Python (FastMCP), share auth/HTTP client utilities.
- Because: one language, one toolchain, simpler ops.
- Selless MCP in TypeScript (`@modelcontextprotocol/sdk`), Knowledge MCP in Python (FastMCP).
- Because: each server reuses its data source's native client/auth; both speak the same MCP wire protocol so the pipeline is language-agnostic to them.
- Add a reranker (Cohere Rerank or Voyage rerank) + hybrid search before changing the LLM.
- Because: Ragas context-precision/recall isolates retrieval failure from generation failure — fix the right layer.
- Golden set = Freshdesk export → normalized JSONL (ticket context, retrieved-or-expected sources, real agent reply as reference).
- Ragas for faithfulness/context metrics; DeepEval (G-Eval custom rubric: factual-correctness + policy-match + tone) vs reference replies; promptfoo as the PR gate.
- Run via Anthropic Batch API to halve cost; write scores back to Langfuse.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pgvector 0.8.x | Postgres 16/17 | Use HNSW index for query speed; IVFFlat only if build time matters. |
| MCP Python SDK v1.x | FastMCP 3.0 | FastMCP 3.0 (Jan 2026) is the high-level API over the v1 core. |
| PydanticAI | anthropic SDK + mcp client | PydanticAI consumes MCP servers as tool sources; confirm MCP client support version at integration time. |
| Langfuse | OpenTelemetry SDK | Instrument via OTel for vendor-neutral export. |
| Ragas / DeepEval | Anthropic or OpenAI judge model | Both support pluggable judge LLMs — point them at Claude (Opus for judge). |
## Future-Phase Tooling (NOT Phase 1 — record only)
| Component | Recommendation | Notes |
|-----------|----------------|-------|
| Orchestration | **LiveKit Agents** (Python 1.5.x, Apache-2.0) or **Pipecat** (BSD-2, by Daily) | LiveKit has native SIP/phone numbers (no Twilio bridge required) + native MCP tool support — reuses the same Selless/Knowledge MCP servers. |
| Telephony | **Twilio** (or LiveKit native SIP) | Twilio if existing carrier relationships; LiveKit SIP to consolidate. |
| STT | **Deepgram Nova-3** | ~6.84% WER, real-time leader (English). |
| TTS | **Cartesia Sonic-3** (~90ms) or **ElevenLabs Flash v2.5** (~75ms) | Latency-critical for natural turn-taking. |
| LLM | Reuse Claude (Sonnet/Haiku) | Same grounding/MCP stack as email. |
- Reuse the *same* classify→retrieve→draft pipeline, MCP servers, RAG store, guardrails, and eval harness — only the channel adapter (web widget + streaming) differs. The Phase-1 architecture should keep the channel layer thin so this is additive, not a rewrite.
## Sources
- platform.claude.com/docs/en/about-claude/pricing — Claude Haiku 4.5 / Sonnet 4.6 / Opus 4.7 availability + pricing (HIGH; corroborated by multiple 2026 pricing trackers and matches runtime model)
- github.com/modelcontextprotocol/typescript-sdk — TS SDK v1.29.0 (Mar 30 2026), v2 pre-alpha, v1.x = production recommended (HIGH). *Note:* one source listed split packages `@modelcontextprotocol/server`/`client` while npm shows `@modelcontextprotocol/sdk` — verify exact package name at install time (MEDIUM on package name).
- github.com/modelcontextprotocol/python-sdk + FastMCP 3.0 (Jan 2026) — Python SDK v1.x, FastMCP high-level API (HIGH)
- developers.freshdesk.com/api/ — v2 reply (`POST /tickets/{id}/reply`), conversations (`GET /tickets/{id}/conversations`), Basic Auth w/ API key, plan-based rate limits (HIGH)
- MTEB 2026 leaderboards (Voyage voyage-3-large lead; OpenAI/Google alternatives) — embeddings (MEDIUM; leaderboard-based)
- 2026 vector DB comparisons (pgvector default <50M; Qdrant best price/perf; Pinecone managed) — vector store (MEDIUM)
- genai.qa / Braintrust / Inference.net 2026 eval-tool comparisons — Ragas (RAG) + DeepEval (CI) + promptfoo (gate/red-team) split (MEDIUM)
- Langfuse docs + 2026 observability comparisons (Langfuse self-host vs LangSmith no-self-host vs Phoenix) — observability (HIGH on capability facts)
- microsoft/presidio + litellm guardrails docs — PII redaction as sidecar to a guardrails platform (HIGH)
- 2026 agent-framework comparisons (PydanticAI type-safe; LangGraph stateful; LlamaIndex RAG) — orchestration (MEDIUM)
- github.com/livekit/agents + 2026 voice-stack guides (Deepgram Nova-3 / Cartesia Sonic / ElevenLabs Flash) — future-phase voice (MEDIUM)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
