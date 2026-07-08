"""CDM Table → HTML, and extraction of TABLE blocks from a ParsedDocument.

Shared by the table scorer (needs HTML per parsed table) and bootstrap (needs
page + HTML per parsed table). HTML is the canonical ground-truth/comparison form.
"""
from __future__ import annotations

from html import escape

import nh3

from app.cdm.models import BlockRole, ParsedDocument, Table

_ALLOWED_TAGS = {"table", "thead", "tbody", "tr", "td", "th"}
_ALLOWED_ATTRS = {"td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan", "scope"}}


def sanitize_table_html(html: str) -> str:
    """Strip everything outside the table-structure allowlist; keep text content.

    Ground-truth HTML is authored by a trusted human but is rendered via
    dangerouslySetInnerHTML and scored, so it is sanitized at the write boundary.
    """
    return nh3.clean(
        html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip_comments=True,
    )


def table_to_html(table: Table) -> str:
    """Prefer the parser's own HTML; otherwise synthesize from structured cells."""
    if table.html:
        return table.html
    if not table.cells:
        return "<table></table>"

    rows: dict[int, list] = {}
    for cell in table.cells:
        rows.setdefault(cell.row, []).append(cell)

    parts = ["<table>"]
    for r in sorted(rows):
        parts.append("<tr>")
        for cell in sorted(rows[r], key=lambda c: c.col):
            tag = "th" if cell.is_header else "td"
            attrs = ""
            if cell.colspan and cell.colspan != 1:
                attrs += f' colspan="{cell.colspan}"'
            if cell.rowspan and cell.rowspan != 1:
                attrs += f' rowspan="{cell.rowspan}"'
            parts.append(f"<{tag}{attrs}>{escape(cell.text or '')}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def extract_cdm_tables(cdm: ParsedDocument) -> list[tuple[int, str]]:
    """Return (page_index, html) for each TABLE block, in reading order."""
    blocks = [b for b in cdm.blocks if b.role == BlockRole.TABLE and b.table is not None]
    blocks.sort(key=lambda b: (b.page_index, b.reading_order if b.reading_order is not None else 0))
    return [(b.page_index, table_to_html(b.table)) for b in blocks]
