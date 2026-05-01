"""Tests for GET/DELETE /projects/{project_id}/indexes/{index_id}/parsed-documents."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexStatus
from app.models.index_document import IndexDocument, IndexDocumentStatus
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


async def _signup(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email, "password": "ValidPass123!",
            "password_confirm": "ValidPass123!", "full_name": "T",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def _make_project(db: AsyncSession, user: User) -> Project:
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _seed_index_with_parsed_doc(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    sha: str = "a" * 64,
    filename: str = "acme-msa.pdf",
    chunks_created: int | None = None,
    status: IndexDocumentStatus = IndexDocumentStatus.pending,
) -> tuple[Index, IndexDocument, ParseRunORM, ParsedDocumentORM]:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf", filename=filename)
    db.add(sd)
    await db.commit()

    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)

    now = datetime.now(timezone.utc)
    run = ParseRunORM(
        source_document_id=sd.id, parser="llamaparse",
        representation_kind="full_markdown",
        config={"result_type": "markdown"}, config_hash="h" * 64,
        status="succeeded", started_at=now, finished_at=now,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    pd = ParsedDocumentORM(
        parse_run_id=run.id, source_document_id=sd.id,
        full_text="hello", full_markdown="# hi",
        page_count=1, block_count=2,
        content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)

    idx = Index(
        project_id=project.id, name="idx",
        config={
            "source_representation": "full_markdown",
            "parser": "llamaparse",
            "parse_config_hash": "h" * 64,
        },
        status=IndexStatus.created, created_by=user.id,
    )
    db.add(idx)
    await db.commit()
    await db.refresh(idx)

    idx_doc = IndexDocument(
        index_id=idx.id, document_id=doc.id,
        parse_run_id=run.id,
        processing_status=status,
        chunks_created=chunks_created,
    )
    db.add(idx_doc)
    await db.commit()
    await db.refresh(idx_doc)

    return idx, idx_doc, run, pd


@pytest.mark.asyncio
async def test_list_index_parsed_documents_returns_expected_fields(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx, idx_doc, run, _ = await _seed_index_with_parsed_doc(
        test_db, user=user, project=project, filename="acme-msa.pdf"
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["parseRunId"] == str(run.id)
    assert item["sourceFilename"] == "acme-msa.pdf"
    assert item["status"] == "pending"
    assert item["chunksCreated"] is None
    assert "parsedAt" in item


@pytest.mark.asyncio
async def test_list_index_parsed_documents_empty_when_no_docs(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx = Index(
        project_id=project.id, name="empty",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_index_parsed_documents_returns_404_for_unknown_index(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{uuid4()}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
