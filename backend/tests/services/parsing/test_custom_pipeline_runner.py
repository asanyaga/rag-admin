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
        "tools": [{"tool_id": "fitz", "config": {}}],
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
    assert "tools" in run.raw_payload
    assert "fitz" in run.raw_payload["tools"]
    assert doc.parse_run_id == run.id
    assert doc.page_count == 2
    assert any(b.role == BlockRole.PARAGRAPH for b in doc.blocks)
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

    config = {"tools": [{"tool_id": "fitz", "config": {}}]}
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
    config = {"tools": [{"tool_id": "fitz", "config": {}}]}
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
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
        ],
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
    assert "fitz_tables" in run.raw_payload["tools"]
    assert any(b.role == BlockRole.TABLE for b in doc_result.blocks)


@pytest.mark.asyncio
async def test_run_custom_pipeline_rejects_dual_table_tools():
    config = {
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
            {"tool_id": "camelot", "config": {}},
        ],
    }
    with pytest.raises(CustomPipelineRunError) as ei:
        await run_custom_pipeline(
            source=_source(),
            file_path=str(FIXTURES / "simple_text.pdf"),
            representation_kind="extract_rich",
            config=config,
            client=None,
        )
    assert ei.value.run.status == ParseRunStatus.FAILED
