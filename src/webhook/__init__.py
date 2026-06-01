"""Webhook receiver module — FastAPI app + HMAC verification."""


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Stub — implemented in Wave 3 (02-05)."""
    raise NotImplementedError("Wave 3: implement HMAC-SHA256 webhook signature verify")
