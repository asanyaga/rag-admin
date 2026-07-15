"""Merge tool outputs into a final ordered block list + an audit raw_output.

Blocks are tagged with the capability that produced them. Precedence is
per-page (see capabilities.resolve_precedence): structure beats loose text, and
OCR sits below native text unless the page is CID-corrupt or the router set
`ocr_prefer`. Losers are evicted (logged, not deleted).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from app.cdm.adapters.custom_pipeline.capabilities import Capability, resolve_precedence
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block


def _area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def overlap_fraction(winner: BBox, loser: BBox) -> float:
    """Intersection area / area(loser), in normalized coords."""
    loser_area = _area(loser)
    if loser_area == 0.0:
        return 0.0
    ix0, iy0 = max(winner.x0, loser.x0), max(winner.y0, loser.y0)
    ix1, iy1 = min(winner.x1, loser.x1), min(winner.y1, loser.y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return inter / loser_area


@dataclass
class MergeResult:
    blocks: List[Block]
    raw_output: Dict[str, Any]


def _sort_key(block: Block) -> Tuple[float, float, float]:
    # A producer that supplies its own reading order (e.g. a layout model that
    # crosses columns correctly) is honoured; producers that don't (fitz) fall
    # back to top-to-bottom, left-to-right geometry and sort after.
    order = float(block.reading_order) if block.reading_order is not None else 1e9
    if block.bbox is None:
        return (order, 1e9, 1e9)
    return (order, block.bbox.y0, block.bbox.x0)


def merge(
    results: Sequence[ToolResult],
    *,
    source_document_id: str,
    page_flags: Dict[int, PageFlags],
    ocr_prefer: bool = False,
    eviction_overlap_threshold: float = 0.5,
    ocr_eviction_threshold: float = 0.3,
) -> MergeResult:
    # Flatten to (block, capability, tool_id), preserving producer order.
    tagged: List[Tuple[Block, Capability, str]] = [
        (b, cap, r.tool_id)
        for r in results
        for cap, blocks in r.blocks_by_capability.items()
        for b in blocks
    ]

    def _threshold(loser_cap: Capability) -> float:
        return (ocr_eviction_threshold if loser_cap is Capability.TEXT_OCR
                else eviction_overlap_threshold)

    def _rank(page_index: int) -> Dict[Capability, int]:
        flags = page_flags.get(page_index)
        return resolve_precedence(
            cid_corrupt=bool(flags and flags.cid_corrupt), ocr_prefer=ocr_prefer,
        )

    # 1. Eviction pass — a block loses to any higher-ranked block that covers it.
    evicted: Dict[str, Dict[str, Any]] = {}
    for loser, loser_cap, loser_tool in tagged:
        if loser.bbox is None:
            continue
        ranks = _rank(loser.page_index)
        for winner, winner_cap, _ in tagged:
            if winner.id == loser.id or winner.bbox is None:
                continue
            if winner.page_index != loser.page_index:
                continue
            if ranks.get(winner_cap, 0) <= ranks.get(loser_cap, 0):
                continue
            # Eviction removes a *duplicate representation* of content. A block
            # that carries no text (e.g. a FIGURE/image) is a container, not a
            # representation — it must not evict text extracted from within it
            # (this is exactly the OCR-of-an-image case).
            if not (winner.text and winner.text.strip()):
                continue
            frac = overlap_fraction(winner.bbox, loser.bbox)
            if frac > _threshold(loser_cap):
                evicted[loser.id] = {
                    "block_id": loser.id,
                    "capability": loser_cap.value,
                    "winner_capability": winner_cap.value,
                    "winner_prov_id": winner.id,
                    "reason": "covered_by",
                    "overlap_fraction": frac,
                    "tool": loser_tool,
                }
                break

    survivors = [(b, c, t) for (b, c, t) in tagged if b.id not in evicted]

    # 2. Mint final ids + reading order, grouped per page.
    by_page: Dict[int, List[Block]] = {}
    for b, _, _ in survivors:
        by_page.setdefault(b.page_index, []).append(b)

    prov_to_final: Dict[str, str] = {}
    final_blocks: List[Block] = []
    for page_index in sorted(by_page):
        for reading_order, block in enumerate(sorted(by_page[page_index], key=_sort_key)):
            final_id = f"{source_document_id}:{page_index}:{reading_order}"
            prov_to_final[block.id] = final_id
            final_blocks.append(
                block.model_copy(update={"id": final_id, "reading_order": reading_order})
            )

    # 3. Audit trail, keyed by instance and explained in capability terms.
    instances: Dict[str, Any] = {}
    for r in results:
        block_map = {
            prov_to_final[prov]: native
            for prov, native in r.native_by_block.items()
            if prov in prov_to_final
        }
        instances[r.tool_id] = {
            "tool": r.tool_id,
            "capabilities": [c.value for c in r.blocks_by_capability],
            "raw": r.raw,
            "block_map": block_map,
        }

    evicted_records: List[Dict[str, Any]] = []
    for record in evicted.values():
        record["won_by"] = prov_to_final.get(record.pop("winner_prov_id"))
        evicted_records.append(record)

    return MergeResult(
        blocks=final_blocks,
        raw_output={"instances": instances, "evicted": evicted_records},
    )
