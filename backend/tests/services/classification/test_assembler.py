from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.services.classification.assembler import (
    BatchPageResult,
    assemble_regions,
    resolve_page_statuses,
)


def _make_doc(page_count: int) -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(page_count)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.TEXT,
            native_type="paragraph",
            text=f"page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(page_count)
    ]
    return ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r",
        page_count=page_count, pages=pages, blocks=blocks,
    )


def test_resolve_prefers_middle_pages():
    """Page 7 appears in batch (0-9) at edge and batch (4-13) in the middle.
    The batch where it's in the middle should win."""
    batch_a = [
        BatchPageResult(page=7, label_statuses={"bs": "start"}, batch_start=0, batch_end=9),
    ]
    batch_b = [
        BatchPageResult(page=7, label_statuses={"bs": "none"}, batch_start=4, batch_end=13),
        BatchPageResult(page=10, label_statuses={"bs": "continue"}, batch_start=4, batch_end=13),
    ]
    resolved = resolve_page_statuses([batch_a, batch_b])
    # Page 7 at edge of batch_a (priority 1) vs middle of batch_b (priority 0)
    assert resolved[7]["bs"] == "none"
    assert resolved[10]["bs"] == "continue"


def test_assemble_simple_region():
    doc = _make_doc(5)
    resolved = {
        0: {"balance_sheet": "none"},
        1: {"balance_sheet": "start"},
        2: {"balance_sheet": "continue"},
        3: {"balance_sheet": "none"},
        4: {"balance_sheet": "none"},
    }
    regions = assemble_regions(resolved, ["balance_sheet"], doc)
    assert len(regions) == 1
    r = regions[0]
    assert r.label == "balance_sheet"
    assert r.page_start == 1
    assert r.page_end == 2
    assert "b1" in r.block_ids
    assert "b2" in r.block_ids
    assert "b0" not in r.block_ids


def test_assemble_no_region():
    doc = _make_doc(3)
    resolved = {i: {"x": "none"} for i in range(3)}
    regions = assemble_regions(resolved, ["x"], doc)
    assert regions == []


def test_assemble_region_open_at_end():
    doc = _make_doc(3)
    resolved = {
        0: {"x": "none"},
        1: {"x": "start"},
        2: {"x": "continue"},
    }
    regions = assemble_regions(resolved, ["x"], doc)
    assert len(regions) == 1
    assert regions[0].page_end == 2


def test_assemble_two_regions_same_label():
    doc = _make_doc(6)
    resolved = {
        0: {"x": "start"},
        1: {"x": "none"},
        2: {"x": "start"},
        3: {"x": "continue"},
        4: {"x": "none"},
        5: {"x": "none"},
    }
    regions = assemble_regions(resolved, ["x"], doc)
    assert len(regions) == 2
    assert regions[0].page_start == 0 and regions[0].page_end == 0
    assert regions[1].page_start == 2 and regions[1].page_end == 3
