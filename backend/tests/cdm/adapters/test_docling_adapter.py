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
