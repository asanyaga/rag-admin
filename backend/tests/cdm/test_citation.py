from app.cdm.citation import CitationRef
from app.cdm.models import BBox


def test_citation_ref_block_level():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
    )
    assert ref.char_start is None
    assert ref.cell_id is None
    assert ref.bbox is None


def test_citation_ref_char_offset():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
        char_start=17,
        char_end=42,
    )
    assert ref.char_end - ref.char_start == 25


def test_citation_ref_cell_level_with_bbox():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
        cell_id="r2c1",
        bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
    )
    assert ref.cell_id == "r2c1"
    assert ref.bbox.x0 == 0.1
