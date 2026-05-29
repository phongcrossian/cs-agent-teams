---
phase: 01-knowledge-survey-conflict-inventory
document: SURVEY-email-templates.md
role: email-templates-source-inventory
status: partial — awaiting cancellation-request templates (checkpoint)
source_url: https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/p/1gop1-Fy6OxafB3wzzrVy0MBwKqWECH0M/edit
last_updated: "2026-05-29"
produced_by: Plan 02 (Task 1 — autonomous survey of existing snapshots)
---

# Email Templates Inventory

> **Purpose:** Inventory of the Google Sites Email Templates source (SRC-02).
> Fills the SRC-02 placeholder row in SURVEY.md Source Inventory.
> Do NOT edit SURVEY.md directly — reconciliation note is at the bottom of this file.
>
> **Source root (Google Sites):**
> https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/p/1gop1-Fy6OxafB3wzzrVy0MBwKqWECH0M/edit
>
> **Update cadence:** TBD — confirm with CS Lead (no versioning metadata visible on Google Sites).
> **Owner / Access:** CS Lead / Google Sites viewer access required for full enumeration.
> **Snapshot format:** Markdown (D-04 decision) — plain text reply boilerplate with placeholder tokens.

---

## Email Templates Inventory

| # | Template Page (file) | Format | Snapshot Path | Covered Workflow Codes | Status | Notes |
|---|----------------------|--------|---------------|------------------------|--------|-------|
| 1 | Product complaint — Within guarantee — Defective/Wrong/Missing items | Markdown | `snapshots/product complaint-within guarantee-template1.md` | A1, A2, A3, A4, A5, A6, A7, A8, A9 | Snapshotted | 9 codes, multiple product-line variants per code (Bra / Pants / Non-apparel). A5 appears in both Replacement and Return sections. |
| 2 | Product complaint — Within guarantee — Non-defective items | Markdown | `snapshots/product complaint-within guarantee-template2.md` | B1, B2, B3, B5, B6, B7, B8, B9, B10, B11, B12, B13 | Snapshotted | B4 absent — not in this file or WorkFlow.svg; flagged as gap. B8–B13 are 365-day guarantee (365 GRT) variants of B3/B5/B6/B7. |
| 3 | Product complaint — Within guarantee — Next responses (D-codes) | Markdown | `snapshots/product complaint-within guarantee-template3.md` | D1, D2, D3, D4, D5, D6, D7, D8, D9 | Snapshotted | Follow-up / confirmation templates. D6 covers two sub-variants (refund path and replacement path). D8 covers "customer refuses 70%" scenario (confirms 70% refund threshold from CODE-MAP). |
| 4 | Product complaint — Out of guarantee | Markdown | `snapshots/product complaint-out of guarantee-template.md` | C1 | Snapshotted | Single template; references both 45-day (purchase) and 14-day (delivery) warranty windows — key conflict candidate. |
| 5 | Product complaint — Replacement not fit | Markdown | `snapshots/product complaint-replacement not fit-template.md` | C2 | Snapshotted | Post-replacement satisfaction complaint; no further compensation. |
| 6 | Change request — New/Processing/Pending — Product variant | Markdown | `snapshots/change-request-template2.md` | E4-Bra, E4-Pants, E5, E10, E11, E12 | Snapshotted | Covers can-change (same/lower and higher price), cannot-change (add items), confirmation, and resume-as-is variants. |
| 7 | Change request — New/Processing/Pending — Non-shipping address | Markdown | `snapshots/change request-template1.md` | E8, E9 | Snapshotted | Covers email address, phone number (both E8 sub-variants), and billing address change confirmations. |
| 8 | Change request — New/Processing/Pending — Shipping address | Markdown | `snapshots/change request-template3.md` | E1, E13 | Snapshotted | Covers successful address change confirmation (E1) and warning-address invalid follow-up (E13). |
| 9 | Change request — TA DO(s) | Markdown | `snapshots/change request-template4.md` | E2, E6-Pants, E6-Bra | Snapshotted | Covers address change (E2) and product variant change (E6) when DO is in-transit (TA status). |
| 10 | Change request — TO DO(s) | Markdown | `snapshots/change request-template5.md` | E3, E7 | Snapshotted | Covers address change (E3) and variant change (E7) when DO is delivered/completed (TO status). |
| 11 | Shipping queries/complaints — DNR (Delivered not received) | Markdown | `snapshots/shipping queries & complaints-template1.md` | G10, G14-Bra, G14-Pants, G14-Non-apparel, G15-Bra, G15-Pants, G15-Non-apparel | Snapshotted | G10 = first response (guide customer to look for package). G14 = replacement offer. G15 = replacement-or-full-refund offer. All three codes have product-line variants. |
| 12 | Shipping queries/complaints — OOS (Out of stock) | Markdown | `snapshots/shipping queries & complaints-template2.md` | G3.1, G3.2 | Snapshotted | G3 has two sub-codes: can-change-variant (G3.1, offer express shipping) vs cannot-change-variant (G3.2, offer 20% refund). |
| 13 | Shipping queries/complaints — RTS (Return to sender) | Markdown | `snapshots/shipping queries & complaints-template3.md` | G11-Bra, G11-Pants, G11-Non-apparel, G13 | Snapshotted | G11 = replacement offer for returned packages (3 product-line variants). G13 = failed delivery / courier attempting redelivery. |
| 14 | Shipping queries/complaints — Test contract | Markdown | `snapshots/shipping queries & complaints-template4.md` | G12 | Snapshotted | Single template: test-contract order cancelled; 30% discount on next purchase offered. |
| 15 | Shipping queries/complaints — Common shipping scenarios | Markdown | `snapshots/shipping queries & complaints-template5.md` | G1, G2, G4, G5, G6, G7, G8-Bra, G8-Pants, G8-Non-apparel, G9 | Snapshotted | G1–G9 (all found). G8 has 3 product-line variants. G9 is second-response (promise replacement/refund on day 40). |
| 16 | Cancellation request — template 1 | Markdown | `snapshots/cancellation request-template1.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 17 | Cancellation request — template 2 | Markdown | `snapshots/cancellation request-template2.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 18 | Cancellation request — template 3 | Markdown | `snapshots/cancellation request-template3.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 19 | Cancellation request — template 4 | Markdown | `snapshots/cancellation request-template4.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 20 | Cancellation request — template 5 | Markdown | `snapshots/cancellation request-template5.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 21 | Cancellation request — template 6 | Markdown | `snapshots/cancellation request-template6.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 22 | Cancellation request — template 7 | Markdown | `snapshots/cancellation request-template7.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 23 | Cancellation request — template 8 | Markdown | `snapshots/cancellation request-template8.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |
| 24 | Cancellation request — template 9 | Markdown | `snapshots/cancellation request-template9.md` | Unknown — F-codes (TBD) | **EMPTY** | Placeholder file, 0 bytes. CS Lead must export content. |

---

## Template Page Count Summary

| Category | Pages (files) | Codes Covered | Status |
|----------|--------------|---------------|--------|
| Product Complaint — Within Guarantee | 3 | A1–A9, B1–B3, B5–B13, D1–D9 | Fully snapshotted |
| Product Complaint — Out of Guarantee | 1 | C1 | Fully snapshotted |
| Product Complaint — Replacement not fit | 1 | C2 | Fully snapshotted |
| Change Request | 5 | E1–E13 (all 13 E-codes present) | Fully snapshotted |
| Shipping Queries & Complaints | 5 | G1–G15 (all found; G3 has sub-codes G3.1/G3.2) | Fully snapshotted |
| Cancellation Request | 5 | F-codes (TBD) | **All empty — awaiting export** |
| **Total** | **20** | **A1–A9, B1–B13 (excl. B4), C1–C2, D1–D9, E1–E13, G1–G15** | **15 snapshotted; 5 empty** |

---

## Placeholder / Missing Template Note

> **templates.md** was referenced in CODE-MAP.md (Plan 01) as the source for G10/G11/G14/G15.
> This file does not exist in snapshots/. The G10, G11, G14, G15 content is present in
> `shipping queries & complaints-template1.md` and `shipping queries & complaints-template3.md`.
> CODE-MAP.md cross-references should be updated to point to these files (tracked for Plan 04).

---

## Gap List (codes without a template — by code family)

### B4 — No template found (possibly retired or subsumed)

- **B4** is absent from all snapshot template files and was not observed as a standalone node in
  WorkFlow.svg. It may be a retired code or subsumed into another range (e.g., within the
  "B(5),(6),(7),8" notation). Flagged for Plan 03/04 verification.

### F-Codes — All 5 cancellation request template files are empty

- **F1–F22** (22 codes total from CODE-MAP.md) have no template content available yet.
  The 5 placeholder files confirm the template pages exist on Google Sites, but content has
  not been exported. This is the primary gap requiring human action (see checkpoint below).

### G-Code gaps (minor)

- **G3** maps to two sub-codes (G3.1 / G3.2) in the template, while CODE-MAP.md records a
  single G3 row. Sub-code distinction confirmed in snapshot; CODE-MAP-templates.md records both.

---

## Newly Discovered Codes (not in original PLAN.md code range list)

| Code | Found In | Status |
|------|----------|--------|
| B8–B13 | `product complaint-within guarantee-template2.md` | 365-day guarantee variants; already added to CODE-MAP.md in Plan 01 |
| C2 | `product complaint-replacement not fit-template.md` | Already added to CODE-MAP.md in Plan 01 |
| G3.1, G3.2 | `shipping queries & complaints-template2.md` | Sub-codes of G3; recorded in CODE-MAP-templates.md |
| G13 | `shipping queries & complaints-template3.md` | Already in CODE-MAP.md range; template confirmed |
| G14, G15 | `shipping queries & complaints-template1.md` | Not listed in original G1–G13 CODE-MAP range — **new discovery**; added to CODE-MAP-templates.md and flagged for CODE-MAP.md update in Plan 04 |

---

## Checkpoint Status

**Status as of Plan 02 Task 1 (autonomous survey):** Partial — 15 of 20 template pages snapshotted.

**What is complete:**
- All Product Complaint templates (A/B/C/D codes): fully snapshotted and wired.
- All Change Request templates (E-codes, all 13): fully snapshotted and wired.
- All Shipping Queries & Complaints templates (G-codes, G1–G15 + G3.1/G3.2): fully snapshotted and wired.

**What requires human action:**
1. The 5 Cancellation Request template files are empty (0 bytes). CS Lead must export the
   Google Sites cancellation-request template pages to Markdown and place them in `snapshots/`.
2. Confirmation that the 20-file set is complete — i.e., no additional template pages exist
   on the Google Sites site that have NOT been placed in snapshots/ (even as empty placeholders).
3. Full page-by-page enumeration of the Google Sites site to confirm no pages are missing
   from the current 20-file list (requires CS Lead read-only viewer access).

---

## SURVEY.md Reconciliation Note

> **For Plan 04 / reviewer reconciliation (do not edit SURVEY.md directly):**
>
> SRC-02 (Google Sites Email Templates) status as of Plan 02, Task 1:
> - **Survey: complete-as-available** — all non-empty snapshot files are inventoried and wired.
> - **Pending:** 5 cancellation-request template files are empty; F-code wiring cannot be
>   completed until CS Lead exports those pages.
> - **Snapshot path:** All files under `snapshots/` (20 Markdown files; 15 with content).
> - **Update cadence:** TBD — CS Lead has not confirmed a review/update schedule for the
>   Google Sites. Flag as a governance gap in Plan 04 action items.
> - **G14/G15 discovery:** These codes are not in the original G1–G13 CODE-MAP.md range.
>   Plan 04 should update CODE-MAP.md to add G14 and G15 as shipping-inquiry DNR replacement codes.
