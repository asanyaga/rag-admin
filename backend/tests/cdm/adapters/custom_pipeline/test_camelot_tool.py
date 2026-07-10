from types import SimpleNamespace

import pandas as pd
import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import CamelotConfig
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta
from app.cdm.adapters.custom_pipeline.tools.camelot_tool import CamelotTool
from app.cdm.models import BlockRole


def _fake_cell(x1, y1, x2, y2, text):
    return SimpleNamespace(x1=x1, y1=y1, x2=x2, y2=y2, text=text)


def _fake_table():
    # camelot bottom-left origin; page is 792pt tall.
    return SimpleNamespace(
        page=2,
        df=pd.DataFrame([["A", "B"]]),  # 1 row, 2 cols
        parsing_report={"accuracy": 98.5, "order": 1, "page": 2, "whitespace": 12.0},
        _bbox=(72.0, 600.0, 540.0, 720.0),  # x1,y1,x2,y2 bottom-left
        cells=[[_fake_cell(72.0, 700.0, 300.0, 720.0, "A"),
                _fake_cell(300.0, 700.0, 540.0, 720.0, "B")]],
    )


def test_camelot_tool_id():
    assert CamelotTool().tool_id == "camelot"


def test_table_to_block_role_and_page_index():
    pm = PageMeta(index=1, width=612.0, height=792.0)
    tool = CamelotTool()
    block = tool._table_to_block(_fake_table(), page_index=1, page_meta=pm, table_seq=0)
    assert block.role == BlockRole.TABLE
    assert block.page_index == 1
    assert block.id == "camelot:1:0"


def test_table_to_block_bbox_y_flipped_and_normalized():
    pm = PageMeta(index=1, width=612.0, height=792.0)
    block = CamelotTool()._table_to_block(_fake_table(), page_index=1, page_meta=pm, table_seq=0)
    bb = block.bbox
    # bottom-left (72,600,540,720) → top-left y: y0=(792-720)/792, y1=(792-600)/792
    assert bb.x0 == pytest.approx(72.0 / 612.0)
    assert bb.x1 == pytest.approx(540.0 / 612.0)
    assert bb.y0 == pytest.approx((792.0 - 720.0) / 792.0)
    assert bb.y1 == pytest.approx((792.0 - 600.0) / 792.0)
    assert bb.source_space == "pdf_points"


def test_table_to_block_cells_and_html_and_extras():
    pm = PageMeta(index=1, width=612.0, height=792.0)
    block = CamelotTool(config=CamelotConfig(flavor="stream"))._table_to_block(
        _fake_table(), page_index=1, page_meta=pm, table_seq=0
    )
    assert block.table is not None
    assert block.table.rows == 1
    assert block.table.cols == 2
    assert "A" in block.table.html and "B" in block.table.html
    assert {c.text for c in block.table.cells} == {"A", "B"}
    assert block.parser_extras["camelot_accuracy"] == 98.5
    assert block.parser_extras["camelot_order"] == 1
    assert block.parser_extras["camelot_flavor"] == "stream"


def test_table_to_block_populates_block_level_content():
    """The TABLE block itself must carry text/markdown/html so it surfaces in
    full_text / full_markdown (block.table alone is not rendered)."""
    pm = PageMeta(index=1, width=612.0, height=792.0)
    block = CamelotTool()._table_to_block(
        _fake_table(), page_index=1, page_meta=pm, table_seq=0
    )
    assert "A" in block.text and "B" in block.text
    assert block.markdown is not None and "A" in block.markdown
    assert block.html is not None and "A" in block.html


def test_run_maps_pages_arg_and_invokes_camelot(monkeypatch):
    calls = {}

    def fake_read_pdf(path, **kwargs):
        calls.update(kwargs)
        calls["path"] = path
        return [_fake_table()]

    import app.cdm.adapters.custom_pipeline.tools.camelot_tool as mod
    monkeypatch.setattr(mod.camelot, "read_pdf", fake_read_pdf)

    pm = {1: PageMeta(index=1, width=612.0, height=792.0)}
    result = CamelotTool().run("/tmp/x.pdf", pages=[1], page_meta=pm)
    # 0-based page 1 → camelot 1-indexed "2"
    assert calls["pages"] == "2"
    assert calls["flavor"] == "lattice"
    assert len(result.blocks_by_capability[Capability.TABLE_DETECTION]) == 1
    assert result.blocks_by_capability[Capability.TABLE_DETECTION][0].id == "camelot:1:0"
    assert result.blocks_by_capability[Capability.TABLE_DETECTION][0].id in result.native_by_block


def test_run_lattice_omits_stream_only_kwargs(monkeypatch):
    """camelot rejects edge_tol/row_tol with flavor='lattice'."""
    calls = {}

    def fake_read_pdf(path, **kwargs):
        calls.update(kwargs)
        return []

    import app.cdm.adapters.custom_pipeline.tools.camelot_tool as mod
    monkeypatch.setattr(mod.camelot, "read_pdf", fake_read_pdf)

    CamelotTool(config=CamelotConfig(flavor="lattice")).run("/tmp/x.pdf")
    assert "edge_tol" not in calls
    assert "row_tol" not in calls


def test_run_stream_includes_tol_kwargs(monkeypatch):
    """edge_tol/row_tol are valid (and useful) for flavor='stream'."""
    calls = {}

    def fake_read_pdf(path, **kwargs):
        calls.update(kwargs)
        return []

    import app.cdm.adapters.custom_pipeline.tools.camelot_tool as mod
    monkeypatch.setattr(mod.camelot, "read_pdf", fake_read_pdf)

    CamelotTool(config=CamelotConfig(flavor="stream", edge_tol=40, row_tol=3)).run("/tmp/x.pdf")
    assert calls["edge_tol"] == 40
    assert calls["row_tol"] == 3


def test_camelot_declares_table_detection():
    assert CamelotTool().provides == frozenset({Capability.TABLE_DETECTION})
