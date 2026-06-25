from pathlib import Path

from app.cdm.adapters.local_pipeline.config import FitzConfig
from app.cdm.adapters.local_pipeline.tools.fitz_tool import FitzTool
from app.cdm.models import BlockRole

FIXTURES = Path(__file__).parent / "fixtures"


def test_fitz_tool_id():
    assert FitzTool().tool_id == "fitz"


def test_fitz_extracts_paragraph_blocks_with_normalized_bbox():
    result = FitzTool().run(FIXTURES / "simple_text.pdf")
    assert result.tool_id == "fitz"
    paras = [b for b in result.blocks if b.role == BlockRole.PARAGRAPH]
    assert len(paras) > 0
    b = paras[0]
    assert b.text.strip() != ""
    assert b.bbox is not None
    for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1):
        assert 0.0 <= v <= 1.0
    assert b.bbox.source_space == "pdf_points"
    assert b.parser_extras["fitz_block_type"] == 0


def test_fitz_provides_page_meta_for_every_page():
    result = FitzTool().run(FIXTURES / "simple_text.pdf")
    assert set(result.page_meta.keys()) == {0, 1}
    assert result.page_meta[0].width > 0
    assert result.page_meta[0].height > 0


def test_fitz_native_record_keyed_by_provisional_id():
    result = FitzTool().run(FIXTURES / "simple_text.pdf")
    b = result.blocks[0]
    assert b.id in result.native_by_block
    assert "bbox" in result.native_by_block[b.id]


def test_fitz_span_detail_off_by_default():
    result = FitzTool().run(FIXTURES / "simple_text.pdf")
    para = next(b for b in result.blocks if b.role == BlockRole.PARAGRAPH)
    assert "spans" not in para.parser_extras


def test_fitz_span_detail_on_records_spans():
    result = FitzTool(config=FitzConfig(span_detail=True)).run(FIXTURES / "simple_text.pdf")
    para = next(b for b in result.blocks if b.role == BlockRole.PARAGRAPH)
    assert "spans" in para.parser_extras
    assert isinstance(para.parser_extras["spans"], list)
