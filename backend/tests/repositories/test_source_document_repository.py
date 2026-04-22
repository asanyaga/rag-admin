"""Tests for SourceDocumentRepository."""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM
from app.repositories.source_document_repository import SourceDocumentRepository


@pytest.fixture
async def repo(test_db: AsyncSession) -> SourceDocumentRepository:
    return SourceDocumentRepository(test_db)


@pytest.mark.asyncio
async def test_create_inserts_and_returns(repo: SourceDocumentRepository):
    sd = await repo.create(sha256="a" * 64, storage_uri="local://a.pdf", filename="a.pdf")
    assert sd.id is not None
    assert sd.sha256 == "a" * 64
    assert sd.filename == "a.pdf"


@pytest.mark.asyncio
async def test_get_by_sha256_returns_row_when_present(repo: SourceDocumentRepository):
    await repo.create(sha256="b" * 64, storage_uri="local://b.pdf")
    found = await repo.get_by_sha256("b" * 64)
    assert found is not None
    assert found.sha256 == "b" * 64


@pytest.mark.asyncio
async def test_get_by_sha256_returns_none_when_absent(repo: SourceDocumentRepository):
    assert await repo.get_by_sha256("z" * 64) is None


@pytest.mark.asyncio
async def test_get_by_id(repo: SourceDocumentRepository):
    sd = await repo.create(sha256="c" * 64, storage_uri="local://c.pdf")
    fetched = await repo.get(sd.id)
    assert fetched is not None and fetched.id == sd.id


@pytest.mark.asyncio
async def test_get_or_create_creates_when_absent(repo: SourceDocumentRepository):
    sd, created = await repo.get_or_create_by_sha256(
        sha256="d" * 64, storage_uri="local://d.pdf", filename="d.pdf",
    )
    assert created is True
    assert sd.filename == "d.pdf"


@pytest.mark.asyncio
async def test_get_or_create_reuses_when_present(repo: SourceDocumentRepository):
    first = await repo.create(sha256="e" * 64, storage_uri="local://e.pdf", filename="first.pdf")
    second, created = await repo.get_or_create_by_sha256(
        sha256="e" * 64, storage_uri="ignored", filename="ignored",
    )
    assert created is False
    assert second.id == first.id
    # Existing fields are NOT overwritten on reuse.
    assert second.filename == "first.pdf"
