---
phase: 01-knowledge-survey-conflict-inventory
document: SURVEY.md
role: master-survey-skeleton
status: seeded-by-plan-01
last_updated: "2026-05-29"
---

# Knowledge Survey — Master Document

> **How to use this document:**  
> This is the section-keyed master survey artifact. Later plans (02, 03, 04) append to each
> section without restructuring. Do NOT rename headings. Do NOT paste raw source markup here —
> reference snapshot paths only.

---

## Traceability

| Section | ROADMAP Phase 1 Success Criterion |
|---------|-----------------------------------|
| Source Inventory | Criterion 1 — Complete inventory of all KB sources with metadata |
| Coverage Map | Criterion 2 — Coverage map linking KB sources to ticket types |
| Conflict Findings | Criterion 3 — Conflict inventory (policy contradictions, stale content) |
| Action Items (forward-ref) | Criterion 4 — CS-team-owned action items for gaps surfaced |

---

## Source Inventory

> **Scope:** Every knowledge-base source used by CS agents to answer customer emails.
> Append new rows as each source is surveyed (Plans 02, 03).
> Do NOT duplicate content — reference the snapshot path.

| Source ID | Source Family | Format | Snapshot Path | Last-Update Cadence | Owner / Access | Notes |
|-----------|---------------|--------|---------------|---------------------|----------------|-------|
| SRC-01 | Whimsical workflow diagram (CEE workspace) | SVG | snapshots/WorkFlow.svg | TBD — confirm with CS Lead (living diagram, no versioning metadata observed) | CEE workspace via CS Lead | Primary process-knowledge backbone. Contains 6 macro-flows, state/template codes A–G, policy thresholds, and internal jargon. Surveyed in Plan 01. |
| SRC-02 | Google Sites Email Templates | Markdown (exported) | snapshots/ *(Plan 02 fills this)* | TBD — confirm with CS Lead | CS Lead / Google Sites | Operational reply templates linked from WorkFlow.svg. Enumerated page-by-page in Plan 02. URL: https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/ |
| SRC-03 | Confluence SCE Root-Cause Classification Guides | PDF (exported) | snapshots/ *(Plan 03 fills this)* | TBD — confirm with CS Lead | CS Lead / Confluence SCE space | Root-cause tagging guides used in step B4. Access requires CS Lead to grant viewer rights. Surveyed in Plan 03. |

---

## Coverage Map (backbone)

> **Method (D-05):** Walk the KB top-down using WorkFlow.svg as the structural backbone, tag
> each source section to the Freshdesk Level-In category it serves. Evidence-sample validation
> per category is completed in Plan 04.  
> **Note:** Per-section tagging and evidence-sample validation are completed in Plan 04;
> this section is the top-down backbone only.

### Freshdesk Level-In Distribution (from 2026-05-28 meeting note)

| Level-In Category | % of Volume | Sub-categories |
|-------------------|-------------|----------------|
| Complaint | 71% | Return 53% · Replace 27% · Review 12% · Refund (partial/full) |
| Change Request | 16% | Address · Size · Color/design · Billing · Add items · Contact details |
| Inquiry | 9.7% | Includes pre-purchase inquiries |
| Chargeback / Claim | 3% | Gateway-initiated; policy updated frequently |
| Other | ~0.3% | Miscellaneous |

### Macro-Flow to Level-In Mapping

| # | WorkFlow Macro-Flow | Level-In Category Served | Notes |
|---|---------------------|--------------------------|-------|
| 1 | CANCELLATION REQUEST | Complaint / Change Request | Covers cancellation within 1-hour window; links to CEE-SCE COLLAB for DO management |
| 2 | CHANGE REQUEST | Change Request (16%) | Address, size, color, billing, add items, contact detail changes within 1-hour window |
| 3 | PRODUCT COMPLAINT | Complaint (71%) | Within-warranty (A, B, D codes) and out-of-warranty (C1) paths; Return/Replace/Refund sub-flows |
| 4 | SHIPPING INQUIRY | Inquiry (9.7%) + Complaint (subset) | Sub-sections: Types of inquiries, Test contract, DNR, OOS, RTS, Common scenarios (G codes) |
| 5 | EMAIL-CALL COLLAB | Cross-cutting (any category needing OB call) | Inter-team coordination; not a customer-facing category but affects how tickets are handled |
| 6 | CEE-SCE COLLAB | Cross-cutting (DO/PO operations, SCE requests) | SCE collaboration for product status checks, postpone, express TA, etc. Not customer-facing category |

> **Coverage gap flags (to be validated in Plan 04):**
> - Chargeback/Claim (3%) — no dedicated macro-flow observed in WorkFlow.svg. May be handled via ad-hoc policy or Confluence-only guidance.
> - Pre-purchase Inquiry sub-set of Inquiry (9.7%) — not explicitly represented as a distinct flow.

---

## Conflict Findings

> **Status:** PLACEHOLDER — Plan 04 (LLM-assisted pairwise conflict detection) populates this section.
>
> Plan 04 will run cross-source threshold comparison (WorkFlow.svg ↔ Confluence ↔ Email Templates)
> and populate findings here. See POLICY-THRESHOLD-INDEX.md for the threshold axis.

*(No entries yet — seeded by Plan 01, populated by Plan 04)*

---

## Linked Deliverables

### Plan 01 outputs (this plan — WorkFlow.svg survey)

| Deliverable | Path | Description |
|-------------|------|-------------|
| GLOSSARY.md | `.planning/phases/01-knowledge-survey-conflict-inventory/GLOSSARY.md` | Internal jargon → plain-English with source per term |
| CODE-MAP.md | `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` | Workflow state/template code → described action |
| POLICY-THRESHOLD-INDEX.md | `.planning/phases/01-knowledge-survey-conflict-inventory/POLICY-THRESHOLD-INDEX.md` | Every numeric/temporal threshold with source |

### Forward references (Plans 02–04)

| Deliverable | Plan | Description |
|-------------|------|-------------|
| COVERAGE-MAP.csv | Plan 04 | Editable CSV/Sheet mapping KB sections to Level-In categories (CS team can edit) |
| CONFLICT-INVENTORY.md | Plan 04 | Enumerated policy conflicts flagged by LLM-assisted pairwise detection |
| ACTION-ITEMS.md | Plan 04 | CS-team-owned action items for knowledge gaps surfaced |
