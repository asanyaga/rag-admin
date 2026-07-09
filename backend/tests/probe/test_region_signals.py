from app.probe.backends.base import ImagePrimitive, PagePrimitives, TextSpan
from app.probe.config import ProbeConfig
from app.probe.report import BBox
from app.probe.signals.region_signals import coverage, dpi, text_overlap


def _img(x0, y0, x1, y1, wpx=900, hpx=600):
    return ImagePrimitive(xref=1, bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1), width_px=wpx, height_px=hpx)


def _page(spans=None):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text="", text_spans=spans or [],
                          images=[], drawings=[])


def test_coverage_is_fraction_of_page():
    s = coverage(_page(), _img(0.0, 0.0, 0.5, 0.5), ProbeConfig())
    assert abs(float(s.value) - 0.25) < 1e-6


def test_dpi_from_pixels_over_rendered_inches():
    # image spans full 612pt width (8.5in) with 900 px -> ~105 dpi
    s = dpi(_page(), _img(0.0, 0.0, 1.0, 0.5, wpx=900), ProbeConfig())
    assert 100 <= float(s.value) <= 110


def test_text_overlap_high_when_text_sits_over_image():
    spans = [TextSpan(text="hi", bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9))]
    s = text_overlap(_page(spans), _img(0.0, 0.0, 1.0, 1.0), ProbeConfig())
    assert float(s.value) > 0.5


def test_text_overlap_zero_when_no_text():
    s = text_overlap(_page([]), _img(0.0, 0.0, 1.0, 1.0), ProbeConfig())
    assert float(s.value) == 0.0
