"""
Local template file-store package (D-31).

Replaces the semantic-RAG Knowledge MCP as the drafter's grounding surface.
Reads the 26 local template snapshots and the CODE-MAP-templates.md wiring directly
from files — no semantic_search, no embeddings, no pgvector/Voyage, no MCP.
"""

from src.file_store.template_store import get_template_from_file, subtype_to_code
from src.file_store.ticket_fields_store import (
    customer_requests_for,
    field_choices,
    level_in_choices,
)
from src.file_store.fd_classification import (
    OWNED_FIELDS,
    build_fd_property_update,
    validate_field,
)

__all__ = [
    "get_template_from_file",
    "subtype_to_code",
    # Phase 8 — FD ticket_fields enum loader + classification (REP-06)
    "level_in_choices",
    "customer_requests_for",
    "field_choices",
    "validate_field",
    "build_fd_property_update",
    "OWNED_FIELDS",
]
