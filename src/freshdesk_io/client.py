"""
FreshdeskClient — the ONLY module permitted to call the Freshdesk REST API.

Architecture boundary: no other module in this codebase may call Freshdesk directly.

Methods:
  post_reply(ticket_id, body)            → ReplyResult
  post_note(ticket_id, body, private)    → NoteResult
  get_conversations(ticket_id)           → list[Conversation]
  get_ticket(ticket_id)                  → dict
  list_updated_tickets(since)            → list[Ticket]

Retry/backoff (D-10):
  - 429 → honor Retry-After header (parse_retry_after), raise FreshdeskRateLimitError
  - 5xx / TransportError → raise FreshdeskTransientError (retry with backoff+jitter)
  - 400 / 401 / 403 / 404 / 409 → raise FreshdeskFatalError (no retry, dead-letter)
  - tenacity: stop_after_attempt(max_attempts), custom freshdesk_wait

Security / PII (T-02-03, T-02-04, CLAUDE.md):
  - API key read from settings (env), never logged
  - Logs only ticket_id + HTTP status + conversation id — no raw body, no from_email
"""

from __future__ import annotations

import random
import logging
from datetime import datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    RetryCallState,
)

from src.freshdesk_io.errors import (
    FreshdeskFatalError,
    FreshdeskRateLimitError,
    FreshdeskTransientError,
)
from src.freshdesk_io.models import Conversation, NoteResult, ReplyResult, Ticket
from src.freshdesk_io.rate_limit import classify_status, parse_retry_after

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tenacity wait strategy
# ---------------------------------------------------------------------------

def _freshdesk_wait(retry_state: RetryCallState) -> float:
    """Custom tenacity wait: honor Retry-After on RateLimitError, else exp+jitter."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, FreshdeskRateLimitError):
        return float(exc.retry_after)
    # Exponential backoff with ±1s jitter; cap at 60s
    attempt = retry_state.attempt_number
    base = min(2 ** attempt, 60)
    return base + random.uniform(-1.0, 1.0)


# ---------------------------------------------------------------------------
# Response → error classification
# ---------------------------------------------------------------------------

def _raise_for_freshdesk_status(response: httpx.Response) -> None:
    """Raise the appropriate exception based on HTTP status.

    Called after every non-2xx response from Freshdesk.
    2xx responses are silently passed through (caller reads .json()).
    """
    status = response.status_code
    if status == 429:
        retry_after = parse_retry_after(dict(response.headers))
        logger.warning("freshdesk_rate_limited", extra={"retry_after": retry_after})
        raise FreshdeskRateLimitError(retry_after=retry_after)

    classification = classify_status(status)
    if classification == "fatal":
        logger.error(
            "freshdesk_fatal_error",
            extra={"status": status},
        )
        raise FreshdeskFatalError(f"HTTP {status}: fatal — no retry")

    if classification == "transient":
        logger.warning(
            "freshdesk_transient_error",
            extra={"status": status},
        )
        raise FreshdeskTransientError(f"HTTP {status}: transient — will retry")


# ---------------------------------------------------------------------------
# FreshdeskClient
# ---------------------------------------------------------------------------

class FreshdeskClient:
    """Async Freshdesk API client with tenacity retry + honor Retry-After.

    Usage:
        client = FreshdeskClient(domain="yourco", api_key="...", max_attempts=5)
        result = await client.post_reply(ticket_id=123, body="<p>Hi</p>")
    """

    def __init__(
        self,
        domain: str,
        api_key: str,
        max_attempts: int = 5,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        # Normalize domain at the boundary: accept "sub", "sub.freshdesk.com",
        # or a full URL. base_url below appends ".freshdesk.com", so strip any
        # scheme and an existing ".freshdesk.com" suffix to avoid double-append.
        normalized = domain.strip().replace("https://", "").replace("http://", "").rstrip("/")
        if normalized.endswith(".freshdesk.com"):
            normalized = normalized[: -len(".freshdesk.com")]
        self._domain = normalized
        self._api_key = api_key
        self._max_attempts = max_attempts
        # Allow injection for testing; otherwise built lazily on first call
        self._http_client = _http_client

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                auth=(self._api_key, "X"),
                base_url=f"https://{self._domain}.freshdesk.com",
                timeout=30.0,
            )
        return self._http_client

    def _make_retry_decorator(self):
        """Build a tenacity retry decorator bound to this instance's max_attempts."""
        return retry(
            stop=stop_after_attempt(self._max_attempts),
            wait=_freshdesk_wait,
            retry=retry_if_exception_type(
                (FreshdeskRateLimitError, FreshdeskTransientError, httpx.TransportError)
            ),
            reraise=True,
        )

    # -----------------------------------------------------------------------
    # post_reply
    # -----------------------------------------------------------------------

    async def post_reply(self, ticket_id: int, body: str) -> ReplyResult:
        """Post a public reply into a Freshdesk ticket.

        POST /api/v2/tickets/{id}/reply
        Returns ReplyResult with the new conversation id.
        """
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> ReplyResult:
            resp = await self._client().post(
                f"/api/v2/tickets/{ticket_id}/reply",
                json={"body": body},
            )
            if resp.status_code not in (200, 201):
                _raise_for_freshdesk_status(resp)
            data: dict[str, Any] = resp.json()
            logger.info(
                "freshdesk_reply_posted",
                extra={"ticket_id": ticket_id, "conversation_id": data.get("id")},
            )
            return ReplyResult(id=data["id"], ticket_id=ticket_id)

        return await _call()

    # -----------------------------------------------------------------------
    # post_note
    # -----------------------------------------------------------------------

    async def post_note(
        self, ticket_id: int, body: str, private: bool = True
    ) -> NoteResult:
        """Post a private note on a Freshdesk ticket.

        POST /api/v2/tickets/{id}/notes
        Returns NoteResult with the new conversation id.
        """
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> NoteResult:
            resp = await self._client().post(
                f"/api/v2/tickets/{ticket_id}/notes",
                json={"body": body, "private": private},
            )
            if resp.status_code not in (200, 201):
                _raise_for_freshdesk_status(resp)
            data: dict[str, Any] = resp.json()
            logger.info(
                "freshdesk_note_posted",
                extra={"ticket_id": ticket_id, "conversation_id": data.get("id")},
            )
            return NoteResult(id=data["id"], ticket_id=ticket_id)

        return await _call()

    # -----------------------------------------------------------------------
    # get_conversations
    # -----------------------------------------------------------------------

    async def get_conversations(self, ticket_id: int) -> list[Conversation]:
        """Fetch all conversations for a ticket.

        GET /api/v2/tickets/{id}/conversations
        Returns list[Conversation].
        """
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> list[Conversation]:
            resp = await self._client().get(
                f"/api/v2/tickets/{ticket_id}/conversations"
            )
            if resp.status_code != 200:
                _raise_for_freshdesk_status(resp)
            items: list[dict[str, Any]] = resp.json()
            return [Conversation(**item) for item in items]

        return await _call()

    # -----------------------------------------------------------------------
    # get_ticket
    # -----------------------------------------------------------------------

    async def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Fetch a single ticket by ID.

        GET /api/v2/tickets/{id}
        Returns raw dict (caller parses as needed).
        """
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> dict[str, Any]:
            resp = await self._client().get(f"/api/v2/tickets/{ticket_id}")
            if resp.status_code != 200:
                _raise_for_freshdesk_status(resp)
            return resp.json()

        return await _call()

    # -----------------------------------------------------------------------
    # list_updated_tickets
    # -----------------------------------------------------------------------

    async def list_updated_tickets(self, since: datetime) -> list[Ticket]:
        """Fetch all tickets updated since `since` (poller dependency — fix #2).

        GET /api/v2/tickets?updated_since={iso}&per_page=100
        Handles pagination: keeps fetching until an empty page is returned.
        Returns list[Ticket].

        NOTE: Growth plan sub-limit for List endpoint is ~20 calls/min.
        The generic Retry-After / tenacity path handles 429 automatically.
        """
        iso = since.isoformat()
        results: list[Ticket] = []
        page = 1

        while True:
            tickets_on_page = await self._fetch_ticket_page(iso, page)
            if not tickets_on_page:
                break
            results.extend(tickets_on_page)
            page += 1

        return results

    async def _fetch_ticket_page(
        self, updated_since_iso: str, page: int
    ) -> list[Ticket]:
        """Fetch a single page of updated tickets with retry."""
        retry_dec = self._make_retry_decorator()

        @retry_dec
        async def _call() -> list[Ticket]:
            resp = await self._client().get(
                "/api/v2/tickets",
                params={
                    "updated_since": updated_since_iso,
                    "per_page": 100,
                    "page": page,
                },
            )
            if resp.status_code != 200:
                _raise_for_freshdesk_status(resp)
            items: list[dict[str, Any]] = resp.json()
            return [Ticket(**item) for item in items]

        return await _call()
