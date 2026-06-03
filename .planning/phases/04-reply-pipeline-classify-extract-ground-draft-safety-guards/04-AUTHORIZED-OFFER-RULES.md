# Phase 4 (reopened): Authorized-Offer & Draft-vs-Escalate Rule Set

**Derived:** 2026-06-03
**Source data:** 312 real Freshdesk tickets (account `shophelp.freshdesk.com`, 2026-06-02..03), 3 pre-categorized
exports (change-request n=67, complaint n=156, inquiry n=89), each joined with the **CS-agent-entered
properties** + the **first public agent reply** (fetched read-only via `scripts/fetch_golden_replies.py`,
summarized by `scripts/analyze_golden.py`). Raw join is gitignored (`.golden-analysis.jsonl` — customer PII).
**Authoritative policy/templates:** Phase-1 `POLICY-THRESHOLD-INDEX.md`, `CODE-MAP-templates.md`, and
`snapshots/*template*.md` (A1–A9, B1–B13, C1, cancellation/shipping/change templates).

> **Why this exists (the reopen reason).** Phase-4 D-13 blocked ALL commitment language → escalate. But the
> real, correct CS flow resolves the highest-volume categories with **policy-bounded templated offers**
> (refund / discount / replacement). The guard must distinguish **authorized templated offers within policy**
> (draft) from **unauthorized / out-of-policy / fabricated commitments** (block→escalate). This file is the
> data-derived rule set the reworked `pre_send_guard.py` + `drafter` + classifier escalation must implement,
> and the answer key the Phase-5 eval scores against.

---

## 0. Authorized vs Unauthorized commitment (the guard's new core)

A commitment in a draft is **AUTHORIZED** (allow) iff ALL hold:
1. It matches an **approved template** for the classified flow (Phase-1 template library), AND
2. The offered value is **within the policy threshold** for that flow (POLICY-THRESHOLD-INDEX), AND
3. The **order is eligible** (warranty window THR-03/04; not already at a higher remediation tier — the
   "offered 50% before?" / "replacement already provided?" state), grounded via Selless, AND
4. It is consistent with the documented Flow + policy for that case (see §1 for the
   operational-action execution boundary).

Anything else is **UNAUTHORIZED** → block → escalate. Examples of unauthorized: a refund % above the
threshold, an offer for an out-of-warranty order, a second remediation after one was already given, an
invented coupon/promo, or an offer/claim that does not follow the documented Flow + policy.

**Threshold authority (user-confirmed Q5):** the AI MAY commit up to the policy thresholds
(THR-05/06/07/08) **without per-case human sign-off**, provided the offer follows policy and the
eligibility is grounded. Human sign-off is required only when the case falls outside policy.

**Thresholds confirmed by the data (match Phase-1 index):**
| Threshold | Value | Where seen |
|---|---|---|
| THR-07 50% refund | 50% | Return (20/64), Partial_Refund (6/11) |
| THR-05 VIP discount + free shipping | 40% + free shipping | Return (48/64), Replace (9/37), Partial_Refund (10/11) |
| THR-06 courtesy/retention | ≤ 20% | Cancel_Order retention (3/15), misc courtesy |
| THR-03/04 warranty gate | 45d purchase / 14d delivery | "warranty_window" phrasing in 30/64 Return, 6/37 Replace |

---

## 1. change_request IS in scope (user-confirmed Q1) — but the execution boundary matters

Real `change_request` replies **claim an operational action was performed**:
- Cancel_Order → *"we have canceled your order, and our billing team has processed the refund"*
- Change_Shipping_Address → *"I've successfully updated the shipping address"*
- Change_Product_Variant → *"we've updated your order to size X"*

`change_request` is **in scope for the AI** (Q1). Approved templates exist: `cancellation request-template1..9`
(F1–F14: 20% retention, reason-specific), `change request-template1..5`. Eligibility is gated by the
1-hour windows (THR-01 cancel, THR-02 change) + order state, grounded via Selless.

**Open execution-boundary (smaller clarification, not blocking — see §4.1):** these replies *assert the
mutation is done*. The AI must not falsely claim an action it did not cause. Two viable models:
(a) the AI drafts the templated confirmation **after** the cancel/address/variant mutation is executed
(by ops or by an authorized Selless action), or (b) the mutation is wired as an authorized AI action.
Until that is wired, a draft that *claims* "we've canceled/updated…" without the mutation having occurred
is an **UNAUTHORIZED** commitment (§0) and must escalate. Phrasing that does not assert a completed action
(e.g., acknowledge + state next step) can be drafted.

---

## 2. Per-category rule table

Action legend: **AUTO** = AI may draft the templated reply (subject to §0 guard); **ESCALATE** = no draft,
route to human; **AUTO\*** = auto only after a grounded eligibility/threshold check, else escalate.

### 2A. COMPLAINT (n=156) — the offer flow (templates A/B/C)
| Customer_Request | n | Dominant real behavior (signals) | Authorized offer / template | AI action |
|---|---|---|---|---|
| **Return** | 64 | 40%+free-ship (48), warranty check (30), 50% refund (20), replacement (14), 2-options (14); tmpl B-RETURN/B7 | Offer alternatives BEFORE return: replacement OR 50% refund (THR-07), + 40% VIP discount + free shipping (THR-05); keep item. Gated on warranty (THR-03/04) + "offered before?" | **AUTO\*** (warranty+eligibility grounded) else ESCALATE |
| **Replace** | 37 | complimentary replacement (22), keep item (23), ask measurements (12), 40% (9); tmpl A/B replacement | Free replacement, keep original, request fit measurements (bra: under/full-bust; pant: waist/hip/inseam) | **AUTO\*** (in-stock variant + warranty) else ESCALATE |
| **Partial_Refund** | 11 | 50% refund (6) + 40%+free-ship (10); tmpl B7/B-RETURN | 50% refund (THR-07) + 40% discount (THR-05) | **AUTO\*** else ESCALATE |
| **Full_Refund** | 9 | mixed; warranty (2), evidence (1), discount (2) | Full refund per flow when variant unavailable / cannot replace (A4/A5/A9), **evidence-gated** (photo + shipping label) where the flow requires it | **AUTO\*** with **stricter checks** — only when the case follows the documented Flow + policy and evidence requirements are met (Q4); else ESCALATE |
| **Review** | 35 | tracking info (17), discount (12); apology + delivery-window explanation; **no dedicated template** | **GAP** — COVERAGE-MAP.csv: "Review complaint (product-review-related), 12% of Complaint, no dedicated template code found — named gap, CS team to confirm" | **ESCALATE** until CS team defines a Review flow (Q2: no flow exists yet) |

### 2B. CHANGE_REQUEST (n=67) — IN SCOPE (Q1); templates exist; gated on §1 execution boundary
| Customer_Request | n | Real behavior / template | Eligibility gate | AI action |
|---|---|---|---|---|
| Change_Shipping_Address | 27 | confirm address update; `change request-template*` | not yet shipped; valid address | **AUTO\*** (after mutation per §1) else ESCALATE |
| Change_Product_Variant | 20 | variant swap + ask measurements; `change request-template*` | THR-02 (≤1h) / not fulfilled; variant in stock | **AUTO\*** (after mutation per §1) else ESCALATE |
| Cancel_Order | 15 | cancel + refund; ≤20% retention offer first (THR-06/16); `cancellation request-template1..9` | THR-01 (≤1h) eligibility; retention attempt | **AUTO\*** retention offer can be drafted; the cancel+refund **execution** follows §1 (else ESCALATE) |
| Change_Non_Shipping_Address / Express_Line | 4 | address/line edit | order state | **AUTO\*** (after mutation per §1) else ESCALATE |

> The ≤20% retention offer on cancellation (THR-06/16) is an **authorized offer** the AI may draft. The
> account/address/variant **mutation** itself is bounded by §1 (AI must not claim an action it did not cause).

### 2C. INQUIRY (n=89) — informational (highest automation value, lowest risk)
| Customer_Request | n | Real behavior | Authorized content | AI action |
|---|---|---|---|---|
| **Ask_About_Delivery_Status** (WISMO) | 45 | provide tracking + ETA (33); late-shipment discount (6) | Tracking status + ETA from Selless/carrier; if late (THR-09 >21d / THR-10 >35d) may offer compensation (THR-08 ≤50%) | **AUTO** for status; **AUTO\*** if compensation triggered, else ESCALATE |
| **Ask_About_Order** | 29 | order details, tracking | Order/status facts from Selless | **AUTO** |
| **Ask_About_Policy** | 5 | policy explanation | Cited KB policy | **AUTO** |
| **Ask_About_Product** | 6 | product info | Product facts via a **scoped product-info API with limits** (Q3 — analogous to the customer-info API: field-whitelisted, rate-limited, audited), plus cited product KB | **AUTO** (within API limits) |
| **Ask_About_Promotion** | 3 | promo info | Cited promo/KB | **AUTO** (do not invent promo terms) |

---

## 3. Implications for the reworked components

- **classifier** — must emit the level-2 `Customer_Request` sub-type (Return/Replace/Cancel_Order/
  Ask_About_Delivery_Status/…), not just the macro category, so the rule table is addressable.
- **escalation_gate.py** — ADD an "operational-action" trigger (any `change_request` sub-type, Full_Refund,
  Review) → escalate. KEEP money/legal/injection/low-confidence/conflict/stale/missing-key triggers.
- **pre_send_guard.py** — REPLACE block-all-commitment with the §0 authorized/unauthorized test: allow an
  offer only if it matches the flow's approved template AND is within the threshold for the grounded order
  eligibility; block out-of-template / over-threshold / ineligible / second-remediation / fabricated.
- **drafter** — select the correct template via Knowledge MCP `get_template` for the classified sub-type;
  ground the eligibility (warranty window, prior-remediation state, in-stock variant) via Selless before
  making any offer; never claim an operational action was executed.
- **Phase-5 gate (per 05-CONTEXT D-27)** — "0 UNAUTHORIZED commitments" = 0 offers failing the §0 test;
  this rule table is the Track-A/Track-B answer key.

---

## 4. Resolved (2026-06-03) + remaining clarifications

**Resolved by user:**
- **Q1 — change_request IN SCOPE.** Handled via existing templates; remaining sub-question is the
  execution boundary (§1) — does the AI trigger the Selless mutation or draft after ops executes?
- **Q2 — "Review" has NO flow yet.** Confirmed Phase-1 gap (COVERAGE-MAP: product-review-related complaint,
  12%, no dedicated template). → ESCALATE until CS team defines the flow.
- **Q3 — product info via a scoped, limited API** (analogous to the customer-info API: whitelist + rate
  limit + audit). Eligibility/product data IS API-accessible within limits → AUTO\* rows are viable.
- **Q4 — Full_Refund is allowed when it follows the Flow + policy** with stricter evidence checks (not a
  blanket escalate).
- **Q5 — AI may commit up to policy thresholds (THR-05/06/07/08) without per-case human sign-off**, as long
  as it follows policy; out-of-policy → human.

**Remaining clarifications (smaller, for replan):**
1. **change_request execution boundary (§1)** — confirm model (a) draft-after-ops-mutation vs (b)
   AI-triggered authorized Selless action. This decides whether AUTO\* drafts may assert "we've canceled/updated".
2. **Eligibility fields surface** — confirm the Selless/MCP exposes: warranty window (purchase/delivery
   dates, THR-03/04), prior-remediation state ("offered 50%/replacement before?"), variant stock, and the
   product-info API (Q3). The AUTO\* rows degrade to ESCALATE for any field not available.
3. **Evidence handling** — for Full_Refund / evidence-gated complaint paths, confirm how photos/labels are
   received + verified (human-in-loop vs automated check).
