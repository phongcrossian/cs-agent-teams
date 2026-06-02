"""
Snapshot readers — yield typed records from the frozen Phase-1 snapshots.

All reads are against the committed snapshot files in:
  .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/

Three public readers:
  read_prose_sources()    -> prose records for kb_chunk (WorkFlow.svg, templates, PDFs)
  read_threshold_rows()   -> exact rows for policy_threshold (D-10)
  read_code_map_rows()    -> exact rows for code_map (D-10)
  read_templates()        -> exact rows for template_library (D-11)

Authority ranks (D-12):
  WorkFlow.svg  -> 3  (primary workflow authority)
  Email Templates -> 2
  Confluence PDFs -> 1

Stale marking (D-15): sources referenced in CONFLICT-INVENTORY.md as STALE
receive recency_flag="stale" on their prose chunks.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution — relative to repo root, not this file
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SNAPSHOTS_DIR = (
    _REPO_ROOT
    / ".planning"
    / "phases"
    / "01-knowledge-survey-conflict-inventory"
    / "snapshots"
)
_PHASE1_DIR = _REPO_ROOT / ".planning" / "phases" / "01-knowledge-survey-conflict-inventory"

# Authority ranks per D-12
_RANK_WORKFLOW = 3
_RANK_TEMPLATE = 2
_RANK_CONFLUENCE = 1


# ---------------------------------------------------------------------------
# Stale source detection (D-15)
# ---------------------------------------------------------------------------

# Sources flagged as stale in CONFLICT-INVENTORY.md (STALE-01 / STALE-02)
# Billing templates (I-codes) are flagged STALE-01 as "updated frequently"
_STALE_SOURCES: frozenset[str] = frozenset(
    {
        "billing-template.md",  # STALE-01: chargeback policy updated frequently
    }
)


def _recency_flag(source_filename: str) -> str | None:
    """Return 'stale' if the source is flagged in CONFLICT-INVENTORY, else None."""
    if source_filename in _STALE_SOURCES:
        return "stale"
    return None


# ---------------------------------------------------------------------------
# SVG prose extraction (best-effort)
# ---------------------------------------------------------------------------


def _extract_svg_text(svg_path: Path) -> str:
    """Extract visible text from a Whimsical SVG export (best-effort).

    Pulls text content from <text> and <tspan> elements. The SVG is large
    (~800KB) so we use a lightweight regex approach rather than a full XML
    parser — the goal is prose extraction, not DOM traversal.
    """
    try:
        content = svg_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read WorkFlow.svg: %s", exc)
        return ""

    # Extract text between <text> and </text> tags (including tspan content)
    # Whimsical SVG uses <text> elements with nested <tspan> for all visible labels
    text_blocks: list[str] = []

    # Match <text ...>...</text> blocks
    text_element_re = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)
    tspan_re = re.compile(r"<tspan[^>]*>(.*?)</tspan>", re.DOTALL)
    html_entity_re = re.compile(r"&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);")

    for m in text_element_re.finditer(content):
        block = m.group(1)
        # Extract tspan content within each text element
        tspan_texts = tspan_re.findall(block)
        if tspan_texts:
            combined = " ".join(t.strip() for t in tspan_texts if t.strip())
        else:
            # Fallback: strip all tags
            combined = re.sub(r"<[^>]+>", " ", block).strip()

        if combined:
            # Decode basic HTML entities
            combined = html_entity_re.sub(" ", combined)
            combined = " ".join(combined.split())  # normalize whitespace
            if len(combined) > 3:  # skip very short noise labels
                text_blocks.append(combined)

    return "\n\n".join(text_blocks)


# ---------------------------------------------------------------------------
# PDF prose extraction (best-effort using pdfminer / fallback)
# ---------------------------------------------------------------------------


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a Confluence PDF (best-effort).

    Tries pdfminer.six first, then falls back to a warning and empty string.
    pdfminer is lightweight and does not require native libs beyond Python.
    """
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        return pdfminer_extract(str(pdf_path))
    except ImportError:
        logger.warning(
            "pdfminer.six not installed — cannot extract text from %s. "
            "Install with: pip install pdfminer.six",
            pdf_path.name,
        )
        return ""
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", pdf_path.name, exc)
        return ""


# ---------------------------------------------------------------------------
# Public reader: prose sources
# ---------------------------------------------------------------------------


def read_prose_sources() -> list[dict[str, Any]]:
    """Yield prose records from frozen Phase-1 snapshots.

    Returns a list of dicts with keys:
        source      str   — display path (e.g. "WorkFlow.svg")
        source_type str   — always "policy_prose"
        authority_rank int — D-12: 3=WorkFlow, 2=Templates, 1=Confluence
        recency_flag str|None — D-15: "stale" | None
        body        str   — raw (un-normalized) prose text

    Normalization and chunking are done by pipeline.py (separation of concerns).
    """
    records: list[dict[str, Any]] = []

    # 1. WorkFlow.svg — authority_rank=3
    svg_path = _SNAPSHOTS_DIR / "WorkFlow.svg"
    if svg_path.exists():
        body = _extract_svg_text(svg_path)
        if body.strip():
            source_key = "WorkFlow.svg"
            records.append(
                {
                    "source": source_key,
                    "source_type": "policy_prose",
                    "authority_rank": _RANK_WORKFLOW,
                    "recency_flag": _recency_flag("WorkFlow.svg"),
                    "conflict_id": _PROSE_CONFLICT_MAP.get(source_key),
                    "body": body,
                }
            )
    else:
        logger.warning("WorkFlow.svg not found at %s", svg_path)

    # 2. Email template .md files — authority_rank=2
    template_files = sorted(_SNAPSHOTS_DIR.glob("*.md"))
    for tmpl_path in template_files:
        # Skip situational-template (included separately); skip billing-template
        # (handled in template_library, also flagged stale)
        try:
            body = tmpl_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read template %s: %s", tmpl_path.name, exc)
            continue

        if body.strip():
            source_key = f"Email Templates/{tmpl_path.name}"
            records.append(
                {
                    "source": source_key,
                    "source_type": "policy_prose",
                    "authority_rank": _RANK_TEMPLATE,
                    "recency_flag": _recency_flag(tmpl_path.name),
                    "conflict_id": _PROSE_CONFLICT_MAP.get(tmpl_path.name)
                              or _PROSE_CONFLICT_MAP.get(source_key),
                    "body": body,
                }
            )

    # 3. Confluence PDFs — authority_rank=1
    confluence_dir = _SNAPSHOTS_DIR / "confluence"
    if confluence_dir.exists():
        for pdf_path in sorted(confluence_dir.glob("*.pdf")):
            body = _extract_pdf_text(pdf_path)
            if body.strip():
                source_key = f"Confluence/{pdf_path.name}"
                records.append(
                    {
                        "source": source_key,
                        "source_type": "policy_prose",
                        "authority_rank": _RANK_CONFLUENCE,
                        "recency_flag": _recency_flag(pdf_path.name),
                        "conflict_id": _PROSE_CONFLICT_MAP.get(pdf_path.name)
                                  or _PROSE_CONFLICT_MAP.get(source_key),
                        "body": body,
                    }
                )

    return records


# ---------------------------------------------------------------------------
# POLICY-THRESHOLD-INDEX.md parser
# ---------------------------------------------------------------------------

# Conflict mapping from CONFLICT-INVENTORY.md (CONTRA-01 involves THR-03/THR-04)
_THRESHOLD_CONFLICT_MAP: dict[str, str] = {
    "THR-03": "CONTRA-01",
    "THR-04": "CONTRA-01",
    "THR-17": "CONTRA-01",  # restatement of the same dual-warranty conflict
    "THR-06": "CONTRA-02",
    "THR-08": "CONTRA-02",
    "THR-05": "CONTRA-02",
    "THR-07": "CONTRA-03",
}

# Conflict mapping for PROSE sources (D-14 / CONFLICT-INVENTORY.md).
# Maps source filename (as stored in kb_chunk.source) -> conflict_id.
# When a prose chunk is ingested from one of these sources, its metadata
# carries the conflict_id so apply_override() (D-14) can look up a
# policy_resolution row without abusing snapshot_version.
#
# Rule: a source entry here means the source participates in at least one
# CONTRA conflict.  If a source participates in multiple conflicts the
# dominant one is listed (rarest case — most sources map to exactly one CONTRA).
_PROSE_CONFLICT_MAP: dict[str, str] = {
    # CONTRA-01: dual-warranty window (45d purchase vs 14d delivery)
    # billing-template.md is the STALE source; WorkFlow.svg is the authoritative one.
    "billing-template.md": "CONTRA-01",
    "Email Templates/billing-template.md": "CONTRA-01",
}

# Authority rank for thresholds — WorkFlow.svg is primary source
_THRESHOLD_AUTHORITY_RANK = _RANK_WORKFLOW


def read_threshold_rows() -> list[dict[str, Any]]:
    """Parse POLICY-THRESHOLD-INDEX.md into exact policy_threshold rows.

    Returns a list of dicts with keys matching knowledge.policy_threshold:
        threshold_id    str
        label           str
        value           str
        source          str
        authority_rank  int
        conflict_id     str | None  (from CONFLICT-INVENTORY CONTRA findings)
        snapshot_version str        (hardcoded to phase-1 snapshot date)

    D-10: these rows NEVER go through embeddings — exact lookup only.
    """
    index_path = _PHASE1_DIR / "POLICY-THRESHOLD-INDEX.md"
    if not index_path.exists():
        logger.warning("POLICY-THRESHOLD-INDEX.md not found at %s", index_path)
        return []

    content = index_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []

    # Parse the markdown table: skip header rows and separator rows
    # Table columns: Threshold ID | Description | Value | Source (...) | Cross-Source Status |
    # Note: rows end with a trailing | so match that explicitly
    table_re = re.compile(
        r"^\|\s*(THR-[A-Z0-9-]+|THR-S\d+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]*)\|",
        re.MULTILINE,
    )

    for m in table_re.finditer(content):
        threshold_id = m.group(1).strip()
        label = m.group(2).strip()
        value = _clean_markdown(m.group(3).strip())
        source_text = m.group(4).strip()
        # cross_source_status = m.group(5).strip()  # not stored as column

        # Determine source: extract primary source reference
        source = _extract_threshold_source(source_text)

        rows.append(
            {
                "threshold_id": threshold_id,
                "label": label,
                "value": value,
                "source": source,
                "authority_rank": _THRESHOLD_AUTHORITY_RANK,
                "conflict_id": _THRESHOLD_CONFLICT_MAP.get(threshold_id),
                "snapshot_version": "phase-1-2026-05-29",
            }
        )

    return rows


def _clean_markdown(text: str) -> str:
    """Remove markdown bold/italic markers and normalize whitespace."""
    text = re.sub(r"\*+", "", text)   # remove **bold** / *italic*
    text = re.sub(r"`+", "", text)    # remove code backticks
    text = " ".join(text.split())     # normalize whitespace
    return text.strip()


def _extract_threshold_source(source_cell: str) -> str:
    """Extract a short source label from the verbose source cell text."""
    # Most threshold sources reference a Flow number or template
    if "Flow 1" in source_cell:
        return "WorkFlow.svg Flow 1"
    if "Flow 2" in source_cell:
        return "WorkFlow.svg Flow 2"
    if "Flow 3" in source_cell:
        return "WorkFlow.svg Flow 3"
    if "Flow 4" in source_cell:
        return "WorkFlow.svg Flow 4"
    if "Flow 5" in source_cell:
        return "WorkFlow.svg Flow 5"
    if "Flow 6" in source_cell:
        return "WorkFlow.svg Flow 6"
    if "template" in source_cell.lower() or "C1" in source_cell:
        return "Email Templates/product complaint-out of guarantee-template.md"
    if "Confluence" in source_cell or "Pants guide" in source_cell or "Bra guide" in source_cell:
        return "Confluence/sizing-guides"
    # Fallback: first 60 chars
    return source_cell[:60].strip()


# ---------------------------------------------------------------------------
# CODE-MAP.md parser
# ---------------------------------------------------------------------------


def read_code_map_rows() -> list[dict[str, Any]]:
    """Parse CODE-MAP.md into exact code_map rows.

    Returns a list of dicts with keys:
        code             str
        action           str
        template_code    str | None
        source           str
        snapshot_version str
    """
    code_map_path = _PHASE1_DIR / "CODE-MAP.md"
    if not code_map_path.exists():
        logger.warning("CODE-MAP.md not found at %s", code_map_path)
        return []

    content = code_map_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []

    # Match table rows: | Code | Macro-flow | Described Action | Linked Email Template | Notes |
    # Note: rows end with trailing | so match that explicitly
    row_re = re.compile(
        r"^\|\s*([A-Z]\d+)\s*\|([^|]+)\|([^|]+)\|([^|]*)\|([^|]*)\|",
        re.MULTILINE,
    )

    for m in row_re.finditer(content):
        code = m.group(1).strip()
        # macro_flow = m.group(2).strip()
        action = _clean_markdown(m.group(3).strip())
        template_ref = m.group(4).strip()

        # Extract template code (e.g. "A1" from linked template reference)
        template_code = _extract_template_code(template_ref, code)

        rows.append(
            {
                "code": code,
                "action": action,
                "template_code": template_code,
                "source": "CODE-MAP.md",
                "snapshot_version": "phase-1-2026-05-29",
            }
        )

    return rows


def _extract_template_code(template_ref: str, code: str) -> str | None:
    """Extract the template code from a linked template reference cell."""
    if not template_ref or template_ref.strip() in ("TBD", "TBD — Plan 02", "N/A", "—"):
        return None
    # The template_ref is usually the filename + section (e.g. "§ A1-Bra")
    # Use the code itself as the template code
    return code if code else None


# ---------------------------------------------------------------------------
# Template reader (template_library rows)
# ---------------------------------------------------------------------------


def read_templates() -> list[dict[str, Any]]:
    """Read template snapshot files into template_library rows.

    Reads CODE-MAP-templates.md and the individual template .md snapshot files.
    Returns a list of dicts with keys:
        code             str
        scenario         str
        subject_template str
        body_template    str
        source           str
        authority_rank   int   (always 2 — Templates)
        snapshot_version str

    D-11: templates are retrieved by exact code lookup, not semantic search.
    """
    rows: list[dict[str, Any]] = []

    # Read CODE-MAP-templates.md for the template index
    templates_map_path = _PHASE1_DIR / "CODE-MAP-templates.md"
    if templates_map_path.exists():
        template_index = _parse_template_map(templates_map_path)
    else:
        logger.warning("CODE-MAP-templates.md not found at %s", templates_map_path)
        template_index = {}

    # Read individual template snapshot files to extract body content
    template_files = sorted(_SNAPSHOTS_DIR.glob("*.md"))
    for tmpl_path in template_files:
        file_templates = _extract_templates_from_file(tmpl_path, template_index)
        rows.extend(file_templates)

    # Dedup by code — keep last occurrence (template files may have variants)
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        seen[row["code"]] = row
    return list(seen.values())


def _parse_template_map(path: Path) -> dict[str, dict[str, str]]:
    """Parse CODE-MAP-templates.md for code -> scenario + subject mappings."""
    index: dict[str, dict[str, str]] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return index

    # Match table rows with code, scenario, subject columns
    # Table format varies — look for rows starting with | Code |
    row_re = re.compile(
        r"^\|\s*([A-Z]\d+(?:-[A-Za-z]+)?)\s*\|([^|]+)\|([^|]+)\|",
        re.MULTILINE,
    )
    for m in row_re.finditer(content):
        code = m.group(1).strip()
        scenario = _clean_markdown(m.group(2).strip())
        subject = _clean_markdown(m.group(3).strip())
        if code and scenario:
            index[code] = {"scenario": scenario, "subject": subject}

    return index


def _extract_templates_from_file(
    tmpl_path: Path, template_index: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    """Extract template rows from a single .md snapshot file.

    Looks for section headers like "## A1" or "### B3" to identify templates,
    then grabs the body content up to the next header.
    """
    rows: list[dict[str, Any]] = []
    try:
        content = tmpl_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read template file %s: %s", tmpl_path.name, exc)
        return rows

    # Split by section headers (## Code or ### Code)
    section_re = re.compile(r"^#{1,4}\s+([A-Z]\d+(?:-[A-Za-z-]+)?)\b", re.MULTILINE)
    sections = section_re.split(content)

    # sections = [preamble, code1, body1, code2, body2, ...]
    i = 1
    while i + 1 < len(sections):
        code = sections[i].strip()
        body = sections[i + 1].strip()
        i += 2

        if not code or not body:
            continue

        # Normalize code (remove variant suffix like -Bra, -Pants for base lookup)
        base_code = re.match(r"^([A-Z]\d+)", code)
        if not base_code:
            continue
        base = base_code.group(1)

        # Get scenario/subject from template index
        index_entry = template_index.get(code) or template_index.get(base) or {}
        scenario = index_entry.get("scenario", f"Template {code}")
        subject = index_entry.get("subject", "")

        # Extract subject line from body if not in index
        if not subject:
            subject_m = re.search(r"(?i)subject\s*[:\-]?\s*(.+)", body)
            if subject_m:
                subject = _clean_markdown(subject_m.group(1).strip())[:200]

        rows.append(
            {
                "code": code,
                "scenario": scenario,
                "subject_template": subject or f"Re: your {scenario} request",
                "body_template": body[:4000],  # cap at 4000 chars
                "source": f"Email Templates/{tmpl_path.name}",
                "authority_rank": _RANK_TEMPLATE,
                "snapshot_version": "phase-1-2026-05-29",
            }
        )

    return rows
