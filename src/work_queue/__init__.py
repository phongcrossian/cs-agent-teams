"""Work queue module — Postgres SKIP LOCKED queue.

Note: module is src/work_queue/ NOT src/queue/ to avoid shadowing stdlib `queue`
(fix review #10).

Public API (Wave 1 — 02-03):
  - enqueue_ticket: idempotent INSERT ON CONFLICT DO NOTHING
  - claim_one: FOR UPDATE SKIP LOCKED claim
  - finalize_done: token-checked done finalization
  - finalize_retry: token-checked retry with backoff
  - recover_stale_claims: sweep stale claimed rows back to pending
  - compute_idempotency_key: deterministic key (ticket_id:inbound_msg_id)

Public API (Wave 2 — 02-04):
  - send_reply: mode-aware send (DRY_RUN / LIVE) with send-intent transactional (fix #1)
  - process_queue_row: full post-path pipeline with guards + redaction
  - worker_loop: sequential worker loop (D-11)
  - DeadLetterSink, RetryOnlyDeadLetterSink: dead-letter protocol (fix #7)
"""

from src.work_queue.idempotency import compute_idempotency_key
from src.work_queue.enqueue import enqueue_ticket
from src.work_queue.claim import (
    claim_one,
    finalize_done,
    finalize_retry,
    recover_stale_claims,
)

# Legacy stub aliases for backward compatibility with test imports
# (tests/test_queue.py: `from src.work_queue import enqueue, claim`)
enqueue = enqueue_ticket
claim = claim_one

__all__ = [
    "compute_idempotency_key",
    "enqueue_ticket",
    "enqueue",
    "claim_one",
    "claim",
    "finalize_done",
    "finalize_retry",
    "recover_stale_claims",
]
