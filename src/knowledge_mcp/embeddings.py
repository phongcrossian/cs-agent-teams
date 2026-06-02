"""
Voyage voyage-3-large embeddings wrapper (CLAUDE.md mandate / KB-05).

Architecture boundary: this module is the ONLY place that calls the Voyage AI API.
All other code must call embed_query() or embed_documents() from here.

Lazy singleton pattern (mirror src/guards/pii.py _get_engines):
  - voyageai.Client is initialized on first call (loading is lightweight but
    we want consistent singleton behavior and testability via monkeypatch).
  - Tests use the stub_embedder fixture (conftest.py) to replace these functions
    with fixed 1024-dim zero vectors — no live Voyage calls in unit tests.

Security:
  - VOYAGE_API_KEY is read from env by voyageai.Client() automatically.
  - The key is NEVER logged (settings.__repr__ excludes voyage_api_key).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy singleton — populated on first call
_vo_client = None


def _get_client():
    """Return the voyageai.Client singleton, initializing on first call.

    Mirror of src/guards/pii.py _get_engines() lazy-init pattern.
    Reads VOYAGE_API_KEY from environment (voyageai.Client default behavior).
    """
    global _vo_client
    if _vo_client is None:
        import voyageai  # deferred import — not required for tests (stub_embedder)
        _vo_client = voyageai.Client()
    return _vo_client


async def embed_query(text: str) -> list[float]:
    """Embed a single query string for semantic search.

    Uses input_type='query' (Voyage distinction from 'document').
    Returns a 1024-dimensional float vector (voyage-3-large default).

    Args:
        text: The query string to embed.

    Returns:
        List of 1024 floats.
    """
    from src.config import settings

    client = _get_client()
    result = client.embed(
        [text],
        model=settings.voyage_model,
        input_type="query",
        output_dimension=settings.voyage_output_dimension,
    )
    return result.embeddings[0]


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document chunks for ingest.

    Uses input_type='document' (Voyage distinction from 'query').
    Returns a list of 1024-dimensional float vectors.

    Args:
        texts: List of document strings to embed.

    Returns:
        List of lists of 1024 floats, one per input text.
    """
    from src.config import settings

    if not texts:
        return []

    client = _get_client()
    result = client.embed(
        texts,
        model=settings.voyage_model,
        input_type="document",
        output_dimension=settings.voyage_output_dimension,
    )
    return result.embeddings
