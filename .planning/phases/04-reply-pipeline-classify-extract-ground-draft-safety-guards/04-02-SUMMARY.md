---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "02"
subsystem: cs-agent-team
tags: [always-draft, file-store, d31, d33, d34, agent-rework, poc-pivot]
dependency_graph:
  requires: ["04-00", "04-01"]
  provides: ["always-draft-pipeline", "file-store-grounding", "advisory-escalation-hint"]
  affects: ["04-04", "04-05"]
tech_stack:
  added: []
  patterns:
    - "Always-draft verdict: action=draft + optional advisory escalation_hint (D-33)"
    - "File-store template grounding: subtype_to_code() + get_template_from_file() from src/file_store/template_store.py (D-31)"
    - "D-34 flow-aware Selless fallback: verify-order / clarify-order-info on missing order"
key_files:
  created: []
  modified:
    - .claude/settings.json
    - .claude/CLAUDE.md
    - .claude/agents/cs-lead.md
    - .claude/agents/classifier.md
    - .claude/agents/extractor.md
    - .claude/agents/drafter.md
    - .claude/agents/critic.md
    - .claude/skills/reply-pipeline/SKILL.md
    - .claude/skills/ground-and-draft/SKILL.md
decisions:
  - "D-33 always-draft enforced in all agent + pipeline-skill LLM contracts: action=draft is the only verdict; escalation_hint is advisory and never suppresses the draft"
  - "D-31 file-store grounding: drafter uses subtype_to_code() + get_template_from_file() (local snapshots); KnowledgeMCP removed from settings.json and all agent tools lists"
  - "D-34 flow-aware Selless fallback documented in drafter.md and ground-and-draft/SKILL.md: missing order → verify-order/clarify-order-info; placeholder tokens only for infra-pending fields on a valid order"
  - "Classifier high_risk and low_confidence reframed as advisory signals (feed escalation_hint); KnowledgeMCP.lookup_code removed from classifier tools (CODE-MAP now local file-store)"
  - "Extractor missing_key reframed as D-34 flow signal (advisory), not a stop gate; pipeline continues to draft with fallback flow"
  - "Critic critique is advisory only: overall=pass|fail (no 'escalate'); failing critique attaches critic_fail to escalation_hint; REP-04 rubric dimensions (faithfulness/policy-match/tone-completeness) retained"
metrics:
  duration_seconds: 410
  completed_date: "2026-06-04"
  tasks_completed: 3
  files_modified: 9
---

# Phase 04 Plan 02: Always-Draft Agent-Team Rework Summary

**One-liner:** Reworked all five cs-agent-team agents and two pipeline-level skills to the always-draft PoC contract (D-33) — KnowledgeMCP removed, verdict is always `action=draft` with an optional advisory `escalation_hint`, drafter grounds on local file-store templates + Selless with D-34 flow-aware fallback.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove KnowledgeMCP from settings.json + always-draft reply-pipeline skill | 838c672 | .claude/settings.json, .claude/CLAUDE.md, .claude/skills/reply-pipeline/SKILL.md |
| 2 | Rework drafter + ground-and-draft skill for file-store grounding (D-31/D-34) | 528bd72 | .claude/agents/drafter.md, .claude/skills/ground-and-draft/SKILL.md |
| 3 | Align cs-lead/classifier/extractor/critic agents to always-draft + advisory hint | 77759e5 | .claude/agents/cs-lead.md, .claude/agents/classifier.md, .claude/agents/extractor.md, .claude/agents/critic.md |

---

## What Was Built

### Task 1 — Settings + Workflow Skill

- **`.claude/settings.json`**: Removed the `KnowledgeMCP` entry (including `DATABASE_URL` and `VOYAGE_API_KEY` env vars). Only `SellessMCP` and `ReplyMCP` remain wired.
- **`.claude/skills/reply-pipeline/SKILL.md`**: Completely rewritten. The old `classify → [escalation gate] → extract → ground+draft → critique → emit escalate/draft` flow is replaced with `classify → extract → ground+draft → critique (advisory) → emit draft verdict`. All stop-and-escalate gates, Hard Escalation Rules table, and Enforcement Reference table referencing deleted hooks are removed. The verdict shape is now a single always-draft payload with an optional `escalation_hint`. File-store grounding (D-31) and D-34 fallback are documented.
- **`.claude/CLAUDE.md`**: The "Escalation Semantics Reference" section replaced with the D-33 "Verdict Shape — Always-Draft + Optional Advisory Hint" section documenting the canonical `action: "draft"` payload with `escalation_hint`.

### Task 2 — Drafter Agent + Ground-and-Draft Skill

- **`.claude/agents/drafter.md`**: Frontmatter tools list drops all `KnowledgeMCP.*` entries (get_template, semantic_search, lookup_threshold). Steps rewritten for: (1) local file-store template selection via `subtype_to_code()` + `get_template_from_file()`, (2) Selless order grounding, (3) D-34 flow-aware fallback table (clarify-order-info / verify-order / placeholder tokens for infra-pending). D-11 mandatory `[KB-N]` citation rule, D-26 authorized-offer block, pre_send_guard language, and RD-Q2 eligibility stub all removed. RD-Q1 (never assert completed mutation) retained.
- **`.claude/skills/ground-and-draft/SKILL.md`**: Rewritten from semantic_search + citation + conflict/stale-escalate + D-26 offer-bounds to file-store template selection + Selless fill + D-34 fallback. `submit_reply` call simplified (no offer block required). D-14 untrusted body rule retained.

### Task 3 — cs-lead, classifier, extractor, critic Agents

- **`cs-lead.md`**: Drops `KnowledgeMCP.*` from tools. Verdict is always `action="draft"` with optional `escalation_hint`. "Escalation Is Final" section removed. Hard rules updated to reference D-33/D-31 instead of D-08/D-10/D-11/D-13/D-26.
- **`classifier.md`**: Drops `KnowledgeMCP.lookup_code` tool (CODE-MAP is now local file-store). Low-confidence and high-risk markers reframed as advisory signals feeding `escalation_hint`, not hard stop gates. 13-value `customer_request` enum (REP-01) retained. Injection-suspicion → `high_risk` marker (D-14) retained.
- **`extractor.md`**: `missing_key` reframed as D-34 flow signal (advisory, not an escalation stop gate). Documents clarify-order-info / verify-order fallback flows. "never fabricate" and D-14 untrusted body rules retained.
- **`critic.md`**: Drops `KnowledgeMCP.semantic_search` tool. Critique made advisory — `overall` is `pass|fail` only (no `"escalate"` outcome). Failing critique attaches `critic_fail` to `escalation_hint`; draft always emitted. Faithfulness definition updated to "supported by selected template + Selless order data" (not `[KB-N]`). REP-04 rubric dimensions (faithfulness/policy-match/tone-completeness) retained.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None introduced in this plan. The RD-Q2 eligibility stub (in drafter.md) was part of the old D-26 authorized-offer block and has been **removed** with that block. The file-store grounding path has no stubs — `subtype_to_code()` and `get_template_from_file()` are fully implemented in `src/file_store/template_store.py` (04-00).

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The `KnowledgeMCP` removal reduces the attack surface (one fewer MCP server with DATABASE_URL + VOYAGE_API_KEY credentials). The D-34 fallback text uses only static template choices (not runtime-derived paths), so T-04-02-02 (drafter fabricates order facts) is mitigated as planned.

---

## Scope Note

Per the plan's scope split: the three **subagent-detail skills** (`classify-ticket/SKILL.md`, `extract-answer-key/SKILL.md`, `self-critique/SKILL.md`) are NOT reworked here — they are in **04-05**. Until 04-05 lands, those skills still reference the old contract. This plan (04-02) aligns the five AGENT `.md` files and two pipeline-level skills; 04-05 completes the skill-level alignment.

---

## Self-Check

Files created/modified:
- [x] .claude/settings.json — exists, KnowledgeMCP removed
- [x] .claude/CLAUDE.md — exists, D-33 verdict shape updated
- [x] .claude/skills/reply-pipeline/SKILL.md — exists, always-draft flow
- [x] .claude/agents/drafter.md — exists, file-store grounding
- [x] .claude/skills/ground-and-draft/SKILL.md — exists, file-store grounding
- [x] .claude/agents/cs-lead.md — exists, always-draft verdict
- [x] .claude/agents/classifier.md — exists, advisory signals
- [x] .claude/agents/extractor.md — exists, D-34 flow signal
- [x] .claude/agents/critic.md — exists, advisory critique

Commits verified:
- [x] 838c672 — Task 1 (settings.json + CLAUDE.md + reply-pipeline/SKILL.md)
- [x] 528bd72 — Task 2 (drafter.md + ground-and-draft/SKILL.md)
- [x] 77759e5 — Task 3 (cs-lead.md + classifier.md + extractor.md + critic.md)

## Self-Check: PASSED
