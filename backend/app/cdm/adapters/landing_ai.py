"""Landing AI ADE adapter — maps ParseResponse output to CDM.

Input is ParseResponse.model_dump(mode="json") — a plain dict with top-level
keys: chunks, markdown, metadata, splits, grounding.
"""
from __future__ import annotations

import re
import uuid
from html.parser import HTMLParser
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
    Quality,
    Table,
)


_ROLE_MAP: Dict[str, BlockRole] = {
    "table":       BlockRole.TABLE,
    "figure":      BlockRole.FIGURE,
    "logo":        BlockRole.FIGURE,
    "attestation": BlockRole.OTHER,
    "scan_code":   BlockRole.FIGURE,
    "marginalia":  BlockRole.MARGINALIA,
}

# Strips the per-chunk anchor LandingAI prepends to every markdown field:
# <a id='UUID'></a>\n\n
_ANCHOR_RE = re.compile(r"^<a\s[^>]*></a>\s*", re.MULTILINE)

_HEADING_RE = re.compile(r"^(#{1,6}) ")


def _first_content_line(markdown: str) -> str:
    """Return the first non-empty line after stripping the leading anchor tag."""
    stripped = _ANCHOR_RE.sub("", markdown, count=1).lstrip("\n")
    for line in stripped.split("\n"):
        line = line.strip()
        if line:
            return line
    return ""


def _detect_text_role(markdown: str) -> BlockRole:
    """Map a text chunk's markdown to TITLE, HEADING, or PARAGRAPH."""
    first = _first_content_line(markdown)
    m = _HEADING_RE.match(first)
    if not m:
        return BlockRole.PARAGRAPH
    return BlockRole.TITLE if len(m.group(1)) == 1 else BlockRole.HEADING


def _map_role(chunk_type: str, markdown: str = "") -> BlockRole:
    if chunk_type == "text":
        return _detect_text_role(markdown)
    return _ROLE_MAP.get(chunk_type, BlockRole.OTHER)


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


def _make_bbox(box: Dict[str, Any]) -> Optional[BBox]:
    if not box:
        return None
    l = float(box.get("left", 0.0))
    t = float(box.get("top", 0.0))
    r = float(box.get("right", 1.0))
    b = float(box.get("bottom", 1.0))
    return BBox(x0=l, y0=t, x1=r, y1=b, source_space="fraction", source_coords=(l, t, r, b))


class _TableHTMLParser(HTMLParser):
    """Extract rows × cells from an HTML table string."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[Dict[str, Any]]] = []
        self._cur_row: Optional[List[Dict[str, Any]]] = None
        self._cur_cell: Optional[Dict[str, Any]] = None
        self._text_buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        adict = dict(attrs)
        if tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = {
                "id": adict.get("id"),
                "is_header": tag == "th",
                "rowspan": int(adict.get("rowspan", 1)),
                "colspan": int(adict.get("colspan", 1)),
            }
            self._text_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cur_cell is not None:
            self._cur_cell["text"] = "".join(self._text_buf).strip()
            if self._cur_row is not None:
                self._cur_row.append(self._cur_cell)
            self._cur_cell = None
        elif tag == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None

    def handle_data(self, data: str) -> None:
        if self._cur_cell is not None:
            self._text_buf.append(data)


def _parse_table(
    html_str: str,
    grounding_dict: Dict[str, Any],
    markdown_str: Optional[str] = None,
) -> Optional[Table]:
    if not html_str or "<table" not in html_str.lower():
        return None
    parser = _TableHTMLParser()
    try:
        parser.feed(html_str)
    except Exception:
        return None
    if not parser.rows:
        return None

    cells: List[Cell] = []
    max_col = 0

    for row_idx, row in enumerate(parser.rows):
        col_idx = 0
        for cell_data in row:
            cell_id = cell_data.get("id")
            rowspan = cell_data["rowspan"]
            colspan = cell_data["colspan"]

            cell_quality: Optional[Quality] = None
            cell_bbox: Optional[BBox] = None

            ge = grounding_dict.get(cell_id) if cell_id else None
            if ge:
                conf = ge.get("confidence")
                if conf is not None:
                    cell_quality = Quality(confidence=float(conf))
                box = ge.get("box")
                if box:
                    cell_bbox = _make_bbox(box)

            cells.append(Cell(
                row=row_idx,
                col=col_idx,
                rowspan=rowspan,
                colspan=colspan,
                text=cell_data["text"],
                bbox=cell_bbox,
                quality=cell_quality,
                is_header=cell_data["is_header"],
            ))
            max_col = max(max_col, col_idx + colspan - 1)
            col_idx += colspan

    return Table(
        rows=len(parser.rows),
        cols=max_col + 1,
        cells=cells,
        html=html_str,
        markdown=markdown_str,
    )


class LandingAIAdapter:
    parser: ClassVar[ParserKind] = ParserKind.LANDING_AI

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        chunks: List[Dict[str, Any]] = raw.get("chunks") or []
        grounding_dict: Dict[str, Any] = raw.get("grounding") or {}

        pages_map: Dict[int, List[str]] = {}
        ro_by_page: Dict[int, int] = {}
        all_blocks: List[Block] = []

        for chunk in chunks:
            chunk_id = str(chunk.get("id", ""))
            chunk_type = str(chunk.get("type", "other"))
            chunk_grounding = chunk.get("grounding") or {}
            page_index = int(chunk_grounding.get("page", 0))

            ro = ro_by_page.get(page_index, 0)
            block_id = _mint_block_id(source_meta.source_document_id, page_index, ro)
            ro_by_page[page_index] = ro + 1

            role = _map_role(chunk_type, chunk.get("markdown") or "")
            bbox = _make_bbox(chunk_grounding.get("box") or {})

            quality: Optional[Quality] = None
            ge = grounding_dict.get(chunk_id) or {}
            if ge:
                conf = ge.get("confidence")
                lcs = ge.get("low_confidence_spans") or []
                if conf is not None or lcs:
                    quality = Quality(
                        confidence=float(conf) if conf is not None else None,
                        low_confidence_spans=[
                            (s["span"][0], s["span"][1]) if isinstance(s, dict) else (s[0], s[1])
                            for s in lcs
                        ] if lcs else [],
                    )

            chunk_md: Optional[str] = chunk.get("markdown") or None

            table: Optional[Table] = None
            text = ""
            if role == BlockRole.TABLE and chunk_md:
                table = _parse_table(chunk_md, grounding_dict, markdown_str=chunk_md)
                if table:
                    text = " | ".join(c.text for c in table.cells if c.text)
            else:
                text = chunk_md or ""

            block = Block(
                id=block_id,
                role=role,
                native_type=chunk_type,
                text=text,
                markdown=chunk_md,
                page_index=page_index,
                bbox=bbox,
                reading_order=ro,
                quality=quality,
                table=table,
                parser_extras={"landing_ai_chunk_id": chunk_id},
            )
            all_blocks.append(block)
            pages_map.setdefault(page_index, []).append(block_id)

        page_count = (max(pages_map.keys()) + 1) if pages_map else 0
        pages = [
            Page(index=pi, block_ids=pages_map.get(pi, []))
            for pi in range(page_count)
        ]

        full_markdown = raw.get("markdown") or (
            "\n\n".join(b.markdown for b in all_blocks if b.markdown) or None
        )
        full_text = "\n\n".join(b.text for b in all_blocks if b.text) or None

        doc_extras: Dict[str, Any] = {}
        if raw.get("splits"):
            doc_extras["landing_ai_splits"] = raw["splits"]

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=page_count,
            pages=pages,
            blocks=all_blocks,
            full_text=full_text,
            full_markdown=full_markdown,
            parser_extras=doc_extras,
        )
