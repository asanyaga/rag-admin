from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.local_pipeline.adapter import LocalPipelineAdapter
from app.cdm.adapters.local_pipeline.tools.base import PageMeta
from app.cdm.models import BBox, Block, BlockRole, ParsedDocument, ParserKind


def _bbox(y0):
    return BBox(x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.05)


def _blocks():
    return [
        Block(id="doc1:0:0", role=BlockRole.PARAGRAPH, native_type="text",
              text="alpha", page_index=0, bbox=_bbox(0.1), reading_order=0),
        Block(id="doc1:0:1", role=BlockRole.TABLE, native_type="table",
              text="A | B", markdown="| A | B |", page_index=0, bbox=_bbox(0.5),
              reading_order=1),
        Block(id="doc1:1:0", role=BlockRole.PARAGRAPH, native_type="text",
              text="beta", page_index=1, bbox=_bbox(0.2), reading_order=0),
    ]


def test_adapter_parser_kind():
    assert LocalPipelineAdapter.parser == ParserKind.LOCAL_PIPELINE


def test_adapter_builds_parsed_document():
    raw = {
        "page_meta": {
            0: PageMeta(index=0, width=612.0, height=792.0),
            1: PageMeta(index=1, width=612.0, height=792.0),
        },
        "blocks": _blocks(),
    }
    doc = LocalPipelineAdapter().adapt(raw, SourceMeta(
        source_document_id="doc1", parse_run_id="run1", filename="x.pdf"
    ))
    assert isinstance(doc, ParsedDocument)
    assert doc.source_document_id == "doc1"
    assert doc.parse_run_id == "run1"
    assert doc.page_count == 2
    assert len(doc.blocks) == 3
    assert doc.full_text == "alpha\n\nA | B\n\nbeta"
    # full_markdown is assembled from block.markdown (only the table here).
    assert doc.full_markdown == "| A | B |"


def test_adapter_page_block_ids_in_reading_order():
    raw = {
        "page_meta": {0: PageMeta(index=0, width=612.0, height=792.0),
                      1: PageMeta(index=1, width=612.0, height=792.0)},
        "blocks": _blocks(),
    }
    doc = LocalPipelineAdapter().adapt(raw, SourceMeta(
        source_document_id="doc1", parse_run_id="run1"
    ))
    page0 = next(p for p in doc.pages if p.index == 0)
    assert page0.block_ids == ["doc1:0:0", "doc1:0:1"]
    assert page0.width == 612.0
    assert page0.height == 792.0
    assert page0.unit == "points"
