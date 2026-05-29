---
phase: 01-knowledge-survey-conflict-inventory
document: SURVEY-confluence.md
role: confluence-sce-source-inventory
status: SURVEYED — sizing root-cause guides only (4 of N domains)
source_url: Confluence SCE root-cause classification space (CS Lead provided 4 sizing guides via PDF export)
last_updated: "2026-05-29"
produced_by: Plan 03 (Task 1 — Confluence SCE sizing guides surveyed after checkpoint resolution)
---

# Confluence SCE Inventory

> **Status: CONFLUENCE SCE SIZING GUIDES SURVEYED.**
>
> The CS Lead provided 4 Confluence SCE root-cause classification guides (PDF exports, D-04)
> covering **sizing-related root causes** across product lines. They are inventoried and their
> root-cause taxonomy is transcribed below.
>
> **Scope limit:** These 4 guides cover the **sizing** root-cause domain only. The SCE root-cause
> classification system almost certainly spans additional non-sizing domains (shipping, billing,
> product defect, etc.) that are NOT covered by these 4 guides — see "Remaining Confluence Gaps".
>
> All taxonomy below is transcribed directly from the PDFs. No content is fabricated. Inferred
> cross-domain categories from non-Confluence sources are clearly labeled as such.

---

## PII Confirmation

All 4 PDFs were reviewed for embedded customer data before commit (T-01-03-PII threat).
**Result: POLICY/TAXONOMY CONTENT ONLY.** The guides contain generic example complaints
("Strap is too short", "Waist too tight"), measurement values, and internal product names
(Daisy bra, Flexcamo, StretchActive, TimelessFlex, TactiShirt, Icedactive, Icy Short). No real
customer names, emails, addresses, phone numbers, or order IDs are present. Safe to commit.

---

## Confluence SCE Inventory

| Source ID | Page Title | Format | Snapshot Path | Pages | Last-Update Cadence | Status | Notes |
|-----------|------------|--------|---------------|-------|---------------------|--------|-------|
| SRC-03a | Sizing-related root causes — Bra sizing | PDF | `snapshots/confluence/CKB-Sizing-related root causes-Bra sizing-290526-112942.pdf` | 5 | TBD — no version date visible on page; export dated 2026-05-29 (290526) | Surveyed | Most detailed guide. Band/cup calculation logic, strap-attribute decision matrix, scenario tables. Footer: "All right reserved by Crossian." |
| SRC-03b | Sizing-related root causes — Pants sizing | PDF | `snapshots/confluence/CKB-Sizing-related root causes-Pants sizing-290526-113032.pdf` | 5 | TBD — export dated 2026-05-29 | Surveyed | Waist/hip/inseam priority rules; measurement-validity guards; scenario tables. Covers Shorts as a sub-case. |
| SRC-03c | Sizing-related root causes — Shirt sizing | PDF | `snapshots/confluence/CKB-Sizing-related root causes-Shirt sizing-290526-113119.pdf` | 2 | TBD — export dated 2026-05-29 | Surveyed | Waist/chest measurement logic; shoulder/sleeve/collar/length treated as waist/chest-related (per SCE team). |
| SRC-03d | Sizing-related root causes — Other Product Lines | PDF | `snapshots/confluence/CKB-Sizing-related root causes-Other Product Lines-290526-113152.pdf` | 1 | TBD — export dated 2026-05-29 | Surveyed | Panties & Shorts → "Same as Pants". Socks → investigate like other lines, use Content/Unfriendly_size_chart. Shorts length feedback → Technical_issue. |

> **Update cadence:** No "last modified" metadata is visible in the page bodies. Export
> timestamps (290526 = 29 May 2026) are in the filenames. Confirm a review/version cadence
> with CS Lead — flag as a governance gap for Plan 04.

---

## Root-cause taxonomy

> Transcribed directly from the 4 SCE sizing guides. These are the **authoritative** SCE
> root-cause labels for sizing complaints (used at step B4 of the agent workflow).

### Root-cause labels (the sizing taxonomy)

| Root-cause Label | Meaning (per guides) | When Selected |
|------------------|----------------------|---------------|
| `Customer-Pick_wrong_size/color` | The customer ordered a size that does not match their measurements; the size chart is fine. | When the customer's complaint **matches** the expected fitting logic for the size difference (correct FFM size ≠ purchased size, and complaint is consistent with that gap). Also when usual/calculated sales size falls outside the chart range / is not mapped to any fulfillment size (Bra NOTE 1). |
| `Content-Unfriendly_size_chart` | The size chart itself is misleading; the customer ordered correctly per the chart but the fit was wrong. | When the customer's complaint **does NOT match** the expected fitting logic (e.g., band tight + cup tight when logic predicts band tight + cup loose). Bra-specific. For Socks, "Content/Unfriendly_size_chart" (note the slash variant in the Other guide). |
| `Product-Technical_issue` | A manufacturing/technical sizing defect — the product does not match its own spec. | Pants/Shirt: when waist/hip/chest measurement falls within the purchased size's range yet the customer reports a fit problem; prioritized over Customer-Pick when waist and hip/chest fall in different size categories. |
| `Undefined-Sizing` | Root cause cannot be determined from the available data. | When the customer provides neither usable measurements nor a usual size; OR when the available measurement options at purchase time cannot resolve the complained attribute (Pants example: hip complaint but only waist+inseam options existed). |

### Rootcause_type (a second axis, distinct from the label above)

| Rootcause_type | Meaning | Source |
|----------------|---------|--------|
| `Technical_issue` | Used as the Rootcause_type (type axis) for Shorts when the root cause is determined from length-related feedback (too short/too long) in non-defective cases. | Pants guide NOTE 6; Other Product Lines guide (Shorts). |

> **Two-axis structure observed:** The guides reference both a **root-cause label**
> (`Customer-Pick_wrong_size/color`, `Content-Unfriendly_size_chart`, `Product-Technical_issue`,
> `Undefined-Sizing`) and a **Rootcause_type** (`Technical_issue`). These appear to be two
> related-but-distinct classification fields. Plan 04 should confirm with SCE whether
> `Product-Technical_issue` (label) and `Technical_issue` (type) are the same concept or two
> fields. Flagged as TAX-01 below.

### Decision logic (the SCE method, summarized — do not re-implement, reference the PDFs)

The guides share a common 4-step method (most explicit in the Bra guide):
1. Identify the customer's correct fulfillment (FFM) size from their measurements/usual size.
2. Compare it to the FFM size the customer purchased.
3. Determine the **expected** fitting issue from the size difference.
4. Compare the customer's actual complaint to the expected logic:
   - Complaint **matches** expected → `Customer-Pick_wrong_size/color`
   - Complaint **does NOT match** expected → `Content-Unfriendly_size_chart`

Pants/Shirt add a `Product-Technical_issue` branch (measurement in-range but bad fit) that is
**prioritized** when waist and hip/chest fall into different size categories.

### Mapping to workflow macro-flows / Level-In categories (Coverage Map backbone)

| Sizing Root-cause | Maps to Level-In | Maps to WorkFlow Macro-Flow / Codes | Notes |
|-------------------|------------------|-------------------------------------|-------|
| All 4 sizing root causes | Complaint (71%) — Return/Replace sub-categories | PRODUCT COMPLAINT (Flow 3): A-codes (defective/wrong/missing) and B-codes (non-defective) | Sizing complaints are a non-defective product-complaint sub-type. `Customer-Pick_wrong_size/color` and `Content-Unfriendly_size_chart` are the SCE root-cause tags applied at B4 *after* the CEE agent has already routed via A/B/C/D codes. |
| `Customer-Pick_wrong_size/color` | Complaint → Change/Return | Relates to H4 (situational size-tag mismatch) and the "Wrong variants" F7/F8 cancellation branches | The H4 situational template ("Mismatch_size_tag/sale_size_label") is the *customer-facing reply*; this root cause is the *internal classification*. |
| `Content-Unfriendly_size_chart` | Complaint | PRODUCT COMPLAINT B-codes | Signals a content/KB defect (the size chart) — feeds back to the content team, not a customer-action. |
| `Product-Technical_issue` | Complaint | PRODUCT COMPLAINT A-codes (defective path) | Technical/manufacturing defect classification. |
| `Undefined-Sizing` | Complaint (pending info) | Maps to "ask for measurements" reply branches (e.g., H4 measurement request) | Terminal "cannot classify yet" state — agent requests more data. |

> **Cross-link to SURVEY.md Coverage Map:** These root causes refine Flow 3 (PRODUCT COMPLAINT)
> in the macro-flow backbone. They are the B4 root-cause tags layered on top of the A/B/C/D
> response codes already mapped in CODE-MAP.md. Plan 04 should add a "SCE root-cause" column to
> the coverage map for the PRODUCT COMPLAINT / sizing sub-category.

---

## Threshold & jargon cross-references

> Per plan Task 1: thresholds found in Confluence are cross-referenced against
> POLICY-THRESHOLD-INDEX.md, and GLOSSARY.md TBDs the guides resolve are recorded here.
> **POLICY-THRESHOLD-INDEX.md and GLOSSARY.md are NOT edited** — findings are staged for Plan 04.

### Thresholds found in the SCE sizing guides

These are **measurement-validity / sizing-calculation thresholds**, a different class from the
policy/temporal thresholds in POLICY-THRESHOLD-INDEX.md (which are time windows and refund caps).
They do not overlap with any existing THR-xx row, so there is **no agreement/contradiction** to
record against the existing index — these are NEW threshold entries for Plan 04 to add.

| Proposed THR ID | Description | Value | Source | Cross-source status vs POLICY-THRESHOLD-INDEX.md |
|-----------------|-------------|-------|--------|---------------------------------------------------|
| THR-S1 | Pants measurement sanity: hip−waist gap upper bound (re-confirm if exceeded) | Hip − Waist > 15″ → ask customer to confirm | Pants guide NOTE 1 | NEW — no existing row; no conflict. Add in Plan 04. |
| THR-S2 | Pants measurement sanity: waist−hip gap upper bound | Waist − Hip > 5″ → ask to confirm | Pants guide NOTE 1 | NEW — no conflict. |
| THR-S3 | Pants measurement sanity: inseam upper bound | Inseam > 36″ → ask to confirm | Pants guide NOTE 1 | NEW — no conflict. |
| THR-S4 | Bra band/cup validity: full-bust minus band-size lower bound | Difference ≥ −5 (else use normal bra size until reliable measurements) | Bra guide NOTE 3 | NEW — no conflict. |
| THR-S5 | Bra band-size formula (even underbust) | Band size = Underbust + 4 | Bra guide scenario 1 / Knowledge 101 | NEW — calculation rule, not a policy cap. |
| THR-S6 | Bra band-size formula (odd underbust) | Band size = Underbust + 5 | Bra guide scenario 1 | NEW — calculation rule. |
| THR-S7 | Decimal-measurement rounding rule | Round up (e.g., 34.5 → 35) | Bra NOTE 2, Pants NOTE 2, Shirt NOTE 1 | NEW — consistent across all 3 guides; no conflict. |

> **No contradiction with the existing 18 THR rows.** The SCE sizing thresholds are
> measurement-calculation guardrails, orthogonal to the cancellation/warranty/refund thresholds
> already indexed. They should be added as a new "Sizing-calculation thresholds (SCE)" section in
> POLICY-THRESHOLD-INDEX.md by Plan 04.

### GLOSSARY.md TBD resolutions from the SCE guides

| Term | Prior Confidence (GLOSSARY.md) | Resolution from SCE Guides | New Confidence |
|------|-------------------------------|----------------------------|----------------|
| SCE | TBD ("Supply Chain / Specialist / Solutions Customer Experience") | The guides are titled "SCE root causes" and the bodies repeatedly cite "confirmed by the SCE team" as the authority on sizing-attribute relationships. The full expansion is still NOT spelled out in these PDFs — only confirmed that SCE is the team that **owns root-cause classification logic**. | Still TBD on the exact words; CONFIRMED on role/ownership. Plan 04 CS-team action item to get the literal expansion. |
| FFM | TBD ("Fulfillment / First Fulfillment") | The guides use "FFM size" extensively as a synonym for **fulfillment size** ("Identify the customer's correct FFM size", "the FFM size purchased"). Confirms FFM = **Fulfillment** (the manufactured size mapped from the sales size). | CONFIRMED = Fulfillment size. Plan 04 to update GLOSSARY.md (currently TBD). |

> **New jargon discovered in the SCE guides (for Plan 04 to add to GLOSSARY.md):**

| Term | Plain-English Meaning | Source | Confidence |
|------|-----------------------|--------|------------|
| Sales size | The size the customer selects/orders on the sellpage (e.g., 36B for a bra, W34/L28 for pants). Mapped to a fulfillment (FFM) size. | All 4 guides | Confirmed |
| Fulfillment size / FFM size | The internal manufactured size that a sales size maps to in a given size chart + product version. Root-cause logic compares purchased FFM size vs calculated FFM size. | All 4 guides | Confirmed |
| Usual size | The size the customer says they normally wear; accepted only if it matches the product sellpage's sizing system. | Bra NOTE 5, Pants NOTE 7 | Confirmed |
| Size chart / product version | A sizing complaint must be resolved within the **same** size chart and product version the customer purchased from (sizes are not portable across charts/versions). | Bra NOTE 4 | Confirmed |
| Knowledge 101: Products | An internal reference doc cited for the detailed band/cup calculation guidelines — a **linked Confluence page not yet provided**. | Bra guide scenario 1 | Confirmed (reference exists) |

---

## Remaining Confluence Gaps

> These 4 guides cover **sizing only**. The SCE root-cause classification system likely spans
> other domains. The following are recorded as still-needed; **no content is fabricated** for them.

### GAP-03-06: SCE root-cause guides for NON-sizing domains — possibly not yet provided

**Priority:** HIGH — sizing is one root-cause domain; B4 root-cause tagging covers all complaint types

**Why critical:** The 4 provided guides all sit under a "Sizing-related root causes" parent.
Step B4 tags root cause for **all** ticket types (shipping, billing/chargeback, product defect,
delivery, etc.), not only sizing. If SCE maintains root-cause guides for those domains, they have
NOT been provided.

**What the CS team must confirm:**
1. Is "Sizing-related root causes" the **only** SCE root-cause guide family, or are there sibling
   guides (e.g., "Shipping-related root causes", "Billing-related root causes", "Product-defect
   root causes")?
2. If sibling guides exist, export them to PDF into `snapshots/confluence/` and notify for survey.
3. If sizing is genuinely the only documented SCE root-cause domain, confirm that explicitly so
   Plan 04 can record the rest as undocumented-tacit-knowledge gaps.

### GAP-03-07: "Knowledge 101: Products" linked page not provided

**Priority:** MEDIUM — referenced dependency

**What:** The Bra guide cites "Knowledge 101: Products" for the detailed band/cup calculation
guidelines. Per D-02 scope (guides + anything they link to), this linked page is in scope but was
NOT exported.

**Action:** CS Lead to export "Knowledge 101: Products" to PDF into `snapshots/confluence/`.

### GAP-03-08: TAX-01 — `Product-Technical_issue` (label) vs `Technical_issue` (Rootcause_type)

**Priority:** MEDIUM — taxonomy clarity

**What:** The guides use `Product-Technical_issue` as a root-cause label and `Technical_issue` as
a Rootcause_type. Whether these are one field or two distinct classification axes is unclear.

**Action:** Plan 04 to confirm the field model with SCE (single label set vs label + type axes).

---

## Newly Discovered Sources (Plan 03 — retained from pre-checkpoint autonomous work)

> During Plan 03 the following sources were found in `snapshots/` (root, not /confluence/) that
> were NOT inventoried in Plans 01 or 02. Retained here for Plan 04 reconciliation.

### SRC-04: Freshdesk Ticket Properties PDF (separate source — NOT a Confluence SCE guide)

| Field | Value |
|-------|-------|
| Title | CKB-[NEW VERSION] Freshdesk Ticket Properties |
| File | `snapshots/CKB-[NEW VERSION] Freshdesk Ticket Properties-290526-082419.pdf` |
| Format | PDF |
| Relevance | Defines Freshdesk ticket custom fields and valid values — governs the Level-In / Level-Out classification properties the AI sets. |
| Status | Present; can now be extracted with poppler (`pdftotext`) — Plan 04 should extract and add as SRC-04 to SURVEY.md. |
| PII Risk | Low — configuration/taxonomy expected. Confirm on extraction. |

### SRC-05: Billing Templates (I-codes I1–I10)

| Field | Value |
|-------|-------|
| File | `snapshots/billing-template.md` |
| Format | Markdown |
| Codes | I1–I4 (PayPal), I5–I7 (Card), I8 (General), I9–I10 (Multiple Charge) |
| Relevance | Maps to Chargeback/Claim Level-In (3% volume). Not in WorkFlow.svg or Plan 02 inventory. |
| Status | Snapshotted; content readable. |
| PII Risk | None — boilerplate only. |

### SRC-06: Situational Templates (H-codes H1–H7)

| Field | Value |
|-------|-------|
| File | `snapshots/situational-template.md` |
| Format | Markdown |
| Codes | H1, H2, H4-Bra/Pants, H5, H6, H7 (H3 absent) |
| Relevance | Cross-cutting: unsubscribe, order-not-found, size-tag mismatch, shipping restrictions. Maps to Inquiry/Other. |
| Status | Snapshotted; content readable. |
| PII Risk | None — boilerplate only. |

> **Note:** H4 (size-tag mismatch) is the customer-facing reply counterpart to the SCE
> `Customer-Pick_wrong_size/color` root cause — a useful cross-link for Plan 04's coverage map.

---

## SURVEY.md Reconciliation Note

> **For Plan 04 / reviewer reconciliation (do not edit SURVEY.md directly):**
>
> **SRC-03 (Confluence SCE Root-Cause Guides) status as of Plan 03:**
> - **Survey: COMPLETE for the sizing domain.** 4 guides (Bra, Pants, Shirt, Other Product Lines)
>   inventoried as SRC-03a–SRC-03d; root-cause taxonomy transcribed.
> - **Pending:** non-sizing SCE root-cause domains (GAP-03-06) and the "Knowledge 101: Products"
>   linked page (GAP-03-07) are not provided.
> - **Snapshot path:** `snapshots/confluence/` (4 PDFs).
>
> **SURVEY.md Source Inventory updates needed (Plan 04):**
> - Update SRC-03 row: snapshot path → `snapshots/confluence/` (4 PDFs); status → surveyed (sizing).
> - Add rows for SRC-04 (Freshdesk Ticket Properties), SRC-05 (billing I-codes), SRC-06 (situational H-codes).
>
> **GLOSSARY.md additions/resolutions needed (Plan 04):**
> - Resolve **FFM** = Fulfillment size (currently TBD) — CONFIRMED by SCE guides.
> - **SCE**: confirmed as the team owning root-cause logic; literal expansion still TBD (CS-team action item).
> - Add new sizing terms: Sales size, Fulfillment/FFM size, Usual size, Size chart/product version.
> - Add ARN (Acquirer Reference Number), 365 GRT (365-day guarantee), Level-Out (`cf_level_out`).
>
> **POLICY-THRESHOLD-INDEX.md additions needed (Plan 04):**
> - Add a new "Sizing-calculation thresholds (SCE)" section: THR-S1–THR-S7 (measurement guards,
>   band-size formulas, rounding rule). No contradiction with existing THR-01–THR-18.
> - From cancellation/billing templates (pre-checkpoint findings): THR-19 (48h retention offer
>   window), THR-20 (7–10d expedited shipping), THR-21 (PayPal refund 3–5 business days),
>   THR-22 (Card refund 5–10 business days).
>
> **CODE-MAP.md additions needed (Plan 04):**
> - Add F23 (aftersale promotion retention) — currently only F1–F22.
> - Add I-codes (I1–I10) and H-codes (H1–H7) families.
> - Add a "SCE root-cause" annotation to PRODUCT COMPLAINT codes linking to the sizing taxonomy.
>
> **Conflict-detection inputs for Plan 04 (D-06):** The Confluence axis of the threshold
> cross-check can now run for the sizing-calculation thresholds. No policy/temporal threshold
> contradictions were found between the SCE sizing guides and POLICY-THRESHOLD-INDEX.md
> (different threshold classes — no overlap).
