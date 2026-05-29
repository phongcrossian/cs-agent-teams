---
phase: "01-knowledge-survey-conflict-inventory"
plan: "02"
subsystem: "knowledge-survey"
status: "complete"
tags: ["email-templates", "code-wiring", "knowledge-survey", "gap-analysis"]
dependency_graph:
  requires: ["01-01"]
  provides: ["SURVEY-email-templates.md", "CODE-MAP-templates.md"]
  affects: ["01-03", "01-04"]
tech_stack:
  added: []
  patterns: ["template-inventory", "code-to-template-wiring", "product-line-fan-out", "do-status-branching"]
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
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template1.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template2.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template3.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template4.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template5.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template6.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template7.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template8.md"
    - ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/cancellation request-template9.md"
  modified: []
decisions:
  - "F23 (Aftersale promotion) discovered as new cancellation code beyond CODE-MAP.md's F1-F22 range — added to CODE-MAP-templates.md, flagged for CODE-MAP.md update in Plan 04"
  - "F-codes are organized by DO status (New/Processing/Pending = can cancel; TA = need SCE; TO = cannot cancel) crossed with cancellation reason — not by sequential branch as CODE-MAP.md implied"
  - "G14 and G15 confirmed as new DNR codes beyond original G1-G13 range — CODE-MAP.md update deferred to Plan 04"
  - "templates.md (previously committed DNR index) is superseded by dedicated shipping template files — cross-reference updated in SURVEY-email-templates.md"
  - "8 new policy thresholds/discrepancies discovered in email templates not in POLICY-THRESHOLD-INDEX: D8 70% refund, G5 50% discount, G7 10% refund, G12 30% discount, plus F-code 20% cap / F8 40% goodwill / 1h+45d restatements"
metrics:
  duration: "checkpoint-spanning (Task 1 ~5m + Task 2 post-checkpoint fold-in)"
  completed_date: "2026-05-29"
  tasks_completed: 3
  tasks_total: 3
  files_created: 21
  files_modified: 0
---

# Phase 01 Plan 02: Email Templates Survey & Code Wiring Summary

## One-liner

Full survey of all 24 Google Sites email template files (Product Complaint, Change Request, Shipping, Cancellation) producing SURVEY-email-templates.md inventory and CODE-MAP-templates.md wiring of 83 workflow codes (A1-A9, B1-B13, C1-C2, D1-D9, E1-E13, F1-F23, G1-G15) to verbatim template headings with product-line fan-out and DO-status branching.

## What Was Built

### Task 1: Inventory and wire the Email Templates already in the repo (COMPLETE)

**SURVEY-email-templates.md** — Inventory of all 24 template files with format, snapshot path, covered codes, status, gap list, newly-discovered codes table, and SURVEY.md reconciliation note.

**CODE-MAP-templates.md** — Wiring of all wirable codes to verbatim template headings (A/B/C/D/E/G), product-line fan-out summary, conflict flags table.

15 content-bearing template files surveyed autonomously (A1-A9, B1-B13, C1-C2, D1-D9, E1-E13, G1-G15).

### Task 2: Fold in newly-provided cancellation templates and finalize (COMPLETE — post-checkpoint)

After the checkpoint was resolved ("templates provided"), all 9 cancellation request template files were read and wired:

- **F1-F23 wired** to verbatim headings across 9 files, organized by DO status:
  - New/Processing/Pending (can cancel): F1-F4, F7, F9, F10, F14, F15, F16, F21, F23
  - TA DO(s) (need SCE, in-transit): F5, F17, F18
  - TO DO(s) (cannot cancel): F6, F8, F11, F19, F20
  - Next responses (confirmation/resume): F12, F13, F22
- **F23 (Aftersale promotion)** discovered as a new code beyond CODE-MAP.md's F1-F22 range.
- Inventory updated from 15/20 to 24/24 files snapshotted; F-code gap (Gap Category 1) closed.
- SRC-02 marked surveyed (complete-as-available) in the reconciliation note.

---

## Deviations from Plan

### Auto-fixed: 9 cancellation template files (plan referenced 5)

**Rule 2 — Auto-add missing inventory items**
- **Found during:** Task 1 staging
- **Issue:** Plan referenced 5 cancellation request files; the repo contained 9.
- **Fix:** Inventoried all 9 (rows 16-24); wired all F-codes across them in Task 2.

### Discovery: F23, G14, G15 are new codes beyond CODE-MAP.md ranges

**Rule 2 — Accuracy completeness**
- **Found during:** Task 1 (G14/G15) and Task 2 (F23) template reading
- **Issue:** CODE-MAP.md (Plan 01) documents F1-F22 and G1-G13. Templates contain F23 (Aftersale promotion), G14 and G15 (DNR replacement codes).
- **Fix:** Added all three to CODE-MAP-templates.md with verbatim headings; flagged CODE-MAP.md for update in Plan 04.

### Discovery: templates.md superseded by dedicated shipping files

- **Issue:** CODE-MAP.md references `snapshots/templates.md` for G10/G11/G14/G15; that file's content is now in the dedicated `shipping queries & complaints-template*.md` files.
- **Fix:** Recorded in SURVEY-email-templates.md "Placeholder / Missing Template Note"; CODE-MAP-templates.md cites the correct files. Tracked for Plan 04 CODE-MAP.md update.

### Discovery: 8 threshold values/discrepancies not in POLICY-THRESHOLD-INDEX.md

**Rule 2 — Policy threshold coverage**
- **Found during:** Task 1 and Task 2 wiring
- **Issue:** Discount/refund amounts and window restatements appear in templates but were not captured in POLICY-THRESHOLD-INDEX.md:
  - D8: 70% refund | G5: 50% discount | G7: 10% refund option | G12: 30% discount
  - F-codes: 20% retention refund (matches 20% cap) | F8: 40% goodwill discount (vs 20% in peers) | 20%-of-PO discount-cap branch points (F15-F20) | 1h window + 45d return window restatements (TA/TO F-codes)
- **Fix:** Flagged as IC-NEW-01 through IC-NEW-08 in CODE-MAP-templates.md conflict flags table. Will be added to POLICY-THRESHOLD-INDEX.md / CONFLICT-INVENTORY in Plan 04.

---

## Known Stubs

None — no template text was invented. All wired codes cite real, verbatim template headings.

---

## Threat Flags

No new security-relevant surface. PII scan of all 9 cancellation template files found no email addresses, phone numbers, or card/SSN-like values — only placeholder tokens (`{{ticket.group.name}}`, `[LINK]`, `[DATE]`, `[Order details]`) and the store's own promo URLs. T-01-02-PII mitigation satisfied.

---

## Codes Survey Summary

| Code Family | Total Codes | Wired to Template | Gap (no template) |
|-------------|-------------|-------------------|-------------------|
| A-codes | 9 | 9 (A1-A9) | 0 |
| B-codes | 13 | 12 (B1-B3, B5-B13) | 1 (B4 — possibly retired) |
| C-codes | 2 | 2 (C1, C2) | 0 |
| D-codes | 9 | 9 (D1-D9) | 0 |
| E-codes | 13 | 13 (E1-E13) | 0 |
| F-codes | 23 | 23 (F1-F23) | 0 |
| G-codes | 15 | 15 (G1-G15 incl. G3.1/G3.2, G14, G15) | 0 |
| **Total** | **84** | **83** | **1 (B4 only)** |

---

## Residual Follow-ups for Plan 04

1. Add F23 (Aftersale promotion), G14, G15 to CODE-MAP.md (owned by Plan 01; updated by Plan 04).
2. Reconcile CODE-MAP.md generic F-code descriptions against verbatim template headings.
3. Resolve B4 (mark deprecated or find in Confluence).
4. Add the 8 IC-NEW threshold flags to POLICY-THRESHOLD-INDEX.md and CONFLICT-INVENTORY.md.
5. Confirm Google Sites update cadence with CS Lead (governance gap).
6. Confirm the 24-file set is the complete Google Sites page list (full enumeration).

---

## Self-Check

**Files exist:**
- SURVEY-email-templates.md: FOUND
- CODE-MAP-templates.md: FOUND

**Commits exist:**
- 83bbdb2 (Task 1): FOUND
- 1e9d7be (Task 2): FOUND

## Self-Check: PASSED
