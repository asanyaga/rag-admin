"""Tests for LLM extraction context utilities."""
import pytest
from app.cdm.models import (
    ParsedDocument, Page, Block, BlockRole,
)
from app.ports.data_extraction import FieldCitation


def _make_parsed_doc(blocks=None, full_markdown=None) -> ParsedDocument:
    blocks = blocks or []
    pages = []
    page_indices = sorted({b.page_index for b in blocks}) if blocks else [0]
    for idx in page_indices:
        page_block_ids = [b.id for b in blocks if b.page_index == idx]
        pages.append(Page(index=idx, block_ids=page_block_ids))
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=len(pages) or 1,
        pages=pages,
        blocks=blocks,
        full_markdown=full_markdown,
    )


def _make_block(id_, text, page_index=0, reading_order=None, markdown=None):
    return Block(
        id=id_,
        role=BlockRole.PARAGRAPH,
        native_type="paragraph",
        text=text,
        markdown=markdown,
        page_index=page_index,
        reading_order=reading_order,
    )


class TestBuildExtractionContext:
    def test_page_markers_injected(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc([
            _make_block("b1", "Page one text", page_index=0),
            _make_block("b2", "Page two text", page_index=1),
        ])
        ctx = build_extraction_context(doc)
        assert "<!-- page: 0 -->" in ctx
        assert "<!-- page: 1 -->" in ctx
        assert "Page one text" in ctx
        assert "Page two text" in ctx

    def test_page_marker_before_block_text(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc([_make_block("b1", "Content", page_index=2)])
        ctx = build_extraction_context(doc)
        marker_pos = ctx.index("<!-- page: 2 -->")
        content_pos = ctx.index("Content")
        assert marker_pos < content_pos

    def test_block_ids_not_injected_by_default(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc([_make_block("my-block-id", "Text", page_index=0)])
        ctx = build_extraction_context(doc)
        assert "my-block-id" not in ctx

    def test_block_ids_injected_when_flag_set(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc([_make_block("my-block-id", "Text", page_index=0)])
        ctx = build_extraction_context(doc, inject_block_ids=True)
        assert "<!-- block: my-block-id -->" in ctx

    def test_uses_block_markdown_over_text(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        block = _make_block("b1", "plain text", markdown="**rich text**", page_index=0)
        doc = _make_parsed_doc([block])
        ctx = build_extraction_context(doc)
        assert "**rich text**" in ctx
        assert "plain text" not in ctx

    def test_reading_order_respected(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc([
            _make_block("b1", "Second", page_index=0, reading_order=2),
            _make_block("b2", "First", page_index=0, reading_order=1),
        ])
        ctx = build_extraction_context(doc)
        assert ctx.index("First") < ctx.index("Second")

    def test_fallback_to_full_markdown_when_no_blocks(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc(blocks=[], full_markdown="# Fallback content")
        ctx = build_extraction_context(doc)
        assert "Fallback content" in ctx

    def test_fallback_to_full_text_when_no_markdown(self):
        from app.adapters.extraction.llm_context import build_extraction_context
        doc = _make_parsed_doc(blocks=[], full_markdown=None)
        doc = doc.model_copy(update={"full_text": "plain text fallback"})
        ctx = build_extraction_context(doc)
        assert "plain text fallback" in ctx


class TestAugmentSchemaWithSources:
    def test_flat_schema_gets_source_siblings(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {
            "type": "object",
            "properties": {
                "total": {"type": "number"},
                "vendor": {"type": "string"},
            },
        }
        aug = augment_schema_with_sources(schema)
        props = aug["properties"]
        assert "total__source" in props
        assert "vendor__source" in props
        assert "page_index" in props["total__source"]["properties"]
        assert "block_id" in props["total__source"]["properties"]

    def test_source_type_is_nullable_object(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object", "properties": {"x": {"type": "string"}}
        })
        assert aug["properties"]["x__source"]["type"] == ["object", "null"]

    def test_source_object_has_additional_properties_false(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object", "properties": {"x": {"type": "string"}}
        })
        assert aug["properties"]["x__source"]["additionalProperties"] is False

    def test_source_required_contains_both_fields(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object", "properties": {"x": {"type": "string"}}
        })
        assert set(aug["properties"]["x__source"]["required"]) == {"page_index", "block_id"}

    def test_block_id_is_nullable_string(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object", "properties": {"x": {"type": "string"}}
        })
        assert aug["properties"]["x__source"]["properties"]["block_id"]["type"] == ["string", "null"]

    def test_parent_object_gets_additional_properties_false(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object", "properties": {"x": {"type": "string"}}
        })
        assert aug["additionalProperties"] is False

    def test_source_fields_added_to_parent_required(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        aug = augment_schema_with_sources({
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        })
        assert "x__source" in aug["required"]

    def test_original_fields_preserved(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        aug = augment_schema_with_sources(schema)
        assert aug["properties"]["x"] == {"type": "string"}

    def test_nested_object_leaf_gets_source(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {"street": {"type": "string"}},
                }
            },
        }
        aug = augment_schema_with_sources(schema)
        nested = aug["properties"]["address"]["properties"]
        assert "street__source" in nested
        assert "address__source" not in aug["properties"]

    def test_array_items_get_source_siblings(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"sku": {"type": "string"}},
                    },
                }
            },
        }
        aug = augment_schema_with_sources(schema)
        item_props = aug["properties"]["items"]["items"]["properties"]
        assert "sku__source" in item_props

    def test_full_level_includes_block_id(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {"type": "object", "properties": {"sku": {"type": "string"}}}
        out = augment_schema_with_sources(schema, level="full")
        props = out["properties"]["sku__source"]["properties"]
        assert "page_index" in props and "block_id" in props

    def test_page_only_level_drops_block_id(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {"type": "object", "properties": {"sku": {"type": "string"}}}
        out = augment_schema_with_sources(schema, level="page_only")
        props = out["properties"]["sku__source"]["properties"]
        assert "page_index" in props and "block_id" not in props
        assert out["properties"]["sku__source"]["required"] == ["page_index"]

    def test_off_level_adds_no_sources(self):
        from app.adapters.extraction.llm_context import augment_schema_with_sources
        schema = {"type": "object", "properties": {"sku": {"type": "string"}}}
        out = augment_schema_with_sources(schema, level="off")
        assert "sku__source" not in out["properties"]
        assert out == schema


class TestStripSourceFields:
    def test_clean_data_and_citations_returned(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw = {
            "total": 1000,
            "total__source": {"page_index": 2, "block_id": "blk-abc"},
        }
        clean, citations = strip_source_fields(raw, schema)
        assert clean == {"total": 1000}
        assert len(citations) == 1
        assert citations[0].field_path == "total"
        assert citations[0].page_index == 2
        assert citations[0].block_ids == ["blk-abc"]

    def test_missing_block_id_yields_none(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        raw = {"x": "val", "x__source": {"page_index": 1}}
        _, citations = strip_source_fields(raw, schema)
        assert citations[0].block_ids is None

    def test_missing_page_index_yields_none_not_error(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        raw = {"x": "val", "x__source": {}}
        _, citations = strip_source_fields(raw, schema)
        assert citations[0].page_index is None

    def test_no_source_fields_returns_empty_citations(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        raw = {"x": "val"}
        clean, citations = strip_source_fields(raw, schema)
        assert clean == {"x": "val"}
        assert citations == []

    def test_null_source_yields_no_citation(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        raw = {"x": "val", "x__source": None}
        clean, citations = strip_source_fields(raw, schema)
        assert clean == {"x": "val"}
        assert citations == []

    def test_nested_object_citations_use_dot_path(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {"street": {"type": "string"}},
                }
            },
        }
        raw = {
            "address": {
                "street": "123 Main St",
                "street__source": {"page_index": 0},
            }
        }
        clean, citations = strip_source_fields(raw, schema)
        assert clean == {"address": {"street": "123 Main St"}}
        assert citations[0].field_path == "address.street"

    def test_array_items_citations_use_bracket_path(self):
        from app.adapters.extraction.llm_context import strip_source_fields
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"sku": {"type": "string"}},
                    },
                }
            },
        }
        raw = {
            "items": [
                {"sku": "ABC", "sku__source": {"page_index": 1}},
                {"sku": "DEF", "sku__source": {"page_index": 2}},
            ]
        }
        clean, citations = strip_source_fields(raw, schema)
        assert clean == {"items": [{"sku": "ABC"}, {"sku": "DEF"}]}
        assert citations[0].field_path == "items[0].sku"
        assert citations[1].field_path == "items[1].sku"
