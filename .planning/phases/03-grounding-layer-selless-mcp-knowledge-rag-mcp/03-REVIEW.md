---
phase: 03-grounding-layer-selless-mcp-knowledge-rag-mcp
reviewed: 2026-06-02T07:35:00Z
depth: standard
files_reviewed: 35
files_reviewed_list:
  - src/config.py
  - src/ingest/sources.py
  - src/ingest/normalize.py
  - src/ingest/chunk.py
  - src/ingest/pipeline.py
  - src/ingest/cli.py
  - src/knowledge_mcp/embeddings.py
  - src/knowledge_mcp/models.py
  - src/knowledge_mcp/retrieval.py
  - src/knowledge_mcp/exact.py
  - src/knowledge_mcp/conflict.py
  - src/knowledge_mcp/server.py
  - src/selless_mcp/errors.py
  - src/selless_mcp/models.py
  - src/selless_mcp/client.py
  - src/selless_mcp/whitelist.py
  - src/selless_mcp/audit.py
  - src/selless_mcp/server.py
  - migrations/versions/0002_knowledge_schema.py
  - migrations/versions/0003_selless_audit.py
  - tests/conftest.py
  - tests/ingest/test_pipeline.py
  - tests/ingest/test_idempotent.py
  - tests/knowledge_mcp/test_semantic.py
  - tests/knowledge_mcp/test_exact.py
  - tests/knowledge_mcp/test_conflict.py
  - tests/knowledge_mcp/test_override.py
  - tests/selless_mcp/test_tools.py
  - tests/selless_mcp/test_resolve_scope.py
  - tests/selless_mcp/test_whitelist.py
  - tests/selless_mcp/test_audit.py
  - tests/selless_mcp/test_rate_limit.py
  - tests/selless_mcp/test_ticket_history.py
  - tests/smoke/test_grounding_demo.py
  - README-grounding.md
findings:
  critical: 2
  warning: 8
  info: 6
  total: 16
status: blockers_resolved
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-02T07:35:00Z
**Depth:** standard
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Reviewed the Phase-3 grounding layer: two MCP servers (Selless transactional + Knowledge RAG)
and the ingest pipeline. The security posture is generally sound on the dimensions the phase
prioritized: the D-04 field whitelist is genuinely explicit-extraction (no `**raw` spread), all
SQL in the audit writer, ingest upserts, exact lookups, and hybrid retrieval is `$N`
parameterized (no f-string SQL injection), and content-hash idempotency is correct.

However, the adversarial pass surfaced two BLOCKER-class defects that defeat security/correctness
guarantees the code claims to provide:

1. The D-14 override path (`apply_override`) is **dead on real data** — it only recovers
   conflict IDs from a `snapshot_version` prefix (`"conflict:..."`) that the ingest pipeline
   never writes. CS-Lead overrides will silently never apply in production despite passing tests.
2. The token-bucket rate limiter (D-08) is **not concurrency-safe across the refill arithmetic**
   under the documented goal, and more importantly the AuditMiddleware swallows the security audit
   write on any failure, meaning a failed/attacked tool call can produce **no audit row at all** —
   the audit trail is best-effort, not guaranteed, which contradicts the SEL-04/D-07 "every call
   is audited" contract.

Plus eight warnings (notably: `caller` never propagated to audit rows; `redact_text` only redacts
result field *names* but the raw input arguments dict — which contains PII — is redacted by a
generic Presidio pass that may miss order codes/IDs; SVG/PDF extraction silently degrades; bare
`except Exception` masking in several spots).

## Critical Issues

### CR-01: D-14 override resolution is dead code on real ingested data — RESOLVED (2026-06-02)

**Resolution commit:** `e2619b0` `fix(03): CR-01 — wire D-14 override to real ingest data via Citation.conflict_id`
**Resolution summary:** Added `Citation.conflict_id` field; added `_PROSE_CONFLICT_MAP` in `sources.py` mapping prose source filenames to CONTRA-* IDs; `ingest_all()` carries `conflict_id` into `kb_chunk.metadata` JSONB; `assemble_citations()` reads it from metadata; `_extract_conflict_ids()` reads `c.conflict_id` directly. False-green tests replaced with four integration tests driving the override through real pipeline-shaped DB rows. All 144 tests pass (4 sandbox skipped).

**File:** `src/knowledge_mcp/conflict.py:61-79`, `126-153`; `src/ingest/pipeline.py:185-209`
**Issue:**
`apply_override()` (D-14) discovers which conflicts to resolve by calling
`_extract_conflict_ids(citations)`, which only extracts an ID when a citation's
`snapshot_version` *starts with the literal prefix* `"conflict:"`:

```python
sv = c.snapshot_version or ""
if sv.startswith("conflict:"):
    parts = sv.split(":", 2)
    ...
```

But the ingest pipeline writes `snapshot_version = run_id` for every prose chunk:

```python
# pipeline.py upsert_chunk
VALUES ($1, ..., $9)   # $9 = run_id, e.g. "20260602T..." or "test-run-1"
```

Nothing in the ingest path ever produces a `snapshot_version` of the form
`"conflict:<CONTRA-ID>:<run_id>"`. The kb_chunk rows also do not carry `conflict_id`
at all (the column exists only on `policy_threshold`, not `kb_chunk` — see
`migrations/versions/0002_knowledge_schema.py:46-62`). Therefore on real data
`_extract_conflict_ids()` always returns `[]`, `apply_override()` returns early with
`resolved_by_override=False`, and the `policy_resolution` table is **never queried**.

The D-14 tests pass only because they hand-craft citations with
`snapshot_version=f"conflict:{conflict_id}:snap-001"` (`tests/knowledge_mcp/test_override.py:44`),
a shape the production pipeline cannot generate. This is a false-green: a CS-Lead ruling in
`policy_resolution` will silently never reorder citations in production, so conflicting policy
passages are surfaced in arbitrary RRF order with no override applied — exactly the failure D-14
exists to prevent.

**Fix:** Make the conflict-ID linkage real. Carry `conflict_id` into the kb_chunk metadata at
ingest (the prose record has no conflict_id today; derive it the same way thresholds do via
`_THRESHOLD_CONFLICT_MAP`, or join prose source → conflict via CONFLICT-INVENTORY), and read it
from `Citation` metadata rather than abusing `snapshot_version`. For example, add a
`conflict_id: Optional[str]` field to `Citation`, populate it in `assemble_citations()` from the
row's `metadata`/dedicated column, and have `_extract_conflict_ids` read `c.conflict_id`:

```python
# models.py Citation
conflict_id: Optional[str] = None

# retrieval.assemble_citations
conflict_id=(row.get("metadata") or {}).get("conflict_id"),

# conflict._extract_conflict_ids
ids = [c.conflict_id for c in citations if c.conflict_id]
```

Then ingest must actually write `metadata={"conflict_id": ...}` for chunks tied to a CONTRA.
Add an integration test that ingests real snapshots and asserts `resolved_by_override=True`
after seeding a `policy_resolution` row — not a hand-built `conflict:` snapshot_version.

### CR-02: AuditMiddleware silently drops the audit row on any write failure — audit trail is not guaranteed — RESOLVED (2026-06-02)

**Resolution commit:** `c19f99e` `fix(03): CR-02 — audit trail fail-closed; pool-unset is explicit not silent`
**Resolution summary:** Removed try/except around `conn.execute` — INSERT failures now propagate as exceptions. Pool-unset path now raises `RuntimeError` unless `_audit_test_bypass=True` (test-only flag). `set_audit_pool()` gains `_test_bypass` kwarg (default False). `assert_audit_pool_configured()` added for server startup enforcement. `AuditMiddleware` finallyblock lets `_write_audit_row` exceptions propagate (fail-closed). Two new tests: `test_audit_fail_closed_on_insert_error` and `test_audit_fail_closed_no_pool_production_mode`. WR-01 partially addressed: caller now extracted from `context.client_id`. All 144 tests pass.

**File:** `src/selless_mcp/audit.py:101-118`, `134-165`
**Issue:**
SEL-04/D-07 states "every Selless MCP tool call writes a PII-redacted audit row." The
implementation makes this best-effort, not guaranteed, in two compounding ways:

1. `_write_audit_row` wraps the INSERT in `try/except Exception` and only logs on failure
   (lines 116-118). A DB outage, a constraint violation, a serialization failure, or the pool
   being momentarily unavailable means **the tool call still returns data to the drafter with no
   audit record written**. For a layer whose entire justification is "scoped + audited" access
   to customer data, a silently-missing audit row is a security/compliance defect, not a
   robustness nicety.

2. `_write_audit_row` returns early (no row) when `_pool is None` (lines 94-99). In production,
   `set_audit_pool()` is only ever called from server startup; if that wiring is missed or the
   server is exercised via the `_impl_*` functions (as all tests and the smoke demo do), tool
   calls execute and return PII-bearing results with **zero** audit rows and only a `debug` log.
   There is no guard that refuses to serve data when auditing is unavailable.

Combined effect: it is possible to read whitelisted-but-still-PII customer order/email data
through this boundary with no durable audit record, which directly contradicts the documented
D-07 contract.

**Fix:** Decide the failure policy explicitly and enforce it. If auditing is mandatory (the
stated contract), audit failures must be loud — at minimum re-raise after logging, or mark the
result as un-served. A safer pattern: write the audit row in the same code path that returns the
result and fail-closed when the pool is unset in a non-test context:

```python
async def _write_audit_row(...):
    pool = get_audit_pool()
    if pool is None:
        raise RuntimeError("audit pool not configured — refusing to serve Selless data unaudited (D-07)")
    async with pool.acquire() as conn:
        await conn.execute(... )   # let failures propagate; do NOT swallow
```

If best-effort is genuinely acceptable, the D-07 docstring/CLAUDE constraint must be downgraded
and the "every call is audited" language removed. As written, code and contract disagree.

## Warnings

### WR-01: `caller` is never populated by AuditMiddleware — audit rows always have caller=NULL

**File:** `src/selless_mcp/audit.py:159-165`
**Issue:** `AuditMiddleware.on_call_tool` calls `_write_audit_row(...)` without passing `caller`,
so it defaults to `None`. The `audit.selless_audit.caller` column and the smoke test
(`tests/smoke/test_grounding_demo.py:334`) both treat `caller` as meaningful, but in the real
middleware path it is always NULL. Audit rows therefore cannot attribute a call to a client
identity — limiting forensic value of the D-07 trail.
**Fix:** Extract a caller/client identity from `context` (e.g. MCP client info / transport
metadata) and pass it through, or document explicitly that `caller` is reserved-and-unused in
Phase 3 and remove it from the smoke assertion to avoid implying it is wired.

### WR-02: AuditMiddleware redacts result field *names* but relies on a generic Presidio pass to scrub raw input args

**File:** `src/selless_mcp/audit.py:139-157`, `59-72`
**Issue:** `raw_key = str(context.message.arguments or {})` captures the full tool arguments
(e.g. `{'param': 'jane.doe@example.com'}` or `{'order_id': '14sv5kq2...'}`). This is then passed
to `redact_text()`. Presidio reliably catches EMAIL_ADDRESS/PHONE, but Selless **order codes and
internal IDs** (`25044-67`, `14sv5kq2iec4to48u4nbcllai`) are not standard PII entities and will
pass through unredacted into `input_key`. The smoke test even acknowledges this
(`test_grounding_demo.py:355-358`: "The order_id itself is not PII"). That may be acceptable, but
the module docstring claims "input_key (redacted)" unconditionally. Meanwhile `_summarize_result`
deliberately records only field *names*, so the asymmetry (args fully stringified, results
name-only) is undocumented and easy to regress.
**Fix:** Either (a) record only the *argument key names* for `input_key` (mirroring
`_summarize_result`) so raw values never reach the table, or (b) add an explicit allow-list of
which arg values may be stored and document that order codes/IDs are intentionally retained.

### WR-03: Token-bucket refill uses `time.monotonic()` deltas but the limiter instance is constructed at import time from settings — config changes and burst=0 edge cases

**File:** `src/selless_mcp/server.py:60-105`, `150-158`
**Issue:** Two issues in the D-08 limiter:
1. The middleware is instantiated once at module import (`mcp.add_middleware(_TokenBucketRateLimiter(...))`)
   reading `settings` at import time. Any later settings override (tests, reconfiguration) does
   not affect the wired limiter. Tests sidestep this by constructing their own limiter, so the
   *server's actual* limiter is never asserted with real config.
2. With `burst_capacity=0`, `_tokens` initializes to `0.0` and `_acquire()` can still admit a
   request after enough wall-clock elapsed because refill is capped at `float(self._burst)=0` —
   so it will never admit (correct), but the constructor allows a `burst` of 0 paired with any
   `rps`, producing a limiter that rejects everything regardless of rps. There is no validation
   that `burst >= 1` when `rps > 0`.
**Fix:** Validate `burst_capacity >= 1` (or document burst=0 = "deny all"), and consider building
the limiter lazily / from a settings reference so reconfiguration is honored. Add a test that
asserts the *server-mounted* limiter reflects `settings.selless_rate_limit_burst`.

### WR-04: `_extract_svg_text` / `_extract_pdf_text` silently return empty string on failure — ingest can produce an empty KB with no hard error

**File:** `src/ingest/sources.py:77-116`, `124-143`; `src/ingest/pipeline.py:80-100`
**Issue:** Both extractors catch broadly and return `""` on any problem (missing `pdfminer`,
unreadable SVG, parse failure). `read_prose_sources()` then simply skips empty bodies, and
`ingest_all()` proceeds with `all_chunks` possibly empty, logging success with `kb_chunk=0`.
The CLI prints "Ingest complete" with 0 chunks. For a system whose core value is "nothing ships
until quality bar is cleared," a silent empty-knowledge ingest is a dangerous quiet failure —
the RAG store would return no citations and the drafter would have nothing to ground on.
**Fix:** Have `ingest_all()` (or the CLI) treat `kb_chunk == 0` as an error/non-zero exit when
prose sources exist, and surface a distinct warning when `pdfminer` is missing rather than
burying it in per-file logs. At minimum, fail the CLI run loudly if WorkFlow.svg yielded no text.

### WR-05: `datetime.datetime.utcnow()` is deprecated and naive — run_id timestamps

**File:** `src/ingest/cli.py:87`
**Issue:** `datetime.datetime.utcnow()` is deprecated as of Python 3.12+ (the project targets
`requires-python >=3.14`, `pyproject.toml:9`) and returns a naive datetime. Under 3.14 this emits
a DeprecationWarning and the produced `run_id` (used as `snapshot_version`) is timezone-ambiguous.
**Fix:** Use `datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")`.

### WR-06: `resolve_order` length guard counts characters, not exactness — a 3+ char substring still hits the live search endpoint

**File:** `src/selless_mcp/client.py:346-386`
**Issue:** D-03 mandates exact-key-only, never fuzzy/browse. `HttpSellessClient.resolve_order`
enforces only `len(param) >= 3` then calls `/po/search?param=<param>&take=1`. If the live Selless
`/po/search` does prefix/substring matching, a partial param (e.g. `"2504"`) would return *some*
order with `take=1`, and the client would happily wrap the first result as a confident
single-identity `ResolvedOrder`. The "exactness" is assumed to be enforced by the remote endpoint,
which is unverified (the gateway-trust model also means no auth scoping). The MockSellessClient
enforces exact match, so tests do not exercise the substring-leak risk.
**Fix:** After fetching, verify the returned `code`/`customer_email` *exactly equals* the input
`param` (case-normalized) before returning; otherwise raise the no-match `ValueError`. This makes
the MCP the enforcer of D-03 exactness rather than trusting the upstream search semantics.

### WR-07: `_impl_get_ticket_history` casts `fd_ticket_id` to `int()` without guarding non-numeric values

**File:** `src/selless_mcp/server.py:211`
**Issue:** `await fd.get_ticket(int(fd_ticket_id))`. The mapping value comes from the Selless
ticket-do endpoint JSON. If `fd_ticket_id` is a non-numeric string, `None` was already handled,
but a value like `"368108x"` or a dict raises `ValueError`/`TypeError` that is not classified or
audited as a ticket-history-specific failure — it propagates raw. Given Freshdesk conversation
IDs are bigint (per project memory), a value exceeding/looking unusual should be validated.
**Fix:** Wrap the cast: `try: fd_id = int(fd_ticket_id) except (TypeError, ValueError): raise
ValueError(f"non-numeric fd_ticket_id {fd_ticket_id!r} for order {order_id!r}")`.

### WR-08: `_selless_wait` backoff can return a negative delay

**File:** `src/selless_mcp/client.py:41-48`
**Issue:** For the first retry, `attempt = 1`, `base = min(2**1, 60) = 2`, then
`return base + random.uniform(-1.0, 1.0)` can be as low as `1.0` (fine), but the jitter is
`uniform(-1.0, 1.0)` regardless of base; if a future change lowered base or attempt math shifted,
the function could return a value < 0, which tenacity would treat as 0/negative sleep. More
concretely, the jitter is not proportional and `2**attempt` grows unbounded before the `min(...,60)`
only caps the base, not the jittered result — acceptable today but fragile.
**Fix:** Clamp the result: `return max(0.0, base + random.uniform(-1.0, 1.0))`, and consider
proportional jitter (`base * random.uniform(0.5, 1.5)`).

## Info

### IN-01: Unused `os` import in ingest sources

**File:** `src/ingest/sources.py:26`
**Issue:** `src/ingest/sources.py` imports `os` but never references it (verified: no `os.` usage in the file). Dead import. (`cli.py` uses both `os` and `sys`, so those are fine.)
**Fix:** Remove the unused `import os` from `sources.py`.

### IN-02: `inspect.isawaitable` bridging pattern duplicated across modules

**File:** `src/ingest/pipeline.py:107-112`, `src/knowledge_mcp/retrieval.py:125-127`
**Issue:** The sync-stub-vs-async-prod bridge (`inspect.isawaitable`) is copy-pasted. The
underlying cause is that `embed_query`/`embed_documents` are declared `async` but tests
monkeypatch them with sync lambdas (`conftest.py:130-131`), forcing every caller to handle both.
This is a code smell that invites a caller to forget the bridge and `await` a list.
**Fix:** Make the stub async too (`lambda` → `async def` or wrap), or provide a single
`await_maybe()` helper, so production callers can `await` unconditionally.

### IN-03: `_extract_template_code` returns the code itself, ignoring the linked template reference

**File:** `src/ingest/sources.py:380-386`
**Issue:** `_extract_template_code(template_ref, code)` ignores `template_ref` entirely (except for
TBD/N/A sentinels) and returns `code`. The docstring says it extracts the template code from the
reference, but it does not parse the reference at all. This makes `code_map.template_code` always
equal `code`, which is likely not the intended mapping (a workflow code C1 may link to template B8).
**Fix:** Actually parse `template_ref` for the linked template code; fall back to `code` only when
no reference is present.

### IN-04: HNSW + zero-vector embeddings make stub-based semantic tests effectively FTS-only

**File:** `tests/knowledge_mcp/test_semantic.py`, `tests/smoke/test_grounding_demo.py:200-205`
**Issue:** With `stub_embedder` returning all-zero 1024-d vectors, cosine distance is undefined,
so the vector ANN arm returns nothing and RRF fusion is driven entirely by FTS. The smoke test
comments acknowledge this. The result: the vector-search half of "hybrid" retrieval is never
exercised by any non-sandbox test, so RRF fusion correctness over *two* populated arms is unverified.
**Fix:** Add a unit test for `_rrf_fuse` that feeds two non-trivial rank lists (it is a pure
function) to verify fusion ordering independent of the DB/embeddings.

### IN-05: `metadata` stores `recency_flag` redundantly with the dedicated column

**File:** `src/ingest/pipeline.py:126`, `migrations/versions/0002_knowledge_schema.py:52-56`
**Issue:** `recency_flag` is written both as a first-class column and inside `metadata` JSON
(`metadata={"recency_flag": chunk["recency_flag"]}`). Two sources of truth invite drift; retrieval
reads the column, not the JSON.
**Fix:** Drop `recency_flag` from `metadata` and keep only the column, or reserve `metadata` for
genuinely free-form fields.

### IN-06: pytest marker `sandbox` used but only `sandbox` registered; smoke file mentions criteria not enforced by markers

**File:** `pyproject.toml:40-42`, `tests/smoke/test_grounding_demo.py:384`
**Issue:** Minor — the marker description says "real Freshdesk sandbox" but the Phase-3 sandbox
test exercises Selless + Voyage, not Freshdesk. Harmless but misleading.
**Fix:** Broaden the marker description to "real external-API sandbox smoke tests."

---

_Reviewed: 2026-06-02T07:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
