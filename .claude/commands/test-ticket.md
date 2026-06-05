# /test-ticket — On-demand ticket validation (D-41)

Run any ticket through the real cs-agent-team (DRY_RUN, read-only PROD) and
write the result to `test-tickets.xlsx` for side-by-side CS-vs-AI review.

## Usage

```
/test-ticket --id <ticket_id>
/test-ticket --list <path-to-uat_ticket.csv>
/test-ticket --list <csv> --limit <N>
/test-ticket --list <csv> --per-cat <N>
```

## What this command does

It dispatches your arguments verbatim to the CLI run subcommand:

```bash
.venv/bin/python scripts/test_tickets_run.py run --id <ticket_id>
.venv/bin/python scripts/test_tickets_run.py run --list <csv> [--limit N] [--per-cat N]
```

There is no Python logic in this slash file — the engine lives entirely in
`scripts/test_tickets_run.py run`.

## Flags

| Flag | Description |
|------|-------------|
| `--id <ticket_id>` | Run exactly ONE ticket by its Freshdesk ID |
| `--list <csv>` | Run a batch from `uat_ticket.csv` (semicolon-delimited, header `Level_in;Resolved date;Ticket ID`) |
| `--limit N` | Total ticket cap across all buckets (D-43) |
| `--per-cat N` | Per-`Level_in` bucket cap; **default = 10** (D-43) |

## Safety

- **DRY_RUN only (D-39):** the pipeline never POSTs a reply to Freshdesk.
  It reads tickets (Freshdesk GET) and order data (Selless read-only) — no writes.
- Uses **PROD credentials** from `.env.prd` (read-only API key).
- Output goes ONLY to gitignored files: `test-tickets.xlsx` and `.test-tickets-data.jsonl`.
  Customer PII is never printed to stdout (IDs/lengths/labels only).

## Cap drops

Any tickets dropped by `--per-cat` or `--limit` are **logged** (count + bucket breakdown)
before processing starts — never silently truncated (D-43).

## Output

After all tickets complete, the command overwrites:
- `test-tickets.xlsx` — one sheet per ticket, CS-vs-AI side-by-side properties,
  AI output block, Checker reason rows (D-37/D-40).
- `.test-tickets-data.jsonl` — raw JSON records (gitignored).

## --list file format

`uat_ticket.csv` is semicolon-delimited with header:

```
Level_in;Resolved date;Ticket ID
Change_Request;2026-05-01 09:11:46 PM;7505172
Complaint;2026-05-03 01:25:19 PM;7502149
Inquiry;2026-05-02 09:05:26 AM;7505402
```

`Level_in` is used as the category hint passed to the real team. `Resolved date` is
informational only. A plain one-ID-per-line file (no header) is also accepted.

## Examples

```bash
# Single ticket
.venv/bin/python scripts/test_tickets_run.py run --id 33403

# Batch from uat_ticket.csv, at most 3 per bucket
.venv/bin/python scripts/test_tickets_run.py run --list uat_ticket.csv --per-cat 3

# Batch, global cap of 5 tickets total
.venv/bin/python scripts/test_tickets_run.py run --list uat_ticket.csv --limit 5
```
