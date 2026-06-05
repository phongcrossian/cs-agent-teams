"""Offline regen tool. NOT on the runtime/test path.

One-off script that fetches GET /api/v2/ticket_fields from Freshdesk PRODUCTION
(read-only, Basic Auth) and writes the static snapshot JSON used by the AI Agent
Team for offline enum lookups.

Usage (run from repo root, requires .env.prd):
    python scripts/fetch_ticket_fields_snapshot.py

Output: .planning/phases/01-knowledge-survey-conflict-inventory/snapshots/freshdesk-ticket-fields.json

SAFETY: read-only GET only, no POST. This script is never imported by the harness
or tests — the runtime path reads the committed static file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SNAPSHOT_PATH = (
    _REPO_ROOT
    / ".planning"
    / "phases"
    / "01-knowledge-survey-conflict-inventory"
    / "snapshots"
    / "freshdesk-ticket-fields.json"
)


def _load_env_prd() -> dict[str, str]:
    """Reuse the same .env.prd loader pattern as test_tickets_run.py."""
    candidate = _REPO_ROOT / ".env.prd"
    if not candidate.exists():
        for parent in _REPO_ROOT.parents:
            alt = parent / ".env.prd"
            if alt.exists():
                candidate = alt
                break
    if not candidate.exists():
        raise FileNotFoundError(
            f".env.prd not found in {_REPO_ROOT} or any parent directory."
        )
    env: dict[str, str] = {}
    for line in candidate.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def fetch_ticket_fields(domain: str, key: str) -> list[dict]:
    """GET /api/v2/ticket_fields (read-only). Returns the raw list of field objects."""
    import httpx  # local import — not a runtime dependency of the harness

    url = f"https://{domain}/api/v2/ticket_fields"
    print(f"GET {url} ...", flush=True)
    r = httpx.get(url, auth=(key, "X"), timeout=30)
    r.raise_for_status()
    return r.json()


def _extract_snapshot(fields: list[dict]) -> dict:
    """Extract the nested Level_in taxonomy and flat dropdown enums from ticket_fields.

    The cf_level_in* field is a nested_field whose choices dict maps
    Level_in values -> list of Customer_Request children.

    Flat dropdown fields are extracted to the dropdowns section by readable name.
    """
    nested: dict[str, dict] = {}
    dropdowns: dict[str, list] = {
        "Rootcause": [],
        "Flow": [],
        "Section_Flow": [],
        "Product_line": [],
        "Level_out": [],
        "Package_status": [],
        "Category": [],
    }

    # Name -> dropdown key mapping for flat fields
    _DROPDOWN_NAME_MAP: dict[str, str] = {
        "rootcause": "Rootcause",
        "cf_rootcause": "Rootcause",
        "flow": "Flow",
        "cf_flow": "Flow",
        "section_flow": "Section_Flow",
        "cf_section_flow": "Section_Flow",
        "product_line": "Product_line",
        "cf_product_line": "Product_line",
        "level_out": "Level_out",
        "cf_level_out": "Level_out",
        "package_status": "Package_status",
        "cf_package_status": "Package_status",
        "category": "Category",
        "cf_category": "Category",
    }

    for field in fields:
        name: str = (field.get("name") or "").lower()
        label: str = (field.get("label") or "").lower()
        field_type: str = field.get("field_type", "")
        choices = field.get("choices")

        # nested_field -> Level_in taxonomy
        if field_type == "nested_field" and name.startswith("cf_level_in"):
            if isinstance(choices, dict):
                nested["Level_in"] = {
                    level: list(subtypes)
                    for level, subtypes in choices.items()
                }
            continue

        # flat dropdown -> extract choices list
        lookup_key = name or label
        if lookup_key in _DROPDOWN_NAME_MAP:
            prop = _DROPDOWN_NAME_MAP[lookup_key]
            if isinstance(choices, list):
                dropdowns[prop] = [str(c) for c in choices if c]
            elif isinstance(choices, dict):
                dropdowns[prop] = list(choices.keys())

    return {"nested": nested, "dropdowns": dropdowns}


if __name__ == "__main__":
    from datetime import date

    print("=== fetch_ticket_fields_snapshot.py (offline regen, read-only GET) ===")
    env = _load_env_prd()
    domain = env["FRESHDESK_DOMAIN"]
    key = env["FRESHDESK_API_KEY"]

    fields = fetch_ticket_fields(domain, key)
    print(f"  fetched {len(fields)} ticket_fields", flush=True)

    extracted = _extract_snapshot(fields)

    snapshot = {
        "_meta": {
            "source": "GET /api/v2/ticket_fields",
            "captured": str(date.today()),
            "version": 1,
            "note": (
                "Static snapshot — runtime/tests MUST read this file, never the network. "
                "Regenerate with scripts/fetch_ticket_fields_snapshot.py when ticket_fields change."
            ),
        },
        "nested": extracted["nested"],
        "dropdowns": extracted["dropdowns"],
    }

    _SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote -> {_SNAPSHOT_PATH}", flush=True)
    print("Done.")
