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
4. It commits only to **customer-answer remediation** (refund/discount/replacement/keep-item) — NOT to an
   **operational action the AI cannot perform** (see §1).

Anything else is **UNAUTHORIZED** → block → escalate. Examples of unauthorized: a refund % above the
threshold, an offer for an out-of-warranty order, a second remediation after one was already given, an
invented coupon, or any claim that an operational action was executed.

**Thresholds confirmed by the data (match Phase-1 index):**
| Threshold | Value | Where seen |
|---|---|---|
| THR-07 50% refund | 50% | Return (20/64), Partial_Refund (6/11) |
| THR-05 VIP discount + free shipping | 40% + free shipping | Return (48/64), Replace (9/37), Partial_Refund (10/11) |
| THR-06 courtesy/retention | ≤ 20% | Cancel_Order retention (3/15), misc courtesy |
| THR-03/04 warranty gate | 45d purchase / 14d delivery | "warranty_window" phrasing in 30/64 Return, 6/37 Replace |

---

## 1. Operational-action boundary (Phase-1 scope guard — STRONG escalate)

Real `change_request` replies **claim an operational action was performed**:
- Cancel_Order → *"we have canceled your order, and our billing team has processed the refund"*
- Change_Shipping_Address → *"I've successfully updated the shipping address"*
- Change_Product_Variant → *"we've updated your order to size X"*

These are **operational actions** (cancel / address edit / variant swap / refund execution). **Phase 1 answers
customers only — it never executes ops** (PROJECT.md / REQUIREMENTS Out-of-Scope). Therefore the AI MUST NOT
draft a reply that **claims** such an action is done. Rule: **any `change_request` sub-type → escalate to ops**
(the human performs the action on the Selless CS Portal, then replies). The AI may not say "we've
canceled/updated…". This is an additional escalation trigger beyond money-risk.

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
| **Full_Refund** | 9 | mixed; warranty (2), evidence (1), discount (2) | Full refund only when variant unavailable / cannot replace (A4/A5/A9); often **evidence-gated** (photo + shipping label) | **ESCALATE** (full-refund authorization + evidence review = human) |
| **Review** | 35 | tracking info (17), discount (12); apology + delivery-window explanation, no clean template | Mixed / needs investigation (SCE) — bespoke explanation, not a single template | **ESCALATE** (this is the "needs human judgement" bucket) |

### 2B. CHANGE_REQUEST (n=67) — operational actions (see §1)
| Customer_Request | n | Real behavior | AI action |
|---|---|---|---|
| Change_Shipping_Address | 27 | "address updated" (operational) | **ESCALATE** (ops) |
| Change_Product_Variant | 20 | "variant changed" + ask measurements (operational) | **ESCALATE** (ops) |
| Cancel_Order | 15 | "order canceled + refund processed"; sometimes ≤20% retention offer first | **ESCALATE** (ops + refund execution) |
| Change_Non_Shipping_Address / Express_Line | 4 | address/line edit | **ESCALATE** (ops) |

> Note: the ≤20% retention offer on cancellation (THR-06/16) is itself an authorized offer, but because the
> resolution requires executing a cancellation/refund, the whole sub-type escalates in Phase 1.

### 2C. INQUIRY (n=89) — informational (highest automation value, lowest risk)
| Customer_Request | n | Real behavior | Authorized content | AI action |
|---|---|---|---|---|
| **Ask_About_Delivery_Status** (WISMO) | 45 | provide tracking + ETA (33); late-shipment discount (6) | Tracking status + ETA from Selless/carrier; if late (THR-09 >21d / THR-10 >35d) may offer compensation (THR-08 ≤50%) | **AUTO** for status; **AUTO\*** if compensation triggered, else ESCALATE |
| **Ask_About_Order** | 29 | order details, tracking | Order/status facts from Selless | **AUTO** |
| **Ask_About_Policy** | 5 | policy explanation | Cited KB policy | **AUTO** |
| **Ask_About_Product** | 6 | product info | Cited product KB | **AUTO** |
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

## 4. OPEN — needs user/CS-lead confirmation
1. **Are `change_request` flows in Phase-1 AI scope at all?** Data says they require ops execution → current
   rule = ESCALATE all. Confirm (vs a future ops-action phase).
2. **"Review" semantics** — confirm this `Customer_Request` value means "route to SCE/human review" (the data
   supports it). If so, it is a hard escalate.
3. **Eligibility data availability** — does Selless expose warranty window (purchase/delivery dates),
   prior-remediation state ("offered 50%/replacement before?"), and variant stock? The AUTO\* rows depend on
   it; if unavailable, those rows degrade to ESCALATE.
4. **Full_Refund** — confirm full refund always needs human authorization + evidence (current rule = ESCALATE).
5. **Threshold authority** — confirm the AI may commit up to THR-05/06/07/08 **without** per-case human sign-off
   when eligibility is grounded (the whole point of automating the offer flow).
