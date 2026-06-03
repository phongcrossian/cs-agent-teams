"""
Settings — read from environment variables (via pydantic-settings).

Security: API key and webhook secret are NEVER logged. See __repr__ override.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


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
    selless_sync_user_ids: Annotated[set[int], NoDecode] = Field(
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

    # === Phase 4 additions — agent team ==========================================

    # Anthropic API key (NEVER log)
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key — NEVER log this value",
    )

    # Per-stage Claude model assignments (D-03)
    # Bedrock cut-over: set CLAUDE_CODE_USE_BEDROCK=1 + AWS_* envs; no code change needed
    claude_model_classify: str = Field(
        default="claude-haiku-4-5",
        description="Haiku for classify/extract stages (D-03 — cheap, fast high-frequency hot path)",
    )
    claude_model_draft: str = Field(
        default="claude-sonnet-4-6",
        description="Sonnet for draft/critic stages (D-03 — near-Opus quality, grounding + citation)",
    )
    claude_model_lead: str = Field(
        default="claude-sonnet-4-6",
        description="Sonnet for team lead orchestration (W3 fix — no Opus on hot path)",
    )

    # DRY_RUN flag for agent team (never posts to Freshdesk in PoC)
    dry_run: bool = Field(
        default=True,
        description="DRY_RUN flag for the agent team (never posts to Freshdesk in PoC)",
    )

    # === Phase 3 additions — grounding layer =====================================

    # Selless API (D-01, gateway-trust model confirmed 2026-06-02)
    selless_api_base_url: str = Field(
        default="https://api.selless.dev/admin/csm/order/public/tickets",
        description=(
            "Selless API base URL (public/tickets prefix). No auth token needed "
            "— access gated at network/gateway layer."
        ),
    )
    # Reserve field for future gateway auth header if prod VPN requires it
    selless_api_gateway_key: str = Field(
        default="",
        description="Optional gateway auth header value — NEVER log this value",
    )

    # Voyage embeddings (KB-05, CLAUDE.md mandate)
    voyage_api_key: str = Field(
        default="",
        description="Voyage AI API key for voyage-3-large embeddings — NEVER log",
    )
    voyage_model: str = Field(
        default="voyage-3-large",
        description="Voyage embedding model name",
    )
    voyage_output_dimension: int = Field(
        default=1024,
        description="Embedding dimension (voyage-3-large default: 1024)",
    )

    # Selless MCP rate limit (D-08, Claude's discretion)
    selless_rate_limit_rps: float = Field(
        default=1.0,
        description="Selless MCP server-wide token bucket: requests/second",
    )
    selless_rate_limit_burst: int = Field(
        default=10,
        description="Selless MCP token bucket burst capacity",
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
        """Never expose api_key, webhook_secret, selless_api_gateway_key, voyage_api_key, or anthropic_api_key."""
        return (
            f"Settings(send_mode={self.send_mode!r}, "
            f"freshdesk_domain={self.freshdesk_domain!r}, "
            f"database_url={self.database_url!r}, "
            f"selless_api_base_url={self.selless_api_base_url!r}, "
            f"claude_model_classify={self.claude_model_classify!r}, "
            f"claude_model_draft={self.claude_model_draft!r}, "
            f"claude_model_lead={self.claude_model_lead!r}, "
            f"dry_run={self.dry_run!r}, "
            f"freshdesk_api_key=<REDACTED>, webhook_secret=<REDACTED>, "
            f"selless_api_gateway_key=<REDACTED>, voyage_api_key=<REDACTED>, "
            f"anthropic_api_key=<REDACTED>)"
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Module-level singleton — import from here
settings = Settings()
