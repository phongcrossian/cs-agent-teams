---
phase: 01-knowledge-survey-conflict-inventory
document: ACTION-ITEMS.md
role: cs-team-owned-knowledge-gap-action-items
status: complete
produced_by: Plan 04 (Task 2)
last_updated: "2026-05-29"
---

# Action Items — CS-Team Knowledge Gaps

> **Scope statement (D-07):** Phase 1 surfaces these gaps as explicit, owned action items.
> Phase 1 does NOT author the missing content. Authoring new KB content, resolving policy
> contradictions, and establishing governance mechanisms are the responsibility of the CS team
> and CS Lead. These items are prerequisites for Phase 3 (RAG ingest) to proceed correctly.
>
> **Sources:** CONFLICT-INVENTORY.md findings (MISS-*, CONTRA-*, STALE-*), COVERAGE-MAP.csv
> named gaps, SURVEY-email-templates.md gap list, SURVEY-confluence.md remaining gaps,
> GLOSSARY.md TBD terms, and governance gaps identified across all surveyed sources.
>
> **Priority legend:**
> - **P0 — Blocker:** Must be resolved before Phase 3 RAG ingest can proceed correctly for this category
> - **P1 — High:** Required for AI accuracy on high-volume ticket types
> - **P2 — Medium:** Required for completeness; AI may function partially without it
> - **P3 — Low:** Governance / quality improvement; AI can proceed but with lower confidence

---

## Action Items

### AI-01 — Resolve the dual warranty-window conflict [CONTRA-01]

**Priority:** P0 — Blocker (HIGH severity conflict on a money/threshold rule)

**Gap description:** Two warranty period thresholds co-exist across sources without a clear ruling on which governs customer-facing decisions:
- 45 days from purchase date (customer-facing, WorkFlow.svg + C1 template)
- 14 days from delivery date (labeled "internal policy" in WorkFlow.svg; also in C1 as an OR clause)

The C1 template presents both to the customer as "returns or exchanges are accepted within 45 days of purchase or 14 days from delivery." It is unclear whether the OR logic is intentional policy (customer gets whichever is more favorable) or an artifact of copying both thresholds without a ruling.

**Impact:** An AI system following C1's OR logic will accept warranty claims that WorkFlow.svg's separation might reject, and vice versa. Any edge case (e.g., late delivery at day 35 of purchase) will produce an incorrect response if the policy is ambiguous.

**Source:** CONFLICT-INVENTORY.md CONTRA-01; POLICY-THRESHOLD-INDEX.md IC-01; THR-03/THR-04/THR-17

**Owner:** CS Lead / Policy Owner

**Required deliverable:** A written ruling stating: (a) which threshold governs customer-facing warranty eligibility, (b) what the 14-day delivery window is used for (internal SLA, not customer communication?), and (c) updated C1 template and WorkFlow.svg reflecting the authoritative rule.

---

### AI-02 — Document the scenario-specific discount and refund rate schedule [CONTRA-02]

**Priority:** P0 — Blocker (HIGH severity — inconsistent offers on same complaint class)

**Gap description:** Multiple discount/refund rates (10%, 20%, 30%, 40%, 50%) are used across templates with no master rate schedule documenting which rate applies to which scenario:
- 20% — cancellation retention, OOS partial refund, duplicate order (standard cap)
- 30% — test contract cancellation only (G12)
- 40% — aftersale promotion (C1, G6), wrong-variant TO-status cancellation (F8)
- 50% — non-defective product complaint refund (B3/B5/B7), shipping appeasement < 21 days (G5)
- 10% — shipping delay partial refund option (G7)
- 70% — escalated product complaint refund (D8)

The sharpest inconsistency: F8 offers 40% goodwill for wrong-variant complaints when the order is already delivered (TO status), while F19/F20 offer 20% for other reasons at the same DO status.

**Impact:** Agents applying the wrong template give customers materially different compensation for equivalent complaints. An AI system with no rate schedule will hallucinate or apply the wrong rate.

**Source:** CONFLICT-INVENTORY.md CONTRA-02, CONTRA-04, CONTRA-05; IC-02/IC-NEW-02/IC-NEW-06; THR-05/THR-06/THR-07/THR-08

**Owner:** CS Lead / Policy Owner

**Required deliverable:** A written scenario-rate table mapping: Level-In category × sub-scenario → authoritative compensation rate. Must explicitly address F8 vs F19/F20 and G5 vs G6 rate differences.

---

### AI-03 — Confirm B3/B5 (OR) vs B7 (AND) refund structure is intentional policy [CONTRA-03]

**Priority:** P1 — High

**Gap description:** B3 and B5 offer "50% refund OR 40% discount + free shipping" (customer chooses). B7 offers "50% refund AND 40% discount + free shipping" (both given simultaneously). These are adjacent codes in the same product-complaint flow. The AND vs OR distinction is undocumented as a deliberate policy difference.

**Source:** CONFLICT-INVENTORY.md CONTRA-03; CODE-MAP-templates.md B3/B5/B7 entries

**Owner:** CS Lead

**Required deliverable:** Confirmation that B7's AND structure is intentional escalation policy (both offered because no replacement option exists), documented in a note appended to CODE-MAP.md or CODE-MAP-templates.md.

---

### AI-04 — Provide SCE root-cause classification guides for non-sizing complaint domains [MISS-03]

**Priority:** P0 — Blocker for Complaint category (71% of volume)

**Gap description:** The SCE root-cause classification system (used at workflow step B4) has been surveyed for the SIZING domain only (4 Confluence guides: Bra, Pants, Shirt, Other Product Lines). No SCE root-cause guide has been provided for:
- Shipping / delivery complaints (late, lost, damaged)
- Billing / payment complaints
- Product defect (non-sizing: wrong item, defective, missing)
- Return / exchange logistics
- Any other non-sizing complaint domain

Step B4 applies to ALL complaint tickets — non-sizing complaints represent the majority of the 71% Complaint volume. Without these guides, the AI system cannot perform correct B4 root-cause tagging for the bulk of complaint tickets.

**Source:** SURVEY-confluence.md GAP-03-06; CONFLICT-INVENTORY.md MISS-03; COVERAGE-MAP.csv cross-cutting SCE row

**Owner:** CS Lead / SCE team

**Required deliverable:** Export all remaining SCE root-cause classification guides (non-sizing domains) to PDF and place in `snapshots/confluence/`. If no such guides exist for a domain, provide a written statement to that effect so Phase 1 can record the domain as undocumented tacit knowledge.

---

### AI-05 — Export and extract the Freshdesk Ticket Properties document (cf_level_out valid values) [MISS-04]

**Priority:** P0 — Blocker for AI ticket-closing

**Gap description:** The Freshdesk Level-Out field (`cf_level_out`) is set by agents when closing a ticket. The valid values list for this field has not been extracted from any source. The Freshdesk Ticket Properties PDF (SRC-04: `CKB-[NEW VERSION] Freshdesk Ticket Properties-290526-082419.pdf`) is present in the repo but was not text-extracted in Plan 03. It likely contains the authoritative field definitions and valid values.

**Impact:** Without valid cf_level_out values, the AI system cannot produce a valid ticket-close classification — a required output for every ticket it handles.

**Source:** CONFLICT-INVENTORY.md MISS-04; SURVEY-confluence.md SRC-04 note

**Owner:** CS Lead (confirm the PDF is current) + Phase 3 team (extract and ingest)

**Required deliverable:** Text-extract SRC-04 using `pdftotext -layout`; confirm the cf_level_out valid-values list is present and current; add cf_level_out to GLOSSARY.md and POLICY-THRESHOLD-INDEX.md as appropriate.

---

### AI-06 — Document chargeback/claim handling policy and confirm billing templates are current [MISS-01, STALE-01]

**Priority:** P0 — Blocker for Chargeback/Claim category (3% volume, ~90 tickets/day)

**Gap description:** The Chargeback/Claim Level-In category (described by CS Lead as having "policy updated frequently") has:
- No dedicated workflow macro-flow in WorkFlow.svg
- No Confluence guide
- Only the billing template file (SRC-05: I-codes I1–I10) as KB coverage — discovered incidentally, not formally surveyed
- No version date or confirmed currency on the billing templates

An AI system handling chargeback/claim tickets will rely on the I-code templates alone, with no decision-logic guidance and no way to detect if the templates are outdated.

**Source:** CONFLICT-INVENTORY.md MISS-01, STALE-01; COVERAGE-MAP.csv Chargeback rows; SURVEY-confluence.md SRC-05 note

**Owner:** CS Lead / Chargeback policy owner

**Required deliverable:** (a) Confirm I-code billing templates (I1–I10 in `snapshots/billing-template.md`) represent current chargeback policy. (b) If the policy has changed since the template was authored, provide the updated templates. (c) Confirm the update cadence and owner for this category. (d) Optionally: provide a brief decision-logic document covering when to escalate vs respond using I-codes.

---

### AI-07 — Provide coverage for pre-purchase inquiries [MISS-02]

**Priority:** P1 — High (sub-set of Inquiry 9.7% volume)

**Gap description:** Pre-purchase inquiries (customers asking about products, shipping times, availability, or policies before placing an order) have no dedicated template or workflow macro-flow. No KB source covers this sub-type. Agents likely handle these ad-hoc via tacit knowledge.

**Source:** CONFLICT-INVENTORY.md MISS-02; COVERAGE-MAP.csv Inquiry / pre-purchase row

**Owner:** CS Lead

**Required deliverable:** Either (a) identify which existing templates (if any) agents use for pre-purchase inquiries and confirm them, or (b) author a new template or policy note covering standard pre-purchase inquiry responses (product info, shipping times, return policy, payment methods). Phase 1 surfaces this gap — the CS team authors the content.

---

### AI-08 — Provide template or policy for review-related complaints [COVERAGE GAP]

**Priority:** P1 — High (Review = 12% of Complaint sub-categories, ~7.5% of total volume)

**Gap description:** "Review" is listed as a Complaint sub-category (12% of Complaint volume) in the meeting note. No dedicated template code or workflow path for review-related complaints was identified across WorkFlow.svg, Email Templates, or Confluence. Review complaints may be handled via general product complaint codes (A/B) or ad-hoc.

**Source:** COVERAGE-MAP.csv Complaint/Review row; 2026-05-28-meeting-note.md

**Owner:** CS Lead

**Required deliverable:** Confirm which templates (if any) agents use for review-related complaints. If a dedicated template exists, add it to the snapshot inventory. If review complaints are handled via A/B product-complaint codes, document that mapping explicitly.

---

### AI-09 — Confirm B4 code status (retired, deprecated, or missing) [STALE-03]

**Priority:** P1 — High

**Gap description:** The B4 code is referenced in CODE-MAP.md's code range for Product Complaint — Within Guarantee (non-defective) but:
- No dedicated workflow action node exists for B4 in WorkFlow.svg
- No email template file covers B4 (confirmed across all 24 snapshot files)
- The "B(5),(6),(7),8" notation in the workflow suggests it may have been subsumed

If B4 is still referenced in agent training or Freshdesk automations, this creates a dead-code reference that an AI system could attempt to invoke incorrectly.

**Source:** SURVEY-email-templates.md gap list; CONFLICT-INVENTORY.md STALE-03; CODE-MAP-templates.md gap category 2

**Owner:** CS Lead

**Required deliverable:** Explicit confirmation of one of: (a) B4 is retired/deprecated — remove from CODE-MAP.md; (b) B4 is subsumed by B3 or B5 — document the mapping; (c) B4 template exists but was not exported — provide the template file.

---

### AI-10 — Add F23, G14, G15 to CODE-MAP.md [STALE-05]

**Priority:** P2 — Medium (administrative accuracy)

**Gap description:** CODE-MAP.md (the authoritative workflow-code-to-action reference produced in Plan 01) lists F1–F22 and G1–G13. The email template survey (Plan 02) discovered three additional codes not in CODE-MAP.md:
- **F23** — Aftersale promotion / price-variation explanation (cancellation request context)
- **G14** — DNR replacement offer (product-line variants: Bra/Pants/Non-apparel)
- **G15** — DNR replacement-or-full-refund offer (product-line variants)

These codes have templates but are absent from the canonical code map, creating a gap for any system that uses CODE-MAP.md as the code authority.

**Source:** SURVEY-email-templates.md newly-discovered codes table; CONFLICT-INVENTORY.md STALE-05; CODE-MAP-templates.md gap categories 1/4

**Owner:** Phase 3 / engineering team (CODE-MAP.md update) + CS Lead (confirm codes are active)

**Required deliverable:** Update CODE-MAP.md to add F23, G14, G15 with descriptions consistent with verbatim template headings in CODE-MAP-templates.md. Confirm with CS Lead whether these codes appear in the WorkFlow.svg or are template-only additions.

---

### AI-11 — Export "Knowledge 101: Products" linked Confluence page [MISS-06]

**Priority:** P2 — Medium (required for complete bra sizing logic)

**Gap description:** The Bra sizing Confluence guide (SRC-03a) explicitly cites "Knowledge 101: Products" for detailed band/cup calculation guidelines. This linked page was not exported as part of Plan 03. Without it, the bra sizing root-cause classification logic is incomplete at its most detailed decision point.

**Source:** SURVEY-confluence.md GAP-03-07; CONFLICT-INVENTORY.md MISS-06

**Owner:** CS Lead

**Required deliverable:** Export "Knowledge 101: Products" from Confluence to PDF. Place in `snapshots/confluence/`. Confirm it contains no customer PII before committing.

---

### AI-12 — Establish version/update cadence for all KB sources [STALE-02, STALE-04]

**Priority:** P1 — High (governance prerequisite for RAG freshness)

**Gap description:** None of the four KB source families carries visible version-date or last-modified metadata:
- WorkFlow.svg (Whimsical) — "living diagram," no versioning
- Google Sites Email Templates — no version visible in Markdown exports
- Confluence SCE guides — export date only (not content-modification date)
- Billing and situational templates — no date metadata

A RAG system built from these snapshots (Phase 3) will become stale whenever any source is updated, with no mechanism to detect the change.

**Source:** CONFLICT-INVENTORY.md STALE-02, STALE-04; SURVEY-email-templates.md SURVEY.md Reconciliation Note; SURVEY-confluence.md update cadence note

**Owner:** CS Lead (all sources) + individual source owners (Whimsical: CEE workspace owner; Google Sites: CS team; Confluence: SCE team)

**Required deliverable:** For each source — (a) the date the content was last updated, (b) the intended review/update frequency, and (c) the owner responsible for notifying the RAG team when content changes. Minimum acceptable: a shared changelog document or calendar reminder linked to the Phase 3 re-ingest schedule.

---

### AI-13 — Confirm CEE and SCE official full-form names [GLOSSARY TBD]

**Priority:** P3 — Low

**Gap description:** GLOSSARY.md records both terms as TBD on their exact full forms:
- **CEE** — strongly implied as "Customer Email Experience" but not confirmed in any document
- **SCE** — two plausible expansions; role confirmed (owns root-cause classification logic) but literal expansion not spelled out in any PDF or workflow node

**Source:** GLOSSARY.md (CEE, SCE rows); SURVEY-confluence.md GLOSSARY resolution note

**Owner:** CS Lead

**Required deliverable:** Confirm the official full-form names for CEE and SCE. Update GLOSSARY.md.

---

### AI-14 — Confirm MOQ operational meaning and Active/Disposed DO status meaning [MISS-07, GLOSSARY TBD]

**Priority:** P2 — Medium

**Gap description:** Two GLOSSARY.md terms remain TBD on operational meaning:
- **MOQ** — appears in SCE request type "Include DO/PO in next arrival batch (MOQ)"; standard supply-chain meaning (Minimum Order Quantity) assumed but not confirmed in this operational context
- **Active/Disposed** — listed as a combined DO status in WorkFlow.svg section 6.4; operational meaning (what it means for CEE action) is unexplained

**Source:** GLOSSARY.md (MOQ, Active/Disposed rows); CONFLICT-INVENTORY.md MISS-07

**Owner:** CS Lead / SCE team

**Required deliverable:** Plain-English operational definitions for both terms, appended to GLOSSARY.md.

---

### AI-15 — Confirm TAX-01: Product-Technical_issue label vs Technical_issue Rootcause_type (one field or two?) [MISS-08]

**Priority:** P2 — Medium (required for correct SCE data model implementation)

**Gap description:** The Confluence SCE sizing guides use two related terms that may be one field or two:
- `Product-Technical_issue` — appears as a root-cause label in the four-label taxonomy
- `Technical_issue` — appears as a `Rootcause_type` value for Shorts length feedback

The data model (single label field vs two separate fields: root_cause_label + rootcause_type) is unclear from the guides alone.

**Source:** SURVEY-confluence.md GAP-03-08/TAX-01; CONFLICT-INVENTORY.md MISS-08

**Owner:** SCE team

**Required deliverable:** Confirmation of the SCE root-cause data model — how many classification fields exist, what their names are, and whether `Product-Technical_issue` and `Technical_issue` are the same concept or two distinct axes.

---

### AI-16 — Confirm H3 template status (absent from situational templates) [COVERAGE GAP]

**Priority:** P2 — Medium

**Gap description:** The situational templates (SRC-06: `snapshots/situational-template.md`) contain H1, H2, H4-Bra/Pants, H5, H6, H7 but H3 is absent. No reference to H3 was found in WorkFlow.svg either. H3 may be retired, subsumed, or simply missing from the available export.

**Source:** SURVEY-confluence.md SRC-06 note; COVERAGE-MAP.csv Other row

**Owner:** CS Lead

**Required deliverable:** Confirm whether H3 is retired/deprecated, subsumed by another code, or needs to be exported. If retired, annotate CODE-MAP.md (once H-codes are added there).

---

### AI-17 — Add I-codes and H-codes to CODE-MAP.md [SURVEY GAP]

**Priority:** P2 — Medium (completeness for Phase 3 ingest)

**Gap description:** CODE-MAP.md (the authoritative workflow code reference) currently covers only A/B/C/D/E/F/G code families. Two additional code families discovered in Plan 03 have no CODE-MAP.md entries:
- **I-codes (I1–I10)** — billing/chargeback templates (SRC-05)
- **H-codes (H1–H7, H3 absent)** — situational/cross-cutting templates (SRC-06)

**Source:** SURVEY-confluence.md SRC-05/SRC-06 notes; 01-03-SUMMARY.md

**Owner:** Phase 3 / engineering team + CS Lead (confirm codes are active and complete)

**Required deliverable:** Add I-code and H-code families to CODE-MAP.md with descriptions derived from `snapshots/billing-template.md` and `snapshots/situational-template.md` verbatim headings.

---

### AI-18 — Provide evidence-sample for coverage-map validation (D-05 HYBRID method) [CHECKPOINT ITEM]

**Priority:** P1 — High (required to satisfy D-05 HYBRID coverage method)

**Gap description:** Per D-05 (HYBRID coverage method), the COVERAGE-MAP.csv is currently marked "not-yet-validated (no ticket sample provided)" for all rows. The top-down KB-driven backbone is complete, but evidence-sample validation — a small set of historical ticket examples per Level-In category confirming which KB sections actually answer them — has not been provided.

The coverage map is usable as a top-down inventory but has lower confidence than a sample-validated map. Any row marked "gap" or "partial" has not been confirmed by actual ticket behaviour.

**What is needed (PII-safe):** A small sample of historical Freshdesk tickets per Level-In category (Complaint, Change Request, Inquiry, Chargeback/Claim, Other) — a handful per category is sufficient. OR: category-level coverage observations without ticket bodies ("tickets in this category are handled by template G5/G6 most of the time"). Customer PII must be removed before sharing. Do NOT commit raw ticket text to the repo.

**Source:** 01-04-PLAN.md checkpoint:human-verify; COVERAGE-MAP.csv Evidence-validation column

**Owner:** CS Lead (Freshdesk export access)

**Required deliverable:** Either (a) redacted/anonymized ticket snippets (PII removed: names, emails, addresses, order IDs) confirming which template/flow handled each Level-In category, OR (b) category-level coverage observations (no ticket bodies). Once provided, update COVERAGE-MAP.csv Evidence-validation column from "not-yet-validated" to "validated-by-sample" or "top-down-only" as appropriate.

---

### AI-19 — Confirm Google Sites email template page list is complete [SURVEY GAP]

**Priority:** P2 — Medium

**Gap description:** The 24 template files in `snapshots/` were surveyed in Plan 02, but the Google Sites full page-by-page enumeration was performed from the available exports rather than from a confirmed-complete page list provided by CS Lead with viewer access. It is possible that additional template pages exist on the Google Sites that were not exported.

**Source:** SURVEY-email-templates.md Checkpoint Status section; 01-02-SUMMARY.md residual follow-up 1

**Owner:** CS Lead (Google Sites viewer access)

**Required deliverable:** Confirmation from CS Lead that the 24 snapshot files represent the complete Google Sites template library. If additional pages exist, export them to Markdown and place in `snapshots/`.

---

### AI-20 — Document CEE-SCE escalation trigger rules in a standalone quick-reference [MISS-05]

**Priority:** P2 — Medium

**Gap description:** The rules for when a CEE agent should escalate a ticket to SCE (vs handling it independently) are embedded only in WorkFlow.svg Flow 6. There is no standalone policy document or quick-reference guide. If the workflow diagram changes, there is no secondary source. An AI system that handles CEE-facing steps but not SCE operations needs these rules to be explicit and separately accessible.

**Source:** CONFLICT-INVENTORY.md MISS-05

**Owner:** CS Lead / SCE team

**Required deliverable:** A brief policy note or workflow addendum (can be a Markdown file added to `snapshots/`) documenting: (a) the categories of ticket that require SCE involvement, (b) the request types available (per Flow 6.4), (c) the 11AM-4PM availability window, and (d) the 1-note-per-request rule.

---

*End of ACTION-ITEMS.md — Phase 1, Plan 04 (2026-05-29)*
*Total action items: 20 (AI-01 through AI-20)*
*P0 blockers: 5 (AI-01, AI-02, AI-04, AI-05, AI-06)*
*P1 high: 5 (AI-03, AI-07, AI-08, AI-09, AI-12, AI-18) [note: AI-03 and AI-18 are P1; list corrected below]*

---

## Summary by Priority

| Priority | Count | Item IDs |
|----------|-------|----------|
| P0 — Blocker | 5 | AI-01, AI-02, AI-04, AI-05, AI-06 |
| P1 — High | 5 | AI-03, AI-07, AI-08, AI-09, AI-12 |
| P1 — High (checkpoint) | 1 | AI-18 |
| P2 — Medium | 8 | AI-10, AI-11, AI-13 (P3), AI-14, AI-15, AI-16, AI-17, AI-19, AI-20 |
| P3 — Low | 1 | AI-13 |

## Owner Summary

| Owner | Items |
|-------|-------|
| CS Lead | AI-01, AI-02, AI-03, AI-06, AI-07, AI-08, AI-09, AI-11, AI-12, AI-13, AI-14, AI-16, AI-18, AI-19, AI-20 |
| SCE team | AI-04, AI-14, AI-15, AI-20 |
| CS Lead + SCE | AI-04 |
| Phase 3 / engineering | AI-05, AI-10, AI-17 |
| Policy Owner | AI-01, AI-02 |
