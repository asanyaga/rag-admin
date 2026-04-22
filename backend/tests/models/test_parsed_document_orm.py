"""Round-trip sanity test for ParsedDocumentORM."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRunORM
from app.models.parsed_document import ParsedDocumentORM
from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_parsed_document_round_trip(test_db: AsyncSession):
    src = SourceDocumentORM(id=uuid4(), sha256="f" * 64, storage_uri="local://f.pdf")
    test_db.add(src)
    await test_db.commit()

    run = ParseRunORM(
        id=uuid4(), source_document_id=src.id,
        parser="llamaparse", representation_kind="vector_light",
        config_hash="0" * 64, status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()

    content = {"pages": [{"index": 0, "block_ids": []}], "full_text": "hello"}
    pdoc = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text="hello",
        full_markdown="# hello",
        page_count=1,
        block_count=0,
        content=content,
    )
    test_db.add(pdoc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(ParsedDocumentORM).where(ParsedDocumentORM.parse_run_id == run.id)
    )).scalar_one()
    assert fetched.full_text == "hello"
    assert fetched.page_count == 1
    assert fetched.content == content
