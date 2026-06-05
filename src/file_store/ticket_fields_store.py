"""
Static ticket_fields enum loader (Phase 8, D-29 file-store pattern).

Exposes the Freshdesk ticket_fields choices from the committed snapshot:
  - Nested Level_in → Customer_Request taxonomy
  - Flat Rootcause / Flow / Section_Flow choice lists (currently empty in snapshot)

Key functions:
  level_in_choices()                  -- the 3 macro Level_in keys
  customer_requests_for(level_in)     -- Customer_Request children for a given Level_in
  field_choices(field)                -- choices for any field by name

Security:
  - SNAPSHOT_PATH is a fixed repo-root-anchored constant; never built from runtime
    or ticket-supplied input (mirrors template_store T-04-00-01 discipline).
  - All functions fail-soft: missing file / malformed JSON / missing key returns
    an empty list, never raises.

No network, no DB, no embeddings, no MCP imports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repo-root and snapshot path anchors (same pattern as template_store.py)
# ---------------------------------------------------------------------------

# Anchor: src/file_store/ticket_fields_store.py -> repo root is 3 levels up
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SNAPSHOT_PATH = (
    _REPO_ROOT
    / ".planning"
    / "phases"
    / "01-knowledge-survey-conflict-inventory"
    / "snapshots"
    / "freshdesk-ticket-fields.json"
)

# ---------------------------------------------------------------------------
# Lazy module-level cache — parsed once, cleared by tests via _CACHE = None
# ---------------------------------------------------------------------------

_CACHE: dict[str, Any] | None = None


def _load(snapshot_path: Path | None = None) -> dict[str, Any]:
    """Parse the snapshot file once and cache the result.

    Args:
        snapshot_path: Override path for testing. None = use module-level SNAPSHOT_PATH.

    Returns:
        Parsed snapshot dict, or {} on any error (fail-soft).
    """
    global _CACHE

    # If using the default path, use the module-level cache.
    if snapshot_path is None:
        if _CACHE is not None:
            return _CACHE
        path = SNAPSHOT_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("ticket_fields snapshot not found: %s", path)
            data = {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Error reading ticket_fields snapshot %s: %s", path, exc)
            data = {}
        _CACHE = data
        return _CACHE
    else:
        # Injected path (tests): never cache at module level
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("ticket_fields snapshot not found: %s", snapshot_path)
            data = {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Error reading ticket_fields snapshot %s: %s", snapshot_path, exc)
            data = {}
        return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def level_in_choices(*, snapshot_path: Path | None = None) -> list[str]:
    """Return the macro-level Level_in keys from the snapshot.

    These are the top-level classification categories (e.g. Inquiry, Change_Request,
    Complaint). Order is preserved as stored in the snapshot.

    Args:
        snapshot_path: Optional override for testing (points to a fixture file).

    Returns:
        list[str]: The Level_in keys. Empty list if snapshot missing or malformed.
        Never raises.
    """
    try:
        data = _load(snapshot_path)
        return list(data.get("nested", {}).get("Level_in", {}).keys())
    except Exception as exc:  # pragma: no cover — defensive catch-all
        logger.error("Unexpected error in level_in_choices: %s", exc)
        return []


def customer_requests_for(level_in: str, *, snapshot_path: Path | None = None) -> list[str]:
    """Return the Customer_Request children for a given Level_in macro key.

    Args:
        level_in: The Level_in value (e.g. "Complaint", "Inquiry").
        snapshot_path: Optional override for testing.

    Returns:
        list[str]: The verbatim Customer_Request values for the given Level_in.
        Returns [] if the level_in is unknown or snapshot is missing. Never raises.
    """
    try:
        data = _load(snapshot_path)
        level_in_map = data.get("nested", {}).get("Level_in", {})
        return list(level_in_map.get(level_in, []))
    except Exception as exc:  # pragma: no cover — defensive catch-all
        logger.error("Unexpected error in customer_requests_for(%r): %s", level_in, exc)
        return []


def field_choices(field: str, *, snapshot_path: Path | None = None) -> list[str]:
    """Return the allowed choice values for a named FD ticket field.

    Dispatches:
      - "Level_in"        -> level_in_choices() (macro keys)
      - "Customer_Request" -> deduped union of all Level_in children (flat, order-preserving)
      - Any dropdown name  -> dropdowns[field] or [] (includes Rootcause/Flow/Section_Flow,
                             which are currently empty in the snapshot)
      - Unknown field      -> [] (fail-soft)

    Args:
        field: Field name (case-sensitive), e.g. "Level_in", "Customer_Request", "Rootcause".
        snapshot_path: Optional override for testing.

    Returns:
        list[str]: Verbatim allowed values. Empty list for unknown or empty-enum fields.
        Never raises.
    """
    try:
        if field == "Level_in":
            return level_in_choices(snapshot_path=snapshot_path)

        if field == "Customer_Request":
            data = _load(snapshot_path)
            level_in_map = data.get("nested", {}).get("Level_in", {})
            seen: set[str] = set()
            result: list[str] = []
            for children in level_in_map.values():
                for child in children:
                    if child not in seen:
                        seen.add(child)
                        result.append(child)
            return result

        # Flat dropdown fields (Rootcause, Flow, Section_Flow, Product_line, etc.)
        data = _load(snapshot_path)
        dropdowns = data.get("dropdowns", {})
        if field in dropdowns:
            return list(dropdowns[field])

        # Unknown field — fail-soft
        return []

    except Exception as exc:  # pragma: no cover — defensive catch-all
        logger.error("Unexpected error in field_choices(%r): %s", field, exc)
        return []
