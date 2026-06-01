"""
signature.py — HMAC-SHA256 webhook signature verification (T-02-15).

Freshdesk does NOT have native HMAC signing (Research A3), so we use a custom
shared-secret header: X-Freshdesk-Signature.

Security: compare_digest provides constant-time comparison to prevent timing attacks.
Never log the secret or the raw body.
"""

from __future__ import annotations

import binascii
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
    # compare_digest: constant-time, resistant to timing side-channel.
    #
    # compare_digest raises TypeError when the two str args contain non-ASCII
    # characters (and ValueError/binascii.Error can arise from malformed input).
    # An attacker controls the X-Freshdesk-Signature header, so a non-ASCII /
    # malformed value must yield verification failure (→ 401), never an
    # unhandled exception (→ 500). Encode both operands to bytes so the
    # comparison is always over ASCII-safe byte strings (BL-03 / T-02-15).
    try:
        return hmac.compare_digest(
            expected.encode("ascii"),
            signature.encode("ascii"),
        )
    except (TypeError, ValueError, binascii.Error, UnicodeEncodeError):
        return False
