---
phase: 01-knowledge-survey-conflict-inventory
document: CONFLICT-INVENTORY.md
role: conflict-inventory-findings
status: complete
produced_by: Plan 04 (Task 1)
last_updated: "2026-05-29"
method: "LLM-assisted pairwise comparison of policy claims across sources (D-06) + manual triage by reviewer. Triage decisions are the reviewer's responsibility — this document surfaces findings, it does not make final rulings."
sources_compared:
  - "WorkFlow.svg (Whimsical CEE workspace) — SRC-01"
  - "Email Templates (Google Sites, Markdown snapshots) — SRC-02"
  - "Confluence SCE sizing root-cause guides (PDF, 4 guides) — SRC-03"
---

# Conflict Inventory

> **Method note (D-06):** This inventory was produced by LLM-assisted pairwise comparison of
> policy claims extracted from the three surveyed KB sources (WorkFlow.svg, Email Templates,
> Confluence SCE guides). Each pair of claims covering the same policy rule was compared for
> agreement, contradiction, or source-silence. Findings are severity-tagged:
> - **HIGH** — contradiction on a numeric/monetary/temporal threshold rule (direct customer-impact)
> - **MEDIUM** — inconsistency or ambiguity that may produce incorrect agent behaviour in edge cases
> - **LOW** — cadence/governance gap, minor terminology inconsistency, or informational gap
>
> **Triage responsibility:** This document surfaces findings for reviewer decision. The CS Lead
> or policy owner must triage each HIGH/MEDIUM finding and make the authoritative ruling.
> Phase 1 does not author resolutions — it surfaces them (D-07).

---

## Threshold Cross-Source Axis

> **MANDATORY per D-06.** Every numeric/temporal policy threshold from POLICY-THRESHOLD-INDEX.md
> compared across the three KB sources. "source-silent" means the source was surveyed but does
> not mention this threshold. "Confluence not surveyed for this topic" means Confluence was only
> partially surveyed (sizing domain only — GAP-03-06); the source may exist but was not provided.

| Threshold ID | Description | Whimsical (WorkFlow.svg) value | Confluence value | Email Template value | Agreement | Finding |
|---|---|---|---|---|---|---|
| THR-01 | Cancellation eligibility window | Within **1 hour** of order placement (Flow 1: "eligible for cancellation if they submit their request within 1 hour after placing the order") | Confluence not surveyed for this topic (sizing guides only) | **1 hour** restated in F5, F17, F18 (TA-status F-codes: "already been in transit … within 1 hour") | Whimsical ↔ Email Templates: **agree** | Consistent across two sources. Confluence absence is a gap, not a contradiction. |
| THR-02 | Change request eligibility window | Within **1 hour** of order placement (Flow 2: "eligible for a change if they make their request within 1 hour after placing an order") | Confluence not surveyed for this topic | **1 hour** restated in TA-status F-codes | Whimsical ↔ Email Templates: **agree** | Consistent. Confluence gap noted. |
| THR-03 | Warranty period — customer-facing (from purchase date) | Within **45 days** of purchase date (Flow 3 WARRANTY section) | Confluence not surveyed for this topic | **45 days of purchase** stated in C1 template (out-of-guarantee) and TO-status F-codes (F6, F8, F11) | Whimsical ↔ Email Templates: **agree** | Consistent across two sources. See IC-01 for the dual-threshold conflict with THR-04. |
| THR-04 | Warranty period — internal policy (from delivery date) | Within **14 days** from delivery date (Flow 3 WARRANTY section, labeled "Internal policy") | Confluence not surveyed for this topic | **14 days from delivery** stated in C1 template alongside 45-day window: "returns or exchanges are accepted within 45 days of purchase or 14 days from delivery" | Whimsical ↔ Email Templates: **agree** (both state both thresholds) | Both sources carry BOTH thresholds simultaneously — this is the IC-01 internal conflict (two different warranty calculations co-existing). Needs policy ruling on which governs. **Severity: HIGH** |
| THR-05 | Aftersale promotion discount | **40% discount + free shipping** (Flow 3: "Offer 40% for next purchase (C1)"; C1 confirmed) | Confluence not surveyed for this topic | **40% VIP discount + free shipping + no limits** confirmed in C1 template; G6 also offers "40% discount as goodwill" | Whimsical ↔ Email Templates: **agree** | Consistent. 40% is the standard aftersale promotion rate. Note: G5 offers 50% (see IC-NEW-02). |
| THR-06 | Partial refund / discount cap (general) | **Up to 20%** (Flow 1: "Offer up to 20% refund"; "Requested discount ≤20%" node; Flow 4 OOS: "up to 20% partial refund") | Confluence not surveyed for this topic | **20%** used consistently across F1/F2/F3/F4/F10/F14/F16/F17/F19/F20/F21 and G3.2; F15-F16 gate: discount < or > 20% of PO | Whimsical ↔ Email Templates: **agree** | Consistent. The 20% cap is a hard branch point confirmed in both sources. Note: F8 uses 40% (IC-NEW-06), G5 uses 50% (IC-NEW-02) — see contradictory policy section. |
| THR-07 | 50% refund offer (product complaint non-warranty path) | **50% refund** (Flow 3: "Offer 50% refund AND 40% discount + free shipping (B7)"; "Offer 50% refund OR 40% discount (B3)") | Confluence not surveyed for this topic | **50% refund** confirmed in B3 ("50% refund OR 40% discount + free shipping") and B5 ("50% refund + 40% discount + free shipping") and B7 ("50% refund AND 40% discount + free shipping") | Whimsical ↔ Email Templates: **agree** | Consistent. 50% refund is the standard non-defective product-complaint offer. Note distinction: B3/B5 = OR (customer chooses); B7 = AND (both given). |
| THR-08 | Discount cap in shipping common scenarios | **Up to 50%** (Flow 4 section 4.6 COMMON SCENARIOS: "offer discount (up to 50%)/partial refund") | Confluence not surveyed for this topic | **50% discount** confirmed in G5 template ("50% discount as appeasement gesture" for shipping delay < 21 days / angry customers) | Whimsical ↔ Email Templates: **agree** | Consistent — both state 50% as the upper ceiling in shipping appeasement. Potential contradiction with the 20% cap (THR-06) depending on scenario scope — see IC-02 finding. |
| THR-09 | Shipping time threshold — late shipment flag | Shipping time **> 21 days** (Flow 4 section 4.6) | Confluence not surveyed for this topic | G4/G5 templates address "Order age within 21 days" (neutral/angry customers); G6/G7 address late delivery (implying > 21 days threshold passed) | Whimsical ↔ Email Templates: **agree** (implied) | Consistent. Threshold is implied in template category headings. |
| THR-10 | Shipping time threshold — severely late flag | Shipping time **> 35 days** (Flow 4 section 4.6) | Confluence not surveyed for this topic | G8 ("Late delivery — Express replacement"), G9 ("Promise replacement/refund on day 40") implicitly follow > 35-day severity | Whimsical ↔ Email Templates: **agree** (implied) | Consistent. Templates map to the > 35-day severe-delay path. |
| THR-11 | Last tracking update threshold — no-update flag | Last tracking update **>= 15 days** (Flow 4 section 4.6) | Confluence not surveyed for this topic | source-silent (no template explicitly states this numeric threshold) | Whimsical: stated. Email Templates: **source-silent** | Numeric threshold not restated in templates; operationally implied by G8 (express replacement). Gap: templates do not make this trigger explicit to the agent. |
| THR-12 | Refund promise deadline (DNR/shipping delay) | Full refund promised on **day 40** (Flow 4 section 4.6 and section 4.3 DNR) | Confluence not surveyed for this topic | **Day 40** confirmed in G9 heading "Promise a replacement/refund on day 40" and template text | Whimsical ↔ Email Templates: **agree** | Consistent. Day-40 commitment is the explicit customer-facing promise. |
| THR-13 | Operational rule — private notes | **1 note per request only** (Flow 6 section 6.3) | Confluence not surveyed for this topic | source-silent (no template addresses note-writing conventions) | Whimsical: stated. Email Templates: **source-silent** | Operational rule exists in workflow but is not captured in any customer-facing template. Agents learn this from the workflow diagram only. |
| THR-14 | SCE availability window | **11AM – 4PM** (Flow 6 section 6.3) | Confluence not surveyed for this topic | source-silent (no template references SCE hours) | Whimsical: stated. Email Templates: **source-silent** | Operational rule in workflow only. Missing from any CS-accessible quick-reference guide. |
| THR-15 | Express replacement offer threshold | Offered when shipping time > 35 days or no tracking update (Flow 4 section 4.6) | Confluence not surveyed for this topic | G8 template heading "Late delivery — Express replacement" (implies severe delay trigger) | Whimsical ↔ Email Templates: **agree** (implied) | Consistent. Exact numeric trigger (> 35 days or >= 15-day tracking gap) is not restated in template; agent must know from workflow. |
| THR-16 | Duplicate order refund cap | **20%** refund for duplicated DO/PO (Flow 1: "Offer 20% refund for duplicated DO/PO") | Confluence not surveyed for this topic | **20%** confirmed in F10 ("Duplicated DO found — offer 20% refund on 2nd order") | Whimsical ↔ Email Templates: **agree** | Consistent. |
| THR-17 | Warranty window restatement — from C1 template | Within **45 days of purchase OR 14 days from delivery** (C1 template; consistent with THR-03 + THR-04) | Confluence not surveyed for this topic | C1 template states both thresholds simultaneously: "45 days of purchase or 14 days from delivery" | Whimsical ↔ Email Templates: **agree** | Restatement of IC-01 dual-threshold issue. Both sources carry both thresholds; the OR logic in C1 gives the customer the more favorable calculation. Whether this is intentional policy or an artifact of copying is unresolved. |
| THR-18 | Collab wait time before escalation (EMAIL-CALL) | **2 days** waiting on call team (Flow 5 section 5.1) | Confluence not surveyed for this topic | source-silent | Whimsical: stated. Email Templates: **source-silent** | Operational coordination rule; no customer-facing template or guide surface. |

### Additional thresholds discovered in Email Templates (not in original POLICY-THRESHOLD-INDEX.md)

> These were flagged as IC-NEW in CODE-MAP-templates.md and are now cross-checked here.

| Threshold ID | Description | Whimsical value | Confluence value | Email Template value | Agreement | Finding |
|---|---|---|---|---|---|---|
| THR-19 | Retention offer hold window (duplicated/unrecognized order) | source-silent | Confluence not surveyed for this topic | **48 hours** — F9 ("hold 48h"), F7 (offer valid 48h), F21 (48h validity) | Whimsical: **source-silent**. Email Templates: stated | Operational rule exists in templates only. No workflow-level articulation found. |
| THR-20 | Expedited / express shipping timeframe | source-silent | Confluence not surveyed for this topic | **7–10 business days** expedited, implied in G3.1 (expedited upgrade); G1/G2 state 7–15 business days standard | Whimsical: **source-silent** | Standard delivery window stated in templates only; WorkFlow.svg does not embed a numeric delivery time frame. |
| THR-21 | PayPal refund processing time | source-silent | Confluence not surveyed for this topic | **3–5 business days** (billing template I-codes, PayPal path) | Whimsical: **source-silent** | Payment-specific threshold in billing templates only. |
| THR-22 | Card refund processing time | source-silent | Confluence not surveyed for this topic | **5–10 business days** (billing template I-codes, card path) | Whimsical: **source-silent** | Payment-specific threshold in billing templates only. |
| THR-23 | D8 70% partial refund threshold | source-silent | Confluence not surveyed for this topic | **70%** refund — D8 template heading "Customer refuse 70%" (customer has already been offered and refused a 70% partial refund) | Whimsical: **source-silent**. Email Templates: stated | Refund option exists in template follow-up flow but not in WorkFlow.svg threshold list. Likely an intermediate offer step in the complaint escalation path. |
| THR-24 | G7 10% refund option | source-silent | Confluence not surveyed for this topic | **10% refund** on current order as one option in G7 "Late delivery — Partial refund & Discount" (alternative to 40% discount) | Whimsical: **source-silent** | Refund option at the low end of the spectrum; appears only in this template. |
| THR-25 | G12 test-contract compensation discount | source-silent | Confluence not surveyed for this topic | **30% discount** on next purchase (G12 — test contract order cancelled) | Whimsical: **source-silent** | Scenario-specific discount rate not in workflow diagram. |
| THR-S1 | Pants measurement sanity: hip−waist gap upper bound | source-silent | **Hip − Waist > 15 inches** → ask customer to confirm (Pants guide NOTE 1) | source-silent | Confluence: stated. Others: **source-silent** | Sizing-calculation threshold, different class from policy/temporal thresholds. No conflict. New entry. |
| THR-S2 | Pants measurement sanity: waist−hip gap upper bound | source-silent | **Waist − Hip > 5 inches** → ask to confirm (Pants guide NOTE 1) | source-silent | Confluence: stated. Others: **source-silent** | Same class as THR-S1. No conflict. |
| THR-S3 | Pants measurement sanity: inseam upper bound | source-silent | **Inseam > 36 inches** → ask to confirm (Pants guide NOTE 1) | source-silent | Confluence: stated. Others: **source-silent** | Sizing-calculation threshold. No conflict. |
| THR-S4 | Bra band/cup validity: full-bust minus band-size lower bound | source-silent | **Difference ≥ −5** (else use normal bra size) (Bra guide NOTE 3) | source-silent | Confluence: stated. Others: **source-silent** | Sizing-calculation threshold. No conflict. |
| THR-S5 | Bra band-size formula (even underbust) | source-silent | **Band size = Underbust + 4** (Bra guide scenario 1) | source-silent | Confluence: stated. Others: **source-silent** | Sizing-calculation formula. No conflict. |
| THR-S6 | Bra band-size formula (odd underbust) | source-silent | **Band size = Underbust + 5** (Bra guide scenario 1) | source-silent | Confluence: stated. Others: **source-silent** | Sizing-calculation formula. No conflict. |
| THR-S7 | Decimal measurement rounding rule | source-silent | **Round up** (e.g., 34.5 → 35) — consistent across Bra NOTE 2, Pants NOTE 2, Shirt NOTE 1 | source-silent | Confluence: stated (consistent across 3 guides). Others: **source-silent** | Sizing-calculation rule. No conflict. Consistent within Confluence. |

---

## Contradictory Policy

> Findings where two sources state different rules for the same situation.
> LLM-assisted pairwise comparison across WorkFlow.svg, Email Templates, and Confluence (where applicable).
> Reviewer must make the authoritative ruling for each HIGH finding before RAG ingest (Phase 3).

### CONTRA-01 — Dual warranty calculation creates ambiguous eligibility boundary [IC-01]

**Severity: HIGH**

**Thresholds involved:** THR-03 (45 days from purchase) vs THR-04 (14 days from delivery)

**Sources:** WorkFlow.svg Flow 3 WARRANTY section; C1 template ("product complaint-out of guarantee-template.md")

**Claim A (Whimsical):** "The request is made within 45 days from the purchase date" (customer-facing). Separately: "Internal policy: within 14 days from the delivery date."

**Claim B (Email Template C1):** "returns or exchanges are accepted within 45 days of purchase or 14 days from delivery" — the two thresholds are combined with OR logic, giving the customer whichever window is more favorable.

**Pairwise analysis:** Both sources acknowledge two thresholds exist. The conflict is not source-vs-source but structural: the WorkFlow.svg separates them as customer-facing vs internal-policy (implying they apply to different decision paths), while the C1 template collapses them into a customer-facing OR statement (giving the customer the more favorable window). The ambiguity: if delivery is very late (e.g., 40 days after purchase), is the customer still within the 14-day delivery window? The OR logic in C1 would say yes; the WorkFlow.svg separation implies the customer-facing rule (45-day purchase) governs customer comms and the internal rule (14-day delivery) governs internal operations.

**Customer impact:** Direct — determines whether a complaint is accepted as within-warranty or treated as out-of-warranty (C1 = no replacement, only aftersale discount).

**Action required:** CS Lead / Policy Owner must rule: Is 45 days from purchase the single customer-facing standard, or does the OR clause stand? Ruling must be propagated into C1 template and WorkFlow.svg.

---

### CONTRA-02 — Discount cap inconsistency: 20% general cap vs 50% shipping-appeasement vs 40% goodwill [IC-02 + IC-NEW-02 + IC-NEW-06]

**Severity: HIGH**

**Thresholds involved:** THR-06 (20% cap), THR-08 (up to 50%), THR-05 (40% aftersale), THR-07 (50% refund)

**Sources:** WorkFlow.svg Flow 1 and Flow 4; Email Templates G5, G6, G7, F8, B3, B7

**Claim A (Whimsical Flow 1):** "Offer up to 20% refund" in cancellation and OOS scenarios. "Requested discount ≤ 20%" is a hard branch-point gate.

**Claim B (Whimsical Flow 4 / Email Template G5):** "Provide tracking update and offer discount (up to 50%)/partial refund" for shipping delays. G5 template offers "50% discount as appeasement gesture."

**Claim C (Email Template F8):** F8 (cannot-cancel — wrong variants, DO in TO status) offers 40% goodwill discount — while F19/F20 (same TO-status group, other reasons) use 20%.

**Claim D (Email Template G6/G7):** G6 offers 40% discount for late delivery; G7 offers 40% discount OR 10% refund — different rates within the same scenario type.

**Pairwise analysis:** Three distinct discount/refund rates (10%, 20%, 30%, 40%, 50%) appear across the template set. The 20% cap appears to be scenario-specific (cancellation retention and OOS), not a universal ceiling. The 40%/50% rates apply to distinct scenarios (product complaint aftersale, shipping appeasement, DNR). F8's 40% vs F19/F20's 20% within the same DO-status group (TO = cannot cancel) is the sharpest inconsistency — same situation, different outcome based on reason code.

**Customer impact:** Direct — inconsistent offers on the same class of complaint. An agent applying the wrong template gives the customer a materially different outcome.

**Action required:** CS Lead must confirm: Is the 20% cap restricted to cancellation-request retention only (not a universal rule)? Is the F8 40% intentional for wrong-variant complaints vs the 20% for other TO-status reasons? Document scenario-specific rate schedule explicitly.

---

### CONTRA-03 — B3 vs B7 refund offer structure: OR vs AND [IC-02 variant]

**Severity: MEDIUM**

**Thresholds involved:** THR-07 (50% refund offer)

**Sources:** Email Templates B3, B5, B7

**Claim A (B3, B5):** "Offer 50% refund OR 40% discount + free shipping" — customer chooses one option.

**Claim B (B7):** "Offer 50% refund AND 40% discount + free shipping" — both are given simultaneously (not a choice).

**Pairwise analysis:** B3/B5 and B7 are adjacent codes in the same non-defective product complaint flow (WorkFlow.svg Flow 3). B7 is triggered when replacement is not possible ("B7-All products-Cannot replace"). The AND vs OR difference is likely intentional (B7 escalates the offer), but it is not documented as a deliberate policy distinction in any source — an agent could easily misread B3's OR as equivalent to B7's AND.

**Action required:** Confirm that B7's AND structure is intentional policy (more generous because no replacement option exists) and document the distinction explicitly.

---

### CONTRA-04 — G5 (50% discount for shipping delay < 21 days) conflicts with standard discount logic [IC-NEW-02]

**Severity: MEDIUM**

**Thresholds involved:** THR-08 (up to 50%), THR-06 (20% general cap)

**Sources:** WorkFlow.svg Flow 4 section 4.6; Email Template G5

**Claim A (Whimsical):** "Offer discount (up to 50%)/partial refund" for shipping common scenarios.

**Claim B (G5 template):** G5 is triggered for orders within 21 days (not yet late by the > 21-day standard), categorized as "angry customers." It offers 50% discount as appeasement.

**Pairwise analysis:** The order has not crossed the late-shipment threshold (> 21 days) yet G5 offers the highest discount rate in the template set (50%). This is counterintuitive — an order that is NOT yet late triggers a 50% appeasement that equals the maximum offered to severely delayed orders. G6 (late delivery, confirmed > 21 days) offers 40%, making G5 more generous despite a less severe situation.

**Action required:** Confirm whether G5's 50% discount for pre-21-day angry customers is intentional de-escalation strategy or an error. If intentional, document the reasoning so agents do not treat it as an anomaly.

---

### CONTRA-05 — F8 uses 40% goodwill discount in a group where peers use 20% [IC-NEW-06]

**Severity: MEDIUM**

**Thresholds involved:** THR-06 (20% cap)

**Sources:** Email Templates F8 (cannot-cancel, wrong variants, TO status) vs F19/F20 (cannot-cancel, other reasons, TO status)

**Claim A (F8):** Offers 40% goodwill discount (CELW40 link) for wrong-variant complaint when DO is already delivered.

**Claim B (F19/F20):** Offer 20% discount/refund for other cannot-cancel reasons at the same DO status (TO).

**Pairwise analysis:** F8 and F19/F20 share the same DO status (TO = delivered, cannot cancel). The only difference is the reason code (wrong variant vs other reasons). F8 escalates the offer to 40%, which is the aftersale promotion rate, not the cancellation-retention rate. This may be intentional (wrong variant = a stronger service failure deserving more compensation) but is not documented as policy.

**Action required:** Confirm the 40% vs 20% distinction for TO-status complaints by reason type is intentional. Add explicit scenario-rate table to CS quick-reference.

---

## Stale / Outdated Content

> Findings where content references obsolete states, retired codes, or volatile policy with
> no confirmed update cadence.

### STALE-01 — Chargeback/Claim policy flagged as "changed frequently" with no update mechanism [HIGH]

**Severity: HIGH**

**Source:** Meeting note (2026-05-28): "Chargeback / claim (3%) — Gateway-initiated; policy updated frequently."

**Finding:** The Chargeback/Claim Level-In category (3% of volume) has policy that the CS Lead explicitly described as changing frequently. However:
- No dedicated macro-flow for Chargeback/Claim exists in WorkFlow.svg
- No Confluence guide covers chargeback/claim policy
- The billing templates (SRC-05, I-codes I1–I10) were discovered in the snapshots repo but were NOT part of the original Plan 01/02 survey scope — they represent the only KB surface for this category
- There is no version-date or update-cadence metadata on any snapshot file

**Risk:** The billing templates (I-codes) may be stale. The policy governing chargeback/claim handling is described as volatile but has no governance mechanism (no version date, no owner, no review cadence documented).

**Action required:** CS Lead to confirm whether I-code billing templates represent current chargeback policy. Establish a review cadence before RAG ingest.

---

### STALE-02 — All four KB sources lack version-date or cadence metadata [MEDIUM]

**Severity: MEDIUM**

**Sources:** WorkFlow.svg (SRC-01), Google Sites Email Templates (SRC-02), Confluence SCE guides (SRC-03), Billing templates (SRC-05), Situational templates (SRC-06)

**Finding:** Not one of the surveyed KB sources carries a "last modified" or "version" date visible in the content or metadata:
- WorkFlow.svg: no version metadata observed in the Whimsical export
- Google Sites: no version/date visible in the Markdown exports
- Confluence PDFs: export timestamp (290526 = 2026-05-29) is in the filename but this is the survey-export date, not the content-modification date
- Billing and situational templates: no date metadata

**Risk:** The survey snapshot is a point-in-time capture (2026-05-29). If any source is updated, the snapshot — and any RAG index built from it — becomes stale without a detection mechanism.

**Action required:** Establish update-cadence governance before Phase 3 RAG ingest. Minimum: ask each source owner (CS Lead) for the last-modified date and intended review frequency.

---

### STALE-03 — B4 code referenced in workflow but absent from all templates [MEDIUM]

**Severity: MEDIUM**

**Sources:** CODE-MAP.md (WorkFlow.svg-derived), Email Templates (all 24 snapshot files), Confluence (sizing guides — no B4 reference)

**Finding:** B4 appears in the CODE-MAP.md code range (A/B/D-code family for Product Complaint — Within Guarantee) but:
- No dedicated workflow action node for B4 was found in WorkFlow.svg
- No email template file covers B4
- The "B(5),(6),(7),8" notation in the workflow suggests B4 may have been subsumed or renumbered
- Confluence sizing guides do not reference B4

**Risk:** If B4 is still referenced in Freshdesk ticket histories or agent training, agents or an AI system could try to use a code that has no template or workflow action.

**Action required:** CS Lead to confirm whether B4 is retired/deprecated, subsumed (into B3 or B5), or simply missing from the available exports. If retired, flag explicitly so Phase 3 does not attempt to ingest it.

---

### STALE-04 — WorkFlow.svg has no versioning or last-modified visibility [MEDIUM]

**Severity: MEDIUM**

**Source:** WorkFlow.svg (SRC-01), Whimsical CEE workspace

**Finding:** The WorkFlow.svg is the primary process-knowledge backbone for the entire KB (6 macro-flows, all threshold rules, all state codes). It is a "living diagram" (per D-01 context) but no versioning metadata is visible in the SVG export. There is no mechanism to detect when the diagram changes between survey snapshots.

**Risk:** Threshold values, workflow branches, or code ranges embedded in the diagram may change after the 2026-05-29 snapshot without the KB being notified.

**Action required:** Establish a re-export cadence with the CEE workspace owner. Consider pinning the Whimsical diagram version or using a scheduled export.

---

### STALE-05 — CODE-MAP.md lists F1–F22 and G1–G13; actual templates show F23 and G14/G15 [LOW]

**Severity: LOW**

**Sources:** CODE-MAP.md (seeded by Plan 01 from WorkFlow.svg); Email Templates (Plan 02 discovery)

**Finding:** The original code-range enumeration in CODE-MAP.md (F1–F22, G1–G13) is outdated — the email templates contain F23 (Aftersale promotion) and G14/G15 (DNR replacement codes) that were not listed in the workflow diagram's apparent code ranges. This suggests either the WorkFlow.svg was updated after the code map was compiled, or these codes exist in sources not yet enumerated.

**Action required:** Update CODE-MAP.md to add F23, G14, G15. Confirm whether these codes exist in the WorkFlow.svg or are template-only additions.

---

## Missing Policy

> Situations where a Freshdesk Level-In category or agent workflow step requires an answer
> but no KB source provides one. Cross-referenced against the Coverage Map backbone.

### MISS-01 — Chargeback/Claim (3% volume): no dedicated workflow macro-flow or Confluence guide [HIGH]

**Severity: HIGH**

**Level-In category affected:** Chargeback / Claim (3% of ticket volume, ~90 tickets/day)

**Sources checked:** WorkFlow.svg (no dedicated macro-flow), Confluence sizing guides (no coverage), Email Templates (billing I-codes I1–I10 in SRC-05 provide partial coverage)

**Finding:** The Chargeback/Claim Level-In category has no dedicated handling macro-flow in the Whimsical workflow diagram. The only KB coverage is the billing template file (SRC-05: I1–I10 covering PayPal, Card, and general chargeback responses). This template source was discovered incidentally in Plan 03; it was not formally inventoried in Plans 01–02. There is no root-cause classification guide for chargeback/claim in Confluence (the sizing guides are the only Confluence content provided).

**Gap:** The AI system has no workflow-level policy for how to handle Chargeback/Claim — only customer-facing reply templates. Decision logic (when to escalate, what evidence to request, refund timelines) is undocumented.

**Action required:** CS Lead to confirm: (a) Is there a workflow or policy doc for Chargeback/Claim handling not yet provided? (b) Are the I-code billing templates the complete policy surface for this category? (c) Given the "updated frequently" characterization, what is the current policy and who owns updates?

---

### MISS-02 — Pre-purchase Inquiry sub-category: no dedicated KB coverage found [MEDIUM]

**Severity: MEDIUM**

**Level-In category affected:** Inquiry (9.7% of volume) — pre-purchase sub-category

**Sources checked:** WorkFlow.svg (no dedicated pre-purchase inquiry macro-flow), Email Templates (no pre-purchase template found), Confluence sizing guides (no coverage)

**Finding:** The Inquiry Level-In category includes pre-purchase inquiries (customers asking questions before ordering). No KB source — workflow, template, or Confluence guide — provides structured guidance for pre-purchase inquiries. The Shipping Inquiry macro-flow (Flow 4) covers post-purchase shipping questions but not pre-purchase product/availability questions.

**Gap:** Agents handling pre-purchase inquiries have no documented template or workflow to follow. This may be handled ad-hoc or via tacit knowledge.

**Action required:** CS Lead to identify whether any template or policy document covers pre-purchase inquiries. If not, this is a tacit-knowledge gap that must be documented as an explicit action item.

---

### MISS-03 — SCE root-cause classification for non-sizing complaint types: no Confluence guide provided [HIGH]

**Severity: HIGH**

**Level-In category affected:** Complaint (71% of volume) — non-sizing sub-categories

**Sources checked:** Confluence (4 sizing guides only); WorkFlow.svg (Flow 3 PRODUCT COMPLAINT branches to SCE B4 root-cause tagging for all complaint types)

**Finding:** Step B4 of the agent workflow requires tagging the root cause via the SCE Confluence classification guide for ALL complaint types, not just sizing. The 4 Confluence guides provided cover the sizing domain only. No guide for the following domains has been provided:
- Shipping/delivery root causes
- Billing / payment root causes
- Product defect (non-sizing) root causes
- Return / exchange logistical root causes

**Gap:** The AI system cannot perform B4 root-cause classification for ~60–70% of Complaint tickets (non-sizing types) because no authoritative SCE guide has been provided.

**Action required:** CS Lead / SCE team to confirm whether sibling root-cause guides exist for non-sizing domains. If yes, export to PDF and add to `snapshots/confluence/`. If no, document that non-sizing root-cause classification is undocumented tacit knowledge (Phase 1 surfaces the gap — CS team must author or confirm).

---

### MISS-04 — cf_level_out (Freshdesk Level-Out field): no valid-values list found in any source [MEDIUM]

**Severity: MEDIUM**

**Level-In category affected:** All (cross-cutting — applies to every ticket at close)

**Sources checked:** WorkFlow.svg (references ticket states but not cf_level_out values), Email Templates (source-silent), Confluence sizing guides (source-silent), Freshdesk Ticket Properties PDF (SRC-04 — not yet text-extracted)

**Finding:** The Freshdesk Level-Out field (`cf_level_out`) is the output classification that agents set when closing a ticket. It is referenced in survey findings but no valid-values list has been extracted from any source. The Freshdesk Ticket Properties PDF (SRC-04) likely contains the authoritative field definition but was not fully extracted in Phase 1.

**Gap:** Without the valid cf_level_out values, the AI system cannot produce a valid ticket close classification.

**Action required:** Extract SRC-04 (CKB-[NEW VERSION] Freshdesk Ticket Properties PDF) to plain text and identify the cf_level_out valid-values list. This is a prerequisite for AI ticket-closing automation.

---

### MISS-05 — CEE-SCE collaboration protocol: undocumented trigger rules for SCE escalation [MEDIUM]

**Severity: MEDIUM**

**Level-In category affected:** Cross-cutting (any ticket requiring SCE involvement)

**Sources checked:** WorkFlow.svg Flow 6 (CEE-SCE COLLAB) provides a workflow; Confluence SCE guides cover root-cause classification only; Email Templates source-silent on escalation triggers

**Finding:** WorkFlow.svg Flow 6 defines the CEE-SCE collaboration process (what requests to raise, the 11AM-4PM window, 1-note-per-request rule). However, the triggers for WHEN to escalate a ticket to SCE vs handle it independently are embedded only in the workflow diagram. No standalone policy document or quick-reference guide exists. The SCE guides cover root-cause classification (a different step) and do not address escalation triggers.

**Gap:** The escalation decision logic is diagram-only. If the workflow diagram changes, there is no secondary source to validate against.

---

### MISS-06 — "Knowledge 101: Products" linked Confluence page not provided [MEDIUM]

**Severity: MEDIUM**

**Level-In category affected:** Complaint (sizing sub-category) — Bra sizing specifically

**Sources checked:** Confluence Bra sizing guide (SRC-03a) references "Knowledge 101: Products" for detailed band/cup calculation guidelines

**Finding:** The Bra sizing guide explicitly cites "Knowledge 101: Products" as a prerequisite reference for the band/cup calculation decision logic. This linked Confluence page was not exported as part of Plan 03. Without it, the bra sizing root-cause logic is incomplete at its most detailed decision point.

**Action required:** CS Lead to export "Knowledge 101: Products" from Confluence to PDF into `snapshots/confluence/`. This is required for accurate bra sizing classification.

---

### MISS-07 — MOQ and Active/Disposed DO status: operational meanings unresolved [LOW]

**Severity: LOW**

**Sources checked:** WorkFlow.svg (references both), GLOSSARY.md (both marked TBD), Confluence (source-silent)

**Finding:** Two terms in GLOSSARY.md remain TBD:
- **MOQ** (Minimum Order Quantity) — used in SCE request type context; standard supply-chain meaning assumed but not confirmed
- **Active/Disposed** — a mixed DO status listed in Flow 6 section 6.4; operational meaning not explained

**Gap:** An AI system routing CEE-SCE collaboration requests cannot correctly interpret MOQ-related requests or Active/Disposed DO status without confirmed definitions.

**Action required:** CS Lead / SCE to confirm the operational meaning of Active/Disposed and whether MOQ in the SCE request type context matches the standard supply-chain definition.

---

### MISS-08 — TAX-01: Product-Technical_issue label vs Technical_issue Rootcause_type — one field or two? [MEDIUM]

**Severity: MEDIUM**

**Sources checked:** Confluence sizing guides (SRC-03b Pants guide NOTE 6, SRC-03d Other Product Lines)

**Finding:** The SCE sizing guides use two seemingly related but distinct terms:
- `Product-Technical_issue` — a root-cause label (the four-label taxonomy)
- `Technical_issue` — a Rootcause_type value (used for Shorts length feedback)

It is unclear whether these are two values in a single field, or two separate classification fields in the SCE root-cause data model.

**Action required:** SCE team to confirm the data model: single label field (with `Product-Technical_issue` and `Technical_issue` as variants) or two separate fields (root_cause_label + rootcause_type)?

---

*End of CONFLICT-INVENTORY.md — Phase 1, Plan 04 (2026-05-29)*
