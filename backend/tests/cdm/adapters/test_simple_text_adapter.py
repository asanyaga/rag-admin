import pytest
from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.simple_text import SimpleTextAdapter
from app.cdm.models import BlockRole, ParserKind


SOURCE_META = SourceMeta(
    source_document_id="src-1",
    parse_run_id="run-1",
    filename="test.pdf",
    sha256="a" * 64,
)

TWO_PAGE_RAW = {
    "text": "[Page 1]\nhello world\n\n[Page 2]\nfoo bar",
    "page_count": 2,
    "page_boundaries": [
        {"page": 1, "start_char": 0, "end_char": 20},
        {"page": 2, "start_char": 22, "end_char": 40},
    ],
}


def test_adapter_parser_kind():
    assert SimpleTextAdapter.parser == ParserKind.SIMPLE


def test_two_pages_produces_two_pages_and_two_blocks():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.page_count == 2
    assert len(doc.pages) == 2
    assert len(doc.blocks) == 2


def test_block_role_is_paragraph():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert all(b.role == BlockRole.PARAGRAPH for b in doc.blocks)


def test_block_ids_are_unique_and_referenced_by_pages():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    block_ids = {b.id for b in doc.blocks}
    assert len(block_ids) == 2
    for page in doc.pages:
        assert len(page.block_ids) == 1
        assert page.block_ids[0] in block_ids


def test_page_indices_are_zero_based():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.pages[0].index == 0
    assert doc.pages[1].index == 1


def test_full_text_preserved():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.full_text == TWO_PAGE_RAW["text"]


def test_source_and_run_ids_wired():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.source_document_id == "src-1"
    assert doc.parse_run_id == "run-1"
    assert doc.source_filename == "test.pdf"


def test_fallback_when_no_page_boundaries():
    raw = {"text": "some text", "page_count": 1, "page_boundaries": []}
    doc = SimpleTextAdapter().adapt(raw, SOURCE_META)
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert len(doc.blocks) == 1
    assert doc.blocks[0].text == "some text"


def test_empty_raw_produces_single_empty_page():
    doc = SimpleTextAdapter().adapt({}, SOURCE_META)
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert len(doc.blocks) == 1


def test_pages_carry_char_offsets_when_boundaries_provided():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.pages[0].start_char == 0
    assert doc.pages[0].end_char == 20
    assert doc.pages[1].start_char == 22
    assert doc.pages[1].end_char == 40


def test_fallback_page_carries_char_offsets_spanning_full_text():
    raw = {"text": "some text", "page_count": 1, "page_boundaries": []}
    doc = SimpleTextAdapter().adapt(raw, SOURCE_META)
    assert doc.pages[0].start_char == 0
    assert doc.pages[0].end_char == len("some text")
