import json
from datetime import datetime, timezone
from pathlib import Path

import fitz
import pytest

from app.cdm.models import BlockRole, ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import CustomPipelineRunError
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline

FIXTURES = Path(__file__).parents[2] / "cdm" / "adapters" / "custom_pipeline" / "fixtures"


def _source() -> SourceDocument:
    return SourceDocument(
        id="doc-xyz",
        sha256="a" * 64,
        filename="simple_text.pdf",
        mime_type="application/pdf",
        byte_size=1234,
        storage_uri=str(FIXTURES / "simple_text.pdf"),
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_run_custom_pipeline_fitz_only_succeeds():
    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}}},
        "capabilities": {"layout_analysis": "fitz"},
        "eviction_overlap_threshold": 0.5,
    }
    run, doc = await run_custom_pipeline(
        source=_source(),
        file_path=str(FIXTURES / "simple_text.pdf"),
        representation_kind="extract_rich",
        config=config,
        client=None,
    )
    assert run.parser == ParserKind.CUSTOM_PIPELINE
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.source_document_id == "doc-xyz"
    assert run.raw_payload is not None
    assert "instances" in run.raw_payload
    assert "fitz" in run.raw_payload["instances"]
    assert doc.parse_run_id == run.id
    assert doc.page_count == 2
    assert any(b.role == BlockRole.TEXT for b in doc.blocks)
    # every block id is namespaced to the source document
    assert all(b.id.startswith("doc-xyz:") for b in doc.blocks)


@pytest.mark.asyncio
async def test_run_custom_pipeline_raw_payload_json_serializable_with_images(tmp_path):
    """Regression: fitz image bytes must not break the JSON raw_payload column."""
    pdf = tmp_path / "with_image.pdf"
    src = fitz.open()
    png = src.new_page().get_pixmap().tobytes("png")
    src.close()
    doc_pdf = fitz.open()
    page = doc_pdf.new_page()
    page.insert_image(fitz.Rect(50, 50, 150, 150), stream=png)
    doc_pdf.save(str(pdf))
    doc_pdf.close()

    config = {"tools": {"fitz": {"tool": "fitz", "config": {}}},
              "capabilities": {"layout_analysis": "fitz"}}
    run, _ = await run_custom_pipeline(
        source=_source(),
        file_path=str(pdf),
        representation_kind="extract_rich",
        config=config,
        client=None,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    # Must serialize cleanly — this is what the parse_runs INSERT does.
    json.dumps(run.raw_payload)


@pytest.mark.asyncio
async def test_run_custom_pipeline_wraps_failure(tmp_path):
    config = {"tools": {"fitz": {"tool": "fitz", "config": {}}},
              "capabilities": {"layout_analysis": "fitz"}}
    with pytest.raises(CustomPipelineRunError) as ei:
        await run_custom_pipeline(
            source=_source(),
            file_path=str(tmp_path / "does_not_exist.pdf"),
            representation_kind="extract_rich",
            config=config,
            client=None,
        )
    assert ei.value.run.status == ParseRunStatus.FAILED
    assert ei.value.run.parser == ParserKind.CUSTOM_PIPELINE


@pytest.mark.asyncio
async def test_run_custom_pipeline_fitz_tables_emits_table_blocks(tmp_path):
    """fitz_tables tool runs end-to-end and emits TABLE blocks."""
    pdf = tmp_path / "table_test.pdf"
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
    doc.save(str(pdf))
    doc.close()

    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "fitz_tables": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"layout_analysis": "fitz", "table_detection": "fitz_tables"},
        "eviction_overlap_threshold": 0.5,
    }
    run, doc_result = await run_custom_pipeline(
        source=_source(),
        file_path=str(pdf),
        representation_kind="extract_rich",
        config=config,
        client=None,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert "fitz_tables" in run.raw_payload["instances"]
    assert any(b.role == BlockRole.TABLE for b in doc_result.blocks)


@pytest.mark.asyncio
async def test_run_custom_pipeline_requires_a_layout_analysis_slot():
    """Two table tools are now structurally unrepresentable (the capabilities map
    has a single table_detection key), so the old dual-table guard is gone. What
    remains worth asserting is the required slot."""
    config = {"tools": {}, "capabilities": {}}
    with pytest.raises(CustomPipelineRunError, match="layout_analysis"):
        await run_custom_pipeline(
            source=_source(),
            file_path=str(FIXTURES / "simple_text.pdf"),
            representation_kind="extract_rich",
            config=config,
            client=None,
        )


@pytest.mark.asyncio
async def test_runner_passes_selected_pages_and_ocr_prefer(monkeypatch):
    """The runner must resolve the OCR page selection via select_pages and pass
    ocr_prefer through to the merger."""
    captured = {}

    import app.cdm.adapters.custom_pipeline.config as cfgmod
    from app.cdm.adapters.custom_pipeline.capabilities import Capability
    from app.cdm.adapters.custom_pipeline.tools.base import ToolResult

    class FakeOcr:
        tool_id = "tesseract"
        provides = frozenset({Capability.TEXT_OCR})
        def __init__(self, config=None): pass
        def select_pages(self, flags):
            captured["select_pages_called"] = True
            return [0]
        def run(self, pdf_path, *, pages=None, page_meta=None, emit=frozenset()):
            captured["ocr_pages"] = pages
            return ToolResult(tool_id="tesseract",
                              blocks_by_capability={Capability.TEXT_OCR: []})

    real_registry = cfgmod._tool_registry
    def fake_registry():
        reg = real_registry()
        reg["tesseract"] = cfgmod.ToolSpec(cfgmod.TesseractConfig,
                                           FakeOcr.provides, lambda c: FakeOcr())
        return reg
    monkeypatch.setattr(cfgmod, "_tool_registry", fake_registry)

    import app.cdm.adapters.custom_pipeline.merger as mergemod
    real_merge = mergemod.merge
    def spy_merge(*a, **k):
        captured["ocr_prefer"] = k.get("ocr_prefer")
        return real_merge(*a, **k)
    monkeypatch.setattr("app.services.parsing.custom_pipeline_runner.merge", spy_merge)

    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "ocr": {"tool": "tesseract", "config": {"pages": "auto"}}},
        "capabilities": {"layout_analysis": "fitz", "text_ocr": "ocr"},
        "precedence": {"text_ocr": "prefer"},
    }
    run, _ = await run_custom_pipeline(
        source=_source(), file_path=str(FIXTURES / "simple_text.pdf"),
        representation_kind="extract_rich", config=config, client=None)
    assert run.status == ParseRunStatus.SUCCEEDED
    assert captured["select_pages_called"] is True
    assert captured["ocr_pages"] == [0]
    assert captured["ocr_prefer"] is True
