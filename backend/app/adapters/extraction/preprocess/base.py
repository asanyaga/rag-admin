"""Preprocess stage registry + runner."""
from __future__ import annotations

from typing import Any, Callable

from app.adapters.extraction.preprocess.block_filter import block_filter
from app.adapters.extraction.preprocess.category_filter import category_filter
from app.cdm.models import ParsedDocument

_STAGES: dict[str, Callable[[ParsedDocument, dict[str, Any]], ParsedDocument]] = {
    "block_filter": block_filter,
    "category_filter": category_filter,
}


def get_preprocess_stages() -> list[dict]:
    return [
        {"stage": "block_filter", "name": "Block filter",
         "description": "Drop blocks by role (headers, footers, page numbers, …).",
         "config_schema": {"type": "object", "properties": {
             "drop": {"type": "array", "items": {"type": "string"}}}}},
        {"stage": "category_filter", "name": "Category filter",
         "description": "Scope extraction to pages/blocks in an upstream classification run's categories.",
         "config_schema": {"type": "object", "properties": {
             "classificationRunId": {"type": "string"},
             "categories": {"type": "array", "items": {"type": "string"}},
             "granularity": {"type": "string", "enum": ["page", "block"], "default": "page"}}}},
    ]


def apply_preprocess(doc: ParsedDocument, stages: list[dict]) -> ParsedDocument:
    for stage in stages or []:
        name = stage.get("stage")
        fn = _STAGES.get(name)
        if fn is None:
            raise ValueError(f"Unknown preprocess stage: {name!r}")
        doc = fn(doc, stage.get("config") or {})
    return doc
