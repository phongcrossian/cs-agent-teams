"""
Enum-validation + fd_property_update assembler for FD ticket re-classification (Phase 8).

Mirrors the allowed-template-codes guard discipline:
  - AI must pick a VERBATIM enum value for each owned field
  - An out-of-enum value is FLAGGED (status "invalid"), NEVER silently accepted/coerced
  - An empty enum (Rootcause/Flow/Section_Flow currently empty in snapshot) is
    "unverifiable" — NOT valid, NOT invalid
  - Missing value -> "missing" (never fabricated)

Owned fields: Level_in, Customer_Request, Rootcause, Flow, Section_Flow (REP-06 scope).
Out-of-scope fields (Level_out, Package_status, Handler, etc.) are NEVER emitted.

Security (threat register 08-01):
  T-08-01: Every value validated against loaded enum; out-of-enum -> "invalid"
  T-08-02: Paths anchored in ticket_fields_store; never from runtime input
  T-08-03: OWNED_FIELDS hard-limits output to the 5 core dropdowns
  T-08-04: ticket_fields enums are non-PII taxonomy labels

No network, no DB, no embeddings, no submit_reply, no Freshdesk write.
This module is ADVISORY/ADDITIVE only (D-33): it returns data, never posts.
"""

from __future__ import annotations

import logging
from typing import Any

from src.file_store.ticket_fields_store import field_choices, customer_requests_for

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Owned-field scope (REP-06; per 08-CONTEXT locked field coverage)
# Out-of-scope fields: Level_out, Package_status, Product_label, Handler,
# SCE_team, Call_type, Request_to_SCE, Category — NEVER emitted.
# ---------------------------------------------------------------------------

OWNED_FIELDS: tuple[str, ...] = (
    "Level_in",
    "Customer_Request",
    "Rootcause",
    "Flow",
    "Section_Flow",
)

# Map from ai_props key (lowercase/snake) to canonical FD field name
_AI_KEY_TO_FIELD: dict[str, str] = {
    "level_in": "Level_in",
    "customer_request": "Customer_Request",
    "rootcause": "Rootcause",
    "flow": "Flow",
    "section_flow": "Section_Flow",
    # Accept "step" as an alias for Section_Flow (per plan: "section_flow" / "step" as available)
    "step": "Section_Flow",
}


# ---------------------------------------------------------------------------
# validate_field
# ---------------------------------------------------------------------------

def validate_field(
    field: str,
    value: str | None,
    *,
    allowed: list[str] | None = None,
) -> dict[str, Any]:
    """Validate a single AI-supplied field value against the enum.

    Status semantics:
      "valid"        -- value is non-empty AND in a non-empty allowed set
      "invalid"      -- value is non-empty BUT NOT in a non-empty allowed set
                        (verbatim value preserved; never coerced)
      "unverifiable" -- allowed set is empty (enum not yet populated in snapshot)
                        Cannot confirm or deny; NOT the same as valid
      "missing"      -- value is None or empty string; field was not supplied

    Args:
        field:   FD field name (e.g. "Level_in", "Customer_Request", "Rootcause").
        value:   The AI-supplied value. None or "" -> "missing".
        allowed: Explicit allowed set. If None, sourced via field_choices(field).

    Returns:
        dict with keys: field, value, status, allowed.
        Never raises.
    """
    try:
        # Resolve allowed set
        if allowed is None:
            allowed = field_choices(field)

        # Normalize value
        norm_value: str = value if value is not None else ""

        # Determine status
        if not norm_value:
            status = "missing"
        elif not allowed:
            # Empty enum — cannot confirm; treat as unverifiable
            status = "unverifiable"
        elif norm_value in allowed:
            status = "valid"
        else:
            status = "invalid"

        return {
            "field": field,
            "value": norm_value,
            "status": status,
            "allowed": list(allowed),
        }

    except Exception as exc:  # pragma: no cover — defensive
        logger.error("Unexpected error in validate_field(%r, %r): %s", field, value, exc)
        return {
            "field": field,
            "value": value or "",
            "status": "missing",
            "allowed": [],
        }


# ---------------------------------------------------------------------------
# build_fd_property_update
# ---------------------------------------------------------------------------

def build_fd_property_update(ai_props: dict[str, Any]) -> dict[str, Any]:
    """Assemble an advisory fd_property_update from AI classification output.

    Reads only the OWNED_FIELDS (Level_in, Customer_Request, Rootcause, Flow,
    Section_Flow). Out-of-scope fields are silently ignored and NEVER emitted.

    Nested integrity: Customer_Request is validated not only against the flat
    Customer_Request enum but also against the children of the chosen Level_in
    via customer_requests_for(level_in). A mismatch is flagged as "nested_mismatch".

    Args:
        ai_props: Dict of AI-supplied classification keys (lowercase snake_case).
                  Accepted keys: level_in, customer_request, rootcause, flow,
                  section_flow (and "step" as Section_Flow alias).

    Returns:
        dict with keys:
          fields:    {<OwnedField>: <validate_field result>}
          all_valid: bool — True only if ALL 5 owned fields have status "valid"
          advisory:  True — always; this is additive/advisory data only (D-33)

    Never raises. Never calls submit_reply, never posts to Freshdesk.
    Never fabricates a value to make it "valid".
    """
    try:
        # Extract AI values for owned fields (fail-soft: missing key -> "")
        ai_values: dict[str, str] = {}
        for ai_key, fd_field in _AI_KEY_TO_FIELD.items():
            raw = ai_props.get(ai_key)
            val = raw if isinstance(raw, str) else (str(raw) if raw is not None else "")
            # Only set if not already set (handles "step" alias — don't overwrite section_flow)
            if fd_field not in ai_values or not ai_values[fd_field]:
                ai_values[fd_field] = val

        # Validate Level_in first (needed for nested integrity check)
        level_in_value = ai_values.get("Level_in", "")
        level_in_result = validate_field("Level_in", level_in_value)

        # Nested integrity: get the allowed Customer_Request children for the chosen Level_in
        # If Level_in is missing/invalid, fall back to the flat Customer_Request enum
        if level_in_result["status"] == "valid":
            nested_allowed = customer_requests_for(level_in_value)
        else:
            nested_allowed = None  # will fall back to field_choices("Customer_Request")

        # Validate Customer_Request with nested integrity
        cr_value = ai_values.get("Customer_Request", "")
        if not cr_value:
            cr_result = validate_field("Customer_Request", cr_value)
        elif nested_allowed is not None:
            # Check against nested children of the chosen Level_in
            if not nested_allowed:
                # Level_in is valid but has no children in snapshot (edge case)
                cr_result = validate_field("Customer_Request", cr_value, allowed=nested_allowed)
            elif cr_value in nested_allowed:
                cr_result = validate_field("Customer_Request", cr_value, allowed=nested_allowed)
                # Confirmed both flat and nested — status "valid"
            else:
                # Customer_Request is not a child of the chosen Level_in -> nested_mismatch
                cr_result = {
                    "field": "Customer_Request",
                    "value": cr_value,
                    "status": "nested_mismatch",
                    "allowed": nested_allowed,
                }
        else:
            # Level_in missing/invalid -> validate against flat enum only
            cr_result = validate_field("Customer_Request", cr_value)

        # Validate remaining owned fields (Rootcause, Flow, Section_Flow)
        remaining_fields = {
            "Rootcause": ai_values.get("Rootcause", ""),
            "Flow": ai_values.get("Flow", ""),
            "Section_Flow": ai_values.get("Section_Flow", ""),
        }
        remaining_results = {
            fd_field: validate_field(fd_field, val)
            for fd_field, val in remaining_fields.items()
        }

        # Assemble fields dict in OWNED_FIELDS order
        fields: dict[str, dict[str, Any]] = {
            "Level_in": level_in_result,
            "Customer_Request": cr_result,
            **remaining_results,
        }

        # all_valid: True only when every owned field has status "valid"
        all_valid = all(
            entry["status"] == "valid"
            for entry in fields.values()
        )

        return {
            "fields": fields,
            "all_valid": all_valid,
            "advisory": True,
        }

    except Exception as exc:  # pragma: no cover — defensive
        logger.error("Unexpected error in build_fd_property_update: %s", exc)
        empty_fields = {
            f: {"field": f, "value": "", "status": "missing", "allowed": []}
            for f in OWNED_FIELDS
        }
        return {"fields": empty_fields, "all_valid": False, "advisory": True}
