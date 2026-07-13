"""DoclingTool — unit tests using a fake DoclingDocument (no docling binary)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingConfig
from app.cdm.models import BlockRole


def _fake_bbox(l=50.0, t=750.0, r=545.0, b=700.0):
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin="BOTTOMLEFT")


def _fake_text_item(text, label="text", page_no=1):
    return SimpleNamespace(
        label=SimpleNamespace(value=label), text=text,
        prov=[SimpleNamespace(page_no=page_no, bbox=_fake_bbox())],
        export_to_markdown=lambda: text)


def _fake_doc(items, width=595.0, height=842.0):
    return SimpleNamespace(
        pages={1: SimpleNamespace(size=SimpleNamespace(width=width, height=height))},
        iterate_items=lambda: iter([(it, 0) for it in items]),
        export_to_markdown=lambda: "\n\n".join(i.text for i in items),
        model_dump_json=lambda: "{}",
    )


@pytest.fixture
def tool_result(monkeypatch, tmp_path):
    from app.cdm.adapters.custom_pipeline.tools import docling_tool
    items = [_fake_text_item("Annual Report", "title"),
             _fake_text_item("Body one", "text"),
             _fake_text_item("Body two", "text")]
    # Stub the heavy conversion + page splitting: one batch, offset 0.
    monkeypatch.setattr(docling_tool, "_convert_batch", lambda path: _fake_doc(items))
    monkeypatch.setattr(docling_tool, "_split_pages", lambda path, size: [(path, 0)])
    pdf = tmp_path / "doc.pdf"; pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    tool = docling_tool.DoclingTool(config=DoclingConfig())
    return tool.run(pdf, emit=frozenset({Capability.LAYOUT_ANALYSIS}))


def test_emits_layout_analysis_blocks(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert [b.role for b in blocks][0] == BlockRole.TITLE
    assert len(blocks) == 3


def test_blocks_carry_intrinsic_reading_order(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert [b.reading_order for b in blocks] == [0, 1, 2]


def test_provisional_ids_and_page_meta(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert blocks[0].id == "docling:0:0"
    assert tool_result.page_meta[0].width == 595.0


def test_bboxes_normalized(tool_result):
    for b in tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]:
        assert 0.0 <= b.bbox.x0 <= b.bbox.x1 <= 1.0
        assert 0.0 <= b.bbox.y0 <= b.bbox.y1 <= 1.0


def test_rejects_emit_it_does_not_provide():
    from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingTool
    from pathlib import Path
    with pytest.raises(ValueError, match="cannot emit"):
        DoclingTool().run(Path("x.pdf"), emit=frozenset({Capability.TABLE_DETECTION}))
