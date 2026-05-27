# Feature Research

**Domain:** AI-powered customer-support email automation (US e-commerce, Freshdesk + Selless MCP + RAG knowledge)
**Researched:** 2026-05-27
**Confidence:** HIGH (domain practices well-corroborated across 2025-2026 vendor + practitioner sources; multiple independent sources agree on classification, confidence-gating, shadow mode, staged rollout, and escalation guardrails as standard patterns)

> Scope note: Phase 1 is **email reply drafting + sending only** (no operational actions). Voice and chatbot are explicitly later phases. Features below are tagged with phase relevance. Categorization assumes the Phase 1 charter in PROJECT.md.

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are the non-negotiable building blocks of a credible AI support-email system. Missing any of these makes the system either unsafe or untrustworthy at 23k emails/week.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Intent / ticket classification** | Every AI support system triages first; routing and reply strategy depend on knowing the category | MEDIUM | Re-classify into PROJECT.md categories (order/tracking, returns/refunds/exchanges, quality complaints, policy/product Q). Must emit a category + confidence. Drives the escalation gate. |
| **Key-info extraction** | A reply cannot be grounded without the order ref / customer identity / issue type | MEDIUM | Extracts order ref, customer, issue type from free-text email. Feeds the Selless MCP lookup. Failure to extract a required field is itself an escalation signal. |
| **Retrieval-grounded reply drafting (RAG)** | Ungrounded LLM replies hallucinate policy/order facts — fatal at this volume | HIGH | Two retrieval sources: Selless MCP (order/customer/history, lookup-by-ID) + Knowledge MCP (policy/product, semantic + citations). Reply must cite/anchor to retrieved facts. |
| **Source citation / grounding traceability** | Reviewers and auditors must see *why* the AI said what it said; anti-hallucination | MEDIUM | Each drafted claim should trace to a Selless field or KB passage. Essential for shadow-mode review and post-incident debugging. |
| **Confidence scoring per draft** | The whole rollout safety model depends on a numeric gate ("auto-send only above threshold") | MEDIUM | Industry-standard pattern: low-risk + high-confidence → auto; medium → review; high-risk or low-confidence → human. A self-evaluation/self-grading step on the draft is now common practice. |
| **High-risk category guardrails (auto-escalate)** | Money / legal / complaints / complex-multi-issue must never auto-send | MEDIUM | Hard rules independent of confidence. Mirrors "never email a refund code without verified ticket ID" guardrail discipline. Routes to human with reasoning + retrieved context attached. |
| **Human-in-the-loop routing with context** | Escalations must arrive with full context so the agent doesn't restart | MEDIUM | Attach AI reasoning, category, confidence, retrieved facts, and proposed draft to the escalated ticket. Repetition/context-loss is the #1 CSAT killer in handoffs. |
| **Post reply into existing Freshdesk ticket via API** | Conversation history must stay intact inside Freshdesk for agents | MEDIUM | Hard constraint from PROJECT.md. Idempotency + correct-ticket targeting are critical (wrong-ticket posting = blast radius). |
| **Shadow mode (draft, don't send)** | Standard de-risking step; AI runs alongside agents with zero customer impact | MEDIUM | AI drafts + scores; agents review/score before any live sending. Generates the labeled data that validates the confidence gate. |
| **Offline evaluation harness vs. golden dataset** | Nothing ships before clearing a measurable bar; this is the quality gate | HIGH | Score AI drafts against historical Freshdesk agent replies (golden set via export). Stable benchmark across model/prompt versions. Proxy metric: "% of past tickets the AI would have answered correctly." |
| **Staged / percentage rollout (5% → scale)** | Controlled exposure caps the cost of a regression at high volume | MEDIUM | Gradual autonomy. Needs a kill switch / instant rollback to shadow. Hold-and-monitor gates between stages. |
| **Live quality monitoring + analytics dashboard** | At 3,200+/day you cannot rollout safely without real-time visibility | MEDIUM | Track auto-send rate, escalation rate, confidence distribution, edit rate, error/incident flags. Central place to fine-tune thresholds. |
| **Feedback loop from agent edits** | Agent corrections are the cheapest, highest-signal training/eval data | MEDIUM | Capture edit deltas in shadow + agent-assist; feed back into prompts/eval set/threshold tuning. The flywheel that improves quality over time. |
| **Tone / brand consistency controls** | An off-brand or tone-deaf reply erodes trust even when factually correct | MEDIUM | System-prompt style guide + few-shot brand examples. Checked in eval rubric, not just human vibes. |
| **PII / data-access scoping & logging** | Selless reads must be scoped, rate-limited, logged (per constraints) | MEDIUM | Enforced at the MCP layer. AI fetches only needed fields. Auditability is table stakes for handling customer/order data. |

### Differentiators (Competitive Advantage)

Not required to ship, but materially raise quality, safety, or trust beyond the baseline. Several align directly with the Core Value ("answer quality is non-negotiable").

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Self-critique / LLM-as-judge gate before send** | A second-pass model grading the draft against a rubric catches errors confidence alone misses | MEDIUM | Now a leading-edge practice. Reuses the offline eval rubric at inference time. Strong fit given the no-bad-reply mandate. |
| **Hallucination / unsupported-claim detector** | Flags any claim not backed by a retrieved source before send | HIGH | Real-time guardrail layer ("watchtower") checking responses against policy + grounding. Highest-value given that stale/conflicting KB is the stated top hallucination risk. |
| **Per-category confidence thresholds** | Returns can tolerate more autonomy than complaints; one global threshold is crude | LOW | Tunable thresholds per ticket type. Cheap to add once classification + confidence exist; big safety/coverage payoff. |
| **Prior-ticket-pattern retrieval** | Reusing how similar past tickets were resolved improves accuracy + consistency | MEDIUM | Surfaced in PROJECT.md as a Knowledge MCP source. Acts as few-shot grounding from real resolutions. |
| **Reply-quality rubric scoring surfaced in dashboard** | Lets ops watch *quality* trend, not just volume, during rollout | MEDIUM | Combine automated rubric scores + agent thumbs/edits into a tracked quality KPI per stage/category. |
| **Auto-detected KB gaps / conflicts** | When the AI can't ground an answer, that signals a missing/stale KB entry for the CS team to author | MEDIUM | Closes the loop with the knowledge survey. Turns escalations into KB backlog items. |
| **A/B / shadow comparison of prompt or model versions** | Safely compare versions on live traffic without customer impact | MEDIUM | Shadow-testing infrastructure; reuse the same harness for offline + live shadow. |
| **Deflection / resolution metrics** | Quantifies the headcount-leverage value the project exists to deliver | LOW-MEDIUM | "Auto-resolved without human touch" rate. Be careful defining it honestly (resolved ≠ merely answered). Becomes the headline ROI metric. |

### Anti-Features (Commonly Requested, Often Problematic)

Things that sound good but are out of scope or actively dangerous for Phase 1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **AI executes operational actions (refund/replace/order change)** | "Why not finish the job?" | Out of Phase 1 scope; high blast radius; ops stays manual on Selless CS Portal until reply quality is proven | Answer customers only; escalate action requests to agents who act in Selless. |
| **Full auto-send from day one** | Speed / "just turn it on" | Skips shadow + staged rollout; unbounded risk at 23k/week | Offline eval → shadow → 5% → scale, gated by quality holding. |
| **Multilingual / translation support** | "Future-proofing" | US market is English-only; adds eval surface, tone drift, and complexity for zero current value | Explicitly English-only. Revisit only if market changes. |
| **AI authoring / curating KB content** | "Let it fill the gaps it finds" | Self-authored knowledge compounds hallucination; KB quality is unverified | AI *surfaces* gaps/conflicts; CS team authors. Ingest/normalize existing sources only. |
| **AI reads raw Confluence / Google Sheets per reply** | "Just point it at the docs" | Scattered, stale, conflicting; per-reply reads are slow and unsafe | Centralized RAG store with citations, built via ingest→normalize→index pipeline. |
| **Single global confidence threshold treated as "good enough"** | Simplicity | Masks category-specific risk; over-sends on complaints, under-sends on easy tickets | Per-category thresholds + hard high-risk overrides. |
| **Auto-close tickets after AI reply** | Tidy queue | Premature closure hides failures and frustrates customers who needed more | Leave open / let normal workflow + customer reply drive closure; monitor reopen rate. |
| **Sentiment-driven auto-tone manipulation beyond brand guide** | "Sound empathetic" | Emotionally charged tickets should escalate, not get a cleverly-worded auto-reply | Route frustrated/angry tickets to humans; keep tone within a fixed brand guide for the rest. |
| **Voice / chatbot work bundled into Phase 1** | "Do it all at once" | Different latency, infra, and eval models; dilutes the email quality bar | Defer to later phases (see Future Consideration). |

---

## Feature Dependencies

```
Knowledge survey + ingest/normalize/index pipeline
        └──requires──> Knowledge MCP (semantic RAG + citations)

Selless MCP (scoped reads, rate-limit, logging)
        └──feeds──> Key-info extraction (order ref → lookup)

Intent/ticket classification
        └──feeds──> High-risk guardrails (category gate)
        └──feeds──> Per-category confidence thresholds

Key-info extraction + Knowledge MCP + Selless MCP
        └──requires──> Retrieval-grounded reply drafting
                              └──requires──> Source citation / grounding
                              └──enhances──> Self-critique gate
                              └──enhances──> Hallucination detector

Confidence scoring + High-risk guardrails
        └──requires──> Human-in-the-loop routing (with context)

Offline eval harness (golden dataset)
        └──gates──> Shadow mode
                        └──gates──> Staged rollout (5% → scale)
                                        └──requires──> Live monitoring dashboard
                                        └──requires──> Kill switch / rollback

Shadow mode + Agent-assist
        └──produces──> Feedback loop from agent edits
                              └──enhances──> Offline eval set + threshold tuning
```

### Dependency Notes

- **Reply drafting requires both MCPs + extraction:** you cannot ground a reply without the order facts (Selless) and policy facts (Knowledge); extraction is what turns the email into a Selless lookup key.
- **Guardrails require classification:** the high-risk gate is category-driven, so classification must land first and be reliable on the risky categories specifically.
- **Shadow mode is gated by the offline eval bar:** don't run shadow on a model that hasn't cleared offline eval — you'd waste agent review time. Shadow then validates that offline scores predict real-world quality.
- **Staged rollout requires live monitoring + rollback:** percentage rollout without real-time quality visibility and an instant kill switch is just slow-motion risk.
- **Feedback loop enhances everything upstream:** agent edits during shadow/assist are the cheapest source of new golden examples and the empirical basis for setting thresholds.
- **Conflicts:** full auto-send conflicts with shadow mode / staged rollout (mutually exclusive postures); AI-authored KB conflicts with the citation-grounding integrity model.

---

## MVP Definition

### Launch With (v1 — Phase 1 charter)

The minimum to safely validate "AI sends accurate replies at scale."

- [ ] Intent/ticket classification (with confidence) — gates everything downstream
- [ ] Key-info extraction — required to ground replies
- [ ] Selless MCP (scoped reads, rate-limit, logging) — order/customer/history facts
- [ ] Knowledge MCP (semantic RAG + citations) — policy/product facts
- [ ] Knowledge survey + ingest→normalize→index pipeline — prerequisite for trustworthy RAG
- [ ] Retrieval-grounded reply drafting with source grounding — the core deliverable
- [ ] Confidence scoring + high-risk category guardrails — safety gate
- [ ] Human-in-the-loop escalation with full context — for everything that fails the gate
- [ ] Post reply into existing Freshdesk ticket via API — integration constraint
- [ ] Offline evaluation harness vs. golden dataset — the quality bar that gates go-live
- [ ] Shadow mode — validate before any live send
- [ ] Staged rollout (5% → scale) + kill switch — controlled exposure
- [ ] Live monitoring dashboard — auto-send rate, escalation rate, confidence dist, edit rate
- [ ] Tone/brand consistency controls — in-prompt + in eval rubric

### Add After Validation (v1.x)

Add once the core send loop holds quality at scale.

- [ ] Feedback loop from agent edits → eval set + threshold tuning — trigger: enough shadow/live edits accumulated
- [ ] Per-category confidence thresholds — trigger: data shows category-specific risk profiles
- [ ] Self-critique / LLM-as-judge pre-send gate — trigger: confidence alone misses error classes
- [ ] Hallucination / unsupported-claim detector — trigger: grounding-miss incidents observed
- [ ] Auto-detected KB gaps/conflicts surfaced to CS — trigger: escalations cluster on missing knowledge
- [ ] Deflection / auto-resolution metrics — trigger: stable auto-send share to measure ROI honestly

### Future Consideration (v2+ — separate phases)

- [ ] **Operational actions (refund/replace)** — defer until reply quality is proven; high blast radius
- [ ] **Contact Form chatbot (≈phase 3)** — synchronous chat; reuses RAG + guardrails but adds session/turn handling, faster latency budget, live handoff UX
- [ ] **Voice / call support (later phase)** — hardest: sub-500ms latency target, ASR/TTS, barge-in, live escalation. Expect ~40-50%+ containment as a *realistic* early bar (some verticals 80%+); CSAT depends heavily on clean context handoff. No concrete design yet.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Classification + confidence | HIGH | MEDIUM | P1 |
| Key-info extraction | HIGH | MEDIUM | P1 |
| Selless MCP (scoped reads) | HIGH | MEDIUM | P1 |
| Knowledge MCP (RAG + citations) | HIGH | HIGH | P1 |
| KB survey + ingest pipeline | HIGH | HIGH | P1 |
| Grounded reply drafting | HIGH | HIGH | P1 |
| High-risk guardrails / escalation | HIGH | MEDIUM | P1 |
| HITL routing with context | HIGH | MEDIUM | P1 |
| Freshdesk API reply posting | HIGH | MEDIUM | P1 |
| Offline eval harness | HIGH | HIGH | P1 |
| Shadow mode | HIGH | MEDIUM | P1 |
| Staged rollout + kill switch | HIGH | MEDIUM | P1 |
| Live monitoring dashboard | HIGH | MEDIUM | P1 |
| Tone/brand controls | MEDIUM | MEDIUM | P1 |
| Feedback loop from agent edits | HIGH | MEDIUM | P2 |
| Per-category thresholds | MEDIUM | LOW | P2 |
| Self-critique gate | MEDIUM | MEDIUM | P2 |
| Hallucination detector | HIGH | HIGH | P2 |
| KB gap/conflict detection | MEDIUM | MEDIUM | P2 |
| Deflection metrics | MEDIUM | LOW | P2 |
| Operational actions | HIGH | HIGH | P3 |
| Chatbot phase | MEDIUM | HIGH | P3 |
| Voice phase | MEDIUM | HIGH | P3 |

**Priority key:** P1 = must have for Phase 1 launch · P2 = add after validation · P3 = future phase

---

## Competitor / Pattern Reference

| Pattern | How leading tools do it | Our approach |
|---------|-------------------------|--------------|
| Agent assist vs. auto-send | Intercom Fin, Freshdesk Freddy, Decagon offer both: Copilot suggests to agents *and* an autonomous mode | Start as assist/shadow; graduate to auto-send only above the confidence gate + outside high-risk categories. |
| Confidence gating | Low-risk+high-conf auto; medium → approval; high-risk/low-conf → human | Same tiering, with hard category overrides for money/legal/complex. |
| Self-evaluation before send | Model grades own draft vs. rubric; sends only if it clears | Adopt as a P2 differentiator reusing the offline eval rubric. |
| Shadow + gradual autonomy | Run alongside agents, expand autonomy incrementally, post-launch QA reviews | Offline → shadow → 5% → scale, with rollback. |
| Deflection metric | AI-handled / total conversations (some report 80%+) | Track honestly as auto-resolved-without-human; don't conflate "answered" with "resolved." |
| Voice containment (future) | 40-50% typical, 80%+ best-case; sub-500ms latency, clean handoff | Note as benchmark for a later voice phase; not Phase 1. |

---

## Sources

- Crisp — Automating Email Responses With AI (https://crisp.chat/en/blog/automating-email-responses-with-ai/)
- Fin.ai — Best AI Email Agents for Customer Support (https://fin.ai/learn/ai-agents-email-support)
- Assembled — AI Email Agent (https://www.assembled.com/features/ai-email-agent)
- Decagon — AI customer service automation: triage, response generation (https://decagon.ai/blog/ai-customer-service-automation)
- Kustomer — Automated Ticket Resolution Using AI (2026) (https://www.kustomer.com/resources/blog/automated-ticket-resolution-using-ai/)
- AgentixLabs — Human-in-the-loop AI agents: risky loophole checks (https://www.agentixlabs.com/blog/general/human-in-the-loop-ai-agents-7-proven-risky-loophole-checks/)
- IrisAgent — AI Ticket Automation 2026 Guide (https://irisagent.com/ai-ticket-automation/) and Voice AI Benchmarks 2026 (https://irisagent.com/blog/voice-ai-customer-service-2026-benchmarks/)
- Cobbai — Shadow Mode, Gradual Autonomy, QA in AI Rollouts (https://cobbai.com/blog/ai-rollout-post-launch-review)
- Statsig — Shadow Testing for AI (https://www.statsig.com/perspectives/shadow-testing-ai-model-evaluation)
- Alhena AI — Dashboard Metrics Decoded (https://alhena.ai/blog/alhena-ai-analytics-dashboard-metrics-decoded/)
- BlueTweak — AI-to-Human Handoff Best Practices 2026 (https://bluetweak.com/blog/ai-to-human-handoff/) and AI Ticket Classification (https://bluetweak.com/blog/ai-ticket-classification/)
- Product School — Evaluation Metrics for AI Products (https://productschool.com/blog/artificial-intelligence/evaluation-metrics)

**Confidence:** HIGH for the table-stakes/differentiator/anti-feature categorization (multiple independent vendor + practitioner sources converge on classification → confidence-gating → shadow → staged rollout → escalation as the standard safe-deployment spine). MEDIUM for specific quantitative benchmarks (deflection 80%+, voice containment 40-87%, sub-500ms latency) — vendor-reported, directionally reliable but not independently audited; treat as planning ranges, not targets.

---
*Feature research for: AI customer-support email automation*
*Researched: 2026-05-27*
