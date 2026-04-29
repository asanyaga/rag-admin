import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Index, IndexStatus
from app.models.index_event import IndexEvent
from app.repositories.index_repository import IndexRepository


async def _make_index(db: AsyncSession, project_id, user_id) -> Index:
    index = Index(
        project_id=project_id,
        created_by=user_id,
        name="test-index",
        config={"chunking_strategy": "recursive_character", "source_representation": "raw_text"},
        status=IndexStatus.ready,
    )
    db.add(index)
    await db.commit()
    await db.refresh(index)
    return index


@pytest.mark.asyncio
async def test_increment_version(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)
    assert index.version == 1

    repo = IndexRepository(test_db)
    await repo.increment_version(index.id)

    await test_db.refresh(index)
    assert index.version == 2


@pytest.mark.asyncio
async def test_write_index_event(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)

    repo = IndexRepository(test_db)
    doc_id = str(uuid4())
    run_id = str(uuid4())

    event = await repo.write_index_event(
        index_id=index.id,
        version=1,
        config_snapshot={"chunking_strategy": "recursive_character"},
        document_bindings={doc_id: run_id},
        triggered_by=user_id,
    )

    assert event.version == 1
    assert event.document_bindings[doc_id] == run_id
    assert event.triggered_by == user_id


@pytest.mark.asyncio
async def test_write_index_event_preserves_null_bindings(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)

    repo = IndexRepository(test_db)
    doc_id = str(uuid4())

    event = await repo.write_index_event(
        index_id=index.id,
        version=1,
        config_snapshot={},
        document_bindings={doc_id: None},
        triggered_by=user_id,
    )

    assert event.document_bindings[doc_id] is None
