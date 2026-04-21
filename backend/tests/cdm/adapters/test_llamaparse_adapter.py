import pytest

from app.cdm.adapters.llamaparse import (
    _map_role,
    _pdf_points_to_normalized,
    _union_bbox,
)
from app.cdm.models import BBox, BlockRole


def test_pdf_points_to_normalized_basic():
    bbox = _pdf_points_to_normalized(x=10, y=20, w=30, h=40,
                                      page_width=100, page_height=200)
    assert bbox.x0 == pytest.approx(0.10)
    assert bbox.y0 == pytest.approx(0.10)
    assert bbox.x1 == pytest.approx(0.40)
    assert bbox.y1 == pytest.approx(0.30)
    assert bbox.source_space == "pdf_points"
    assert bbox.source_coords == (10.0, 20.0, 30.0, 40.0)


def test_pdf_points_clamps_to_unit_square():
    bbox = _pdf_points_to_normalized(x=0, y=0, w=101, h=201,
                                      page_width=100, page_height=200)
    assert bbox.x0 == 0.0
    assert bbox.y0 == 0.0
    assert bbox.x1 == 1.0
    assert bbox.y1 == 1.0


def test_union_bbox_single():
    b = BBox(x0=0.1, y0=0.2, x1=0.5, y1=0.6)
    assert _union_bbox([b]) == b


def test_union_bbox_multiple():
    b1 = BBox(x0=0.1, y0=0.2, x1=0.4, y1=0.5)
    b2 = BBox(x0=0.2, y0=0.1, x1=0.6, y1=0.4)
    u = _union_bbox([b1, b2])
    assert u.x0 == pytest.approx(0.1)
    assert u.y0 == pytest.approx(0.1)
    assert u.x1 == pytest.approx(0.6)
    assert u.y1 == pytest.approx(0.5)


def test_union_bbox_empty_returns_none():
    assert _union_bbox([]) is None


@pytest.mark.parametrize("llama_type,expected_role", [
    ("heading", BlockRole.HEADING),
    ("text", BlockRole.PARAGRAPH),
    ("list", BlockRole.LIST),
    ("table", BlockRole.TABLE),
    ("image", BlockRole.FIGURE),
    ("header", BlockRole.HEADER),
    ("footer", BlockRole.FOOTER),
    ("code", BlockRole.CODE),
    ("link", BlockRole.LINK),
    ("mystery", BlockRole.OTHER),
])
def test_map_role(llama_type, expected_role):
    assert _map_role(llama_type) == expected_role
