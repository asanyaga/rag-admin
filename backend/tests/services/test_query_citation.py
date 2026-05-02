"""Tests for ChunkCitation resolution inside QueryService._to_result."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.cdm.models import BBox, Block, BlockRole, CoordSpace, Quality
from app.services.query_service import QueryService


def _chunk(*, source_type: str, chunk_metadata: dict, parse_run_id=None,
           document_title="Doc"):
    chunk_id = uuid4()
    document_id = uuid4()
    index_id = uuid4()
    return SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        index_id=index_id,
        index_version=1,
        parse_run_id=parse_run_id,
        source_type=source_type,
        chunk_metadata=chunk_metadata,
        chunk_index=0,
        token_count=10,
        char_count=42,
        content="content",
        document=SimpleNamespace(
            title=document_title,
            source_metadata={"filename": "doc.pdf"},
        ),
    )


@pytest.mark.asyncio
async def test_citation_resolution_text_chunk_populates_text_fields():
    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="full_text",
        chunk_metadata={"start_char": 100, "end_char": 250, "page_numbers": [3]},
    )
    result = await svc._to_result(chunk, score=0.9, rank=1)

    assert result.citation is not None
    assert result.citation.source_type == "full_text"
    assert result.citation.start_char == 100
    assert result.citation.end_char == 250
    assert result.citation.page_numbers == [3]
    assert result.citation.block_ids is None


@pytest.mark.asyncio
async def test_citation_resolution_markdown_chunk_populates_heading_path():
    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="full_markdown",
        chunk_metadata={
            "start_char": 0,
            "end_char": 100,
            "heading_path": ["Financials", "Q3 Results"],
        },
    )
    result = await svc._to_result(chunk, score=0.8, rank=1)

    assert result.citation.heading_path == ["Financials", "Q3 Results"]


@pytest.mark.asyncio
async def test_citation_resolution_block_resolves_against_parsed_doc(monkeypatch):
    parse_run_id = uuid4()
    bbox = BBox(x0=0.1, y0=0.0, x1=0.9, y1=0.05, space=CoordSpace.NORMALIZED)
    blocks = [
        Block(
            id="b1", role=BlockRole.HEADING, native_type="h1", page_index=2,
            bbox=bbox, text="Heading", quality=Quality(confidence=0.95),
        ).model_dump(),
        Block(
            id="b2", role=BlockRole.PARAGRAPH, native_type="p", page_index=2,
            bbox=bbox.model_copy(update={"y0": 0.1, "y1": 0.2}),
            text="body", quality=Quality(confidence=0.6),
        ).model_dump(),
    ]
    parsed_doc_row = SimpleNamespace(content={"blocks": blocks})
    repo_get = AsyncMock(return_value=parsed_doc_row)
    monkeypatch.setattr(
        "app.services.query_service.ParsedDocumentRepository",
        lambda session: SimpleNamespace(get_by_run=repo_get),
    )

    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=SimpleNamespace(session=object()),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="block",
        parse_run_id=parse_run_id,
        chunk_metadata={"block_ids": ["b1", "b2"]},
    )
    result = await svc._to_result(chunk, score=0.7, rank=1)

    cit = result.citation
    assert cit.block_ids == ["b1", "b2"]
    assert cit.page_indices == [2]
    assert cit.block_roles == ["heading", "paragraph"]
    assert len(cit.bboxes) == 2
    assert cit.confidence == pytest.approx(0.6)
    repo_get.assert_awaited_once_with(parse_run_id)


@pytest.mark.asyncio
async def test_citation_resolution_block_missing_parse_run_degrades_gracefully(monkeypatch):
    repo_get = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.query_service.ParsedDocumentRepository",
        lambda session: SimpleNamespace(get_by_run=repo_get),
    )

    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=SimpleNamespace(session=object()),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="block",
        parse_run_id=uuid4(),
        chunk_metadata={"block_ids": ["x"]},
    )
    result = await svc._to_result(chunk, score=0.5, rank=1)

    cit = result.citation
    assert cit.block_ids is None
    assert cit.bboxes is None
    assert cit.confidence is None
    assert cit.source_type == "block"
