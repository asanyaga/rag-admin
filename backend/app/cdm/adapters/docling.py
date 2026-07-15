"""Docling → CDM mapping helpers, shared by DoclingTool.

These pure functions translate docling's item/bbox/table shapes into CDM types.
DoclingTool (in tools/docling_tool.py) drives the iteration; the standalone
single-shot parser these once belonged to has been retired.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.cdm.models import BBox, BlockRole, Cell, Table

_ROLE_MAP: Dict[str, BlockRole] = {
    "title":               BlockRole.TITLE,
    "section_header":      BlockRole.HEADING,
    "text":                BlockRole.TEXT,
    "paragraph":           BlockRole.TEXT,
    "list_item":           BlockRole.LIST,
    "table":               BlockRole.TABLE,
    "picture":             BlockRole.FIGURE,
    "figure":              BlockRole.FIGURE,
    "caption":             BlockRole.CAPTION,
    "code":                BlockRole.CODE,
    "formula":             BlockRole.FORMULA,
    "inline_math":         BlockRole.FORMULA,
    "page_header":         BlockRole.HEADER,
    "page_footer":         BlockRole.FOOTER,
    "footnote":            BlockRole.OTHER,
    "checkbox_selected":   BlockRole.OTHER,
    "checkbox_unselected": BlockRole.OTHER,
    "form":                BlockRole.OTHER,
    "key_value_region":    BlockRole.OTHER,
    "document_index":      BlockRole.OTHER,
    "grounding":           BlockRole.OTHER,
}


def _map_role(label: Any) -> BlockRole:
    return _ROLE_MAP.get(label.value, BlockRole.OTHER)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _to_cdm_bbox(raw: Any, page_width: float, page_height: float) -> BBox:
    """Convert a docling BoundingBox to a normalized CDM BBox."""
    l, t, r, b = raw.l, raw.t, raw.r, raw.b
    origin = str(getattr(raw, "coord_origin", "BOTTOMLEFT"))
    is_bottom_left = "BOTTOMLEFT" in origin.upper()

    if is_bottom_left:
        x0 = _clamp(l / page_width)
        x1 = _clamp(r / page_width)
        y0 = _clamp(1.0 - t / page_height)
        y1 = _clamp(1.0 - b / page_height)
    else:  # TOPLEFT
        x0 = _clamp(l / page_width)
        y0 = _clamp(t / page_height)
        x1 = _clamp(r / page_width)
        y1 = _clamp(b / page_height)

    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(l, t, r, b),
    )


def _map_table(item: Any) -> Table:
    """Map a docling TableItem to a CDM Table."""
    seen: set[tuple[int, int]] = set()
    cells: List[Cell] = []

    for row in item.data.grid:
        for cell in row:
            key = (cell.start_row_offset, cell.start_col_offset)
            if key in seen:
                continue
            seen.add(key)
            cells.append(Cell(
                row=cell.start_row_offset,
                col=cell.start_col_offset,
                rowspan=cell.row_span,
                colspan=cell.col_span,
                text=cell.text,
                is_header=getattr(cell, "column_header", False),
            ))

    rows = max((c.row + c.rowspan for c in cells), default=0)
    cols = max((c.col + c.colspan for c in cells), default=0)

    html: Optional[str] = None
    try:
        html = item.export_to_html()
    except Exception:
        pass

    md: Optional[str] = None
    try:
        md = item.export_to_markdown()
    except Exception:
        pass

    return Table(rows=rows, cols=cols, cells=cells, html=html, markdown=md)
