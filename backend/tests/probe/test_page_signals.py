from app.probe.backends.base import DocumentPrimitives, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.signals.page_signals import text_layer, font_health, copy_restricted


def _page(text="", spans=None):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text=text,
                          text_spans=spans or [], images=[], drawings=[])


def test_text_layer_reports_char_count_and_presence():
    sigs = {s.name: s for s in text_layer(_page("Hello world " * 5), ProbeConfig())}
    assert sigs["has_text_layer"].value == "true"
    assert float(sigs["char_count"].value) >= 55


def test_font_health_flags_cid_corruption():
    corrupt = "".join(chr(0xE000 + i % 10) for i in range(100))
    sigs = {s.name: s for s in font_health(_page(corrupt), ProbeConfig())}
    assert sigs["font_health"].value == "cid_corrupt"


def test_copy_restricted_signal():
    doc = DocumentPrimitives(page_count=1, copy_restricted=True, pages=[_page("x")])
    sigs = {s.name: s for s in copy_restricted(doc, ProbeConfig())}
    assert sigs["copy_restricted"].value == "true"
