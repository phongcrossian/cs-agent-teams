"""
Settings — read from environment variables (via pydantic-settings).

Security: API key and webhook secret are NEVER logged. See __repr__ override.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class SendMode(str, Enum):
    """Config-driven send-mode switch (D-05).

    DRY_RUN (default): persist would-be action to dry_run_log; do NOT call Freshdesk.
    LIVE: post reply/note into actual Freshdesk ticket.
    """

    DRY_RUN = "dry_run"
    LIVE = "live"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    SECURITY: api_key and webhook_secret are excluded from __repr__ / logs.
    """

    # Database
    database_url: str = Field(
        default="postgresql://csbot:csbot@localhost:5432/csbot",
        description="asyncpg-compatible Postgres URL",
    )

    # Freshdesk
    freshdesk_domain: str = Field(
        default="",
        description="Freshdesk subdomain (e.g. 'yourcompany' for yourcompany.freshdesk.com)",
    )
    freshdesk_api_key: str = Field(
        default="",
        description="Freshdesk API key — NEVER log this value",
    )

    # Webhook
    webhook_secret: str = Field(
        default="",
        description="Shared secret for HMAC-SHA256 webhook verification — NEVER log",
    )

    # Send mode (D-05)
    send_mode: SendMode = Field(
        default=SendMode.DRY_RUN,
        description="dry_run = persist only; live = post to Freshdesk",
    )

    # Selless sync user IDs (D-07 loop-guard layer 4)
    selless_sync_user_ids: set[int] = Field(
        default_factory=set,
        description="Freshdesk user_ids of Selless sync integration (CSV env string parsed below)",
    )

    # Retry / backoff
    retry_max_attempts: int = Field(
        default=5,
        description="Max Freshdesk API retry attempts before dead-lettering",
    )

    # Poller
    poller_interval_seconds: int = Field(
        default=300,
        description="Reconciliation poller cadence in seconds (~5 min default, D-09)",
    )

    # Per-ticket reply throttle (loop-guard D-06, fix #4)
    per_ticket_reply_throttle_n: int = Field(
        default=1,
        description="Max replies allowed per ticket within throttle window",
    )
    per_ticket_reply_throttle_window_minutes: int = Field(
        default=30,
        description="Throttle window in minutes for per-ticket reply limit",
    )

    @field_validator("selless_sync_user_ids", mode="before")
    @classmethod
    def parse_selless_sync_user_ids(cls, v: object) -> set[int]:
        """Parse comma-separated int string from env into set[int]."""
        if isinstance(v, set):
            return v
        if isinstance(v, (list, tuple)):
            return {int(x) for x in v if str(x).strip()}
        if isinstance(v, str):
            return {int(x.strip()) for x in v.split(",") if x.strip()}
        return set()

    def __repr__(self) -> str:
        """Never expose api_key or webhook_secret in repr/logs."""
        return (
            f"Settings(send_mode={self.send_mode!r}, "
            f"freshdesk_domain={self.freshdesk_domain!r}, "
            f"database_url={self.database_url!r}, "
            f"freshdesk_api_key=<REDACTED>, webhook_secret=<REDACTED>)"
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Module-level singleton — import from here
settings = Settings()
