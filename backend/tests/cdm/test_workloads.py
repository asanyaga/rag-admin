import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.cdm.workloads import slice_doc


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(5)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.TEXT,
            native_type="paragraph",
            text=f"text on page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(5)
    ]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=5,
        pages=pages,
        blocks=blocks,
    )


def test_slice_doc_returns_only_region_pages():
    doc = _make_doc()
    region = ClassifiedRegion(label="balance_sheet", page_start=1, page_end=3, block_ids=[])
    sliced = slice_doc(doc, region)
    assert sliced.page_count == 3
    assert [p.index for p in sliced.pages] == [1, 2, 3]
    assert [b.id for b in sliced.blocks] == ["b1", "b2", "b3"]


def test_slice_doc_sets_lineage():
    doc = _make_doc()
    region = ClassifiedRegion(label="income_statement", page_start=0, page_end=1, block_ids=[])
    sliced = slice_doc(doc, region)
    assert sliced.derived_from == "doc-1"
    assert "income_statement" in sliced.derivation
    assert "0" in sliced.derivation
    assert "1" in sliced.derivation


def test_slice_doc_original_unchanged():
    doc = _make_doc()
    region = ClassifiedRegion(label="x", page_start=0, page_end=0, block_ids=[])
    slice_doc(doc, region)
    assert doc.page_count == 5  # original not mutated


def test_slice_doc_rejects_inverted_range():
    doc = _make_doc()
    region = ClassifiedRegion(label="x", page_start=3, page_end=1, block_ids=[])
    with pytest.raises(ValueError):
        slice_doc(doc, region)
