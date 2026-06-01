"""
idempotency.py — Idempotency key computation for the queue (D-02).

DATA CONTRACT (D-02):
  Key = f"{ticket_id}:{inbound_msg_id}" where inbound_msg_id is the conversation id
  of the latest incoming customer message (resolved by the caller BEFORE enqueue via
  GET /conversations — "resolve-then-enqueue").

  Both the webhook path and the reconciliation poller derive the SAME key from the SAME
  ticket state, so the UNIQUE index + ON CONFLICT DO NOTHING is the single dedup guard.

  NEVER pass a sentinel (0, -1) for inbound_msg_id. NEVER re-key inside the worker.
"""


def compute_idempotency_key(ticket_id: int, inbound_msg_id: int) -> str:
    """Return the deterministic idempotency key for a given (ticket, inbound message) pair.

    Args:
        ticket_id: Freshdesk ticket ID.
        inbound_msg_id: Freshdesk conversation ID of the latest *incoming* customer message
            (NOT the ticket ID, NOT a webhook delivery ID, NOT a content hash — per D-02
            and RESEARCH § Postgres Queue Pattern Pitfall 2).

    Returns:
        "{ticket_id}:{inbound_msg_id}" — stable, collision-free, same output for same inputs.
    """
    return f"{ticket_id}:{inbound_msg_id}"
