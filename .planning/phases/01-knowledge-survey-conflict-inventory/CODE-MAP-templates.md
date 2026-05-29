---
phase: 01-knowledge-survey-conflict-inventory
document: CODE-MAP-templates.md
role: workflow-code-to-email-template-wiring
status: partial — F-codes pending cancellation template export
source: snapshots/*.md (email template files in snapshots/)
companion: CODE-MAP.md (workflow-code-to-action mapping from Plan 01)
last_updated: "2026-05-29"
produced_by: Plan 02 (Task 1 — autonomous survey)
---

# Code-to-Template Wiring Map

> **How to use:** Each row maps a workflow state/template code to its concrete email template
> variant as found verbatim in the snapshot files. Columns:
> - **Code** — workflow state/template code from CODE-MAP.md
> - **Template Heading** — verbatim section heading as it appears in the snapshot file
> - **Product Line** — Bra / Pants / Non-apparel / All / N/A
> - **Snapshot File** — path relative to `.planning/phases/01-knowledge-survey-conflict-inventory/`
> - **Notes** — sub-variants, response sequence, or conflict flags
>
> **Wiring rule:** Only codes whose template heading ACTUALLY appears in a snapshot file are
> wired here. Unmatched codes are in the gap list at the bottom.
>
> **Key:** `[placeholder]` = Freshdesk merge field or fill-in token in the template text.
> `{{ticket.group.name}}` = agent name token used in every template opening.

---

## A-Codes: Product Complaint — Within Guarantee, Defective/Wrong/Missing Items

Source file: `snapshots/product complaint-within guarantee-template1.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| A1 | `A1-Bra-Can replace-Not provide measurements` | Bra | product complaint-within guarantee-template1.md | First response; requests underbust + full-bust measurements. |
| A1 | `A1-Pants-Can replace-Not provide measurements` | Pants | product complaint-within guarantee-template1.md | First response; requests waist + hip + inseam measurements. |
| A2 | `A2-Sizing products-Can replace-Provided measurements` | Bra + Pants | product complaint-within guarantee-template1.md | Measurements already provided; includes sizing advice block. |
| A3 | `A3-Non-apparel products-Can replace` | Non-apparel | product complaint-within guarantee-template1.md | Option to change color/style offered. |
| A4 | `A4-Cannot replace-Evidence provided` | All | product complaint-within guarantee-template1.md | Full refund + 20% next-purchase loyalty discount. |
| A5 | `A5-Cannot replace-Need evidence` | All | product complaint-within guarantee-template1.md | Requests defect photo + shipping label. Appears in both Replacement and Return request sections. |
| A6 | `A6-Bra-Can replace-Not provide measurements-Evidence provided` | Bra | product complaint-within guarantee-template1.md | Return request; offers replacement OR full refund; no return shipment required. |
| A6 | `A6-Pants-Can replace-Not provide measurements-Evidence provided` | Pants | product complaint-within guarantee-template1.md | Return request variant for pants. |
| A6 | `A6-Non-apparel products-Can replace-Evidence provided` | Non-apparel | product complaint-within guarantee-template1.md | Return request variant for non-apparel. |
| A7 | `A7-Bra-Can replace-Not provide measurements-Evidence not provided` | Bra | product complaint-within guarantee-template1.md | Evidence not yet provided; requests defect photo before option 2 (refund). |
| A7 | `A7-Pants-Can replace-Not provide measurements-Evidence not provided` | Pants | product complaint-within guarantee-template1.md | Pants variant. |
| A7 | `A7-Non-apparel products-Can replace-Evidence not provided` | Non-apparel | product complaint-within guarantee-template1.md | Non-apparel variant. |
| A8 | `A8-Sizing products-Can replace-Provided measurements-Evidence provided` | Bra + Pants | product complaint-within guarantee-template1.md | Measurements + evidence both provided; offers replacement OR full refund. |
| A9 | `A9-Cannot replace-Evidence provided` | All | product complaint-within guarantee-template1.md | Partial refund (variable amount [Refund Amount]) + 20% discount. |

---

## B-Codes: Product Complaint — Within Guarantee, Non-Defective (Fit/Satisfaction) Items

Source file: `snapshots/product complaint-within guarantee-template2.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| B1 | `B1-Bra-Can replace-Not provide measurements` | Bra | product complaint-within guarantee-template2.md | First response; requests underbust + full-bust. |
| B1 | `B1-Pants-Can replace-Not provide measurements` | Pants | product complaint-within guarantee-template2.md | Requests waist + hip + inseam. |
| B1 | `B1-Non-apparel products-Can replace` | Non-apparel | product complaint-within guarantee-template2.md | Option to change color/style. |
| B2 | `B2-Sizing products-Can replace-Provided measurements` | Bra + Pants | product complaint-within guarantee-template2.md | Measurements provided; sizing advice included. |
| B3 | `B3-Cannot replace-Variant is not available` | All | product complaint-within guarantee-template2.md | Offers 50% refund OR 40% discount + free shipping. |
| B5 | `B5-Sizing products-Can replace-Provided measurements` | Bra + Pants | product complaint-within guarantee-template2.md | Return request; offers replacement OR 50% refund + 40% discount + free shipping. |
| B5 | `B5-Non-apparel products-Can replace` | Non-apparel | product complaint-within guarantee-template2.md | Non-apparel return variant. |
| B6 | `B6-Bra-Can replace-Not provide measurements` | Bra | product complaint-within guarantee-template2.md | Return request; measurements not yet provided. |
| B6 | `B6-Pants-Can replace-Not provide measurements` | Pants | product complaint-within guarantee-template2.md | Pants return variant. |
| B7 | `B7-All products-Cannot replace` | All | product complaint-within guarantee-template2.md | Cannot replace; offers 50% refund AND 40% discount + free shipping (both, not either/or). |
| B8 | `B8-Cannot replace-Variant is not available (365 GRT)` | All | product complaint-within guarantee-template2.md | 365-day guarantee variant of B3. |
| B9 | `B9-Sizing products- Can replace- Provided measurements (365 GRT)` | Bra + Pants | product complaint-within guarantee-template2.md | 365-day guarantee variant of B5-Sizing. Full refund eligible. |
| B10 | `B10-Non-apparel products-Can replace (365 GRT)` | Non-apparel | product complaint-within guarantee-template2.md | 365-day guarantee variant of B5-Non-apparel. |
| B11 | `B11-Bra-Can replace-Not provide measurements (365 GRT)` | Bra | product complaint-within guarantee-template2.md | 365-day guarantee variant of B6-Bra. |
| B12 | `B12-Pants-Can replace-Not provide measurements (365 GRT)` | Pants | product complaint-within guarantee-template2.md | 365-day guarantee variant of B6-Pants. |
| B13 | `B13-All products-Cannot replace (365 GRT)` | All | product complaint-within guarantee-template2.md | 365-day guarantee variant of B7. |

---

## C-Codes: Product Complaint — Out of Guarantee / Replacement Not Fit

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| C1 | `C1-Out of warranty` | All | product complaint-out of guarantee-template.md | 40% VIP discount + free shipping; no replacement/refund. References both 45-day (purchase) and 14-day (delivery) warranty windows — **conflict flag IC-01**. |
| C2 | `C2-Sizing products-Replacement still does not fit` | Bra + Pants | product complaint-replacement not fit-template.md | No additional compensation; 40% VIP discount only. |

---

## D-Codes: Product Complaint — Follow-up / Confirmation Responses

Source file: `snapshots/product complaint-within guarantee-template3.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| D1 | `D1-Sizing products-Customer accepts replacement-Not confirm size` | Bra + Pants | product complaint-within guarantee-template3.md | Follow-up when customer accepts replacement but has not confirmed measurements. |
| D2 | `D2-Customer accepts replacement-Confirmed size` | All | product complaint-within guarantee-template3.md | Confirmation: replacement being processed. |
| D3 | `D3-Customer accepts a refund` | All | product complaint-within guarantee-template3.md | Refund confirmation template. |
| D4 | `D4-All products-Customer accepts 40% discount for alternatives` | All | product complaint-within guarantee-template3.md | Customer chooses 40% discount option instead of refund/replacement. |
| D5 | `D5-Bra-Customer selects replacement-Not provide measurements` | Bra | product complaint-within guarantee-template3.md | Replacement selected; measurements still needed. |
| D5 | `D5-Pants-Customer selects replacement-Not provide measurements` | Pants | product complaint-within guarantee-template3.md | Pants variant. |
| D6 | `D6-All products-Customer accepts 50% refund AND 40% discount for alternatives (follow-up B5, B6)` | All | product complaint-within guarantee-template3.md | Follow-up for B5/B6 when customer accepts refund + discount. |
| D6 | `D6-All products-Customer accepts replacement AND 40% discount for alternatives (follow-up B5, B6)` | All | product complaint-within guarantee-template3.md | Follow-up for B5/B6 when customer accepts replacement + discount. D6 has two distinct sub-variants. |
| D7 | `D7-Provide return address` | All | product complaint-within guarantee-template3.md | Provides return shipping address to customer. |
| D8 | `D8-Customer refuse 70%` | All | product complaint-within guarantee-template3.md | Customer refuses 70% refund offer — escalation path. Confirms 70% refund threshold exists (not in original POLICY-THRESHOLD-INDEX; flag for Plan 04). |
| D9 | `D9-Invalid/ Not Provide Evidence` | All | product complaint-within guarantee-template3.md | Request for valid evidence when customer-provided evidence is insufficient or missing. |

---

## E-Codes: Change Request Actions

### E-codes — New/Processing/Pending orders (within 1-hour window)

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| E1 | `E1-Shipping address-Can change` | N/A | change request-template3.md | Successful address change confirmation; new address confirmed in reply. |
| E4 | `E4-Bra-Product variant-Can change-Same or lower price` | Bra | change-request-template2.md | Requests underbust + full-bust measurements before processing. |
| E4 | `E4-Pants-Product variant-Can change-Same or lower price` | Pants | change-request-template2.md | Requests waist + hip + inseam measurements. |
| E5 | `E5-Product variant-Can change-Higher price` | All | change-request-template2.md | Invoice for price difference sent; 48-hour payment window before reverting to original. |
| E8 | `E8-Change email address` | N/A | change request-template1.md | Email address updated confirmation; new email stated in reply. |
| E8 | `E8-Change phone number` | N/A | change request-template1.md | Phone number updated confirmation. E8 covers two contact-detail sub-types. |
| E9 | `E9-Change billing address` | N/A | change request-template1.md | Billing address updated; note that shipping address is unchanged. |
| E10 | `E10-Product variant-Cannot change-Add more items` | All | change-request-template2.md | System cannot add items; 20% discount offered on new order. |
| E11 | `E11-Change variant successfully` | All | change-request-template2.md | Variant change processed successfully confirmation. |
| E12 | `E12-Order resumed as it is-Unable to contact customer` | All | change-request-template2.md | Order processed with original selection after no customer response. |
| E13 | `E13-Warning Address-Address still invalid` | N/A | change request-template3.md | System-flagged invalid address; requests customer to confirm/correct. |

### E-codes — TA DO(s) (in-transit, outside 1-hour window)

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| E2 | `E2-Shipping address-Need SCE to confirm` | N/A | change request-template4.md | Cannot guarantee change; forwarded to fulfillment; 24–48h follow-up; asks for correct address. |
| E6 | `E6-Pants-Product variant-Need SCE to confirm` | Pants | change request-template4.md | Forwarded to fulfillment; requests waist + hip + inseam measurements. |
| E6 | `E6-Bra-Product variant-Need SCE to confirm` | Bra | change request-template4.md | Forwarded to fulfillment; requests underbust + full-bust measurements. |

### E-codes — TO DO(s) (delivered/completed, outside window)

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| E3 | `E3-Shipping address-Cannot change` | N/A | change request-template5.md | Package shipped; advise carrier contact + 40% discount for re-order. References discount link. |
| E7 | `E7-Product variant-Cannot change` | All | change request-template5.md | Package shipped; 45-day return/exchange window referenced; 40% discount offered. |

---

## F-Codes: Cancellation Request Actions

> **STATUS: ALL EMPTY — No template content available.**
>
> All 5 cancellation request template files (cancellation request-template1.md through
> cancellation request-template5.md) are 0 bytes. F-code wiring cannot be completed until
> the CS Lead exports the Google Sites cancellation request template pages to Markdown.
>
> From CODE-MAP.md, 22 F-codes exist (F1–F22). None can be wired to a template heading.

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| F1 | — | — | cancellation request-template?.md | **EMPTY FILE** — template not yet exported. |
| F2 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F3 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F4 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F5 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F6 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F7 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F8 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F9 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F10 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F11 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F12 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F13 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F14 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F15 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F16 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F17 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F18 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F19 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F20 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F21 | — | — | cancellation request-template?.md | **EMPTY FILE** |
| F22 | — | — | cancellation request-template?.md | **EMPTY FILE** |

---

## G-Codes: Shipping Inquiry / Complaint Actions

### G-codes — DNR (Delivered Not Received)

Source file: `snapshots/shipping queries & complaints-template1.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| G10 | `G10-Delivered not received` | All | shipping queries & complaints-template1.md | First response: guide customer to check porch/neighbors; provide carrier contact; attach proof of delivery. |
| G14 | `G14-Bra-DNR-Replacement` | Bra | shipping queries & complaints-template1.md | Second response: complimentary replacement; requests valid address + underbust/full-bust. **G14 is a NEW CODE not in original CODE-MAP.md G1–G13 range.** |
| G14 | `G14-Pants-DNR-Replacement` | Pants | shipping queries & complaints-template1.md | Requests waist + hip + inseam. |
| G14 | `G14-Non-apparel products-DNR-Replacement` | Non-apparel | shipping queries & complaints-template1.md | Option to change color/style. |
| G15 | `G15-Bra-DNR-Replacement or Full Refund` | Bra | shipping queries & complaints-template1.md | Second response when customer explicitly requests refund: offer replacement first, or proceed with full refund. **G15 is a NEW CODE not in original CODE-MAP.md G1–G13 range.** |
| G15 | `G15-Pants-DNR-Replacement or Full Refund` | Pants | shipping queries & complaints-template1.md | Pants variant. |
| G15 | `G15-Non-apparel products-DNR-Replacement or Full Refund` | Non-apparel | shipping queries & complaints-template1.md | Non-apparel variant. |

### G-codes — OOS (Out of Stock)

Source file: `snapshots/shipping queries & complaints-template2.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| G3.1 | `G3.1-Out of stock-Order is not fulfilled-Can change variant` | All | shipping queries & complaints-template2.md | Can switch to available variant; complimentary expedited shipping upgrade offered. |
| G3.2 | `G3.2-Out of stock-Order is not fulfilled-Cannot change variant` | All | shipping queries & complaints-template2.md | Cannot change; express shipping once fulfilled; 20% refund offered as goodwill. |

### G-codes — RTS (Return to Sender)

Source file: `snapshots/shipping queries & complaints-template3.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| G11 | `G11-Bra-Returned to sender` | Bra | shipping queries & complaints-template3.md | Complimentary replacement; requests valid address + underbust/full-bust. |
| G11 | `G11-Pants-Returned to sender` | Pants | shipping queries & complaints-template3.md | Requests waist + hip + inseam. |
| G11 | `G11-Non-apparel products-Returned to sender` | Non-apparel | shipping queries & complaints-template3.md | Option to change color/style. |
| G13 | `G13-Failed delivery-Courier attempting redelivery` | All | shipping queries & complaints-template3.md | Advise customer to contact last-mile courier for re-delivery; no compensation offered at this stage. |

### G-codes — Test Contract

Source file: `snapshots/shipping queries & complaints-template4.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| G12 | `G12-Test contract order` | All | shipping queries & complaints-template4.md | Order cancelled (OOS); refund within 3–5 days; 30% discount on next purchase via dedicated link. |

### G-codes — Common Shipping Scenarios

Source file: `snapshots/shipping queries & complaints-template5.md`

| Code | Template Heading (verbatim) | Product Line | Snapshot File | Notes |
|------|-----------------------------|--------------|---------------|-------|
| G1 | `G1 - Order is not created (Ask about delivery time frame)` | All | shipping queries & complaints-template5.md | No order in system; informs customer of 7–15 business day standard delivery window. |
| G2 | `G2-Order is not fulfilled-Neutral customers` | All | shipping queries & complaints-template5.md | Order in warehouse; dispatch within 1–2 days; 7–15 business day delivery. |
| G4 | `G4-Order age within 21 days-Neutral customers` | All | shipping queries & complaints-template5.md | Package in transit; provides current location + ETA. |
| G5 | `G5-Order age within 21 days-Angry customers` | All | shipping queries & complaints-template5.md | Empathetic tone; provides location + ETA + 50% discount as appeasement gesture. |
| G6 | `G6-Late delivery-Discount` | All | shipping queries & complaints-template5.md | Delay acknowledged; 40% discount offered as goodwill; ETA provided. |
| G7 | `G7-Late delivery-Partial refund & Discount` | All | shipping queries & complaints-template5.md | Two-option offer: 40% VIP discount OR 10% refund on current order. |
| G8 | `G8-Bra-Late delivery-Express replacement` | Bra | shipping queries & complaints-template5.md | Package presumed lost in transit; express replacement; requests address + underbust/full-bust. |
| G8 | `G8-Pants-Late delivery-Express replacement` | Pants | shipping queries & complaints-template5.md | Requests waist + hip + inseam. |
| G8 | `G8-Non-apparel products-Late delivery-Express replacement` | Non-apparel | shipping queries & complaints-template5.md | Option to change color/style. |
| G9 | `G9-Late delivery-Promise a replacement/refund on day 40` | All | shipping queries & complaints-template5.md | Second response: if package not arrived by Day 40, will arrange replacement or full refund. |

---

## Codes Without a Template (Gap List)

> These codes appear in CODE-MAP.md but have NO matching template heading in any snapshot file.
> They are surfaced as coverage gaps for Plan 04.

### Gap Category 1: F-Codes — Template files empty (content exists on Google Sites, not yet exported)

All 22 F-codes (F1–F22) from CODE-MAP.md are in this category.

| Code | Code-MAP Description | Gap Type | Action |
|------|---------------------|----------|--------|
| F1 | Confirm cancellation eligibility check | Template exists on Google Sites; file empty | CS Lead must export and fill `cancellation request-template*.md` files |
| F2 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F3 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F4 | Offer express shipping (as alternative to cancellation) | Template exists on Google Sites; file empty | As above |
| F5 | Customer agrees to proceed | Template exists on Google Sites; file empty | As above |
| F6 | Reject cancellation request | Template exists on Google Sites; file empty | As above |
| F7 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F8 | Reject cancellation request (grouped with F6, F11) | Template exists on Google Sites; file empty | As above |
| F9 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F10 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F11 | Reject cancellation request (grouped with F6, F8) | Template exists on Google Sites; file empty | As above |
| F12 | Cancel DO/PO | Template exists on Google Sites; file empty | As above |
| F13 | Process upon customer confirmation | Template exists on Google Sites; file empty | As above |
| F14 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F15 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F16 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F17 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F18 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F19 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F20 | Cancellation flow branch action | Template exists on Google Sites; file empty | As above |
| F21 | Offer partial refund to retain order | Template exists on Google Sites; file empty | As above |
| F22 | Process upon customer confirmation (paired with F13) | Template exists on Google Sites; file empty | As above |

### Gap Category 2: B4 — Code possibly retired or subsumed

| Code | CODE-MAP Description | Gap Type | Action |
|------|---------------------|----------|--------|
| B4 | Referenced without dedicated node in WorkFlow.svg; not in any template file | No template found; may be retired code | Verify in Plan 03 (Confluence) or Plan 04. May be subsumed by B3/B5/B6 range or "B(5),(6),(7),8" notation. |

### Gap Category 3: D-codes partially mapped from workflow but now have templates

> All D-codes (D1–D9) previously marked "TBD — Plan 02" in CODE-MAP.md are now wired.
> No remaining D-code gaps.

### Gap Category 4: G14, G15 — New codes discovered, not in original CODE-MAP.md

| Code | Gap Type | Action |
|------|----------|--------|
| G14 | Present in template but not in CODE-MAP.md (range was G1–G13) | Add G14 to CODE-MAP.md in Plan 04 |
| G15 | Present in template but not in CODE-MAP.md (range was G1–G13) | Add G15 to CODE-MAP.md in Plan 04 |

---

## Conflict Flags Discovered During Wiring

| Flag ID | Codes Involved | Description | Action |
|---------|---------------|-------------|--------|
| IC-01 (pre-existing) | C1 | Template references both 45-day (purchase-date) and 14-day (delivery-date) warranty windows in the same template — inconsistency also flagged in POLICY-THRESHOLD-INDEX.md from Plan 01. | Plan 04 conflict detection |
| IC-NEW-01 | D8 | Template heading `D8-Customer refuse 70%` confirms a 70% partial refund option exists. This threshold was in CODE-MAP.md note for D6 but not in POLICY-THRESHOLD-INDEX.md. | Add to POLICY-THRESHOLD-INDEX.md in Plan 04 |
| IC-NEW-02 | G5 | G5 template offers a 50% discount as appeasement gesture for shipping delay — a higher discount rate than the standard 40% discount seen in most other templates. Cross-source threshold discrepancy for Plan 04. | Plan 04 conflict detection |
| IC-NEW-03 | G12 | G12 (test contract) offers a 30% discount — different from the standard 40% discount and the 20%/50% used elsewhere. May be intentional for test-contract scenario; flag for Plan 04 verification. | Plan 04 conflict detection |
| IC-NEW-04 | G7 | G7 offers 10% refund as one option vs 40% discount as another — the refund percentage (10%) appears only in this template and is not in POLICY-THRESHOLD-INDEX.md. | Add to POLICY-THRESHOLD-INDEX.md in Plan 04 |

---

## Product-Line Fan-Out Summary

> Many codes map to multiple template variants by product line. This table summarises the fan-out pattern.

| Fan-out Type | Applies To | Variants |
|-------------|------------|---------|
| Bra / Pants / Non-apparel (3 variants) | A1, A6, A7, B1, B5, B6, G8, G11, G14, G15 | Three separate templates; measurement requests differ by product type |
| Bra / Pants only (2 variants — sizing products) | A2, A8, B2, D1, D5, E4, E6 | Sizing products only; non-apparel not applicable |
| All products (single template) | A4, A5, A9, B3, B7, B8, B13, C1, C2, D2, D3, D4, D6, D7, D8, D9, E1–E13 (most), G1–G7, G9, G10, G12, G13 | Single template covers all product types |
| Sub-code split (not product-line) | G3 (G3.1 / G3.2), D6 (two sub-variants), E8 (email / phone) | Split by condition, not product type |
