"""Normalise extraction pipeline output into a canonical schema-aligned dict.

The normaliser bridges the gap between pipeline-specific output formats and
the canonical form defined by the extraction schema.  It is used by the eval
engine, and can also be used for export (CSV, database, etc.).

Usage::

    from app.services.extraction.normaliser import normalise

    canonical = normalise(
        structured_data=extraction_result.structured_data,
        extraction_method=extraction_result.extraction_method,
        schema_definition=extraction_result.schema_definition_snapshot,
    )
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Normaliser profiles — one per extraction pipeline
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict[str, str]] = {
    "llamaextract": {
        # Returns a list of per-page dicts: [{key: [page items]}, ...]
        "list_handling": "merge_pages",
        "scalar_handling": "first_page",
    },
    "landing_ai": {
        "list_handling": "flat",
        "scalar_handling": "flat",
    },
    "custom_pipeline": {
        "list_handling": "flat",
        "scalar_handling": "flat",
    },
}

_DEFAULT_PROFILE: dict[str, str] = {
    "list_handling": "auto",
    "scalar_handling": "auto",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalise(
    structured_data: Any,
    extraction_method: str,
    schema_definition: dict[str, Any],
) -> dict[str, Any]:
    """Transform pipeline output into the canonical form defined by the schema.

    Args:
        structured_data: Raw output from the extraction pipeline.
            May be a dict, a list of dicts, a list of lists, or None.
        extraction_method: Pipeline identifier (e.g. ``"llamaextract"``).
        schema_definition: The extraction schema's ``schema_definition``
            (JSON-Schema-like dict with a ``properties`` key).

    Returns:
        A dict whose keys match ``schema_definition.properties`` and whose
        values are in canonical form (scalars or flat lists of dicts).
    """
    if structured_data is None:
        return {}

    profile = PROFILES.get(extraction_method, _DEFAULT_PROFILE)
    field_types = _classify_fields(schema_definition)

    # If the data is already a dict, it may still need field-level cleanup
    if isinstance(structured_data, dict):
        return _normalise_dict(structured_data, field_types)

    if isinstance(structured_data, list):
        return _normalise_list(structured_data, field_types, profile)

    # Unrecognised type — return empty
    return {}


# ---------------------------------------------------------------------------
# Field classification
# ---------------------------------------------------------------------------

def _classify_fields(
    schema_definition: dict[str, Any],
) -> dict[str, str]:
    """Return a mapping of field_name → "array" | "scalar"."""
    properties = schema_definition.get("properties", {})
    result: dict[str, str] = {}
    for key, prop in properties.items():
        if isinstance(prop, dict) and prop.get("type") == "array":
            result[key] = "array"
        else:
            result[key] = "scalar"
    return result


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_dict(
    data: dict[str, Any],
    field_types: dict[str, str],
) -> dict[str, Any]:
    """Normalise a dict that is already in roughly the right shape."""
    # Nothing to transform — it's already a dict with the right keys.
    # Future: could validate/coerce field types here.
    return data


def _normalise_list(
    data: list,
    field_types: dict[str, str],
    profile: dict[str, str],
) -> dict[str, Any]:
    """Normalise a list-type extraction result into a dict."""
    if not data:
        return {}

    list_handling = profile.get("list_handling", "auto")
    scalar_handling = profile.get("scalar_handling", "auto")

    # Resolve "auto" by inspecting the data shape
    if list_handling == "auto" or scalar_handling == "auto":
        detected = _detect_list_shape(data, field_types)
        if list_handling == "auto":
            list_handling = detected
        if scalar_handling == "auto":
            scalar_handling = "first_page" if detected == "merge_pages" else "flat"

    if list_handling == "merge_pages":
        return _merge_pages(data, field_types, scalar_handling)

    if list_handling == "flat":
        return _handle_flat_list(data, field_types)

    # Fallback
    return _handle_flat_list(data, field_types)


def _detect_list_shape(
    data: list,
    field_types: dict[str, str],
) -> str:
    """Auto-detect whether a list is paginated results or flat records."""
    if not data or not isinstance(data[0], dict):
        return "flat"

    # If list elements have keys that overlap with the schema, it's paginated
    schema_keys = set(field_types.keys())
    first_keys = set(data[0].keys())
    if schema_keys and first_keys & schema_keys:
        return "merge_pages"

    return "flat"


def _merge_pages(
    pages: list,
    field_types: dict[str, str],
    scalar_handling: str,
) -> dict[str, Any]:
    """Merge per-page dicts into a single canonical dict.

    Array fields: concatenate lists across pages.
    Scalar fields: take from first page (or last non-empty).
    """
    merged: dict[str, Any] = {}

    for page in pages:
        if not isinstance(page, dict):
            continue
        for key, value in page.items():
            field_type = field_types.get(key, "scalar")

            if field_type == "array" and isinstance(value, list):
                if key not in merged:
                    merged[key] = []
                merged[key].extend(value)
            else:
                # Scalar: keep first non-empty value
                if scalar_handling == "first_page":
                    if key not in merged:
                        merged[key] = value
                else:
                    # last_page / overwrite
                    merged[key] = value

    return merged


def _handle_flat_list(
    data: list,
    field_types: dict[str, str],
) -> dict[str, Any]:
    """Handle a flat list of record dicts.

    If the schema has a single array field, wrap the list under that key.
    Otherwise return the first element if it's a dict.
    """
    array_fields = [k for k, t in field_types.items() if t == "array"]

    if len(array_fields) == 1 and data and isinstance(data[0], dict):
        # Wrap flat records under the single array field
        return {array_fields[0]: data}

    if data and isinstance(data[0], dict):
        return data[0]

    return {}
