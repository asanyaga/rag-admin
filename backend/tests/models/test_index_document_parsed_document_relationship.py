"""IndexDocument relationship to ParsedDocument and parse_run FK cascade behaviour.

Unit 1 of the parsed-document refactor: with no separate `parsed_document_id`
column (parsed_documents.parse_run_id IS its primary key — 1:1 with parse_run),
IndexDocument exposes a `parsed_document` relationship by joining on
`parse_run_id`, and the existing `parse_run_id` FK cascades on delete to keep
integrity in the parsed-doc-centric model.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Document, DocumentStatus, Project, User
from app.models.index import Index
from app.models.index_document import IndexDocument
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument


def _parse_run_fk(table) -> object:
    """Return the FK constraint on index_documents.parse_run_id."""
    for fk in table.foreign_keys:
        if fk.column.table.name == "parse_runs":
            return fk
    raise AssertionError("No FK to parse_runs found on index_documents")


def test_index_document_parse_run_fk_cascades_on_delete():
    fk = _parse_run_fk(IndexDocument.__table__)
    assert fk.ondelete == "CASCADE", (
        "IndexDocument.parse_run_id must cascade-delete in the parsed-doc-centric model "
        f"(current ondelete={fk.ondelete!r})"
    )


@pytest.mark.asyncio
async def test_index_document_parsed_document_relationship_traverses(test_db: AsyncSession):
    user = User(id=uuid4(), email="u@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P")
    src = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add_all([user, project, src])
    await test_db.commit()

    document = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="a" * 64, title="T",
        source_metadata={}, status=DocumentStatus.ready,
        source_document_id=src.id,
    )
    run = ParseRun(
        id=uuid4(), source_document_id=src.id,
        parser="llamaparse", representation_kind="full_markdown",
        config_hash="0" * 64, status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add_all([document, run])
    await test_db.commit()

    parsed_doc = ParsedDocument(
        parse_run_id=run.id, source_document_id=src.id,
        full_text="hello", full_markdown="# hello",
        page_count=1, block_count=1, content={},
    )
    index = Index(
        id=uuid4(), project_id=project.id, name="ix",
        config={}, created_by=user.id,
    )
    test_db.add_all([parsed_doc, index])
    await test_db.commit()

    idoc = IndexDocument(
        index_id=index.id, document_id=document.id, parse_run_id=run.id,
    )
    test_db.add(idoc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(IndexDocument)
        .where(IndexDocument.index_id == index.id, IndexDocument.document_id == document.id)
        .options(selectinload(IndexDocument.parsed_document))
    )).scalar_one()
    assert fetched.parsed_document is not None
    assert fetched.parsed_document.parse_run_id == run.id
    assert fetched.parsed_document.full_markdown == "# hello"


@pytest.mark.asyncio
async def test_index_document_parsed_document_is_none_when_parse_run_id_is_null(
    test_db: AsyncSession,
):
    user = User(id=uuid4(), email="u2@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P2")
    test_db.add_all([user, project])
    await test_db.commit()

    document = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="legacy", title="L",
        source_metadata={}, status=DocumentStatus.ready,
    )
    index = Index(
        id=uuid4(), project_id=project.id, name="ix2",
        config={}, created_by=user.id,
    )
    test_db.add_all([document, index])
    await test_db.commit()

    idoc = IndexDocument(
        index_id=index.id, document_id=document.id, parse_run_id=None,
    )
    test_db.add(idoc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(IndexDocument)
        .where(IndexDocument.index_id == index.id)
        .options(selectinload(IndexDocument.parsed_document))
    )).scalar_one()
    assert fetched.parse_run_id is None
    assert fetched.parsed_document is None
