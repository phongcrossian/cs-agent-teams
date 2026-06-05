---
phase: 04-reply-pipeline-classify-extract-ground-draft-safety-guards
plan: "06"
reviewed: 2026-06-05T08:25:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/test_tickets_run.py
  - scripts/test_test_tickets_run.py
  - .claude/commands/test-ticket.md
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 04 Plan 06: Code Review Report

**Reviewed:** 2026-06-05T08:25:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Plan 04-06 repackages the Phase-4 validation harness into an on-demand `/test-ticket` command.
The three deliverables — the `run` subcommand engine, six unit tests, and the thin slash wrapper —
are functionally sound at the happy path. The DRY_RUN guarantee is correctly asserted in both
`run_ai_team` (line 398) and `run()` (line 1216); no Freshdesk POST path was introduced.
The `_SUBTYPE_TEMPLATES` deterministic map is intact; the free-pick anti-pattern (T-04.06-05)
is not reintroduced.

Key defects found: (1) `_load_env_prd()` raises an unguarded `FileNotFoundError` when `.env.prd`
is absent from all parent directories — the walk-up loop exits without updating `candidate`, so
`candidate.read_text()` crashes with an opaque OS error; (2) `collect()` was **not** refactored to
call `_process_row()` as both the plan and SUMMARY claim — the per-ticket body is fully duplicated,
creating a latent correctness risk; (3) `time.sleep(0.3)` inside async loops blocks the event
loop; (4) `_apply_caps` attributes dropped-row buckets misleadingly under `--limit`-only mode.

---

## Critical Issues

### CR-01: `_load_env_prd()` raises bare `FileNotFoundError` when `.env.prd` is absent everywhere

**File:** `scripts/test_tickets_run.py:80-96`

**Issue:** The walk-up loop searches parent directories for `.env.prd` but only updates `candidate`
when a match is found. When no match is found, `candidate` retains the original value
(`_REPO_ROOT / ".env.prd"`), and line 91 calls `candidate.read_text()` unconditionally — raising
a bare `FileNotFoundError` with no diagnostic message about what is missing or where to put it.
In a fresh clone, a CI environment, or any git worktree where the walk-up reaches `/` without
finding the file, the user gets an OS traceback rather than an actionable error.

**Fix:** After the walk-up loop, check `candidate.exists()` before reading and raise an explicit
error if absent:

```python
def _load_env_prd() -> dict[str, str]:
    candidate = _REPO_ROOT / ".env.prd"
    if not candidate.exists():
        for parent in _REPO_ROOT.parents:
            alt = parent / ".env.prd"
            if alt.exists():
                candidate = alt
                break
    if not candidate.exists():
        raise FileNotFoundError(
            f".env.prd not found in {_REPO_ROOT} or any parent directory. "
            "Copy it from the main repo root or set FRESHDESK_DOMAIN / "
            "FRESHDESK_API_KEY in your environment."
        )
    env: dict[str, str] = {}
    for line in candidate.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env
```

---

### CR-02: `collect()` was NOT refactored to use `_process_row()` — plan claim contradicts code

**File:** `scripts/test_tickets_run.py:459-508`

**Issue:** The 04-06-SUMMARY.md (line 63) states: *"`_process_row` extracted as shared coroutine:
both `collect()` and `run()` call it."* The plan task (04-06-PLAN.md Task 2) explicitly requires:
*"Prefer extracting the per-ticket body of `collect()` into a shared coroutine (`_process_row`)
that BOTH `collect` and `run` call, rather than duplicating it."*

The actual code shows `collect()` (lines 459–508) still contains its own full inline per-ticket
pipeline (`fetch_conversation` → `fetch_selless_order` → `run_ai_team` → manual record assembly).
`_process_row` (lines 1146–1196) exists and `run()` calls it, but `collect()` does not. The two
implementations are near-identical today but can drift silently — any future field addition or bug
fix applied to `_process_row` will not be reflected in `collect()`, and no test exercises both
paths against each other.

**Fix:** Replace the inline per-ticket body in `collect()` with a call to `_process_row()`:

```python
async def collect(per_cat: int, only_tid: str | None, only_cat: str | None) -> None:
    env = _load_env_prd()
    domain, key = env["FRESHDESK_DOMAIN"], env["FRESHDESK_API_KEY"]
    cats = [only_cat] if only_cat else list(_CSV.keys())
    records: list[dict] = []
    sclient = httpx.AsyncClient(base_url=_SELLESS_BASE, timeout=20)
    with httpx.Client() as client:
        for cat in cats:
            rows = _select(cat, per_cat, only_tid)
            print(f"== {cat}: {len(rows)} ticket(s) ==", flush=True)
            for i, row in enumerate(rows, 1):
                tid = (row.get("Ticket ID") or "").strip()
                if not tid:
                    continue
                rec = await _process_row(row, client, sclient, domain, key, cat)
                records.append(rec)
                await asyncio.sleep(0.3)  # see WR-01
    await sclient.aclose()
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"DONE {len(records)} records -> {_DATA_PATH}", flush=True)
```

---

## Warnings

### WR-01: `time.sleep()` inside async functions blocks the entire event loop

**File:** `scripts/test_tickets_run.py:503, 1268`

**Issue:** Both `collect()` (line 503) and `run()` (line 1268) call `time.sleep(0.3)` inside
`async def` coroutines driven by `asyncio.run()`. `time.sleep` is a blocking call that suspends
the OS thread for 300 ms per ticket, preventing the event loop from driving any pending I/O
(Selless response reads, subprocess stdout draining) during that window. For a 30-ticket run this
wastes ~9 s of wall time with no yield to the event loop.

**Fix:** Replace both occurrences with `await asyncio.sleep(0.3)`:

```python
# In both collect() and run():
await asyncio.sleep(0.3)
```

---

### WR-02: `_apply_caps` misattributes dropped-row buckets under `--limit`-only mode

**File:** `scripts/test_tickets_run.py:1135-1141`

**Issue:** When `per_cat=None` and only `limit` is applied, the function trims from the tail of
the input list. Given 5 Complaint rows followed by 5 Inquiry rows with `limit=4`, the dropped
report is `{'Complaint': 1, 'Inquiry': 5}` — Inquiry appears nearly entirely dropped even though
the cut is bucket-agnostic. The D-43 requirement is that drops are "logged (count + buckets)";
a skewed report misleads operators reviewing the log.

**Fix:** Either document this input-order dependency explicitly in the docstring, or apply a
round-robin interleaving before trimming so the limit distributes evenly across buckets:

```python
# Apply global limit using round-robin to distribute evenly
if limit is not None and len(selected) > limit:
    by_b: dict[str, list[dict]] = {}
    for r in selected:
        by_b.setdefault(r.get("Level_in") or "unknown", []).append(r)
    interleaved: list[dict] = []
    queues = list(by_b.values())
    while len(interleaved) < limit and any(queues):
        for q in queues:
            if q and len(interleaved) < limit:
                interleaved.append(q.pop(0))
    over = [r for q in queues for r in q]
    for r in over:
        b = r.get("Level_in") or "unknown"
        dropped_report[b] = dropped_report.get(b, 0) + 1
    selected = interleaved
```

---

### WR-03: `_select()` opens a file handle without a context manager (resource leak)

**File:** `scripts/test_tickets_run.py:451`

**Issue:** `csv.DictReader(open(_CSV[category], newline="", encoding="utf-8"))` opens a file
handle that is never explicitly closed. Under normal execution Python's reference counting closes
it immediately after `list()` is evaluated, but under exception paths the handle leaks until GC
runs. This is flagged as `ResourceWarning` in test mode (`-W error::ResourceWarning`).

**Fix:**

```python
with open(_CSV[category], newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
```

---

### WR-04: `--per-cat 0` and `--limit 0` are silently accepted and drop all tickets

**File:** `scripts/test_tickets_run.py:1279-1306`

**Issue:** `argparse` accepts any integer for `--per-cat` and `--limit`. Passing `0` causes
`_apply_caps` to select zero rows and emit only a drop-count log. The user sees
`"[run] Cap applied: 0 selected, N dropped"` and gets an empty xlsx — indistinguishable from a
genuine zero-match result. A typo like `--per-cat 0` (intending `--per-cat 10`) silently
processes nothing.

**Fix:** Validate in `main()` after parsing:

```python
elif args.cmd == "run":
    if args.per_cat is not None and args.per_cat <= 0:
        print("ERROR: --per-cat must be >= 1.", file=sys.stderr)
        sys.exit(1)
    if args.limit is not None and args.limit <= 0:
        print("ERROR: --limit must be >= 1.", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run(args.ticket_id, args.list_path, args.limit, args.per_cat))
```

---

## Info

### IN-01: `category_hint or None` is a no-op in `_process_row`

**File:** `scripts/test_tickets_run.py:1174`

**Issue:** `run_ai_team(ticket, selless, category_hint or None)` — by the time execution reaches
line 1174, `category_hint` is either a non-empty string or `None` (the empty-string case is
already converted to `None` at line 1263). The `or None` suffix is therefore a no-op that adds
visual noise and may mislead readers into thinking it performs a meaningful transformation.

**Fix:** Remove the `or None`:

```python
ai = await run_ai_team(ticket, selless, category_hint)
```

---

### IN-02: `test_apply_caps_limit` declares `tmp_path` fixture but never uses it

**File:** `scripts/test_test_tickets_run.py:129`

**Issue:** `def test_apply_caps_limit(tmp_path: Path)` requests the `tmp_path` pytest fixture but
the test body creates no files and never references `tmp_path`. pytest injects and creates a
temporary directory unconditionally, wasting I/O on every test run.

**Fix:** Remove the `tmp_path` parameter:

```python
def test_apply_caps_limit() -> None:
```

---

### IN-03: `_parse_draft_json` JSON extraction uses an O(n²) backward scan (pre-existing)

**File:** `scripts/test_tickets_run.py:729-738`

**Issue:** The final fallback in `_parse_draft_json` iterates `range(len(s), start, -1)` — up to
n candidate slices of length 1…n — to find the largest balanced `{…}`. This pre-dates Plan 04-06
and is not new code. For the harness's typical model output sizes (< 10 KB) this has no practical
impact, but `_iter_json_objects` (lines 218–253) — added in an earlier pass — is an O(n) brace-
matching alternative that already handles the same problem more correctly. The `draft` subcommand
could adopt it instead of carrying this fallback forward.

---

_Reviewed: 2026-06-05T08:25:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
