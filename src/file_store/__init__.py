"""
Local template file-store package (D-31).

Replaces the semantic-RAG Knowledge MCP as the drafter's grounding surface.
Reads the 26 local template snapshots and the CODE-MAP-templates.md wiring directly
from files — no semantic_search, no embeddings, no pgvector/Voyage, no MCP.
"""

from src.file_store.template_store import get_template_from_file, subtype_to_code

__all__ = ["get_template_from_file", "subtype_to_code"]
