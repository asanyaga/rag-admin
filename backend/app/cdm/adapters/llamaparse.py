"""LlamaParse adapter — maps llama-cloud parsing output to CDM.

Input is the result of ``client.parsing.parse(...)`` after ``.model_dump()``,
i.e. a plain dict with top-level keys controlled by the ``expand`` parameter
(``text``, ``markdown``, ``items``, ``metadata``, ``job_metadata``).
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional, Tuple

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Page,
    ParsedDocument,
    ParserKind,
    Quality,
)


_ROLE_MAP: Dict[str, BlockRole] = {
    "heading": BlockRole.HEADING,
    "text":    BlockRole.PARAGRAPH,
    "list":    BlockRole.LIST,
    "table":   BlockRole.TABLE,
    "image":   BlockRole.FIGURE,
    "header":  BlockRole.HEADER,
    "footer":  BlockRole.FOOTER,
    "code":    BlockRole.CODE,
    "link":    BlockRole.LINK,
}


def _map_role(native_type: str) -> BlockRole:
    return _ROLE_MAP.get(native_type, BlockRole.OTHER)


def _clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _pdf_points_to_normalized(
    *, x: float, y: float, w: float, h: float,
    page_width: float, page_height: float,
) -> BBox:
    x0 = _clamp(x / page_width)
    y0 = _clamp(y / page_height)
    x1 = _clamp((x + w) / page_width)
    y1 = _clamp((y + h) / page_height)
    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(float(x), float(y), float(w), float(h)),
    )


def _union_bbox(bboxes: List[BBox]) -> Optional[BBox]:
    if not bboxes:
        return None
    if len(bboxes) == 1:
        return bboxes[0]
    x0 = min(b.x0 for b in bboxes)
    y0 = min(b.y0 for b in bboxes)
    x1 = max(b.x1 for b in bboxes)
    y1 = max(b.y1 for b in bboxes)
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)
