"""
Pydantic models for the Knowledge MCP query surface (KB-05).

These models define the wire contracts for:
  - semantic_search: SemanticSearchResult containing cited passages (Citation)
  - lookup_threshold / lookup_code: ThresholdResult, dict
  - get_template: TemplateResult

D-12 authority hierarchy stored in Citation.authority_rank:
  WorkFlow.svg = 3 > Email Templates = 2 > Confluence = 1

D-13 conflict flag is in SemanticSearchResult.conflict.
D-14 override resolution is in SemanticSearchResult.resolved_by_override.
D-15 stale downrank/flag is in Citation.recency_flag.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Citation(BaseModel):
    """A single retrieved passage with full provenance metadata.

    Carries D-12 authority rank, D-15 recency flag, and RRF score so
    the Phase-4 caller can apply its own ranking policy if needed.

    conflict_id: populated from kb_chunk.metadata["conflict_id"] (set at ingest
    time for prose chunks linked to a CONFLICT-INVENTORY CONTRA entry) or from
    policy_threshold.conflict_id for threshold-based citations. Used by
    _extract_conflict_ids() to look up policy_resolution override rows (D-14).
    NEVER encoded in snapshot_version — that field is the ingest run_id only.
    """

    text: str
    source: str             # e.g. "WorkFlow.svg" | "Email Templates/warranty.md" | "Confluence/returns"
    source_type: str        # "policy_prose" | "template" | "threshold" | "code_map"
    authority_rank: int     # D-12: WorkFlow=3, Templates=2, Confluence=1
    recency_flag: Optional[str] = None  # D-15: "stale" if CONFLICT-INVENTORY flagged, else None
    snapshot_version: str   # run_id from ingest run (idempotent ingest key)
    score: float            # RRF fused score (higher = more relevant)
    conflict_id: Optional[str] = None  # D-14: CONTRA-* if chunk is part of a known conflict


class SemanticSearchResult(BaseModel):
    """Result of a semantic search query over the Knowledge RAG store.

    D-13: if conflicting passages are present, conflict=True and ALL are returned
    (MCP never self-arbitrates — Phase-4 escalation reacts to conflict=True).
    D-14: if a policy_resolution override row exists, resolved_by_override=True
    and the winning passage is ordered first in citations.
    """

    citations: list[Citation]
    conflict: bool              # D-13: True if conflicting passages retrieved
    resolved_by_override: bool  # D-14: True if a policy_resolution row applied


class ThresholdResult(BaseModel):
    """Exact numeric/temporal threshold from knowledge.policy_threshold.

    D-10: value is the exact stored string — never LLM-inferred.
    e.g. threshold_id="THR-03", value="45 days from purchase date"
    """

    threshold_id: str                       # e.g. "THR-03"
    value: str                              # e.g. "45 days from purchase"
    source: str                             # origin snapshot file
    conflict_id: Optional[str] = None       # e.g. "CONTRA-01" if in CONFLICT-INVENTORY
    override_resolution: Optional[str] = None  # resolved_value from policy_resolution if present


class TemplateResult(BaseModel):
    """Reply template scaffold from knowledge.template_library.

    D-11: keyed retrieval only (by code/scenario) — not semantic search.
    """

    code: str
    scenario: str
    subject_template: str
    body_template: str
    source: str
    authority_rank: int  # D-12: Templates=2
