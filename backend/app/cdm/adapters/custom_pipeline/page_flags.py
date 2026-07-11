"""Per-page facts consumed by the merger (CID precedence flip) and by the OCR
tool's `pages: "auto"` selector.

fitz metadata only — no rasterization. Deliberately independent of `app/probe/`:
the probe is advisory evidence, this is deterministic execution state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import fitz
from pydantic import BaseModel

Rect = Tuple[float, float, float, float]  # (x0, y0, x1, y1) in page points


class PageFlagsConfig(BaseModel):
    min_chars: int = 10                    # below this, the page has no usable text layer
    cid_ratio: float = 0.3                 # private-use-area char ratio => cid_corrupt
    min_uncovered_coverage: float = 0.10   # an image must cover >= this share of the page to matter
    covered_overlap: float = 0.6           # >= this share overlapped by text => "covered"


class PageFlags(BaseModel):
    index: int
    char_count: int
    pua_ratio: float
    cid_corrupt: bool
    has_text_layer: bool
    has_uncovered_image: bool


def pua_ratio(text: str) -> float:
    """Fraction of characters in the Unicode private-use area.

    A broken CID font decodes to private-use codepoints, so a high ratio means
    the page has a text layer that is present but unusable.
    """
    if not text:
        return 0.0
    pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    return pua / len(text)


def _intersection_area(a: Rect, b: Rect) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def image_is_uncovered(
    image: Rect, words: Sequence[Rect], page_w: float, page_h: float,
    cfg: PageFlagsConfig,
) -> bool:
    """True if this image is large enough to matter and is NOT substantially
    covered by native text — i.e. it may hold text trapped in an image.

    This is the term that stops a full-bleed marketing image from triggering OCR
    on every page: a decorative image has near-zero text over it, yes, but so
    does a scanned figure. The caller's page-level policy decides what to do;
    here we only report the fact.
    """
    page_area = page_w * page_h
    img_area = max(0.0, image[2] - image[0]) * max(0.0, image[3] - image[1])
    if page_area <= 0 or img_area <= 0:
        return False
    if (img_area / page_area) < cfg.min_uncovered_coverage:
        return False
    covered = sum(_intersection_area(image, w) for w in words)
    return (covered / img_area) < cfg.covered_overlap


def compute_page_flags(pdf_path: Path, cfg: PageFlagsConfig) -> Dict[int, PageFlags]:
    out: Dict[int, PageFlags] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            page = doc[i]
            w, h = page.rect.width, page.rect.height
            text = page.get_text("text")
            ratio = pua_ratio(text)
            char_count = len(text.strip())

            words: List[Rect] = [
                (word[0], word[1], word[2], word[3])
                for word in page.get_text("words")
            ]
            uncovered = False
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    if image_is_uncovered(
                        (rect.x0, rect.y0, rect.x1, rect.y1), words, w, h, cfg
                    ):
                        uncovered = True
                        break
                if uncovered:
                    break

            out[i] = PageFlags(
                index=i,
                char_count=char_count,
                pua_ratio=ratio,
                cid_corrupt=ratio > cfg.cid_ratio,
                has_text_layer=char_count >= cfg.min_chars,
                has_uncovered_image=uncovered,
            )
    finally:
        doc.close()
    return out
