from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.classification.serializer import build_batches, serialize_pages


def _make_doc(page_count: int) -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(page_count)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.PARAGRAPH,
            native_type="paragraph",
            text=f"content on page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(page_count)
    ]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=page_count,
        pages=pages,
        blocks=blocks,
    )


def test_serialize_pages_format():
    doc = _make_doc(3)
    text = serialize_pages(doc, 0, 1)
    assert "[page 0, paragraph] content on page 0" in text
    assert "[page 1, paragraph] content on page 1" in text
    assert "page 2" not in text


def test_serialize_pages_prefers_markdown():
    from pydantic import ValidationError
    import pytest
    pages = [Page(index=0, block_ids=["b0"])]
    blocks = [
        Block(
            id="b0",
            role=BlockRole.TABLE,
            native_type="table",
            text="plain text",
            markdown="| col1 | col2 |",
            page_index=0,
            reading_order=0,
        )
    ]
    doc = ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r",
        page_count=1, pages=pages, blocks=blocks,
    )
    text = serialize_pages(doc, 0, 0)
    assert "| col1 | col2 |" in text
    assert "plain text" not in text


def test_build_batches_25_pages():
    batches = build_batches(page_count=25, batch_size=10, overlap=3)
    assert batches[0] == (0, 9)
    assert batches[1] == (7, 16)
    assert batches[2] == (14, 23)
    assert batches[3] == (21, 24)


def test_build_batches_small_doc():
    batches = build_batches(page_count=5, batch_size=10, overlap=3)
    assert batches == [(0, 4)]


def test_build_batches_exact_fit():
    batches = build_batches(page_count=10, batch_size=10, overlap=3)
    assert batches == [(0, 9)]
