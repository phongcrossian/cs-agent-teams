# Project Research Summary

**Project:** Customer Support Email Automation (Phase 1)
**Domain:** AI-powered customer-support email automation (classify → extract → ground → draft → send via Freshdesk, dual-MCP RAG, offline eval)
**Researched:** 2026-05-27
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a high-volume (~23k emails/7 days, English-only, US e-commerce) AI support-email system whose defining trait is that **answer quality is non-negotiable — nothing ships until it clears an offline evaluation bar.** Across all four research streams, experts build this exact shape: an event-driven, stateless pipeline that re-classifies a ticket, extracts the order/customer key, grounds a reply through two separate retrieval surfaces (a transactional Selless MCP keyed by ID + a semantic Knowledge MCP with citations), and passes every candidate reply through a single guardrail/routing gate that decides escalate-vs-answer and shadow-vs-live. The recommended stack is Python-primary (PydanticAI orchestration, Claude Haiku for the high-frequency classify/route hot path, Claude Sonnet for drafting, Opus reserved for the eval judge), pgvector + Voyage embeddings for RAG, Freshdesk REST v2 for I/O, and a Ragas/DeepEval/promptfoo eval harness with Langfuse observability — with PII redaction (Presidio) and guardrails (NeMo/Guardrails AI) as cross-cutting safety layers.

The safe-deployment spine is universally agreed and already committed in PROJECT.md: **knowledge survey → MCP grounding layer → classify/draft pipeline → offline eval (the gate) → shadow mode → 5% live → scale to 100%**, each step gated by quality holding. The two architectural non-negotiables are the **two-MCP split** (transactional vs. semantic have opposite query models, freshness SLAs, and QC needs) and **MCP-mediated grounding** (the reply generator never reads source systems directly — this is the core anti-hallucination boundary and a hard project constraint).

The dominant risks are quality and trust, not throughput (3,200/day is modest compute). The top five: (1) hallucinated policies from stale/conflicting KB sources — mitigated by surveying conflicts first and enforcing claim-vs-citation faithfulness; (2) ungrounded refund/financial commitments — mitigated by hard money→escalate rules plus a commitment-language output guard; (3) indirect prompt injection via email body — mitigated by treating email as data, input screening, output verification, and read-only scoped MCP privilege separation; (4) high-risk misclassification routing complaints/legal to auto-reply — mitigated by asymmetric-cost thresholds tuned for recall on escalate classes; and (5) eval metrics that don't correlate with real quality — mitigated by scoring faithfulness/correctness rather than similarity to flawed historical replies, plus a held-out set reconciled against shadow-mode human grades.

## Key Findings

### Recommended Stack

Python-primary stack: the CS-automation pipeline lives in the richest LLM ecosystem (Python), while the two MCP servers split by where their data lives (Knowledge MCP in Python co-located with the ingest/index pipeline; Selless MCP in TypeScript if the Selless backend is Node/TS, else Python). Model tiering is the key cost lever at 3,200+/day: cheap/fast model on the per-email hot path, stronger model only for final drafts, strongest model only off the hot path. See `STACK.md` for full rationale, alternatives, and version compatibility.

**Core technologies:**
- **Claude Haiku 4.5**: classification + routing + cheap extraction — runs on every email; keeps the high-frequency hot path cheap/fast.
- **Claude Sonnet 4.6**: drafting + extraction — near-Opus quality with strong grounding/citation behavior at lower cost; native MCP client support.
- **Claude Opus 4.7**: eval judge / hard-case escalation only — reserved off the hot path.
- **PydanticAI**: orchestration with type-safe schema-enforced outputs — right fit for a mostly-linear pipeline (vs. LangGraph overkill).
- **MCP SDK v1.x** (Python FastMCP 3.0 / TS `@modelcontextprotocol/sdk`): the two MCP servers — stay on v1.x; v2 is pre-alpha.
- **pgvector 0.8.x on Postgres 16/17 + Voyage voyage-3-large**: RAG vector store + embeddings — small KB, one datastore, top retrieval quality.
- **Freshdesk REST API v2**: `POST /tickets/{id}/reply` (live), `POST /tickets/{id}/notes` (shadow/escalate) — constraint-mandated.
- **Ragas + DeepEval + promptfoo + Langfuse**: eval harness (faithfulness/correctness) + CI gate + observability/score store.
- **Presidio + NeMo/Guardrails AI**: PII redaction + topic/safety/escalation rails (cross-cutting).

### Expected Features

Phase 1 is **email reply drafting + sending only** (no operational actions; voice/chatbot are later phases). The table-stakes set forms the safe-deployment spine; differentiators raise quality/safety beyond baseline. See `FEATURES.md` for the full landscape, dependency graph, and prioritization matrix.

**Must have (table stakes):**
- Intent/ticket classification with confidence — gates everything downstream.
- Key-info extraction (order ref, customer, issue type) — turns email into a Selless lookup key.
- Selless MCP (scoped reads, rate-limit, logging) + Knowledge MCP (semantic RAG + citations).
- KB survey + ingest→normalize→index pipeline — prerequisite for trustworthy RAG.
- Retrieval-grounded reply drafting with source citation/traceability.
- Confidence scoring + high-risk category guardrails (money/legal/complex → human).
- Human-in-the-loop routing with full context attached.
- Post reply into existing Freshdesk ticket via API (idempotent, correct-ticket).
- Offline eval harness vs. golden dataset — the quality bar that gates go-live.
- Shadow mode → staged rollout (5% → scale) + kill switch → live monitoring dashboard.
- Tone/brand consistency controls.

**Should have (competitive):**
- Self-critique / LLM-as-judge pre-send gate — catches errors confidence alone misses.
- Hallucination / unsupported-claim detector — highest value given stale-KB risk.
- Per-category confidence thresholds — cheap once classification+confidence exist.
- Feedback loop from agent edits — the quality flywheel.
- Auto-detected KB gaps/conflicts surfaced to CS; deflection/auto-resolution metrics.

**Defer (v2+):**
- Operational actions (refund/replace) — high blast radius; prove reply quality first.
- Contact Form chatbot (≈phase 3); voice/call support (later phase).
- Multilingual support; AI-authored KB content (compounds hallucination).

### Architecture Approach

A stable, repeatable shape: an event-driven pipeline triggered by a Freshdesk Automation webhook (with a low-frequency poller as reconciliation safety net), feeding stateless queue workers that classify→extract→orchestrate a grounded draft, then pass every candidate through a single guardrail/routing gate. The gate enforces risk rules + grounding/citation checks and resolves mode via **deterministic hash-bucketing** (shadow vs. live, % rollout) so retries don't flip modes. A parallel offline eval harness replays the golden dataset through the *same* production code path. See `ARCHITECTURE.md` for the system diagram, project structure, patterns, and anti-patterns.

**Major components:**
1. **Freshdesk I/O layer** (isolated) — only module that calls Freshdesk; centralizes rate-limit handling and reply-vs-note distinction.
2. **Pipeline workers** (intake/dedup → classify/extract → reply orchestrator) — stateless, behind a queue.
3. **Guardrail/Routing gate** — single chokepoint; risk rules, grounding check, shadow/live + % bucketing.
4. **MCP Selless** (transactional, scoped lookup-by-ID) + **MCP Knowledge** (semantic RAG + citations) — separate deployables, never merged.
5. **KB ingest pipeline** — pull→normalize→chunk→embed→index on a schedule.
6. **Offline eval harness** — imports pipeline + guardrails, scores vs. reference; never posts to Freshdesk.
7. **Observability/dashboard** — traces, decision audit, quality metrics, MCP health.

### Critical Pitfalls

Top five of twelve documented (see `PITFALLS.md` for all twelve plus the "looks done but isn't" checklist and recovery strategies):

1. **Hallucinated policies from stale/conflicting KB** — survey conflicts first (not just coverage); attach source/recency/authority metadata in ingest; require claim-vs-citation faithfulness (the cited chunk must contain the asserted fact); gate specific-number claims on retrieval confidence.
2. **Ungrounded financial/refund commitments** — hard money→escalate rule at the routing layer; output guard that blocks commitment language about refunds/credits/charges regardless of category.
3. **Indirect prompt injection via email body** — treat email as data with delimiters; run an injection classifier on inbound; scan drafts for prompt leakage / foreign-customer data; read-only ticket-scoped MCP privilege separation.
4. **High-risk misclassification → auto-reply** — asymmetric-cost thresholds tuned for high recall on escalate classes; any high-risk signal escalates the whole ticket; report per-high-risk-class recall, not overall accuracy.
5. **Eval metrics that don't correlate with real quality** — score faithfulness/correctness not similarity to flawed historical replies; stratify + add adversarial/conflicting-policy cases; hold out a set and reconcile offline scores against shadow human grades.

Plus cross-cutting: runaway send loops/duplicates (idempotency keys + per-ticket reply cap + auto-mail detection), rate-limit cascades (queue + backoff/jitter + DLQ), and monitoring blind spots (live sampling + alert thresholds + kill-switch *before* 5%).

## Implications for Roadmap

The committed rollout already implies the phase spine. Research strongly endorses front-loading the **KB survey** and treating the **eval harness + dashboard** as first-class load-bearing deliverables, not afterthoughts — the "nothing ships until it clears the bar" core value makes them the critical path.

### Phase 1: Knowledge Survey + Conflict Inventory
**Rationale:** PROJECT.md prerequisite and the #1 hallucination defense; blocks meaningful RAG. Must precede ingest.
**Delivers:** Inventory of sources, coverage by ticket type, **conflicts**, update cadence, and tacit-knowledge gaps (a lightweight inventory, not full collection).
**Addresses:** KB survey (table stakes).
**Avoids:** Pitfall 1 (stale/conflicting policy) — conflicts are findings, not edge cases.

### Phase 2: Freshdesk I/O Layer + Ingestion Trigger
**Rationale:** Foundational — everything posts through it; isolating it centralizes rate-limit and reply-vs-note logic early.
**Delivers:** Webhook receiver + safety poller, rate-limit-aware client (honor `Retry-After`), reply/note posting, idempotency + loop guards.
**Uses:** Freshdesk REST v2, httpx + tenacity (STACK.md).
**Implements:** `freshdesk/` + `ingestion/` (ARCHITECTURE.md). **Avoids:** Pitfalls 8 (loops/duplicates) and 9 (rate limits).

### Phase 3: MCP Layer (Selless reads + Knowledge RAG via ingest pipeline)
**Rationale:** The two grounding surfaces; can proceed in parallel after Phases 1–2. Knowledge depends on the survey; Selless depends only on Selless API access.
**Delivers:** MCP Selless (scoped, ticket-ID-keyed reads, rate-limit, audit log) + KB ingest→index → MCP Knowledge (cited, recency/authority metadata).
**Uses:** MCP SDK v1.x, pgvector, Voyage embeddings (STACK.md).
**Avoids:** Pitfall 4 (PII/wrong-customer — identity binding) and 1 (ingest metadata + canonicalization).

### Phase 4: Classify/Extract + Reply-Generation Orchestrator
**Rationale:** Classification gates everything downstream; orchestrator depends on both MCPs + extraction.
**Delivers:** Classifier with confidence + asymmetric thresholds, key-info extraction, grounded cited drafting, commitment-language + entity output guards, injection delimiting/screening, tone/brand controls.
**Uses:** Claude Haiku (classify/route), Claude Sonnet (draft), PydanticAI, Presidio, guardrails (STACK.md).
**Avoids:** Pitfalls 2 (refund commitments), 3 (injection), 5 (misclassification), 11 (tone).

### Phase 5: Offline Eval Harness — THE GATE
**Rationale:** The quality bar that authorizes everything live. Reuses the production code path; gate before shadow and before every % increase.
**Delivers:** Golden set from Freshdesk export → normalized JSONL; Ragas faithfulness/context + DeepEval correctness/tone rubric + promptfoo PR gate; stratified + adversarial + conflicting-policy + escalation cases; held-out set; scores to Langfuse.
**Uses:** Ragas, DeepEval, promptfoo, Opus judge, Batch API (STACK.md).
**Avoids:** Pitfall 6 (golden-set bias) — faithfulness not overlap.

### Phase 6: Guardrail/Routing Gate + Shadow Mode + Observability
**Rationale:** Single chokepoint enabling shadow (drafts as private notes); dashboard must exist before any live send.
**Delivers:** Risk rules + grounding check + deterministic hash-bucket router; structured shadow review (reason codes, grounding correctness, edit distance); live monitoring dashboard + alert thresholds + kill-switch-to-draft-only; explicit go/no-go gate to 5%.
**Uses:** Langfuse, OpenTelemetry (STACK.md).
**Avoids:** Pitfalls 7 (shadow false green light) and 12 (monitoring blind spots).

### Phase 7: Staged Rollout (5% → scale to 100%)
**Rationale:** Controlled exposure; flip one config value, each step gated by eval + dashboard quality.
**Delivers:** 5% live → graduated scaling with hold-and-monitor gates; feedback loop from agent edits; per-category thresholds; deflection metrics (P2 differentiators added here as data accumulates).
**Avoids:** Pitfall 10 (over-automation) — optimize quality-gated coverage, keep escalation rules permanent.

### Phase Ordering Rationale
- **Dependencies:** survey → ingest → Knowledge MCP → orchestrator → eval → guardrail/shadow → rollout is the discovered dependency chain. Selless MCP and KB ingest parallelize after the I/O layer; classify/extract can be built somewhat independently of full grounding.
- **Architecture grouping:** the guardrail gate, shadow mode, and observability cluster naturally (one chokepoint, one decision audit). The eval harness is isolated but must import production code, so it follows the orchestrator.
- **Pitfall avoidance:** front-loading the survey (P1) and making the eval harness + dashboard load-bearing (P5/P6) directly counters the project's two highest-cost failure modes (hallucination, false go-live). Cross-cutting guards (idempotency, injection, PII scoping, commitment-language) are designed in during P2–P4 even though they only *bite* during live rollout.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (MCP/RAG):** RAG component specifics were MEDIUM confidence — chunking strategy, reranking decision, hybrid search tuning, and exact Selless API surface need `/gsd-research-phase`. Confirm exact TS package name at install time.
- **Phase 5 (Eval harness):** eval-tool split (Ragas/DeepEval/promptfoo) is MEDIUM; designing the faithfulness rubric, golden-set stratification, and the quality-bar thresholds warrants focused research.
- **Phase 6 (Guardrail/rollout mechanics):** rollout-control mechanics and shadow go/no-go gate definitions were MEDIUM; worth validating instrumentation patterns.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Freshdesk I/O):** Freshdesk REST v2 endpoints, rate limits, and idempotency patterns are HIGH-confidence and well-documented.
- **Phase 4 (Classify/draft):** structured-output classification and grounded drafting with Claude + PydanticAI are well-established.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | LLM/MCP/Freshdesk/eval core verified against current sources; MEDIUM only on RAG specifics and deferred-phase voice tooling. |
| Features | HIGH | Classification → confidence-gating → shadow → staged rollout → escalation converge across multiple independent vendor + practitioner sources. |
| Architecture | MEDIUM-HIGH | Component model HIGH from PROJECT.md + established patterns; Freshdesk specifics HIGH; rollout-control mechanics MEDIUM. |
| Pitfalls | HIGH | Failure modes well-documented and corroborated; MEDIUM only on exact phase mapping (depends on final roadmap shape). |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address
- **KB quality is unverified** — the survey (Phase 1) is the gate that resolves this; do not design RAG specifics until conflicts/cadence are catalogued.
- **RAG retrieval tuning** — chunking, reranking (Cohere/Voyage rerank), and hybrid-search depth are TBD; let Ragas context-precision/recall isolate retrieval-vs-generation failure before changing the LLM. Handle during Phase 3 planning.
- **Selless backend language + API surface** — stack splits depending on whether Selless is Node/TS or Python; "scattered, not AI-ready" APIs mean latency/availability is uncertain. Confirm and load-test before 5%.
- **Quantitative benchmarks (deflection 80%+, voice containment) are vendor-reported** — treat as planning ranges, not targets.
- **Quality-bar threshold values** — the actual numeric go/no-go gates (grounding-correct ≥ X%, refund-leakage = 0) must be set during Phase 5/6 against held-out + shadow data, not assumed up front.

## Sources

### Primary (HIGH confidence)
- platform.claude.com/docs — Claude Haiku/Sonnet/Opus pricing + availability.
- developers.freshdesk.com/api — v2 reply/notes/conversations, Basic Auth, rate limits, Automation webhook.
- github.com/modelcontextprotocol (python-sdk + typescript-sdk) — MCP SDK v1.x production recommendation, FastMCP 3.0.
- OWASP LLM Prompt Injection Prevention Cheat Sheet; AWS Securing Bedrock Agents against indirect prompt injection.
- PROJECT.md — committed constraints (two-MCP split, escalation rules, rollout stages, risk categories).
- microsoft/presidio + litellm guardrails docs — PII redaction sidecar pattern.
- Langfuse docs + 2026 observability comparisons.

### Secondary (MEDIUM confidence)
- MTEB 2026 leaderboards (Voyage voyage-3-large) + 2026 vector DB comparisons (pgvector default <50M).
- 2026 eval-tool comparisons (Ragas + DeepEval + promptfoo split) and agent-framework comparisons (PydanticAI vs LangGraph).
- AI support / RAG reference architectures (slashdev, vellum, kore.ai) — orchestration, rerankers, shadow→cohort rollout, golden-set + LLM-judge eval.
- Vendor/practitioner feature sources (Crisp, Fin.ai, Assembled, Decagon, Kustomer, Cobbai, Statsig, BlueTweak, IrisAgent) — table-stakes/differentiator categorization.
- Hallucination/failure-mode sources (Air Canada case via EvidentlyAI, Parloa, InsightFinder, Lakera, InjecAgent benchmark).

### Tertiary (LOW confidence)
- Real-world LLM production failures (single-author Medium) — directional only.
- Vendor-reported quantitative benchmarks (deflection/containment rates) — planning ranges, not audited targets.

---
*Research completed: 2026-05-27*
*Ready for roadmap: yes*
