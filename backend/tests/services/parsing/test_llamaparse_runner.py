from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.llamaparse_runner import run_llamaparse


MINIMAL_RAW = {
    "text": "Hello.",
    "markdown": "Hello.",
    "items": {"pages": [{
        "page_number": 1, "width": 100.0, "height": 200.0,
        "items": [{"type": "text", "value": "Hello.", "md": "Hello.",
                   "bbox": [{"x": 0, "y": 0, "w": 100, "h": 10, "confidence": 0.9}]}],
    }]},
    "metadata": {"pages": [{"page_number": 1, "confidence": 0.95}]},
    "job_metadata": {"job_id": "job-xyz",
                     "pdf-inputTokens": 10, "pdf-outputTokens": 5, "pdf-llmTime": 500},
}


class _FakeClient:
    def __init__(self, response: dict):
        self.parsing = SimpleNamespace(
            parse=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: response))
        )


@pytest.mark.asyncio
async def test_runner_returns_run_and_doc_on_success(tmp_path):
    src = SourceDocument(
        id="src-1", sha256="a" * 64,
        filename="hello.pdf",
        created_at=datetime.now(timezone.utc),
    )
    file_path = tmp_path / "hello.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    client = _FakeClient(MINIMAL_RAW)

    run, doc = await run_llamaparse(
        source=src,
        file_path=str(file_path),
        representation_kind="extract_rich",
        config={"tier": "agentic"},
        client=client,
    )
    assert run.parser == ParserKind.LLAMAPARSE
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.provider_refs["llamaparse_job_id"] == "job-xyz"
    assert run.input_tokens == 10
    assert run.output_tokens == 5
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert doc.parse_run_id == run.id
    assert doc.source_document_id == src.id


@pytest.mark.asyncio
async def test_runner_records_failure(tmp_path):
    src = SourceDocument(
        id="src-1", sha256="a" * 64,
        created_at=datetime.now(timezone.utc),
    )
    file_path = tmp_path / "hello.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    class _BoomClient:
        def __init__(self):
            self.parsing = SimpleNamespace(parse=AsyncMock(side_effect=RuntimeError("boom")))
    client = _BoomClient()

    with pytest.raises(RuntimeError):
        await run_llamaparse(
            source=src,
            file_path=str(file_path),
            representation_kind="extract_rich",
            config={},
            client=client,
        )
