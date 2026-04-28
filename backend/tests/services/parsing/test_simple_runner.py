from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.ports.document_processing import ExtractionResult
from app.services.parsing.errors import SimpleRunError
from app.services.parsing.simple_runner import run_simple


def _make_source() -> SourceDocument:
    return SourceDocument(
        id="src-1",
        sha256="a" * 64,
        filename="test.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )


def _make_extractor(text: str = "hello", page_count: int = 1) -> AsyncMock:
    result = ExtractionResult(
        text=text,
        page_count=page_count,
        metadata={},
        page_boundaries=[{"page": 1, "start_char": 0, "end_char": len(text)}],
    )
    mock = AsyncMock()
    mock.extract = AsyncMock(return_value=result)
    return mock


@pytest.mark.asyncio
async def test_success_returns_run_and_doc():
    client = _make_extractor("hello world")
    run, doc = await run_simple(
        source=_make_source(),
        file_path="/tmp/test.pdf",
        representation_kind="extract_rich",
        config={"parser": "simple"},
        client=client,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.SIMPLE
    assert doc.full_text == "hello world"
    assert doc.page_count == 1


@pytest.mark.asyncio
async def test_extractor_called_with_file_path_and_mime_type():
    client = _make_extractor()
    source = _make_source()
    await run_simple(
        source=source,
        file_path="/tmp/doc.pdf",
        representation_kind="extract_rich",
        config={"parser": "simple"},
        client=client,
    )
    client.extract.assert_awaited_once_with("/tmp/doc.pdf", "application/pdf")


@pytest.mark.asyncio
async def test_extractor_failure_raises_simple_run_error():
    client = AsyncMock()
    client.extract = AsyncMock(side_effect=IOError("file not found"))
    with pytest.raises(SimpleRunError) as exc_info:
        await run_simple(
            source=_make_source(),
            file_path="/tmp/missing.pdf",
            representation_kind="extract_rich",
            config={"parser": "simple"},
            client=client,
        )
    assert exc_info.value.run.status == ParseRunStatus.FAILED
    assert "file not found" in exc_info.value.run.error


@pytest.mark.asyncio
async def test_run_id_propagated_when_provided():
    client = _make_extractor()
    run, _ = await run_simple(
        source=_make_source(),
        file_path="/tmp/test.pdf",
        representation_kind="extract_rich",
        config={"parser": "simple"},
        client=client,
        parse_run_id="fixed-run-id",
    )
    assert run.id == "fixed-run-id"
