"""
Local template file-store loader (D-31).

Provides deterministic, file-based lookup for reply templates and sub-type → code mapping.
Replaces the semantic-RAG Knowledge MCP for the D-29/D-30 always-draft PoC.

Key functions:
  get_template_from_file(code)  -- fetch template body by code from local snapshot files
  subtype_to_code(sub_type)     -- map customer_request sub-type to candidate template codes

Security:
  - All snapshot paths are resolved ONLY from the fixed SNAPSHOTS_DIR constant anchored to
    the repo root. No path is ever derived from runtime/ticket-supplied input (T-04-00-01).
  - Fail-soft on missing file or heading: returns found=False, never fabricates a body.

No network, no DB, no embeddings, no import of src.knowledge_mcp or any RAG component.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repo-root and snapshot directory anchors
# ---------------------------------------------------------------------------

# Anchor to this file's location: src/file_store/template_store.py
# -> repo root is two levels up
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SNAPSHOTS_DIR = (
    _REPO_ROOT
    / ".planning"
    / "phases"
    / "01-knowledge-survey-conflict-inventory"
    / "snapshots"
)

CODE_MAP_FILE = (
    _REPO_ROOT
    / ".planning"
    / "phases"
    / "01-knowledge-survey-conflict-inventory"
    / "CODE-MAP-templates.md"
)

# ---------------------------------------------------------------------------
# CODE-MAP index: code -> (snapshot_file_name, verbatim_heading)
# Parsed lazily and cached; the snapshot_file_name is relative to SNAPSHOTS_DIR.
# Multiple rows per code are allowed (e.g. A1 has Bra and Pants variants).
# We store ALL rows per code so the caller gets all variants.
# ---------------------------------------------------------------------------

_INDEX: dict[str, list[dict[str, str]]] | None = None


def _parse_code_map() -> dict[str, list[dict[str, str]]]:
    """Parse CODE-MAP-templates.md table rows into {code: [{heading, snapshot_file}]}.

    Only rows from the markdown table are parsed (lines starting with `| <code> |`).
    Lines that are headers, separators, or notes are skipped.
    """
    index: dict[str, list[dict[str, str]]] = {}

    try:
        text = CODE_MAP_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("CODE-MAP-templates.md not found at %s", CODE_MAP_FILE)
        return index

    for line in text.splitlines():
        line = line.strip()
        # Only process table data rows (start and end with |, not separator lines)
        if not line.startswith("|") or not line.endswith("|"):
            continue
        # Skip separator rows like |---|---|
        if re.match(r"^\|[-| ]+\|$", line):
            continue

        parts = [p.strip() for p in line.split("|")]
        # Remove empty first/last elements from split
        parts = [p for p in parts if p != ""]

        # Expect at minimum: Code | Template Heading | Product Line | Snapshot File
        if len(parts) < 4:
            continue

        code_raw = parts[0].strip()
        heading_raw = parts[1].strip()
        snapshot_file_raw = parts[3].strip()

        # Skip header row
        if code_raw.lower() in ("code", "**code**"):
            continue
        # Skip rows where code looks like a header label
        if not code_raw or code_raw.startswith("#") or code_raw.startswith("*"):
            continue
        # Skip if heading looks like a column header
        if "heading" in heading_raw.lower() and "verbatim" in heading_raw.lower():
            continue

        # Strip inline backtick markers from heading (they appear in the table)
        heading = heading_raw.strip("`")
        # Strip inline backtick markers from snapshot file name
        snapshot_file = snapshot_file_raw.strip("`")

        if not code_raw or not heading or not snapshot_file:
            continue

        entry = {"heading": heading, "snapshot_file": snapshot_file}
        if code_raw not in index:
            index[code_raw] = []
        # Only add if not duplicate
        if entry not in index[code_raw]:
            index[code_raw].append(entry)

    return index


def _get_index() -> dict[str, list[dict[str, str]]]:
    """Return the lazily-parsed CODE-MAP index (cached after first call)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = _parse_code_map()
    return _INDEX


# ---------------------------------------------------------------------------
# Section extractor: read a markdown heading section from a snapshot file
# ---------------------------------------------------------------------------

def _extract_section(snapshot_file: str, heading: str) -> str | None:
    """Read the body of a section from a snapshot file, identified by its verbatim heading.

    Searches for the exact heading as a markdown `## <heading>` line.
    Returns the text between that heading and the next heading of equal or higher level,
    or end of file.

    Returns None if the file is not found or the heading is not present.
    Security: snapshot_file is always joined to SNAPSHOTS_DIR (never raw path from input).
    """
    snapshot_path = SNAPSHOTS_DIR / snapshot_file
    try:
        text = snapshot_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Snapshot file not found: %s", snapshot_path)
        return None
    except OSError as exc:
        logger.warning("Error reading snapshot %s: %s", snapshot_path, exc)
        return None

    lines = text.splitlines()

    # Find the line containing the heading as a markdown heading.
    # Strategy: do TWO passes.
    #   Pass 1 — prefer a proper markdown heading line (## heading, ### heading, etc.)
    #             because bare code labels (e.g. "A4-...") also appear as TOC entries
    #             near the top of snapshot files and would be matched first in a single pass.
    #   Pass 2 — fall back to bare heading only if no markdown heading was found.
    # The CODE-MAP says heading is verbatim (e.g. "B7-All products-Cannot replace").
    heading_pattern_h2 = f"## {heading}"
    heading_pattern_h2_backtick = f"## `{heading}`"

    start_idx: int | None = None
    start_level: int | None = None

    # Pass 1: look for a proper markdown heading (# or ##, etc.)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == heading_pattern_h2 or stripped == heading_pattern_h2_backtick:
            start_idx = i
            start_level = 2
            break
        # Also accept heading level 3+ (### heading)
        m = re.match(r"^(#{1,6})\s+" + re.escape(heading) + r"\s*$", stripped)
        if m:
            start_idx = i
            start_level = len(m.group(1))
            break

    # Pass 2: bare heading fallback — only if no markdown heading found
    if start_idx is None:
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == heading:
                start_idx = i
                start_level = None  # bare — collect until next markdown heading or bare code
                break

    if start_idx is None:
        logger.debug(
            "Heading %r not found in snapshot %s", heading, snapshot_file
        )
        return None

    # Collect lines from start_idx+1 until the next heading of equal or higher level
    body_lines: list[str] = []
    for j in range(start_idx + 1, len(lines)):
        line = lines[j]
        stripped = line.strip()

        if start_level is not None:
            # Stop at next markdown heading of equal or higher level
            m = re.match(r"^(#{1,6})\s", stripped)
            if m and len(m.group(1)) <= start_level:
                break
        else:
            # Bare heading mode: stop if we hit a markdown heading OR another bare heading
            # that looks like a known template code (e.g. "B1-Bra-...")
            if re.match(r"^#{1,6}\s", stripped):
                break
            # Stop at another bare heading that matches the CODE-MAP heading pattern
            # (typically "XN-...") — letter(s) + digit + dash
            if re.match(r"^[A-Z]\d+[\w\s-]+$", stripped) and stripped != heading:
                break

        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return body if body else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_template_from_file(code: str) -> dict[str, Any]:
    """Fetch a reply template by code from local snapshot files.

    Looks up the code in the CODE-MAP-templates.md index, resolves the snapshot file
    path (anchored to SNAPSHOTS_DIR), extracts the section body under the verbatim
    heading, and returns the result.

    For codes with multiple product-line variants (e.g. A1-Bra, A1-Pants), the FIRST
    matching variant whose body can be extracted is returned. All variants are listed
    in the returned `variants` field.

    Args:
        code: Template code (e.g. "B7", "A4", "F1"). Case-sensitive.

    Returns:
        dict with keys:
          - code (str): The requested code.
          - found (bool): True if the code exists in the index AND body was extracted.
          - heading (str | None): Verbatim heading from CODE-MAP.
          - body (str | None): Extracted template text. None if not found.
          - snapshot_file (str | None): Snapshot file name (relative to SNAPSHOTS_DIR).
          - variants (list[dict]): All CODE-MAP entries for this code.

    Never raises. Fail-soft on missing file or heading.
    """
    index = _get_index()

    if code not in index:
        return {
            "code": code,
            "found": False,
            "heading": None,
            "body": None,
            "snapshot_file": None,
            "variants": [],
        }

    entries = index[code]

    # Try each variant in order; return first one that yields a body
    for entry in entries:
        heading = entry["heading"]
        snapshot_file = entry["snapshot_file"]
        body = _extract_section(snapshot_file, heading)
        if body:
            return {
                "code": code,
                "found": True,
                "heading": heading,
                "body": body,
                "snapshot_file": snapshot_file,
                "variants": entries,
            }

    # All variants failed to extract a body — fail-soft
    logger.warning(
        "Code %r found in index but no body extracted (tried %d variants)",
        code, len(entries),
    )
    return {
        "code": code,
        "found": False,
        "heading": entries[0]["heading"] if entries else None,
        "body": None,
        "snapshot_file": entries[0]["snapshot_file"] if entries else None,
        "variants": entries,
    }


# ---------------------------------------------------------------------------
# Sub-type → template code mapping (from SKILL.md ground-and-draft table)
# ---------------------------------------------------------------------------

# Ordered candidate codes per customer_request sub-type.
# Source: .claude/skills/ground-and-draft/SKILL.md "Sub-type → template code mapping" table.
# Review returns [] — confirmed Phase-1 gap, no template exists.
_SUBTYPE_TO_CODES: dict[str, list[str]] = {
    "Return": [
        # Non-defective return (B-codes first — most common path)
        "B5", "B6", "B7", "B3",
        # 365-day guarantee variants
        "B9", "B10", "B11", "B12", "B13", "B8",
        # Defective return (A-codes)
        "A4", "A5", "A6", "A7", "A8", "A9",
        # Out-of-warranty
        "C1",
    ],
    "Replace": [
        # Can-replace paths (A-codes)
        "A1", "A2", "A3",
        # Non-defective (B-codes)
        "B1", "B2",
        # DNR / RTS shipping replacement
        "G11", "G14",
    ],
    "Partial_Refund": [
        # 50% refund + 40% discount (most common)
        "B7",
        # Variant unavailable
        "B3",
        # Partial refund path
        "A9",
    ],
    "Full_Refund": [
        # Evidence provided
        "A4",
        # Evidence needed
        "A5",
        # Other full-refund paths
        "A9",
        # DNR replacement-or-full-refund
        "G15",
    ],
    # Review: NO TEMPLATE — Phase-1 confirmed gap
    "Review": [],
    "Cancel_Order": [
        # New/Processing/Pending — can cancel (reason-based retention)
        "F1", "F2", "F3", "F4", "F7", "F9", "F10", "F14", "F15", "F16", "F21", "F23",
        # TA (in-transit, need SCE)
        "F5", "F17", "F18",
        # TO (delivered, cannot cancel)
        "F6", "F8", "F11", "F19", "F20",
        # Next responses
        "F12", "F13", "F22",
    ],
    "Change_Shipping_Address": ["E1", "E2", "E3", "E13"],
    "Change_Product_Variant": ["E4", "E5", "E6", "E7", "E10", "E11", "E12"],
    "Ask_About_Delivery_Status": [
        # Status + comp
        "G1", "G2", "G4", "G5", "G6", "G7", "G8", "G9",
        # DNR / RTS
        "G10", "G13", "G14", "G15",
    ],
    # Informational sub-types — no commitment template
    "Ask_About_Order": [],
    "Ask_About_Policy": [],
    "Ask_About_Product": [],
    "Ask_About_Promotion": [],
}


def subtype_to_code(sub_type: str) -> list[str]:
    """Map a customer_request sub-type to an ordered list of candidate template codes.

    Returns the ordered candidate codes per the SKILL.md sub-type → code mapping table.
    Returns [] for sub-types with no template (Review, Ask_About_* informational flows,
    or any unknown sub-type).

    Args:
        sub_type: The customer_request sub-type string (e.g. "Return", "Review").

    Returns:
        list[str]: Ordered candidate template codes. Always a list; never raises.
    """
    return list(_SUBTYPE_TO_CODES.get(sub_type, []))
