---
phase: 2
slug: freshdesk-i-o-layer-pipeline-backbone
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (uv-managed) |
| **Config file** | `pyproject.toml` — none yet, Wave 0 installs |
| **Quick run command** | `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds (mocked HTTP via respx; no network) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green + Freshdesk sandbox smoke test passes
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | REP-05 | — | Reply posted into correct existing ticket, exactly once | integration | `pytest tests/test_queue.py tests/test_client.py -x` | ❌ W0 | ⬜ pending |
| TBD | — | — | REP-05 | — | Retry / duplicate inbound never produces a second send | integration | `pytest tests/test_queue.py::test_idempotency -x` | ❌ W0 | ⬜ pending |
| TBD | — | — | REP-05 | — | Rate limit + `Retry-After` honored, exhaustion → dead-letter | unit | `pytest tests/test_client.py::test_retry_after -x` | ❌ W0 | ⬜ pending |
| TBD | — | — | REP-05 (crit #4) | — | Auto-reply / no-reply / sync-echo never triggers a send | unit | `pytest tests/test_loop_guard.py -x` | ❌ W0 | ⬜ pending |
| TBD | — | — | REP-05 (crit #2) | — | Real `POST /reply` works on sandbox (D-03) | smoke (manual) | `pytest tests/test_e2e_sandbox.py -m sandbox` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task IDs are filled by the planner once PLAN.md files exist.*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — pytest config + dependency declarations (uv)
- [ ] `docker-compose.yml` — Postgres 16 (pgvector-ready) for local dev/test
- [ ] `tests/conftest.py` — asyncpg pool fixtures, respx HTTP mocks, test DB setup
- [ ] `tests/test_client.py` — FreshdeskClient unit tests (respx mock) for REP-05
- [ ] `tests/test_queue.py` — SKIP LOCKED dedup, idempotency, dead-letter, stale recovery
- [ ] `tests/test_webhook.py` — webhook secret/HMAC verify + enqueue flow
- [ ] `tests/test_loop_guard.py` — RFC 3834 headers, sender patterns, source/actor (D-06/D-07)
- [ ] `tests/test_e2e_sandbox.py` — real Freshdesk sandbox smoke tests (marked `sandbox`)
- [ ] spaCy model install: `python -m spacy download en_core_web_lg` (Presidio backend)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real reply posts into a live sandbox ticket (D-03) | REP-05 (crit #2) | Requires a real Freshdesk sandbox account + live API key with reply scope; cannot run in CI | Flip send-mode to `live-send`, run `pytest -m sandbox`, confirm reply appears on the target ticket and a re-run does NOT post a second reply |
| D-07 sync-echo distinguishability | REP-05 (crit #4) | Needs a real Selless→Freshdesk sync update to inspect `user_id`/`from_email` actually stamped | Trigger a Selless sync, `GET /tickets/{id}/conversations`, record whether source/actor distinguishes sync-origin; if not, activate marker/tag fallback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
