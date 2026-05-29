---
phase: 01-knowledge-survey-conflict-inventory
document: SURVEY-confluence.md
role: confluence-sce-source-inventory
status: NOT SURVEYED — access gap (Plan 03)
source_url: TBD — Confluence SCE root-cause classification space (CS Lead to confirm)
last_updated: "2026-05-29"
produced_by: Plan 03 (Task 1 — maximum autonomous work; Confluence PDF exports not provided)
---

# Confluence SCE Inventory

> **Status: CONFLUENCE SCE NOT SURVEYED THIS PHASE**
>
> This file records the Confluence SCE root-cause classification guides as a **source gap**.
> No Confluence PDF exports were provided before Plan 03 execution. Per plan Task 1 action
> ("If the human replied 'confluence unavailable'..."), this file documents the gap explicitly
> and surfaces precise CS-team action items for resolution before Plan 04.
>
> **No SCE root-cause taxonomy is fabricated here.** All taxonomy entries below are sourced
> exclusively from material that IS available: the WorkFlow.svg (SRC-01), the Email Templates
> (SRC-02), and the Freshdesk Ticket Properties PDF (SRC-04, newly discovered this plan).

---

## Confluence SCE Inventory

> No Confluence PDFs were provided. The `snapshots/confluence/` directory does not exist.
> The table below records the expected source entry with its current status.

| Source ID | Page Title | Source URL | Format | Snapshot Path | Last-Update Cadence | Status | Notes |
|-----------|------------|------------|--------|---------------|---------------------|--------|-------|
| SRC-03 | Confluence SCE Root-Cause Classification Guides | TBD — CS Lead to provide the Confluence SCE space URL and page list | PDF (D-04) | `snapshots/confluence/` *(not created — no PDFs provided)* | TBD | **NOT SURVEYED** | Access is read-only viewer via CS Lead only (D-01). Space/page list unknown. No exports provided before Plan 03 execution. |

---

## Root-Cause Taxonomy

> **STATUS: NOT AVAILABLE — Confluence not surveyed.**
>
> The SCE Confluence guides define the root-cause classification categories agents use at
> step B4 (2026-05-28 meeting note). No taxonomy can be transcribed without the PDFs.
>
> The following section records what IS inferrable from non-Confluence sources as a
> cross-reference baseline for when Confluence is eventually surveyed.

### Root-Cause Categories Inferrable from WorkFlow.svg (SRC-01)

The WorkFlow.svg workflow encodes outcome-level logic but does NOT enumerate named SCE
root-cause categories. The following macro-flow terminal states are the closest available
proxy — they represent the operational outcomes that map to root causes at step B4:

| Inferred Root-Cause Domain | WorkFlow Macro-Flow | Terminal Outcome Codes | Notes |
|----------------------------|---------------------|------------------------|-------|
| Cancellation — within window | CANCELLATION REQUEST | F12 (Cancel DO/PO), F13/F22 (resume) | 1-hour eligibility window (THR-01) |
| Cancellation — outside window (TA) | CANCELLATION REQUEST | F5, F17, F18 — SCE-confirm path | Requires SCE coordination via CEE-SCE COLLAB |
| Cancellation — outside window (TO) | CANCELLATION REQUEST | F6, F8, F11, F19, F20 — cannot cancel | DO already delivered |
| Change request — fulfilled | CHANGE REQUEST | E1–E13 | Address, variant, billing, contact details |
| Product complaint — within warranty | PRODUCT COMPLAINT | A, B, D codes (A1–A9, B1–B13, D1–D9) | 45-day/14-day warranty gates (THR-03/THR-04) |
| Product complaint — out of warranty | PRODUCT COMPLAINT | C1 | Aftersale 40% offer (THR-05) |
| Product complaint — replacement not fit | PRODUCT COMPLAINT | C2 | Post-replacement satisfaction issue |
| Shipping — DNR (delivered not received) | SHIPPING INQUIRY | G10, G14, G15 | Carrier marks delivered; customer disputes |
| Shipping — OOS (out of stock) | SHIPPING INQUIRY | G3.1, G3.2 | Variant swap or partial refund |
| Shipping — RTS (return to sender) | SHIPPING INQUIRY | G11, G13 | Package returned to warehouse |
| Shipping — Test contract | SHIPPING INQUIRY | G12 | Internal test order; 30% discount offered |
| Shipping — Late/delayed | SHIPPING INQUIRY | G1–G9 (common scenarios) | >21 day (THR-09), >35 day (THR-10) gates |
| Billing dispute — PayPal | (not in WorkFlow) | I1–I4 | Discovered in billing-template.md (Plan 03) |
| Billing dispute — Card | (not in WorkFlow) | I5–I7 | Discovered in billing-template.md (Plan 03) |
| Billing — Multiple charge | (not in WorkFlow) | I8–I10 | Discovered in billing-template.md (Plan 03) |
| Situational / miscellaneous | (not in WorkFlow) | H1–H7 | Discovered in situational-template.md (Plan 03) |

> **IMPORTANT:** These are inferred outcome domains, NOT the authoritative SCE root-cause
> classification labels. The actual SCE Confluence guide may use different naming, grouping,
> or a different taxonomy hierarchy. The table above must be reconciled against the Confluence
> taxonomy once it is surveyed. Do NOT use this table as the ground truth for root-cause tags.

---

## Threshold & Jargon Cross-References

> **STATUS: PARTIAL — based on WorkFlow.svg and Email Templates only; Confluence pending.**
>
> Per plan Task 1, this section records any threshold or GLOSSARY.md TBD that Confluence
> would resolve. Since Confluence is not available, the section records:
> (a) which thresholds most need Confluence cross-checking, and
> (b) GLOSSARY.md TBDs that Confluence is the designated resolver for.

### Thresholds Most Needing Confluence Cross-Check (for Plan 04)

| Threshold ID | Value (WorkFlow.svg) | Why Confluence Cross-Check Is Critical |
|--------------|----------------------|----------------------------------------|
| THR-01 | Cancellation within 1 hour | F5/F17/F18/F8 templates confirm the 1-hour rule in agent-facing language; Confluence may carry a different or more nuanced operational definition for SCE-side root-cause tagging |
| THR-02 | Change request within 1 hour | F19/F20 templates confirm 1-hour language ("one-hour window"); confirm whether Confluence aligns |
| THR-03 / THR-04 | Warranty 45 days from purchase OR 14 days from delivery | Templates C1 (out-of-guarantee), F19, F20 all cite "45 days of purchase date" only; the 14-day internal threshold (THR-04) does not appear in agent-facing templates — Confluence may clarify which threshold SCE uses for root-cause classification |
| THR-05 | 40% aftersale promotion | F8 (cannot cancel — wrong variants) template cites a 40% discount link, consistent with THR-05; Confluence may define when this offer is SCE-authorized vs CEE-discretionary |
| THR-06 | 20% partial refund / discount cap | Multiple F-code templates (F1–F3, F7, F9, F10, F11, F13–F16, F17–F21) universally use "20% refund" as the standard retention offer; Confluence may carry the authoritative policy rule governing when 20% is the max vs when higher is permitted |

### GLOSSARY.md TBDs That Confluence Is the Primary Resolver

| Term | Current Confidence | Why Confluence Should Resolve It |
|------|--------------------|----------------------------------|
| CEE | TBD | SCE Confluence guides are produced by or for SCE; their cover page / header likely states both team names in full |
| SCE | TBD | Same as above — the full expansion of SCE is likely stated in the guide title or introduction |
| MOQ | TBD | SCE request type "Include DO/PO in next arrival batch (MOQ)" — SCE guides likely define this operational term |
| FFM | TBD | "Provide tentative FFM date" (OOS scenario) — SCE may define FFM in the context of fulfillment scheduling |

### New Jargon Discovered from Additional Templates (Plan 03)

The following terms were discovered from template files added since Plan 02 (billing-template.md,
situational-template.md, cancellation templates). These are NOT in GLOSSARY.md yet. They are
recorded here for Plan 04 to add to GLOSSARY.md.

| Term | Plain-English Meaning | Source | Confidence | Notes |
|------|-----------------------|--------|------------|-------|
| ARN | Acquirer Reference Number — a unique transaction identifier used by card networks to trace refunds | `snapshots/billing-template.md` I7 | Confirmed | Template: "The ARN (Acquirer Reference Number): [CODE]. You can give this code to your payment provider" |
| 365 GRT | 365-day guarantee — an extended warranty/guarantee period for select products | `snapshots/product complaint-within guarantee-template2.md` (B8–B13) | Confirmed | Already in CODE-MAP.md; not yet in GLOSSARY.md. Flag for Plan 04. |
| WOC | Waiting on Customer (Freshdesk tag/status) | WorkFlow.svg (already in GLOSSARY.md) | Confirmed | Present in GLOSSARY.md; listed here for completeness as it also appears in billing flows |
| PayPal dispute / Case status | Freshdesk/PayPal dispute state values: "Need seller's response", "Need buyer's response", "Under review" | `snapshots/billing-template.md` I1–I3 | Confirmed | These are PayPal Resolution Center case states; agents reference them in I-code templates |
| Level-out | Freshdesk ticket property (outbound classification level) | `snapshots/billing-template.md` I5: `{{ticket.cf_level_out}}` | TBD | Template variable `cf_level_out` suggests a "Level-Out" custom field on the Freshdesk ticket, parallel to Level-In. Needs definition. |

---

## Newly Discovered Sources (Plan 03)

> During Plan 03 execution, material present in `snapshots/` that was NOT inventoried in
> Plans 01 or 02 was identified. These sources are recorded here for Plan 04 reconciliation.

### SRC-04: Freshdesk Ticket Properties PDF

| Field | Value |
|-------|-------|
| Source ID | SRC-04 (proposed) |
| Title | CKB-[NEW VERSION] Freshdesk Ticket Properties |
| File | `snapshots/CKB-[NEW VERSION] Freshdesk Ticket Properties-290526-082419.pdf` |
| Format | PDF |
| Date Stamped | 2026-05-29 (filename: 290526) |
| Relevance | Defines Freshdesk ticket custom fields and their valid values — directly governs the Level-In classification property that the AI classifier must set. Also likely defines Level-Out (`cf_level_out`), product-line tags, and other structured fields visible in the ticket property panel. |
| Status | Present in snapshots/ but NOT yet readable (requires `poppler` / `pdftotext` to extract text). PDF is binary-compressed. Cannot be surveyed until tooling is available or the file is converted. |
| PII Risk | Low — expected to be configuration/taxonomy documentation (field names, valid values), not customer data. Confirm before committing. |
| Action | Install `brew install poppler` and run `pdftotext` to extract content, OR convert to Markdown manually. Add SRC-04 to SURVEY.md Source Inventory in Plan 04. |

**What IS visible (from Freshdesk ticket PNG at `snapshots/Ticket-ContactForm-Product Complaint.png`):**

The ticket UI screenshot shows the following ticket property panel fields (right side panel):
- Ticket Status dropdown (visible)
- Ticket Type
- Priority
- Agent / Group assignment panel
- Custom properties panel (visible but small — field labels partially readable)
- Tags section
- Associated Tickets / Linked Tickets panel

The custom fields panel is consistent with Level-In classification being a custom Freshdesk
field. The exact field names and valid value enumerations are in the PDF (SRC-04) which
cannot currently be extracted.

### SRC-05: Billing Templates (I-codes)

| Field | Value |
|-------|-------|
| Source ID | SRC-05 (proposed) |
| Title | Billing Templates |
| File | `snapshots/billing-template.md` |
| Format | Markdown |
| Codes Covered | I1–I10 (10 templates: PayPal I1–I4, Card I5–I7, General I8, Multiple Charge I9–I10) |
| Relevance | Billing/chargeback/dispute resolution templates — maps to the Chargeback/Claim Level-In category (3% of volume per meeting note). NOT present in WorkFlow.svg or Plan 02 Email Templates inventory. Newly discovered. |
| Status | Snapshotted — content present and readable |
| PII Risk | None — template boilerplate only; no customer data embedded |

### SRC-06: Situational Templates (H-codes)

| Field | Value |
|-------|-------|
| Source ID | SRC-06 (proposed) |
| Title | Situational / Miscellaneous Templates |
| File | `snapshots/situational-template.md` |
| Format | Markdown |
| Codes Covered | H1 (Unsubscribe), H2 (Order not found), H4-Bra/Pants (Size tag mismatch), H5 (No return label), H6 (Order details — unsubscribed customer), H7 (Shipping restrictions) |
| Relevance | Handles cross-cutting scenarios not tied to a single macro-flow: unsubscribe requests, order lookup failures, size-label discrepancies, shipping-region restrictions. Maps primarily to Inquiry and Other Level-In categories. NOT in WorkFlow.svg or Plan 02 inventory. |
| Status | Snapshotted — content present and readable. Note: H3 is not present in the file — gap or intentional omission. |
| PII Risk | None — template boilerplate only |

---

## Source Gap — High Priority Action Items

> **This section is the primary output for Plan 04 when Confluence remains unavailable.**
> These items must be resolved before the AI classification system can correctly tag root
> causes at step B4.

### GAP-03-01: Confluence SCE Root-Cause Classification Guides — NOT SURVEYED

**Priority:** HIGH — blocks root-cause taxonomy foundation

**Why critical:**
- Step B4 of the agent workflow ("tag root-cause per SCE Confluence guide") is the authoritative
  source for root-cause classification labels.
- The AI classification model must learn these labels to replicate step B4 behavior.
- Without the Confluence taxonomy, the AI has no authoritative label set for root-cause tags.
- Plan 04's LLM-assisted conflict detection (D-06) cannot run the Confluence axis of the
  threshold cross-check without this source.

**What the CS team / CS Lead must do:**
1. Identify the Confluence SCE space name and confirm the root page URL(s) for the
   root-cause classification guides.
2. Walk every guide page in the Confluence UI, following all linked pages (D-02 scope).
3. Export each page to PDF (D-04) and place files under:
   `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/confluence/`
   (create the folder if it does not exist).
4. Confirm that no PII (customer names, emails, order IDs) is embedded in the exported PDFs;
   redact or exclude example-laden pages if needed (T-01-03-PII threat).
5. Reply "confluence provided" and list the PDF files added and the source page URLs.

**If Confluence cannot be granted this phase:**
- Reply "confluence unavailable" and provide the reason.
- Plan 04 will record the SCE root-cause taxonomy as a knowledge gap and surface it as a
  CS-team-owned action item. The classification model will be trained with incomplete root-cause
  labels until this gap is closed.

### GAP-03-02: SRC-04 Freshdesk Ticket Properties PDF — Not Yet Extracted

**Priority:** HIGH — governs ticket field names the AI classifier must set

**Why critical:**
- The AI must set the correct Freshdesk ticket properties (Level-In, product line, feedback
  issue, etc.) when classifying incoming tickets. The PDF defines the valid values for each
  custom field.
- `cf_level_out` discovered in billing templates (I5) suggests a Level-Out field not yet
  defined anywhere in the surveyed material.

**What must be done:**
1. Install poppler: `brew install poppler`
2. Run: `pdftotext "snapshots/CKB-[NEW VERSION] Freshdesk Ticket Properties-290526-082419.pdf" > snapshots/freshdesk-ticket-properties.md`
3. Add SRC-04 to SURVEY.md Source Inventory.
4. Extract all custom field names and their valid value enumerations into a structured table.
5. Resolve `cf_level_out` definition and add Level-Out taxonomy to GLOSSARY.md and CODE-MAP.md.

### GAP-03-03: H3 Template Missing

**Priority:** LOW — single template gap

**What:** The situational-template.md file contains H1, H2, H4–H7 but no H3. Either H3 does
not exist, was removed, or was not exported.

**Action:** Confirm with CS Lead whether H3 exists and if so export it to Markdown.

### GAP-03-04: Code Families I and H Not in CODE-MAP.md or SURVEY.md

**Priority:** MEDIUM — coverage map is incomplete without these families

**What:** I-codes (I1–I10, billing) and H-codes (H1–H7, situational) are present in new
template files but are not yet in:
- CODE-MAP.md (workflow code → described action)
- CODE-MAP-templates.md (code → template file)
- SURVEY.md Source Inventory (no SRC-05/SRC-06 rows)
- SURVEY-email-templates.md (no rows for billing or situational pages)

**Action:** Plan 04 should add I-codes and H-codes to all relevant mapping artifacts.

### GAP-03-05: F23 Code Not in CODE-MAP.md

**Priority:** MEDIUM — F-code range incomplete

**What:** `cancellation request-template1.md` contains code F23 (Aftersale promotion
retention offer). CODE-MAP.md covers F1–F22 only. F23 is missing.

**Action:** Plan 04 to add F23 to CODE-MAP.md with action: "Offer 20% refund / shipping fee
waiver as retention alternative to cancellation when customer questions aftersale price."

---

## SURVEY.md Reconciliation Note

> **For Plan 04 / reviewer reconciliation (do not edit SURVEY.md directly):**
>
> SRC-03 (Confluence SCE Root-Cause Guides) status as of Plan 03:
> - **Survey: NOT COMPLETED** — no PDF exports provided; access gap persists.
> - **Action:** See GAP-03-01 above.
>
> Newly discovered sources (SRC-04, SRC-05, SRC-06) are inventoried in this file.
> Plan 04 should add rows for SRC-04, SRC-05, SRC-06 to SURVEY.md Source Inventory.
>
> GLOSSARY.md additions needed (Plan 04):
> - ARN (Acquirer Reference Number) — confirmed, source billing-template.md
> - 365 GRT (365-day guarantee) — confirmed, source within-guarantee-template2.md
> - Level-Out / cf_level_out — TBD definition; source billing-template.md I5
>
> POLICY-THRESHOLD-INDEX.md cross-check status (all entries remain "Whimsical only"):
> - Confluence cross-check column cannot be filled until GAP-03-01 is resolved.
> - Email Templates partial cross-checks from Plan 02 (THR-17 already recorded) remain the
>   only non-Whimsical confirmations. No new threshold contradictions discovered in Plan 03.
>
> New threshold candidate from cancellation templates (for Plan 04 to add to POLICY-THRESHOLD-INDEX.md):
> - **F3/F4/F7/F18 48-hour offer window:** Multiple cancellation templates state the
>   retention offer (20% refund) is "available for the next 48 hours." This is a
>   time-bounded operational rule not previously captured in POLICY-THRESHOLD-INDEX.md.
>   Add as THR-19: "Retention offer validity window — 48 hours."
> - **F9 48-hour hold:** F9 template: "we will place this order on hold for 48 hours."
>   Same 48-hour window — supports THR-19.
> - **F4 expedited shipping time:** "reduce your delivery time to just 7–10 days" — new
>   threshold not in POLICY-THRESHOLD-INDEX.md. Add as THR-20: "Expedited shipping ETA
>   offered on cancellation request — 7–10 days."
> - **I4/I6 refund processing time (PayPal):** "allow 3–5 business days." Add as THR-21.
> - **I6 refund processing time (Card):** "bank may take 5–10 business days." Add as THR-22.
> - **I3/I5 chargeback discount:** 50% discount link offered when PayPal/card dispute is
>   under review — same 50% level as THR-07/THR-08 but in billing context. Note for Plan 04.
