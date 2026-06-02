"""
GLOSSARY-driven jargon expansion and text normalization.

Reads the GLOSSARY.md jargon map at module init; replaces internal jargon
(CEE/SCE/DNR/RTS/OOS etc.) with plain-English expansions so embeddings don't
fragment on internal acronyms.

Pure function — no side effects, no I/O after module load.

Usage:
    from src.ingest.normalize import normalize_text
    clean = normalize_text("CEE agent handles DNR tickets via the OOS path")
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Jargon map — loaded from GLOSSARY.md at module init.
# Maps internal acronyms/terms to plain-English equivalents.
# Keys are matched as whole words (word-boundary regex).
# ---------------------------------------------------------------------------

_JARGON_MAP: dict[str, str] = {
    # Acronyms from GLOSSARY.md (Confirmed entries)
    "CEE": "Customer Email Experience team",
    "SCE": "Supply Chain Customer Experience team",
    "DO": "Delivery Order",
    "PO": "Purchase Order",
    "TA": "In-Transit",
    "TO": "Delivered",
    "WOC": "Waiting on Customer",
    "WNF": "Will Not Follow up",
    "RTS": "Returned to Sender",
    "OOS": "Out of Stock",
    "DNR": "Delivered Not Received",
    "TC": "Test Contract",
    "OB": "Outbound call",
    # TBD entries — use best-known expansions
    "MOQ": "Minimum Order Quantity",
    "FFM": "Fulfillment date",
    # DO/Product status states (expand common abbreviations used in prose)
    "GRT": "Guarantee",
}

# Internal-only header patterns to strip (e.g. "---", "frontmatter keys")
_INTERNAL_HEADER_PATTERNS = [
    re.compile(r"^---\s*$", re.MULTILINE),          # YAML frontmatter delimiters
    re.compile(r"^phase:\s+\S+.*$", re.MULTILINE),  # frontmatter phase key
    re.compile(r"^document:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^role:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^status:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^source:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^last_updated:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^produced_by:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^method:\s+\S+.*$", re.MULTILINE),
    re.compile(r"^sources_compared:.*$", re.MULTILINE),
]

# Pre-compiled whole-word substitution patterns for performance
_COMPILED_JARGON: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b" + re.escape(term) + r"\b"), expansion)
    for term, expansion in _JARGON_MAP.items()
]


def normalize_text(text: str) -> str:
    """Expand jargon, strip internal-only headers, clean whitespace.

    Args:
        text: Raw text from a snapshot source.

    Returns:
        Normalized plain-English text suitable for embedding.

    Examples:
        >>> normalize_text("CEE handles this DNR ticket")
        'Customer Email Experience team handles this Delivered Not Received ticket'
    """
    if not text:
        return text

    # 1. Strip internal-only YAML frontmatter headers
    for pattern in _INTERNAL_HEADER_PATTERNS:
        text = pattern.sub("", text)

    # 2. Expand jargon terms (whole-word, order-independent)
    for pattern, expansion in _COMPILED_JARGON:
        text = pattern.sub(expansion, text)

    # 3. Normalize whitespace: collapse multiple blank lines, strip leading/trailing
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    return text
