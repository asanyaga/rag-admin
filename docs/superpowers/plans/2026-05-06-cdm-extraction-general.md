# CDM Extraction — General Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the extraction subsystem foundation so every extractor receives a CDM `ParsedDocument` instead of a raw file path, with a provenance model that captures page-level citations and full provider response preservation.

**Architecture:** Update the `DataExtractor` port signature, add `FieldCitation`/`ExtractionOutput` types, build shared LLM context utilities (page-annotated markdown, shadow schema, citation post-processing), redesign the registry with identity-based keys, and wire the service layer to fetch the CDM from `parse_run_id`. The `LlamaExtractAdapter` receives a stub implementing the new signature but raises `NotImplementedError` — its full refactor is a separate plan.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest-asyncio

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `backend/app/ports/data_extraction.py` | Port interface + `FieldCitation` + `ExtractionOutput` types |
| Create | `backend/app/adapters/extraction/llm_context.py` | Pure LLM context utilities (page markdown, shadow schema, citation stripping) |
| Modify | `backend/app/adapters/extraction/registry.py` | Identity-based `EXTRACTOR_PREFERENCE_ORDER`, updated factory |
| Modify | `backend/app/adapters/extraction/llamaextract.py` | Stub new port signature (raises `NotImplementedError`) |
| Modify | `backend/app/models/extraction_result.py` | Add `source_parse_run_id`, `citations`, `provider_response_raw` columns |
| Create | `backend/alembic/versions/xxxx_add_extraction_provenance_columns.py` | Alembic migration |
| Modify | `backend/app/repositories/extraction_result_repository.py` | `create` + `update_result` accept new provenance fields |
| Modify | `backend/app/schemas/extraction_result.py` | `RunExtractionRequest` uses `parse_run_id`; response types expose new fields |
| Modify | `backend/app/services/extraction_service.py` | `run_extraction` takes `parse_run_id`; `process_extraction` fetches CDM |
| Modify | `backend/app/routers/extraction.py` | Updated DI, request body, background task wiring |
| Create | `backend/tests/adapters/extraction/__init__.py` | Package marker |
| Create | `backend/tests/adapters/extraction/test_llm_context.py` | LLM context utility tests |
| Create | `backend/tests/services/test_extraction_service.py` | Service layer tests |

---

## Task 1: Update Port — `FieldCitation`, `ExtractionOutput`, `DataExtractor`

**Files:**
- Modify: `backend/app/ports/data_extraction.py`

Replace the entire file. The new `DataExtractor` port takes a CDM `ParsedDocument`; the old `file_path` signature is gone.

- [ ] **Step 1: Write failing test confirming old signature is gone and new types exist**

Create `backend/tests/ports/__init__.py` (empty) and `backend/tests/ports/test_data_extraction_port.py`:

```python
"""Tests for the DataExtractor port contract."""
from dataclasses import FrozenInstanceError
from uuid import UUID
import pytest
from app.ports.data_extraction import DataExtractor, ExtractionOutput, FieldCitation


class TestFieldCitation:
    def test_frozen(self):
        c = FieldCitation(field_path="total", page_index=1, block_ids=None, text_spans=None)
        with pytest.raises((FrozenInstanceError, TypeError)):
            c.page_index = 2  # type: ignore

    def test_page_index_can_be_none(self):
        c = FieldCitation(field_path="total", page_index=None, block_ids=None, text_spans=None)
        assert c.page_index is None

    def test_block_ids_list(self):
        c = FieldCitation(field_path="f", page_index=0, block_ids=["abc", "def"], text_spans=None)
        assert c.block_ids == ["abc", "def"]


class TestExtractionOutput:
    def test_frozen(self):
        run_id = UUID("00000000-0000-0000-0000-000000000001")
        o = ExtractionOutput(
            structured_data={}, source_parse_run_id=run_id,
            citations=None, provider_response_raw=None, extraction_metadata=None,
        )
        with pytest.raises((FrozenInstanceError, TypeError)):
            o.structured_data = {"x": 1}  # type: ignore

    def test_source_parse_run_id_required(self):
        with pytest.raises(TypeError):
            ExtractionOutput(structured_data={})  # type: ignore


class TestDataExtractorPort:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DataExtractor()  # type: ignore

    def test_concrete_must_implement_extract_and_extractor_type(self):
        class Stub(DataExtractor):
            @property
            def extractor_type(self):
                return "stub"
            async def extract(self, parsed_document, schema, config=None):
                return None
        stub = Stub()
        assert stub.extractor_type == "stub"
        assert stub.display_name == "stub"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run --directory backend python -m pytest tests/ports/test_data_extraction_port.py -v
```

Expected: `ImportError` or multiple failures — `FieldCitation`, `ExtractionOutput` not defined yet.

- [ ] **Step 3: Replace `backend/app/ports/data_extraction.py`**

```python
"""Data extraction port interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class FieldCitation:
    """Provenance link from an extracted field value back to the CDM."""
    field_path: str               # dot/bracket path: "total", "line_items[0].sku"
    page_index: int | None        # always attempted; None only when truly unavailable
    block_ids: list[str] | None   # CDM Block.id values; None in phase 1
    text_spans: list[str] | None  # verbatim text drawn from; optional


@dataclass(frozen=True)
class ExtractionOutput:
    """Extractor-agnostic output contract."""
    structured_data: dict[str, Any]           # always — clean extracted values
    source_parse_run_id: UUID                  # always — minimum provenance anchor
    citations: list[FieldCitation] | None      # LLM adapters only
    provider_response_raw: dict | None         # provider adapters only
    extraction_metadata: dict[str, Any] | None # timing, tokens, cost


class DataExtractor(ABC):
    """Port: extract structured data from a CDM ParsedDocument using a JSON Schema."""

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """Registry key, e.g. 'ollama', 'llamaextract'."""
        ...

    @property
    def display_name(self) -> str:
        return self.extractor_type

    @abstractmethod
    async def extract(
        self,
        parsed_document: Any,   # app.cdm.models.ParsedDocument — Any avoids circular import
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        """Extract structured data from a CDM ParsedDocument."""
        ...
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/ports/test_data_extraction_port.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ports/data_extraction.py backend/tests/ports/__init__.py backend/tests/ports/test_data_extraction_port.py
git commit -m "feat(extraction): update DataExtractor port — ParsedDocument input, FieldCitation, ExtractionOutput"
```

---

## Task 2: LLM Context Utilities

**Files:**
- Create: `backend/app/adapters/extraction/llm_context.py`
- Create: `backend/tests/adapters/extraction/__init__.py`
- Create: `backend/tests/adapters/extraction/test_llm_context.py`

Pure functions with no I/O. These are the shared building blocks for all LLM adapters.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/adapters/extraction/__init__.py` (empty).

Create `backend/tests/adapters/extraction/test_llm_context.py`:

```python
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
        assert props["total__source"]["type"] == "object"
        assert "page_index" in props["total__source"]["properties"]
        assert "block_id" in props["total__source"]["properties"]
        assert props["total__source"]["required"] == ["page_index"]

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
        # The outer 'address' object itself does NOT get a __source sibling
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_context.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.adapters.extraction.llm_context'`

- [ ] **Step 3: Create `backend/app/adapters/extraction/llm_context.py`**

```python
"""Shared LLM extraction context utilities.

Pure functions used by all LLM-based extraction adapters.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument
from app.ports.data_extraction import FieldCitation


def build_extraction_context(
    parsed_doc: ParsedDocument,
    inject_block_ids: bool = False,
) -> str:
    """Build page-annotated markdown context for LLM extraction.

    Outputs full_markdown with <!-- page: N --> markers before each page's
    content. When inject_block_ids is True, also prepends <!-- block: {id} -->
    before each block for phase-2 block-level citation support.

    Falls back to full_markdown (without page markers) if no blocks exist.
    """
    if not parsed_doc.blocks:
        return parsed_doc.full_markdown or parsed_doc.full_text or ""

    # Group blocks by page, preserving reading order within each page
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


def augment_schema_with_sources(schema: dict[str, Any]) -> dict[str, Any]:
    """Add __source sibling fields to every leaf property in a JSON Schema.

    Leaf fields (type != object/array) get a corresponding fieldname__source
    object with page_index (required) and block_id (optional). Nested objects
    and array item schemas are recursed into.
    """
    return _augment_recursive(schema)


def _augment_recursive(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "object" and "properties" in schema:
        new_props: dict[str, Any] = {}
        for key, value in schema["properties"].items():
            new_props[key] = _augment_recursive(value)
            if value.get("type") not in ("object", "array"):
                new_props[f"{key}__source"] = {
                    "type": "object",
                    "properties": {
                        "page_index": {"type": "integer"},
                        "block_id": {"type": "string"},
                    },
                    "required": ["page_index"],
                }
        return {**schema, "properties": new_props}

    if schema.get("type") == "array" and "items" in schema:
        return {**schema, "items": _augment_recursive(schema["items"])}

    return schema


def strip_source_fields(
    raw_data: dict[str, Any],
    original_schema: dict[str, Any],
) -> tuple[dict[str, Any], list[FieldCitation]]:
    """Strip __source fields from raw model output.

    Returns (clean_structured_data, citations). Missing page_index yields
    FieldCitation(page_index=None) rather than raising — provenance is never
    silently dropped.
    """
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
            source = source_map[key] or {}
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_context.py -v
```

Expected: All 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/llm_context.py backend/tests/adapters/extraction/__init__.py backend/tests/adapters/extraction/test_llm_context.py
git commit -m "feat(extraction): add LLM context utilities — page markers, shadow schema, citation stripping"
```

---

## Task 3: Registry Redesign

**Files:**
- Modify: `backend/app/adapters/extraction/registry.py`
- Modify: `backend/app/adapters/extraction/llamaextract.py` (stub new port signature)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/adapters/extraction/test_registry.py`:

```python
"""Tests for extraction adapter registry."""
import pytest
from unittest.mock import patch
from app.adapters.extraction.registry import (
    EXTRACTOR_PREFERENCE_ORDER,
    get_available_extractors,
    get_extractor,
)


class TestExtractorPreferenceOrder:
    def test_ollama_is_first(self):
        assert EXTRACTOR_PREFERENCE_ORDER[0] == "ollama"

    def test_opaque_providers_are_last(self):
        last_two = EXTRACTOR_PREFERENCE_ORDER[-2:]
        assert "llamaextract" in last_two
        assert "landingai" in last_two

    def test_llamaextract_after_all_llm_adapters(self):
        llm_adapters = ["ollama", "together_ai", "groq", "openai", "anthropic"]
        llamaextract_idx = EXTRACTOR_PREFERENCE_ORDER.index("llamaextract")
        for adapter in llm_adapters:
            assert EXTRACTOR_PREFERENCE_ORDER.index(adapter) < llamaextract_idx


class TestGetAvailableExtractors:
    def test_returns_list(self):
        extractors = get_available_extractors()
        assert isinstance(extractors, list)

    def test_each_entry_has_required_keys(self):
        for e in get_available_extractors():
            assert "extraction_method" in e
            assert "name" in e
            assert "description" in e

    def test_order_matches_preference_order(self):
        extractors = get_available_extractors()
        methods = [e["extraction_method"] for e in extractors]
        # All returned methods must appear in EXTRACTOR_PREFERENCE_ORDER
        for method in methods:
            assert method in EXTRACTOR_PREFERENCE_ORDER
        # Their relative order must match preference
        for i in range(len(methods) - 1):
            assert EXTRACTOR_PREFERENCE_ORDER.index(methods[i]) < EXTRACTOR_PREFERENCE_ORDER.index(methods[i + 1])


class TestGetExtractor:
    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown extraction method"):
            get_extractor("nonexistent_method")

    def test_llamaextract_returns_adapter_when_key_present(self):
        with patch("app.adapters.extraction.registry.settings") as mock_settings:
            mock_settings.LLAMA_CLOUD_KEY = "test-key"
            extractor = get_extractor("llamaextract")
            assert extractor is not None
            assert extractor.extractor_type == "llamaextract"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_registry.py -v
```

Expected: `ImportError` for `EXTRACTOR_PREFERENCE_ORDER`, plus failures for tests relying on the new ordering.

- [ ] **Step 3: Replace `backend/app/adapters/extraction/registry.py`**

```python
"""Extractor registry — maps extraction method strings to adapter instances."""
from app.config import settings
from app.ports.data_extraction import DataExtractor

EXTRACTOR_PREFERENCE_ORDER = [
    "ollama",         # open-weight, local or self-hosted — highest autonomy
    "together_ai",    # hosted open-weight
    "groq",           # hosted open-weight
    "openai",         # proprietary SOTA
    "anthropic",      # proprietary SOTA
    "llamaextract",   # opaque extraction provider
    "landingai",      # opaque extraction provider
]


def get_extractor(extraction_method: str) -> DataExtractor:
    """Get an extractor instance by method string.

    Raises ValueError for unknown methods. Adapter-specific dependencies
    (storage service, repositories) are injected by each adapter's factory.
    """
    if extraction_method == "llamaextract":
        from app.adapters.extraction.llamaextract import LlamaExtractAdapter
        api_key = settings.LLAMA_CLOUD_KEY or None
        return LlamaExtractAdapter(api_key=api_key)

    raise ValueError(f"Unknown extraction method: {extraction_method!r}")


def get_available_extractors() -> list[dict]:
    """Return info about available extraction methods in preference order."""
    all_extractors: dict[str, dict] = {}

    if settings.LLAMA_CLOUD_KEY:
        all_extractors["llamaextract"] = {
            "extraction_method": "llamaextract",
            "name": "LlamaExtract",
            "description": (
                "Structured extraction via LlamaCloud. Multimodal, supports "
                "citations and reasoning."
            ),
            "config_schema": {
                "type": "object",
                "properties": {
                    "system_prompt": {
                        "type": "string",
                        "description": "Custom extraction prompt (maps to LlamaExtract prompt_override)",
                    },
                    "extraction_mode": {
                        "type": "string",
                        "enum": ["FAST", "BALANCED", "MULTIMODAL", "PREMIUM"],
                        "default": "MULTIMODAL",
                        "description": "Extraction mode — affects quality and cost",
                    },
                    "cite_sources": {
                        "type": "boolean",
                        "default": False,
                        "description": "Trace extracted values to source pages/text",
                    },
                    "use_reasoning": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include reasoning for extraction decisions",
                    },
                    "page_range": {
                        "type": "string",
                        "description": "Pages to extract from, e.g. '1-5'",
                    },
                },
            },
        }

    # Return in EXTRACTOR_PREFERENCE_ORDER, skipping unconfigured adapters
    return [
        all_extractors[method]
        for method in EXTRACTOR_PREFERENCE_ORDER
        if method in all_extractors
    ]
```

- [ ] **Step 4: Stub the new port signature in `LlamaExtractAdapter`**

Replace `backend/app/adapters/extraction/llamaextract.py`:

```python
"""LlamaExtract adapter — stub for CDM port signature.

Full refactor in: docs/superpowers/specs/2026-05-06-llamaextract-adapter-refactor-design.md
"""
from typing import Any
from app.ports.data_extraction import DataExtractor, ExtractionOutput


class LlamaExtractAdapter(DataExtractor):
    """LlamaExtract adapter (pending CDM refactor)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def extractor_type(self) -> str:
        return "llamaextract"

    @property
    def display_name(self) -> str:
        return "LlamaExtract"

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        raise NotImplementedError(
            "LlamaExtractAdapter.extract() requires the CDM refactor. "
            "See docs/superpowers/specs/2026-05-06-llamaextract-adapter-refactor-design.md"
        )
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_registry.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/adapters/extraction/registry.py backend/app/adapters/extraction/llamaextract.py backend/tests/adapters/extraction/test_registry.py
git commit -m "feat(extraction): redesign registry with identity-based preference order; stub LlamaExtract for CDM port"
```

---

## Task 4: ORM Columns + Migration

**Files:**
- Modify: `backend/app/models/extraction_result.py`
- Create: Alembic migration (path determined at generation time)

- [ ] **Step 1: Write failing ORM test**

Create `backend/tests/models/test_extraction_result_orm.py`:

```python
"""Tests for ExtractionResult ORM model — new provenance columns."""
import pytest
from app.models.extraction_result import ExtractionResult


class TestExtractionResultColumns:
    def test_has_source_parse_run_id_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "source_parse_run_id" in columns

    def test_has_citations_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "citations" in columns

    def test_has_provider_response_raw_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "provider_response_raw" in columns

    def test_source_parse_run_id_is_nullable(self):
        col = ExtractionResult.__table__.columns["source_parse_run_id"]
        assert col.nullable is True

    def test_citations_is_nullable(self):
        col = ExtractionResult.__table__.columns["citations"]
        assert col.nullable is True

    def test_provider_response_raw_is_nullable(self):
        col = ExtractionResult.__table__.columns["provider_response_raw"]
        assert col.nullable is True
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run --directory backend python -m pytest tests/models/test_extraction_result_orm.py -v
```

Expected: 3 failures — columns do not exist yet.

- [ ] **Step 3: Add columns to `backend/app/models/extraction_result.py`**

Add these three columns after the `extraction_metadata` column (around line 45):

```python
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider_response_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_parse_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
```

Also add the new index to `__table_args__`:

```python
    __table_args__ = (
        sa.Index('ix_extraction_results_document_schema', 'document_id', 'extraction_schema_id'),
        sa.Index('ix_extraction_results_document_id', 'document_id'),
        sa.Index('ix_extraction_results_status', 'status'),
        sa.Index('ix_extraction_results_parse_run', 'source_parse_run_id'),  # new
    )
```

- [ ] **Step 4: Run ORM tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/models/test_extraction_result_orm.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Generate and verify the Alembic migration**

```bash
uv run --directory backend alembic revision --autogenerate -m "add_extraction_provenance_columns"
```

Open the generated file in `backend/alembic/versions/`. Verify it contains:

```python
def upgrade() -> None:
    op.add_column('extraction_results', sa.Column('citations', sa.JSON(), nullable=True))
    op.add_column('extraction_results', sa.Column('provider_response_raw', sa.JSON(), nullable=True))
    op.add_column('extraction_results', sa.Column('source_parse_run_id', sa.UUID(), nullable=True))
    op.create_foreign_key(None, 'extraction_results', 'parse_runs', ['source_parse_run_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_extraction_results_parse_run', 'extraction_results', ['source_parse_run_id'])

def downgrade() -> None:
    op.drop_index('ix_extraction_results_parse_run', table_name='extraction_results')
    op.drop_constraint(None, 'extraction_results', type_='foreignkey')
    op.drop_column('extraction_results', 'source_parse_run_id')
    op.drop_column('extraction_results', 'provider_response_raw')
    op.drop_column('extraction_results', 'citations')
```

If the autogenerate missed any of the above, add them manually.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/extraction_result.py backend/alembic/versions/ backend/tests/models/test_extraction_result_orm.py
git commit -m "feat(extraction): add source_parse_run_id, citations, provider_response_raw columns to extraction_results"
```

---

## Task 5: Repository Update

**Files:**
- Modify: `backend/app/repositories/extraction_result_repository.py`

Update `create` and `update_result` to accept the new provenance fields. Both new parameters are optional to preserve backward-compat with existing call sites.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/repositories/test_extraction_result_repository.py`:

```python
"""Tests for ExtractionResultRepository provenance fields."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.models.extraction_result import ExtractionResult, ExtractionResultStatus


def _make_mock_result(**kwargs):
    result = MagicMock(spec=ExtractionResult)
    result.id = kwargs.get("id", uuid4())
    result.structured_data = kwargs.get("structured_data", None)
    result.citations = kwargs.get("citations", None)
    result.provider_response_raw = kwargs.get("provider_response_raw", None)
    result.extraction_metadata = kwargs.get("extraction_metadata", None)
    result.status = kwargs.get("status", ExtractionResultStatus.pending)
    result.source_parse_run_id = kwargs.get("source_parse_run_id", None)
    return result


class TestCreateAcceptsSourceParseRunId:
    @pytest.mark.asyncio
    async def test_create_passes_source_parse_run_id_to_orm(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        doc_id = uuid4()
        schema_id = uuid4()
        user_id = uuid4()
        parse_run_id = uuid4()

        # Capture the ExtractionResult instance passed to session.add
        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
        session.add.side_effect = capture_add

        await repo.create(
            document_id=doc_id,
            source_parse_run_id=parse_run_id,
            extraction_schema_id=schema_id,
            schema_definition_snapshot={"type": "object"},
            extraction_method="ollama",
            created_by=user_id,
        )
        assert added_instance is not None
        assert added_instance.source_parse_run_id == parse_run_id

    @pytest.mark.asyncio
    async def test_create_without_source_parse_run_id_defaults_none(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
        session.add.side_effect = capture_add

        await repo.create(
            document_id=uuid4(),
            extraction_schema_id=uuid4(),
            schema_definition_snapshot={},
            extraction_method="ollama",
            created_by=uuid4(),
        )
        assert added_instance.source_parse_run_id is None


class TestUpdateResultAcceptsProvenanceFields:
    @pytest.mark.asyncio
    async def test_update_result_sets_citations(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        citations_data = [{"field_path": "total", "page_index": 1, "block_ids": None, "text_spans": None}]
        await repo.update_result(
            result_id=mock_result.id,
            structured_data={"total": 1000},
            citations=citations_data,
        )
        assert mock_result.citations == citations_data

    @pytest.mark.asyncio
    async def test_update_result_sets_provider_response_raw(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        raw = {"data": {"total": 1000}, "_meta": {"model": "llama"}}
        await repo.update_result(
            result_id=mock_result.id,
            structured_data={"total": 1000},
            provider_response_raw=raw,
        )
        assert mock_result.provider_response_raw == raw

    @pytest.mark.asyncio
    async def test_update_result_omitting_provenance_leaves_none(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        await repo.update_result(result_id=mock_result.id, structured_data={"x": 1})
        assert mock_result.citations is None
        assert mock_result.provider_response_raw is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/repositories/test_extraction_result_repository.py -v
```

Expected: Failures — `create` doesn't accept `source_parse_run_id`, `update_result` doesn't accept `citations`/`provider_response_raw`.

- [ ] **Step 3: Update `backend/app/repositories/extraction_result_repository.py`**

Update `create` to accept `source_parse_run_id`:

```python
    async def create(
        self,
        document_id: UUID,
        extraction_schema_id: UUID,
        schema_definition_snapshot: dict,
        extraction_method: str,
        created_by: UUID,
        config: dict | None = None,
        source_parse_run_id: UUID | None = None,   # new — optional for compat
    ) -> ExtractionResult:
        """Create a new pending extraction result."""
        result = ExtractionResult(
            document_id=document_id,
            source_parse_run_id=source_parse_run_id,    # new
            extraction_schema_id=extraction_schema_id,
            schema_definition_snapshot=schema_definition_snapshot,
            extraction_method=extraction_method,
            config=config,
            created_by=created_by,
            status=ExtractionResultStatus.pending,
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result
```

Update `update_result` to accept provenance fields:

```python
    async def update_result(
        self,
        result_id: UUID,
        structured_data: dict,
        citations: list[dict] | None = None,           # new — serialised FieldCitations
        provider_response_raw: dict | None = None,     # new — full provider response
        extraction_metadata: dict | None = None,
    ) -> ExtractionResult | None:
        """Update extraction result with completed data."""
        extraction_result = await self.get_by_id(result_id)
        if not extraction_result:
            return None

        extraction_result.structured_data = structured_data
        extraction_result.citations = citations                       # new
        extraction_result.provider_response_raw = provider_response_raw  # new
        extraction_result.extraction_metadata = extraction_metadata
        extraction_result.status = ExtractionResultStatus.completed
        extraction_result.status_message = None

        await self.session.commit()
        await self.session.refresh(extraction_result)
        return extraction_result
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/repositories/test_extraction_result_repository.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/extraction_result_repository.py backend/tests/repositories/test_extraction_result_repository.py
git commit -m "feat(extraction): update ExtractionResultRepository — source_parse_run_id, citations, provider_response_raw"
```

---

## Task 6: Schema Updates

**Files:**
- Modify: `backend/app/schemas/extraction_result.py`

`RunExtractionRequest` switches from `document_id` to `parse_run_id`. Response types expose the three new provenance fields.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/schemas/test_extraction_result_schemas.py`:

```python
"""Tests for extraction result Pydantic schemas — provenance fields."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.extraction_result import (
    RunExtractionRequest,
    ExtractionResultResponse,
)
from app.models.extraction_result import ExtractionResultStatus


class TestRunExtractionRequest:
    def test_accepts_parse_run_id(self):
        run_id = uuid4()
        req = RunExtractionRequest(
            parseRunId=str(run_id),
            extractionSchemaId=str(uuid4()),
            extractionMethod="ollama",
        )
        assert req.parse_run_id == run_id

    def test_rejects_document_id_field(self):
        with pytest.raises(Exception):
            RunExtractionRequest(
                documentId=str(uuid4()),    # old field — must not be accepted
                extractionSchemaId=str(uuid4()),
                extractionMethod="ollama",
            )


class TestExtractionResultResponse:
    def _make_mock_orm(self, **kwargs):
        from unittest.mock import MagicMock
        obj = MagicMock()
        obj.id = kwargs.get("id", uuid4())
        obj.document_id = kwargs.get("document_id", uuid4())
        obj.source_parse_run_id = kwargs.get("source_parse_run_id", uuid4())
        obj.extraction_schema_id = kwargs.get("extraction_schema_id", uuid4())
        obj.schema_definition_snapshot = kwargs.get("schema_definition_snapshot", {})
        obj.extraction_method = kwargs.get("extraction_method", "ollama")
        obj.config = kwargs.get("config", None)
        obj.structured_data = kwargs.get("structured_data", None)
        obj.citations = kwargs.get("citations", None)
        obj.provider_response_raw = kwargs.get("provider_response_raw", None)
        obj.extraction_metadata = kwargs.get("extraction_metadata", None)
        obj.status = kwargs.get("status", ExtractionResultStatus.pending)
        obj.status_message = kwargs.get("status_message", None)
        obj.started_at = kwargs.get("started_at", None)
        obj.created_by = kwargs.get("created_by", uuid4())
        obj.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        obj.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
        return obj

    def test_source_parse_run_id_in_response(self):
        run_id = uuid4()
        obj = self._make_mock_orm(source_parse_run_id=run_id)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.source_parse_run_id == run_id

    def test_citations_in_response(self):
        citations = [{"field_path": "total", "page_index": 1, "block_ids": None, "text_spans": None}]
        obj = self._make_mock_orm(citations=citations)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.citations == citations

    def test_provider_response_raw_in_response(self):
        raw = {"data": {"x": 1}}
        obj = self._make_mock_orm(provider_response_raw=raw)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.provider_response_raw == raw

    def test_null_provenance_fields_accepted(self):
        obj = self._make_mock_orm(citations=None, provider_response_raw=None, source_parse_run_id=None)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.citations is None
        assert resp.provider_response_raw is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/schemas/test_extraction_result_schemas.py -v
```

Expected: Failures — `parse_run_id` not in request, new response fields missing.

- [ ] **Step 3: Update `backend/app/schemas/extraction_result.py`**

Replace `RunExtractionRequest` and `ExtractionResultResponse`:

```python
class RunExtractionRequest(BaseModel):
    """Request to run an extraction against a CDM ParsedDocument."""
    parse_run_id: UUID = Field(..., alias="parseRunId")    # replaces documentId
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class ExtractionResultResponse(BaseModel):
    """Full extraction result response."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    source_parse_run_id: UUID | None = Field(None, alias="sourceParseRunId")   # new
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    schema_definition_snapshot: dict = Field(..., alias="schemaDefinitionSnapshot")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    structured_data: dict | None = Field(None, alias="structuredData")
    citations: list | None = Field(None, alias="citations")                    # new
    provider_response_raw: dict | None = Field(None, alias="providerResponseRaw")  # new
    extraction_metadata: dict | None = Field(None, alias="extractionMetadata")
    status: ExtractionResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    started_at: datetime | None = Field(None, alias="startedAt")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionResultResponse":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            sourceParseRunId=obj.source_parse_run_id,       # new
            extractionSchemaId=obj.extraction_schema_id,
            schemaDefinitionSnapshot=obj.schema_definition_snapshot,
            extractionMethod=obj.extraction_method,
            config=obj.config,
            structuredData=obj.structured_data,
            citations=obj.citations,                         # new
            providerResponseRaw=obj.provider_response_raw,  # new
            extractionMetadata=obj.extraction_metadata,
            status=obj.status,
            statusMessage=obj.status_message,
            startedAt=obj.started_at,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/schemas/test_extraction_result_schemas.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/extraction_result.py backend/tests/schemas/test_extraction_result_schemas.py
git commit -m "feat(extraction): update schemas — RunExtractionRequest uses parse_run_id; ExtractionResultResponse exposes provenance fields"
```

---

## Task 7: Service Layer

**Files:**
- Modify: `backend/app/services/extraction_service.py`

`run_extraction` takes `parse_run_id`; `process_extraction` fetches the CDM and passes it to the extractor.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_extraction_service.py`:

```python
"""Tests for ExtractionService CDM-based flow."""
import dataclasses
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID

from app.cdm.models import ParsedDocument, Page, Block, BlockRole
from app.models.extraction_result import ExtractionResultStatus
from app.ports.data_extraction import DataExtractor, ExtractionOutput, FieldCitation
from app.services.extraction_service import ExtractionService, process_extraction


def _make_cdm_doc(parse_run_id: str, source_document_id: str) -> ParsedDocument:
    return ParsedDocument(
        id="doc-1",
        source_document_id=source_document_id,
        parse_run_id=parse_run_id,
        page_count=1,
        pages=[Page(index=0, block_ids=["b1"])],
        blocks=[Block(id="b1", role=BlockRole.PARAGRAPH, native_type="p", text="hello", page_index=0)],
        full_markdown="hello",
    )


def _make_extraction_output(parse_run_id: UUID) -> ExtractionOutput:
    return ExtractionOutput(
        structured_data={"total": 1000},
        source_parse_run_id=parse_run_id,
        citations=[FieldCitation(field_path="total", page_index=0, block_ids=None, text_spans=None)],
        provider_response_raw=None,
        extraction_metadata={"latency_ms": 100},
    )


class StubExtractor(DataExtractor):
    def __init__(self, output: ExtractionOutput):
        self._output = output
    @property
    def extractor_type(self):
        return "stub"
    async def extract(self, parsed_document, schema, config=None):
        return self._output


class TestRunExtraction:
    @pytest.mark.asyncio
    async def test_run_extraction_uses_parse_run_id(self):
        parse_run_id = uuid4()
        source_doc_id = uuid4()
        schema_id = uuid4()
        user_id = uuid4()

        # CDM ORM row (has source_document_id)
        mock_orm_cdm = MagicMock()
        mock_orm_cdm.source_document_id = source_doc_id

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_cdm

        mock_schema = MagicMock()
        mock_schema.schema_definition = {"type": "object"}
        mock_schema.extraction_target = "PER_DOC"
        mock_schema_repo = AsyncMock()
        mock_schema_repo.get_by_id.return_value = mock_schema

        mock_result = MagicMock()
        mock_result.id = uuid4()
        mock_result_repo = AsyncMock()
        mock_result_repo.create.return_value = mock_result

        service = ExtractionService(
            schema_repo=mock_schema_repo,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
        )

        await service.run_extraction(
            parse_run_id=parse_run_id,
            extraction_schema_id=schema_id,
            extraction_method="stub",
            user_id=user_id,
        )

        mock_parsed_doc_repo.get_by_run.assert_called_once_with(parse_run_id)
        call_kwargs = mock_result_repo.create.call_args.kwargs
        assert call_kwargs["source_parse_run_id"] == parse_run_id
        assert call_kwargs["document_id"] == source_doc_id

    @pytest.mark.asyncio
    async def test_run_extraction_raises_not_found_when_parse_run_missing(self):
        from app.services.exceptions import NotFoundError
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = None

        service = ExtractionService(
            schema_repo=AsyncMock(),
            result_repo=AsyncMock(),
            parsed_document_repo=mock_parsed_doc_repo,
        )
        with pytest.raises(NotFoundError):
            await service.run_extraction(
                parse_run_id=uuid4(),
                extraction_schema_id=uuid4(),
                extraction_method="stub",
                user_id=uuid4(),
            )


class TestProcessExtraction:
    @pytest.mark.asyncio
    async def test_passes_cdm_parsed_doc_to_extractor(self):
        parse_run_id = uuid4()
        result_id = uuid4()

        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_result.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        output = _make_extraction_output(parse_run_id)
        extractor = StubExtractor(output)
        received_docs = []
        original_extract = extractor.extract
        async def capture_extract(parsed_document, schema, config=None):
            received_docs.append(parsed_document)
            return await original_extract(parsed_document, schema, config)
        extractor.extract = capture_extract

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        assert len(received_docs) == 1
        assert received_docs[0].parse_run_id == str(parse_run_id)

    @pytest.mark.asyncio
    async def test_citations_persisted_on_success(self):
        parse_run_id = uuid4()
        result_id = uuid4()
        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_result.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        output = _make_extraction_output(parse_run_id)
        extractor = StubExtractor(output)

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        call_kwargs = mock_result_repo.update_result.call_args.kwargs
        assert call_kwargs["citations"] is not None
        assert call_kwargs["citations"][0]["field_path"] == "total"

    @pytest.mark.asyncio
    async def test_marks_failed_when_parse_run_not_found(self):
        result_id = uuid4()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = uuid4()
        mock_extraction_result.schema_definition_snapshot = {}
        mock_extraction_result.config = None

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_status.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = None  # not found

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=MagicMock(),
        )

        mock_result_repo.update_status.assert_called_once_with(
            result_id, ExtractionResultStatus.failed, "ParsedDocument not found for parse_run_id"
        )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/services/test_extraction_service.py -v
```

Expected: Failures — `ExtractionService.__init__` doesn't accept `parsed_document_repo`; `run_extraction` doesn't accept `parse_run_id`.

- [ ] **Step 3: Rewrite `backend/app/services/extraction_service.py`**

Replace the `ExtractionService.__init__`, `run_extraction`, and `process_extraction`:

```python
"""Extraction service — manages extraction schemas, results, and background extraction."""
import dataclasses
import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.cdm import models as cdm_models
from app.models.extraction_result import ExtractionResultStatus
from app.ports.data_extraction import DataExtractor
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.extraction_result import (
    ExtractionSchemaResponse,
    ExtractionResultResponse,
    ExtractionResultListResponse,
    ExtractorInfoResponse,
)
from app.adapters.extraction.registry import get_available_extractors
from app.services.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

STALE_TIMEOUT = timedelta(minutes=10)


class ExtractionService:
    """Service for extraction operations."""

    def __init__(
        self,
        schema_repo: ExtractionSchemaRepository,
        result_repo: ExtractionResultRepository,
        parsed_document_repo: ParsedDocumentRepository,
    ):
        self.schema_repo = schema_repo
        self.result_repo = result_repo
        self.parsed_document_repo = parsed_document_repo

    # --- Schema CRUD (unchanged) ---

    async def create_schema(self, project_id, user_id, name, schema_definition,
                             description=None, extraction_target="PER_DOC"):
        try:
            schema = await self.schema_repo.create(
                project_id=project_id, name=name, schema_definition=schema_definition,
                created_by=user_id, description=description, extraction_target=extraction_target,
            )
        except Exception as e:
            if "uq_extraction_schemas_project_name" in str(e):
                raise ConflictError(f"Schema with name '{name}' already exists in this project")
            raise
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def get_schema(self, schema_id: UUID, user_id: UUID) -> ExtractionSchemaResponse:
        schema = await self.schema_repo.get_by_id_for_user(schema_id, user_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def list_schemas(self, project_id: UUID, user_id: UUID) -> list[ExtractionSchemaResponse]:
        schemas = await self.schema_repo.list_by_project(project_id, user_id)
        return [ExtractionSchemaResponse.from_orm_model(s) for s in schemas]

    async def update_schema(self, schema_id, user_id, name=None, description=None,
                             schema_definition=None, extraction_target=None):
        schema = await self.schema_repo.update(
            schema_id=schema_id, user_id=user_id, name=name, description=description,
            schema_definition=schema_definition, extraction_target=extraction_target,
        )
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def delete_schema(self, schema_id: UUID, user_id: UUID) -> bool:
        deleted = await self.schema_repo.delete(schema_id, user_id)
        if not deleted:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return True

    # --- Extraction ---

    async def run_extraction(
        self,
        parse_run_id: UUID,
        extraction_schema_id: UUID,
        extraction_method: str,
        user_id: UUID,
        config: dict | None = None,
    ) -> ExtractionResultResponse:
        """Create a pending extraction result anchored to a CDM ParsedDocument."""
        orm_parsed_doc = await self.parsed_document_repo.get_by_run(parse_run_id)
        if not orm_parsed_doc:
            raise NotFoundError(f"ParsedDocument for parse_run_id {parse_run_id} not found")

        schema = await self.schema_repo.get_by_id(extraction_schema_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

        merged_config = dict(config or {})
        merged_config["extraction_target"] = schema.extraction_target

        result = await self.result_repo.create(
            document_id=orm_parsed_doc.source_document_id,
            source_parse_run_id=parse_run_id,
            extraction_schema_id=extraction_schema_id,
            schema_definition_snapshot=schema.schema_definition,
            extraction_method=extraction_method,
            created_by=user_id,
            config=merged_config,
        )
        return ExtractionResultResponse.from_orm_model(result)

    # --- Results ---

    async def _reap_stale(self, result):
        if result.status != ExtractionResultStatus.pending:
            return result
        reference_time = result.started_at or result.created_at
        if not reference_time:
            return result
        age = datetime.utcnow() - reference_time.replace(tzinfo=None)
        if age > STALE_TIMEOUT:
            result = await self.result_repo.update_status(
                result.id, ExtractionResultStatus.failed,
                "Extraction job timed out (exceeded 10 minutes)",
            )
        return result

    async def get_extraction_result(self, result_id: UUID) -> ExtractionResultResponse:
        result = await self.result_repo.get_by_id(result_id)
        if not result:
            raise NotFoundError(f"Extraction result {result_id} not found")
        result = await self._reap_stale(result)
        return ExtractionResultResponse.from_orm_model(result)

    async def list_extraction_results(self, document_id: UUID) -> list[ExtractionResultListResponse]:
        results = await self.result_repo.list_by_document(document_id)
        results = [await self._reap_stale(r) for r in results]
        return [ExtractionResultListResponse.from_orm_model(r) for r in results]

    async def get_extractors(self) -> list[ExtractorInfoResponse]:
        extractors = get_available_extractors()
        return [
            ExtractorInfoResponse(
                extractionMethod=e["extraction_method"],
                name=e["name"],
                description=e["description"],
                configSchema=e.get("config_schema"),
            )
            for e in extractors
        ]


async def process_extraction(
    extraction_result_id: UUID,
    result_repo: ExtractionResultRepository,
    parsed_document_repo: ParsedDocumentRepository,
    extractor: DataExtractor,
) -> None:
    """Background task: fetch CDM ParsedDocument and run extraction."""
    try:
        await result_repo.set_started(extraction_result_id)

        extraction_result = await result_repo.get_by_id(extraction_result_id)
        if not extraction_result:
            logger.error("Extraction result %s not found during background task", extraction_result_id)
            return

        orm_parsed_doc = await parsed_document_repo.get_by_run(extraction_result.source_parse_run_id)
        if not orm_parsed_doc:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                "ParsedDocument not found for parse_run_id",
            )
            return

        cdm_doc = cdm_models.ParsedDocument.model_validate(orm_parsed_doc.content)

        output = await extractor.extract(
            parsed_document=cdm_doc,
            schema=extraction_result.schema_definition_snapshot,
            config=extraction_result.config,
        )

        citations_data = (
            [dataclasses.asdict(c) for c in output.citations]
            if output.citations is not None else None
        )

        await result_repo.update_result(
            result_id=extraction_result_id,
            structured_data=output.structured_data,
            citations=citations_data,
            provider_response_raw=output.provider_response_raw,
            extraction_metadata=output.extraction_metadata,
        )

    except Exception as e:
        logger.exception("Extraction failed for result=%s", extraction_result_id)
        try:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                str(e),
            )
        except Exception:
            logger.exception("Failed to update extraction result status for %s", extraction_result_id)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/services/test_extraction_service.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction_service.py backend/tests/services/test_extraction_service.py
git commit -m "feat(extraction): service layer — run_extraction takes parse_run_id; process_extraction fetches CDM"
```

---

## Task 8: Router Update

**Files:**
- Modify: `backend/app/routers/extraction.py`

Update the `get_extraction_service` DI factory and the `run_extraction` endpoint to use the new service signature and background task parameters.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/routers/test_extraction_router.py`:

```python
"""Tests for extraction router — parse_run_id request contract."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app


@pytest.mark.asyncio
async def test_run_extraction_accepts_parse_run_id(client: AsyncClient):
    """POST /extractions/run must accept parseRunId not documentId."""
    parse_run_id = uuid4()
    schema_id = uuid4()

    with patch("app.routers.extraction.get_extractor") as mock_factory, \
         patch("app.routers.extraction.ExtractionService.run_extraction", new_callable=AsyncMock) as mock_run:

        mock_extractor = AsyncMock()
        mock_extractor.extractor_type = "stub"
        mock_factory.return_value = mock_extractor

        mock_result = AsyncMock()
        mock_result.id = uuid4()
        mock_result.document_id = uuid4()
        mock_result.source_parse_run_id = parse_run_id
        mock_result.extraction_schema_id = schema_id
        mock_result.schema_definition_snapshot = {}
        mock_result.extraction_method = "stub"
        mock_result.config = None
        mock_result.structured_data = None
        mock_result.citations = None
        mock_result.provider_response_raw = None
        mock_result.extraction_metadata = None
        from app.models.extraction_result import ExtractionResultStatus
        mock_result.status = ExtractionResultStatus.pending
        mock_result.status_message = None
        mock_result.started_at = None
        mock_run.return_value = mock_result

        response = await client.post(
            "/extractions/run",
            json={
                "parseRunId": str(parse_run_id),
                "extractionSchemaId": str(schema_id),
                "extractionMethod": "stub",
            },
            headers={"Authorization": "Bearer test-token"},
        )

    # 401 is expected (no real auth) — the important check is NOT 422
    assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY, \
        f"422 means parseRunId was rejected: {response.json()}"


@pytest.mark.asyncio
async def test_run_extraction_rejects_document_id(client: AsyncClient):
    """documentId is no longer accepted in the request body."""
    response = await client.post(
        "/extractions/run",
        json={
            "documentId": str(uuid4()),          # old field
            "extractionSchemaId": str(uuid4()),
            "extractionMethod": "stub",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/routers/test_extraction_router.py -v
```

Expected: `test_run_extraction_accepts_parse_run_id` fails with 422 (router still expects `documentId`).

- [ ] **Step 3: Update `backend/app/routers/extraction.py`**

Replace the `get_extraction_service` dependency and the `run_extraction` endpoint:

```python
from app.repositories.parsed_document_repository import ParsedDocumentRepository  # new import


def get_extraction_service(
    db: AsyncSession = Depends(get_db),
) -> ExtractionService:
    """Dependency to create ExtractionService."""
    return ExtractionService(
        schema_repo=ExtractionSchemaRepository(db),
        result_repo=ExtractionResultRepository(db),
        parsed_document_repo=ParsedDocumentRepository(db),  # replaces document_repo
    )
```

Replace the `run_extraction` endpoint body:

```python
@router.post(
    "/extractions/run",
    response_model=ExtractionResultResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run extraction on a CDM ParsedDocument",
)
async def run_extraction(
    body: RunExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    try:
        extractor = get_extractor(body.extraction_method)
        if extractor is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown extraction method: {body.extraction_method}",
            )

        result = await service.run_extraction(
            parse_run_id=body.parse_run_id,
            extraction_schema_id=body.extraction_schema_id,
            extraction_method=body.extraction_method,
            user_id=current_user.id,
            config=body.config,
        )

        background_tasks.add_task(
            process_extraction,
            extraction_result_id=result.id,
            result_repo=ExtractionResultRepository(db),
            parsed_document_repo=ParsedDocumentRepository(db),  # replaces document_repo
            extractor=extractor,
        )

        return result

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

Remove the `document_repo` and `DocumentRepository` imports from the router — they are no longer used here.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/routers/test_extraction_router.py -v
```

Expected: Both tests pass (first passes with 401 not 422; second passes with 422).

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
uv run --directory backend python -m pytest -x -q
```

Expected: All existing tests pass. Any failure is a regression introduced by this plan.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/extraction.py backend/tests/routers/test_extraction_router.py
git commit -m "feat(extraction): update router — parse_run_id request body, ParsedDocumentRepository DI"
```

---

## Self-Review

**Spec coverage:**
- ✅ Port interface (`DataExtractor`, `FieldCitation`, `ExtractionOutput`) — Task 1
- ✅ `llm_context.py` utilities (`build_extraction_context`, `augment_schema_with_sources`, `strip_source_fields`) — Task 2
- ✅ Registry with `EXTRACTOR_PREFERENCE_ORDER` and identity-based keys — Task 3
- ✅ LlamaExtract stub for new port signature — Task 3
- ✅ ORM columns (`source_parse_run_id`, `citations`, `provider_response_raw`) — Task 4
- ✅ Alembic migration — Task 4
- ✅ Repository `create` + `update_result` new params — Task 5
- ✅ `RunExtractionRequest` uses `parse_run_id` — Task 6
- ✅ `ExtractionResultResponse` exposes new provenance fields — Task 6
- ✅ `ExtractionService.run_extraction` takes `parse_run_id` — Task 7
- ✅ `process_extraction` fetches CDM, passes to extractor — Task 7
- ✅ Router wired to new service + background task — Task 8

**Type consistency:** `FieldCitation` defined in Task 1 is used as `dataclasses.asdict(c)` in Task 7 (correct — `dataclasses.asdict` works on frozen dataclasses). `ParsedDocument` from `app.cdm.models` is used consistently across Tasks 2, 7, and 8.

**Backwards compat:** `storage_service` import is removed from the router's `run_extraction` background task but still available via `Depends(get_storage_service)` for other potential uses. If it's unused after this change, the import can be cleaned up — but leave it rather than risk a missing-dependency error until the LlamaExtract refactor supplies it.
