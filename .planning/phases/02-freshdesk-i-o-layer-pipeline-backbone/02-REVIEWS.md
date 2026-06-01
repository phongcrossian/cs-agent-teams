---
phase: 2
reviewers: [critic-opus, architect-opus]
review_mode: internal-subagent  # no independent external CLI available (only `claude` detected, running inside Claude Code → skipped for independence); user opted into fresh-context subagent review
reviewed_at: 2026-06-01T06:06:33Z
plans_reviewed: [02-01-PLAN.md, 02-02-PLAN.md, 02-03-PLAN.md, 02-04-PLAN.md, 02-05-PLAN.md, 02-06-PLAN.md]
---

# Cross-AI Plan Review — Phase 2: Freshdesk I/O Layer & Pipeline Backbone

> **Review provenance:** No independent external AI CLI was available (`gemini`/`codex`/`coderabbit`/`opencode`/`qwen`/`cursor` not installed; only `claude` present, but the session runs inside Claude Code so it was skipped per the independence rule). At user direction, two **fresh-context Opus subagents** reviewed the plans from distinct lenses (adversarial critic + systems architect). These share the Claude model family with the planner, so treat as a strong internal review, not a true cross-model independent review.

---

## Critic Review (adversarial, Opus)

### 1. Summary

Strong, unusually well-sequenced set of plans. The resolve-then-enqueue idempotency design (D-02) is the right call and genuinely closes the webhook/poller duplicate-enqueue race. Wave structure, TDD scaffolding in Wave 0, and per-plan threat models are above bar. However, the plans have **one genuine CRITICAL correctness gap in the exactly-once guarantee** (crash window between a successful Freshdesk POST and the DB `finalize_done` — the exact REP-05 property the phase exists to guarantee), **a missing client capability** (`list_updated_tickets` / `Ticket` model) that 02-05 depends on but 02-02 never builds, plus several MEDIUM gaps (poller window durability, loop-guard partly inert on the real data path, "exactly-once" tested only at the queue layer). The four success criteria are *mostly* made true, but criterion #2 ("a retried/duplicate inbound never produces a second send") is **not guaranteed** as written — only de-duplication of *enqueue* is, not de-duplication of *send*.

### 2. Strengths

- **Resolve-then-enqueue (D-02) is correct and well-reasoned.** Both webhook and poller compute the key from the same ticket state before enqueue → the unique index is a real dedup guard. The fix commit `5c41178` clearly addressed an earlier sentinel-based design.
- **Wave 0 test scaffolding is disciplined.** All 7 test files (incl. `test_poller.py`) created RED-on-purpose; later waves convert RED→GREEN. VALIDATION enforces "no 3 consecutive tasks without automated verify."
- **Claim/finalize uses claim_token + stale recovery** — `finalize_done ... WHERE id=$1 AND claim_token=$2` correctly prevents a stale recovered worker from finalizing a re-claimed row.
- **Suppression vs dead-letter distinction (D-08)** carried all the way to `test_suppressed_not_dead_letter` in 02-06.
- **Dependency ordering is sound** — Wave 0 → {02-02, 02-03} → {02-04, 02-05} → 02-06. No cycles. D-07 checkpoint made non-blocking with documented rationale.
- **Secrets/PII hygiene consistent** across every plan's threat register.

### 3. Concerns

- **`HIGH/CRITICAL` — Crash window between successful Freshdesk POST and `finalize_done` can produce a duplicate send.** In 02-04-T2, `process_queue_row` does `send_reply(...)` (live → real `client.post_reply`) **then** `finalize_done(...)`. If the worker crashes after Freshdesk accepts the reply but before `finalize_done` commits, the row stays `claimed`, `recover_stale_claims` flips it to `pending`, the worker re-claims and calls `post_reply` **again**. The D-02 key only dedups *enqueue*; `ON CONFLICT` never fires on a re-claim of an existing row. The plans assert "retry does not double-send" but only test enqueue-dedup. Confidence HIGH. **Fix:** record send-intent transactionally (`sent_at`/`freshdesk_reply_id` column, skip to finalize on re-claim of a row with `sent_at`), and/or a pre-send existence check via `GET /conversations` for a system marker. Add `test_worker_crash_after_post_does_not_resend`.
- **`MAJOR/HIGH` — 02-05 depends on `FreshdeskClient.list_updated_tickets()` and a `Ticket` model that 02-02 never builds.** 02-02 scopes the client to `post_reply, post_note, get_conversations, get_ticket` only. The poller (half of criterion #1) cannot be built as written. **Fix:** add `list_updated_tickets(since) -> list[Ticket]` (+ `Ticket` model, + pagination `updated_since`/`per_page=100`) to 02-02 must_haves and a `test_list_updated_tickets`.
- **`MAJOR/HIGH` — Poller window is in-memory only; on restart it loses or re-scans the reconciliation window.** No checkpoint column/migration exists (0001 creates only `ticket_queue`, `dead_letter`, `dry_run_log`); `test_poller_advances_window` only advances an in-memory value. On restart, dropped events during downtime are permanently missed — defeating the safety-net rationale of D-09. **Fix:** add a `poller_checkpoint` table to migration 0001, persist `last_since` after each `reconcile_once`, resume with a safety overlap. Add `test_poller_window_persists_across_restart`.
- **`MEDIUM` — Loop-guard's most important layers (RFC 3834 headers, sender pattern) may not be applied on the real intake path.** Resolve filters only `incoming=true AND private=false`; the full `should_suppress` runs later in the worker, but raw RFC 3834 headers may not be exposed via the API at all (RESEARCH A4), making layer 1 potentially inert. Net: a four-layer guard degrades to ~two layers. A `noreply`-style sender with a non-matching local part could slip through. **Fix:** verify header exposure on sandbox; if absent, add a per-ticket reply-count/time-window throttle as a true loop-breaker independent of sender classification. Add `test_loop_guard_throttle`.
- **`MEDIUM` — "Exactly-once" never tested end-to-end through the worker against a real double-send.** 02-06-T3 re-runs *intake* (enqueue-dedup again), not claim→POST-succeeds→finalize-fails→re-claim. The headline property's hardest case is unexercised. **Fix:** add the mock-HTTP crash-after-post test (no sandbox needed).
- **`MEDIUM` — `claim_one` ORDER BY `next_attempt_at ASC` has no tiebreaker** → non-deterministic FIFO when many enqueue in one poller tick. **Fix:** `ORDER BY next_attempt_at ASC, id ASC`. Document worst-case drain at burst (3,200/day ≈ 2.2/min avg, bursty).
- **`MEDIUM` — 409 handling hand-waved.** Freshdesk `POST /reply` has no documented server-side idempotency; treating an arbitrary 409 as "success/duplicate" is a guess that could swallow a real error. **Fix:** until a verified semantic is observed on sandbox, treat 409 as fatal → dead-letter; do not rely on it for exactly-once.
- **`LOW` — RESEARCH `send_reply` snippet writes `dry_run_log (ticket_id, body, created_at)`** missing `inbound_msg_id`/`action`. Doc drift only; 02-04 is correct. Flag executor to follow the plan, not the snippet.
- **`LOW` — Single migration 0001 doesn't anticipate the checkpoint/`sent_at` columns** the fixes above require → schema churn after the fact. Account for it now.
- **`LOW` — `src/queue/` shadows the stdlib `queue` module.** Consider `src/work_queue/` or `src/jobs/`.

### 4. Suggestions
- Add `sent_at TIMESTAMPTZ` + `freshdesk_reply_id BIGINT` to `ticket_queue` in 0001 now; gate `post_reply` on `sent_at IS NULL` within the claimed row's lifecycle.
- Add RED scaffolds from the start: `test_worker_crash_after_post_does_not_resend`, `test_poller_window_persists_across_restart`, `test_list_updated_tickets`.
- Pull `list_updated_tickets` + `Ticket` into 02-02 must_haves.
- Implement a per-ticket reply throttle as an independent loop-breaker.
- Replace 409-as-success with 409 → dead-letter until verified.
- Add `, id ASC` to the claim ORDER BY.
- In 02-06-T3, demonstrate the real exactly-once property (kill worker between POST and finalize).

### 5. Risk Assessment

**MEDIUM-HIGH** (would be MEDIUM with the CRITICAL fixed). Architecture & sequencing are sound; the team already iterated the idempotency design once. Risk concentrates in (1) the real crash-window hole in exactly-once that the test suite would let ship believed-correct, and (2) the concrete `list_updated_tickets` build gap blocking the poller. Both fixable with small Wave-0 + 02-02/04/05/06 additions. **Verdict: REVISE** before execution.

### Open Questions
- Does Freshdesk `POST /reply` accept a client idempotency token or return a stable reply id usable to detect a prior successful send? (Verify on sandbox — cleaner CRITICAL fix.)
- Does `GET /conversations` / `GET /tickets/{id}` expose raw RFC 3834 headers (A4)? Resolves whether loop-guard layer 1 is real or inert.
- Observed per-endpoint sub-limit for `POST /reply` (RESEARCH open Q4).

---

## Architect Review (systems architecture, Opus)

### 1. Summary

Well-structured, carefully sequenced plan for the project's first code phase. Macro architecture is sound: single isolated Freshdesk client, Postgres `SELECT ... FOR UPDATE SKIP LOCKED` queue, resolve-then-enqueue idempotency, config-driven send-mode switch — the right primitives to de-risk a 23k/week rollout. The dependency DAG across six plans is acyclic and wave ordering is correct. Concerns concentrate in three areas: (a) the loop-guard is applied in two places with a subtle semantic split risking a TOCTOU gap, (b) `main.py` co-locates pool + uvicorn + poller + worker with shared-pool assumptions that deserve an explicit boundary, and (c) the "Phase 3 pgvector co-location" claim is asserted but never exercised by any schema/migration decision. None blocking; all addressable within the current structure.

### 2. Strengths
- **Single Freshdesk seam genuinely enforced** — `freshdesk_io/client.py` is the only module with httpx auth + base_url; downstream plans consume via interface (02-02-PLAN.md:175).
- **Resolve-then-enqueue is the right idempotency design** (02-03:47-50, 02-05:73-80) — same helper, same key derivation, single UNIQUE index + `ON CONFLICT DO NOTHING`.
- **Claim/finalize uses claim_token correctly** (02-03:129-132) + stale recovery — forward-supports N-worker path without rework.
- **Send-mode switch designed as a real seam, not a flag** (02-04:144, D-05) — dry-run default + persisted would-be action is exactly what Phase 6/7 plug into.
- **PII-redaction-before-persist wired from day one** (D-12) — including non-obvious leak paths (`last_error` 02-03:131, `dry_run_log.body` 02-04:144).
- **Wave 0 RED-scaffold strategy excellent** — 7 import-clean deliberately-failing scaffolds; VALIDATION ties every task to a test with no MISSING references.
- **The two LOW-confidence external unknowns (D-07 sync-echo, raw headers) correctly isolated behind graceful-degradation defaults + human checkpoints** rather than blocking the build.

### 3. Concerns
- **`HIGH` — Loop-guard runs in two places with divergent semantics → TOCTOU gap + duplicated truth.** Resolve step inlines `incoming=true AND private=false` (02-05:77-78); worker re-runs `should_suppress` after re-fetching conversations (02-04:146-147). Layers 3/4 are evaluated twice via two code paths (drift risk), and a row enqueued for one inbound can be suppressed against a *different* latest inbound by the time the worker runs ("suppress, không đổi key", 02-04:146) — **silently dropping a real customer message** with no dead-letter/alert. For a quality-non-negotiable system a dropped reply is arguably worse than a duplicate and is currently unobservable.
- **`MEDIUM` — "Same Postgres that Phase 3 pgvector extends" is asserted but not architecturally established.** Only concrete forward-compat is the `pgvector/pgvector:pg16` image (02-01:116). No schema namespace decision; single shared asyncpg pool. Phase 3 embedding writes + ANN queries on the same pool/DB will contend with the latency-sensitive `SKIP LOCKED` claims. "One pool, one DB, public schema" is locked in by omission.
- **`MEDIUM` — `main.py` co-locates uvicorn + poller + single worker + stale-recovery in one asyncio process sharing one pool, with undefined back-pressure shape** (02-06:136-140). The webhook does an in-request `get_conversations` resolve before returning 200 (02-05:114); if that Freshdesk call is slow/rate-limited, webhook responses slow, Freshdesk re-fires (30-min retry, 1000/hr cap — 02-RESEARCH:351), risking a feedback loop. The research's "thin webhook + fat worker" pattern is explicitly abandoned (02-05:114) without trade-off analysis.
- **`MEDIUM` — Worker error-handling seam between 02-04 and 02-06 is a stringly-typed "if it exists" hook.** `to_dead_letter` doesn't exist until 02-06; at end of Wave 2 a fatal 404 burns 5 retries instead of going straight to DLQ. **Fix:** define a `DeadLetterSink` protocol in 02-04 (retry-only default), swap the real impl in 02-06.
- **`LOW` — Three independent timers (10-min stale lease / 5–15-min poller / 30-min webhook retry) with no coherence analysis.** Queue exactly-once doesn't guarantee Freshdesk exactly-once if a crash occurs between `post_reply` 200 and `finalize_done` commit — the classic dual-write problem. (Same root cause as the Critic's CRITICAL.)
- **`LOW` — 409 handling under-specified** (02-02:99) — unverified Freshdesk semantics; could mark a row `done` when no reply posted.
- **`LOW` — Exhausted-but-unlettered rows can silently stick.** A row reaching `attempts >= max_attempts` via `finalize_retry` that never gets dead-lettered (worker crash right after final increment) is filtered out of the claim query AND never moved to dead_letter. Stale-recovery only targets `status='claimed'`.

### 4. Suggestions
- **Unify the loop-guard into one evaluation point/code path.** Make `should_suppress` the single source of truth, called at resolve. If a worker re-check must suppress a row enqueued as valid, route to a distinct `status='stale_inbound'` + alert (not silent `suppressed`) so dropped replies are observable.
- **Record an explicit queue-vs-vector co-location decision** — put queue tables in a dedicated `queue` Postgres schema in 0001; document whether Phase 3 shares the pool or uses a separate pool/`statement_timeout`.
- **Decide the webhook resolve-in-request vs enqueue-thin trade-off explicitly** (timeout + fallback, or document the poller backstops it).
- **Make the dead-letter sink an injected protocol in 02-04** so fatal-404 → DLQ works even before 02-06.
- **Add a "post-succeeded-but-not-finalized" reconciliation check** (marker scan or `sent_at` + reply id persisted before finalize) — the only way exactly-once holds across a send/finalize crash. Add a sandbox crash-after-send test.
- **Add a sweeper for `status='pending' AND attempts>=max_attempts`** to stale-recovery so exhausted rows can't stick.
- **Verify 409 semantics on sandbox** before treating as success.

### 5. Risk Assessment

**MEDIUM (low-leaning).** Foundational architecture is correct; evidence of a prior review cycle that fixed the worst bug class (sentinel/re-key race). Safety primitives (dry-run default, bounded retry, dead-letter, loop-guard, PII redaction, sandbox-gated live send) all present and correctly placed. Not LOW because of three under-specified seams: (1) split loop-guard → silent dropped-reply path threatening the core value, (2) Phase-3 Postgres co-location asserted not designed, (3) the untested send/finalize crash gap that produces duplicate customer emails at scale. None block execution. Resolve the HIGH loop-guard concern + add post-vs-finalize reconciliation → drops to LOW.

---

## Consensus Summary

Two independent fresh-context reviewers (adversarial critic + systems architect) **agree the plans are well-structured, correctly sequenced (acyclic DAG, sensible waves), and that the resolve-then-enqueue idempotency design is the right call** — but both independently flag the **same single highest-stakes defect** and recommend **REVISE before execution**.

### Agreed Strengths (raised by both)
- Resolve-then-enqueue idempotency (D-02) is correct and robust — closes the webhook/poller duplicate-*enqueue* race; same key derived from same ticket state both paths.
- Single Freshdesk client seam is genuinely enforced; downstream plans consume via interface.
- Claim/finalize with `claim_token` + stale recovery is the textbook crash-safe pattern; forward-supports N-worker scaling.
- Send-mode switch (D-05) is a real forward seam for Phase 6 kill-switch / Phase 7 rollout, not a throwaway flag.
- PII-redaction-before-persist (D-12) wired from day one, including non-obvious leak paths.
- Wave 0 RED-on-purpose test scaffolding is disciplined; VALIDATION has no MISSING test references.
- The two LOW-confidence external unknowns (D-07, raw headers) correctly isolated behind graceful degradation + human checkpoints.

### Agreed Concerns (raised by both — HIGHEST PRIORITY)
1. **🔴 CRITICAL — Send/finalize crash window breaks true exactly-once (REP-05).** *Both reviewers, independently.* A crash (deploy/OOM/restart) between a successful `client.post_reply` (200 from Freshdesk) and the DB `finalize_done` leaves the row `claimed` → stale-recovery → re-claim → **second real reply to the customer**. The D-02 key dedups *enqueue*, not *send-on-re-claim*; `ON CONFLICT` never fires on an existing row. This is the exact failure the phase exists to prevent, and it is **asserted as solved but never tested** (tests cover enqueue-dedup only). **Required fix:** persist send-intent transactionally (`sent_at` + `freshdesk_reply_id` column, skip-to-finalize on re-claim) and/or a pre-send marker existence check via `GET /conversations`; add a crash-after-post mock-HTTP test (CI, no sandbox needed).
2. **🟠 409 handling is an unverified guess** — both flag treating Freshdesk `POST /reply` 409 as "success/duplicate" as unsafe; verify on sandbox or treat as fatal → dead-letter.
3. **🟠 Exactly-once is tested only at the queue/enqueue layer** — both note the sandbox demo re-drives *intake*, never the dangerous post-then-crash path.

### Additional High/Major (each raised once, both worth acting on)
- **🟠 (Critic) Missing client capability** — `list_updated_tickets()` + `Ticket` model are required by the 02-05 poller but never built in 02-02. Concrete build blocker for half of criterion #1.
- **🟠 (Critic) Poller window not durable** — in-memory only, no checkpoint table/migration; loses dropped events across a restart, defeating the reconciliation safety-net.
- **🟠 (Architect) Loop-guard split semantics / TOCTOU** — resolve-step inline filter vs worker `should_suppress` can **silently drop a real customer reply** on state change, with no alert. Threatens "answer quality is non-negotiable."
- **🟡 (Architect) Phase-3 pgvector co-location asserted, not designed** — single shared pool/`public` schema locked in by omission; contention risk two phases out. Cheap to fix now (dedicated `queue` schema + recorded decision).
- **🟡 (Architect) Webhook resolves in-request** — blocking outbound Freshdesk call before returning 200 risks a re-fire feedback loop under slowness.
- **🟡 (Architect) `to_dead_letter` "if it exists" hook** — make it an injected `DeadLetterSink` protocol so fatal-404 → DLQ works at Wave 2.

### Divergent Views
- **Overall severity:** Critic rates **MEDIUM-HIGH** (CRITICAL hole would ship believed-correct due to the test gap); Architect rates **MEDIUM (low-leaning)** (sound foundation, fixes are local). Both converge on **REVISE, not block** — the disagreement is only on how loud the alarm should be. Given REP-05 is the phase's reason to exist and the failure produces duplicate customer emails at volume, treat the crash-window fix as a **mandatory pre-execution revision**.
- **Loop-guard framing:** Critic frames it as *layers going inert* (headers not exposed → guard weaker than advertised, risk = missed suppression / loop); Architect frames it as *split evaluation* (TOCTOU → risk = silently dropped valid reply). These are complementary, not contradictory — a single unified `should_suppress` evaluation point + a per-ticket reply throttle + observable `stale_inbound` status addresses both.

### Recommended Action
Run **`/gsd-plan-phase 2 --reviews`** to fold this feedback into a plan revision. Minimum bar before executing Wave 0:
1. Close the send/finalize crash window (transactional send-intent + pre-send check) — **mandatory**.
2. Add `list_updated_tickets` + `Ticket` to 02-02 — **mandatory** (poller blocker).
3. Add a durable `poller_checkpoint` table to migration 0001 — **mandatory** (safety-net integrity).
4. Unify the loop-guard to one evaluation point + observable `stale_inbound` + per-ticket reply throttle.
5. Decide 409 handling (verify-or-dead-letter) and record the Phase-3 Postgres schema/pool co-location decision.
6. Add the three RED tests in Wave 0: `test_worker_crash_after_post_does_not_resend`, `test_poller_window_persists_across_restart`, `test_list_updated_tickets`.
