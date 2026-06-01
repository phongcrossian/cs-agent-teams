"""Freshdesk I/O module — only module permitted to call Freshdesk API."""


class FreshdeskClient:
    """Stub — implemented in Wave 1 (02-02)."""

    async def post_reply(self, ticket_id: int, body: str) -> dict:
        raise NotImplementedError("Wave 1: implement FreshdeskClient.post_reply")

    async def post_note(self, ticket_id: int, body: str) -> dict:
        raise NotImplementedError("Wave 1: implement FreshdeskClient.post_note")

    async def list_updated_tickets(self, since: str) -> list:
        raise NotImplementedError("Wave 1: implement FreshdeskClient.list_updated_tickets")
