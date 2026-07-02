from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult, clamp01
from app.cdm.models import Block, BlockRole


def test_clamp01_bounds():
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0
    assert clamp01(0.25) == 0.25


def test_page_meta_defaults():
    pm = PageMeta(index=0, width=612.0, height=792.0)
    assert pm.unit == "points"
    assert pm.rotation == 0


def test_tool_result_holds_blocks_and_native_records():
    block = Block(id="fitz:0:0", role=BlockRole.TEXT, native_type="text",
                  text="hi", page_index=0)
    result = ToolResult(
        tool_id="fitz",
        blocks=[block],
        page_meta={0: PageMeta(index=0, width=612.0, height=792.0)},
        raw={"pages": {}},
        native_by_block={"fitz:0:0": {"type": 0}},
    )
    assert result.tool_id == "fitz"
    assert result.blocks[0].text == "hi"
    assert result.native_by_block["fitz:0:0"] == {"type": 0}
    assert result.warnings == []
    assert result.duration_ms == 0
