"""Docling adapter — maps DoclingDocument to CDM ParsedDocument."""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, List, Optional

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Cell,
    Page,
    ParsedDocument,
    ParserKind,
    Table,
)

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


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


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


class DoclingAdapter:
    parser: ClassVar[ParserKind] = ParserKind.DOCLING

    def adapt(
        self,
        raw: Any,  # DoclingDocument
        source_meta: SourceMeta,
        *,
        page_offset: int = 0,
    ) -> ParsedDocument:
        # Build page dimension index (docling pages are 1-indexed)
        page_sizes: Dict[int, tuple[float, float]] = {}
        for page_no, page_item in raw.pages.items():
            size = getattr(page_item, "size", None)
            w = size.width if size else 595.0
            h = size.height if size else 842.0
            page_sizes[int(page_no)] = (w, h)

        all_blocks: List[Block] = []
        page_block_ids: Dict[int, List[str]] = {}

        for reading_order, (item, depth) in enumerate(raw.iterate_items()):
            prov_list = getattr(item, "prov", None) or []
            if not prov_list:
                continue

            prov = prov_list[0]
            page_no = int(prov.page_no)
            page_index = (page_no - 1) + page_offset
            page_width, page_height = page_sizes.get(page_no, (595.0, 842.0))

            bbox: Optional[BBox] = None
            raw_bbox = getattr(prov, "bbox", None)
            if raw_bbox is not None:
                try:
                    bbox = _to_cdm_bbox(raw_bbox, page_width, page_height)
                except Exception:
                    pass

            label = item.label
            native_type = label.value
            role = _map_role(label)
            block_id = _mint_block_id(source_meta.source_document_id, page_index, reading_order)

            table: Optional[Table] = None
            if role == BlockRole.TABLE:
                try:
                    table = _map_table(item)
                except Exception:
                    pass

            md: Optional[str] = None
            try:
                md = item.export_to_markdown() or None
            except Exception:
                pass

            text = getattr(item, "text", "") or ""
            if not text and md:
                text = md

            heading_depth: Optional[int] = depth if role == BlockRole.HEADING else None

            block = Block(
                id=block_id,
                role=role,
                native_type=native_type,
                text=text,
                markdown=md,
                page_index=page_index,
                bbox=bbox,
                reading_order=reading_order,
                depth=heading_depth,
                table=table,
            )
            all_blocks.append(block)
            page_block_ids.setdefault(page_index, []).append(block_id)

        pages: List[Page] = []
        for page_no, (w, h) in sorted(page_sizes.items()):
            page_index = (page_no - 1) + page_offset
            pages.append(Page(
                index=page_index,
                width=w,
                height=h,
                unit="points",
                block_ids=page_block_ids.get(page_index, []),
            ))

        full_markdown: Optional[str] = None
        try:
            full_markdown = raw.export_to_markdown() or None
        except Exception:
            pass

        full_text = "\n\n".join(b.text for b in all_blocks if b.text) or None

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=all_blocks,
            full_text=full_text,
            full_markdown=full_markdown,
        )

    def supported_file_types(self) -> list[str]:
        return ["application/pdf"]
