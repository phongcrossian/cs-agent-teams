---
phase: quick-260605-mfi-fd-props-cf-order-capture
plan: 01
type: tdd
wave: 1
depends_on: []
files_modified:
  - scripts/test_tickets_run.py
  - scripts/test_test_tickets_run.py
  - .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json
  - scripts/fetch_ticket_fields_snapshot.py
autonomous: true
requirements:
  - MFI-1  # extract fd_props + cf_order -> order_ref, reuse existing Selless path
  - MFI-2  # collect fd_props (prefix-matched), store + merge into cs_props
  - MFI-3  # PII redaction on cf_email_support / cf_shophelp_discussion_link
  - MFI-4  # build_xlsx FD-properties section
  - MFI-5  # safety contract unchanged (DRY_RUN, reads only)
  - MFI-6  # versioned static ticket_fields enum snapshot + offline regen script

must_haves:
  truths:
    - "On the `run --id` path, cf_order from the FD ticket payload drives the Selless lookup (AI no longer asks the customer for an order number when the FD ticket carries one)."
    - "fd_props captured from the FD GET payload includes cf_level_in*, cf_customer_request*, cf_category, cf_rootcause, cf_package_status, cf_product_label, cf_product_line, cf_flow, cf_section_flow, status, priority, tags — matched by prefix for suffixed keys."
    - "PII-bearing custom fields (cf_email_support, cf_shophelp_discussion_link, any email/URL value) are redacted before being stored in the record or written to xlsx."
    - "test-tickets.xlsx shows an FD-ticket-properties section beside the AI output."
    - "The ticket_fields option enums (nested Level_in -> Customer_Request taxonomy + other dropdowns) exist as a committed static JSON snapshot; tests and the runtime path never call the network for it."
    - "Safety contract unchanged: assert settings.dry_run holds, no Freshdesk POST/reply path added, reads only."
  artifacts:
    - path: "scripts/test_tickets_run.py"
      provides: "_extract_fd_props helper + fd_props capture + cf_order -> Selless trigger + xlsx FD section"
      contains: "_extract_fd_props"
    - path: "scripts/test_test_tickets_run.py"
      provides: "Offline RED->GREEN tests for _extract_fd_props (prefix match, redaction, order extraction, no network)"
      contains: "_extract_fd_props"
    - path: ".planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json"
      provides: "Versioned static ticket_fields enum snapshot (nested Level_in->Customer_Request + other dropdowns)"
      contains: "Level_in"
    - path: "scripts/fetch_ticket_fields_snapshot.py"
      provides: "One-off regen script that fetches GET /api/v2/ticket_fields and writes the static JSON (not on the runtime path)"
      contains: "ticket_fields"
  key_links:
    - from: "scripts/test_tickets_run.py:fetch_conversation"
      to: "scripts/test_tickets_run.py:_extract_fd_props"
      via: "call _extract_fd_props(tj) and return fd_props + fd_order_code"
      pattern: "_extract_fd_props\\("
    - from: "scripts/test_tickets_run.py:_process_row"
      to: "scripts/test_tickets_run.py:fetch_selless_order"
      via: "order_code falls back to conv['fd_order_code'] when row['Order'] empty"
      pattern: "fetch_selless_order\\("
---

<objective>
Capture Freshdesk ticket custom_fields in the validation harness and use `custom_fields.cf_order`
to drive the existing Selless lookup on the `run --id` path, so the AI grounds on the real order
instead of asking the customer for an order number. Also snapshot the FD `ticket_fields` option enums
(the nested Level_in -> Customer_Request taxonomy + other dropdowns) into a versioned, committable
static reference the AI Agent Team can read offline.

Purpose: today `fetch_conversation()` discards every custom field — on `run --id` the synthetic row
has only a Ticket ID, so (1) there is no CS-gold property column for side-by-side review and (2)
Selless is never queried because the order code lives in FD `custom_fields.cf_order` and is never read.

Output:
- `_extract_fd_props(tj)` helper + `fd_props` in the record + cf_order driving the existing Selless path.
- FD-properties section in test-tickets.xlsx.
- Static `freshdesk-ticket-fields.json` enum snapshot + an offline regen script.
- Extended offline unit tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@./.claude/CLAUDE.md
@scripts/test_tickets_run.py
@scripts/test_test_tickets_run.py

<interfaces>
<!-- Key contracts the executor needs. Use these directly — no codebase exploration needed. -->

From src/guards/pii.py:
```python
def redact_text(text: str) -> str: ...   # synchronous, str -> str
```
Imported in scripts/test_tickets_run.py via:
```python
from scripts.cs_team_demo import (_CLAUDE_CLI, _parse_verdict, _pre_screen_ticket, redact_text, settings)
```

Current fetch_conversation (scripts/test_tickets_run.py ~L105) returns:
```python
{"customer_msg": str, "cs_reply": str, "error": str}
```
It already parses the ticket GET into `tj = t.json()` (~L114). The Selless trigger already exists:
```python
async def fetch_selless_order(client: httpx.AsyncClient, order_code: str) -> dict | None: ...
```
and _process_row (~L1127) already calls it:
```python
order_code = (row.get("Order") or "").strip()
selless = await fetch_selless_order(sclient, order_code) if order_code else None
```

VERIFIED FD payload facts (ticket 7508382, live):
- custom_fields.cf_order = "28451-7"                     (order code -> feed Selless)
- custom_fields.cf_level_in285413 = "Inquiry"            (CS gold Level_in; numeric suffix varies)
- custom_fields.cf_customer_request83284 = "Ask_About_Order"  (CS gold sub-type; numeric suffix varies)
- other useful cf: cf_category, cf_rootcause, cf_package_status, cf_product_label, cf_product_line, cf_flow, cf_section_flow
- standard: status, priority, tags
- PII-bearing: cf_email_support (email), cf_shophelp_discussion_link (URL containing an email)
- GET /api/v2/ticket_fields: each dropdown carries `choices`; cf_level_in* is a nested_field whose
  `choices` is a dict mapping Level_in -> list of Customer_Request children:
    Inquiry -> [Ask_About_Product, Ask_About_Policy, Ask_About_Promotion, Ask_About_Order, Ask_About_Delivery_Status]
    Change_Request -> [Change_Shipping_Address, Change_Non_Shipping_Address, Change_Product_Variant, Cancel_Order, Change_Shipping_Express_Line]
    Complaint -> [Review, Return, Replace, Full_Refund, Partial_Refund]
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — offline tests for _extract_fd_props (prefix match, PII redaction, order extraction)</name>
  <files>scripts/test_test_tickets_run.py</files>
  <behavior>
    Add tests that import `_extract_fd_props` from scripts.test_tickets_run and feed a FAKE `tj`
    payload (a dict literal, no network). The fake `tj` mirrors the verified ticket 7508382 shape:
    ```
    custom_fields = {
      "cf_order": "28451-7",
      "cf_level_in285413": "Inquiry",
      "cf_customer_request83284": "Ask_About_Order",
      "cf_category": "...", "cf_rootcause": "...", "cf_package_status": "...",
      "cf_product_label": "...", "cf_product_line": "...", "cf_flow": "...", "cf_section_flow": "...",
      "cf_email_support": "jane.doe@example.com",
      "cf_shophelp_discussion_link": "https://shophelp/x?email=jane.doe@example.com",
    }
    tj = {"custom_fields": custom_fields, "status": 2, "priority": 1, "tags": ["vip","reship"]}
    ```
    - Test A (order extraction): `_extract_fd_props(tj)` returns a 2-tuple `(fd_props, order_code)`
      with `order_code == "28451-7"`.
    - Test B (prefix match): `fd_props["Level_in"] == "Inquiry"` and
      `fd_props["Customer_Request"] == "Ask_About_Order"` (matched by `cf_level_in`/`cf_customer_request`
      PREFIX, robust to the numeric suffix). Also assert keys for cf_category, cf_rootcause,
      cf_package_status, cf_product_label, cf_product_line, cf_flow, cf_section_flow, status,
      priority, tags are present in fd_props.
    - Test C (PII redaction): the raw email `"jane.doe@example.com"` does NOT appear verbatim in any
      fd_props value (cf_email_support + cf_shophelp_discussion_link went through redact_text).
      Assert by substring: `assert "jane.doe@example.com" not in json.dumps(fd_props)`.
    - Test D (empty/missing): `_extract_fd_props({})` returns `({}, "")` (or `({}, None)`) without raising,
      and `_extract_fd_props({"custom_fields": {}})` returns empty fd_props + empty order_code.
    - Test E (no network): the whole module under test is imported but NO httpx client is constructed
      in these tests; `_extract_fd_props` is a pure function over the dict. (Enforced structurally by
      passing a dict literal — add a comment asserting the offline contract.)
  </behavior>
  <action>
    Extend scripts/test_test_tickets_run.py. Add `_extract_fd_props` to the existing import block
    from scripts.test_tickets_run (the import will fail until Task 2 — that is the RED state).
    Add a fixture/helper building the fake `tj` above and the five tests (A–E). Keep the existing
    six tests untouched. Do NOT import collect/run/run_ai_team and do NOT construct any httpx client
    or call claude/Freshdesk/Selless. Run the suite to confirm RED (ImportError or failing asserts),
    per RED->GREEN discipline. Commit: `test(quick-mfi): add failing _extract_fd_props tests`.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest scripts/test_test_tickets_run.py -x 2>&1 | grep -Eq "ImportError|cannot import name _extract_fd_props|[1-9][0-9]* (failed|error)" && echo RED-CONFIRMED</automated>
  </verify>
  <done>New tests A–E exist and FAIL (RED) because _extract_fd_props is not yet implemented; the six pre-existing tests are unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — implement _extract_fd_props, wire cf_order to Selless, add fd_props to record + xlsx</name>
  <files>scripts/test_tickets_run.py</files>
  <behavior>
    `_extract_fd_props(tj: dict) -> tuple[dict, str]` makes Tests A–E pass:
    - Reads `cf = tj.get("custom_fields") or {}`.
    - order_code = first non-empty of cf prefix-matching `cf_order` (exact `cf_order`), stripped.
    - Maps suffixed nested keys by PREFIX: any key starting `cf_level_in` -> fd_props["Level_in"];
      any key starting `cf_customer_request` -> fd_props["Customer_Request"].
    - Copies the fixed cf keys to readable names: cf_category->Category, cf_rootcause->Rootcause,
      cf_package_status->Package_status, cf_product_label->Product_label, cf_product_line->Product_line,
      cf_flow->Flow, cf_section_flow->Section_Flow. Copies standard status->Status, priority->Priority,
      tags->Tags (Tags joined to a comma string if a list).
    - Drops empty values. Redacts PII: cf_email_support, cf_shophelp_discussion_link, AND any value
      that looks like an email or URL (simple `@` or `http` substring test) -> `redact_text(value)`
      before storing. order_code itself is an order ref, not PII — leave it.
    - Returns `({}, "")` for empty/missing custom_fields without raising.
  </behavior>
  <action>
    In scripts/test_tickets_run.py:
    1) Add the pure helper `_extract_fd_props(tj)` per the behavior above (place it just above
       `fetch_conversation`). Reuse the already-imported `redact_text`. Match `cf_level_in*` and
       `cf_customer_request*` by prefix so the numeric suffix (e.g. 285413, 83284) does not matter.
    2) In `fetch_conversation`, after `tj = t.json()`, call `fd_props, fd_order_code = _extract_fd_props(tj)`
       and add them to the returned dict: `out["fd_props"] = fd_props; out["fd_order_code"] = fd_order_code`.
       Initialize both keys at the top `out` literal so error paths still return them.
    3) In `_process_row`, derive the order code as: `order_code = (row.get("Order") or "").strip() or
       conv.get("fd_order_code", "")`. This makes the `--id` path (no Order column) use cf_order to
       trigger the EXISTING `fetch_selless_order` — do NOT add a new Selless call. Update the
       `selless = await fetch_selless_order(...) if order_code else None` guard to use this order_code.
    4) Store fd_props in the record: add `"fd_props": conv.get("fd_props", {})` to the dict returned by
       `_process_row`. Merge into cs_props ONLY for keys the CSV did not supply (so xlsx side-by-side
       works for `--id`): for each k,v in fd_props, set `rec_cs_props.setdefault(k, v)` style — never
       overwrite a non-empty CSV value.
    5) `build_xlsx()`: after the existing "— AI Team output —" / checker blocks, add a
       "— FD ticket properties —" labelled section that lists each fd_props key/value (from
       `rec.get("fd_props", {})`) in column A (label) / column C (value). Keep it beside the AI output.
       Do NOT print raw PII to stdout — keep existing id/length/label-only logging.
    BLOCKING ANTI-PATTERN: do NOT touch `_SUBTYPE_TEMPLATES`, `_allowed_codes_for_subtype`, or any
    template-selection logic. This task only adds property capture + the Selless trigger + xlsx section.
    SAFETY (MFI-5): keep every `assert settings.dry_run`; add NO Freshdesk POST/reply path; reads only.
    Run the full test suite to confirm GREEN (Tests A–E pass, original six still pass).
    Commit: `feat(quick-mfi): capture fd_props + drive Selless via cf_order; xlsx FD section`.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest scripts/test_test_tickets_run.py -x -q 2>&1 | tail -5 && grep -c "_extract_fd_props" scripts/test_tickets_run.py | grep -qv '^0$' && grep -q "fd_order_code" scripts/test_tickets_run.py && echo IMPL-OK</automated>
  </verify>
  <done>All tests pass (RED->GREEN). _extract_fd_props exists; fetch_conversation returns fd_props + fd_order_code; _process_row uses cf_order to trigger the existing fetch_selless_order; record carries fd_props (merged into cs_props for missing keys); build_xlsx renders an FD-properties section; no template-selection edits; all dry_run asserts intact; no POST path added.</done>
</task>

<task type="auto">
  <name>Task 3: Versioned static ticket_fields enum snapshot + offline regen script</name>
  <files>scripts/fetch_ticket_fields_snapshot.py, .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json</files>
  <action>
    1) Create the STATIC committed snapshot `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json`
       capturing the dropdown option enums for the AI Agent Team to read offline. Structure it as a
       versioned object:
       ```
       {
         "_meta": {"source": "GET /api/v2/ticket_fields", "captured": "2026-06-05", "version": 1,
                    "note": "Static snapshot — runtime/tests MUST read this file, never the network."},
         "nested": {
           "Level_in": {
             "Inquiry": ["Ask_About_Product","Ask_About_Policy","Ask_About_Promotion","Ask_About_Order","Ask_About_Delivery_Status"],
             "Change_Request": ["Change_Shipping_Address","Change_Non_Shipping_Address","Change_Product_Variant","Cancel_Order","Change_Shipping_Express_Line"],
             "Complaint": ["Review","Return","Replace","Full_Refund","Partial_Refund"]
           }
         },
         "dropdowns": {
           "Rootcause": [], "Flow": [], "Section_Flow": [], "Product_line": [], "Level_out": [],
           "Package_status": [], "Category": []
         }
       }
       ```
       Populate `nested.Level_in` with the verified taxonomy above (the load-bearing data). For the
       flat `dropdowns` (Rootcause, Flow, Section_Flow, Product_line, Level_out, Package_status,
       Category): if the regen script in step 2 can be run live by the developer, prefer its output;
       otherwise commit them as empty `[]` lists with the keys present so the file is structurally
       complete and the regen script can fill them later. Do NOT block on values you cannot verify —
       the nested Level_in->Customer_Request taxonomy is the required content.
    2) Create the one-off regen script `scripts/fetch_ticket_fields_snapshot.py`: loads `.env.prd`
       (reuse the `_load_env_prd` pattern — import it from scripts.test_tickets_run or duplicate the
       minimal loader), GETs `https://{domain}/api/v2/ticket_fields` (read-only, Basic Auth key/"X"),
       extracts each dropdown field's `choices` (the cf_level_in* nested_field's `choices` dict ->
       nested.Level_in; the flat dropdowns -> dropdowns.<Name>), and writes the JSON above to the
       snapshot path. This script is for REGENERATION ONLY — it is never imported by the harness or
       tests, and the runtime path reads the static file. Guard it with `if __name__ == "__main__":`.
       Add a module docstring stating: "Offline regen tool. NOT on the runtime/test path."
    SAFETY: read-only GET only; no POST. Tests/harness MUST NOT call the network for the snapshot.
    Commit: `chore(quick-mfi): snapshot FD ticket_fields enums + offline regen script`.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,pathlib; p=pathlib.Path('.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json'); d=json.loads(p.read_text()); assert d['nested']['Level_in']['Complaint']==['Review','Return','Replace','Full_Refund','Partial_Refund']; assert 'Ask_About_Order' in d['nested']['Level_in']['Inquiry']; print('SNAPSHOT-OK')" && grep -q "ticket_fields" scripts/fetch_ticket_fields_snapshot.py && grep -q '__main__' scripts/fetch_ticket_fields_snapshot.py && echo REGEN-OK</automated>
  </verify>
  <done>Static freshdesk-ticket-fields.json exists with the verified nested Level_in->Customer_Request taxonomy (and dropdown keys present, values filled or empty placeholders). Offline regen script exists, is __main__-guarded, and is not imported by the harness/tests. No network on the runtime/test path.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Freshdesk ticket payload -> harness | Untrusted: custom_fields (esp. cf_email_support, cf_shophelp_discussion_link, ticket body) carry customer PII and attacker-controllable text. |
| harness record/xlsx -> disk | PII must be redacted before persistence; data files are gitignored but redaction is still required (D-04). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-mfi-01 | Information Disclosure | fd_props storing cf_email_support / cf_shophelp_discussion_link / email/URL values | mitigate | `_extract_fd_props` routes PII-bearing values through `redact_text()` before storing (D-04); Test C asserts the raw email never appears in fd_props. |
| T-mfi-02 | Information Disclosure | stdout logging of ticket properties | mitigate | Keep id/length/label-only logging; never print raw fd_props/PII to stdout. |
| T-mfi-03 | Tampering / Elevation | accidental live Freshdesk write | mitigate | No POST/reply path added; every `assert settings.dry_run` retained (MFI-5, D-39); snapshot regen + ticket reads are GET-only. |
| T-mfi-04 | Tampering | injection text in ticket body/custom_fields | accept | Out of scope for this property-capture change; existing `_pre_screen_ticket` (D-14) advisory screen on the body path is unchanged. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest scripts/test_test_tickets_run.py -q` — all tests pass (6 pre-existing + 5 new).
- No new Freshdesk POST/reply call: `grep -nE "reply|/api/v2/tickets/.*/(reply|notes)|POST" scripts/test_tickets_run.py` shows no added write path.
- `assert settings.dry_run` still present in `run_ai_team` and `run`.
- `_SUBTYPE_TEMPLATES` / `_allowed_codes_for_subtype` unchanged (git diff shows no edits to those defs).
- Static snapshot loads offline and carries the verified Level_in nested taxonomy.
</verification>

<success_criteria>
- `_extract_fd_props(tj)` extracts cf_order as order_code and prefix-matches cf_level_in*/cf_customer_request*; PII redacted; empty input safe.
- On `run --id`, cf_order drives the EXISTING `fetch_selless_order` (no duplicate Selless logic) so the AI grounds on the real order.
- Record carries `fd_props`; merged into `cs_props` only for keys the CSV omitted; xlsx shows an FD-properties section beside the AI output.
- Versioned static `freshdesk-ticket-fields.json` snapshot committed with the nested Level_in->Customer_Request taxonomy + dropdown keys; offline regen script present and off the runtime/test path.
- Safety contract intact: DRY_RUN asserts kept, reads only, no POST path, template-selection logic untouched.
</success_criteria>

<output>
Create `.planning/quick/260605-mfi-fd-props-cf-order-capture/260605-mfi-SUMMARY.md` when done.
</output>
