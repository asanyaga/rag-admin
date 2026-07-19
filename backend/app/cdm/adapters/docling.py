"""Docling → CDM: pure mapping helpers plus the DoclingAdapter that assembles
a ParsedDocument from one or more converted batches.

The helpers translate docling's item/bbox/table shapes into CDM types; the
adapter owns iteration, id minting, and document assembly. Batching itself is
the runner's job — it hands the adapter `(document, page_offset)` pairs.
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from app.cdm.adapters.base import SourceMeta
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

_DEFAULT_PAGE_WIDTH = 595.0
_DEFAULT_PAGE_HEIGHT = 842.0

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


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


def _page_sizes(doc: Any) -> Dict[int, Tuple[float, float]]:
    sizes: Dict[int, Tuple[float, float]] = {}
    for page_no, page_item in doc.pages.items():
        size = getattr(page_item, "size", None)
        sizes[int(page_no)] = (
            size.width if size else _DEFAULT_PAGE_WIDTH,
            size.height if size else _DEFAULT_PAGE_HEIGHT,
        )
    return sizes


class DoclingAdapter:
    """Assembles ParsedDocument from converted docling batches.

    `raw` is a sequence of `(DoclingDocument, page_offset)` pairs — a bare
    document is accepted as a single batch at offset 0. Docling's
    `iterate_items()` order *is* reading order (it crosses columns correctly),
    so it is preserved as emitted rather than re-sorted geometrically.
    """

    parser: ClassVar[ParserKind] = ParserKind.DOCLING

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument:
        batches = self._normalize(raw)

        blocks: List[Block] = []
        page_geometry: Dict[int, Tuple[float, float]] = {}
        markdown_parts: List[str] = []
        reading_order = 0

        for doc, page_offset in batches:
            try:
                part = doc.export_to_markdown()
            except Exception:  # noqa: BLE001 — never lose a batch over serialization
                part = ""
            if part:
                markdown_parts.append(part)

            sizes = _page_sizes(doc)
            for page_no, (width, height) in sizes.items():
                page_geometry[(page_no - 1) + page_offset] = (width, height)

            for item, depth in doc.iterate_items():
                prov_list = getattr(item, "prov", None) or []
                if not prov_list:
                    continue
                prov = prov_list[0]
                page_index = (int(prov.page_no) - 1) + page_offset
                width, height = sizes.get(
                    int(prov.page_no), (_DEFAULT_PAGE_WIDTH, _DEFAULT_PAGE_HEIGHT)
                )

                blocks.append(self._to_block(
                    item, depth,
                    prov=prov,
                    page_index=page_index,
                    page_width=width,
                    page_height=height,
                    block_id=_mint_block_id(
                        source_meta.source_document_id, page_index, reading_order),
                    reading_order=reading_order,
                ))
                reading_order += 1

        return self._assemble(
            blocks, page_geometry, source_meta,
            full_markdown="\n\n".join(markdown_parts) or None,
        )

    # -- internals

    @staticmethod
    def _normalize(raw: Any) -> Sequence[Tuple[Any, int]]:
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return [(raw, 0)]

    @staticmethod
    def _to_block(item, depth, *, prov, page_index, page_width, page_height,
                  block_id, reading_order) -> Block:
        bbox: Optional[BBox] = None
        raw_bbox = getattr(prov, "bbox", None)
        if raw_bbox is not None:
            try:
                bbox = _to_cdm_bbox(raw_bbox, page_width, page_height)
            except Exception:  # noqa: BLE001 — a bad box must not lose the block
                pass

        role = _map_role(item.label)

        table: Optional[Table] = None
        if role is BlockRole.TABLE:
            try:
                table = _map_table(item)
            except Exception:  # noqa: BLE001
                pass

        # Per-block markdown only where it differs from plain text. docling's
        # TextItem has no export_to_markdown at all (the doc-level serializer
        # owns that), so full_markdown comes from `doc.export_to_markdown()`.
        markdown: Optional[str] = None
        if table is not None:
            markdown = table.markdown or None
        elif role is BlockRole.HEADING:
            text = getattr(item, "text", "") or ""
            markdown = f"{'#' * min(max(depth, 1), 6)} {text}" if text else None

        return Block(
            id=block_id,
            role=role,
            native_type=item.label.value,
            native_label=item.label.value,
            text=getattr(item, "text", "") or "",
            markdown=markdown,
            page_index=page_index,
            bbox=bbox,
            reading_order=reading_order,
            depth=depth if role is BlockRole.HEADING else None,
            table=table,
        )

    @staticmethod
    def _assemble(blocks: List[Block],
                  page_geometry: Dict[int, Tuple[float, float]],
                  source_meta: SourceMeta,
                  *, full_markdown: Optional[str]) -> ParsedDocument:
        by_page: Dict[int, List[Block]] = {}
        for b in blocks:
            by_page.setdefault(b.page_index, []).append(b)

        pages: List[Page] = []
        for idx in sorted(set(page_geometry) | set(by_page)):
            width, height = page_geometry.get(idx, (None, None))
            pages.append(Page(
                index=idx,
                width=width,
                height=height,
                unit="pdf_points" if width else None,
                block_ids=[b.id for b in by_page.get(idx, [])],
            ))

        full_text = "\n\n".join(b.text for b in blocks if b.text)

        return ParsedDocument(
            id=str(uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=blocks,
            full_text=full_text or None,
            full_markdown=full_markdown,
        )
