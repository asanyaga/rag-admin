"""Shared fixtures for the PR A equivalence gate.

Both the golden-capture script (run once, pre-refactor) and the post-refactor
comparison test import these, so the two sides can never drift.
"""
from __future__ import annotations

from pathlib import Path

import fitz


def build_text_pdf(path: Path) -> None:
    """Two text blocks, no table — exercises plain text_extraction."""
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Quarterly revenue report", fontsize=14)
    page.insert_text(fitz.Point(72, 110), "Figures are provisional.", fontsize=10)
    d.save(str(path)); d.close()


def build_table_pdf(path: Path) -> None:
    """Text plus a ruled grid — exercises text + table_detection + eviction."""
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Quarterly revenue report", fontsize=14)
    col_x, row_y = [72, 236, 400], [200, 250, 300]
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), width=1)
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), width=1)
    page.insert_text(fitz.Point(80, 235), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 235), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 285), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 285), "1", fontsize=11)
    d.save(str(path)); d.close()


# Config keyed by golden name. NOTE: written in the *current* contract
# (capabilities.text_extraction). Task A5's comparison test rewrites the key to
# layout_analysis and asserts the produced content still matches these goldens —
# proving the rename changed nothing.
EQUIV_CONFIGS: dict[str, dict] = {
    "text_only": {
        "tools": {"fitz": {"tool": "fitz", "config": {}}},
        "capabilities": {"text_extraction": "fitz"},
    },
    "text_plus_table": {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "tbl": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"text_extraction": "fitz", "table_detection": "tbl"},
    },
}

_BUILDERS = {"text_only": build_text_pdf, "text_plus_table": build_table_pdf}


def build_for(name: str, path: Path) -> None:
    _BUILDERS[name](path)


def content_projection(doc) -> dict:
    """Stable, volatile-field-free projection of a ParsedDocument.

    Excludes `id` and `parse_run_id` (random/UUID per run); everything that
    describes *content* — pages, blocks, text, markdown — is deterministic
    because block ids derive from the fixed source_document_id.
    """
    return doc.model_dump(
        mode="json",
        include={"page_count", "pages", "blocks", "full_text", "full_markdown"},
    )
