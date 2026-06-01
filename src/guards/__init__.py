"""Loop/auto-reply guard module — D-06 four-signal layer + per-ticket throttle.

Public API:
  should_suppress(conv, headers, from_email, selless_sync_user_ids) -> (bool, str)
  should_throttle_ticket(conn, ticket_id, n, window_minutes) -> bool  [async]
  redact_text(text) -> str

SINGLE SOURCE OF TRUTH (fix #4): both resolve step (02-05) and worker (02-04)
import should_suppress from here.  No inline incoming/private checks elsewhere.
"""

from src.guards.loop_guard import should_suppress, should_throttle_ticket
from src.guards.pii import redact_text

__all__ = [
    "should_suppress",
    "should_throttle_ticket",
    "redact_text",
]
