import shutil

import fitz
import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import TesseractConfig
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import TesseractTool


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _flags(**over):
    base = dict(index=0, char_count=0, pua_ratio=0.0, cid_corrupt=False,
                has_text_layer=False, has_uncovered_image=False)
    base.update(over)
    return PageFlags(**base)


def test_provides_text_ocr():
    assert TesseractTool().provides == frozenset({Capability.TEXT_OCR})


def test_select_pages_all_returns_none():
    tool = TesseractTool(config=TesseractConfig(pages="all"))
    assert tool.select_pages({0: _flags(), 1: _flags()}) is None


def test_select_pages_explicit_list_is_sorted():
    tool = TesseractTool(config=TesseractConfig(pages=[2, 0]))
    assert tool.select_pages({}) == [0, 2]


def test_select_pages_auto_picks_scanned_cid_and_uncovered():
    tool = TesseractTool(config=TesseractConfig(pages="auto"))
    flags = {
        0: _flags(index=0, has_text_layer=True),                       # clean text -> skip
        1: _flags(index=1, has_text_layer=False),                      # scanned -> ocr
        2: _flags(index=2, has_text_layer=True, cid_corrupt=True),     # cid -> ocr
        3: _flags(index=3, has_text_layer=True, has_uncovered_image=True),  # image text -> ocr
    }
    assert tool.select_pages(flags) == [1, 2, 3]


def test_run_rejects_an_emit_it_does_not_provide(tmp_path):
    doc = fitz.open(); doc.new_page(); p = tmp_path / "x.pdf"; doc.save(str(p)); doc.close()
    with pytest.raises(ValueError, match="cannot emit"):
        TesseractTool().run(p, emit=frozenset({Capability.TABLE_DETECTION}))


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract binary not installed")
def test_run_recovers_text_from_a_rendered_page(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=612, height=200)
    page.insert_text((40, 120), "INVOICE TOTAL", fontsize=48)
    p = tmp_path / "scan.pdf"; doc.save(str(p)); doc.close()

    result = TesseractTool(config=TesseractConfig(dpi=200)).run(
        p, pages=[0], emit=frozenset({Capability.TEXT_OCR}))
    blocks = result.blocks_by_capability[Capability.TEXT_OCR]
    assert blocks, "expected at least one OCR block"
    joined = " ".join(b.text for b in blocks).upper()
    assert "INVOICE" in joined
    b = blocks[0]
    assert b.native_type == "ocr_text"
    assert b.parser_extras["capability"] == "text_ocr"
    assert b.quality is not None and 0.0 <= b.quality.confidence <= 1.0
    for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1):
        assert 0.0 <= v <= 1.0
