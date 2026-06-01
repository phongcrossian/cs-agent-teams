"""Loop/auto-reply guard module — D-06 four-signal layer + per-ticket throttle."""


def should_suppress(conv: dict, settings=None) -> bool:
    """Stub — single source of truth for suppress decision (fix review #4).

    Implemented in Wave 2 (02-04).
    Returns True if the conversation should be suppressed (no reply sent).
    """
    raise NotImplementedError("Wave 2: implement should_suppress (unified loop-guard)")
