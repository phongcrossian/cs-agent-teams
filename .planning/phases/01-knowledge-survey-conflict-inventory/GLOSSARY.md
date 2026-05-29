---
phase: 01-knowledge-survey-conflict-inventory
document: GLOSSARY.md
role: internal-jargon-reference
status: seeded-by-plan-01
source: snapshots/WorkFlow.svg + 2026-05-28-meeting-note.md
last_updated: "2026-05-29"
---

# Internal Jargon Glossary

> **How to use:** Each term has a Source (workflow macro-flow / node label or meeting note) and
> a Confidence level. **Confirmed** = the diagram or meeting note explicitly defines or uses the
> term in context. **TBD** = meaning inferred from context; must be resolved via Confluence
> (Plan 03) or CS-team action item (Plan 04).  
> Append new terms as later plans surface them; do not rename existing rows.

---

## Acronyms & Terms

| Term | Plain-English Meaning | Source | Confidence | Notes |
|------|-----------------------|--------|------------|-------|
| CEE | Customer Email Experience team — the email CS agent team that handles Freshdesk email tickets | WorkFlow.svg section headers (flows 1–4); meeting note (team name) | TBD | Name is strongly implied by context. Confirm official full form with CS Lead (Plan 04 action item). |
| SCE | Supply Chain / Specialist/Solutions Customer Experience — internal ops team that handles product status, DO/PO management, and root-cause classification guidance | WorkFlow.svg section 6 "CEE-SCE COLLAB"; meeting note B4 (SCE Confluence guides) | TBD | Two plausible expansions. SCE provides root-cause classification guides (Confluence, Plan 03). Confirm full name with CS Lead. |
| DO | Delivery Order — an individual shipment/fulfillment record linked to a customer order | WorkFlow.svg flows 1 (Cancel DO/PO), 2, 6 "Postpone DO/PO in TA status"; 6.4 request type list | Confirmed | Diagram explicitly references "Cancel DO/PO", "Postpone DO(s)", "DO already TO?", "DO Status: New/Pending/…". |
| PO | Purchase Order — the customer's original purchase record; parent of one or more DOs | WorkFlow.svg flows 1 ("Cancel DO/PO"), 6 ("Postpone DO/PO in TA status") | Confirmed | Paired with DO throughout the diagram. "Offer 20% refund for duplicated DO/PO" and "PO value?" confirm usage. |
| TA | In-Transit / en-route shipment status — the DO status meaning the shipment has been handed to the carrier and is in transit | WorkFlow.svg flow 2 "DO(s) TA already?"; flow 1 "already TA?"; 6.4 "Postpone DO/PO in TA status" | Confirmed | Used as a status gate ("already TA?") and in SCE request type "Postpone DO/PO in TA status". Full word form not spelled out in diagram. |
| TO | Delivered / completed shipment status — the DO status meaning delivery has been completed (order is "taken out") | WorkFlow.svg flows 1 "DO already TO?", 4 "already TO?" | Confirmed | Used as a decision gate in cancellation and shipping flows. |
| WOC | Waiting on Customer — a Freshdesk ticket status/tag indicating the agent is awaiting a customer reply | WorkFlow.svg flow 1 "Set WOC", "Set WOC+Postpone DO(s) if not pending" | Confirmed | Explicitly set as a ticket property in multiple flow branches. |
| WNF | Will Not Follow (up) — a Freshdesk ticket status/tag indicating the ticket is closed without further action (e.g., customer did not respond) | WorkFlow.svg flow 1 "Set WNF"; flow 4 "Set Resolved/WNF" | Confirmed | Used as terminal state in no-reply branches. |
| RTS | Returned to Sender — a shipment status where the carrier returned the package to the sender/warehouse instead of completing delivery | WorkFlow.svg section 4.5 "RTS"; table of content "SHIPPING INQUIRIES" sub-section | Confirmed | Diagram section 4.5 is explicitly titled "RTS" and describes DO(s) returned to sender flow. |
| OOS | Out of Stock — a product/variant status indicating the item is currently unavailable for fulfillment | WorkFlow.svg section 4.4 "OOS"; flow "DO(s) under Out of stock" | Confirmed | Section 4.4 explicitly labeled "OOS" and describes out-of-stock order scenarios. |
| DNR | Delivered Not Received — a customer complaint type where the carrier marks delivery as complete but the customer claims not to have received the package | WorkFlow.svg section 4.3 "DNR" and node "DO(s) delivered not received"; templates.md header "Delivered not received (DNR)" | Confirmed | Section 4.3 of shipping inquiry flow and template file both confirm this meaning. |
| TC | Test Contract — an internal order classification marking an order as a test/non-real transaction (not a genuine customer order) | WorkFlow.svg section 4.2 "TEST CONTRACT"; node "DO(s) Test contract / TC tag AND DO Status: New/Pending/Canceled" | Confirmed | Diagram section 4.2 explicitly describes Test Contract handling. |
| OB | Outbound call — a proactive call initiated by the call-agent team to a customer | WorkFlow.svg flow 5 "Make OB?", "Need OB / No need OB", 5.3 "EMAIL-CALL COLLAB-FOR CALL AGENT" | Confirmed | Used as a decision gate: whether to make an outbound call. |
| MOQ | Minimum Order Quantity — a threshold for batch production/fulfilment in the supply chain | WorkFlow.svg section 6.4 request type "Include DO/PO in next arrival batch (MOQ)" | TBD | Appears in SCE request type context. Supply-chain meaning is standard; confirm operational usage with SCE team (Plan 04 action item). |
| FFM | Fulfillment / First Fulfillment — likely refers to the fulfillment date or first shipment milestone | WorkFlow.svg section 4.4 OOS flow "Provide tentative FFM date" | TBD | Only occurrence is "Provide tentative FFM date" in the OOS scenario. Exact expansion not stated. Resolve via Confluence (Plan 03) or CS-team action item (Plan 04). |
| WOC (tag) | See WOC above — also used as a Freshdesk ticket tag (distinct from status) | WorkFlow.svg flow 1 | Confirmed | Same as WOC row above; listed separately to flag both ticket-status and tag usages. |

---

## DO Product/Status States

> These are the valid status values for a Delivery Order (DO) as defined in the WorkFlow.svg
> CEE-SCE COLLAB section (6.4 "Product status and CEE action").

| Status | Plain-English Meaning | Source | Confidence | Notes |
|--------|-----------------------|--------|------------|-------|
| New | DO has been created but not yet processed | WorkFlow.svg section 6.4 "Product status" node | Confirmed | Listed as first state in the status sequence. |
| Active | DO is being actively processed / product is available | WorkFlow.svg section 6.4 | Confirmed | "Yes (if inventory > 0)" maps to Active state for replacement. |
| In-active | DO/product is inactive — no longer being processed or available | WorkFlow.svg section 6.4 | Confirmed | Listed in status enumeration. |
| Clear-stock | Product is in clearance / end-of-life inventory mode | WorkFlow.svg section 6.4 | Confirmed | Listed as a distinct status with its own handling note. |
| Write-off | Product/DO has been financially written off but not yet physically disposed | WorkFlow.svg section 6.4 | Confirmed | Distinct from Written-off. |
| Written-off | Product/DO has been fully written off (completed write-off process) | WorkFlow.svg section 6.4 | Confirmed | Final written-off state. |
| Disposed | Product/DO has been physically disposed of | WorkFlow.svg section 6.4 "Disposed" | Confirmed | Listed as a terminal status. |
| Active/Disposed | DO is in a mixed Active+Disposed state | WorkFlow.svg section 6.4 | TBD | Listed as a combined status; operational meaning unclear. Resolve via SCE team (Plan 04 action item). |
| Pending | DO has been placed but not yet in active processing (used in cancellation eligibility checks) | WorkFlow.svg flow 1 "DO Status: New/Pending/Canceled" | Confirmed | Appears in Test Contract section as one of the eligible statuses for cancellation. |
| Canceled | DO has been canceled | WorkFlow.svg flow 1 "DO Status: New/Pending/Canceled" | Confirmed | Terminal state for canceled orders. |
