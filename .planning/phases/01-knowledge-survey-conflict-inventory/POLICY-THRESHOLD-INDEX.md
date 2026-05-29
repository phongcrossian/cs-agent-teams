---
phase: 01-knowledge-survey-conflict-inventory
document: POLICY-THRESHOLD-INDEX.md
role: policy-threshold-canonical-reference
status: seeded-by-plan-01
source: snapshots/WorkFlow.svg
last_updated: "2026-05-29"
---

# Policy Threshold Index

> **Purpose (D-06):** Every numeric and temporal policy threshold embedded in the knowledge
> sources, captured with source citation so conflict detection (Plan 04) can run the
> cross-source axis explicitly: WorkFlow.svg ↔ Confluence ↔ Email Templates.
>
> **Cross-source status column:** All entries seeded from WorkFlow.svg only.
> Plan 04 fills the Confluence and Email Template columns.
> "Whimsical only — pending cross-check (Plan 04)" means the value has not yet been
> validated against other sources.

---

## Threshold Table

| Threshold ID | Description | Value | Source (WorkFlow macro-flow + node text) | Cross-Source Status |
|--------------|-------------|-------|------------------------------------------|---------------------|
| THR-01 | Cancellation eligibility window | Within **1 hour** after order placement | Flow 1 (CANCELLATION REQUEST): "A customer is eligible for cancellation if they submit their request within 1 hour after placing the order." | Whimsical only — pending cross-check (Plan 04) |
| THR-02 | Change request eligibility window | Within **1 hour** after order placement | Flow 2 (CHANGE REQUEST): "A customer is eligible for a change if they make their request within 1 hour after placing an order" | Whimsical only — pending cross-check (Plan 04) |
| THR-03 | Warranty period — from purchase date | Within **45 days** of purchase date | Flow 3 (PRODUCT COMPLAINT) WARRANTY section: "The request is made within 45 days from the purchase date" | Whimsical only — pending cross-check (Plan 04) |
| THR-04 | Warranty period — internal policy (from delivery date) | Within **14 days** from delivery date | Flow 3 (PRODUCT COMPLAINT) WARRANTY section: "Internal policy: within 14 days from the delivery date" | Whimsical only — pending cross-check (Plan 04). NOTE: THR-03 and THR-04 are two different thresholds for the same warranty concept — potential internal conflict to flag in Plan 04. |
| THR-05 | Aftersale promotion discount | **40% discount + free shipping** | Flow 3 (PRODUCT COMPLAINT): "Offer 40% for next purchase (C1)"; C1 template confirms "40% VIP discount … along with free shipping on all items and no limits" | Whimsical only — pending cross-check (Plan 04) |
| THR-06 | Partial refund / discount cap (general) | **Up to 20%** | Flow 1 (CANCELLATION REQUEST): "Offer up to 20% refund of higher-priced order"; "Offer 20% refund for entire PO"; "Requested discount ≤20%" node. Flow 4 (SHIPPING INQUIRY) OOS section: "Offer partial refund (up to 20%) if customer requests refund" | Whimsical only — pending cross-check (Plan 04) |
| THR-07 | 50% refund offer (product complaint non-warranty path) | **50% refund** | Flow 3 (PRODUCT COMPLAINT): "Offer 50% refund AND 40% discount + free shipping (B7)"; "Offer 50% refund OR 40% discount + free shipping (B3)"; "Offered 50% refund before?" decision node | Whimsical only — pending cross-check (Plan 04) |
| THR-08 | Discount cap in shipping common scenarios | **Up to 50%** | Flow 4 (SHIPPING INQUIRY) section 4.6 COMMON SCENARIOS: "Provide tracking update and offer discount (up to 50%)/partial refund" | Whimsical only — pending cross-check (Plan 04) |
| THR-09 | Shipping time threshold — late shipment flag | Shipping time **> 21 days** | Flow 4 (SHIPPING INQUIRY) section 4.6: "Shipping time > 21 days" | Whimsical only — pending cross-check (Plan 04) |
| THR-10 | Shipping time threshold — severely late flag | Shipping time **> 35 days** | Flow 4 (SHIPPING INQUIRY) section 4.6: "Shipping time > 35 days" | Whimsical only — pending cross-check (Plan 04) |
| THR-11 | Last tracking update threshold — no update flag | Last tracking update **>= 15 days** | Flow 4 (SHIPPING INQUIRY) section 4.6: "Last tracking update [>=] 15 days" (extracted from node text) | Whimsical only — pending cross-check (Plan 04) |
| THR-12 | Refund promise deadline (DNR/shipping delay) | Full refund promised on **day 40** | Flow 4 (SHIPPING INQUIRY) section 4.6: "Promise a full refund on day 40"; section 4.3 DNR: "Promise refund on day 40" | Whimsical only — pending cross-check (Plan 04) |
| THR-13 | Operational rule — private notes | **1 note per request only** | Flow 6 (CEE-SCE COLLAB) section 6.3: "1 note per request only" | Whimsical only — pending cross-check (Plan 04) |
| THR-14 | SCE availability window | **11AM – 4PM** | Flow 6 (CEE-SCE COLLAB) section 6.3: "SCE check on: 11AM - 4PM" | Whimsical only — pending cross-check (Plan 04) |
| THR-15 | Express replacement offer threshold (shipping delay) | Offered when shipping time > 35 days or no tracking update | Flow 4 (SHIPPING INQUIRY) section 4.6: "Offer an immediate express replacement" as one option when shipping time > 35 days | Whimsical only — pending cross-check (Plan 04) |
| THR-16 | Duplicate order refund cap | **20%** refund for duplicated DO/PO | Flow 1 (CANCELLATION REQUEST): "Offer 20% refund for duplicated DO/PO" | Whimsical only — pending cross-check (Plan 04) |
| THR-17 | Warranty: returns/exchanges acceptance window (from C1 template) | Within **45 days** of purchase OR **14 days** from delivery | snapshots/product complaint-out of guarantee-template.md (C1 template): "returns or exchanges are accepted within 45 days of purchase or 14 days from delivery" | Email Templates + Whimsical — values match THR-03/THR-04; confirmed consistent in these two sources. Still pending Confluence cross-check (Plan 04). |
| THR-18 | Collab wait time before escalation (EMAIL-CALL) | **2 days** waiting on call team | Flow 5 (EMAIL-CALL COLLAB) section 5.1: "2 days / Waiting on Call" timeout branch | Whimsical only — pending cross-check (Plan 04) |

---

## Potential Internal Conflicts (flagged for Plan 04)

| Conflict ID | Thresholds Involved | Description |
|-------------|---------------------|-------------|
| IC-01 | THR-03 vs THR-04 | Warranty period stated as "45 days from purchase date" (customer-facing) AND "14 days from delivery date" (internal policy). These are different calculations; may conflict in edge cases. Needs explicit reconciliation. |
| IC-02 | THR-06 vs THR-08 | Partial refund cap is "up to 20%" in cancellation and OOS scenarios, but "up to 50% discount" appears in shipping common scenarios. Scope of each cap needs clarification. |
