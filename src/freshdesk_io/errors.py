"""
Freshdesk I/O error taxonomy — D-10 (classify transient vs fatal).

FreshdeskRateLimitError  → 429 (honor Retry-After header, then retry)
FreshdeskTransientError  → 5xx / timeout (retry with backoff+jitter)
FreshdeskFatalError      → 400 / 401 / 403 / 404 / 409 (fail immediately, dead-letter)

NOTE: 409 is classified as FATAL (fix review #5).
Treating 409 as success/duplicate would silently swallow real errors.
409 semantic on Freshdesk sandbox is unverified until 02-06 Task 3.
Until then: 409 → dead-letter for human inspection.
"""


class FreshdeskRateLimitError(Exception):
    """Raised on HTTP 429. Carries retry_after (seconds) from Retry-After header."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")


class FreshdeskTransientError(Exception):
    """Raised on 5xx / transport timeout. Safe to retry with backoff."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FreshdeskFatalError(Exception):
    """Raised on 400 / 401 / 403 / 404 / 409. Do NOT retry — dead-letter immediately."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
