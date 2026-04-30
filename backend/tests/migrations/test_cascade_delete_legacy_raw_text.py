"""Test the Unit 3 cascade-delete-legacy-raw_text migration."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from datetime import datetime, timezone

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexStatus
from app.models.index_document import IndexDocument, IndexDocumentStatus
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


@pytest.mark.asyncio
async def test_cascade_delete_keeps_cdm_indexes_drops_raw_text_indexes(test_db: AsyncSession):
    user = User(email="m@example.com", password_hash="x", full_name="m", auth_provider="email")
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    project = Project(user_id=user.id, name="P")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    sd = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier="a",
        title="A",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)

    pr = ParseRun(
        source_document_id=sd.id,
        parser="llamaparse",
        representation_kind="full_text",
        config={},
        config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    test_db.add(pr)
    await test_db.commit()
    await test_db.refresh(pr)

    pd = ParsedDocument(
        parse_run_id=pr.id,
        source_document_id=sd.id,
        full_text="hello",
        full_markdown=None,
        page_count=1,
        block_count=1,
        content={"blocks": [{"text": "hello"}]},
    )
    test_db.add(pd)
    await test_db.commit()

    legacy_idx = Index(
        project_id=project.id,
        name="legacy-raw-text",
        config={"source_representation": "raw_text"},
        status=IndexStatus.created,
        created_by=user.id,
    )
    cdm_idx = Index(
        project_id=project.id,
        name="cdm-full-text",
        config={"source_representation": "full_text"},
        status=IndexStatus.created,
        created_by=user.id,
    )
    empty_idx = Index(
        project_id=project.id,
        name="no-docs-index",
        config={"source_representation": "full_text"},
        status=IndexStatus.created,
        created_by=user.id,
    )
    test_db.add_all([legacy_idx, cdm_idx, empty_idx])
    await test_db.commit()
    await test_db.refresh(legacy_idx)
    await test_db.refresh(cdm_idx)
    await test_db.refresh(empty_idx)

    legacy_doc = IndexDocument(
        index_id=legacy_idx.id,
        document_id=doc.id,
        processing_status=IndexDocumentStatus.completed,
        parse_run_id=None,  # legacy
    )
    cdm_doc = IndexDocument(
        index_id=cdm_idx.id,
        document_id=doc.id,
        processing_status=IndexDocumentStatus.completed,
        parse_run_id=pr.id,
    )
    test_db.add_all([legacy_doc, cdm_doc])
    await test_db.commit()

    # SQLite does not enforce FK CASCADE without `PRAGMA foreign_keys = ON`,
    # so this test only verifies the primary `indexes` row delete. Cascade to
    # index_documents/chunks/index_events is enforced by the FK definitions
    # in the model layer and is verified end-to-end against PostgreSQL when
    # the migration is applied to the dev/prod stack.

    # Run the migration's DELETE statement directly.
    await test_db.execute(
        text(
            """
            DELETE FROM indexes
            WHERE id IN (
                SELECT DISTINCT index_id FROM index_documents
                WHERE parse_run_id IS NULL
            )
            """
        )
    )
    await test_db.commit()

    legacy_after = await test_db.execute(
        select(Index).where(Index.id == legacy_idx.id)
    )
    cdm_after = await test_db.execute(
        select(Index).where(Index.id == cdm_idx.id)
    )
    empty_after = await test_db.execute(
        select(Index).where(Index.id == empty_idx.id)
    )

    assert legacy_after.scalar_one_or_none() is None, "legacy raw_text index should be deleted"
    assert cdm_after.scalar_one_or_none() is not None, "CDM index should survive"
    assert empty_after.scalar_one_or_none() is not None, "index with no documents should survive"
