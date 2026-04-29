import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.index_event import IndexEvent


@pytest.mark.asyncio
async def test_index_event_can_be_created(test_db: AsyncSession):
    # Requires a user and index to exist — use raw inserts to avoid FK issues in test
    user_id = uuid4()
    index_id = uuid4()

    event = IndexEvent(
        index_id=index_id,
        version=1,
        config_snapshot={"chunking_strategy": "recursive_character"},
        document_bindings={str(uuid4()): str(uuid4())},
        triggered_by=user_id,
    )
    test_db.add(event)
    await test_db.commit()
    await test_db.refresh(event)

    assert event.id is not None
    assert event.version == 1
    assert event.config_snapshot["chunking_strategy"] == "recursive_character"
    assert event.created_at is not None


from app.models import Index, IndexDocument, Chunk


def test_index_model_has_new_fields():
    index = Index()
    assert hasattr(index, 'version')
    assert hasattr(index, 'parser')
    assert hasattr(index, 'parse_config_hash')
    assert hasattr(index, 'config_dirty')


def test_index_document_model_has_parse_run_id():
    doc = IndexDocument()
    assert hasattr(doc, 'parse_run_id')


def test_chunk_model_has_provenance_fields():
    chunk = Chunk()
    assert hasattr(chunk, 'index_version')
    assert hasattr(chunk, 'parse_run_id')
    assert hasattr(chunk, 'source_type')
