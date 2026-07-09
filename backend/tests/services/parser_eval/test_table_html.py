from app.cdm.models import Block, BlockRole, Cell, Page, ParsedDocument, Table
from app.services.parser_eval.table_html import (
    extract_cdm_tables, sanitize_table_html, table_to_html,
)


def test_table_to_html_prefers_existing_html():
    t = Table(rows=1, cols=1, cells=[], html="<table><tr><td>x</td></tr></table>")
    assert table_to_html(t) == "<table><tr><td>x</td></tr></table>"


def test_table_to_html_synthesizes_from_cells():
    cells = [
        Cell(row=0, col=0, text="Item", is_header=True),
        Cell(row=0, col=1, text="Qty", is_header=True),
        Cell(row=1, col=0, text="Widget"),
        Cell(row=1, col=1, text="3"),
    ]
    html = table_to_html(Table(rows=2, cols=2, cells=cells))
    assert html.count("<tr>") == 2
    assert "<th>Item</th>" in html
    assert "<td>Widget</td>" in html


def test_table_to_html_encodes_colspan_and_escapes():
    cells = [Cell(row=0, col=0, colspan=2, text="A & B")]
    html = table_to_html(Table(rows=1, cols=2, cells=cells))
    assert 'colspan="2"' in html
    assert "A &amp; B" in html


def test_extract_cdm_tables_orders_by_page_then_reading_order():
    blocks = [
        Block(id="b2", role=BlockRole.TABLE, native_type="table", page_index=1,
              reading_order=0, table=Table(rows=1, cols=1, cells=[], html="<table>p1</table>")),
        Block(id="b1", role=BlockRole.TABLE, native_type="table", page_index=0,
              reading_order=5, table=Table(rows=1, cols=1, cells=[], html="<table>p0</table>")),
        Block(id="b0", role=BlockRole.TEXT, native_type="p", page_index=0, text="ignore me"),
    ]
    cdm = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                         page_count=2, pages=[Page(index=0), Page(index=1)], blocks=blocks)
    result = extract_cdm_tables(cdm)
    assert result == [(0, "<table>p0</table>"), (1, "<table>p1</table>")]


def test_sanitize_strips_script_and_handlers_keeps_text():
    dirty = '<table><tr><td onclick="x()">Hi<script>alert(1)</script></td></tr></table>'
    clean = sanitize_table_html(dirty)
    assert "script" not in clean.lower()
    assert "onclick" not in clean.lower()
    assert "Hi" in clean


def test_sanitize_keeps_table_tags_and_span_attrs():
    html = ('<table><tr><th colspan="2" scope="col">H</th></tr>'
            '<tr><td rowspan="2">a</td><td>b</td></tr></table>')
    clean = sanitize_table_html(html)
    assert "<th" in clean and 'colspan="2"' in clean and 'scope="col"' in clean
    assert 'rowspan="2"' in clean


def test_sanitize_drops_non_table_wrapper_tags():
    clean = sanitize_table_html('<div style="x"><table><tr><td>c</td></tr></table></div>')
    assert "<div" not in clean
    assert "style" not in clean
    assert "<td>c</td>" in clean
