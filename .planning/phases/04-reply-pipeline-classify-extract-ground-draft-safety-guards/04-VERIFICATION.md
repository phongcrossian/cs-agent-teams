---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
verified: 2026-06-05T08:30:00Z
status: human_needed
score: 14/14
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed:
    - "D-32: Four retired guard hooks deleted from disk (pre_send_guard, escalation_gate, grounding_check, authorized_offer) — 04-01"
    - "D-31: Local file-store (get_template_from_file + subtype_to_code) replaces KnowledgeMCP semantic search — 04-00"
    - "D-33: All agents/skills/demo emit action=draft only; never action=escalate-with-no-body — 04-02/04-03"
    - "D-34: Drafter consults Workflow/CODE-MAP on missing order; no fabricated order facts — 04-02/04-03"
    - "settings.json: KnowledgeMCP removed; submit_reply PreToolUse chain gone; only injection_screen + pii_redact wired — 04-01/04-02"
    - "Test suite (tests/cs_team): 97 passed, 5 skipped after retiring 6 deleted-hook test files and rewriting 4 — 04-04"
    - "Subagent-detail skills (classify-ticket / extract-answer-key / self-critique) aligned to always-draft advisory contract — 04-05"
    - "04-06 /test-ticket command: run subcommand + _parse_ticket_list + _apply_caps + thin slash wrapper — 04-06"
    - "CR-01 (_load_env_prd bare FileNotFoundError): explicit raise with diagnostic message — 04-06 review fix"
    - "CR-02 (collect() not calling _process_row): collect() now calls _process_row at line 482 — 04-06 review fix"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run `/test-ticket --id <id>` (or CLI equivalent) against one real ticket from uat_ticket.csv"
    expected: "test-tickets.xlsx written; terminal shows action=draft with non-empty body grounded on a real template phrase; no Freshdesk POST"
    why_human: "Requires live PROD Freshdesk GET + Selless read + real claude --print subprocess; cannot be validated without live credentials and running services"
  - test: "Run a high-risk (refund/money) ticket via --id and inspect test-tickets.xlsx"
    expected: "AI output block shows action=draft with non-null escalation_hint whose reason contains 'high_risk' or equivalent; CS reply column present for side-by-side"
    why_human: "pytest mocks the pipeline; confirming the real team produces the correct advisory hint shape on live ticket data requires human eyes on xlsx output"
  - test: "Run a ticket with no order reference via --id; verify D-34 fallback in xlsx"
    expected: "Draft body uses verify-order or clarify-order-info language; no fabricated order number (ORD-XXXXX) in draft"
    why_human: "D-34 fallback is unit-tested in simulation (30/30 always-draft tests); live execution with real ticket data needs human confirmation"
---

# Phase 4: Reply Pipeline — Always-Draft PoC (D-29/D-30 Pivot) Verification Report

**Phase Goal:** Assemble the per-ticket reply pipeline — re-classify the ticket, extract the answer key,
ground+draft a reply on the local file-store template + Selless order data (D-31, no RAG),
self-critique against the rubric (advisory), and ALWAYS emit action="draft" with an optional advisory
escalation_hint (D-33), using flow-aware Selless fallback (D-34). Safety floor retained: injection
screening (D-14) + PII redaction (D-04) + no-Opus-on-hot-path (D-03). Four hard guard hooks
intentionally DELETED (D-32). DRY_RUN only. On-demand /test-ticket command (D-41..D-45).

**Verified:** 2026-06-05T08:30:00Z
**Status:** human_needed
**Re-verification:** Yes — full pivot re-verification after D-29/D-30 always-draft rework (plans 04-00..04-06)
superseding the prior fail-closed D-26 architecture verification (2026-06-04).

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Four retired guard hooks (pre_send_guard, escalation_gate, grounding_check, authorized_offer) are deleted from disk | VERIFIED | `test ! -f` for all four → passes; `test_hook_deletion.py` 15 assertions pass; 04-01 commits 665937f + 902cfee |
| 2 | settings.json wires ONLY injection_screen (UserPromptSubmit) + pii_redact (PostToolUse); no deleted-hook entries; KnowledgeMCP removed; CS_RUN_ID gone | VERIFIED | 10-assertion python3 check: all PASS — KnowledgeMCP removed, SellessMCP/ReplyMCP present, injection_screen/pii_redact wired, pre_send_guard/escalation_gate/grounding_check/authorized_offer/CS_RUN_ID absent |
| 3 | injection_screen.py (D-14) and pii_redact.py (D-04) remain on disk and wired | VERIFIED | `test -f` both → SAFETY_FLOOR_INTACT; both referenced in settings.json |
| 4 | Drafter grounds on local file-store template + Selless; no KnowledgeMCP/semantic_search in any agent or pipeline skill | VERIFIED | drafter.md: 5 file-store references (`get_template_from_file`, `subtype_to_code`); grep of all 5 agents + 2 pipeline skills shows no KnowledgeMCP/semantic_search (only negation phrases "No KnowledgeMCP") |
| 5 | Pipeline always emits action="draft"; never action="escalate" with no body (D-33) | VERIFIED | reply-pipeline/SKILL.md: "There is no escalate=no-draft outcome" + "no action: 'escalate' verdict"; 30/30 always-draft contract tests pass; test_e2e_dry_run asserts action != "escalate" for all fixtures |
| 6 | D-34 flow-aware fallback: missing order → verify-order/clarify-order-info flow, no fabricated order facts | VERIFIED | drafter.md Step 3 D-34 table present (clarify-order-info / verify-order rows); TestMissingOrderTicket (4 tests) asserts no ORD-XXXXX fabricated pattern and body references verify/clarify-order |
| 7 | Advisory escalation_hint for money/legal/injection signals; never suppresses draft | VERIFIED | reply-pipeline/SKILL.md documents escalation_hint as optional/advisory; HIGH_RISK test asserts action=draft WITH non-null hint; INJECTION test asserts action=draft WITH hint.reason contains "injection:" |
| 8 | voyageai and RAG-use pgvector/ragas removed from pyproject.toml | VERIFIED | `grep -v '^#' pyproject.toml | grep -i "voyageai\|ragas"` returns nothing — only a comment line documenting the removal; no actual package entry |
| 9 | Subagent-detail skills (classify-ticket / extract-answer-key / self-critique) match always-draft advisory contract | VERIFIED | classify-ticket: advisory/escalation_hint present, no escalation_gate/lookup_code/KnowledgeMCP; extract-answer-key: resolve_order + D-34 flow-signal (verify-order/clarify-order), no hard-escalate; self-critique: faithfulness/policy-match/tone-completeness retained, no semantic_search/[KB-/[SEL-/overall:escalate |
| 10 | pytest tests/cs_team GREEN (97 passed, 5 skipped, 0 failed) | VERIFIED | `.venv/bin/python -m pytest tests/cs_team -q` → 97 passed, 5 skipped |
| 11 | Model assignments correct: Haiku for classify/extract, Sonnet for draft/critic/lead, no Opus (D-03) | VERIFIED | classifier=claude-haiku-4-5, extractor=claude-haiku-4-5, drafter=claude-sonnet-4-6, critic=claude-sonnet-4-6, cs-lead=claude-sonnet-4-6 (all confirmed via grep on agent frontmatter) |
| 12 | run subcommand exists with --id/--list/--limit/--per-cat; reuses collect() machinery via shared _process_row coroutine | VERIFIED | `add_parser("run")` at line 1271; `_parse_ticket_list`/`_apply_caps`/`_process_row` defined at lines 1036/1079/1127; collect() calls `_process_row` at line 482 with comment "collect() and run() both call _process_row so the two paths cannot drift"; `run --help` shows all 4 flags |
| 13 | /test-ticket slash command exists, contains no python logic, dispatches to `test_tickets_run.py run` | VERIFIED | `.claude/commands/test-ticket.md` exists; lines 20-21 dispatch to `test_tickets_run.py run --id`/`--list`; `grep -E "^import|^def|asyncio|httpx"` returns nothing; DRY_RUN/read-only documented |
| 14 | Harness never POSTs to Freshdesk (D-39); `assert settings.dry_run` present; no /reply send path | VERIFIED | `assert settings.dry_run` at line 404; `grep -niE "\.post\(|/reply"` in scripts returns nothing new; test_test_tickets_run.py 6 passed; smoke test (04-06 SUMMARY): exit 0, xlsx written, "no Freshdesk POST (D-39 DRY_RUN confirmed)" |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/file_store/template_store.py` | get_template_from_file + subtype_to_code; no RAG imports | VERIFIED | 386 lines; no knowledge_mcp/voyage/pgvector/semantic imports; 22 unit tests pass |
| `src/file_store/__init__.py` | Package init | VERIFIED | File exists |
| `tests/test_file_store.py` | Unit tests for file-store | VERIFIED | Part of 67-test suite (all passed) |
| `tests/test_hook_deletion.py` | 15 assertions: 4 hooks absent + 2 survivors wired | VERIFIED | 15 assertions pass |
| `.claude/settings.json` | ONLY injection_screen + pii_redact; no deleted-hook entries; KnowledgeMCP removed | VERIFIED | All 10 settings checks pass |
| `.claude/agents/drafter.md` | File-store grounding + D-34 fallback table + Sonnet model | VERIFIED | 5 file-store lines; D-34 table; model=claude-sonnet-4-6 |
| `.claude/agents/cs-lead.md` | Always-draft verdict + advisory escalation_hint + no KnowledgeMCP | VERIFIED | advisory/escalation_hint present; D-33 contract documented |
| `.claude/agents/classifier.md` | 13-value customer_request enum + Haiku + advisory signals | VERIFIED | customer_request enum present; model=claude-haiku-4-5; advisory framing |
| `.claude/agents/extractor.md` | resolve_order + missing_key as D-34 flow signal | VERIFIED | resolve_order present; D-34 flow signal documented |
| `.claude/agents/critic.md` | Advisory critique; overall=pass/fail; REP-04 dimensions retained | VERIFIED | faithfulness/policy-match/tone-completeness present; advisory contract |
| `.claude/skills/reply-pipeline/SKILL.md` | Always-draft flow; escalation_hint advisory; file-store grounding | VERIFIED | "D-33 — Always-draft" headline; no escalate=no-draft outcome; file-store references |
| `.claude/skills/ground-and-draft/SKILL.md` | File-store grounding; D-34 fallback; no semantic_search | VERIFIED | "No semantic_search, no KnowledgeMCP" explicit; get_template_from_file + subtype_to_code referenced |
| `.claude/skills/classify-ticket/SKILL.md` | REP-01 13-value enum; advisory signals; no lookup_code | VERIFIED | customer_request enum on line 51+; advisory framing; no escalation_gate |
| `.claude/skills/extract-answer-key/SKILL.md` | REP-02 resolve_order; missing_key = D-34 flow signal | VERIFIED | resolve_order at line 51; D-34 flow signal framing |
| `.claude/skills/self-critique/SKILL.md` | REP-04 faithfulness/policy-match/tone-completeness; no semantic_search; advisory | VERIFIED | All 3 dimensions present; no KB citations; overall=pass/fail only |
| `scripts/cs_team_demo.py` | Always-draft runner; file-store grounded; no deleted-hook imports | VERIFIED | _DRAFT_ACTION only; file_store imported; injection_screen surviving; 30/30 always-draft tests |
| `tests/test_cs_team_demo_always_draft.py` | 30 tests asserting always-draft across 4 fixture types | VERIFIED | 30 passed in 0.56s |
| `tests/fixtures/sample_tickets.py` | Template-backed BENIGN/HIGH_RISK fixtures; MISSING_ORDER fixture | VERIFIED | Return (B7) + Partial_Refund (B7) + MISSING_ORDER_TICKET present; no Review sub-type |
| `scripts/test_tickets_run.py` | run subcommand + _process_row + _parse_ticket_list + _apply_caps; DRY_RUN assert | VERIFIED | All helpers at expected lines; collect() calls _process_row; assert settings.dry_run |
| `.claude/commands/test-ticket.md` | Thin slash wrapper; no python logic; dispatches to CLI | VERIFIED | No python statements; dispatches to `test_tickets_run.py run` |
| `scripts/test_test_tickets_run.py` | 6 unit tests for CSV parse/caps/selection/anti-pattern guard | VERIFIED | 6 passed in 0.03s |
| `tests/cs_team/conftest.py` | ONLY injection_screen + pii_redact in _HOOK_MODULES | VERIFIED | Only 2 entries; no pre_send_guard/escalation_gate/grounding_check |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `drafter.md` | `src/file_store/template_store.py` | `subtype_to_code` + `get_template_from_file` (D-31) | VERIFIED | 5 matching lines in drafter.md referencing file-store functions |
| `drafter.md` | `SellessMCP.resolve_order` | order grounding + D-34 fallback table | VERIFIED | Step 3 D-34 table: clarify-order-info / verify-order rows |
| `reply-pipeline/SKILL.md` | `ReplyMCP.submit_reply` | always-draft single emission path | VERIFIED | submit_reply referenced as the only emission path |
| `scripts/test_tickets_run.py run()` | `collect()` per-ticket body via `_process_row` | shared async coroutine | VERIFIED | collect() line 482; run() line 1247; both call _process_row |
| `.claude/commands/test-ticket.md` | `scripts/test_tickets_run.py run` | slash dispatch (no python logic) | VERIFIED | Lines 20-21: `test_tickets_run.py run --id / --list` |
| `tests/cs_team/conftest.py` | `.claude/hooks/injection_screen.py` | _HOOK_MODULES registration | VERIFIED | Only injection_screen + pii_redact registered |
| `tests/cs_team/test_settings_hook_bindings.py` | `.claude/settings.json` | asserts slimmed two-hook wiring | VERIFIED | Asserts UserPromptSubmit→injection_screen, PostToolUse→pii_redact, no PreToolUse(submit_reply), KnowledgeMCP absent |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `src/file_store/template_store.py` | `body` (template text) | Snapshot `.md` files read via `Path.read_text()` keyed on CODE-MAP heading | Yes — 22 tests prove real B7 body (1013 chars) returned | FLOWING |
| `scripts/cs_team_demo.py` | draft `body` in verdict | `subtype_to_code()` + `get_template_from_file()` from real file-store | Yes — W4 body-match asserts first 10 words of real B7 template appear verbatim in draft | FLOWING |
| `scripts/test_tickets_run.py run()` | `records` list | `_process_row` → `fetch_conversation` (Freshdesk GET) + `run_ai_team` (real claude, DRY_RUN) | Yes — smoke test (04-06): exit 0, xlsx 6615 bytes, action=draft, template=F1 | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Four guard hooks absent from disk | `test ! -f .claude/hooks/pre_send_guard.py && … && echo DELETED` | DELETED | PASS |
| settings.json wires only 2 hooks, KnowledgeMCP absent | python3 10-assertion check | All 10 PASS | PASS |
| File-store returns real template body (B7) | 22 unit tests in test_file_store.py | 22 passed | PASS |
| run --help shows --id/--list/--limit/--per-cat | `.venv/bin/python scripts/test_tickets_run.py run --help` | All 4 flags shown | PASS |
| Slash command contains no python logic | `grep -E "^import|^def|asyncio|httpx" .claude/commands/test-ticket.md` | empty | PASS |
| No Freshdesk POST path in harness | `grep -niE "\.post\(|/reply" scripts/test_tickets_run.py` | empty | PASS |
| pytest tests/cs_team GREEN | `.venv/bin/python -m pytest tests/cs_team -q` | 97 passed, 5 skipped | PASS |
| pytest test_test_tickets_run.py GREEN | `.venv/bin/python -m pytest scripts/test_test_tickets_run.py -q` | 6 passed | PASS |
| Model discipline: Haiku classify/extract, Sonnet draft/critic/lead | grep agent frontmatter `model:` | All 5 agents correct | PASS |
| collect() calls _process_row (CR-02 fix) | `grep -n "_process_row" scripts/test_tickets_run.py` + read line 482 | Line 482 confirmed | PASS |
| _load_env_prd raises explicit error (CR-01 fix) | Read lines 80-95 | `raise FileNotFoundError(...)` with diagnostic message at line 91 | PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REP-01 | 04-02, 04-04, 04-05 | AI re-classifies ticket into correct support category + 13-value sub-type | SATISFIED | classify-ticket/SKILL.md has 13-value customer_request enum; test_team_definitions asserts it; classifier.md Haiku |
| REP-02 | 04-02, 04-04, 04-05 | AI extracts key info (order ref, customer, issue type) | SATISFIED | resolve_order in extract-answer-key/SKILL.md; extractor.md retains REP-02 steps; D-34 missing-key flow signal |
| REP-03 | 04-00, 04-02, 04-03, 04-06 | AI drafts via local template + Selless fill (D-29 reword; no mandatory citations) | SATISFIED | file-store built (04-00); drafter grounds on it (04-02); demo runner proves it (04-03); run path reuses in 04-06 |
| REP-04 | 04-02, 04-04, 04-05 | AI self-critique scores draft against faithfulness/policy-match/tone-completeness rubric | SATISFIED | All 3 dimension names in self-critique/SKILL.md; critic.md advisory; test_team_definitions asserts 3 dimensions |
| SAFE-03 | 04-01, 04-02, 04-03, 04-04, 04-05 | High-risk routing — advisory per D-30 (not blocking) | SATISFIED | escalation_hint advisory; HIGH_RISK test asserts action=draft WITH non-null hint; never action=escalate |
| SAFE-04 | 04-01, 04-04 | Hard output guard SUPERSEDED/REMOVED by D-30 | SATISFIED | Four guard hooks deleted; test_hook_deletion.py 15 assertions pass; settings.json wiring absent |

**Orphaned requirement check:** REQUIREMENTS.md traceability maps REP-01..REP-04, SAFE-03, SAFE-04 to Phase 4. All 6 are covered above. No orphaned Phase 4 requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/test_tickets_run.py` | 494 | Stale docstring comment references "D-26 authorized-offer guard" in `draft()` mode preamble | INFO | Comment only; `draft()` body contains no guard logic; stale documentation artefact from pre-pivot code; non-blocking |
| `scripts/test_tickets_run.py` | 484, 869, 1249 | `time.sleep(0.3)` inside async coroutines (collect, draft, run) | WARNING (WR-01 from 04-REVIEW.md) | Blocks event loop for 300 ms per ticket; advisory only — functional at current ticket volumes; not a correctness issue |
| `scripts/test_tickets_run.py` | 1135-1141 | `_apply_caps` misattributes dropped-bucket counts under `--limit`-only mode | WARNING (WR-02 from 04-REVIEW.md) | Skewed per-bucket drop log when limit trims from list tail; total count correct; advisory |
| `scripts/test_tickets_run.py` | 451 | `csv.DictReader(open(...))` missing context manager | WARNING (WR-03 from 04-REVIEW.md) | ResourceWarning under `-W error::ResourceWarning`; no functional impact at runtime; advisory |
| `scripts/test_tickets_run.py` | argparse | `--per-cat 0` / `--limit 0` silently accepted | WARNING (WR-04 from 04-REVIEW.md) | Produces empty xlsx without error; advisory — add argparse validation before live use |

**Debt marker gate:** No TBD, FIXME, or XXX markers found in any file modified by this phase. Gate PASSES.

**Critical issues from 04-REVIEW.md — both RESOLVED before this verification:**
- CR-01 (`_load_env_prd` bare FileNotFoundError): Fixed — `raise FileNotFoundError(...)` with diagnostic message confirmed at lines 90-95.
- CR-02 (collect() duplicates per-ticket body instead of calling _process_row): Fixed — collect() calls `_process_row` at line 482, confirmed by grep and source read.

---

### Human Verification Required

#### 1. End-to-end /test-ticket single-ticket run against PROD

**Test:** Run `.venv/bin/python scripts/test_tickets_run.py run --id <any_id_from_uat_ticket.csv>` (or invoke `/test-ticket --id <id>` inside Claude Code)
**Expected:** Command exits 0; `test-tickets.xlsx` is written/updated; terminal output shows `action=draft` with non-empty body containing a recognisable template phrase; no Freshdesk POST occurs
**Why human:** Requires live PROD Freshdesk GET + Selless read-only query + real `claude --print` subprocess with credentials; cannot be validated without `.env.prd` and running services

#### 2. Advisory escalation_hint visible in xlsx for a high-risk (refund/money) ticket

**Test:** Run a ticket classified as Partial_Refund or Return (money-related) via `--id` and open the produced `test-tickets.xlsx`
**Expected:** AI output block shows `action=draft`; an `escalation_hint` field is present with a `reason` containing "high_risk" or a money/legal label; the CS agent's reply is in the adjacent column for side-by-side comparison
**Why human:** pytest mocks simulate the pipeline; confirming the real cs-agent-team produces the correct advisory hint shape on live ticket data requires human inspection of xlsx output

#### 3. D-34 fallback visible in xlsx for a ticket without an order reference

**Test:** Run a ticket that has no order code (e.g. a general inquiry with blank Order column) via `--id` and inspect the AI draft in `test-tickets.xlsx`
**Expected:** Draft body uses verify-order or clarify-order-info phrasing; no fabricated order number (pattern ORD-XXXXX or similar) appears in the draft body
**Why human:** The D-34 fallback is unit-tested in simulation (TestMissingOrderTicket, 4 assertions); live execution with real Freshdesk ticket data needs human eyes to confirm the fallback operates correctly in the real pipeline

---

### Gaps Summary

No blocking gaps. All 14 must-have truths are verified in the codebase.

The two critical findings from 04-REVIEW.md (CR-01 bare error, CR-02 collect/process_row duplication) were fixed prior to this verification. The four advisory warnings (WR-01 blocking sleep, WR-02 limit bucketing, WR-03 resource leak, WR-04 zero cap) are open quality improvements noted in 04-REVIEW.md — none affect the phase goal or safety floor.

Three human verification items are required to confirm the live end-to-end behaviour with real PROD data and credentials.

---

_Verified: 2026-06-05T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — full pivot re-verification after D-29/D-30 always-draft rework (plans 04-00..04-06)_
