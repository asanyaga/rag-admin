"""TesseractTool — OCR for the text_ocr capability slot.

Emits paragraph-level CDM TEXT blocks. It must never emit line- or word-level
blocks: the merger re-sorts blocks by (y0, x0), which would interleave the
lines of a multi-column page into gibberish. Paragraph granularity keeps each
block internally ordered and atomic.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import TesseractConfig
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult, clamp01
from app.cdm.models import BBox, Block, BlockRole, Quality


@dataclass
class OcrParagraph:
    text: str
    bbox: Tuple[float, float, float, float]  # normalized (x0, y0, x1, y1)
    confidence: float                         # 0..1


def aggregate_paragraphs(
    data: Dict[str, list], img_w: int, img_h: int, min_confidence: float,
) -> List[OcrParagraph]:
    """Group image_to_data word rows into ordered paragraph blocks.

    Rows are grouped by (block_num, par_num); within a paragraph, words are
    grouped by line_num and joined with spaces, lines joined with newlines. The
    dict preserves tesseract's reading order, so we do not re-sort.
    """
    n = len(data.get("text", []))
    paragraphs: List[Tuple[int, int]] = []              # ordered paragraph keys
    lines: Dict[Tuple[int, int], List[int]] = {}        # paragraph -> ordered line nums
    words: Dict[Tuple[int, int, int], List[int]] = {}   # (block,par,line) -> row indices

    for i in range(n):
        text = (data["text"][i] or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < min_confidence * 100.0:
            continue
        pkey = (int(data["block_num"][i]), int(data["par_num"][i]))
        lkey = (*pkey, int(data["line_num"][i]))
        if pkey not in lines:
            paragraphs.append(pkey)
            lines[pkey] = []
        if lkey not in words:
            lines[pkey].append(lkey[2])
            words[lkey] = []
        words[lkey].append(i)

    out: List[OcrParagraph] = []
    for pkey in paragraphs:
        line_texts: List[str] = []
        confs: List[float] = []
        x0s: List[float] = []
        y0s: List[float] = []
        x1s: List[float] = []
        y1s: List[float] = []
        for line_num in lines[pkey]:
            lkey = (*pkey, line_num)
            line_words: List[str] = []
            for i in words[lkey]:
                line_words.append(data["text"][i].strip())
                confs.append(float(data["conf"][i]))
                left, top = float(data["left"][i]), float(data["top"][i])
                x0s.append(left)
                y0s.append(top)
                x1s.append(left + float(data["width"][i]))
                y1s.append(top + float(data["height"][i]))
            line_texts.append(" ".join(line_words))
        if not confs:
            continue
        out.append(OcrParagraph(
            text="\n".join(line_texts),
            bbox=(
                clamp01(min(x0s) / img_w), clamp01(min(y0s) / img_h),
                clamp01(max(x1s) / img_w), clamp01(max(y1s) / img_h),
            ),
            confidence=sum(confs) / len(confs) / 100.0,
        ))
    return out


def _render_page(page, dpi: int):
    """Render a fitz page to a PIL image at the given DPI."""
    from PIL import Image  # local import: Pillow is only needed when OCR runs
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0))
    return Image.open(io.BytesIO(pix.tobytes("png"))), pix.width, pix.height


class TesseractTool:
    tool_id = "tesseract"
    provides = frozenset({Capability.TEXT_OCR})

    def __init__(self, config: Optional[TesseractConfig] = None) -> None:
        self.config = config or TesseractConfig()

    def select_pages(self, flags: Dict[int, PageFlags]) -> Optional[List[int]]:
        pages = self.config.pages
        if pages == "all":
            return None
        if isinstance(pages, list):
            return sorted(pages)
        # "auto"
        return sorted(
            i for i, f in flags.items()
            if (not f.has_text_layer) or f.cid_corrupt or f.has_uncovered_image
        )

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset = frozenset({Capability.TEXT_OCR}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")

        import pytesseract
        from pytesseract import Output

        t0 = time.perf_counter()
        blocks: List[Block] = []
        native_by_block: Dict[str, object] = {}
        warnings: List[str] = []
        raw: Dict[int, object] = {}

        doc = fitz.open(str(pdf_path))
        try:
            for i in range(len(doc)):
                if pages is not None and i not in pages:
                    continue
                try:
                    image, img_w, img_h = _render_page(doc[i], self.config.dpi)
                    data = pytesseract.image_to_data(
                        image, lang=self.config.lang,
                        config=f"--psm {self.config.psm}",
                        output_type=Output.DICT,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"page {i}: OCR failed — {exc}")
                    continue

                paras = aggregate_paragraphs(
                    data, img_w, img_h, self.config.min_confidence)
                raw[i] = {"paragraphs": len(paras)}
                for seq, para in enumerate(paras):
                    prov_id = f"tesseract:{i}:{seq}"
                    blocks.append(Block(
                        id=prov_id, role=BlockRole.TEXT, native_type="ocr_text",
                        text=para.text, page_index=i,
                        bbox=BBox(x0=para.bbox[0], y0=para.bbox[1],
                                  x1=para.bbox[2], y1=para.bbox[3],
                                  source_space="pixels"),
                        quality=Quality(confidence=round(para.confidence, 4)),
                        parser_extras={"producer": "tesseract",
                                       "capability": "text_ocr", "engine": "tesseract"},
                    ))
                    native_by_block[prov_id] = {"page": i, "seq": seq,
                                                "confidence": para.confidence}
        finally:
            doc.close()

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TEXT_OCR: blocks},
            page_meta={},
            raw={"pages": raw},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
