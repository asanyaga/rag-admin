"""FitzTool — text + image extraction via PyMuPDF. Emits CDM Blocks."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import FitzConfig
from app.cdm.adapters.custom_pipeline.tools.base import (
    PageMeta,
    ToolResult,
    clamp01,
)
from app.cdm.models import BBox, Block, BlockRole


def _json_safe(obj: Any) -> Any:
    """Recursively replace non-JSON-serializable bytes with a size marker.

    fitz image blocks carry raw image bytes under the "image" key; these must
    not reach the JSON ``raw_payload`` column. We don't need the raw bytes in
    the audit trail — the bbox and image metadata are enough.
    """
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _block_text(native_block: Dict[str, Any]) -> str:
    """Join span texts within a fitz text block into a single string."""
    parts: List[str] = []
    for line in native_block.get("lines", []):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        parts.append(line_text)
    return "\n".join(parts).strip()


def _spans(native_block: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in native_block.get("lines", []):
        for span in line.get("spans", []):
            out.append({
                "text": span.get("text", ""),
                "font": span.get("font"),
                "size": span.get("size"),
                "flags": span.get("flags"),
                "bbox": span.get("bbox"),
            })
    return out


class FitzTool:
    tool_id = "fitz"
    provides = frozenset({Capability.TEXT_EXTRACTION})

    def __init__(self, config: Optional[FitzConfig] = None) -> None:
        self.config = config or FitzConfig()

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,  # unused; fitz is the source
        emit: frozenset[Capability] = frozenset({Capability.TEXT_EXTRACTION}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")

        t0 = time.perf_counter()
        blocks: List[Block] = []
        page_meta_out: Dict[int, PageMeta] = {}
        native_raw: Dict[int, Any] = {}
        native_by_block: Dict[str, Any] = {}
        warnings: List[str] = []

        doc = fitz.open(str(pdf_path))
        try:
            for i in range(len(doc)):
                if pages is not None and i not in pages:
                    continue
                page = doc[i]
                pd = page.get_text("dict")
                width = float(pd["width"])
                height = float(pd["height"])
                page_meta_out[i] = PageMeta(
                    index=i, width=width, height=height, rotation=page.rotation
                )
                native_raw[i] = _json_safe(pd)

                char_count = 0
                for bi, blk in enumerate(pd.get("blocks", [])):
                    btype = blk.get("type", 0)
                    x0, y0, x1, y1 = blk["bbox"]
                    bbox = BBox(
                        x0=clamp01(x0 / width),
                        y0=clamp01(y0 / height),
                        x1=clamp01(x1 / width),
                        y1=clamp01(y1 / height),
                        source_space="pdf_points",
                        source_coords=(float(x0), float(y0), float(x1), float(y1)),
                    )
                    prov_id = f"fitz:{i}:{bi}"

                    if btype == 0:
                        text = _block_text(blk)
                        char_count += len(text)
                        extras: Dict[str, Any] = {"fitz_block_type": 0}
                        if self.config.span_detail:
                            extras["spans"] = _spans(blk)
                        block = Block(
                            id=prov_id,
                            role=BlockRole.TEXT,
                            native_type="text",
                            text=text,
                            page_index=i,
                            bbox=bbox,
                            parser_extras=extras,
                        )
                        blocks.append(block)
                        native_by_block[prov_id] = _json_safe(blk)
                    elif btype == 1 and self.config.include_images:
                        block = Block(
                            id=prov_id,
                            role=BlockRole.FIGURE,
                            native_type="image",
                            page_index=i,
                            bbox=bbox,
                            parser_extras={"fitz_block_type": 1},
                        )
                        blocks.append(block)
                        native_by_block[prov_id] = _json_safe(blk)

                if char_count < self.config.min_chars_threshold:
                    warnings.append(
                        f"page {i}: {char_count} chars below threshold "
                        f"{self.config.min_chars_threshold} (possible CID corruption or scan)"
                    )
        finally:
            doc.close()

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TEXT_EXTRACTION: blocks},
            page_meta=page_meta_out,
            raw={"pages": native_raw},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
