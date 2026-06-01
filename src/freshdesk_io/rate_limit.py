"""
Rate-limit helpers for Freshdesk I/O client.

parse_retry_after  — reads Retry-After header (default 60s if missing)
classify_status    — maps HTTP status code to "transient" | "fatal"

Classification table (per RESEARCH § Error Classification):
  transient: 429, 500, 502, 503, 504
  fatal:     400, 401, 403, 404, 409

NOTE: 409 is FATAL (fix review #5). See errors.py for rationale.
"""

from __future__ import annotations

from typing import Literal


def parse_retry_after(headers: dict) -> int:
    """Return seconds to wait from Retry-After header.

    Accepts case-insensitive header dict.
    Returns 60 if header is absent, unparseable, or zero.
    """
    # Try both common casings
    raw = headers.get("Retry-After") or headers.get("retry-after") or ""
    try:
        value = int(raw)
        return value if value > 0 else 60
    except (ValueError, TypeError):
        return 60


def classify_status(status_code: int) -> Literal["transient", "fatal"]:
    """Map an HTTP status code to retry disposition.

    transient → safe to retry (429 / 5xx)
    fatal     → dead-letter immediately (400 / 401 / 403 / 404 / 409)
    """
    _TRANSIENT = {429, 500, 502, 503, 504}
    _FATAL = {400, 401, 403, 404, 409}

    if status_code in _TRANSIENT:
        return "transient"
    if status_code in _FATAL:
        return "fatal"
    # Anything else (2xx, 3xx, other 4xx) — caller handles
    # Default: treat unknown 4xx as fatal, unknown 5xx as transient
    if 500 <= status_code < 600:
        return "transient"
    return "fatal"
