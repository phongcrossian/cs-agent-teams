# Phase 1: Knowledge Survey & Conflict Inventory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 1-knowledge-survey-conflict-inventory
**Areas discussed:** Survey input method
**Areas deferred to plan-phase:** Coverage measurement, Conflict detection, Deliverable format + tacit-knowledge scope
**Language:** Vietnamese (user requested mid-session)

---

## Survey input method

### Q1: Access reality

| Option | Description | Selected |
|--------|-------------|----------|
| Full direct access | Engineer has Confluence + Google Drive API tokens; can script enumeration | |
| Read-only via CS lead | CS lead grants viewer access to spaces/folders; browse manually | ✓ |
| Indirect via exports/handoff | CS lead exports dump (PDFs/.docx/sheet copies); never touch live systems | |
| Unknown — need to find out | Survey plan should clarify access first | |

**User's choice:** Read-only via CS lead
**Notes:** Implies manual UI walk-through, no scripted enumeration.

---

### Q2: Enumeration breadth

| Option | Description | Selected |
|--------|-------------|----------|
| Every page/sheet listed | Inventory every page even ones suspected dead | |
| Top-down by space/folder | List spaces + major pages, drill in when coverage gap forces | |
| Ticket-type-driven sampling | Start from ticket types, follow links from KB sources actually used | |

**User's response:** *Free-text:* "Tôi đã tổng hợp nội dung meeting discussion với CS Lead rồi trong file 2026-05-28-meeting-note.md — đọc và làm việc tiếp với tôi"

**Notes:** User pivoted from the abstract question to providing concrete context. Reading `2026-05-28-meeting-note.md` revealed CS Lead had **already named** the 3 KB source families (Confluence SCE root-cause guides, Google Sites Email Templates, Whimsical CEE workspace workflow). This **resolved the breadth question by replacement**: scope = those 3 sources + anything they link to. Q2 was effectively answered by the meeting note, not by selecting an option.

Important facts pulled from the meeting note (now in CONTEXT.md `<specifics>`):
- Volume: ~3,000 tickets/day total. Channel split: Email 30% / Contact Form 60% / Other 10%.
- Level-In distribution quantified (Complaint 71%, Change request 16%, Inquiry 9.7%, Chargeback 3%).
- Agent workflow B1–B4 documented.

---

### Q3: Depth per source

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata only | Title, URL, owner, last-updated, ticket-types served, format | |
| Metadata + content snapshot | Above + frozen copy (markdown / export / screenshot) | ✓ |
| Metadata + snapshot + per-section Level-In tagging | Above + tagging by Return/Replace/Refund/etc. | |

**User's choice:** Metadata + content snapshot
**Notes:** Per-section Level-In tagging deferred to the coverage-map step (likely Phase 1 later task or Phase 3), not done during input capture.

**Mid-question language switch:** First answer to Q3 was "trao đổi với tôi bằng tiếng việt" — re-asked Q3 in Vietnamese.

---

### Q4: Snapshot method

| Option | Description | Selected |
|--------|-------------|----------|
| Manual export → commit to repo | UI export per source (PDF/Word/PNG/PDF), committed to .planning/phases/01-.../snapshots/ | |
| Copy-paste to Markdown | Reviewer copies content to .md files; loses formatting/images | |
| Mixed (PDF/PNG for refs + Markdown for content) | Confluence/Whimsical → PDF/PNG (preserve visuals); Email Templates → Markdown (text input for Phase 3 ingest) | ✓ |
| CS Lead exports + handoff | CS Lead provides the dump; we don't touch source systems | |

**User's choice:** Mixed (PDF/PNG for refs + Markdown for content)

**Follow-up clarification:** "whimsical tôi chỉ copy được image PNG or SVG thôi" → upgraded Whimsical format from generic PNG to **SVG preferred (vector + searchable text), fallback PNG**. Confluence stays PDF. Email Templates stays Markdown.

---

### Next-steps question (post-Q4)

| Option | Description | Selected |
|--------|-------------|----------|
| Write CONTEXT.md and stop here | Commit decisions, move to /gsd:plan-phase 1 | |
| Discuss: Coverage measurement | | |
| Discuss: Conflict detection | | |
| Discuss: Deliverable + tacit knowledge | | |

**User's response:** *Free-text:* "Tôi export rồi vào làm việc tiếp" — paused to export WorkFlow.svg before continuing. Checkpoint written.

---

### Resume after export (`/gsd-discuss-phase 1` with WorkFlow.svg)

User returned with `WorkFlow.svg` placed at `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/WorkFlow.svg` (~819KB). Reading the SVG revealed substantial new structure:

- 6 macro-flows (Cancellation, Change request, Product complaint, Shipping inquiry, Email-Call collab, CEE-SCE collab)
- Embedded policy thresholds (1h cancel, 45d warranty, 40% promo, 20% discount cap)
- Internal jargon (CEE / SCE / DO / PO / TA / TO / RTS / OOS / DNR / Active / Disposed)
- State/template codes (A1–A9, B1–B7, D8/D9, E1–E12, F1–F20, G1–G13) referenced throughout

This led to identifying **3 new Phase 1 deliverables** beyond ROADMAP.md's original success criteria:
- GLOSSARY.md
- CODE-MAP (state code → action → linked email template)
- Policy-Threshold Index

---

### Final question: continue discussing remaining 3 areas, or write CONTEXT.md now?

| Option | Description | Selected |
|--------|-------------|----------|
| Coverage measurement method | Evidence-based / KB-driven / CS self-report | |
| Conflict detection method | Manual / LLM pairwise / cross-ref real agent replies | |
| Deliverable + tacit knowledge | Artifact format + CS interview scope | |
| Write CONTEXT.md, skip 3 areas | Planner will surface them with recommendations | ✓ |

**User's response (free-text):** "Viết CONTEXT.md với những gì đã chốt, bỏ qua 3 mục còn lại, Tôi chưa hiểu discussion phase này lắm, tôi muốn cung cấp all thông tin để chuẩn bị làm knowledge base cho Agents Team phục vụ project này"

**Notes:** User's mental model = "give Claude everything I have so the KB is ready." Captured as guidance in CONTEXT.md `<specifics>`: planner should structure tasks so additional dropped context (meeting notes, screenshots, more exports) folds in cleanly — append-friendly, section-keyed deliverable, not a single linear doc the user has to re-edit.

The 3 unresolved areas are flagged in CONTEXT.md as **D-TBD-A/B/C** for `gsd-planner` to surface with options + recommendations, **not** to auto-decide.

---

## Claude's Discretion
- Sub-directory organization under `.../snapshots/` (group by source family)
- File-naming conventions for snapshots
- Markdown structure of inventory artifacts (planner may adapt)

## Deferred Ideas
- **Channel-scope re-check (project-level, not Phase 1):** PROJECT.md scopes Phase 1 = email but Email is only 30% of inbound; Contact Form is 60% and is already synced into Freshdesk per PROJECT.md. Flagged for `/gsd:complete-milestone` review.
- **Workflow.svg collab sections (Email-Call, CEE-SCE):** treated as context-only for Phase-1 email automation; relevant if/when call-channel scope is added.
- **State-code-to-template schema:** flat key/value may be insufficient; defer richer schema to Phase 3 ingest planning.
