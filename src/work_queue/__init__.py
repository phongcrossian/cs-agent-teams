"""Work queue module — Postgres SKIP LOCKED queue.

Note: module is src/work_queue/ NOT src/queue/ to avoid shadowing stdlib `queue`
(fix review #10).
"""


async def enqueue(conn, ticket_id: int, inbound_msg_id: int, payload: dict) -> bool:
    """Stub — implemented in Wave 1 (02-03)."""
    raise NotImplementedError("Wave 1: implement enqueue")


async def claim(conn, worker_id: str):
    """Stub — implemented in Wave 1 (02-03)."""
    raise NotImplementedError("Wave 1: implement claim (SKIP LOCKED)")
