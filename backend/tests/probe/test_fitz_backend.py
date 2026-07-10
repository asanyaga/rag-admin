import fitz
import numpy as np
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.report import BBox


def _make_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Hello invoice world", fontsize=12)
    page.draw_rect(fitz.Rect(100, 300, 500, 500))  # a box -> a drawing
    path = tmp_path / "sample.pdf"
    doc.save(str(path)); doc.close()
    return path


def test_inspect_extracts_text_size_and_drawings(tmp_path):
    path = _make_pdf(tmp_path)
    with FitzBackend().open(path) as session:
        prims = session.inspect()
    assert prims.page_count == 1
    p = prims.pages[0]
    assert p.width_pt == 612 and p.height_pt == 792
    assert "invoice" in p.text
    assert len(p.text_spans) >= 1
    assert all(0.0 <= s.bbox.x0 <= 1.0 for s in p.text_spans)  # normalized
    assert len(p.drawings) >= 1


def test_render_gray_returns_2d_array(tmp_path):
    path = _make_pdf(tmp_path)
    with FitzBackend().open(path) as session:
        gray = session.render_gray(0, BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.7), target_px=64)
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert max(gray.shape) <= 64


def test_render_gray_degenerate_bbox_never_empty(tmp_path):
    # A zero-width (or zero-height) region must not produce a zero-size axis,
    # which would crash downstream edge detection.
    path = _make_pdf(tmp_path)
    with FitzBackend().open(path) as session:
        gray = session.render_gray(0, BBox(x0=0.5, y0=0.3, x1=0.5, y1=0.7), target_px=64)
    assert gray.ndim == 2
    assert min(gray.shape) >= 1


def test_document_opened_once_per_run(tmp_path):
    # Guards against the O(images) reopen regression: inspect + all region
    # rasters must share a single fitz.open.
    import app.probe.backends.fitz_backend as fb
    path = _make_pdf(tmp_path)
    calls = {"n": 0}
    orig = fb.fitz.open

    def counting_open(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    fb.fitz.open = counting_open
    try:
        with FitzBackend().open(path) as session:
            session.inspect()
            session.render_gray(0, BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.7))
            session.render_gray(0, BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.7))
    finally:
        fb.fitz.open = orig
    assert calls["n"] == 1
