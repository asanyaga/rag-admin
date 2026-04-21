import pytest
from pydantic import ValidationError

from app.cdm.models import BBox, BlockRole, CoordSpace, ParserKind


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
