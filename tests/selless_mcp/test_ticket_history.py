"""SEL-03/D-05: get_ticket_history composes Selless ticket-do mapping + Phase-2 Freshdesk client.

Contract:
  1. Selless ticket-do: fetch_ticket_mapping(order_id) -> {fd_ticket_id, do_ids[]}
  2. Phase-2 FreshdeskClient.get_ticket(fd_ticket_id) -> raw ticket dict
  3. apply_ticket_history_whitelist -> TicketHistory
     ALLOW: rootcause, customer_feedback, customer_request, status, source, created
     DENY: agent, agent_id (internal CS fields — must never reach the drafter)
"""

from __future__ import annotations

import pytest

from src.selless_mcp.server import _impl_get_ticket_history
from src.selless_mcp.models import TicketHistory


# ---------------------------------------------------------------------------
# Stub Freshdesk client (mirrors MockSellessClient approach)
# ---------------------------------------------------------------------------

class StubFreshdeskClient:
    """Minimal Freshdesk client stub for get_ticket_history unit tests.

    Returns a fixture ticket dict that includes both ALLOW and DENY fields
    so the whitelist test can prove DENY fields are stripped.
    """

    FIXTURE_TICKET = {
        # ALLOW fields
        "rootcause": "Item arrived damaged",
        "customer_feedback": "Very unhappy with the product",
        "customer_request": "Full refund requested",
        "status": 5,  # Freshdesk status code
        "source": 1,  # Freshdesk source code (email)
        "created_at": "2026-04-15T10:00:00Z",
        # DENY: internal CS fields
        "agent": {"id": 9001, "name": "John Agent"},
        "agent_id": 9001,
        # Other internal fields (also not needed)
        "id": 368108,
        "responder_id": 9001,
        "updated_at": "2026-04-16T12:00:00Z",
    }

    async def get_ticket(self, ticket_id: int) -> dict:
        return dict(self.FIXTURE_TICKET)


class StubFreshdeskClientNoTicket:
    """Stub that simulates Freshdesk returning ticket without agent fields."""

    async def get_ticket(self, ticket_id: int) -> dict:
        return {
            "rootcause": "Wrong item shipped",
            "customer_feedback": "Please fix this",
            "customer_request": "Send correct item",
            "status": 2,
            "source": 1,
            "created_at": "2026-03-10T08:00:00Z",
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ticket_history_returns_ticket_history(mock_selless_client):
    """SEL-03: get_ticket_history returns a TicketHistory model."""
    fd_stub = StubFreshdeskClientNoTicket()
    result = await _impl_get_ticket_history(
        "14sv5kq2iec4to48u4nbcllai",
        client=mock_selless_client,
        freshdesk_client=fd_stub,
    )
    assert isinstance(result, TicketHistory)


@pytest.mark.asyncio
async def test_get_ticket_history_allow_fields(mock_selless_client):
    """SEL-03/D-05: TicketHistory contains ALLOW-listed fields from Freshdesk ticket."""
    fd_stub = StubFreshdeskClientNoTicket()
    result = await _impl_get_ticket_history(
        "14sv5kq2iec4to48u4nbcllai",
        client=mock_selless_client,
        freshdesk_client=fd_stub,
    )
    assert result.rootcause == "Wrong item shipped"
    assert result.customer_feedback == "Please fix this"
    assert result.customer_request == "Send correct item"


@pytest.mark.asyncio
async def test_get_ticket_history_denies_agent_fields(mock_selless_client):
    """SEL-03/D-05: agent and agent_id must be absent from TicketHistory (DENY D-04)."""
    fd_stub = StubFreshdeskClient()
    result = await _impl_get_ticket_history(
        "14sv5kq2iec4to48u4nbcllai",
        client=mock_selless_client,
        freshdesk_client=fd_stub,
    )
    # The raw fixture includes agent/agent_id — these must be stripped
    assert not hasattr(result, "agent"), "agent must be DENIED from TicketHistory (D-04)"
    assert not hasattr(result, "agent_id"), "agent_id must be DENIED from TicketHistory (D-04)"


@pytest.mark.asyncio
async def test_get_ticket_history_uses_selless_mapping(mock_selless_client):
    """SEL-03/D-05: get_ticket_history uses ticket-do mapping (fd_ticket_id) as join key."""
    calls_log = []

    class TrackingFreshdeskClient:
        async def get_ticket(self, ticket_id: int) -> dict:
            calls_log.append(ticket_id)
            return {
                "rootcause": "test",
                "customer_feedback": "test fb",
                "customer_request": "test req",
                "status": 5,
                "source": 1,
                "created_at": "2026-01-01T00:00:00Z",
            }

    fd_stub = TrackingFreshdeskClient()
    await _impl_get_ticket_history(
        "14sv5kq2iec4to48u4nbcllai",
        client=mock_selless_client,
        freshdesk_client=fd_stub,
    )

    # Should have called Freshdesk with the fd_ticket_id from the Selless mapping fixture
    # FIXTURE_TICKET_MAPPING has fd_ticket_id = 368108
    assert len(calls_log) == 1
    assert calls_log[0] == 368108, (
        f"Expected Freshdesk call with fd_ticket_id=368108 from Selless mapping, got {calls_log[0]}"
    )


@pytest.mark.asyncio
async def test_get_ticket_history_no_freshdesk_client_returns_empty(mock_selless_client):
    """SEL-03/D-05: if no Freshdesk client configured, returns empty TicketHistory gracefully."""
    result = await _impl_get_ticket_history(
        "14sv5kq2iec4to48u4nbcllai",
        client=mock_selless_client,
        freshdesk_client=None,
    )
    assert isinstance(result, TicketHistory)
    # All fields should be None (empty)
    assert result.rootcause is None
    assert result.customer_feedback is None
    assert not hasattr(result, "agent_id")


def test_ticket_history_model_no_agent_field():
    """D-04 source assertion: TicketHistory model has no agent or agent_id field defined."""
    fields = TicketHistory.model_fields
    assert "agent" not in fields, "TicketHistory must not have agent field (DENY D-04)"
    assert "agent_id" not in fields, "TicketHistory must not have agent_id field (DENY D-04)"
