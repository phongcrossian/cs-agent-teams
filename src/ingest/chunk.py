"""
Prose chunking — split normalized text into conservative passages for embedding.

Strategy:
  - Split on paragraph boundaries (double newline) to preserve semantic units.
  - If a paragraph exceeds MAX_CHARS, split further on sentence boundaries.
  - Minimum chunk size: MIN_CHARS (avoid embedding near-empty passages).
  - Never splits numeric thresholds out of their sentence — those live in
    exact tables (D-10), not in kb_chunk. The chunker operates on PROSE only.

Usage:
    from src.ingest.chunk import chunk_prose
    passages = chunk_prose(text, source="WorkFlow.svg")
"""

from __future__ import annotations

import re

# Chunk size bounds (characters)
MAX_CHARS = 800    # soft cap per passage — split further if exceeded
MIN_CHARS = 50     # minimum meaningful passage length

# Sentence-boundary pattern for secondary splitting
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_prose(text: str, source: str) -> list[dict[str, str]]:
    """Split normalized prose into embedding-ready passages.

    Args:
        text:   Normalized text (output of normalize_text()).
        source: Source identifier (e.g. "WorkFlow.svg", "Email Templates/C1").

    Returns:
        List of dicts with keys: ``body`` (str), ``source`` (str).
        Each passage has a non-empty body.

    Guarantees:
        - Always returns >= 1 passage for non-empty input.
        - Never returns a passage with an empty body.
        - Does not split within a numeric threshold value sentence
          (thresholds are extracted separately into exact tables).
    """
    if not text or not text.strip():
        return []

    # Step 1: split on paragraph boundaries
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    passages: list[str] = []
    for para in paragraphs:
        if len(para) <= MAX_CHARS:
            passages.append(para)
        else:
            # Step 2: secondary split on sentence boundaries
            sentences = _SENTENCE_SPLIT.split(para)
            current = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if current and len(current) + 1 + len(sentence) > MAX_CHARS:
                    passages.append(current.strip())
                    current = sentence
                else:
                    current = (current + " " + sentence).strip() if current else sentence
            if current.strip():
                passages.append(current.strip())

    # Filter out passages shorter than MIN_CHARS
    result = [
        {"body": p, "source": source}
        for p in passages
        if len(p) >= MIN_CHARS
    ]

    # Fallback: if all passages were filtered (e.g. very short text),
    # return the full text as a single passage rather than an empty list.
    if not result and text.strip():
        result = [{"body": text.strip(), "source": source}]

    return result
