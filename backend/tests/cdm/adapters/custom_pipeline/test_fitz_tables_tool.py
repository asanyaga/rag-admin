"""Tests for FitzTablesTool — table extraction via page.find_tables()."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.cdm.adapters.local_pipeline.config import FitzTablesConfig
from app.cdm.adapters.local_pipeline.tools.base import PageMeta
from app.cdm.adapters.local_pipeline.tools.fitz_tables_tool import FitzTablesTool
from app.cdm.models import BlockRole


def _make_table_pdf(path: Path) -> None:
    """Write a one-page PDF with a drawn 2-column × 2-row grid table."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    col_x = [72, 236, 400]
    row_y = [100, 150, 200]
    for x in col_x:
        page.draw_line(
            fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]),
            color=(0, 0, 0), width=1,
        )
    for y in row_y:
        page.draw_line(
            fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y),
            color=(0, 0, 0), width=1,
        )
    page.insert_text(fitz.Point(80, 135), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 135), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 185), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 185), "1", fontsize=11)
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def table_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "table.pdf"
    _make_table_pdf(p)
    return p


@pytest.fixture()
def page_meta() -> dict:
    return {0: PageMeta(index=0, width=595.0, height=842.0)}


def test_fitz_tables_tool_id():
    assert FitzTablesTool().tool_id == "fitz_tables"


def test_fitz_tables_emits_table_blocks(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    tables = [b for b in result.blocks if b.role == BlockRole.TABLE]
    assert len(tables) >= 1


def test_fitz_tables_block_has_normalized_bbox(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.bbox is not None
    for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1):
        assert 0.0 <= v <= 1.0
    assert b.bbox.source_space == "pdf_points"


def test_fitz_tables_bbox_no_y_flip(table_pdf, page_meta):
    """Coordinates use top-left origin — source y0 < source y1 (no y-flip)."""
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.bbox is not None
    assert b.bbox.source_coords is not None
    x0, y0, x1, y1 = b.bbox.source_coords
    assert y0 < y1  # top-left origin: y increases downward


def test_fitz_tables_block_has_table_cdm(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.table is not None
    assert b.table.rows >= 2
    assert b.table.cols >= 2


def test_fitz_tables_cell_text(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    all_text = " ".join(c.text for c in b.table.cells)
    assert "Name" in all_text or "Value" in all_text


def test_fitz_tables_html_and_markdown(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.html is not None and "<table>" in b.html
    assert b.markdown is not None and "|" in b.markdown


def test_fitz_tables_block_id_format(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.id.startswith("fitz_tables:0:")


def test_fitz_tables_duration_ms_is_non_negative(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    assert result.duration_ms >= 0


def test_fitz_tables_native_by_block_keyed_by_prov_id(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.id in result.native_by_block


def test_fitz_tables_custom_snap_tolerance_accepted(table_pdf, page_meta):
    cfg = FitzTablesConfig(snap_tolerance=5.0)
    result = FitzTablesTool(config=cfg, page_meta=page_meta).run(table_pdf)
    assert result.tool_id == "fitz_tables"


def test_fitz_tables_empty_pdf_emits_no_table_blocks(tmp_path):
    pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()
    result = FitzTablesTool().run(pdf)
    assert not any(b.role == BlockRole.TABLE for b in result.blocks)
