---
phase: 01-knowledge-survey-conflict-inventory
plan: "01"
subsystem: knowledge-survey
tags: [survey, glossary, code-map, policy-thresholds, workflow]
dependency_graph:
  requires: []
  provides:
    - SURVEY.md master skeleton (section-keyed, append-friendly)
    - GLOSSARY.md internal jargon reference
    - CODE-MAP.md workflow code to action mapping
    - POLICY-THRESHOLD-INDEX.md numeric/temporal threshold index
  affects:
    - Plan 02 (Email Templates survey — appends to SURVEY.md, wires Linked email template column in CODE-MAP.md)
    - Plan 03 (Confluence survey — appends to SURVEY.md, confirms TBD glossary terms)
    - Plan 04 (conflict detection — populates Conflict Findings in SURVEY.md, fills Cross-source status in POLICY-THRESHOLD-INDEX.md)
tech_stack:
  added: []
  patterns:
    - section-keyed append-friendly Markdown survey pattern
    - policy threshold index with cross-source status column
    - workflow code map with TBD-Plan-02 template wiring stub
key_files:
  created:
    - .planning/phases/01-knowledge-survey-conflict-inventory/SURVEY.md
    - .planning/phases/01-knowledge-survey-conflict-inventory/GLOSSARY.md
    - .planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md
    - .planning/phases/01-knowledge-survey-conflict-inventory/POLICY-THRESHOLD-INDEX.md
  modified: []
decisions:
  - "B4 flagged as referenced-without-node (no dedicated workflow node found in SVG or template files)"
  - "B8-B13 discovered as 365-day guarantee variants in template files — not listed in PLAN.md code range; added to CODE-MAP and flagged for Plan 02/03 verification"
  - "C2 (replacement-still-not-fit) discovered in template file — not in PLAN.md C-code range; added to CODE-MAP"
  - "Two internal warranty threshold conflict flags pre-staged: IC-01 (45-day purchase-date vs 14-day delivery-date) and IC-02 (20% cap vs 50% discount scope)"
  - "D6 70% refund threshold discovered in flow but not in PLAN.md threshold list — flagged in CODE-MAP coverage note for Plan 04"
metrics:
  duration_seconds: 302
  completed_date: "2026-05-29"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 0
---

# Phase 1 Plan 01: WorkFlow.svg Survey — SUMMARY

**One-liner:** Whimsical WorkFlow.svg fully extracted into four append-friendly deliverables: section-keyed SURVEY skeleton, 25-term GLOSSARY (15 acronyms + 10 DO status states), 80+ code CODE-MAP across 7 families (A–G), and 18-threshold POLICY-THRESHOLD-INDEX with two pre-staged internal conflict flags.

---

## What Was Built

Four documentation deliverables created from `snapshots/WorkFlow.svg` and the snapshot template files:

| Artifact | Path | Content |
|----------|------|---------|
| SURVEY.md | `.planning/phases/01-knowledge-survey-conflict-inventory/SURVEY.md` | Master section-keyed skeleton with Source Inventory (3 rows: SRC-01 confirmed, SRC-02/SRC-03 placeholders), Coverage Map backbone (5 Level-In categories × 6 macro-flows), Conflict Findings placeholder, Linked Deliverables |
| GLOSSARY.md | `.planning/phases/01-knowledge-survey-conflict-inventory/GLOSSARY.md` | 15 acronym rows (CEE, SCE, DO, PO, TA, TO, WOC, WNF, RTS, OOS, DNR, TC, OB, MOQ, FFM) + 10 DO status state rows; each with Source and Confirmed/TBD confidence |
| CODE-MAP.md | `.planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP.md` | A1–A9, B1–B13, C1–C2, D1–D9, E1–E13, F1–F22, G1–G13 — 80+ rows across 7 code families; each with Macro-flow, Described action, Linked email template (TBD–Plan 02), Notes |
| POLICY-THRESHOLD-INDEX.md | `.planning/phases/01-knowledge-survey-conflict-inventory/POLICY-THRESHOLD-INDEX.md` | 18 thresholds (THR-01 through THR-18) covering 1-hour windows, 45-day/14-day warranty, 40% promo, 20%/50%/70% refund caps, shipping day thresholds (21d/35d/15d/40d/2d), operational rules; 2 pre-staged internal conflict flags |

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create SURVEY.md master skeleton | f6557de | SURVEY.md |
| 2 | Build GLOSSARY.md and POLICY-THRESHOLD-INDEX.md | ebcfe8a | GLOSSARY.md, POLICY-THRESHOLD-INDEX.md |
| 3 | Build CODE-MAP.md for all workflow codes | 00eb824 | CODE-MAP.md |

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

### Discoveries Added (Rule 2: missing critical content)

**1. [Rule 2 - Missing Critical Content] B8–B13 (365-day guarantee variants) added to CODE-MAP**
- **Found during:** Task 3
- **Issue:** Template files contained B8, B9, B10, B11, B12, B13 (all labeled "365 GRT" — 365-day guarantee variants). PLAN.md listed the code range as B1–B3, B5–B7, B9–B11 only.
- **Fix:** Added all discovered codes to CODE-MAP.md with notes flagging them for Plan 02/03 verification. B4 confirmed as referenced-without-node.
- **Files modified:** CODE-MAP.md

**2. [Rule 2 - Missing Critical Content] C2 (replacement-still-not-fit) added to CODE-MAP**
- **Found during:** Task 3
- **Issue:** `product complaint-replacement not fit-template.md` contains C2 template. PLAN.md listed only C1 in the C-code range.
- **Fix:** Added C2 row to CODE-MAP.md with note flagging for Plan 02/03 verification.
- **Files modified:** CODE-MAP.md

**3. [Rule 2 - Missing Critical Content] D6 70% refund threshold flagged**
- **Found during:** Task 3
- **Issue:** WorkFlow.svg references "agrees to 70% refund?" and "confirmation (D2, D6, D4)" — a 70% refund threshold not captured in POLICY-THRESHOLD-INDEX.md or PLAN.md threshold list.
- **Fix:** Documented in CODE-MAP.md Coverage Note for Plan 04 to capture as an additional threshold.
- **Files modified:** CODE-MAP.md (coverage note)

---

## Known Stubs

| Stub | File | Location | Reason |
|------|------|----------|--------|
| "Linked email template" column = "TBD — Plan 02" for F-codes, G-codes, and some D-codes | CODE-MAP.md | All F1–F22, G1–G13 rows (except G10), D1–D9 rows | Plan 02 owns email template wiring; this column is intentionally deferred. |
| SRC-02 snapshot path = placeholder | SURVEY.md | Source Inventory table | Plan 02 fills this after Google Sites enumeration. |
| SRC-03 snapshot path = placeholder | SURVEY.md | Source Inventory table | Plan 03 fills this after Confluence access is granted. |
| "## Conflict Findings" section empty | SURVEY.md | Conflict Findings | Plan 04 populates after LLM-assisted pairwise detection. |
| Cross-source status = "Whimsical only" for all 18 thresholds | POLICY-THRESHOLD-INDEX.md | All rows | Plan 04 fills Confluence and Email Template columns. |

These stubs are all intentional and documented — they are the staged inputs for Plans 02, 03, and 04.

---

## Threat Flags

No new security-relevant surface introduced. This plan creates documentation artifacts only; no customer PII is present in any deliverable. All content is sourced from the internal workflow diagram (already in-repo) and internal template files.

---

## Self-Check

Checking that all claimed files exist and commits are present:

| Item | Status |
|------|--------|
| SURVEY.md | FOUND |
| GLOSSARY.md | FOUND |
| CODE-MAP.md | FOUND |
| POLICY-THRESHOLD-INDEX.md | FOUND |
| 01-01-SUMMARY.md | FOUND |
| Commit f6557de (Task 1) | FOUND |
| Commit ebcfe8a (Task 2) | FOUND |
| Commit 00eb824 (Task 3) | FOUND |

## Self-Check: PASSED
