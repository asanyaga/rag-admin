from __future__ import annotations
from pathlib import Path
import fitz
import numpy as np
from app.probe.backends.base import (
    DocumentPrimitives, DrawingPrimitive, ImagePrimitive, PagePrimitives, TextSpan,
)
from app.probe.report import BBox


def _norm(x0, y0, x1, y1, w, h) -> BBox:
    return BBox(x0=max(0.0, x0 / w), y0=max(0.0, y0 / h),
                x1=min(1.0, x1 / w), y1=min(1.0, y1 / h))


class FitzSession:
    """Holds one opened PDF for the duration of a probe run.

    Opening a (potentially large) PDF is expensive, so it is done exactly once
    here and reused for inspection and every region raster — instead of
    re-opening per image, which is O(images) full re-parses of the document.
    """

    def __init__(self, pdf_path: Path):
        self._doc = fitz.open(str(pdf_path))

    def __enter__(self) -> "FitzSession":
        return self

    def __exit__(self, *exc) -> bool:
        self._doc.close()
        return False

    def inspect(self) -> DocumentPrimitives:
        copy_restricted = (self._doc.permissions & fitz.PDF_PERM_COPY) == 0
        pages = [self._page(i) for i in range(len(self._doc))]
        return DocumentPrimitives(
            page_count=len(pages), copy_restricted=copy_restricted, pages=pages,
        )

    def _page(self, i) -> PagePrimitives:
        page = self._doc[i]
        w, h = page.rect.width, page.rect.height
        text = page.get_text("text")
        spans = []
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append(TextSpan(text=span["text"], bbox=_norm(x0, y0, x1, y1, w, h)))
        images = []
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            r = rects[0]
            images.append(ImagePrimitive(
                xref=xref, bbox=_norm(r.x0, r.y0, r.x1, r.y1, w, h),
                width_px=int(img[2]), height_px=int(img[3]),
            ))
        drawings = []
        for path in page.get_drawings():
            for item in path.get("items", []):
                if item[0] in ("l", "re"):
                    rect = path.get("rect")
                    if rect:
                        drawings.append(DrawingPrimitive(
                            kind=item[0], bbox=_norm(rect.x0, rect.y0, rect.x1, rect.y1, w, h)))
        return PagePrimitives(
            index=i, width_pt=w, height_pt=h, text=text,
            text_spans=spans, images=images, drawings=drawings,
        )

    def render_gray(self, page_index: int, bbox: BBox, target_px: int = 256) -> np.ndarray:
        page = self._doc[page_index]
        w, h = page.rect.width, page.rect.height
        clip = fitz.Rect(bbox.x0 * w, bbox.y0 * h, bbox.x1 * w, bbox.y1 * h)
        longest = max(clip.width, clip.height) or 1.0
        scale = min(target_px / longest, 4.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, colorspace=fitz.csGRAY)
        if pix.width == 0 or pix.height == 0:
            # Thin/degenerate clip rounded to zero pixels — return a valid 1x1 raster.
            return np.zeros((1, 1), dtype=np.uint8)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


class FitzBackend:
    name = "fitz"
    version = fitz.VersionBind

    def open(self, pdf_path: Path) -> FitzSession:
        return FitzSession(pdf_path)
