"""Merge tool outputs into a final ordered block list + an audit raw_output.

Eviction rule: later-declared tools win. A fitz PARAGRAPH block that overlaps
a table block beyond the threshold is evicted (logged, not deleted).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.cdm.adapters.local_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block


def _area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def overlap_fraction(table_bbox: BBox, fitz_bbox: BBox) -> float:
    """Intersection area / area(fitz_bbox), in normalized coords."""
    fitz_area = _area(fitz_bbox)
    if fitz_area == 0.0:
        return 0.0
    ix0 = max(table_bbox.x0, fitz_bbox.x0)
    iy0 = max(table_bbox.y0, fitz_bbox.y0)
    ix1 = min(table_bbox.x1, fitz_bbox.x1)
    iy1 = min(table_bbox.y1, fitz_bbox.y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return inter / fitz_area


@dataclass
class MergeResult:
    blocks: List[Block]
    raw_output: Dict[str, Any]


def _sort_key(block: Block) -> Tuple[float, float]:
    if block.bbox is None:
        return (1e9, 1e9)
    return (block.bbox.y0, block.bbox.x0)


def merge(
    fitz_result: ToolResult,
    table_result: ToolResult,
    *,
    source_document_id: str,
    eviction_overlap_threshold: float = 0.5,
) -> MergeResult:
    table_blocks = list(table_result.blocks)

    # 1. Eviction pass — fitz blocks overlapping any table beyond threshold.
    evicted_ids = set()
    eviction_winner: Dict[str, str] = {}
    eviction_overlap: Dict[str, float] = {}
    for fb in fitz_result.blocks:
        if fb.bbox is None:
            continue
        for tb in table_blocks:
            if tb.page_index != fb.page_index or tb.bbox is None:
                continue
            frac = overlap_fraction(tb.bbox, fb.bbox)
            if frac > eviction_overlap_threshold:
                evicted_ids.add(fb.id)
                eviction_winner[fb.id] = tb.id
                eviction_overlap[fb.id] = frac
                break

    surviving_fitz = [b for b in fitz_result.blocks if b.id not in evicted_ids]
    combined = surviving_fitz + table_blocks

    # 2. Mint final ids + reading order, grouped per page.
    by_page: Dict[int, List[Block]] = {}
    for b in combined:
        by_page.setdefault(b.page_index, []).append(b)

    prov_to_final: Dict[str, str] = {}
    final_blocks: List[Block] = []
    for page_index in sorted(by_page.keys()):
        ordered = sorted(by_page[page_index], key=_sort_key)
        for reading_order, block in enumerate(ordered):
            final_id = f"{source_document_id}:{page_index}:{reading_order}"
            prov_to_final[block.id] = final_id
            final_blocks.append(
                block.model_copy(update={"id": final_id, "reading_order": reading_order})
            )

    # 3. Build raw_output (audit trail).
    def _block_map(result: ToolResult) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for prov_id, native in result.native_by_block.items():
            final_id = prov_to_final.get(prov_id)
            if final_id is not None:
                out[final_id] = native
        return out

    evicted_records = [
        {
            "block_id": prov_id,
            "tool": "fitz",
            "reason": "spatial_overlap",
            "won_by": prov_to_final[eviction_winner[prov_id]],
            "overlap_fraction": eviction_overlap[prov_id],
            "raw_block": fitz_result.native_by_block.get(prov_id),
        }
        for prov_id in evicted_ids
    ]

    raw_output = {
        "tools": {
            "fitz": {"raw": fitz_result.raw, "block_map": _block_map(fitz_result)},
            table_result.tool_id: {
                "raw": table_result.raw,
                "block_map": _block_map(table_result),
            },
        },
        "evicted": evicted_records,
    }

    return MergeResult(blocks=final_blocks, raw_output=raw_output)
