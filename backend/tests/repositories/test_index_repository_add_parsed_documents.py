"""Tests for IndexRepository.add_parsed_documents."""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexStatus
from app.models.index_document import IndexDocument, IndexDocumentStatus
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.repositories.index_repository import IndexRepository


async def _seed_project(db: AsyncSession):
    user = User(
        email=f"u{uuid4().hex[:6]}@example.com",
        password_hash="x",
        full_name="u",
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return user, project


async def _seed_doc_with_parsed(
    db: AsyncSession, *, user: User, project: Project, sha: str
) -> tuple[DocumentORM, ParsedDocument]:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    db.add(sd)
    await db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    pr = ParseRun(
        source_document_id=sd.id, parser="llamaparse",
        representation_kind="full_text", config={}, config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    pd = ParsedDocument(
        parse_run_id=pr.id, source_document_id=sd.id,
        full_text="hello", full_markdown=None,
        page_count=1, block_count=1, content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)
    await db.commit()
    await db.refresh(pd)
    return doc, pd


@pytest.mark.asyncio
async def test_add_parsed_documents_creates_index_documents_with_parse_run_id(test_db: AsyncSession):
    user, project = await _seed_project(test_db)
    doc, pd = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="a" * 64)

    idx = Index(
        project_id=project.id, name="idx",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    repo = IndexRepository(test_db)
    rows = await repo.add_parsed_documents(idx.id, [pd.parse_run_id])
    assert len(rows) == 1
    assert rows[0].parse_run_id == pd.parse_run_id
    assert rows[0].document_id == doc.id
    assert rows[0].processing_status == IndexDocumentStatus.pending


@pytest.mark.asyncio
async def test_add_parsed_documents_handles_multiple(test_db: AsyncSession):
    user, project = await _seed_project(test_db)
    docA, pdA = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="a" * 64)
    docB, pdB = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="b" * 64)

    idx = Index(
        project_id=project.id, name="idx2",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    repo = IndexRepository(test_db)
    rows = await repo.add_parsed_documents(idx.id, [pdA.parse_run_id, pdB.parse_run_id])
    by_run = {r.parse_run_id: r for r in rows}
    assert by_run[pdA.parse_run_id].document_id == docA.id
    assert by_run[pdB.parse_run_id].document_id == docB.id


@pytest.mark.asyncio
async def test_add_parsed_documents_empty_list_returns_empty(test_db: AsyncSession):
    user, project = await _seed_project(test_db)
    idx = Index(
        project_id=project.id, name="idx3",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    repo = IndexRepository(test_db)
    rows = await repo.add_parsed_documents(idx.id, [])
    assert rows == []
