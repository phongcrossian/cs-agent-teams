"""
Selless MCP error taxonomy — mirror of freshdesk_io/errors.py (1:1 rename).

SellessRateLimitError  → 429 (honor Retry-After header, then retry)
SellessTransientError  → 5xx / timeout (retry with backoff+jitter)
SellessFatalError      → 400 / 401 / 403 / 404 / 409 (fail immediately, dead-letter)

SEL-04 / D-08: the Selless API enforces no rate-limit of its own — MCP layer is sole
security boundary.  These errors are raised by HttpSellessClient and propagated to
tenacity retry decorators.
"""


class SellessRateLimitError(Exception):
    """Raised on HTTP 429. Carries retry_after (seconds) from Retry-After header."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")


class SellessTransientError(Exception):
    """Raised on 5xx / transport timeout. Safe to retry with backoff."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SellessFatalError(Exception):
    """Raised on 400 / 401 / 403 / 404 / 409. Do NOT retry — dead-letter immediately."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
