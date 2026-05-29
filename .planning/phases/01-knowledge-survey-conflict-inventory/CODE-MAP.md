---
phase: 01-knowledge-survey-conflict-inventory
document: CODE-MAP.md
role: workflow-code-to-action-mapping
status: seeded-by-plan-01
source: snapshots/WorkFlow.svg + snapshots/templates.md + snapshot template files
last_updated: "2026-05-29"
---

# Workflow Code Map

> **How to use:** Each row maps a workflow state/template code to its action as described in
> the WorkFlow.svg node text. The "Linked email template" column is filled by Plan 02
> (Email Templates survey). Do NOT rename columns.  
> Source: `snapshots/WorkFlow.svg` (node text transcribed verbatim where possible).
> Template file cross-references are from the snapshot Markdown files in `snapshots/`.

---

## A-Codes: Product Complaint — Within Warranty, Defective/Wrong/Missing Items

> Macro-flow: **3. PRODUCT COMPLAINT** — within-warranty path, defective/wrong/missing item sub-flow.

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| A1 | 3. PRODUCT COMPLAINT | Offer complimentary replacement (sizing products — bra or pants, measurements not yet provided) | product complaint-within guarantee-template1.md § A1-Bra / A1-Pants | Two variants: Bra (ask underbust/full-bust) and Pants (ask waist/hip/inseam). |
| A2 | 3. PRODUCT COMPLAINT | Offer complimentary replacement (sizing products — measurements already provided) | product complaint-within guarantee-template1.md § A2 | Includes sizing advice block. |
| A3 | 3. PRODUCT COMPLAINT | Offer complimentary replacement (non-apparel products — can replace) | product complaint-within guarantee-template1.md § A3 | Option to change color/style. |
| A4 | 3. PRODUCT COMPLAINT | Cannot replace — evidence provided; process full refund (item unavailable); offer 20% loyalty discount | product complaint-within guarantee-template1.md § A4 | Refund + 20% next-purchase discount. |
| A5 | 3. PRODUCT COMPLAINT | Cannot replace — evidence not yet provided; request evidence before refund | product complaint-within guarantee-template1.md § A5 | Request defect photo + shipping label. Appears in both Replacement Request and Return Request sections. |
| A6 | 3. PRODUCT COMPLAINT | Return request — can replace; offer replacement OR full refund (evidence provided) | product complaint-within guarantee-template1.md § A6-Bra / A6-Pants / A6-Non-apparel | Three variants by product type. No return required. |
| A7 | 3. PRODUCT COMPLAINT | Return request — can replace; offer replacement OR full refund (evidence not yet provided) | product complaint-within guarantee-template1.md § A7-Bra / A7-Pants / A7-Non-apparel | Three variants. Option 2 (refund) requires evidence photo. |
| A8 | 3. PRODUCT COMPLAINT | Return request — sizing product, measurements provided, evidence provided; offer replacement OR full refund | product complaint-within guarantee-template1.md § A8 | Includes sizing advice. |
| A9 | 3. PRODUCT COMPLAINT | Cannot replace — evidence provided; process partial refund + 20% discount | product complaint-within guarantee-template1.md § A9 | Refund amount is variable [Refund Amount]; 20% discount offered. |

---

## B-Codes: Product Complaint — Within Warranty, Non-Defective (Fit/Satisfaction) Items

> Macro-flow: **3. PRODUCT COMPLAINT** — within-warranty path, non-defective/fit/satisfaction sub-flow.
> Also partially referenced in **1. CANCELLATION REQUEST** (B7 exception note).

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| B1 | 3. PRODUCT COMPLAINT | Replacement request — can replace; offer complimentary replacement (measurements not provided) | product complaint-within guarantee-template2.md § B1-Bra / B1-Pants / B1-Non-apparel | Three variants by product type. |
| B2 | 3. PRODUCT COMPLAINT | Replacement request — sizing product, measurements provided; offer complimentary replacement with sizing advice | product complaint-within guarantee-template2.md § B2 | Includes sizing advice block. |
| B3 | 3. PRODUCT COMPLAINT | Replacement request — cannot replace (variant unavailable); offer 50% refund OR 40% discount + free shipping | product complaint-within guarantee-template2.md § B3 | Flow node: "Offer 50% refund OR 40% discount + free shipping (B3)". |
| B4 | 3. PRODUCT COMPLAINT | Referenced in SVG flow range notation — no dedicated node observed | TBD — Plan 02 | **Referenced without a dedicated node.** The SVG references "B(5),(6),(7),8" as a range; B4 does not appear as its own node in WorkFlow.svg or in any snapshot template file. Verify in Plan 03/04 whether B4 is a retired code or was subsumed into another. |
| B5 | 3. PRODUCT COMPLAINT | Return request — can replace (sizing product, measurements provided OR non-apparel); offer replacement OR 50% refund + 40% discount + free shipping | product complaint-within guarantee-template2.md § B5-Sizing / B5-Non-apparel | Flow node: "Offer 50% refund plus 40% discount + free shipping (B5,B6)". Two template variants. |
| B6 | 3. PRODUCT COMPLAINT | Return request — can replace (bra or pants, measurements not provided); offer replacement (with measurement request) OR 50% refund + 40% discount + free shipping | product complaint-within guarantee-template2.md § B6-Bra / B6-Pants | Flow node: "Offer 50% refund plus 40% discount + free shipping (B5,B6)". Two variants. |
| B7 | 3. PRODUCT COMPLAINT | Return request — cannot replace (all products); offer 50% refund AND 40% discount + free shipping (both together) | product complaint-within guarantee-template2.md § B7 | Flow node: "Offer 50% refund AND 40% discount + free shipping (B7)". Exception note in CANCELLATION REQUEST: if request is to add line items (impossible), explain system limitation and offer discount. |
| B8 | 3. PRODUCT COMPLAINT | Replacement request — cannot replace, variant unavailable (365-day guarantee variant) | product complaint-within guarantee-template2.md § B8 | **Discovered in template file — not observed as a standalone node in WorkFlow.svg.** May be referenced inside the "B(5),(6),(7),8" range notation. Represents the 365-day guarantee variant of B3. Verify node existence in Plan 03/04. |
| B9 | 3. PRODUCT COMPLAINT | Return request — sizing product, measurements provided (365-day guarantee variant); offer replacement OR 50% refund + 40% discount | product complaint-within guarantee-template2.md § B9 | 365 GRT (Guarantee) variant of B5-Sizing. Full refund eligible. |
| B10 | 3. PRODUCT COMPLAINT | Return request — non-apparel, can replace (365-day guarantee variant); offer replacement OR 50% refund + 40% discount | product complaint-within guarantee-template2.md § B10 | 365 GRT variant of B5-Non-apparel. Full refund eligible. |
| B11 | 3. PRODUCT COMPLAINT | Return request — bra, measurements not provided (365-day guarantee variant); offer replacement OR 50% refund + 40% discount | product complaint-within guarantee-template2.md § B11 | 365 GRT variant of B6-Bra. |
| B12 | 3. PRODUCT COMPLAINT | Return request — pants, measurements not provided (365-day guarantee variant); offer replacement OR 50% refund + 40% discount | product complaint-within guarantee-template2.md § B12 | 365 GRT variant of B6-Pants. |
| B13 | 3. PRODUCT COMPLAINT | Return request — all products, cannot replace (365-day guarantee variant); offer 50% refund AND 40% discount + free shipping | product complaint-within guarantee-template2.md § B13 | 365 GRT variant of B7. |

---

## C-Codes: Product Complaint — Out of Warranty

> Macro-flow: **3. PRODUCT COMPLAINT** — out-of-warranty path.

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| C1 | 3. PRODUCT COMPLAINT | Out-of-warranty complaint: offer 40% VIP discount + free shipping for next purchase (no replacement/refund) | product complaint-out of guarantee-template.md § C1 | Flow node: "Offer 40% for next purchase (C1)". Template confirms 45-day/14-day warranty window. |
| C2 | 3. PRODUCT COMPLAINT | Replacement still does not fit (post-replacement complaint): no additional compensation; offer 40% VIP discount + free shipping | product complaint-replacement not fit-template.md § C2 | Not listed in PLAN.md code range but present in snapshot. Discovered from template file. Verify node in Plan 03/04. |

---

## D-Codes: Product Complaint — Resolution / Evidence / Refund Processing

> Macro-flow: **3. PRODUCT COMPLAINT** — resolution branch (confirmation and processing nodes).

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| D1 | 3. PRODUCT COMPLAINT | Confirm replacement action / proceed with replacement (first and subsequent replies) | TBD — Plan 02 | Flow node: "confirmation (D1, D2, D5, D3)" and "subsequent replies (D1)". |
| D2 | 3. PRODUCT COMPLAINT | Confirm refund action (full refund path) | TBD — Plan 02 | Referenced in "confirmation (D1, D2, D5, D3)" and "confirmation (D2, D6, D4)". |
| D3 | 3. PRODUCT COMPLAINT | Confirm action after customer chooses option (replacement or refund) | TBD — Plan 02 | Referenced in "confirmation (D3)". |
| D4 | 3. PRODUCT COMPLAINT | Confirm action (return/refund path variant) | TBD — Plan 02 | Referenced in "confirmation (D2, D6, D4)". |
| D5 | 3. PRODUCT COMPLAINT | Confirm action (replacement confirmation variant) | TBD — Plan 02 | Referenced in "confirmation (D1, D2, D5, D3)". |
| D6 | 3. PRODUCT COMPLAINT | Confirm action (70% refund path) | TBD — Plan 02 | Flow node: "agrees to 70% refund?" and "confirmation (D2, D6, D4)". Note: 70% refund referenced in flow; not listed in POLICY-THRESHOLD-INDEX — flagged as additional threshold. |
| D7 | 3. PRODUCT COMPLAINT | Provide return address to customer | TBD — Plan 02 | Flow node: "Provide return address (D7)". |
| D8 | 3. PRODUCT COMPLAINT | Process full refund excluding shipping fee + handling fee | TBD — Plan 02 | Flow node: "Process full refund excluding shipping fee + handling fee". |
| D9 | 3. PRODUCT COMPLAINT | Request evidence from customer (photos of defect + shipping label) | TBD — Plan 02 | Flow node: "Request evidence" decision branch. |

---

## E-Codes: Change Request Actions

> Macro-flow: **2. CHANGE REQUEST**

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| E1 | 2. CHANGE REQUEST | Change shipping address — confirmed and updated successfully | change request-template3.md § E1 | Flow node: "Change address (E1)"; "confirmation (E1, E11)". |
| E2 | 2. CHANGE REQUEST | Change shipping address — DO already TA (in-transit); request forwarded to fulfillment team; cannot guarantee change | change request-template4.md § E2 | Outside 1-hour window; 24–48 hour follow-up promised. |
| E3 | 2. CHANGE REQUEST | Change address — DO already TO (delivered/completed); cannot change; advise customer to contact carrier; offer 40% discount for re-order | change request-template5.md § E3 | Flow node: "Change address: cancel order (E3)". 40% discount offered. |
| E4 | 2. CHANGE REQUEST | Change product variant — can change, same or lower price; confirm size/measurements before processing | change-request-template2.md § E4-Bra / E4-Pants | Two variants (Bra/Pants). Price difference = 0 or credit. |
| E5 | 2. CHANGE REQUEST | Change product variant — can change, higher price; send invoice for price difference; process within 48 hours | change-request-template2.md § E5 | Balance due before order is updated. |
| E6 | 2. CHANGE REQUEST | Change product variant — DO already TA; forwarded to fulfillment team; ask for measurements; 24–48h follow-up | change request-template4.md § E6-Bra / E6-Pants | Outside 1-hour window. Two variants. |
| E7 | 2. CHANGE REQUEST | Change product variant — DO already TO (cannot change); advise return/exchange within 45 days; offer 40% discount | change request-template5.md § E7 | Outside window; references 45-day return window. |
| E8 | 2. CHANGE REQUEST | Confirm contact detail change (email address or phone number updated successfully) | change request-template1.md § E8 | Two sub-variants: email address and phone number. |
| E9 | 2. CHANGE REQUEST | Confirm billing address updated | change request-template1.md § E9 | Billing address only; shipping address unchanged. |
| E10 | 2. CHANGE REQUEST | Cannot add items to existing order (system limitation); offer 20% discount on new order | change-request-template2.md § E10 | Flow note: "Exception: B7 — if request is to add more line items which is impossible, explain system limitation and offer discount". |
| E11 | 2. CHANGE REQUEST | Confirm variant change successfully processed | change-request-template2.md § E11 | Flow node: "confirmation (E1, E11)". |
| E12 | 2. CHANGE REQUEST | Order resumed as-is — unable to contact customer for confirmation | change-request-template2.md § E12 | Flow node: "Change variant: Resume order (E12)". |
| E13 | 2. CHANGE REQUEST | Warning address — address still invalid; request customer to confirm/correct address | change request-template3.md § E13 | Flow node: "Validate address (E13)". Used when system flags address as invalid. |

---

## F-Codes: Cancellation Request Actions

> Macro-flow: **1. CANCELLATION REQUEST**

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| F1 | 1. CANCELLATION REQUEST | [Action node — confirm cancellation eligibility check / initial response] | TBD — Plan 02 | Code referenced in flow but no dedicated node text extracted. Verify in Plan 02/03. |
| F2 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F3 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F4 | 1. CANCELLATION REQUEST | Offer express shipping (as alternative to cancellation) | TBD — Plan 02 | Flow node: "Offer express shipping (F4)". |
| F5 | 1. CANCELLATION REQUEST | Customer agrees to proceed (cancellation confirmed — yes branch) | TBD — Plan 02 | Flow node: "Yes (F5)" in the customer agreement branch. |
| F6 | 1. CANCELLATION REQUEST | Reject cancellation request (DO already shipped or ineligible) | TBD — Plan 02 | Flow node: "Reject request (F6, F8, F11)". |
| F7 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F8 | 1. CANCELLATION REQUEST | Reject cancellation request (grouped with F6, F11) | TBD — Plan 02 | Flow node: "Reject request (F6, F8, F11)". |
| F9 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F10 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F11 | 1. CANCELLATION REQUEST | Reject cancellation request (grouped with F6, F8) | TBD — Plan 02 | Flow node: "Reject request (F6, F8, F11)". |
| F12 | 1. CANCELLATION REQUEST | Cancel DO/PO — process cancellation of delivery order and/or purchase order | TBD — Plan 02 | Flow node: "Cancel DO/PO (F12)". Core cancellation execution action. |
| F13 | 1. CANCELLATION REQUEST | Process upon customer confirmation (final cancellation/action confirmation) | TBD — Plan 02 | Flow node: "Process upon customer's confirmation (F13, F22)" and "confirmation (F13)". |
| F14 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F15 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F16 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F17 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F18 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F19 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F20 | 1. CANCELLATION REQUEST | [Action node — cancellation flow branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| F21 | 1. CANCELLATION REQUEST | Offer partial refund to retain order (customer wants to keep but requests discount) | TBD — Plan 02 | Flow node: "Offer partial refund to retain order (F21)". |
| F22 | 1. CANCELLATION REQUEST | Process upon customer confirmation (paired with F13) | TBD — Plan 02 | Flow node: "Process upon customer's confirmation (F13, F22)". |

---

## G-Codes: Shipping Inquiry Actions

> Macro-flow: **4. SHIPPING INQUIRY** — sub-sections: Types of inquiries, Test contract (4.2), DNR (4.3), OOS (4.4), RTS (4.5), Common scenarios (4.6).

| Code | Macro-flow | Described Action (from diagram/template node text) | Linked Email Template | Notes |
|------|------------|----------------------------------------------------|-----------------------|-------|
| G1 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch (provide tracking update) | TBD — Plan 02 | Flow node: "G1, G2, G4, G5, G6, G7, G8" listed as common scenario options. |
| G2 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch | TBD — Plan 02 | Part of the common scenarios group G1–G8. |
| G3 | 4. SHIPPING INQUIRY | OOS scenario — offer variant change + express shipping (G3.1) OR partial refund up to 20% (G3.2) | TBD — Plan 02 | Flow nodes: "Offer variant change and express shipping (G3.1)"; "Offer partial refund (up to 20%) if customer requests refund (G3.2)". Two sub-codes. |
| G4 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch | TBD — Plan 02 | Part of the common scenarios group G1–G8. |
| G5 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch | TBD — Plan 02 | Part of the common scenarios group G1–G8. |
| G6 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch | TBD — Plan 02 | Part of the common scenarios group G1–G8. |
| G7 | 4. SHIPPING INQUIRY | Shipping inquiry action — common scenarios branch | TBD — Plan 02 | Part of the common scenarios group G1–G8. |
| G8 | 4. SHIPPING INQUIRY | Offer express replacement (shipping time > 35 days or severe delay) | TBD — Plan 02 | Flow node: "Offer express replacement (G8)". |
| G9 | 4. SHIPPING INQUIRY | [Action node — shipping inquiry branch action] | TBD — Plan 02 | Not directly observed in extracted node text. Verify in Plan 02/03. |
| G10 | 4. SHIPPING INQUIRY (DNR) | Guide customer to look for the package — first response for DNR (Delivered Not Received) | templates.md § G10-Delivered not received | Flow node: "Guide customer to look for the package (G10)". Template confirmed. |
| G11 | 4. SHIPPING INQUIRY (DNR) | Offer replacement for DNR — customer still cannot locate package | templates.md § G11 (referenced; full template in templates.md) | Flow node: "Offer replacement (G11)". |
| G12 | 4. SHIPPING INQUIRY (TC) | Inform customer about Test Contract order status / cancel order | TBD — Plan 02 | Flow node: "Inform customer (G12)". Test Contract scenario. |
| G13 | 4. SHIPPING INQUIRY | [Terminal action node — shipping inquiry] | TBD — Plan 02 | Present in SVG (confirmed by plan spec "G13 must be present"). Verify action text in Plan 02/03. |

---

## Coverage Note

The following code families have ambiguous or partially-extracted node text in WorkFlow.svg and require verification in Plan 02/03:

| Code Family | Issue | Action |
|-------------|-------|--------|
| F1–F3, F7, F9–F10, F14–F20 | Node text not explicitly extracted from SVG (binary encoding limited extraction). Codes exist per the F1–F22 range confirmed in PLAN.md. | Verify each code's action text in Plan 02 (Email Templates wiring) or Plan 03 (Confluence). |
| G9, G13 | Node text not explicitly observed in SVG extraction output. Code range G1–G13 confirmed by plan. | Verify in Plan 02/03. |
| B4 | Not observed as a standalone node in WorkFlow.svg OR in any snapshot template file. May be a retired code or subsumed into another range. | Explicitly verify or mark as deprecated in Plan 03/04. |
| B8–B13 | Not listed in the PLAN.md code range (PLAN listed B1–B3, B5–B7, B9–B11) but found in snapshot template files. The 365-day guarantee (365 GRT) variants. | Confirm whether these are additions to the workflow since the PLAN was written, or were always present in WorkFlow.svg but not extracted. Plan 02/03 to resolve. |
| C2 | Not listed in PLAN.md C-code range (only C1 was listed) but found in snapshot template file. | Verify presence as a workflow node in Plan 02/03. |
| D6 | References 70% refund offer — not captured in POLICY-THRESHOLD-INDEX.md. | Flag as additional threshold in Plan 04 conflict detection. |
