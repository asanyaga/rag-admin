"""DoclingAdapter — DoclingDocument batches → ParsedDocument.

Driven by a captured fixture (`fixtures/docling_simple_text.json`, docling
2.105.0 over `custom_pipeline/fixtures/simple_text.pdf`) so these run without
invoking docling. The pure bbox/role/table helpers are covered separately in
test_docling_adapter.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.models import BlockRole, ParserKind

FIXTURE = Path(__file__).parent / "fixtures" / "docling_simple_text.json"


@pytest.fixture
def docling_doc():
    from docling_core.types.doc import DoclingDocument
    return DoclingDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture
def source_meta():
    return SourceMeta(
        source_document_id="src-1",
        parse_run_id="run-1",
        filename="simple_text.pdf",
        sha256="abc123",
    )


@pytest.fixture
def parsed(docling_doc, source_meta):
    from app.cdm.adapters.docling import DoclingAdapter
    return DoclingAdapter().adapt([(docling_doc, 0)], source_meta)


def test_adapter_declares_its_parser_kind():
    from app.cdm.adapters.docling import DoclingAdapter
    assert DoclingAdapter.parser is ParserKind.DOCLING


def test_identity_comes_from_source_meta(parsed):
    assert parsed.source_document_id == "src-1"
    assert parsed.parse_run_id == "run-1"
    assert parsed.source_filename == "simple_text.pdf"


def test_page_count_and_geometry(parsed):
    assert parsed.page_count == 2
    assert [p.index for p in parsed.pages] == [0, 1]
    for page in parsed.pages:
        assert page.width and page.width > 0
        assert page.height and page.height > 0


def test_blocks_carry_roles_from_docling_labels(parsed):
    roles = {b.role for b in parsed.blocks}
    assert BlockRole.TEXT in roles
    assert BlockRole.TABLE in roles


def test_reading_order_is_dense_and_ascending(parsed):
    orders = [b.reading_order for b in parsed.blocks]
    assert orders == list(range(len(orders)))


def test_blocks_are_ordered_by_page_then_reading_order(parsed):
    keys = [(b.page_index, b.reading_order) for b in parsed.blocks]
    assert keys == sorted(keys)


def test_block_ids_follow_the_house_convention(parsed):
    for b in parsed.blocks:
        assert b.id == f"src-1:p{b.page_index}:b{b.reading_order}"
    assert len({b.id for b in parsed.blocks}) == len(parsed.blocks)


def test_bboxes_are_normalized(parsed):
    boxed = [b for b in parsed.blocks if b.bbox is not None]
    assert boxed, "fixture should yield at least one positioned block"
    for b in boxed:
        assert 0.0 <= b.bbox.x0 <= 1.0
        assert 0.0 <= b.bbox.y0 <= 1.0
        assert 0.0 <= b.bbox.x1 <= 1.0
        assert 0.0 <= b.bbox.y1 <= 1.0


def test_pages_reference_their_blocks(parsed):
    by_page = {p.index: p.block_ids for p in parsed.pages}
    for b in parsed.blocks:
        assert b.id in by_page[b.page_index]
    assert sum(len(v) for v in by_page.values()) == len(parsed.blocks)


def test_a_structureless_table_region_still_yields_a_block(parsed):
    """docling detected a table region in this fixture but recovered no cells.
    The block must survive with an empty Table rather than being dropped — and
    crucially without raising, which is what used to empty every table block."""
    tables = [b for b in parsed.blocks if b.role is BlockRole.TABLE]
    assert tables
    assert tables[0].table is not None
    assert tables[0].table.cells == []


# ── A document with a real table ─────────────────────────────────────────────

TABLE_FIXTURE = Path(__file__).parent / "fixtures" / "docling_table_doc.json"


@pytest.fixture
def parsed_table_doc(source_meta):
    from docling_core.types.doc import DoclingDocument
    from app.cdm.adapters.docling import DoclingAdapter

    doc = DoclingDocument.model_validate(
        json.loads(TABLE_FIXTURE.read_text(encoding="utf-8")))
    return DoclingAdapter().adapt(doc, source_meta)


def _the_table(parsed):
    tables = [b for b in parsed.blocks if b.role is BlockRole.TABLE]
    assert tables, "fixture should contain a table"
    return tables[0]


def test_a_table_block_carries_its_structure(parsed_table_doc):
    table = _the_table(parsed_table_doc).table
    assert table is not None
    assert table.rows == 4
    assert table.cols == 3
    assert len(table.cells) == 12


def test_a_table_block_is_not_empty_to_text_consumers(parsed_table_doc):
    """The reported symptom: table blocks had text="" and markdown=None while
    the document markdown rendered the table fine. Chunking, search and eval
    all read the block, so an empty block loses the table entirely."""
    block = _the_table(parsed_table_doc)
    assert block.text, "a table block with no text is invisible downstream"
    assert "Bolt" in block.text
    assert block.markdown and "Bolt" in block.markdown


def test_a_table_block_keeps_its_html(parsed_table_doc):
    table = _the_table(parsed_table_doc).table
    assert table.html and "<table" in table.html


def test_the_table_survives_into_the_document_markdown(parsed_table_doc):
    assert "Bolt" in (parsed_table_doc.full_markdown or "")


def test_full_text_follows_reading_order(parsed):
    assert parsed.full_text
    assert "Hello world" in parsed.full_text
    assert parsed.full_text.index("Hello world") < parsed.full_text.index("Page two")


def test_full_markdown_is_populated(parsed):
    assert parsed.full_markdown


def test_native_type_is_preserved_for_provenance(parsed):
    assert all(b.native_type for b in parsed.blocks)


# ── Batching ──────────────────────────────────────────────────────────────────

def test_page_offset_shifts_page_indices(docling_doc, source_meta):
    """The runner splits large PDFs into batches; each batch's pages must land
    at their offset in the assembled document."""
    from app.cdm.adapters.docling import DoclingAdapter

    parsed = DoclingAdapter().adapt([(docling_doc, 0), (docling_doc, 2)], source_meta)
    assert parsed.page_count == 4
    assert [p.index for p in parsed.pages] == [0, 1, 2, 3]


def test_reading_order_is_continuous_across_batches(docling_doc, source_meta):
    from app.cdm.adapters.docling import DoclingAdapter

    parsed = DoclingAdapter().adapt([(docling_doc, 0), (docling_doc, 2)], source_meta)
    orders = [b.reading_order for b in parsed.blocks]
    assert orders == list(range(len(orders)))
    assert len({b.id for b in parsed.blocks}) == len(parsed.blocks)


def test_bare_document_is_accepted_as_a_single_batch(docling_doc, source_meta):
    from app.cdm.adapters.docling import DoclingAdapter

    parsed = DoclingAdapter().adapt(docling_doc, source_meta)
    assert parsed.page_count == 2
