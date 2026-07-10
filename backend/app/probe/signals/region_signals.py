from __future__ import annotations
from typing import List, Tuple
from app.probe.backends.base import ImagePrimitive, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import BBox, Signal


def bbox_area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def intersect_area(a: BBox, b: BBox) -> float:
    ix0, iy0 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix1, iy1 = min(a.x1, b.x1), min(a.y1, b.y1)
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def coverage(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    frac = bbox_area(image.bbox)   # page is the unit square in normalized coords
    return Signal(name="coverage", value=round(frac, 4), unit="fraction",
                  strength=min(frac, 1.0), detail=f"{frac:.0%} of page")


def dpi(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    rendered_in = ((image.bbox.x1 - image.bbox.x0) * page.width_pt) / 72.0
    value = (image.width_px / rendered_in) if rendered_in > 0 else 0.0
    return Signal(name="dpi", value=round(value, 1), unit="dpi",
                  strength=min(value / 300.0, 1.0), detail=f"{image.width_px}px over {rendered_in:.1f}in")


def text_overlap(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    img_area = bbox_area(image.bbox)
    if img_area == 0.0:
        return Signal(name="text_overlap", value=0.0, unit="fraction", strength=0.0)
    covered = sum(intersect_area(image.bbox, s.bbox) for s in page.text_spans)
    frac = min(covered / img_area, 1.0)
    return Signal(name="text_overlap", value=round(frac, 4), unit="fraction",
                  strength=frac, detail=f"{frac:.0%} of image covered by text spans")


def table_grid(page: PagePrimitives, cfg: ProbeConfig) -> List[Tuple[BBox, Signal]]:
    lines = [d.bbox for d in page.drawings if d.kind in ("l", "re")]
    if len(lines) < cfg.thresholds.table_line_min:
        return []
    x0 = min(b.x0 for b in lines); y0 = min(b.y0 for b in lines)
    x1 = max(b.x1 for b in lines); y1 = max(b.y1 for b in lines)
    grid = BBox(x0=x0, y0=y0, x1=x1, y1=y1)
    regularity = min(len(lines) / 12.0, 1.0)
    sig = Signal(name="table_grid", value=float(len(lines)), unit="lines",
                 strength=regularity, detail=f"{len(lines)} ruling lines")
    return [(grid, sig)]
