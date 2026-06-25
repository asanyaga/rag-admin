from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.cdm.models import BlockRole, ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import LocalPipelineRunError
from app.services.parsing.local_pipeline_runner import run_local_pipeline

FIXTURES = Path(__file__).parents[2] / "cdm" / "adapters" / "local_pipeline" / "fixtures"


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
async def test_run_local_pipeline_fitz_only_succeeds():
    config = {
        "tools": [{"tool_id": "fitz", "config": {}}],
        "eviction_overlap_threshold": 0.5,
    }
    run, doc = await run_local_pipeline(
        source=_source(),
        file_path=str(FIXTURES / "simple_text.pdf"),
        representation_kind="extract_rich",
        config=config,
        client=None,
    )
    assert run.parser == ParserKind.LOCAL_PIPELINE
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
async def test_run_local_pipeline_wraps_failure(tmp_path):
    config = {"tools": [{"tool_id": "fitz", "config": {}}]}
    with pytest.raises(LocalPipelineRunError) as ei:
        await run_local_pipeline(
            source=_source(),
            file_path=str(tmp_path / "does_not_exist.pdf"),
            representation_kind="extract_rich",
            config=config,
            client=None,
        )
    assert ei.value.run.status == ParseRunStatus.FAILED
    assert ei.value.run.parser == ParserKind.LOCAL_PIPELINE
