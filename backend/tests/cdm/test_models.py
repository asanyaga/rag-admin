import pytest
from pydantic import ValidationError

from app.cdm.models import BBox, BlockRole, Cell, CoordSpace, ParserKind, Quality, Span, Style, Table


def test_parser_kind_values():
    assert ParserKind.LLAMAPARSE.value == "llamaparse"
    assert ParserKind.LITEPARSE.value == "liteparse"
    assert ParserKind.UNSTRUCTURED.value == "unstructured"
    assert ParserKind.LANDING_AI.value == "landing_ai"


def test_block_role_has_coarse_taxonomy():
    # Closed taxonomy — ~14 values.
    assert BlockRole.TITLE.value == "title"
    assert BlockRole.PARAGRAPH.value == "paragraph"
    assert BlockRole.TABLE.value == "table"
    assert BlockRole.OTHER.value == "other"


def test_bbox_defaults_to_normalized_space():
    b = BBox(x0=0.1, y0=0.2, x1=0.5, y1=0.6)
    assert b.space == CoordSpace.NORMALIZED
    assert b.source_space is None
    assert b.source_coords is None


def test_bbox_preserves_source_coords():
    b = BBox(
        x0=0.1, y0=0.2, x1=0.5, y1=0.6,
        source_space="pdf_points",
        source_coords=(72.0, 144.0, 360.0, 432.0),
    )
    assert b.source_space == "pdf_points"
    assert b.source_coords == (72.0, 144.0, 360.0, 432.0)


def test_bbox_is_frozen():
    b = BBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    with pytest.raises(ValidationError):
        b.x0 = 0.5


def test_quality_defaults():
    q = Quality()
    assert q.confidence is None
    assert q.low_confidence_spans == []
    assert q.notes is None


def test_style_fields_optional():
    s = Style(font_name="Helvetica", font_size=12.0, bold=True, italic=False)
    assert s.bold is True


def test_span_carries_text_and_optional_bbox():
    sp = Span(text="hello")
    assert sp.text == "hello"
    assert sp.bbox is None
    assert sp.style is None


def test_cell_minimum_fields():
    c = Cell(row=0, col=0, text="A")
    assert c.rowspan == 1
    assert c.colspan == 1
    assert c.is_header is False


def test_table_requires_dimensions_and_cells():
    t = Table(rows=2, cols=2, cells=[
        Cell(row=0, col=0, text="A", is_header=True),
        Cell(row=0, col=1, text="B", is_header=True),
        Cell(row=1, col=0, text="1"),
        Cell(row=1, col=1, text="2"),
    ])
    assert t.rows == 2
    assert len(t.cells) == 4
    assert t.html is None
    assert t.markdown is None
