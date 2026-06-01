"""
signature.py — HMAC-SHA256 webhook signature verification (T-02-15).

Freshdesk does NOT have native HMAC signing (Research A3), so we use a custom
shared-secret header: X-Freshdesk-Signature.

Security: compare_digest provides constant-time comparison to prevent timing attacks.
Never log the secret or the raw body.
"""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(
    body: bytes,
    signature: str | None,
    secret: bytes,
) -> bool:
    """Verify HMAC-SHA256 webhook signature (constant-time).

    Args:
        body: Raw request body bytes.
        signature: Hex digest from X-Freshdesk-Signature header (None/empty → False).
        secret: Shared webhook secret bytes.

    Returns:
        True if signature is valid; False if tampered, missing, or empty.

    Security: Uses hmac.compare_digest to prevent timing attacks (T-02-15).
    """
    if not signature:
        return False

    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    # compare_digest: constant-time, resistant to timing side-channel
    return hmac.compare_digest(expected, signature)
