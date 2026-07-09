from app.probe.backends.base import DrawingPrimitive, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import BBox
from app.probe.signals.region_signals import table_grid


def _page(drawings):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text="",
                          text_spans=[], images=[], drawings=drawings)


def test_table_grid_detected_when_enough_lines_cluster():
    lines = [DrawingPrimitive(kind="l", bbox=BBox(x0=0.1, y0=0.1 + i * 0.05, x1=0.9, y1=0.1 + i * 0.05))
             for i in range(5)]
    results = table_grid(_page(lines), ProbeConfig())
    assert len(results) == 1
    bbox, sig = results[0]
    assert sig.name == "table_grid"
    assert float(sig.value) >= 5


def test_no_table_when_too_few_lines():
    lines = [DrawingPrimitive(kind="l", bbox=BBox(x0=0.1, y0=0.2, x1=0.9, y1=0.2))]
    assert table_grid(_page(lines), ProbeConfig()) == []
