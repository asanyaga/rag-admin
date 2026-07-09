import fitz
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.config import ProbeConfig
from app.probe.prober import Prober


def _pdf(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Quarterly revenue table follows " * 3, fontsize=11)
    for i in range(5):
        page.draw_line(fitz.Point(100, 300 + i * 20), fitz.Point(500, 300 + i * 20))
    p = tmp_path / "r.pdf"; doc.save(str(p)); doc.close()
    return p


def test_prober_produces_report_with_pages_and_table_region(tmp_path):
    report = Prober(FitzBackend()).run(_pdf(tmp_path), document_id="doc-1",
                                       filename="r.pdf", config=ProbeConfig())
    assert report.page_count == 1
    page = report.pages[0]
    assert page.page_type in ("text", "mixed")
    assert any(r.kind == "table" for r in page.regions)
    assert report.inspection["backend"] == "fitz"
    assert report.suggestion is not None


def test_disabled_signal_is_skipped(tmp_path):
    cfg = ProbeConfig(enabled_signals=["text_layer"])
    report = Prober(FitzBackend()).run(_pdf(tmp_path), document_id="d", filename="r.pdf", config=cfg)
    names = {s.name for s in report.pages[0].signals}
    assert "font_health" not in names
    assert "char_count" in names
