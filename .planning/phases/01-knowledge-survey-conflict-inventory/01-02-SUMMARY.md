---
phase: "01-knowledge-survey-conflict-inventory"
plan: "02"
subsystem: "knowledge-survey"
status: "partial — checkpoint reached; awaiting cancellation template exports"
tags: ["email-templates", "code-wiring", "knowledge-survey", "gap-analysis"]
dependency_graph:
  requires: ["01-01"]
  provides: ["SURVEY-email-templates.md", "CODE-MAP-templates.md"]
  affects: ["01-03", "01-04"]
tech_stack:
  added: []
  patterns: ["template-inventory", "code-to-template-wiring", "product-line-fan-out"]
key_files:
  created:
    - ".planning/phases/01-knowledge-survey-conflict-inventory/SURVEY-email-templates.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/CODE-MAP-templates.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/change request-template1.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/change request-template3.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/change request-template4.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/change request-template5.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/change-request-template2.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/shipping queries & complaints-template1.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/shipping queries & complaints-template2.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/shipping queries & complaints-template3.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/shipping queries & complaints-template4.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/shipping queries & complaints-template5.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template1.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template2.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template3.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template4.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template5.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template6.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template7.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template8.md (empty)"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template9.md (empty)"
  modified: []
decisions:
  - "G14 and G15 discovered as new DNR codes beyond original G1-G13 CODE-MAP.md range — added to CODE-MAP-templates.md and flagged for CODE-MAP.md update in Plan 04"
  - "templates.md (previously committed DNR index) is superseded by dedicated shipping template files — not recommitted; cross-reference updated in SURVEY-email-templates.md"
  - "9 cancellation request template placeholder files found empty (0 bytes) — all F-codes (F1-F22) are a confirmed gap requiring CS Lead export"
  - "4 new discount/refund thresholds discovered in templates not in POLICY-THRESHOLD-INDEX: D8 70% refund, G5 50% discount, G7 10% refund, G12 30% discount"
metrics:
  duration: "4m 41s"
  completed_date: "2026-05-29"
  tasks_completed: 1
  tasks_total: 3
  files_created: 21
  files_modified: 0
---

# Phase 01 Plan 02: Email Templates Survey & Code Wiring Summary

## One-liner

Autonomous survey of 15 non-empty Google Sites email template snapshots producing SURVEY-email-templates.md inventory and CODE-MAP-templates.md wiring for all A/B/C/D/E/G workflow codes; F-code (cancellation) templates confirmed empty — checkpoint reached.

## What Was Built

### Task 1: Inventory and wire the Email Templates already in the repo (COMPLETE)

**SURVEY-email-templates.md** — Full inventory of 24 template files (15 snapshotted with content, 9 cancellation request placeholders empty). Includes:
- Template page / file, format (Markdown), snapshot path, covered codes, status, notes
- Template page count summary by category
- Placeholder/missing template note (templates.md superseded)
- Gap list (B4, all F-codes, G14/G15 new codes)
- Newly discovered codes table
- Checkpoint status and human-action requirements
- SURVEY.md reconciliation note (SRC-02 status for Plan 04)

**CODE-MAP-templates.md** — Wiring of all wirable codes to verbatim template headings:
- A1–A9 (14 template variants, product-line fan-out for A1/A6/A7)
- B1–B3, B5–B13 (16 variants; B4 gap confirmed; B8–B13 = 365-day guarantee variants)
- C1, C2 (out-of-guarantee and replacement-not-fit)
- D1–D9 (11 variants including D6 dual sub-variant)
- E1–E13 (all 13 E-codes wired across 5 change-request template files)
- F1–F22 (all 22 F-codes listed as EMPTY — no template content available)
- G1–G15 (G3 split to G3.1/G3.2; G8 has 3 product-line variants; G14/G15 newly discovered)
- Product-line fan-out summary table
- Conflict flags table (4 new threshold discoveries)
- Codes-without-a-template gap list

**Snapshot files added (5 change request + 5 shipping + 9 cancellation placeholders):**
All change request and shipping template files are fully content-bearing. All 9 cancellation request template files are 0 bytes (placeholders only).

---

## Checkpoint Status

**Stopped at:** Task 2 (checkpoint:human-verify — F-codes require cancellation template export)

**Tasks 1/3 complete. Task 2 requires human action. Task 3 is the post-checkpoint continuation.**

---

## Deviations from Plan

### Auto-fixed: Discovered more cancellation template files than expected

**Rule 2 — Auto-add missing inventory items**
- **Found during:** Task 1 staging
- **Issue:** Plan referenced 5 cancellation request template files; git status revealed 9 empty files (template1.md through template9.md).
- **Fix:** Updated SURVEY-email-templates.md to inventory all 9 empty files (rows 16–24).
- **Files modified:** SURVEY-email-templates.md

### Discovery: G14 and G15 are new codes beyond the original G1–G13 range

**Rule 2 — Auto-add missing critical functionality (accuracy)**
- **Found during:** Task 1 template reading
- **Issue:** CODE-MAP.md (Plan 01) documents G1–G13. The shipping DNR template file contains G14 and G15 as distinct codes (DNR-Replacement and DNR-Replacement-or-Full-Refund).
- **Fix:** Added G14 and G15 rows to CODE-MAP-templates.md with verbatim headings; flagged CODE-MAP.md for update in Plan 04.
- **Files modified:** CODE-MAP-templates.md, SURVEY-email-templates.md

### Discovery: templates.md superseded by dedicated shipping files

**Found during:** Reading snapshots directory.
- **Issue:** CODE-MAP.md (Plan 01) cross-references `snapshots/templates.md` for G10/G11/G14/G15. This file was in the previous commit but is deleted in the working tree. Its content is entirely present in `shipping queries & complaints-template1.md` and `shipping queries & complaints-template3.md`.
- **Fix:** SURVEY-email-templates.md records this in the "Placeholder / Missing Template Note" section. CODE-MAP-templates.md cites the correct shipping template files. Did not recommit `templates.md` deletion (not our change to make).
- **Tracked:** Noted for Plan 04 to update CODE-MAP.md cross-references.

### Discovery: 4 new threshold values not in POLICY-THRESHOLD-INDEX.md

**Rule 2 — Missing completeness (policy threshold coverage)**
- **Found during:** Task 1 template wiring
- **Issue:** Four discount/refund amounts appear in templates but were not captured in POLICY-THRESHOLD-INDEX.md from Plan 01:
  - D8: 70% refund (customer refusal scenario)
  - G5: 50% discount (angry customer appeasement)
  - G7: 10% refund option (late delivery choice 2)
  - G12: 30% discount (test contract cancellation)
- **Fix:** Flagged as IC-NEW-01 through IC-NEW-04 in CODE-MAP-templates.md conflict flags table. Will be added to POLICY-THRESHOLD-INDEX.md in Plan 04.
- **Files modified:** CODE-MAP-templates.md (conflict flags section)

---

## Known Stubs

None — no template text was invented. All stubs/placeholders in CODE-MAP-templates.md are explicit "EMPTY FILE" annotations for F-codes, not fabricated content.

---

## Threat Flags

No new security-relevant surface introduced. Template files contain only reusable boilerplate with placeholder tokens (`{{ticket.group.name}}`, `[shipping address]`, etc.). No real customer PII found in any snapshot file.

---

## Codes Survey Summary

| Code Family | Total Codes | Wired to Template | Gap (no template) |
|-------------|-------------|-------------------|-------------------|
| A-codes | 9 | 9 (A1–A9) | 0 |
| B-codes | 13 | 12 (B1–B3, B5–B13) | 1 (B4 — possibly retired) |
| C-codes | 2 | 2 (C1, C2) | 0 |
| D-codes | 9 | 9 (D1–D9) | 0 |
| E-codes | 13 | 13 (E1–E13) | 0 |
| F-codes | 22 | 0 | **22 (all empty — awaiting export)** |
| G-codes | 15 (G1–G15) | 15 (G1–G15 incl. G3.1/G3.2, G14, G15) | 0 |
| **Total** | **83** | **60** | **23** |

---

## Human Action Required (Checkpoint)

The following actions are needed to complete Task 2 and enable Task 3:

1. **Export cancellation request templates** — Fill all 9 empty `cancellation request-template*.md` files in `snapshots/` with the corresponding Google Sites page content (Markdown export per D-04). These cover F-codes (F1–F22).

2. **Confirm the complete Google Sites page list** — Verify that the 24 template files currently in `snapshots/` represent the complete set of pages on the Email Templates site. If any pages are missing (not even as empty placeholders), add them.

3. **Grant read-only viewer access** — Provide access to https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/p/1gop1-Fy6OxafB3wzzrVy0MBwKqWECH0M/edit for full enumeration.

4. **Reply signal** — Type "templates provided" (and list added files) OR "no more templates available" (if the repo set is already complete as-is).

---

## Self-Check

**Files exist:**
- SURVEY-email-templates.md: FOUND
- CODE-MAP-templates.md: FOUND

**Commit exists:**
- 83bbdb2: FOUND (21 files changed, 1352 insertions)

## Self-Check: PASSED
