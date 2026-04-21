from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.cdm.models import ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument


def test_source_document_minimum_shape():
    s = SourceDocument(
        id="src-1",
        sha256="a" * 64,
        created_at=datetime.now(timezone.utc),
    )
    assert s.filename is None
    assert s.storage_uri is None


def test_parse_run_defaults():
    r = ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        status=ParseRunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
    )
    assert r.config == {}
    assert r.cost == {}
    assert r.provider_refs == {}
    assert r.failed_pages == []
    assert r.warnings == []


def test_parse_run_is_frozen():
    r = ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        status=ParseRunStatus.PENDING,
        started_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        r.status = ParseRunStatus.SUCCEEDED


def test_parse_run_statuses():
    assert ParseRunStatus.PENDING.value == "pending"
    assert ParseRunStatus.RUNNING.value == "running"
    assert ParseRunStatus.SUCCEEDED.value == "succeeded"
    assert ParseRunStatus.FAILED.value == "failed"
    assert ParseRunStatus.PARTIAL.value == "partial"
