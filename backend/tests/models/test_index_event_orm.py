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
