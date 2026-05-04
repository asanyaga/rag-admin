"""Round-trip sanity test for ParseRun."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRun
from app.models.source_document import SourceDocument


@pytest.mark.asyncio
async def test_parse_run_round_trip(test_db: AsyncSession):
    src = SourceDocument(
        id=uuid4(), sha256="b" * 64, storage_uri="local://b.pdf",
    )
    test_db.add(src)
    await test_db.commit()

    run = ParseRun(
        id=uuid4(),
        source_document_id=src.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config={"tier": "agentic"},
        config_hash="c" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(ParseRun).where(ParseRun.id == run.id)
    )).scalar_one()
    assert fetched.parser == "llamaparse"
    assert fetched.config == {"tier": "agentic"}
    assert fetched.warnings == []
    assert fetched.provider_refs == {}


@pytest.mark.asyncio
async def test_parse_run_duplicate_content_config_allowed(test_db: AsyncSession):
    """Two parse runs with the same (source_document_id, representation_kind, config_hash)
    must be insertable — the unique constraint was dropped so that failed runs can be retried."""
    src = SourceDocument(id=uuid4(), sha256="d" * 64, storage_uri="local://d.pdf")
    test_db.add(src)
    await test_db.commit()

    def make_run(**kw):
        return ParseRun(
            id=uuid4(),
            source_document_id=src.id,
            parser="llamaparse",
            representation_kind="vector_light",
            config={}, config_hash="e" * 64,
            status="succeeded",
            started_at=datetime.now(timezone.utc),
            **kw,
        )

    test_db.add(make_run())
    await test_db.commit()
    test_db.add(make_run())
    await test_db.commit()  # must not raise

    result = await test_db.execute(select(ParseRun).where(ParseRun.source_document_id == src.id))
    assert len(result.scalars().all()) == 2
