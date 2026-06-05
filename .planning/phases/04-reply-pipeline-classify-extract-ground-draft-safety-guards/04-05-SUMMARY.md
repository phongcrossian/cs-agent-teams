---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "05"
subsystem: cs-agent-team / subagent-detail skills
tags: [always-draft, advisory-signals, d33, d34, d31, rep-01, rep-02, rep-04, safe-03]
dependency_graph:
  requires: ["04-00", "04-01", "04-02"]
  provides: ["consistent-skill-agent-contract", "rep-01-classify-skill", "rep-02-extract-skill", "rep-04-critique-skill"]
  affects: [".claude/skills/classify-ticket/SKILL.md", ".claude/skills/extract-answer-key/SKILL.md", ".claude/skills/self-critique/SKILL.md"]
tech_stack:
  added: []
  patterns:
    - "Advisory escalation_hint signals — high_risk/confidence feed hint, never drive hard escalate"
    - "D-34 flow-signal missing_key — drafter selects verify-order/clarify-order-info fallback"
    - "File-store faithfulness — faithfulness scored against template content + Selless resolved_order fields"
key_files:
  modified:
    - ".claude/skills/classify-ticket/SKILL.md"
    - ".claude/skills/extract-answer-key/SKILL.md"
    - ".claude/skills/self-critique/SKILL.md"
decisions:
  - "Advisory-signal contract: high_risk/confidence/missing_key are escalation_hint inputs, not hard stop gates"
  - "File-store faithfulness: faithfulness dimension scored against local template + Selless data, not KB citations"
  - "Self-critique overall is pass|fail only — escalate verdict value fully retired from skill guidance"
metrics:
  duration: "5m"
  completed: "2026-06-05"
  tasks: 2
  files: 3
---

# Phase 4 Plan 05: Subagent-Detail Skills Rework Summary

**One-liner:** Reworked classify-ticket, extract-answer-key, and self-critique skills to always-draft advisory contract (D-29/D-30/D-33/D-34) — removing escalation_gate, lookup_code, KnowledgeMCP, mandatory [KB-N] citations, semantic_search, and escalate=no-draft from all three skill files so they match the already-reworked agent prompts (04-02).

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rework classify-ticket + extract-answer-key | `4073122` | `.claude/skills/classify-ticket/SKILL.md`, `.claude/skills/extract-answer-key/SKILL.md` |
| 2 | Rework self-critique | `fde09eb`, `badc10a` | `.claude/skills/self-critique/SKILL.md` |

---

## What Changed

### classify-ticket/SKILL.md (REP-01)

- **Preserved:** Two-level taxonomy, 13-value `customer_request` enum, confidence bucket rules, high-risk marker rules, fail-safe `customer_request: null` rule, D-14 untrusted-body rule.
- **Removed:** `lookup_code`/KnowledgeMCP validation requirement from the Level-2 Code section; "The output drives the escalation gate"; "Low confidence always escalates"; "High-risk → escalate (enforced by escalation_gate.py)".
- **Added/reframed:** `high_risk` and `confidence: low` are explicitly advisory signals that feed `escalation_hint`; CODE-MAP candidate `code` is a best-effort hint for the drafter; drafter resolves the authoritative code from the local file-store (D-31).

### extract-answer-key/SKILL.md (REP-02)

- **Preserved:** Answer-key schema, `resolve_order` order verification (REP-02), never-fabricate rule, D-14 untrusted-body rule.
- **Removed:** "Missing-Key Rule D-07 — A missing key always escalates (enforced by escalation_gate.py)"; "missing_key: true is a hard escalation signal".
- **Added/reframed:** `missing_key: true` is explicitly a **D-34 flow signal** — it drives the drafter to select `clarify-order-info` or `verify-order` fallback flow; the pipeline always drafts (D-33).

### self-critique/SKILL.md (REP-04)

- **Preserved:** Three rubric dimension names exactly (`faithfulness`, `policy-match`, `tone-completeness`), Phase-5 DeepEval G-Eval alignment table, one-redraft protocol, D-14 untrusted-body rule.
- **Removed:** `[KB-N]`/`[SEL-N]` inline citation marker requirement; `semantic_search` from KnowledgeMCP spot-check step; `pre_send_guard.py` / D-13 commitment-block reference in policy-match; `overall: "escalate"` as a third output value; second-fail → escalate-no-draft branch.
- **Added/reframed:** Faithfulness defined against selected file-store template content + whitelisted Selless resolved_order fields. `overall` is `pass|fail` only — a second failure attaches `critic_fail` advisory signal to `escalation_hint`; draft still emitted (D-33).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Acceptance grep caught retired-term mentions in header blockquotes**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** The header `>` blockquote notes in the reworked files mentioned the retired terms (`escalation_gate.py`, `lookup_code/KnowledgeMCP`, `[KB-N]/[SEL-N]`, `semantic_search`, `overall.*escalate`) to explain what was removed — these contextual references caused the acceptance grep checks to return non-empty results.
- **Fix:** Rephrased all header notes to avoid the literal banned strings while preserving the same meaning (e.g. "the hard escalation hook is deleted" instead of "`escalation_gate.py` is deleted"; "no mandatory inline citation markers" instead of "no `[KB-N]`/`[SEL-N]` citation markers").
- **Files modified:** All three skill files
- **Commits:** `4073122`, `badc10a`

---

## Known Stubs

None. These are markdown skill-prose files — no data flows, no stubs.

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan edits `.claude/skills/*.md` guidance files only. Threat register items T-04-05-01 and T-04-05-02 are addressed: D-14 untrusted-body rule retained in all three skills; never-fabricate rule retained in extract-answer-key. T-04-05-03 (advisory critique lets unauthorized commitment through) accepted as PoC trade-off per plan (DRY_RUN only).

---

## Self-Check: PASSED

- `.claude/skills/classify-ticket/SKILL.md` — exists, contains `customer_request` (8 lines), `advisory`/`escalation_hint` (7 lines), no `escalation_gate`/`lookup_code`/`KnowledgeMCP`
- `.claude/skills/extract-answer-key/SKILL.md` — exists, contains `resolve_order` (6 lines), `verify-order`/`clarify-order` (3 lines), no `escalation_gate`/`hard escalation signal`
- `.claude/skills/self-critique/SKILL.md` — exists, contains `faithfulness` (8), `policy-match` (6), `tone-completeness` (6), `advisory`/`still emitted` (9), no `semantic_search`/`KnowledgeMCP`/`[KB-`/`[SEL-`/`pre_send_guard`/`overall.*escalate`
- Commits `4073122`, `fde09eb`, `badc10a` — verified in git log
