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


class FitzBackend:
    name = "fitz"
    version = fitz.VersionBind

    def inspect(self, pdf_path: Path) -> DocumentPrimitives:
        doc = fitz.open(str(pdf_path))
        try:
            copy_restricted = (doc.permissions & fitz.PDF_PERM_COPY) == 0
            pages = [self._page(doc, i) for i in range(len(doc))]
            return DocumentPrimitives(
                page_count=len(pages), copy_restricted=copy_restricted, pages=pages,
            )
        finally:
            doc.close()

    def _page(self, doc, i) -> PagePrimitives:
        page = doc[i]
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

    def render_gray(self, pdf_path: Path, page_index: int, bbox: BBox, target_px: int = 256) -> np.ndarray:
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[page_index]
            w, h = page.rect.width, page.rect.height
            clip = fitz.Rect(bbox.x0 * w, bbox.y0 * h, bbox.x1 * w, bbox.y1 * h)
            longest = max(clip.width, clip.height) or 1.0
            scale = min(target_px / longest, 4.0)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, colorspace=fitz.csGRAY)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            return arr
        finally:
            doc.close()
