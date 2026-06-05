# Phase 8: Ticket Re-Classification & FD Property Write-Back — Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Task Boundary

The Agent Team has two outputs per ticket: (1) the customer reply (Phase 4, done), and (2) a
**re-classification that defines the core Freshdesk classification properties** to be written back
into the ticket. This phase delivers output (2) as a **DRY_RUN would-be update**: classify → map to
exact `ticket_fields` enum values → validate against the enum → log to xlsx/jsonl. The live
`PUT /tickets/{id}` write is DEFERRED.
</domain>

<decisions>
## Implementation Decisions (LOCKED — user-approved 2026-06-05)

### Home
- New dedicated phase (Phase 8). NOT a Phase 4 reopen. (Write-back is a new FD write surface.)

### Write-back execution scope
- **DRY_RUN only**: classify + map + validate + log a would-be FD property update. Defer the live
  `PUT /tickets/{id}`. No new live Freshdesk write path in this phase.
- ⚠️ Write-back is a NEW Freshdesk write path beyond the `submit_reply` chokepoint — must stay
  DRY_RUN-gated and be revisited before any live write at 23k/week.

### Field coverage (what the AI OWNS)
- Core classification dropdowns ONLY: **Level_in, Customer_Request (nested under Level_in),
  Rootcause, Flow, Section_Flow**.
- OUT of scope (stay manual): Level_out, Package_status, Product_label/line, Handler, SCE team,
  Call type, Request to SCE, and all other agent-workflow fields.

### Grounding & validation
- Enum source of truth = the committed snapshot
  `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json`,
  read **statically** (no network at runtime). A file-store loader exposes the choices, including
  the nested Level_in→Customer_Request map.
- The AI must pick a **verbatim** value from the allowed enum per field; output is **validated**
  against the enum and an out-of-enum value is **flagged, never silently accepted** — same
  discipline as the blocking "free-pick template" anti-pattern (allowed-codes).
- Grounding signals for the classification = ticket body + Selless order data + Workflow/CODE-MAP.

### Verification
- Reuse the existing validation harness (`scripts/test_tickets_run.py`) to show AI-defined
  properties vs CS gold FD `custom_fields` side-by-side with a per-field match metric. The gold
  values come from FD custom_fields (cf_level_in*, cf_customer_request*, cf_rootcause, cf_flow,
  cf_section_flow) — already captured into `fd_props` by quick task 260605-mfi.
</decisions>

<specifics>
## Specific Ideas / Code Context

- **Enum loader:** extend `src/file_store/` (alongside `template_store.py`'s `subtype_to_code`) with a
  reader for the ticket_fields snapshot — e.g. `field_choices(field)` and
  `customer_requests_for(level_in)`. Static file read; offline-testable.
- **Pipeline output:** the classifier/extractor stage (`.claude/agents/classifier.md`,
  `.claude/agents/extractor.md`, skills `classify-ticket` / `extract-answer-key`) should emit an
  `fd_property_update` block with one verbatim enum value per owned field. Keep it advisory/additive
  to the always-draft verdict (D-33) — it does not change the reply path.
- **Validation:** a deterministic enum-validation helper (mirrors the template-code allowed-set
  guard) flags out-of-enum values; surface `*_valid` columns in `test-tickets.xlsx`.
- **Harness:** `_extract_fd_props` (quick task 260605-mfi) already pulls CS gold props into `fd_props`;
  add the AI-defined props + per-field match to the xlsx side-by-side.
- **Taxonomy reference:** see memory note `fd-ticket-fields-taxonomy` — Level_in (9) → Customer_Request
  children; Rootcause (14); Flow (7); Section_Flow (5).

</specifics>

<canonical_refs>
## Canonical References

- ROADMAP.md Phase 8 entry (Goal + Success Criteria + Scope boundary) — authoritative.
- REQUIREMENTS.md REP-06.
- `.claude/CLAUDE.md` — always-draft safety contract; DRY_RUN only; submit_reply is the sole
  customer-facing write chokepoint (property write-back must NOT bypass safety posture).
- Snapshot: `.planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json`.

</canonical_refs>
