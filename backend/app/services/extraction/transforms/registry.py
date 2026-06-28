"""Catalogue + factory for ExtractionResult transforms (mirrors chunking registry)."""
from __future__ import annotations

from app.services.extraction.transforms.base import ExtractionResultTransform
from app.services.extraction.transforms.merge_records import MergeRecords
from app.services.extraction.transforms.normalize_field import NormalizeField

_RULE_TYPES = [
    "trim", "collapseWhitespace", "lowercase", "uppercase", "titlecase",
    "stripRegex", "stripTrailingChars", "stripPrefix", "stripSuffix",
    "split", "regexExtract", "replace", "alias", "nullifyIfIn",
]

_FIELD_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "sourceField": {"type": "string", "description": "Field to read. Never mutated."},
        "outputField": {"type": "string", "description": "New column to write on every row."},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": _RULE_TYPES},
                    "chars": {},
                    "pattern": {"type": "string"},
                    "prefix": {"type": "string"},
                    "suffix": {"type": "string"},
                    "delimiter": {"type": "string"},
                    "index": {"type": "integer"},
                    "group": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                    "find": {"type": "string"},
                    "replacement": {"type": "string"},
                    "map": {"type": "object"},
                    "values": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["type"],
            },
        },
    },
    "required": ["sourceField", "outputField", "rules"],
}

_NORMALIZE_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "minItems": 1,
            "items": _FIELD_ENTRY_SCHEMA,
            "description": "Ordered list of field normalizations. All run in one apply call producing one ExtractionResult.",
        },
    },
    "required": ["fields"],
}

_MERGE_RECORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "groupBy": {"type": "array", "items": {"type": "string"}},
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
            "transform_type": "normalize_field",
            "name": "Normalize field",
            "description": "Apply a rule chain to a source field and write the result to a new output column.",
            "config_schema": _NORMALIZE_FIELD_SCHEMA,
        },
        {
            "transform_type": "merge_records",
            "name": "Merge records",
            "description": "Group rows by a normalized key and collapse non-spine rows into spine rows.",
            "config_schema": _MERGE_RECORDS_SCHEMA,
        },
    ]


def build_transform(transform_type: str) -> ExtractionResultTransform:
    if transform_type == "normalize_field":
        return NormalizeField()
    if transform_type == "merge_records":
        return MergeRecords()
    raise ValueError(f"Unknown transform type: {transform_type!r}")
