from __future__ import annotations
from typing import List
from app.probe.backends.base import DocumentPrimitives, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import Signal


def text_layer(page: PagePrimitives, cfg: ProbeConfig) -> List[Signal]:
    chars = len(page.text.strip())
    has = chars >= cfg.thresholds.min_text_chars
    return [
        Signal(name="char_count", value=float(chars), unit="chars"),
        Signal(name="has_text_layer", value="true" if has else "false",
               strength=1.0 if has else 0.0, detail=f"{chars} chars (min {cfg.thresholds.min_text_chars})"),
    ]


def font_health(page: PagePrimitives, cfg: ProbeConfig) -> List[Signal]:
    text = page.text
    if not text.strip():
        return [Signal(name="font_health", value="unknown")]
    pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    ratio = pua / len(text)
    if ratio > cfg.thresholds.cid_ratio:
        health = "cid_corrupt"
    elif ratio > 0.05:
        health = "mixed"
    else:
        health = "clean"
    return [Signal(name="font_health", value=health, strength=1.0 - min(ratio, 1.0),
                   detail=f"{ratio:.0%} private-use chars")]


def copy_restricted(doc: DocumentPrimitives, cfg: ProbeConfig) -> List[Signal]:
    return [Signal(name="copy_restricted", value="true" if doc.copy_restricted else "false",
                   detail="PDF_PERM_COPY bit clear" if doc.copy_restricted else "copy allowed")]
