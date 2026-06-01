"""
Pydantic models for Freshdesk API responses.

Conversation  — inbound/outbound message on a ticket
Ticket        — minimal ticket representation (id + updated_at)
ReplyResult   — returned after successful POST reply
NoteResult    — returned after successful POST note

All models use extra="ignore" so unexpected API fields are silently dropped
(T-02-06: parse only, never eval response content).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Conversation(BaseModel):
    """A single conversation entry on a Freshdesk ticket.

    Key fields for loop-guard and routing:
      incoming   — True = customer reply; False = agent/AI/system
      private    — True = private note (not visible to customer)
      user_id    — ID of the author (agent or contact)
      from_email — sender email address
      source     — numeric source code (email=1, portal=2, phone=3, ...)
      body_text  — plain-text content (used for processing; NOT logged raw)
    """

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    incoming: bool
    private: bool
    user_id: int
    from_email: str
    source: int
    body_text: str = ""


class Ticket(BaseModel):
    """Minimal ticket model — used by the poller (02-05, fix review #2).

    Only id + updated_at are required; all other API fields are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    updated_at: datetime


class ReplyResult(BaseModel):
    """Result of a successful POST /api/v2/tickets/{id}/reply."""

    model_config = ConfigDict(extra="ignore")

    id: int
    ticket_id: int


class NoteResult(BaseModel):
    """Result of a successful POST /api/v2/tickets/{id}/notes."""

    model_config = ConfigDict(extra="ignore")

    id: int
    ticket_id: int
