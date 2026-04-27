"""Tests for run_landingai using a mock SDK client."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import LandingAIRunError
from app.services.parsing.landingai_runner import run_landingai


def _source() -> SourceDocument:
    return SourceDocument(
        id=str(uuid4()),
        sha256="b" * 64,
        filename="test.jpg",
        storage_uri="local://test.jpg",
        created_at=datetime.now(timezone.utc),
    )


def _completed_response(source_id: str) -> Any:
    """Simulate a completed parse_jobs.get() response."""
    raw = {
        "chunks": [
            {
                "id": "chunk-1",
                "type": "text",
                "markdown": "Hello",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            }
        ],
        "markdown": "Hello",
        "metadata": {
            "filename": "test.jpg",
            "page_count": 1,
            "duration_ms": 500,
            "credit_usage": 0.5,
            "job_id": "job-xyz",
            "version": "dpt-2-latest",
            "failed_pages": [],
        },
        "splits": [],
        "grounding": {
            "chunk-1": {"type": "chunkText", "confidence": 0.9, "low_confidence_spans": []},
        },
    }
    data = MagicMock()
    data.model_dump = MagicMock(return_value=raw)
    return SimpleNamespace(status="completed", data=data)


def _make_client(source_id: str, fail: bool = False) -> Any:
    job = SimpleNamespace(job_id="job-xyz")
    if fail:
        poll_response = SimpleNamespace(status="failed", data=None)
    else:
        poll_response = _completed_response(source_id)
    client = MagicMock()
    client.parse_jobs.create.return_value = job
    client.parse_jobs.get.return_value = poll_response
    return client


@pytest.mark.asyncio
async def test_run_landingai_success(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")  # minimal JPEG header
    client = _make_client(src.id)

    run, doc = await run_landingai(
        source=src,
        file_path=str(f),
        representation_kind="extract_rich",
        config={"model": "dpt-2-latest"},
        client=client,
    )

    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.LANDING_AI
    assert run.provider_refs.get("landingai_job_id") == "job-xyz"
    assert run.parser_version == "dpt-2-latest"
    assert run.cost.get("credits") == pytest.approx(0.5)
    assert doc is not None
    assert doc.source_document_id == src.id
    assert doc.page_count == 1


@pytest.mark.asyncio
async def test_run_landingai_failure_raises_error(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")
    client = _make_client(src.id, fail=True)

    with pytest.raises(LandingAIRunError) as exc_info:
        await run_landingai(
            source=src,
            file_path=str(f),
            representation_kind="extract_rich",
            config={"model": "dpt-2-latest"},
            client=client,
        )

    err = exc_info.value
    assert err.run.status == ParseRunStatus.FAILED
    assert err.run.parser == ParserKind.LANDING_AI


@pytest.mark.asyncio
async def test_run_landingai_timeout_raises_error(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")

    # Client always returns "running" — will time out immediately with poll_timeout_s=0
    job = SimpleNamespace(job_id="job-xyz")
    running_response = SimpleNamespace(status="running", data=None)
    client = MagicMock()
    client.parse_jobs.create.return_value = job
    client.parse_jobs.get.return_value = running_response

    with pytest.raises(LandingAIRunError) as exc_info:
        await run_landingai(
            source=src,
            file_path=str(f),
            representation_kind="extract_rich",
            config={"model": "dpt-2-latest", "poll_timeout_s": 0, "poll_interval_s": 0.01},
            client=client,
        )

    assert exc_info.value.run.status == ParseRunStatus.FAILED
