from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.merger import merge, overlap_fraction
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block, BlockRole

TE, TB, OC = Capability.TEXT_EXTRACTION, Capability.TABLE_DETECTION, Capability.TEXT_OCR


def _b(bid, x0, y0, x1, y1, role=BlockRole.TEXT):
    return Block(id=bid, role=role, native_type=role.value, page_index=0,
                 bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1))


def _res(tool_id, cap, blocks):
    return ToolResult(tool_id=tool_id, blocks_by_capability={cap: blocks},
                      native_by_block={b.id: {} for b in blocks})


def _flags(cid=False):
    return {0: PageFlags(index=0, char_count=100, pua_ratio=0.0, cid_corrupt=cid)}


def test_overlap_fraction_is_share_of_the_loser():
    assert overlap_fraction(BBox(x0=0, y0=0, x1=1, y1=1),
                            BBox(x0=0, y0=0, x1=0.5, y1=1)) == 1.0


def test_overlap_fraction_of_zero_area_loser_is_zero():
    assert overlap_fraction(BBox(x0=0, y0=0, x1=1, y1=1),
                            BBox(x0=0.5, y0=0.5, x1=0.5, y1=0.5)) == 0.0


def test_table_evicts_overlapping_text():
    text = _res("fitz", TE, [_b("t1", 0.1, 0.1, 0.9, 0.4)])
    table = _res("fitz_tables", TB, [_b("tb1", 0.0, 0.0, 1.0, 0.5, BlockRole.TABLE)])
    out = merge([text, table], source_document_id="d", page_flags=_flags())
    assert len(out.blocks) == 1
    rec = out.raw_output["evicted"][0]
    assert rec["capability"] == "text_extraction"
    assert rec["winner_capability"] == "table_detection"
    assert rec["reason"] == "covered_by"
    assert rec["won_by"] == "d:0:0"


def test_native_text_evicts_overlapping_ocr_by_default():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 1.0, 0.5)])
    ocr = _res("tesseract", OC, [_b("o1", 0.1, 0.1, 0.3, 0.2)])
    out = merge([text, ocr], source_document_id="d", page_flags=_flags())
    assert [b.id for b in out.blocks] == ["d:0:0"]
    assert out.raw_output["evicted"][0]["capability"] == "text_ocr"


def test_ocr_survives_where_no_native_text_covers_it():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 1.0, 0.2)])
    ocr = _res("tesseract", OC, [_b("o1", 0.0, 0.6, 0.5, 0.8)])  # no overlap
    out = merge([text, ocr], source_document_id="d", page_flags=_flags())
    assert len(out.blocks) == 2
    assert out.raw_output["evicted"] == []


def test_cid_corrupt_page_lets_ocr_evict_native_text():
    text = _res("fitz", TE, [_b("t1", 0.1, 0.1, 0.3, 0.2)])
    ocr = _res("tesseract", OC, [_b("o1", 0.0, 0.0, 1.0, 0.5)])
    out = merge([text, ocr], source_document_id="d", page_flags=_flags(cid=True))
    assert out.raw_output["evicted"][0]["capability"] == "text_extraction"
    assert out.raw_output["evicted"][0]["winner_capability"] == "text_ocr"


def test_ocr_prefer_flips_precedence_for_the_whole_run():
    text = _res("fitz", TE, [_b("t1", 0.1, 0.1, 0.3, 0.2)])
    ocr = _res("tesseract", OC, [_b("o1", 0.0, 0.0, 1.0, 0.5)])
    out = merge([text, ocr], source_document_id="d", page_flags=_flags(), ocr_prefer=True)
    assert out.raw_output["evicted"][0]["capability"] == "text_extraction"


def test_reading_order_is_contiguous_from_zero_per_page():
    text = _res("fitz", TE, [_b("a", 0.0, 0.5, 0.2, 0.6), _b("b", 0.0, 0.1, 0.2, 0.2)])
    out = merge([text], source_document_id="d", page_flags=_flags())
    assert [b.reading_order for b in out.blocks] == [0, 1]
    assert [b.id for b in out.blocks] == ["d:0:0", "d:0:1"]


def test_audit_trail_is_keyed_by_instance():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 0.2, 0.2)])
    out = merge([text], source_document_id="d", page_flags=_flags())
    assert "instances" in out.raw_output and "tools" not in out.raw_output
    assert out.raw_output["instances"]["fitz"]["capabilities"] == ["text_extraction"]
    assert "d:0:0" in out.raw_output["instances"]["fitz"]["block_map"]
