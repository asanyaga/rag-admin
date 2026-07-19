"""Tests for docling → CDM mapping helpers, shared by DoclingTool."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def _fake_bbox(l=50.0, t=750.0, r=545.0, b=700.0, origin="BOTTOMLEFT"):
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin=origin)


# ── BBox conversion ───────────────────────────────────────────────────────────

def test_to_cdm_bbox_bottomleft_full_page():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Full page in bottom-left: l=0, t=842 (top from bottom), r=595, b=0
    bbox = _fake_bbox(l=0.0, t=842.0, r=595.0, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(1.0)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_bottomleft_bottom_half():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Bottom half: l=0, t=421, r=595, b=0 → CDM y0=0.5, y1=1.0
    bbox = _fake_bbox(l=0.0, t=421.0, r=595.0, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.5, abs=0.01)
    assert result.x1 == pytest.approx(1.0)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_topleft():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Top-left quarter: l=0, t=0, r=297.5, b=421
    bbox = _fake_bbox(l=0.0, t=0.0, r=297.5, b=421.0, origin="TOPLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(0.5)
    assert result.y1 == pytest.approx(0.5)


def test_to_cdm_bbox_clamped():
    from app.cdm.adapters.docling import _to_cdm_bbox
    bbox = _fake_bbox(l=-10.0, t=900.0, r=700.0, b=-5.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert 0.0 <= result.x0 <= result.x1 <= 1.0
    assert 0.0 <= result.y0 <= result.y1 <= 1.0


# ── Role mapping ──────────────────────────────────────────────────────────────

def test_map_role_known_labels():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole

    cases = [
        ("title",          BlockRole.TITLE),
        ("section_header", BlockRole.HEADING),
        ("text",           BlockRole.TEXT),
        ("paragraph",      BlockRole.TEXT),
        ("list_item",      BlockRole.LIST),
        ("table",          BlockRole.TABLE),
        ("picture",        BlockRole.FIGURE),
        ("caption",        BlockRole.CAPTION),
        ("code",           BlockRole.CODE),
        ("formula",        BlockRole.FORMULA),
        ("page_header",    BlockRole.HEADER),
        ("page_footer",    BlockRole.FOOTER),
        ("footnote",       BlockRole.OTHER),
    ]
    for label_value, expected_role in cases:
        label = SimpleNamespace(value=label_value)
        assert _map_role(label) == expected_role, f"failed for {label_value}"


def test_map_role_unknown_falls_back_to_other():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole
    label = SimpleNamespace(value="some_future_label")
    assert _map_role(label) == BlockRole.OTHER


# ── Table mapping ─────────────────────────────────────────────────────────────
#
# Driven by a captured DoclingDocument, not hand-rolled fakes. The previous
# fakes here invented `start_row_offset`, matching the code under test rather
# than docling_core's actual TableCell — so they validated the very bug that
# left every table block empty.

import json
from pathlib import Path

_TABLE_FIXTURE = Path(__file__).parent / "fixtures" / "docling_table_doc.json"


@pytest.fixture
def table_item():
    from docling_core.types.doc import DoclingDocument
    doc = DoclingDocument.model_validate(
        json.loads(_TABLE_FIXTURE.read_text(encoding="utf-8")))
    for item, _ in doc.iterate_items():
        if item.label.value == "table":
            return item, doc
    pytest.fail("fixture should contain a table")


def test_table_cell_field_names_are_what_we_map(table_item):
    """Pin the upstream shape. If docling_core renames these, fail here loudly
    rather than silently producing empty tables."""
    item, _ = table_item
    cell = item.data.table_cells[0]
    for field in ("start_row_offset_idx", "start_col_offset_idx",
                  "end_row_offset_idx", "end_col_offset_idx",
                  "row_span", "col_span", "column_header", "text"):
        assert hasattr(cell, field), f"TableCell lost {field!r}"


def test_map_table_recovers_the_real_grid(table_item):
    from app.cdm.adapters.docling import _map_table
    item, doc = table_item
    table = _map_table(item, doc)

    assert table.rows == 4
    assert table.cols == 3
    assert len(table.cells) == 12
    assert {c.text for c in table.cells} >= {"Item", "Qty", "Price", "Bolt"}


def test_map_table_marks_the_header_row(table_item):
    from app.cdm.adapters.docling import _map_table
    item, doc = table_item
    header_texts = {c.text for c in _map_table(item, doc).cells if c.is_header}
    assert "Item" in header_texts


def test_map_table_places_cells_at_their_real_coordinates(table_item):
    from app.cdm.adapters.docling import _map_table
    item, doc = table_item
    by_pos = {(c.row, c.col): c.text for c in _map_table(item, doc).cells}
    assert by_pos[(0, 0)] == "Item"
    assert by_pos[(1, 0)] == "Bolt"
    assert by_pos[(1, 1)] == "12"


def test_map_table_renders_html_and_markdown(table_item):
    """export_to_html returns nothing without the doc argument, so a table that
    mapped fine still lost its HTML."""
    from app.cdm.adapters.docling import _map_table
    item, doc = table_item
    table = _map_table(item, doc)
    assert table.html and "<table" in table.html
    assert table.markdown and "Bolt" in table.markdown


def test_map_table_on_a_structureless_table_is_empty_not_broken():
    """docling sometimes marks a region as a table but recovers no cells. That
    must yield an empty Table, not an exception."""
    from app.cdm.adapters.docling import _map_table
    from types import SimpleNamespace

    empty = SimpleNamespace(
        data=SimpleNamespace(table_cells=[], grid=[], num_rows=0, num_cols=0),
        export_to_html=lambda *a, **k: "",
        export_to_markdown=lambda *a, **k: "",
    )
    table = _map_table(empty, None)
    assert table.rows == 0
    assert table.cells == []
