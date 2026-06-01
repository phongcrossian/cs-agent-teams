"""
test_client.py — FreshdeskClient unit tests.

Uses respx to mock httpx calls — no network required.
All 6 tests must pass (Wave 1 / 02-02 GREEN phase).

Tests:
  test_post_reply_success       — POST reply → ReplyResult with conversation id
  test_post_note                — POST note (private=True) → NoteResult
  test_retry_after              — 429 Retry-After honored; retry succeeds
  test_fatal_404_no_retry       — 404 → FreshdeskFatalError immediately (call count == 1)
  test_get_conversations        — GET conversations → list[Conversation]
  test_list_updated_tickets     — list_updated_tickets(since) with pagination → list[Ticket]
"""

from __future__ import annotations

import pytest
import respx
import httpx
from datetime import datetime, timezone

from src.freshdesk_io import FreshdeskClient
from src.freshdesk_io.errors import FreshdeskFatalError, FreshdeskRateLimitError
from src.freshdesk_io.models import Conversation, ReplyResult, NoteResult, Ticket


DOMAIN = "testdomain"
API_KEY = "testapikey"


def make_client() -> FreshdeskClient:
    return FreshdeskClient(domain=DOMAIN, api_key=API_KEY)


# ---------------------------------------------------------------------------
# test_post_reply_success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_reply_success(respx_mock):
    """FreshdeskClient.post_reply posts to /api/v2/tickets/{id}/reply and returns ReplyResult."""
    respx_mock.post(
        f"https://{DOMAIN}.freshdesk.com/api/v2/tickets/123/reply"
    ).mock(
        return_value=httpx.Response(
            201,
            json={"id": 456, "ticket_id": 123, "body": "<p>hi</p>"},
        )
    )

    client = make_client()
    result = await client.post_reply(ticket_id=123, body="<p>hi</p>")

    assert isinstance(result, ReplyResult)
    assert result.id == 456
    assert result.ticket_id == 123


# ---------------------------------------------------------------------------
# test_post_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_note(respx_mock):
    """FreshdeskClient.post_note posts to /api/v2/tickets/{id}/notes with private=True."""
    route = respx_mock.post(
        f"https://{DOMAIN}.freshdesk.com/api/v2/tickets/123/notes"
    ).mock(
        return_value=httpx.Response(
            201,
            json={"id": 789, "ticket_id": 123, "private": True},
        )
    )

    client = make_client()
    result = await client.post_note(ticket_id=123, body="<p>internal note</p>")

    assert isinstance(result, NoteResult)
    assert result.id == 789
    assert result.ticket_id == 123
    # Verify private=True was sent in request body
    request_body = route.calls[0].request
    import json
    sent_json = json.loads(request_body.content)
    assert sent_json.get("private") is True


# ---------------------------------------------------------------------------
# test_retry_after
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_after(respx_mock):
    """FreshdeskClient honors Retry-After header on 429 then retries and succeeds."""
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "1"},
                json={"message": "rate limited"},
            )
        return httpx.Response(
            201,
            json={"id": 999, "ticket_id": 42},
        )

    respx_mock.post(
        f"https://{DOMAIN}.freshdesk.com/api/v2/tickets/42/reply"
    ).mock(side_effect=side_effect)

    client = make_client()
    result = await client.post_reply(ticket_id=42, body="<p>retry test</p>")

    assert isinstance(result, ReplyResult)
    assert result.id == 999
    assert call_count == 2, f"Expected exactly 2 calls (1 × 429 + 1 × 201), got {call_count}"


# ---------------------------------------------------------------------------
# test_fatal_404_no_retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fatal_404_no_retry(respx_mock):
    """FreshdeskClient raises FreshdeskFatalError immediately on 404 — no retry."""
    route = respx_mock.post(
        f"https://{DOMAIN}.freshdesk.com/api/v2/tickets/404/reply"
    ).mock(
        return_value=httpx.Response(404, json={"description": "Ticket not found"})
    )

    client = make_client()
    with pytest.raises(FreshdeskFatalError):
        await client.post_reply(ticket_id=404, body="<p>gone</p>")

    assert route.call_count == 1, (
        f"Expected exactly 1 call (no retry on 404), got {route.call_count}"
    )


# ---------------------------------------------------------------------------
# test_get_conversations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_conversations(respx_mock):
    """FreshdeskClient.get_conversations returns list[Conversation]."""
    respx_mock.get(
        f"https://{DOMAIN}.freshdesk.com/api/v2/tickets/77/conversations"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1001,
                    "incoming": True,
                    "private": False,
                    "user_id": 50,
                    "from_email": "customer@example.com",
                    "source": 1,
                    "body_text": "Hello support",
                },
                {
                    "id": 1002,
                    "incoming": False,
                    "private": False,
                    "user_id": 99,
                    "from_email": "agent@company.com",
                    "source": 1,
                    "body_text": "Hi there",
                },
            ],
        )
    )

    client = make_client()
    convs = await client.get_conversations(ticket_id=77)

    assert len(convs) == 2
    assert all(isinstance(c, Conversation) for c in convs)
    assert convs[0].incoming is True
    assert convs[1].incoming is False
    assert convs[0].from_email == "customer@example.com"


# ---------------------------------------------------------------------------
# test_list_updated_tickets (fix review #2 — poller dependency)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_updated_tickets(respx_mock):
    """list_updated_tickets(since) returns list[Ticket] and handles pagination.

    Mock: page 1 returns 2 tickets; page 2 returns empty → stop.
    Result must include all tickets from all pages.
    """
    since = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    page1_tickets = [
        {"id": 101, "updated_at": "2026-06-01T01:00:00Z", "subject": "Issue 1"},
        {"id": 102, "updated_at": "2026-06-01T02:00:00Z", "subject": "Issue 2"},
    ]
    page2_tickets: list = []

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        # Parse page param from URL
        url = str(request.url)
        if "page=2" in url:
            return httpx.Response(200, json=page2_tickets)
        return httpx.Response(200, json=page1_tickets)

    respx_mock.get(
        url__regex=rf"https://{DOMAIN}\.freshdesk\.com/api/v2/tickets.*updated_since.*"
    ).mock(side_effect=side_effect)

    client = make_client()
    tickets = await client.list_updated_tickets(since=since)

    assert len(tickets) == 2, f"Expected 2 tickets (from page 1), got {len(tickets)}"
    assert all(isinstance(t, Ticket) for t in tickets)
    assert tickets[0].id == 101
    assert tickets[1].id == 102
    assert call_count >= 1, "Expected at least one page request"
