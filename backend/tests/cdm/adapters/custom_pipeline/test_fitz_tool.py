import json
from pathlib import Path

import fitz

from app.cdm.adapters.custom_pipeline.config import FitzConfig
from app.cdm.adapters.custom_pipeline.tools.fitz_tool import FitzTool, _json_safe
from app.cdm.models import BlockRole

FIXTURES = Path(__file__).parent / "fixtures"


def _make_image_pdf(path: Path) -> None:
    """Write a one-page PDF containing an embedded raster image."""
    src = fitz.open()
    png = src.new_page().get_pixmap().tobytes("png")
    src.close()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 150, 150), stream=png)
    doc.save(str(path))
    doc.close()


def test_fitz_tool_id():
    assert FitzTool().tool_id == "fitz"


def test_fitz_extracts_paragraph_blocks_with_normalized_bbox():
    result = FitzTool().run(FIXTURES / "simple_text.pdf")
    assert result.tool_id == "fitz"
    paras = [b for b in result.blocks if b.role == BlockRole.TEXT]
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
    para = next(b for b in result.blocks if b.role == BlockRole.TEXT)
    assert "spans" not in para.parser_extras


def test_fitz_span_detail_on_records_spans():
    result = FitzTool(config=FitzConfig(span_detail=True)).run(FIXTURES / "simple_text.pdf")
    para = next(b for b in result.blocks if b.role == BlockRole.TEXT)
    assert "spans" in para.parser_extras
    assert isinstance(para.parser_extras["spans"], list)


def test_json_safe_strips_bytes():
    out = _json_safe({"image": b"\x00\x01", "nested": [{"x": b"ab"}], "n": 3})
    assert isinstance(out["image"], str)
    assert isinstance(out["nested"][0]["x"], str)
    assert out["n"] == 3
    json.dumps(out)  # must not raise


def test_fitz_raw_is_json_serializable_with_images(tmp_path):
    pdf = tmp_path / "with_image.pdf"
    _make_image_pdf(pdf)
    result = FitzTool().run(pdf)
    # Sanity: an image block was extracted as a FIGURE.
    assert any(b.role == BlockRole.FIGURE for b in result.blocks)
    # The raw audit data must be JSON-serializable (no raw image bytes).
    json.dumps(result.raw)
    json.dumps(result.native_by_block)
