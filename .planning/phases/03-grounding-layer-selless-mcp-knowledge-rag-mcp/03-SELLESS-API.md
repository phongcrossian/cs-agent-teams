# Selless API — Confirmed Surface (Phase 3 Selless MCP)

**Source:** `https://api.selless.dev/admin/csm/order/swagger.json` (OpenAPI 3.0.1, `Selless.CSM.Order.Admin` v1.7.54.0)
**Source code:** `/Users/admin/work/crossian/csm/csm-order-admin` (.NET / C#)
**Confirmed:** 2026-06-02 — live `GET .../public/tickets/po/search?param=25044-67` returned **HTTP 200** with no auth header.
**Status:** Replaces the "deferred to user docs" assumption in 03-RESEARCH.md (D-01/D-05). This is now the concrete client-seam contract.

---

## 1. Auth & Transport (resolves D-01)

- **Base URL:** `https://api.selless.dev/admin/csm/order`
- **Auth in swagger:** `securitySchemes: {}`, global `security: []` — **NO authentication declared**. The `/public/` route prefix means access is gated at the **network/gateway layer**, not by an API token.
- **Live confirmation:** the example call succeeded over plain HTTPS GET with no credentials.
- **⚠ SEL-04 implication (validates D-08):** the Selless API itself enforces **no auth, no scope, no rate-limit, no audit**. Therefore **100% of scope enforcement, read-only guarantee, per-tool rate-limiting, field whitelist, and audit logging MUST be implemented in our MCP layer.** The MCP is the only security boundary.
- **Client seam:** `SellessClient` Protocol + `MockSellessClient` (fixtures from the live JSON below) + `HttpSellessClient` (httpx+tenacity, base URL from config). Network/gateway auth (if any header/VPN is needed in prod) is a config concern — confirm at deploy.

---

## 2. Public `/public/tickets` Endpoints (keyed lookups)

All GET unless noted. Prefix: `/admin/csm/order/public/tickets`

| Endpoint | Key | Returns | Maps to | Notes |
|----------|-----|---------|---------|-------|
| `GET /po/search?param=&skip=&take=` | free-text | `PoSearch[]` | resolution | **Free-text cross-customer** (id/code/tracking/name/email/phone). Min 3 chars. ⚠ conflicts with D-03 — see §5. |
| `GET /po/{id}` | order id | `OrderDetail` | **SEL-01** order status, line items, addresses | id = the `id` from PoSearch (e.g. `14sv5kq2iec4to48u4nbcllai`), not the human code. |
| `GET /po/{id}/dispute` | order id | `DisputeViewModel` | SEL-01 context | dispute status for the PO |
| `GET /po/{id}/refunds` | order id | `RefundViewModel` `{amount, include_refund_guarantee}` | SEL-01 context | |
| `GET /po/{id}/irreplaceable` | order id | `IrreplaceableViewModel[]` `{do_id, soft/hard_irreplaceable}` | SEL-01 context | |
| `GET /customer/{id}` | customer id | `CustomerViewModel` | **SEL-02** customer info | name/email/phone + warning status |
| `GET /{id}/ticket-do` | fd_ticket_id | `TicketDoModel` `{fd_ticket_id, do_ids[]}` | mapping | order↔Freshdesk-ticket mapping only |
| `POST /{id}/ticket-do` | — | creates mapping | **WRITE** | ⛔ **NEVER expose** — Phase 3 is read-only (SEL-04/D-08). |

---

## 3. Prior Ticket History — D-05 GAP

The customer's **prior CS ticket history content** lives in `TicketViewModel`:
`{id, fd_ticket_id, rootcause, customer_feedback, customer_request, source, status, agent, agent_id, level_in, level_out, created, updated}` — adequate, stable fields for SEL-03.

**But it is served by a NON-public endpoint:** `GET /admin/csm/order/po/{id}/tickets` (keyed by PO id).
A related event log is `GET /admin/csm/order/po/{id}/histories` → `HistoryViewModel[]` (PO/DO action log: action, reason, source, created_by).

The `/public/tickets` surface only exposes the `ticket-do` **mapping** (order ↔ fd_ticket_id), not ticket content. **Open decision (see §5 Q1).**

---

## 4. Field Whitelist & Deny-list (D-04)

**DENY (hard — never return to drafter, never log):**
- `PoViewModel.payment` entire object → `payment.{transaction_id, gateway_id, provider, card_first4, card_last4, card_brand, merchant_name, merchant_email, paid}` — **card / payment data**.
- `*.total_product_cost` (`LineItemModelView`, `line_item_info`, `VariantViewModel`) — **internal cost / margin**.
- `DoViewModel.{supplier_id, supplier_code, contract_id, is_fake_contract, fulfillment_version_id/name}`, `*.supplier_name` — **internal sourcing/fulfillment**.
- `DisputeViewModel.payload`, `HistoryViewModel.payload` — opaque internal blobs.
- `PoViewModel.handling_fee` — internal economics (review).

**ALLOW (needed to answer a reply):**
- Order: `PoViewModel.{id, code, status (ACTIVE/PENDING/CANCELLED/CLOSED/VALIDATING), created, amount, items_amount, tax_amount, discount, shipping, closed_reason}`, `shipping_address`/`billing_address` (`address.{address1,2, city, state, country, postal_code, first_name, last_name, email, phone}`), `product.{id,name,code,line,family}`. **(`note` is DENIED — see deny-list; it is an internal ops memo field, not customer-facing.)**
- DO/fulfillment: `DoViewModel.{id, code, status, odo_status (NEW/PROCESSING/TA/TO/INUS/DELIVERED/CLOSED/CANCELLED/PENDING), status_date_*, trackings, failed_reason, product_label, urgent}`.
- Customer: `CustomerViewModel.{id, first_name, last_name, full_name, email, phone, email_status, phone_status}`.
- Refund/dispute/irreplaceable: as returned (minus payload).
- Ticket history (if exposed): `TicketViewModel.{rootcause, customer_feedback, customer_request, status, source, level_in, level_out, created}` — `agent_id`/`agent` are internal (review).

**PII note (D-06):** name/email/phone/address ARE returned in-context to the drafter (needed to address customer), but **Presidio redacts before any log/audit/trace write** (`src/guards/pii.py`).

---

## 5. Open Decisions for Planning

**Q1 — Prior ticket history source (D-05). — RESOLVED 2026-06-02 → Option B, full in Phase 3.** Content is at non-public `po/{id}/tickets`; `/public` only has `ticket-do` mapping. **Decision:** Phase 3 ships a full `get_ticket_history(order_id)` tool that uses `ticket-do` mapping → `fd_ticket_id` → the existing **Phase-2 Freshdesk client** to fetch prior-ticket content, then whitelists the fields. SEL-03 fully satisfied within Phase 3; source of content = Freshdesk; composition lives inside the Selless MCP tool.
- ~~(A) Wrap non-public `po/{id}/tickets`~~ — not chosen (avoid non-public endpoint dependency).
- **(B) ✅ ticket-do → fd_ticket_id → Freshdesk (Phase-2 client) — CHOSEN.**
- ~~(C) Defer content to follow-up~~ — not chosen.

**Q2 — Free-text search vs D-03.** `po/search` is genuinely free-text cross-customer. D-03 forbids exposing that at the MCP. Options:
- (A) Don't expose search at all; MCP exposes only keyed `get_order(id)` / `get_customer(id)`. (But then how does Phase 4 resolve email→order id? The human `code` like `25044-67` still needs `po/search` to get the internal `id`.)
- (B) Expose a constrained `resolve_order` tool: accepts an **exact** order code OR verified email, returns only exact-key matches (single identity), never a fuzzy/browse list — honors the "keyed lookup, no cross-customer browsing" spirit of D-03 while enabling resolution. **(Recommended.)**

**Q3 — Field whitelist** in §4 — confirm the deny-list (esp. `note`, `handling_fee`, `agent`/`agent_id`).
