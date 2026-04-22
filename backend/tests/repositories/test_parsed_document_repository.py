"""Tests for ParsedDocumentRepository."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRun
from app.models.source_document import SourceDocument
from app.repositories.parsed_document_repository import (
    ParsedDocumentCreate,
    ParsedDocumentRepository,
)


@pytest.fixture
async def source_doc(test_db: AsyncSession) -> SourceDocument:
    sd = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)
    return sd


@pytest.fixture
async def parse_run(test_db: AsyncSession, source_doc) -> ParseRun:
    run = ParseRun(
        id=uuid4(),
        source_document_id=source_doc.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    await test_db.refresh(run)
    return run


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParsedDocumentRepository:
    return ParsedDocumentRepository(test_db)


@pytest.mark.asyncio
async def test_create_persists_row(repo, parse_run, source_doc):
    content = {"pages": [{"index": 0, "block_ids": ["b1"]}], "full_text": "hello"}
    pdoc = await repo.create(ParsedDocumentCreate(
        parse_run_id=parse_run.id,
        source_document_id=source_doc.id,
        full_text="hello",
        full_markdown="# hello",
        page_count=1,
        block_count=1,
        content=content,
    ))
    assert pdoc.parse_run_id == parse_run.id
    assert pdoc.content == content


@pytest.mark.asyncio
async def test_get_by_run_returns_row(repo, parse_run, source_doc):
    await repo.create(ParsedDocumentCreate(
        parse_run_id=parse_run.id,
        source_document_id=source_doc.id,
        full_text="x", full_markdown=None,
        page_count=0, block_count=0, content={},
    ))
    found = await repo.get_by_run(parse_run.id)
    assert found is not None
    assert found.parse_run_id == parse_run.id


@pytest.mark.asyncio
async def test_get_by_run_returns_none_when_absent(repo):
    assert await repo.get_by_run(uuid4()) is None
