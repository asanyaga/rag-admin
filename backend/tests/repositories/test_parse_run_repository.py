"""Tests for ParseRunRepository."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM
from app.repositories.parse_run_repository import (
    ParseRunCreate,
    ParseRunRepository,
)


@pytest.fixture
async def source_doc(test_db: AsyncSession) -> SourceDocumentORM:
    sd = SourceDocumentORM(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)
    return sd


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParseRunRepository:
    return ParseRunRepository(test_db)


def make_dto(source_doc, **override) -> ParseRunCreate:
    base = dict(
        source_document_id=source_doc.id,
        parser="llamaparse",
        parser_version=None,
        representation_kind="vector_light",
        config={"tier": "agentic"},
        config_hash="h" * 64,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    base.update(override)
    return ParseRunCreate(**base)


@pytest.mark.asyncio
async def test_create_persists_row(repo, source_doc):
    run = await repo.create(make_dto(source_doc))
    assert run.id is not None
    assert run.parser == "llamaparse"
    assert run.config == {"tier": "agentic"}


@pytest.mark.asyncio
async def test_get_returns_row_by_id(repo, source_doc):
    run = await repo.create(make_dto(source_doc))
    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.id == run.id


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(repo):
    assert await repo.get(uuid4()) is None


@pytest.mark.asyncio
async def test_get_latest_for_content_finds_exact_match(repo, source_doc):
    run = await repo.create(make_dto(source_doc, config_hash="x" * 64))
    found = await repo.get_latest_for_content(
        source_document_id=source_doc.id,
        representation_kind="vector_light",
        config_hash="x" * 64,
    )
    assert found is not None and found.id == run.id


@pytest.mark.asyncio
async def test_get_latest_for_content_returns_none_on_config_mismatch(repo, source_doc):
    await repo.create(make_dto(source_doc, config_hash="y" * 64))
    found = await repo.get_latest_for_content(
        source_document_id=source_doc.id,
        representation_kind="vector_light",
        config_hash="different" + "y" * 55,
    )
    assert found is None


@pytest.mark.asyncio
async def test_update_status_transitions_pending_to_succeeded(repo, source_doc):
    run = await repo.create(make_dto(source_doc, status="pending"))
    updated = await repo.update_status(
        run.id,
        status="succeeded",
        finished_at=datetime.now(timezone.utc),
        duration_ms=1234,
        input_tokens=100,
        output_tokens=50,
    )
    assert updated.status == "succeeded"
    assert updated.duration_ms == 1234
    assert updated.input_tokens == 100
    assert updated.output_tokens == 50
    assert updated.finished_at is not None
