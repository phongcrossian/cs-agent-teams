# Architecture Research

**Domain:** AI-powered customer-support email automation (Freshdesk + dual-MCP RAG, e-commerce)
**Researched:** 2026-05-27
**Confidence:** MEDIUM-HIGH (component model HIGH from PROJECT.md + established patterns; Freshdesk specifics HIGH; rollout-control mechanics MEDIUM)

## Standard Architecture

This domain has a stable, repeatable shape: an **event-driven pipeline** from a ticketing system, through a **stateless reply-generation orchestrator** that grounds itself via tool calls, behind a **guardrail/routing gate** that decides shadow vs. live and escalate vs. answer. Grounding is split across two retrieval surfaces (transactional lookup vs. semantic RAG). A parallel **offline eval harness** replays a golden dataset through the same orchestrator without touching production. The defining architectural choice here is that **the reply generator never reads source systems directly** — all data access is mediated by the two MCP servers, and all sending is mediated by the routing/guardrail layer.

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  INGESTION / TRIGGER                                                   │
│  Email → IMAP/SMTP fwd → Freshdesk → Automation "Trigger Webhook"      │
│                                              │ (POST ticket id+event)  │
└──────────────────────────────────────────────┼────────────────────────┘
                                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PIPELINE / ORCHESTRATION (stateless workers behind a queue)           │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────────┐    │
│  │ Intake & │→ │ Classify &   │→ │ Reply-Generation Orchestrator │    │
│  │ Dedup    │  │ Extract      │  │ (plan → retrieve → draft)     │    │
│  └──────────┘  └──────┬───────┘  └───────────┬───────────────────┘    │
│                       │ (category, risk flags)│ tool calls            │
│                       ▼                       ▼                       │
│              ┌─────────────────────────────────────────┐             │
│              │  GUARDRAIL / ESCALATION + ROUTING GATE   │             │
│              │  risk rules · grounding/citation check · │             │
│              │  shadow-vs-live · % rollout bucketing     │             │
│              └───────────┬───────────────┬───────────────┘            │
└──────────────────────────┼───────────────┼───────────────────────────┘
              live & passed │               │ shadow OR escalate
                            ▼               ▼
              ┌──────────────────┐   ┌────────────────────┐
              │ Reply Poster     │   │ Draft/Note Poster  │
              │ Freshdesk /reply │   │ Freshdesk /notes   │
              └──────────────────┘   │ (+ assign to agent)│
                                     └────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  GROUNDING (two MCP servers — NEVER merged)                            │
│  ┌────────────────────────────┐   ┌────────────────────────────────┐  │
│  │ MCP Selless (transactional)│   │ MCP Knowledge (semantic RAG)   │  │
│  │ lookup-by-ID: order/cust/  │   │ vector search + rerank +       │  │
│  │ history; scoped read, rate │   │ citations over centralized KB  │  │
│  │ limit, audit log           │   │                                │  │
│  └────────────┬───────────────┘   └───────────────┬────────────────┘  │
└───────────────┼──────────────────────────────────┼─────────────────────┘
                ▼                                   ▼
        Selless platform APIs            ┌───────────────────────────┐
        (two-way sync w/ Freshdesk)      │ KB Ingest Pipeline        │
                                         │ Confluence + GSheet/Doc → │
                                         │ normalize → chunk → embed │
                                         │ → index (scheduled)       │
                                         └───────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  OFFLINE EVAL HARNESS (out-of-band, same orchestrator code)            │
│  golden export (tickets + real agent replies) → replay → score vs ref │
│  → metrics report (gate for shadow / % increases)                     │
├──────────────────────────────────────────────────────────────────────┤
│  OBSERVABILITY / QUALITY DASHBOARD                                     │
│  traces · per-ticket decisions · citation coverage · escalation rate  │
│  · shadow agent scores · live outcomes · MCP latency/error/rate-limit │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Ingestion/Trigger | Detect a ticket needing AI handling; hand off ticket id + event | Freshdesk **Automation → Trigger Webhook** (push) to an HTTPS endpoint; polling the List Tickets API as fallback |
| Intake & Dedup | Fetch full ticket, idempotency guard, enqueue | Webhook receiver → message queue; dedup key = ticket id + conversation hash |
| Classify & Extract | Re-classify ticket into support category; extract order ref / customer / issue type; emit risk signals | LLM call (often single combined call) with structured (JSON) output |
| Reply-Generation Orchestrator | Plan what data is needed, call MCP tools, draft a cited reply | Stateless worker; LLM with tool-calling over the two MCPs; retrieve→synthesize→draft loop |
| MCP Selless (transactional) | Scoped read-only lookups by ID (order status, customer, history) | MCP server wrapping curated Selless API fields; per-tool scopes, rate limit, audit log |
| MCP Knowledge (semantic RAG) | Semantic search over centralized KB; return passages **with citations** | MCP server over a vector store + reranker; returns source ids/URLs |
| KB Ingest Pipeline | Pull → normalize → chunk → embed → index KB content on a schedule | Connectors (Confluence API, Google Sheets/Docs API) → normalizer → embedder → vector index |
| Guardrail/Escalation + Routing Gate | Decide answer-vs-escalate (risk rules), enforce grounding/citation checks, decide shadow-vs-live, apply % rollout bucketing | Deterministic rules + LLM-based checks; central decision point, every reply passes through |
| Reply Poster | Post approved reply into the existing ticket | Freshdesk `POST /tickets/{id}/reply` |
| Draft/Note Poster | In shadow/escalate, attach AI draft as private note + route to agent | Freshdesk `POST /tickets/{id}/notes` (private) + ticket assignment/tagging |
| Offline Eval Harness | Replay golden dataset through orchestrator, score vs. reference agent replies | Batch runner reusing orchestrator code; LLM-as-judge + retrieval metrics; report |
| Observability/Dashboard | End-to-end traces, decision audit, quality metrics, MCP health | Structured logs + traces → metrics store → dashboard |

## Recommended Project Structure

```
src/
├── ingestion/              # webhook receiver + (fallback) poller
│   ├── webhook.ts          # verifies + enqueues Freshdesk events
│   └── poller.ts           # safety-net polling of List Tickets
├── pipeline/               # the per-ticket processing flow (queue workers)
│   ├── intake.ts           # fetch ticket, idempotency/dedup
│   ├── classify.ts         # category + extraction (structured output)
│   └── orchestrator.ts     # plan → retrieve(MCP) → draft, returns candidate reply
├── guardrails/             # the routing & safety gate (central decision point)
│   ├── risk-rules.ts       # money/legal/complex → escalate
│   ├── grounding-check.ts  # citation coverage / hallucination check
│   └── router.ts           # shadow-vs-live + % rollout bucketing
├── freshdesk/              # all Freshdesk API I/O isolated here
│   ├── client.ts           # rate-limit aware client (Retry-After honoring)
│   ├── reply.ts            # POST /reply (live send)
│   └── note.ts             # POST /notes (shadow draft / escalation)
├── mcp-selless/            # transactional MCP server (separate deployable)
├── mcp-knowledge/          # RAG MCP server (separate deployable)
├── kb-ingest/              # ingest→normalize→chunk→embed→index pipeline
│   ├── connectors/         # confluence, gsheets, gdocs
│   ├── normalize.ts        # canonical doc format, conflict tagging
│   └── index.ts            # chunk + embed + upsert to vector store
├── eval/                   # offline eval harness (reuses pipeline/ + guardrails/)
│   ├── golden/             # exported tickets + reference replies
│   ├── runner.ts           # replay through orchestrator
│   └── scorers.ts          # judge + retrieval metrics
├── observability/          # tracing, decision log, metrics emit
└── config/                 # rollout %, risk thresholds, feature flags
```

### Structure Rationale

- **`freshdesk/` isolated:** the only module allowed to call Freshdesk; centralizes rate-limit handling (50–5000 calls/hr depending on plan — material at 3,200 emails/day) and the reply-vs-note distinction.
- **`mcp-selless/` and `mcp-knowledge/` are separate deployables, not just folders:** they have different scaling, security, and update-cadence profiles. The orchestrator depends only on their tool contracts.
- **`guardrails/` is the single chokepoint** every candidate reply passes through — this is where shadow/live and % rollout live, so the decision is auditable in one place.
- **`eval/` imports `pipeline/` and `guardrails/`** rather than reimplementing them — the eval must score the *same* code path that runs in production, or the quality bar is meaningless.

## Architectural Patterns

### Pattern 1: Push trigger via Freshdesk Automation Webhook (not polling)

**What:** Configure a Freshdesk Automation ("Ticket is created/updated" → "Trigger Webhook") to POST the ticket id + event to your intake endpoint. Keep a low-frequency poller of the List Tickets API only as a reconciliation safety net.
**When to use:** Default for this system. Push gives near-real-time handoff and avoids burning the API rate budget on polling.
**Trade-offs:** Webhooks can be missed (no native delivery guarantee) → the safety-net poller and idempotent intake cover gaps. Polling alone wastes rate limit and adds latency.

### Pattern 2: MCP-mediated grounding (orchestrator never touches source systems directly)

**What:** The reply generator only obtains facts through `MCP Selless` (transactional, lookup-by-id) and `MCP Knowledge` (semantic, cited). It cannot call Selless APIs or read Confluence/Sheets directly.
**When to use:** Always here — it is a hard project constraint and the core anti-hallucination boundary.
**Trade-offs:** Adds an indirection layer to build and maintain, but yields scoping, rate-limiting, audit logging, and a clean swap point. Critically, the **two-MCP split is deliberate**: transactional data is real-time, exact, lookup-by-ID, low-cardinality-per-ticket; knowledge is slow-changing, fuzzy, semantic, cited. They have different freshness SLAs, query models, and QC needs — merging them would force one access pattern onto both and entangle KB-quality work with order-data access control.

### Pattern 3: Single routing gate carrying shadow/live + percentage rollout

**What:** Every candidate reply hits one router that decides: (a) escalate? (risk rules), (b) grounded enough? (citation check), (c) what mode is this ticket in? Mode is resolved by **deterministic bucketing** — hash(ticket id) mod 100 < rollout_percent → live, else shadow — read from config/feature flags.
**When to use:** From the first shadow run onward; the same gate evolves from "always shadow" → "5% live" → "100%" by changing one config value.
**Trade-offs:** Centralizing is the right call (auditable, single source of truth). Hash-bucketing gives a stable, deterministic split so the same ticket doesn't flip modes on retry; the alternative (random) breaks idempotency.

**Example:**
```typescript
function resolveMode(ticketId: string, cfg: RolloutConfig): "live" | "shadow" {
  if (cfg.globalShadowOnly) return "shadow";
  const bucket = stableHash(ticketId) % 100;        // 0..99, deterministic
  return bucket < cfg.livePercent ? "live" : "shadow";
}
// shadow → post AI draft as private NOTE + (optionally) assign for agent review
// live   → post AI reply via /reply, but only after guardrails pass
```

### Pattern 4: Eval harness reuses the production code path

**What:** The offline harness replays golden tickets through the *same* classify→orchestrate→guardrail code, with MCP calls pointed at a frozen KB snapshot + recorded/sandboxed Selless reads, then scores drafts against the real agent reply (LLM-as-judge + retrieval metrics). It never posts to Freshdesk.
**When to use:** As the gate before shadow and before every rollout-percentage increase.
**Trade-offs:** Requires the orchestrator to be cleanly invocable out-of-band (a forcing function for good separation). Reference-based scoring is imperfect (multiple valid answers) — pair it with rubric/groundedness scoring.

## Data Flow

### Request Flow (per ticket, live path)

```
Email → Freshdesk ticket → Automation webhook (POST id+event)
    ↓
Intake (fetch ticket, dedup) → enqueue
    ↓
Classify & Extract (category, order ref, customer, risk flags)
    ↓
Orchestrator: plan → MCP Selless (order/customer/history) + MCP Knowledge (cited policy/product)
    ↓
Candidate reply (with citations)
    ↓
Guardrail/Router: risk? grounded? mode?
    ├── escalate / shadow → Freshdesk POST /notes (private draft) + assign agent
    └── live & passed     → Freshdesk POST /reply (into existing ticket)
    ↓
Observability: trace + decision record + metrics
```

### Key Data Flows

1. **KB ingest (offline, scheduled):** Confluence + Google Sheets/Docs → normalize (canonical format, flag stale/conflicting) → chunk → embed → upsert into vector index that MCP Knowledge serves. Runs on a cadence independent of ticket traffic.
2. **Golden dataset (offline, one-way export):** Freshdesk export → tickets + real agent replies → eval harness as reference answers. PROJECT.md notes this is an export, not a live API path.
3. **Selless ↔ Freshdesk two-way sync:** independent of the AI pipeline; the AI reads order/customer data through MCP Selless and posts replies through the Freshdesk API — it does not drive the sync.

## Suggested Build Order (dependencies)

This ordering follows the rollout gates and the dependency graph. Components are listed so each phase produces something testable.

1. **KB inventory/survey** (PROJECT.md prerequisite) — must precede ingest; determines coverage, conflicts, gaps. Blocks meaningful RAG.
2. **Freshdesk I/O layer + ingestion trigger** — webhook receiver, rate-limit-aware client, reply/note posting. Foundational; everything posts through it.
3. **MCP Selless** and **KB ingest pipeline → MCP Knowledge** — the two grounding surfaces. Can proceed in parallel after #1/#2. Knowledge depends on the survey (#1); Selless depends only on Selless API access.
4. **Classify & Extract** — needs ticket data (from #2) but not full grounding; can be built and eval'd somewhat independently.
5. **Reply-Generation Orchestrator** — depends on #3 (both MCPs) and #4 (extraction output).
6. **Offline Eval Harness** — depends on #4/#5 (the code path it replays) and the golden export. **Gate to proceed.**
7. **Guardrail/Routing Gate** — risk rules + grounding check + shadow/% control. Depends on #5; enables shadow mode (drafts as notes).
8. **Observability/Dashboard** — should be built alongside #6/#7 so shadow scores and live outcomes are measurable; it is the instrument that authorizes each % increase.
9. **Staged rollout** — flip config: shadow → 5% → scale to 100%, each step gated by eval + dashboard quality.

**Critical-path note:** #1 (KB survey) and #6 (eval harness) are the two gating items. Build order should front-load the survey and treat the eval harness + dashboard as first-class deliverables, not afterthoughts — the project's core value ("nothing ships until it clears an evaluation bar") makes them load-bearing.

## Scaling Considerations

At ~3,200 emails/day (~2–3/min average, with peaks), raw throughput is modest; the constraints are **rate limits and quality**, not compute.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Phase 1 (~3.2k/day) | Single queue + horizontally-scalable stateless workers is ample. Main risk is the Freshdesk API rate limit (3,000–5,000/hr/plan) — coalesce calls, honor `Retry-After`, cache ticket fetch. |
| 2–5x volume / future channels | Separate queues per stage; backpressure; per-MCP autoscaling. Selless reads likely the next ceiling (its own rate limit/log). |
| Multi-channel (voice/chatbot, future phases) | Promote orchestrator + MCPs to shared services behind a thin channel-adapter layer (email/chat/voice adapters feed the same pipeline). The two-MCP grounding core is channel-agnostic and should be designed to be reused. |

### Scaling Priorities

1. **First bottleneck: Freshdesk API rate limit.** Mitigate with a rate-limit-aware client (queue + `Retry-After`), minimize calls per ticket, batch where possible.
2. **Second bottleneck: MCP Selless throughput / Selless backend.** Its own rate-limit + caching of stable fields (e.g., customer record) per ticket.
3. **Third: vector index latency under reranking.** Cache embeddings, tune top-k + rerank depth.

## Anti-Patterns

### Anti-Pattern 1: Merging the two MCPs into one "data" service

**What people do:** Build a single retrieval/data layer covering both order lookups and policy knowledge.
**Why it's wrong:** Transactional and semantic data have opposite query models, freshness SLAs, and quality-control needs; merging entangles order-data access control with KB-quality work and forces a wrong access pattern on one side.
**Do this instead:** Keep MCP Selless (exact, lookup-by-id, scoped) and MCP Knowledge (fuzzy, cited, centralized) separate — as PROJECT.md mandates.

### Anti-Pattern 2: Letting the orchestrator read source systems directly

**What people do:** Have the reply LLM query Selless APIs or read Confluence/Sheets per reply for convenience.
**Why it's wrong:** No scoping/audit, uncontrolled rate usage, and reading raw/conflicting KB per-reply is the top hallucination risk called out in PROJECT.md.
**Do this instead:** All grounding through the MCPs; KB read only from the curated, indexed store.

### Anti-Pattern 3: Eval harness that re-implements the pipeline

**What people do:** Write a separate scoring script with its own prompt/retrieval logic.
**Why it's wrong:** It scores something other than what ships; the quality bar becomes fiction.
**Do this instead:** The harness invokes the production orchestrator/guardrail code on golden inputs.

### Anti-Pattern 4: Polling Freshdesk as the primary trigger

**What people do:** Poll the List Tickets API on a tight loop.
**Why it's wrong:** Burns the limited API rate budget and adds latency.
**Do this instead:** Automation webhook as primary; low-frequency poller only as a reconciliation safety net, with idempotent intake.

### Anti-Pattern 5: Random (non-deterministic) shadow/live bucketing

**What people do:** Roll a random number per processing attempt to pick mode.
**Why it's wrong:** A retried ticket can flip between shadow and live, breaking idempotency and audit.
**Do this instead:** Deterministic hash(ticket id) bucketing against the rollout percentage.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Freshdesk (trigger) | Automation → Trigger Webhook (POST on create/update) | No native delivery guarantee → idempotent intake + safety poller |
| Freshdesk (write) | `POST /tickets/{id}/reply` (live) and `POST /tickets/{id}/notes` (shadow/escalate, private) | Rate limits 3,000–5,000/hr by plan; honor `Retry-After`; replies/notes are editable |
| Selless platform | Wrapped by MCP Selless (curated read-only fields) | Native APIs scattered/not AI-ready; scope + rate-limit + audit at the MCP |
| Confluence | KB ingest connector (scheduled pull) | Stale/conflicting content is the top hallucination risk — normalize + flag |
| Google Sheets/Docs | KB ingest connector (scheduled pull) | Same normalization/conflict handling |
| Freshdesk (export) | One-time/periodic export for golden dataset | Export path, not live API; feeds eval only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Ingestion ↔ Pipeline | Message queue | Decouples webhook spikes from processing; enables idempotency/retry |
| Orchestrator ↔ MCP Selless / MCP Knowledge | MCP tool calls (network) | Orchestrator depends only on tool contracts; MCPs are separate deployables |
| Pipeline ↔ Guardrail/Router | In-process call returning candidate reply | Single chokepoint; emits the auditable decision |
| Guardrail ↔ Freshdesk layer | In-process → HTTP | Only path that can send; mode decides reply vs note |
| Eval harness ↔ Pipeline/Guardrail | Imports production code | Replays same path; MCPs pointed at frozen snapshot/sandbox |

## Sources

- PROJECT.md (project constraints, two-MCP decision, rollout stages, risk categories) — HIGH (authoritative project context)
- Freshdesk API docs — replies (`/tickets/{id}/reply`) vs private notes (`/tickets/{id}/notes`), Automations endpoints, rate limits (3,000–5,000/hr by plan, `Retry-After`) — HIGH (https://developers.freshdesk.com/api/)
- Freshdesk Automations "Trigger Webhook" action (push trigger on create/update) — MEDIUM (established product feature; exact UI doc not re-fetched)
- AI support / RAG reference architectures (orchestration, rerankers, shadow→cohort rollout, golden-set + LLM-judge eval) — MEDIUM (multiple 2026 industry sources, corroborating):
  - https://slashdev.io/blog/enterprise-rag-and-ai-agents-a-reference-architecture
  - https://www.vellum.ai/blog/agentic-rag
  - https://www.kore.ai/blog/what-is-agentic-rag

---
*Architecture research for: AI customer-support email automation (Freshdesk + dual-MCP RAG)*
*Researched: 2026-05-27*
