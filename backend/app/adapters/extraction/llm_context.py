"""Shared LLM extraction context utilities.

Pure functions used by all LLM-based extraction adapters.
"""
from __future__ import annotations

from typing import Any, Literal

from app.cdm.models import ParsedDocument
from app.ports.data_extraction import FieldCitation

CitationLevel = Literal["full", "page_only", "off"]


def build_extraction_context(
    parsed_doc: ParsedDocument,
    inject_block_ids: bool = False,
) -> str:
    """Build page-annotated markdown context for LLM extraction.

    Falls back to full_markdown (without page markers) if no blocks exist.
    """
    if not parsed_doc.blocks:
        return parsed_doc.full_markdown or parsed_doc.full_text or ""

    blocks_by_page: dict[int, list] = {}
    for block in parsed_doc.blocks:
        blocks_by_page.setdefault(block.page_index, []).append(block)

    for page_idx in blocks_by_page:
        blocks_by_page[page_idx].sort(
            key=lambda b: b.reading_order if b.reading_order is not None else float("inf")
        )

    parts: list[str] = []
    for page_idx in sorted(blocks_by_page.keys()):
        parts.append(f"<!-- page: {page_idx} -->")
        for block in blocks_by_page[page_idx]:
            if inject_block_ids:
                parts.append(f"<!-- block: {block.id} -->")
            content = block.markdown or block.text
            if content:
                parts.append(content)

    return "\n\n".join(parts)


def augment_schema_with_sources(
    schema: dict[str, Any], level: CitationLevel = "full"
) -> dict[str, Any]:
    """Add __source sibling fields to every leaf property in a JSON Schema.

    level controls provenance granularity:
      - "full": page_index + block_id (default)
      - "page_only": page_index only
      - "off": no __source fields (schema returned unchanged)
    """
    if level == "off":
        return schema
    return _augment_recursive(schema, level)


def _source_schema(level: CitationLevel) -> dict[str, Any]:
    if level == "page_only":
        return {
            "type": ["object", "null"],
            "properties": {"page_index": {"type": "integer"}},
            "required": ["page_index"],
            "additionalProperties": False,
        }
    return {
        "type": ["object", "null"],
        "properties": {
            "page_index": {"type": "integer"},
            "block_id": {"type": ["string", "null"]},
        },
        "required": ["page_index", "block_id"],
        "additionalProperties": False,
    }


def _augment_recursive(schema: dict[str, Any], level: CitationLevel) -> dict[str, Any]:
    if schema.get("type") == "object" and "properties" in schema:
        new_props: dict[str, Any] = {}
        new_required = list(schema.get("required") or [])

        for key, value in schema["properties"].items():
            new_props[key] = _augment_recursive(value, level)
            if value.get("type") not in ("object", "array"):
                source_key = f"{key}__source"
                new_props[source_key] = _source_schema(level)
                if source_key not in new_required:
                    new_required.append(source_key)

        result = {**schema, "properties": new_props, "additionalProperties": False}
        if new_required:
            result["required"] = new_required
        return result

    if schema.get("type") == "array" and "items" in schema:
        return {**schema, "items": _augment_recursive(schema["items"], level)}

    return schema


def strip_source_fields(
    raw_data: dict[str, Any],
    original_schema: dict[str, Any],
) -> tuple[dict[str, Any], list[FieldCitation]]:
    """Strip __source fields from raw model output, returning (clean_data, citations)."""
    citations: list[FieldCitation] = []
    clean = _strip_recursive(raw_data, original_schema, "", citations)
    return clean, citations


def _strip_recursive(
    data: dict[str, Any],
    schema: dict[str, Any],
    path_prefix: str,
    citations: list[FieldCitation],
) -> dict[str, Any]:
    source_map = {
        k[: -len("__source")]: v
        for k, v in data.items()
        if k.endswith("__source")
    }

    clean: dict[str, Any] = {}
    for key, value in data.items():
        if key.endswith("__source"):
            continue

        field_path = f"{path_prefix}.{key}" if path_prefix else key
        field_schema = (schema.get("properties") or {}).get(key, {})

        if key in source_map:
            source = source_map[key]
            if source is not None:
                raw_page = source.get("page_index")
                citations.append(
                    FieldCitation(
                        field_path=field_path,
                        page_index=int(raw_page) if raw_page is not None else None,
                        block_ids=[source["block_id"]] if source.get("block_id") else None,
                        text_spans=None,
                    )
                )

        if isinstance(value, dict) and field_schema.get("type") == "object":
            clean[key] = _strip_recursive(value, field_schema, field_path, citations)
        elif isinstance(value, list) and field_schema.get("type") == "array":
            items_schema = field_schema.get("items", {})
            clean_list: list[Any] = []
            for i, item in enumerate(value):
                item_path = f"{field_path}[{i}]"
                if isinstance(item, dict):
                    clean_list.append(_strip_recursive(item, items_schema, item_path, citations))
                else:
                    clean_list.append(item)
            clean[key] = clean_list
        else:
            clean[key] = value

    return clean
