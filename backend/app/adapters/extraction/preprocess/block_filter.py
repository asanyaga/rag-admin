"""Preprocess stages that drop blocks before extraction."""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument


def block_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    """Return a derived doc with blocks of the named roles removed."""
    drop = {r.lower() for r in (config.get("drop") or [])}
    if not drop:
        return doc
    kept = [b for b in doc.blocks if b.role.value.lower() not in drop]
    return doc.model_copy(update={
        "blocks": kept,
        "derived_from": doc.parse_run_id,
        "derivation": "preprocess:block_filter",
    })


def category_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    """SEAM (deferred): scope doc to pages/blocks in classification regions.

    Implemented in a follow-up spec; will read an upstream classificationRunId.
    """
    raise NotImplementedError(
        "category_filter is not yet implemented. It will scope the document to "
        "pages matching the configured categories using an upstream classification run."
    )
