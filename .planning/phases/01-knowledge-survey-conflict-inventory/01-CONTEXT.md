# Phase 1: Knowledge Survey & Conflict Inventory - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce a trustworthy, reviewable picture of the existing knowledge base — what sources exist, what they cover by ticket type, and where they conflict or go stale — so RAG ingest (Phase 3) builds on a known foundation. Phase 1 is a **discovery / inventory deliverable**, not implementation code. No RAG store, no embeddings, no API integration in this phase.

**In scope:**
- Source inventory (every KB doc/page/sheet with metadata)
- Frozen snapshots of source content committed to repo
- Coverage map: KB sources ↔ ticket types
- Conflict inventory: stale, contradictory, missing policy content
- Glossary of internal jargon (newly identified necessity — see Specifics)
- State/template-code mapping (newly identified necessity — see Specifics)
- CS-team-owned knowledge gaps surfaced as explicit action items

**Out of scope (defer to later phases):**
- Building the RAG store / chunking / embeddings — Phase 3
- Authoring new KB content to fill gaps — CS-team responsibility, surfaced not solved here
- Selless MCP / Freshdesk integration — Phase 2 / 3
- Live access to source systems via API — viewer-only via CS Lead

</domain>

<decisions>
## Implementation Decisions

### Survey Input Method
- **D-01: Access model** — Read-only viewer access granted via CS Lead. No API tokens, no scripted enumeration. Manual UI walk-through.
- **D-02: Scope** — Survey is bounded to the 3 KB source families CS Lead identified, plus any documents they link to:
  1. **Confluence** — SCE root-cause classification guides (and anything linked from them)
  2. **Google Sites Email Templates** — operational reply templates
  3. **Whimsical workflow diagram** — process knowledge (CEE workspace) — distinct from policy knowledge
- **D-03: Depth per source** — Metadata **+ content snapshot** (frozen copy committed to repo). Per-section Level-In tagging is part of the **coverage map** work later, not the snapshot step.
- **D-04: Snapshot format per source**
  - Confluence → **PDF** export (preserves structure + visuals)
  - Whimsical → **SVG** (vector + searchable text), fallback **PNG**
  - Google Sites Email Templates → **Markdown** (direct text input ready for Phase 3 ingest)
  - All committed under `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/`

### To Be Decided During Planning (user wants more info before locking)
These 3 areas were intentionally left open — `gsd-planner` will surface them with recommendations for user review, NOT auto-decide:

- **D-TBD-A: Coverage measurement method** — Three viable approaches:
  - *Evidence-based:* sample N historical Freshdesk tickets per Level-In category, map each to the KB source(s) the agent would use to answer it.
  - *KB-driven:* walk the surveyed KB top-down, tag each section with which Level-In category it serves. Workflow.svg already provides much of this structure.
  - *CS self-report:* ask CS agents which sources they rely on per category.
  - Recommend `gsd-planner` propose a **hybrid** (KB-driven from Workflow.svg structure, validated by a small evidence-based sample) and ask user.

- **D-TBD-B: Conflict detection method** — Three viable approaches:
  - *Manual reviewer:* read every snapshot, flag contradictions.
  - *LLM-assisted pairwise comparison:* feed pairs of policy claims to an LLM (Sonnet 4.6) to flag contradictions; reviewer triages.
  - *Cross-reference against real agent replies:* sample answered tickets from Freshdesk export, compare what agents actually said vs what the KB says.
  - **Risk to address regardless of method:** Workflow.svg embeds policy thresholds (1h cancellation window, 45d warranty, 40% promo, 20% discount cap) that may contradict Confluence/Email Templates. Conflict detection MUST check this cross-source axis explicitly.

- **D-TBD-C: Deliverable format + tacit-knowledge scope** — Open questions:
  - SURVEY.md alone, or SURVEY.md + structured CSV/Sheets the CS team can edit?
  - Glossary as a separate `GLOSSARY.md` or a section in SURVEY.md?
  - Tacit-knowledge interviews: light async questionnaire to a few seniors, structured interviews with N CS agents + ops lead, or skip in Phase 1?

### Claude's Discretion
- Directory structure under `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/` (sub-organize by source family)
- File-naming conventions for snapshots
- Markdown structure of the inventory artifact (templates can be adapted by planner)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before planning or implementing.**

### Project-Level (already locked)
- `.planning/PROJECT.md` — phase boundary (Phase 1 = email-answering only, no ops actions), two-MCP architecture decision, Knowledge readiness = pre-RAG survey gate
- `.planning/REQUIREMENTS.md` — KB-01 (source inventory + coverage), KB-02 (conflict inventory) map to this phase
- `.planning/ROADMAP.md` §"Phase 1" — 4 success criteria, dependencies (none — first phase)
- `CLAUDE.md` — full recommended stack, locked constraints

### User-Provided (this phase)
- `2026-05-28-meeting-note.md` — **PRIMARY context from CS Lead**: team size, volume by channel, Level-In distribution with %, agent workflow B1–B4, names the 3 KB sources
- `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/WorkFlow.svg` — **the Whimsical CS workflow diagram** (CEE workspace). Embeds operational policy thresholds, internal jargon, state codes. Survey must extract structured facts from this, not just snapshot it.

### External (to be enumerated during survey itself — placeholders)
- Whimsical workspace: `https://whimsical.com/cee-workspace/workflow-R2Fxikffas5bP6ZkyKbbfT` (source of WorkFlow.svg above)
- Google Sites Email Templates root: `https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/p/1gop1-Fy6OxafB3wzzrVy0MBwKqWECH0M/edit` — must be enumerated page-by-page and exported to Markdown
- Confluence SCE root-cause guides: specific space/page list TBD — CS Lead to grant access; survey enumerates from there

### Stack Decisions (from CLAUDE.md — relevant only as guard-rails, not used to build in Phase 1)
- Two separate MCPs (Selless transactional + Knowledge RAG) — NEVER merged
- Centralized RAG store with citations — Phase 3 consumer of this phase's output
- `pgvector` on Postgres + Voyage `voyage-3-large` — Phase 3, not Phase 1

</canonical_refs>

<code_context>
## Existing Code Insights

**No code exists yet.** Repo currently contains only planning artifacts (`.planning/`, `CLAUDE.md`, `Plan-discussion.md`, `2026-05-28-meeting-note.md`, and the WorkFlow.svg snapshot under the phase folder). Phase 1 produces documentation deliverables; no source code is created in this phase.

### Reusable Assets
- None (greenfield)

### Established Patterns
- `.planning/` directory layout is the GSD convention; Phase 1 outputs live under `.planning/phases/01-knowledge-survey-conflict-inventory/`.

### Integration Points
- Phase 3 (KB ingest) will consume the snapshots in `.../snapshots/` and the inventory/coverage/conflict reports as ingest input — Phase 1 artifacts must be in a format Phase 3 can read (Markdown for text, structured front-matter or sidecar JSON/CSV for metadata).

</code_context>

<specifics>
## Specific Ideas

### Facts captured from CS Lead meeting (`2026-05-28-meeting-note.md`)

**Team & volume:**
- 43 CS agents (38 actively answering tickets)
- ~3,000 tickets/day total (all channels)
- Channel split: **Email 30% · Contact Form 60% · Other 10%**
  - ⚠️ Email-only Phase-1 scope (per PROJECT.md) covers only ~900/day. Worth re-examining at project level — captured in Deferred Ideas.

**Freshdesk "Level-In" classification (with empirical %):**
| Level-In | % | Sub-categories |
|---|---|---|
| Complaint | 71% | Return 53 · Replace 27 · Review 12 · Refund (partial/full) ... |
| Change request | 16% | |
| Inquiry | 9.7% | Includes pre-purchase |
| Chargeback / claim | 3% | Gateway-initiated; policy updated frequently |
| Other | remainder | |

**Agent workflow (B1–B4):**
- **B1** Open ticket (pre-classified by Freshdesk); verify source classification
- **B2** Re-classify Level-In + find order — three branches: no order (template ask), 1 order (proceed), many orders (identify from message OR send 30-day list template)
- **B3** Validate order → classify customer-feedback expectation → tag by product line + feedback issue
- **B4** Reply using Email Templates; tag root-cause per SCE Confluence guide

### Facts extracted from `WorkFlow.svg` (Whimsical export)

**6 macro-flows present in the diagram:**
1. CANCELLATION REQUEST
2. CHANGE REQUEST
3. PRODUCT COMPLAINT
4. SHIPPING INQUIRY (with sub-sections: Types of inquiries, Test contract, DNR, OOS, RTS, Common scenarios)
5. EMAIL-CALL COLLAB (flow + Email-agent side + Call-agent side + Request to call team)
6. CEE-SCE COLLAB (flow + CEE side + SCE side + Request types)

**Policy thresholds embedded in the diagram (must be reconciled with Confluence/Email Templates during conflict detection):**
- Cancellation eligible: within **1 hour** of order placement
- Change eligible: within **1 hour** of order placement
- Warranty: within **45 days** of purchase date
- Aftersale promotion offered: **40% discount + free shipping**
- Discount cap: **up to 20%** (in some scenarios)
- Operational rule: **1 note per request only**

**Internal jargon (glossary needed — to be produced as a Phase 1 deliverable):**
- **CEE** — likely Customer Email Experience team (TBD confirm)
- **SCE** — likely Supply Chain / Solutions / Specialist Customer Experience (TBD confirm)
- **DO / PO** — Delivery Order / Purchase Order
- **TA / TO** — TBD
- **RTS** — Return to Sender (likely)
- **OOS** — Out of Stock
- **DNR** — TBD (Do Not Refund? Do Not Reship?)
- **Active / Disposed** — DO status states
- **Test contract / Clear-stock** — operational categories

**State / template codes referenced** (need mapping to actions/email-templates):
- A1–A9, B1–B7, D8/D9, E1–E12, F1–F20, G1–G13 — each code maps to a workflow node (and likely a specific email template in the Google Sites). **Code-to-template mapping is a required Phase 1 deliverable** — otherwise Phase 3 ingest cannot resolve cross-references between the workflow and the Email Templates.

### Newly-identified Phase 1 deliverables (not in original ROADMAP.md success criteria, but necessary)

Original ROADMAP.md Phase 1 success criteria expand to include:

- **(NEW) GLOSSARY.md** — internal jargon → plain-English definition, with source per term (workflow node ID, Confluence page, etc.)
- **(NEW) CODE-MAP.md or sidecar JSON** — workflow code (E1, F12, …) → described action → linked email template (if exists)
- **(NEW) Policy-Threshold Index** — every embedded numeric/temporal threshold (1h cancel, 45d warranty, 20% cap, 40% promo, …) listed with source, so conflict detection can run cross-source

### User intent (clarified at end of discussion)
> "Tôi chưa hiểu discussion phase này lắm, tôi muốn cung cấp all thông tin để chuẩn bị làm knowledge base cho Agents Team phục vụ project này"

**Implication for planner:** The user's mental model treats Phase 1 = "give Claude everything I have so the KB is ready." Planner should structure tasks so any additional context the user drops (more meeting notes, more exports, screenshots) folds in cleanly. The artifact format should be append-friendly and section-keyed, not a single linear document the user has to re-edit.

</specifics>

<deferred>
## Deferred Ideas

### Project-level scope re-check (NOT Phase 1)
- **Channel scope vs volume:** PROJECT.md scopes Phase 1 = email, but the meeting note shows Email = 30% / Contact Form = 60% of inbound. Email-only covers only ~900/day; Contact Form is the larger channel. Worth a project-level decision: do we restrict to email as planned, OR widen Phase-1 product scope to "tickets in Freshdesk regardless of inbound channel" (since Contact Form is already two-way-synced into Freshdesk per PROJECT.md context)? **Capture as a flag for `/gsd:complete-milestone` review, not a Phase 1 task.**

### Phase 3 inputs
- The decision on how to map state codes → email templates may need a richer schema than a flat key/value (e.g., one code maps to N templates by sub-condition). Defer detailed schema to Phase 3 ingest planning; Phase 1 captures raw mapping.

### v2 / Future
- Whimsical's "EMAIL-CALL COLLAB" and "CEE-SCE COLLAB" sections describe inter-team coordination knowledge. For Phase 1 (email reply automation) we treat them as *context* knowledge — the AI is not in those collab loops yet. May become relevant if/when call-channel automation is scoped (PROJECT.md "Out of Scope: Call/voice support").

</deferred>

---

*Phase: 1-knowledge-survey-conflict-inventory*
*Context gathered: 2026-05-29*
