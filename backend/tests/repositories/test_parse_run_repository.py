"""Tests for ParseRunRepository."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.document import Document as DocumentORM
from app.models.source_document import SourceDocument
from app.repositories.parse_run_repository import (
    ParseRunCreate,
    ParseRunRepository,
)


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="test@example.com",
        full_name="Test User",
        auth_provider="email",
        password_hash="hashed",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def source_doc(test_db: AsyncSession) -> SourceDocument:
    sd = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
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


@pytest.fixture
async def source_and_doc(test_db: AsyncSession, user: User):
    """Returns (SourceDocument ORM, project_id UUID) with a Document linking them."""
    project_id = uuid4()
    sd = SourceDocument(id=uuid4(), sha256="b" * 64, storage_uri="local://b.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)

    doc = DocumentORM(
        project_id=project_id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier="b.pdf",
        title="B",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    return sd, project_id


@pytest.mark.asyncio
async def test_get_latest_for_project_finds_run_in_same_project(repo, source_and_doc):
    sd, project_id = source_and_doc
    run = await repo.create(make_dto(sd, config_hash="p" * 64))
    found = await repo.get_latest_for_project(
        source_document_id=sd.id,
        representation_kind="vector_light",
        config_hash="p" * 64,
        project_id=project_id,
    )
    assert found is not None
    assert found.id == run.id


@pytest.mark.asyncio
async def test_get_latest_for_project_returns_none_for_different_project(repo, source_and_doc):
    sd, _project_id = source_and_doc
    await repo.create(make_dto(sd, config_hash="p" * 64))
    other_project_id = uuid4()
    found = await repo.get_latest_for_project(
        source_document_id=sd.id,
        representation_kind="vector_light",
        config_hash="p" * 64,
        project_id=other_project_id,
    )
    assert found is None


@pytest.mark.asyncio
async def test_get_latest_for_project_returns_none_for_config_mismatch(repo, source_and_doc):
    sd, project_id = source_and_doc
    await repo.create(make_dto(sd, config_hash="p" * 64))
    found = await repo.get_latest_for_project(
        source_document_id=sd.id,
        representation_kind="vector_light",
        config_hash="different" + "x" * 55,
        project_id=project_id,
    )
    assert found is None


@pytest.mark.asyncio
async def test_list_for_source_document_empty(repo):
    assert await repo.list_for_source_document(uuid4()) == []


@pytest.mark.asyncio
async def test_list_for_source_document_orders_newest_first(
    repo, source_doc, test_db
):
    r1 = await repo.create(make_dto(source_doc, config_hash="1" * 64))
    r2 = await repo.create(make_dto(source_doc, config_hash="2" * 64))
    r3 = await repo.create(make_dto(source_doc, config_hash="3" * 64))

    # Bump created_at deterministically: r2 newest, r3 middle, r1 oldest.
    r1.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    r3.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    r2.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    await test_db.commit()

    rows = await repo.list_for_source_document(source_doc.id)
    assert [r.id for r in rows] == [r2.id, r3.id, r1.id]


@pytest.mark.asyncio
async def test_list_for_source_document_excludes_other_sources(
    repo, source_doc, test_db
):
    await repo.create(make_dto(source_doc, config_hash="1" * 64))
    other = SourceDocument(id=uuid4(), sha256="c" * 64, storage_uri="local://c.pdf")
    test_db.add(other)
    await test_db.commit()
    await test_db.refresh(other)
    other_run = await repo.create(make_dto(other, config_hash="2" * 64))

    rows = await repo.list_for_source_document(other.id)
    assert [r.id for r in rows] == [other_run.id]


@pytest.mark.asyncio
async def test_create_with_explicit_id(repo, source_doc):
    explicit_id = uuid4()
    run = await repo.create(make_dto(source_doc, id=explicit_id))
    assert run.id == explicit_id
