---
phase: 01-knowledge-survey-conflict-inventory
document: SURVEY-email-templates.md
role: email-templates-source-inventory
status: complete — all 24 template files inventoried and wired (F-codes provided at checkpoint)
source_url: https://sites.google.com/d/1NCS0KCGO-4Kj2DXEbwW7cAok-tLh37M0/p/1gop1-Fy6OxafB3wzzrVy0MBwKqWECH0M/edit
last_updated: "2026-05-29"
produced_by: Plan 02 (Task 1 autonomous survey + Task 2 post-checkpoint fold-in)
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
| 16 | Cancellation request — New/Processing/Pending — Aftersale promotion | Markdown | `snapshots/cancellation request-template1.md` | F23 | Snapshotted | After-sales promotion price-variation explanation; shipping-fee waiver / 20% refund. F23 is a NEW code (not in CODE-MAP.md). |
| 17 | Cancellation request — New/Processing/Pending — Discount not applied | Markdown | `snapshots/cancellation request-template2.md` | F15, F16 | Snapshotted | Discount <20% PO (apply discount) vs >20% PO (offer 20% refund cap). |
| 18 | Cancellation request — New/Processing/Pending — Duplicated DO(s) | Markdown | `snapshots/cancellation request-template3.md` | F9, F10 | Snapshotted | F9 = order not found (hold 48h); F10 = order found (20% refund on 2nd order). |
| 19 | Cancellation request — New/Processing/Pending — Not recognize transaction | Markdown | `snapshots/cancellation request-template4.md` | F21 | Snapshotted | Provides order detail list for verification; 20% refund to retain. |
| 20 | Cancellation request — New/Processing/Pending — Wrong variants | Markdown | `snapshots/cancellation request-template5.md` | F7-Bra, F7-Pants | Snapshotted | Size/color swap OR 20% refund; 48h validity. Two product-line variants. |
| 21 | Cancellation request — New/Processing/Pending — Other reasons | Markdown | `snapshots/cancellation request-template6.md` | F1, F2, F3, F4, F14 | Snapshotted | F1 unknown reason, F2 cheaper price, F3 bad reviews, F4 shipping time, F14 product origin. Mostly 20% refund retention (F4 = express shipping upgrade). |
| 22 | Cancellation request — Next responses | Markdown | `snapshots/cancellation request-template7.md` | F12, F13, F22 | Snapshotted | F12 = cancel confirmed + refund; F13 = resume (20% accepted); F22 = resume (express accepted). |
| 23 | Cancellation request — TA DO(s) | Markdown | `snapshots/cancellation request-template8.md` | F5, F17, F18 | Snapshotted | In-transit / need SCE; 1-hour window message. F5 = other reasons; F17/F18 = discount <20% / >20% PO. |
| 24 | Cancellation request — TO DO(s) | Markdown | `snapshots/cancellation request-template9.md` | F6, F8, F11, F19, F20 | Snapshotted | Cannot cancel (in processing); 45-day return policy. F8 uses 40% discount (others 20%). |

---

## Template Page Count Summary

| Category | Pages (files) | Codes Covered | Status |
|----------|--------------|---------------|--------|
| Product Complaint — Within Guarantee | 3 | A1–A9, B1–B3, B5–B13, D1–D9 | Fully snapshotted |
| Product Complaint — Out of Guarantee | 1 | C1 | Fully snapshotted |
| Product Complaint — Replacement not fit | 1 | C2 | Fully snapshotted |
| Change Request | 5 | E1–E13 (all 13 E-codes present) | Fully snapshotted |
| Shipping Queries & Complaints | 5 | G1–G15 (all found; G3 has sub-codes G3.1/G3.2) | Fully snapshotted |
| Cancellation Request | 9 | F1–F23 (all found; F23 is a new code beyond CODE-MAP.md's F1–F22) | Fully snapshotted (provided at checkpoint) |
| **Total** | **24** | **A1–A9, B1–B13 (excl. B4), C1–C2, D1–D9, E1–E13, F1–F23, G1–G15** | **24 snapshotted; 0 empty** |

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

### F-Codes — RESOLVED at checkpoint (templates provided 2026-05-29)

- All 9 cancellation request template files now contain content. **F1–F23** are wired in
  CODE-MAP-templates.md. No F-code content gap remains.
- **Residual discrepancy (not a content gap):** F23 (Aftersale promotion) is a NEW code
  present in the templates but absent from CODE-MAP.md (Plan 01 listed F1–F22). Add F23 to
  CODE-MAP.md in Plan 04. Several CODE-MAP.md F-code descriptions were generic and should be
  reconciled against the verbatim template headings now captured.

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
| F23 | `cancellation request-template1.md` | Not listed in original F1–F22 CODE-MAP range — **new discovery** (Aftersale promotion); added to CODE-MAP-templates.md and flagged for CODE-MAP.md update in Plan 04 |

---

## Checkpoint Status

**Status as of Plan 02 Task 2 (post-checkpoint):** COMPLETE — checkpoint resolved
("templates provided"). 24 of 24 template files snapshotted; all carry content.

**What is complete:**
- All Product Complaint templates (A/B/C/D codes): fully snapshotted and wired.
- All Change Request templates (E-codes, all 13): fully snapshotted and wired.
- All Shipping Queries & Complaints templates (G-codes, G1–G15 + G3.1/G3.2): fully snapshotted and wired.
- All Cancellation Request templates (F-codes, F1–F23): fully snapshotted and wired (provided at checkpoint).

**Checkpoint resolution (2026-05-29):**
- The 9 cancellation request template files were filled by the user with real template content.
- F1–F23 are now wired (F23 = new code discovered, beyond the original F1–F22 range).
- The Email Templates source (SRC-02) is now inventoried **complete-as-available**: every
  template file present in `snapshots/` is inventoried and (where it carries codes) wired.

**Residual (non-blocking) follow-ups for Plan 04:**
1. Confirm the 24-file set is the *complete* Google Sites page list (full page-by-page
   enumeration still benefits from CS-Lead viewer access, but no missing-content gap is known).
2. Add F23 and G14/G15 to CODE-MAP.md (Plan 01 owns it; updated by Plan 04).
3. Confirm Google Sites update cadence with CS Lead (governance gap).

---

## SURVEY.md Reconciliation Note

> **For Plan 04 / reviewer reconciliation (do not edit SURVEY.md directly):**
>
> SRC-02 (Google Sites Email Templates) status as of Plan 02 (COMPLETE):
> - **Survey: surveyed (complete-as-available)** — all 24 snapshot files are inventoried
>   and wired. No empty placeholder files remain; no known missing-content gap.
> - **Snapshot path:** All files under `snapshots/` (24 Markdown files; all with content).
> - **Code coverage:** A1–A9, B1–B13 (excl. B4), C1–C2, D1–D9, E1–E13, F1–F23, G1–G15.
> - **Update cadence:** TBD — CS Lead has not confirmed a review/update schedule for the
>   Google Sites. Flag as a governance gap in Plan 04 action items.
> - **New codes for CODE-MAP.md update (Plan 04):** F23 (Aftersale promotion), G14 and G15
>   (DNR replacement codes) — present in templates but beyond CODE-MAP.md's original ranges.
> - **B4 gap:** Still no template found for B4; confirmed missing across all sources. Plan 04
>   to mark deprecated or resolve via Confluence.
