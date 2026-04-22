"""Round-trip sanity test for SourceDocument."""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocument


@pytest.mark.asyncio
async def test_source_document_round_trip(test_db: AsyncSession):
    row = SourceDocument(
        id=uuid4(),
        sha256="a" * 64,
        filename="test.pdf",
        mime_type="application/pdf",
        byte_size=1234,
        storage_uri="local://test.pdf",
    )
    test_db.add(row)
    await test_db.commit()

    result = await test_db.execute(
        select(SourceDocument).where(SourceDocument.sha256 == "a" * 64)
    )
    fetched = result.scalar_one()
    assert fetched.filename == "test.pdf"
    assert fetched.byte_size == 1234
    assert fetched.storage_uri == "local://test.pdf"
