import pytest
from app.cdm.source import ParseRun, ParseRunStatus
from app.cdm.models import ParserKind
from datetime import datetime, timezone

from app.services.parsing.errors import LlamaParseRunError, ParseFailedError


def _make_failed_run() -> ParseRun:
    return ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        config={},
        status=ParseRunStatus.FAILED,
        started_at=datetime.now(timezone.utc),
        error="SDK error: boom",
    )


def test_llama_parse_run_error_carries_run():
    run = _make_failed_run()
    err = LlamaParseRunError("SDK error: boom", run=run)
    assert err.run is run
    assert "boom" in str(err)


def test_parse_failed_error_is_runtime_error():
    err = ParseFailedError("parse failed")
    assert isinstance(err, RuntimeError)
    assert str(err) == "parse failed"
