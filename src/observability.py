"""
observability.py — Structured logging (structlog) + in-memory metric counters (D-12).

Setup:
  call configure_logging() once at startup (main.py).

Metrics (in-memory counters — Phase 2 baseline; Phase 6 wires Prometheus/OTel):
  processed_total      — rows successfully processed to 'done'
  suppressed_total     — rows suppressed by loop-guard (D-08)
  stale_inbound_total  — rows that became stale_inbound post-enqueue (fix #4)
  dead_lettered_total  — rows moved to dead_letter (crit #3)
  retries_total        — finalize_retry calls (transient errors)

PII contract (D-12):
  NEVER log raw ticket body, customer email, or any PII.
  Callers must redact BEFORE passing to emit_alert / logger calls.
  Only structural identifiers (ticket_id, row_id, error_type) are logged.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# ── Try structlog; fall back to stdlib if not installed ───────────────────────
try:
    import structlog

    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog (or stdlib fallback) with JSON renderer.

    Call once at application startup. Safe to call multiple times (idempotent).
    """
    if _STRUCTLOG_AVAILABLE:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    # Always configure stdlib root logger as well (structlog uses stdlib internally)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
        format="%(message)s",  # structlog renders full JSON; stdlib fallback uses this
    )


# ── In-memory metric counters ─────────────────────────────────────────────────
# Phase 2: simple dict counters.
# Phase 6: replace with Prometheus Counter objects or OTel instruments.

_counters: dict[str, int] = {
    "processed_total": 0,
    "suppressed_total": 0,
    "stale_inbound_total": 0,
    "dead_lettered_total": 0,
    "retries_total": 0,
}


def increment(metric: str, amount: int = 1) -> None:
    """Increment a named counter. Unknown metrics are created on first use."""
    _counters[metric] = _counters.get(metric, 0) + amount


def get_counter(metric: str) -> int:
    """Return current value of a named counter (for tests / health endpoint)."""
    return _counters.get(metric, 0)


def reset_counters() -> None:
    """Reset all counters to zero (test utility — not for production use)."""
    for key in list(_counters.keys()):
        _counters[key] = 0


# ── Alert helper ──────────────────────────────────────────────────────────────

_logger = logging.getLogger("csbot.alert")


def emit_alert(event: str, **kwargs: Any) -> None:
    """Log a structured alert at WARNING level.

    Phase 6 wires this to a real alert sink (PagerDuty, Slack, metric spike).
    For now: structured WARNING log only.

    PII contract: kwargs MUST NOT include raw customer text, email addresses,
    ticket body content, or any PII. Only structural IDs and redacted error types.

    Example:
        emit_alert("dead_letter", ticket_id=123, attempts=5, error_type="FreshdeskFatalError")
    """
    _logger.warning(
        "ALERT:%s",
        event,
        extra={"alert_event": event, **kwargs},
    )
