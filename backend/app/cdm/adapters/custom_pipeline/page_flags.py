"""Per-page facts consumed by the merger (CID precedence flip) and, in PR B,
by the OCR tool's `pages: "auto"` selector.

fitz metadata only — no rasterization. Deliberately independent of `app/probe/`:
the probe is advisory evidence, this is deterministic execution state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import fitz
from pydantic import BaseModel


class PageFlagsConfig(BaseModel):
    min_chars: int = 10      # below this, the page has no usable text layer
    cid_ratio: float = 0.3   # private-use-area char ratio => cid_corrupt


class PageFlags(BaseModel):
    index: int
    char_count: int
    pua_ratio: float
    cid_corrupt: bool


def pua_ratio(text: str) -> float:
    """Fraction of characters in the Unicode private-use area.

    A broken CID font decodes to private-use codepoints, so a high ratio means
    the page has a text layer that is present but unusable.
    """
    if not text:
        return 0.0
    pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    return pua / len(text)


def compute_page_flags(pdf_path: Path, cfg: PageFlagsConfig) -> Dict[int, PageFlags]:
    out: Dict[int, PageFlags] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            text = doc[i].get_text("text")
            ratio = pua_ratio(text)
            out[i] = PageFlags(
                index=i,
                char_count=len(text.strip()),
                pua_ratio=ratio,
                cid_corrupt=ratio > cfg.cid_ratio,
            )
    finally:
        doc.close()
    return out
