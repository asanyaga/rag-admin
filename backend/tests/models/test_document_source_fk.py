"""Document.source_document_id FK + relationship test."""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Document, DocumentStatus, Project, User
from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_document_can_reference_source_document(test_db: AsyncSession):
    user = User(id=uuid4(), email="u@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P")
    src = SourceDocumentORM(id=uuid4(), sha256="1" * 64, storage_uri="local://1.pdf")
    test_db.add_all([user, project, src])
    await test_db.commit()

    doc = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="1" * 64, title="T",
        source_metadata={}, status=DocumentStatus.ready,
        source_document_id=src.id,
    )
    test_db.add(doc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(Document).where(Document.id == doc.id).options(selectinload(Document.source_document))
    )).scalar_one()
    assert fetched.source_document_id == src.id
    assert fetched.source_document is not None
    assert fetched.source_document.sha256 == "1" * 64


@pytest.mark.asyncio
async def test_document_source_document_id_is_nullable(test_db: AsyncSession):
    """PR 1 leaves FK nullable for migration-ordering reasons."""
    user = User(id=uuid4(), email="u2@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P2")
    test_db.add_all([user, project])
    await test_db.commit()

    doc = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="null-test", title="T",
        source_metadata={}, status=DocumentStatus.ready,
    )
    test_db.add(doc)
    await test_db.commit()
    assert doc.source_document_id is None
