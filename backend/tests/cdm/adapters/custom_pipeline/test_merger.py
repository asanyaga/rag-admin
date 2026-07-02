from app.cdm.adapters.custom_pipeline.merger import merge, overlap_fraction
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult
from app.cdm.models import BBox, Block, BlockRole


def _bbox(x0, y0, x1, y1):
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def test_overlap_fraction_full_containment():
    table = _bbox(0.0, 0.0, 1.0, 1.0)
    fitz = _bbox(0.1, 0.1, 0.2, 0.2)
    assert overlap_fraction(table, fitz) == 1.0


def test_overlap_fraction_no_overlap():
    table = _bbox(0.0, 0.0, 0.1, 0.1)
    fitz = _bbox(0.5, 0.5, 0.6, 0.6)
    assert overlap_fraction(table, fitz) == 0.0


def _fitz_result():
    blocks = [
        Block(id="fitz:0:0", role=BlockRole.TEXT, native_type="text",
              text="heading", page_index=0, bbox=_bbox(0.1, 0.05, 0.9, 0.1)),
        Block(id="fitz:0:1", role=BlockRole.TEXT, native_type="text",
              text="inside table", page_index=0, bbox=_bbox(0.2, 0.55, 0.8, 0.65)),
    ]
    return ToolResult(
        tool_id="fitz", blocks=blocks,
        page_meta={0: PageMeta(index=0, width=612.0, height=792.0)},
        raw={"pages": {}},
        native_by_block={"fitz:0:0": {"k": "h"}, "fitz:0:1": {"k": "t"}},
    )


def _camelot_result():
    block = Block(id="camelot:0:0", role=BlockRole.TABLE, native_type="table",
                  page_index=0, bbox=_bbox(0.1, 0.5, 0.9, 0.7))
    return ToolResult(
        tool_id="camelot", blocks=[block], page_meta={},
        raw={"tables": []}, native_by_block={"camelot:0:0": {"acc": 99}},
    )


def test_merge_evicts_overlapping_fitz_block():
    result = merge(_fitz_result(), _camelot_result(),
                   source_document_id="doc1", eviction_overlap_threshold=0.5)
    texts = [b.text for b in result.blocks]
    assert "heading" in texts
    assert "inside table" not in texts  # evicted by the table
    assert result.raw_output["evicted"][0]["reason"] == "spatial_overlap"
    assert result.raw_output["evicted"][0]["won_by"].startswith("doc1:0:")


def test_merge_mints_block_ids_and_reading_order():
    result = merge(_fitz_result(), _camelot_result(),
                   source_document_id="doc1", eviction_overlap_threshold=0.5)
    for b in result.blocks:
        assert b.id.startswith("doc1:0:")
        assert b.reading_order is not None
    # heading (y0=0.05) comes before the table (y0=0.5)
    ordered = sorted(result.blocks, key=lambda b: b.reading_order)
    assert ordered[0].text == "heading"
    assert ordered[1].role == BlockRole.TABLE


def test_merge_raw_output_has_tool_block_maps():
    result = merge(_fitz_result(), _camelot_result(),
                   source_document_id="doc1", eviction_overlap_threshold=0.5)
    ro = result.raw_output
    assert set(ro["tools"].keys()) == {"fitz", "camelot"}
    assert "raw" in ro["tools"]["fitz"]
    assert "block_map" in ro["tools"]["camelot"]
    # surviving table maps to its native record
    table_id = next(b.id for b in result.blocks if b.role == BlockRole.TABLE)
    assert ro["tools"]["camelot"]["block_map"][table_id] == {"acc": 99}


def test_merge_raw_output_key_uses_table_result_tool_id():
    """raw_output["tools"] key is the table tool's tool_id, not the string "camelot"."""
    block = Block(
        id="fitz_tables:0:0", role=BlockRole.TABLE, native_type="table",
        page_index=0, bbox=_bbox(0.1, 0.5, 0.9, 0.7),
    )
    fitz_tables_result = ToolResult(
        tool_id="fitz_tables", blocks=[block], page_meta={},
        raw={"tables": []}, native_by_block={"fitz_tables:0:0": {"rows": 2}},
    )
    result = merge(
        _fitz_result(), fitz_tables_result,
        source_document_id="doc1", eviction_overlap_threshold=0.5,
    )
    assert "fitz_tables" in result.raw_output["tools"]
    assert "camelot" not in result.raw_output["tools"]
