"""Catalogue + factory for ExtractionResult transforms (mirrors chunking registry)."""
from __future__ import annotations

from app.services.extraction.transforms.base import ExtractionResultTransform
from app.services.extraction.transforms.merge_records import MergeRecords

_MERGE_RECORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "groupBy": {"type": "array", "items": {"type": "string"}},
        "keyNormalize": {
            "type": "object",
            "properties": {
                "firstTokenOnly": {"type": "boolean", "default": False},
                "stripTrailingLetters": {"type": "array", "items": {"type": "string"}},
                "stripPatterns": {"type": "array", "items": {"type": "string"}},
                "casefold": {"type": "boolean", "default": True},
            },
        },
        "spine": {
            "type": "object",
            "properties": {"whereFieldsPresent": {"type": "array", "items": {"type": "string"}}},
            "required": ["whereFieldsPresent"],
        },
        "conflict": {"type": "string", "enum": ["prefer_spine", "first_non_null"], "default": "prefer_spine"},
        "onGroupWithoutSpine": {"type": "string", "enum": ["keep", "drop"], "default": "keep"},
    },
    "required": ["groupBy", "spine"],
}


def get_transforms() -> list[dict]:
    return [
        {
            "transform_type": "merge_records",
            "name": "Merge records",
            "description": "Group rows by a normalized key and collapse non-spine rows into spine rows.",
            "config_schema": _MERGE_RECORDS_SCHEMA,
        },
    ]


def build_transform(transform_type: str) -> ExtractionResultTransform:
    if transform_type == "merge_records":
        return MergeRecords()
    raise ValueError(f"Unknown transform type: {transform_type!r}")
