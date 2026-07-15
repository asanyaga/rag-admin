"""DoclingTool — tier-1 authoritative layout analysis for the custom pipeline.

Docling's `iterate_items()` order IS reading order (it crosses columns
correctly), so blocks are emitted with an intrinsic `reading_order` the merger
honours. Text, headings, and tables all come out of a single conversion pass;
this tool fills only the layout_analysis slot for now (table content flows
through as ordinary BlockRole.TABLE blocks).
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult
from app.cdm.adapters.docling import _map_role, _map_table, _to_cdm_bbox
from app.cdm.models import Block, BlockRole

logger = logging.getLogger(__name__)

# Docling is memory-hungry; serialize concurrent conversions. run() executes in
# a worker thread (the runner offloads it via asyncio.to_thread), so a threading
# lock is the right primitive. Fixed for this slice; revisited with the job
# queue. See design section 4.
_DOCLING_LOCK = threading.Lock()


class DoclingConfig(BaseModel):
    """Kept minimal on purpose; add knobs when we learn what matters."""
    page_batch_size: int = 20


def _split_pages(pdf_path: Path, batch_size: int) -> List[Tuple[Path, int]]:
    """Split into (batch_path, page_offset). One batch => original file, offset 0."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    if total <= batch_size:
        return [(pdf_path, 0)]

    batches: List[Tuple[Path, int]] = []
    for start in range(0, total, batch_size):
        writer = PdfWriter()
        for i in range(start, min(start + batch_size, total)):
            writer.add_page(reader.pages[i])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            writer.write(tmp)
            batches.append((Path(tmp.name), start))
    return batches


def _convert_batch(pdf_path: Path) -> Any:
    """Heavy docling conversion. Returns a DoclingDocument."""
    from docling.document_converter import DocumentConverter
    return DocumentConverter().convert(str(pdf_path)).document


class DoclingTool:
    tool_id = "docling"
    provides = frozenset({Capability.LAYOUT_ANALYSIS})

    def __init__(self, config: Optional[DoclingConfig] = None) -> None:
        self.config = config or DoclingConfig()

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,       # ignored: docling is the source
        page_meta: Optional[Dict[int, PageMeta]] = None,  # ignored: docling is the source
        emit: frozenset[Capability] = frozenset({Capability.LAYOUT_ANALYSIS}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")

        t0 = time.perf_counter()
        blocks: List[Block] = []
        page_meta_out: Dict[int, PageMeta] = {}
        native_by_block: Dict[str, Any] = {}
        warnings: List[str] = []
        raw_batches: List[Any] = []

        batches = _split_pages(pdf_path, self.config.page_batch_size)
        made_temp = len(batches) > 1
        try:
            with _DOCLING_LOCK:
                for batch_path, page_offset in batches:
                    doc = _convert_batch(batch_path)
                    raw_batches.append(doc)
                    self._collect(doc, page_offset, blocks, page_meta_out,
                                  native_by_block, warnings)
        finally:
            if made_temp:
                for batch_path, _ in batches:
                    Path(batch_path).unlink(missing_ok=True)

        raw: Any = None
        try:
            raw = ([json.loads(d.model_dump_json()) for d in raw_batches]
                   if len(raw_batches) != 1 else json.loads(raw_batches[0].model_dump_json()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("docling: raw serialization failed: %s", exc)

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.LAYOUT_ANALYSIS: blocks},
            page_meta=page_meta_out,
            raw=raw,
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _collect(self, doc, page_offset, blocks, page_meta_out,
                 native_by_block, warnings) -> None:
        page_sizes: Dict[int, Tuple[float, float]] = {}
        for page_no, page_item in doc.pages.items():
            size = getattr(page_item, "size", None)
            w = size.width if size else 595.0
            h = size.height if size else 842.0
            idx = (int(page_no) - 1) + page_offset
            page_sizes[int(page_no)] = (w, h)
            page_meta_out[idx] = PageMeta(index=idx, width=w, height=h)

        for order, (item, depth) in enumerate(doc.iterate_items()):
            prov_list = getattr(item, "prov", None) or []
            if not prov_list:
                continue
            prov = prov_list[0]
            page_no = int(prov.page_no)
            page_index = (page_no - 1) + page_offset
            w, h = page_sizes.get(page_no, (595.0, 842.0))

            bbox = None
            raw_bbox = getattr(prov, "bbox", None)
            if raw_bbox is not None:
                try:
                    bbox = _to_cdm_bbox(raw_bbox, w, h)
                except Exception:  # noqa: BLE001
                    pass

            role = _map_role(item.label)
            table = None
            if role == BlockRole.TABLE:
                try:
                    table = _map_table(item)
                except Exception:  # noqa: BLE001
                    pass

            md = None
            try:
                md = item.export_to_markdown() or None
            except Exception:  # noqa: BLE001
                pass
            text = getattr(item, "text", "") or (md or "")

            prov_id = f"{self.tool_id}:{page_index}:{order}"
            blocks.append(Block(
                id=prov_id, role=role, native_type=item.label.value,
                text=text, markdown=md, page_index=page_index, bbox=bbox,
                reading_order=order,
                depth=depth if role == BlockRole.HEADING else None,
                table=table,
                parser_extras={"producer": "docling", "capability": "layout_analysis"},
            ))
            native_by_block[prov_id] = {"label": item.label.value, "markdown": md}
