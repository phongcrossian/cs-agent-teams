"""Reconciliation poller module — updated_since scan + durable checkpoint (D-09)."""


async def reconcile_once(pool, client, since: str) -> int:
    """Stub — implemented in Wave 3 (02-05)."""
    raise NotImplementedError("Wave 3: implement reconcile_once")


async def load_checkpoint(conn) -> str:
    """Stub — load last_since from queue.poller_checkpoint."""
    raise NotImplementedError("Wave 3: implement load_checkpoint")


async def save_checkpoint(conn, last_since: str) -> None:
    """Stub — persist last_since to queue.poller_checkpoint."""
    raise NotImplementedError("Wave 3: implement save_checkpoint")
