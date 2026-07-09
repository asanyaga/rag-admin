from app.probe.recommend import recommend
from app.probe.report import (
    Observation, PageProfile, ProbeReport, RegionFinding, Signal, BBox,
)


def _report(pages):
    return ProbeReport(document_id="d", filename="f.pdf", page_count=len(pages),
                       inspection={}, pages=pages, suggestion=None, duration_ms=1, probed_at="t")


def test_recommends_ocr_for_text_image_page():
    region = RegionFinding(id="p0:img0", page_index=0, kind="image",
                           bbox=BBox(x0=0, y0=0, x1=1, y1=1), signals=[],
                           observation=Observation(label="text_image", confidence=0.9))
    page = PageProfile(index=0, page_type="scanned", signals=[], regions=[region])
    sug = recommend(_report([page]))
    assert sug.authoritative is False
    assert 0 in sug.ocr_pages
    assert any("OCR" in r for r in sug.rationale)


def test_recommends_fitz_tables_when_table_present():
    region = RegionFinding(id="p0:tbl0", page_index=0, kind="table",
                           bbox=BBox(x0=0, y0=0, x1=1, y1=1),
                           signals=[Signal(name="table_grid", value=9.0, strength=0.7)],
                           observation=Observation(label="table_grid", confidence=0.7))
    page = PageProfile(index=0, page_type="text",
                       signals=[Signal(name="has_text_layer", value="true", strength=1.0)],
                       regions=[region])
    sug = recommend(_report([page]))
    assert "fitz" in sug.tools and "fitz_tables" in sug.tools
