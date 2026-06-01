# Customer Support Email Automation — Phase 2: Freshdesk I/O Layer

AI system that automates customer-support email for a US e-commerce business. This phase builds the pipeline backbone: webhook receiver → Postgres queue → sequential worker → Freshdesk reply/note client.

## Architecture

```
Freshdesk
  │  (webhook POST on ticket create/update)
  ▼
FastAPI Webhook Receiver  →  Postgres Queue (SKIP LOCKED)
                                    │
                              Sequential Worker
                                    │
                         send_mode switch (default: dry_run)
                          ├── dry_run → dry_run_log table
                          └── live    → Freshdesk I/O Client
```

## Setup

### Prerequisites

- Python 3.14+
- Docker Desktop (for local Postgres via docker-compose)
  - Install from https://www.docker.com/products/docker-desktop/
  - Alternatively: install PostgreSQL 16 locally

### Installation (pip)

```bash
# uv is the recommended package manager per CLAUDE.md, but not yet in PATH.
# Install uv first:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Then reload shell and use:
uv sync --all-extras

# Fallback (pip + venv):
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Presidio PII Redaction — spaCy model

Presidio requires the English NER model. Install after the packages above:

```bash
python -m spacy download en_core_web_lg
```

### Environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, FRESHDESK_DOMAIN, FRESHDESK_API_KEY, WEBHOOK_SECRET
# SEND_MODE defaults to dry_run (safe)
```

### Start local Postgres

```bash
docker compose up -d postgres
docker compose exec postgres pg_isready
```

### Run migrations

```bash
alembic upgrade head
```

### Run tests

```bash
# Quick (no network, no Postgres needed for most tests):
pytest tests/ -x --ignore=tests/test_e2e_sandbox.py -q

# Full suite:
pytest tests/ -q

# Sandbox smoke tests (real Freshdesk — requires live API key + SEND_MODE=live):
RUN_SANDBOX=1 pytest tests/test_e2e_sandbox.py -m sandbox -x
```

## Project Structure

```
src/
├── freshdesk_io/       # Only module allowed to call Freshdesk API
│   ├── client.py       # FreshdeskClient (httpx + tenacity)
│   ├── models.py       # Pydantic models: Ticket, Conversation, Reply
│   └── rate_limit.py   # X-RateLimit-* / Retry-After parsing
├── work_queue/         # Postgres-backed queue (SKIP LOCKED)
│   ├── enqueue.py      # INSERT ON CONFLICT DO NOTHING
│   ├── worker.py       # Claim loop + send-intent (sent_at)
│   └── dead_letter.py  # Move exhausted rows to dead_letter
├── webhook/            # FastAPI webhook receiver
│   ├── receiver.py     # HMAC verify + enqueue
│   └── signature.py    # hmac.compare_digest helper
├── poller/             # Reconciliation poller (D-09)
│   └── reconcile.py    # updated_since scan + durable checkpoint
├── guards/             # Loop/auto-reply guard (D-06)
│   ├── loop_guard.py   # RFC3834, sender patterns, source/actor
│   └── pii.py          # Presidio redaction wrapper
├── config.py           # Settings (send_mode default=dry_run, DB URL, ...)
└── main.py             # Entry point: webhook + poller + worker
migrations/
└── versions/
    └── 0001_initial_queue_schema.py   # schema `queue`: 4 tables
tests/
docker-compose.yml      # Postgres 16 + pgvector (Phase 3 ready)
pyproject.toml
```

## Key Design Decisions

- **send_mode default = dry_run**: Nothing posts to Freshdesk unless `SEND_MODE=live`. Safe for dev/CI.
- **Idempotency key = `ticket_id:inbound_msg_id`**: Dedup at insert (ON CONFLICT DO NOTHING) — both webhook and poller paths produce the same key.
- **send-intent (sent_at column)**: Worker sets `sent_at` before calling Freshdesk. On re-claim, if `sent_at IS NOT NULL` → skip POST, go straight to finalize_done. Closes the crash-window between POST 200 and finalize_done.
- **Schema `queue`**: All queue tables live in schema `queue` (not `public`) to keep the Phase 3 pgvector extension in `public` without naming conflicts.
- **PII redaction**: Presidio runs before any text is persisted to DB or logs (D-12).

## Phase 3 Integration Note

Postgres is shared with Phase 3 (pgvector). Queue tables use schema `queue`; pgvector will use schema `public`. Pool sharing vs separate pool / `statement_timeout` is a Phase 3 decision.
